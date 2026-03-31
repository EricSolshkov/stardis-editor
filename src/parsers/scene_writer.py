"""
S7: 场景生成器 — SceneModel → .txt + STL 导出

生成 stardis 场景描述文件和边界 STL，保存项目文件。
"""

import os
import shutil
from typing import List

from models.scene_model import (
    SceneModel, Body, SurfaceZone, ImportedSTL, PaintedRegion,
    TemperatureBC, ConvectionBC, FluxBC, CombinedBC,
    SolidFluidConnection, SolidSolidConnection,
    BodyType, BoundaryType, Side, clone_volume,
    SceneLight, LightType,
)


class SceneWriter:
    """将 SceneModel 序列化为 stardis .txt + STL 文件。"""

    def save(self, model: SceneModel, output_dir: str, scene_filename: str = "scene.txt"):
        """
        保存完整场景到目标文件夹。

        产物:
          output_dir/
          ├── scene.txt
          ├── S_*.stl          (Body 几何拷贝)
          ├── B_*.stl          (边界 STL 拷贝或涂选导出)
          └── .stardis_project.json
        """
        os.makedirs(output_dir, exist_ok=True)
        scene_path = os.path.join(output_dir, scene_filename)

        # 1) 导出几何 STL（统一 ASCII 格式，命名 S_<body_name>.stl）
        body_rel = {}   # body_name → [rel_stl, ...]
        for body in model.bodies:
            rels = []
            for idx, stl in enumerate(body.stl_files):
                suffix = "" if idx == 0 else f"_{idx + 1}"
                dst_name = f"S_{body.name}{suffix}.stl"
                dst = os.path.join(output_dir, dst_name)
                self._export_stl_ascii(stl, dst)
                rels.append(dst_name)
            body_rel[body.name] = rels

        # 2) 导出边界 STL — 统一从 BoundaryLabel 按 zone_id 提取
        #    无论 source 是 ImportedSTL 还是 PaintedRegion，
        #    只要有 cell_ids 就从母体导出子网格，确保涂选持久化。
        zone_rel = {}   # (body_name, zone_name) → [rel_stl]
        for body in model.bodies:
            for zone in body.surface_zones:
                dst_name = f"B_{zone.name}.stl"
                dst = os.path.join(output_dir, dst_name)
                if isinstance(zone.source, PaintedRegion) and zone.source.cell_ids:
                    self._export_painted_zone(body, zone, dst)
                    zone_rel[(body.name, zone.name)] = [dst_name]
                elif isinstance(zone.source, ImportedSTL) and zone.source.stl_file:
                    # 未涂选过的区域：重新导出为 ASCII STL
                    self._export_stl_ascii(zone.source.stl_file, dst)
                    zone_rel[(body.name, zone.name)] = [dst_name]

        # 3) 写 scene.txt
        lines = self._generate_scene_txt(model, body_rel, zone_rel)
        with open(scene_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")

        # 4) 保存项目文件
        project_path = os.path.join(output_dir, ".stardis_project.json")
        model.save_project(project_path)

    # ─── 生成 scene.txt 内容 ─────────────────────────────────────

    def _generate_scene_txt(self, model, body_rel, zone_rel) -> List[str]:
        lines = []

        # TRAD / SCALE
        gs = model.global_settings
        lines.append(f"TRAD {gs.t_ambient} {gs.t_reference}")
        if gs.scale != 1.0:
            lines.append(f"SCALE {gs.scale}")
        lines.append("")

        # media
        lines.append("# media")
        for body in model.bodies:
            stls = " ".join(body_rel.get(body.name, []))
            lines.extend(self._body_lines(body, stls))
        lines.append("")

        # boundaries
        lines.append("# boundaries")
        for body in model.bodies:
            for zone in body.surface_zones:
                stls = " ".join(zone_rel.get((body.name, zone.name), []))
                lines.append(self._boundary_line(zone, stls))
        lines.append("")

        # connections
        if model.connections:
            lines.append("# connections")
            for conn in model.connections:
                lines.append(self._connection_line(conn))
            lines.append("")

        # spherical sources (only SPHERICAL_SOURCE and SPHERICAL_SOURCE_PROG)
        src_lights = [l for l in model.lights
                      if l.light_type in (LightType.SPHERICAL_SOURCE, LightType.SPHERICAL_SOURCE_PROG)]
        if src_lights:
            lines.append("# spherical sources")
            for light in src_lights:
                lines.append(self._spherical_source_line(light))
            lines.append("")

        return lines

    def _body_lines(self, body: Body, stl_str: str) -> List[str]:
        front_on = body.front_enabled
        back_on = body.back_enabled

        if front_on and back_on and body.sync_front_back:
            vol = clone_volume(body.front_volume)
            vol.side = Side.BOTH
            return [self._single_body_line(body.name, vol, stl_str)]

        lines = []
        if front_on:
            vol = clone_volume(body.front_volume)
            vol.side = Side.FRONT
            lines.append(self._single_body_line(body.name, vol, stl_str))
        if back_on:
            vol = clone_volume(body.back_volume)
            vol.side = Side.BACK
            lines.append(self._single_body_line(body.name, vol, stl_str))

        if not lines:
            # 异常兜底: 至少写一条 FRONT
            vol = clone_volume(body.front_volume or body.volume)
            vol.side = Side.FRONT
            lines.append(self._single_body_line(body.name, vol, stl_str))
        return lines

    def _single_body_line(self, name: str, v, stl_str: str) -> str:
        m = v.material
        delta_s = "AUTO" if v.delta is None else str(v.delta)
        imposed_s = "UNKNOWN" if v.imposed_temp is None else str(v.imposed_temp)

        if v.body_type == BodyType.SOLID:
            return (f"SOLID {name} {m.conductivity} {m.density} {m.specific_heat} "
                    f"{delta_s} {v.initial_temp} {imposed_s} {v.volumetric_power} "
                    f"{v.side.value} {stl_str}")
        return (f"FLUID {name} {m.density} {m.specific_heat} "
                f"{v.initial_temp} {imposed_s} {v.side.value} {stl_str}")

    def _boundary_line(self, zone: SurfaceZone, stl_str: str) -> str:
        bc = zone.boundary
        bt = zone.boundary_type.value

        if isinstance(bc, TemperatureBC):
            return f"{bt} {zone.name} {bc.temperature} {stl_str}"
        elif isinstance(bc, ConvectionBC):
            return (f"{bt} {zone.name} {bc.tref} {bc.emissivity} "
                    f"{bc.specular_fraction} {bc.hc} {bc.t_env} {stl_str}")
        elif isinstance(bc, FluxBC):
            return f"{bt} {zone.name} {bc.flux} {stl_str}"
        elif isinstance(bc, CombinedBC):
            return (f"{bt} {zone.name} {bc.tref} {bc.emissivity} "
                    f"{bc.specular_fraction} {bc.hc} {bc.t_env} {bc.flux} {stl_str}")
        return f"# UNKNOWN BOUNDARY {zone.name}"

    def _connection_line(self, conn) -> str:
        stls = " ".join(os.path.basename(s) for s in conn.stl_files)
        if isinstance(conn, SolidFluidConnection):
            return (f"SOLID_FLUID_CONNECTION {conn.name} {conn.tref} "
                    f"{conn.emissivity} {conn.specular_fraction} {conn.hc} {stls}")
        elif isinstance(conn, SolidSolidConnection):
            return f"SOLID_SOLID_CONNECTION {conn.name} {conn.contact_resistance} {stls}"
        return f"# UNKNOWN CONNECTION {conn.name}"

    def _spherical_source_line(self, light: SceneLight) -> str:
        if light.light_type == LightType.SPHERICAL_SOURCE_PROG:
            return light.raw_line
        p = light.position
        return (f"SPHERICAL_SOURCE {light.radius} "
                f"{p[0]} {p[1]} {p[2]} {light.power} {light.diffuse_radiance}")

    # ─── STL 导出 ────────────────────────────────────────────────

    def _export_painted_zone(self, body: Body, zone: SurfaceZone, output_path: str):
        """
        从涂选区域导出 STL。
        需要 VTK 支持 — 如果几何体 polydata 已加载则使用 vtkThreshold 提取。
        此处提供接口，实际导出由 viewport/surface_painter.py 执行。
        """
        try:
            import vtk
            if not body.stl_files:
                return
            # 加载母体
            reader = vtk.vtkSTLReader()
            reader.SetFileName(body.stl_files[0])
            reader.Update()
            poly = reader.GetOutput()

            if not isinstance(zone.source, PaintedRegion):
                return

            # 构建 BoundaryLabel 数组
            labels = vtk.vtkIntArray()
            labels.SetName("BoundaryLabel")
            labels.SetNumberOfTuples(poly.GetNumberOfCells())
            labels.Fill(0)
            for cid in zone.source.cell_ids:
                if cid < poly.GetNumberOfCells():
                    labels.SetValue(cid, 1)
            poly.GetCellData().AddArray(labels)

            # 提取 label==1
            threshold = vtk.vtkThreshold()
            threshold.SetInputData(poly)
            threshold.SetInputArrayToProcess(0, 0, 0,
                                             vtk.vtkDataObject.FIELD_ASSOCIATION_CELLS, "BoundaryLabel")
            threshold.SetLowerThreshold(1)
            threshold.SetUpperThreshold(1)
            threshold.Update()

            surface = vtk.vtkDataSetSurfaceFilter()
            surface.SetInputConnection(threshold.GetOutputPort())
            surface.Update()

            writer = vtk.vtkSTLWriter()
            writer.SetFileName(output_path)
            writer.SetInputConnection(surface.GetOutputPort())
            writer.SetFileTypeToASCII()
            writer.Write()
        except ImportError:
            pass  # VTK 不可用时跳过

    # ─── 工具 ────────────────────────────────────────────────────

    @staticmethod
    def _export_stl_ascii(src: str, dst: str):
        """读取任意格式 STL 并以 ASCII 格式重新写出。"""
        src_abs = os.path.abspath(src)
        dst_abs = os.path.abspath(dst)
        if not os.path.isfile(src_abs):
            return
        try:
            import vtk
            reader = vtk.vtkSTLReader()
            reader.SetFileName(src_abs)
            reader.Update()
            writer = vtk.vtkSTLWriter()
            writer.SetFileName(dst_abs)
            writer.SetInputConnection(reader.GetOutputPort())
            writer.SetFileTypeToASCII()
            writer.Write()
        except ImportError:
            # VTK 不可用时退回直接拷贝
            if src_abs != dst_abs:
                shutil.copy2(src_abs, dst_abs)

    @staticmethod
    def _copy_if_needed(src: str, dst: str):
        """如果源和目标不同且源存在，执行拷贝。"""
        src_abs = os.path.abspath(src)
        dst_abs = os.path.abspath(dst)
        if src_abs != dst_abs and os.path.isfile(src_abs):
            shutil.copy2(src_abs, dst_abs)
