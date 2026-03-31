"""
S8: 场景解析器 — .txt → SceneModel

支持:
- TRAD / SCALE
- SOLID / FLUID
- T_BOUNDARY_FOR_SOLID / H_BOUNDARY_FOR_SOLID / F_BOUNDARY_FOR_SOLID / HF_BOUNDARY_FOR_SOLID
- SOLID_FLUID_CONNECTION / SOLID_SOLID_CONNECTION
- 注释 (#) 保留
- 边界→几何体匹配 (zone_parent_map 优先 / 文件名启发式回退)
- 三角形哈希匹配恢复涂选状态
- 项目文件 (.stardis_project.json) 加载
"""

import json
import os
import re
from typing import List, Tuple, Optional, Dict

from models.scene_model import (
    SceneModel, GlobalSettings, Body, VolumeProperties, MaterialRef,
    SurfaceZone, ImportedSTL, PaintedRegion,
    TemperatureBC, ConvectionBC, FluxBC, CombinedBC,
    SolidFluidConnection, SolidSolidConnection,
    BodyType, Side, BoundaryType,
    SceneLight, LightType,
    NormalOrientation, detect_normal_orientation,
    clone_volume,
)
from parsers.triangle_hash_matcher import (
    load_stl_polydata, build_parent_hash_map, match_child_to_parent,
)


class SceneParser:
    """将 stardis .txt 场景文件解析为 SceneModel。"""

    def __init__(self):
        self.warnings: List[str] = []
        self.comments: List[Tuple[int, str]] = []
        # 需要用户手动指定父体的边界列表 (无 JSON 且启发式失败时)
        self.unresolved_boundaries: List[Tuple[BoundaryType, str, object, List[str]]] = []

    def parse_file(self, filepath: str) -> SceneModel:
        """解析 .txt 文件并返回 SceneModel。"""
        self.warnings.clear()
        self.comments.clear()
        self.unresolved_boundaries.clear()

        base_dir = os.path.dirname(os.path.abspath(filepath))
        with open(filepath, "r", encoding="utf-8") as f:
            lines = f.readlines()

        model = SceneModel()
        # 临时：平面边界列表（解析后再匹配到 Body）
        flat_boundaries: List[Tuple[BoundaryType, str, object, List[str]]] = []

        for lineno, raw_line in enumerate(lines, start=1):
            line = raw_line.strip()
            if not line:
                continue
            if line.startswith("#"):
                self.comments.append((lineno, line))
                continue

            tokens = line.split()
            keyword = tokens[0].upper()

            try:
                if keyword == "TRAD":
                    model.global_settings.t_ambient = float(tokens[1])
                    model.global_settings.t_reference = float(tokens[2])

                elif keyword == "SCALE":
                    model.global_settings.scale = float(tokens[1])

                elif keyword == "SOLID":
                    name, stl_files, vol = self._parse_solid(tokens, base_dir)
                    self._upsert_media_body(model, name, stl_files, vol)

                elif keyword == "FLUID":
                    name, stl_files, vol = self._parse_fluid(tokens, base_dir)
                    self._upsert_media_body(model, name, stl_files, vol)

                elif keyword == "T_BOUNDARY_FOR_SOLID":
                    flat_boundaries.append(self._parse_t_boundary(tokens, base_dir))

                elif keyword == "H_BOUNDARY_FOR_SOLID":
                    flat_boundaries.append(self._parse_h_boundary(tokens, base_dir))

                elif keyword == "F_BOUNDARY_FOR_SOLID":
                    flat_boundaries.append(self._parse_f_boundary(tokens, base_dir))

                elif keyword == "HF_BOUNDARY_FOR_SOLID":
                    flat_boundaries.append(self._parse_hf_boundary(tokens, base_dir))

                elif keyword == "SOLID_FLUID_CONNECTION":
                    model.connections.append(self._parse_sf_connection(tokens, base_dir))

                elif keyword == "SOLID_SOLID_CONNECTION":
                    model.connections.append(self._parse_ss_connection(tokens, base_dir))

                elif keyword == "SPHERICAL_SOURCE":
                    model.lights.append(self._parse_spherical_source(tokens))

                elif keyword == "SPHERICAL_SOURCE_PROG":
                    model.lights.append(self._parse_spherical_source_prog(line))

                else:
                    self.warnings.append(f"第 {lineno} 行: 未知关键字 '{keyword}'")
            except Exception as e:
                self.warnings.append(f"第 {lineno} 行解析出错: {e}")

        # 加载伴随项目文件中的 zone_parent_map (用于确定性匹配)
        project_file = os.path.join(base_dir, ".stardis_project.json")
        zone_parent_map = self._load_zone_parent_map(project_file)

        # 将边界匹配到 Body
        self._assign_boundaries_to_bodies(model, flat_boundaries, zone_parent_map)

        # 如果场景文件中定义了常量球面源，移除 __post_init__ 创建的默认光源
        has_spherical = any(l.light_type == LightType.SPHERICAL_SOURCE for l in model.lights)
        if has_spherical:
            model.lights = [l for l in model.lights if l.light_type != LightType.DEFAULT]

        # 加载伴随项目文件 (探针、摄像机、光源、zone_id)
        model.load_project(project_file)

        # 法线朝向自动检测：对仍为 UNKNOWN 的 Body 尝试检测
        for body in model.bodies:
            if body.normal_orientation == NormalOrientation.UNKNOWN and body.stl_files:
                body.normal_orientation = detect_normal_orientation(body.stl_files[0])

        # 三角形哈希匹配：从 B_*.stl 恢复涂选状态 (cell_ids)
        self._recover_paint_state_by_hash(model)

        # 确保至少有一个参与光照的光源
        model.ensure_default_light()

        return model

    # ─── SOLID ───────────────────────────────────────────────────

    def _parse_solid(self, tokens: List[str], base_dir: str):
        # SOLID <name> <λ> <ρ> <cp> <δ|AUTO> <T_init> <T_imposed|UNKNOWN> <power> <FRONT|BACK|BOTH> <stl...>
        name = tokens[1]
        lam = float(tokens[2])
        rho = float(tokens[3])
        cp = float(tokens[4])
        delta = None if tokens[5].upper() == "AUTO" else float(tokens[5])
        t_init = float(tokens[6])
        t_imposed = None if tokens[7].upper() == "UNKNOWN" else float(tokens[7])
        power = float(tokens[8])
        side = Side[tokens[9].upper()]
        stl_files = [self._resolve_path(t, base_dir) for t in tokens[10:]]

        return (
            name,
            stl_files,
            VolumeProperties(
                body_type=BodyType.SOLID,
                material=MaterialRef(conductivity=lam, density=rho, specific_heat=cp),
                delta=delta,
                initial_temp=t_init,
                imposed_temp=t_imposed,
                volumetric_power=power,
                side=side,
            )
        )

    # ─── FLUID ───────────────────────────────────────────────────

    def _parse_fluid(self, tokens: List[str], base_dir: str):
        # FLUID <name> <ρ> <cp> <T_init> <T_imposed|UNKNOWN> <FRONT|BACK|BOTH> <stl...>
        name = tokens[1]
        rho = float(tokens[2])
        cp = float(tokens[3])
        t_init = float(tokens[4])
        t_imposed = None if tokens[5].upper() == "UNKNOWN" else float(tokens[5])
        side = Side[tokens[6].upper()]
        stl_files = [self._resolve_path(t, base_dir) for t in tokens[7:]]

        return (
            name,
            stl_files,
            VolumeProperties(
                body_type=BodyType.FLUID,
                material=MaterialRef(conductivity=0.0, density=rho, specific_heat=cp),
                delta=None,
                initial_temp=t_init,
                imposed_temp=t_imposed,
                volumetric_power=0.0,
                side=side,
            )
        )

    def _upsert_media_body(self, model: SceneModel, name: str, stl_files: List[str], vol: VolumeProperties):
        """将一条 SOLID/FLUID 媒介定义合并到同名 Body 的 FRONT/BACK 结构中。"""
        body = model.get_body_by_name(name)
        if body is None:
            body = Body(name=name, stl_files=stl_files, volume=clone_volume(vol))
            body.front_enabled = False
            body.back_enabled = False
            body.sync_front_back = False
            model.bodies.append(body)
        elif not body.stl_files and stl_files:
            body.stl_files = stl_files

        if vol.side == Side.BOTH:
            body.front_volume = clone_volume(vol)
            body.back_volume = clone_volume(vol)
            body.front_enabled = True
            body.back_enabled = True
            body.sync_front_back = True
        elif vol.side == Side.FRONT:
            body.front_volume = clone_volume(vol)
            body.front_enabled = True
            body.sync_front_back = False
        else:
            body.back_volume = clone_volume(vol)
            body.back_enabled = True
            body.sync_front_back = False

        if body.front_volume is None and body.back_volume is not None:
            body.front_volume = clone_volume(body.back_volume)
        if body.back_volume is None and body.front_volume is not None:
            body.back_volume = clone_volume(body.front_volume)

        body._refresh_legacy_volume_view()

    # ─── 边界条件 ────────────────────────────────────────────────

    def _parse_t_boundary(self, tokens, base_dir):
        # T_BOUNDARY_FOR_SOLID <name> <temperature> <stl...>
        name = tokens[1]
        temp = float(tokens[2])
        stls = [self._resolve_path(t, base_dir) for t in tokens[3:]]
        return (BoundaryType.T_BOUNDARY, name, TemperatureBC(temperature=temp), stls)

    def _parse_h_boundary(self, tokens, base_dir):
        # H_BOUNDARY_FOR_SOLID <name> <Tref> <ε> <spec> <hc> <T_env> <stl...>
        name = tokens[1]
        tref = float(tokens[2])
        emi = float(tokens[3])
        spec = float(tokens[4])
        hc = float(tokens[5])
        t_env = float(tokens[6])
        stls = [self._resolve_path(t, base_dir) for t in tokens[7:]]
        return (BoundaryType.H_BOUNDARY, name,
                ConvectionBC(tref=tref, emissivity=emi, specular_fraction=spec, hc=hc, t_env=t_env), stls)

    def _parse_f_boundary(self, tokens, base_dir):
        # F_BOUNDARY_FOR_SOLID <name> <flux> <stl...>
        name = tokens[1]
        flux = float(tokens[2])
        stls = [self._resolve_path(t, base_dir) for t in tokens[3:]]
        return (BoundaryType.F_BOUNDARY, name, FluxBC(flux=flux), stls)

    def _parse_hf_boundary(self, tokens, base_dir):
        # HF_BOUNDARY_FOR_SOLID <name> <Tref> <ε> <spec> <hc> <T_env> <flux> <stl...>
        name = tokens[1]
        tref = float(tokens[2])
        emi = float(tokens[3])
        spec = float(tokens[4])
        hc = float(tokens[5])
        t_env = float(tokens[6])
        flux = float(tokens[7])
        stls = [self._resolve_path(t, base_dir) for t in tokens[8:]]
        return (BoundaryType.HF_BOUNDARY, name,
                CombinedBC(tref=tref, emissivity=emi, specular_fraction=spec, hc=hc, t_env=t_env, flux=flux), stls)

    # ─── 连接 ────────────────────────────────────────────────────

    def _parse_sf_connection(self, tokens, base_dir):
        # SOLID_FLUID_CONNECTION <name> <Tref> <ε> <spec> <hc> <stl...>
        name = tokens[1]
        tref = float(tokens[2])
        emi = float(tokens[3])
        spec = float(tokens[4])
        hc = float(tokens[5])
        stls = [self._resolve_path(t, base_dir) for t in tokens[6:]]
        return SolidFluidConnection(
            name=name, tref=tref, emissivity=emi, specular_fraction=spec, hc=hc,
            stl_files=stls,
        )

    def _parse_ss_connection(self, tokens, base_dir):
        # SOLID_SOLID_CONNECTION <name> <resistance> <stl...>
        name = tokens[1]
        resistance = float(tokens[2])
        stls = [self._resolve_path(t, base_dir) for t in tokens[3:]]
        return SolidSolidConnection(
            name=name, contact_resistance=resistance, stl_files=stls,
        )

    # ─── 球面源光源 ─────────────────────────────────────────────

    def _parse_spherical_source(self, tokens):
        # SPHERICAL_SOURCE radius position_x position_y position_z power diffuse_radiance
        radius = float(tokens[1])
        px, py, pz = float(tokens[2]), float(tokens[3]), float(tokens[4])
        power = float(tokens[5])
        diffuse_radiance = float(tokens[6])
        # 自动命名
        name = f"SphericalSource"
        return SceneLight(
            name=name,
            light_type=LightType.SPHERICAL_SOURCE,
            radius=radius,
            position=(px, py, pz),
            power=power,
            diffuse_radiance=diffuse_radiance,
        )

    def _parse_spherical_source_prog(self, raw_line: str):
        # SPHERICAL_SOURCE_PROG radius prog_name PROG_PARAMS args...
        # 原样读入，原样输出
        tokens = raw_line.split()
        radius = float(tokens[1])
        name = tokens[2] if len(tokens) > 2 else "ProgSource"
        return SceneLight(
            name=name,
            light_type=LightType.SPHERICAL_SOURCE_PROG,
            radius=radius,
            raw_line=raw_line.strip(),
        )

    # ─── 边界→Body 匹配 ─────────────────────────────────────────

    @staticmethod
    def _load_zone_parent_map(project_file: str) -> Dict[str, str]:
        """从 .stardis_project.json 加载 zone_name → parent_body_name 映射。"""
        if not os.path.isfile(project_file):
            return {}
        try:
            with open(project_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data.get("zone_parent_map", {})
        except Exception:
            return {}

    def _assign_boundaries_to_bodies(self, model: SceneModel, flat_boundaries,
                                     zone_parent_map: Dict[str, str]):
        """
        将平面边界列表匹配到 Body 的 surface_zones。
        优先策略: zone_parent_map（确定性），回退: 文件名启发式。
        无 JSON 且启发式失败时，收集到 unresolved_boundaries 待用户交互。
        """
        has_parent_map = bool(zone_parent_map)

        for btype, bname, bc, stl_files in flat_boundaries:
            target_body = None

            # 策略 1: zone_parent_map 确定性匹配
            if bname in zone_parent_map:
                parent_name = zone_parent_map[bname]
                target_body = model.get_body_by_name(parent_name)
                if target_body is None:
                    self.warnings.append(
                        f"边界 '{bname}' 的父体 '{parent_name}' 不存在，回退到启发式匹配")

            # 策略 2: 文件名启发式
            if target_body is None:
                target_body = self._match_boundary_to_body(stl_files, model.bodies)

            # 策略 3: 单 Body 时全部归入
            if target_body is None:
                if len(model.bodies) == 1:
                    target_body = model.bodies[0]
                elif model.bodies and not has_parent_map:
                    # 无 JSON: 收集待用户交互
                    self.unresolved_boundaries.append((btype, bname, bc, stl_files))
                    # 临时归入第一个 body，后续由编辑器弹窗让用户重新分配
                    target_body = model.bodies[0]
                    self.warnings.append(
                        f"边界 '{bname}' 无法自动匹配到几何体（无项目文件），已临时归入 '{target_body.name}'")
                elif model.bodies:
                    target_body = model.bodies[0]
                    self.warnings.append(
                        f"边界 '{bname}' 无法自动匹配到几何体，已归入 '{target_body.name}'")
                else:
                    self.warnings.append(f"边界 '{bname}' 无可归属几何体，已忽略")
                    continue

            zone = SurfaceZone(
                zone_id=target_body.allocate_zone_id(),
                name=bname,
                source=ImportedSTL(stl_file=stl_files[0] if stl_files else ""),
                boundary_type=btype,
                boundary=bc,
            )
            target_body.surface_zones.append(zone)

    def _recover_paint_state_by_hash(self, model: SceneModel):
        """
        三角形哈希匹配：将 ImportedSTL 的 B_*.stl 与父 Body STL 比对，
        恢复 cell_ids 并转换 source 为 PaintedRegion。
        """
        for body in model.bodies:
            if not body.stl_files or not os.path.isfile(body.stl_files[0]):
                continue

            parent_poly = None  # 惰性加载
            parent_hash_map = None

            for zone in body.surface_zones:
                if not isinstance(zone.source, ImportedSTL):
                    continue
                stl_file = zone.source.stl_file
                if not stl_file or not os.path.isfile(stl_file):
                    continue

                # 惰性加载父体
                if parent_poly is None:
                    parent_poly = load_stl_polydata(body.stl_files[0])
                    parent_hash_map = build_parent_hash_map(parent_poly)

                child_poly = load_stl_polydata(stl_file)
                if child_poly.GetNumberOfCells() == 0:
                    continue

                cell_ids, unmatched = match_child_to_parent(
                    parent_poly, child_poly,
                    parent_hash_map=parent_hash_map)

                if cell_ids:
                    zone.source = PaintedRegion(cell_ids=cell_ids)
                    if unmatched > 0:
                        self.warnings.append(
                            f"区域 '{zone.name}': {unmatched} 个三角面未在父体 "
                            f"'{body.name}' 中找到匹配")
                elif unmatched > 0:
                    self.warnings.append(
                        f"区域 '{zone.name}' 的所有三角面均未在父体 "
                        f"'{body.name}' 中找到匹配，可能选错了父几何体")

    def _match_boundary_to_body(self, boundary_stls: List[str], bodies: List[Body]) -> Optional[Body]:
        """文件名启发式: 检查边界 STL 名称是否包含 Body STL 的核心部分。"""
        if len(bodies) <= 1:
            return bodies[0] if bodies else None

        for bstl in boundary_stls:
            bname_lower = os.path.basename(bstl).lower()
            for body in bodies:
                for body_stl in body.stl_files:
                    # 从 S_walls.stl → walls
                    base = os.path.basename(body_stl).lower()
                    core = re.sub(r'^s_', '', base)
                    core = core.replace('.stl', '')
                    if core and core in bname_lower:
                        return body
        return None

    # ─── 工具 ────────────────────────────────────────────────────

    @staticmethod
    def _resolve_path(token: str, base_dir: str) -> str:
        """将场景文件中的相对路径解析为绝对路径。"""
        if os.path.isabs(token):
            return token
        return os.path.normpath(os.path.join(base_dir, token))
