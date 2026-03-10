"""
S4 + 集成: 场景编辑器主窗口

将场景树、3D 视口、属性面板连接为一个完整的编辑环境。
支持: 新建/打开/保存场景，双向选择联动，涂选模式。
"""

import sys
import os

from PyQt5.QtWidgets import (
    QMainWindow, QSplitter, QFileDialog, QMenuBar, QAction,
    QMessageBox, QApplication, QWidget, QVBoxLayout,
    QDialog, QFormLayout, QComboBox, QDialogButtonBox, QLabel,
)
from PyQt5.QtCore import Qt

# 确保 src/ 在路径上
sys.path.insert(0, os.path.dirname(__file__))

from models.scene_model import (
    SceneModel, Body, VolumeProperties, MaterialRef, SurfaceZone,
    Probe, ProbeType, BodyType, Side, ImportedSTL, PaintedRegion, IRCamera,
    SceneLight, LightType,
)
from panels.scene_tree_panel import SceneTreePanel
from panels.property_panel import PropertyPanel
from viewport.scene_viewport import SceneViewport
from parsers.scene_parser import SceneParser
from parsers.scene_writer import SceneWriter


class SceneEditor(QMainWindow):
    """Stardis 场景编辑器主窗口 (v2 geometry-centered)。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Stardis Scene Editor")
        self.resize(1400, 900)

        self._model = SceneModel()
        self._scene_file: str = ""   # 当前打开的 .txt 路径
        self._parser = SceneParser()
        self._writer = SceneWriter()

        self._build_ui()
        self._build_menus()
        self._connect_signals()
        self._refresh_all()

    # ─── UI 布局 ─────────────────────────────────────────────────

    def _build_ui(self):
        splitter = QSplitter(Qt.Horizontal, self)
        self.setCentralWidget(splitter)

        # 左: 场景树
        self._tree = SceneTreePanel()
        self._tree.setMinimumWidth(220)
        splitter.addWidget(self._tree)

        # 中: 3D 视口
        self._viewport = SceneViewport()
        splitter.addWidget(self._viewport)

        # 右: 属性面板
        self._props = PropertyPanel()
        self._props.setMinimumWidth(400)
        splitter.addWidget(self._props)

        splitter.setSizes([250, 700, 350])

    # ─── 菜单栏 ─────────────────────────────────────────────────

    def _build_menus(self):
        mb = self.menuBar()

        # 文件菜单
        file_menu = mb.addMenu("文件")

        new_act = QAction("新建场景", self)
        new_act.setShortcut("Ctrl+N")
        new_act.triggered.connect(self.new_scene)
        file_menu.addAction(new_act)

        open_act = QAction("打开场景 (.txt)...", self)
        open_act.setShortcut("Ctrl+O")
        open_act.triggered.connect(self.open_scene)
        file_menu.addAction(open_act)

        save_act = QAction("保存场景", self)
        save_act.setShortcut("Ctrl+S")
        save_act.triggered.connect(self.save_scene)
        file_menu.addAction(save_act)

        save_as_act = QAction("另存为...", self)
        save_as_act.setShortcut("Ctrl+Shift+S")
        save_as_act.triggered.connect(self.save_scene_as)
        file_menu.addAction(save_as_act)

        file_menu.addSeparator()
        exit_act = QAction("退出", self)
        exit_act.setShortcut("Ctrl+Q")
        exit_act.triggered.connect(self.close)
        file_menu.addAction(exit_act)

        # 场景菜单
        scene_menu = mb.addMenu("场景")

        add_body_act = QAction("添加几何体...", self)
        add_body_act.triggered.connect(self._on_add_body)
        scene_menu.addAction(add_body_act)

        validate_act = QAction("验证场景 (stub)", self)
        validate_act.triggered.connect(self._on_validate)
        scene_menu.addAction(validate_act)

    # ─── 信号连接 ────────────────────────────────────────────────

    def _connect_signals(self):
        tree = self._tree
        vp = self._viewport
        props = self._props

        # 场景树 → 视口 + 属性面板
        tree.body_selected.connect(self._on_tree_body_selected)
        tree.zone_selected.connect(self._on_tree_zone_selected)
        tree.connection_selected.connect(self._on_tree_conn_selected)
        tree.probe_selected.connect(self._on_tree_probe_selected)
        tree.global_selected.connect(self._on_tree_global_selected)
        tree.camera_selected.connect(self._on_tree_camera_selected)
        tree.light_selected.connect(self._on_tree_light_selected)
        tree.ambient_selected.connect(self._on_tree_ambient_selected)
        tree.selection_cleared.connect(self._on_tree_cleared)

        # 场景树右键操作
        tree.request_add_body.connect(self._on_add_body)
        tree.request_delete_body.connect(self._on_delete_body)
        tree.request_paint_mode.connect(self._on_enter_paint)
        tree.request_add_probe.connect(self._on_add_probe_manual)
        tree.request_delete_probe.connect(self._on_delete_probe)
        tree.request_delete_conn.connect(self._on_delete_conn)
        tree.request_add_camera_default.connect(self._on_add_camera_default)
        tree.request_add_camera_from_view.connect(self._on_add_camera_from_view)
        tree.request_delete_camera.connect(self._on_delete_camera)
        tree.request_apply_camera_to_view.connect(self._on_apply_camera_to_view)
        tree.request_add_default_light.connect(self._on_add_default_light)
        tree.request_add_spherical_source.connect(self._on_add_spherical_source)
        tree.request_add_spherical_source_prog.connect(self._on_add_spherical_source_prog)
        tree.request_delete_light.connect(self._on_delete_light)

        # 视口 → 场景树 + 属性面板
        vp.body_picked.connect(self._on_vp_body_picked)
        vp.probe_picked.connect(self._on_vp_probe_picked)
        vp.nothing_picked.connect(self._on_vp_nothing_picked)
        vp.probe_placed.connect(self._on_vp_probe_placed)
        vp.paint_changed.connect(self._on_paint_changed)
        vp.paint_mode_entered.connect(self._on_vp_paint_entered)

        # 属性面板
        props.request_paint_mode.connect(self._on_enter_paint)

        # 属性面板值变化 → 写回模型
        props.global_editor.property_changed.connect(lambda: self._apply_and_refresh_tree())
        props.body_editor.property_changed.connect(lambda: self._apply_and_refresh_tree())
        props.zone_editor.property_changed.connect(lambda: self._apply_and_refresh_tree())
        props.conn_editor.property_changed.connect(lambda: self._apply_and_refresh_tree())
        props.probe_editor.property_changed.connect(lambda: self._apply_and_refresh_tree())
        props.light_editor.property_changed.connect(lambda: self._apply_and_refresh_lights())
        props.ambient_editor.property_changed.connect(lambda: self._apply_and_refresh_ambient())

    # ─── 文件操作 ────────────────────────────────────────────────

    def new_scene(self):
        self._model = SceneModel()
        self._scene_file = ""
        self._refresh_all()
        self.setWindowTitle("Stardis Scene Editor - 新建场景")

    def open_scene(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "打开场景文件", "", "Stardis 场景 (*.txt);;所有文件 (*)")
        if not path:
            return
        self._parser = SceneParser()
        self._model = self._parser.parse_file(path)
        self._scene_file = path

        # 处理需要用户手动指定父体的边界
        if self._parser.unresolved_boundaries:
            self._resolve_boundary_parents()

        if self._parser.warnings:
            QMessageBox.warning(self, "解析警告",
                                "解析过程中发现以下问题:\n\n" +
                                "\n".join(self._parser.warnings[:20]))

        self._refresh_all()
        self.setWindowTitle(f"Stardis Scene Editor - {os.path.basename(path)}")

    def save_scene(self):
        if not self._scene_file:
            return self.save_scene_as()
        self._do_save(os.path.dirname(self._scene_file),
                      os.path.basename(self._scene_file))

    def save_scene_as(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "保存场景", "", "Stardis 场景 (*.txt)")
        if not path:
            return
        self._scene_file = path
        self._do_save(os.path.dirname(path), os.path.basename(path))
        self.setWindowTitle(f"Stardis Scene Editor - {os.path.basename(path)}")

    def _do_save(self, output_dir: str, filename: str):
        self._props.apply_current()
        self._writer.save(self._model, output_dir, filename)
        QMessageBox.information(self, "保存成功",
                                f"场景已保存到:\n{os.path.join(output_dir, filename)}")

    def _resolve_boundary_parents(self):
        """
        弹窗让用户为未匹配的边界 STL 选择父几何体。
        用户选择后，重新执行三角形哈希匹配来恢复 cell_ids。
        """
        body_names = [b.name for b in self._model.bodies]
        if not body_names:
            return

        unresolved = self._parser.unresolved_boundaries
        if not unresolved:
            return

        dlg = QDialog(self)
        dlg.setWindowTitle("指定边界归属")
        layout = QVBoxLayout(dlg)
        layout.addWidget(QLabel(
            "以下边界条件无法自动匹配到几何体，请为每个边界选择所属的父几何体："))

        form = QFormLayout()
        combos = {}
        for btype, bname, bc, stl_files in unresolved:
            combo = QComboBox()
            combo.addItems(body_names)
            # 尝试预选当前已临时归入的 body
            for body in self._model.bodies:
                if any(z.name == bname for z in body.surface_zones):
                    idx = body_names.index(body.name)
                    combo.setCurrentIndex(idx)
                    break
            form.addRow(f"{bname}:", combo)
            combos[bname] = combo
        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)
        layout.addWidget(buttons)

        if dlg.exec_() != QDialog.Accepted:
            return

        # 根据用户选择重新分配边界
        from parsers.triangle_hash_matcher import (
            load_stl_polydata, build_parent_hash_map, match_child_to_parent,
        )

        for btype, bname, bc, stl_files in unresolved:
            chosen_body_name = combos[bname].currentText()

            # 找到当前临时归属的 body 上的同名 zone
            old_body = None
            old_zone = None
            for body in self._model.bodies:
                for zone in body.surface_zones:
                    if zone.name == bname:
                        old_body = body
                        old_zone = zone
                        break
                if old_zone:
                    break

            new_body = self._model.get_body_by_name(chosen_body_name)
            if not new_body or not old_zone:
                continue

            # 如果需要移动到不同 body
            if old_body and old_body.name != chosen_body_name:
                old_body.surface_zones.remove(old_zone)
                old_zone.zone_id = new_body.allocate_zone_id()
                new_body.surface_zones.append(old_zone)

            # 三角形哈希匹配恢复 cell_ids
            if new_body.stl_files and stl_files:
                stl_path = stl_files[0]
                if os.path.isfile(stl_path) and os.path.isfile(new_body.stl_files[0]):
                    parent_poly = load_stl_polydata(new_body.stl_files[0])
                    child_poly = load_stl_polydata(stl_path)
                    cell_ids, unmatched = match_child_to_parent(parent_poly, child_poly)
                    if cell_ids:
                        old_zone.source = PaintedRegion(cell_ids=cell_ids)
                        if unmatched > 0:
                            self._parser.warnings.append(
                                f"区域 '{bname}': {unmatched} 个三角面未在父体 "
                                f"'{chosen_body_name}' 中找到匹配")

    # ─── 场景树选中 → 视口 + 属性面板 ────────────────────────────

    def _on_tree_body_selected(self, name):
        self._viewport.highlight_body(name)
        self._props.show_body(name)

    def _on_tree_zone_selected(self, body_name, zone_name):
        self._viewport.highlight_zone(body_name, zone_name)
        self._props.show_zone(body_name, zone_name)

    def _on_tree_conn_selected(self, name):
        self._viewport.clear_highlight()
        self._props.show_connection(name)

    def _on_tree_probe_selected(self, name):
        self._viewport.highlight_probe(name)
        self._props.show_probe(name)

    def _on_tree_global_selected(self):
        self._viewport.clear_highlight()
        self._props.show_global()

    def _on_tree_camera_selected(self, name):
        self._viewport.clear_highlight()
        self._props.show_camera(name)

    def _on_tree_cleared(self):
        self._viewport.clear_highlight()
        self._props.show_empty()

    # ─── 视口拾取 → 场景树 + 属性面板 ────────────────────────────

    def _on_vp_body_picked(self, name):
        self._tree.select_body(name)
        self._props.show_body(name)

    def _on_vp_probe_picked(self, name):
        self._tree.select_probe(name)
        self._props.show_probe(name)

    def _on_vp_nothing_picked(self):
        self._tree.clearSelection()
        self._props.show_empty()

    # ─── 探针 ────────────────────────────────────────────────────

    def _on_vp_probe_placed(self, body_name, x, y, z):
        """视口双击几何体 → 放置新探针。"""
        name = self._model.next_probe_name()
        probe = Probe(
            name=name,
            probe_type=ProbeType.VOLUME_TEMP,
            position=(x, y, z),
        )
        self._model.probes.append(probe)
        self._viewport.add_probe_visual(probe)
        self._tree.rebuild(self._model)
        self._tree.select_probe(name)
        self._props.show_probe(name)

    def _on_add_probe_manual(self):
        name = self._model.next_probe_name()
        probe = Probe(name=name, probe_type=ProbeType.VOLUME_TEMP, position=(0, 0, 0))
        self._model.probes.append(probe)
        self._viewport.add_probe_visual(probe)
        self._tree.rebuild(self._model)
        self._tree.select_probe(name)
        self._props.show_probe(name)

    def _on_delete_probe(self, name):
        self._model.probes = [p for p in self._model.probes if p.name != name]
        self._viewport.remove_probe_visual(name)
        self._tree.rebuild(self._model)
        self._props.show_empty()

    # ─── 几何体管理 ──────────────────────────────────────────────

    def _on_add_body(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self, "选择 STL 文件", "", "STL Files (*.stl)")
        if not paths:
            return
        for path in paths:
            basename = os.path.splitext(os.path.basename(path))[0]
            # 去除 S_ 前缀
            name = basename
            if name.lower().startswith("s_"):
                name = name[2:]
            name = name.upper()

            # 避免重名
            existing = {b.name for b in self._model.bodies}
            if name in existing:
                i = 2
                while f"{name}_{i}" in existing:
                    i += 1
                name = f"{name}_{i}"

            body = Body(
                name=name,
                stl_files=[path],
                volume=VolumeProperties(
                    body_type=BodyType.SOLID,
                    material=MaterialRef(conductivity=1.0, density=1.0, specific_heat=1.0),
                    side=Side.FRONT,
                ),
            )
            self._model.bodies.append(body)

        self._refresh_all()

    def _on_delete_body(self, name):
        self._model.bodies = [b for b in self._model.bodies if b.name != name]
        self._refresh_all()

    def _on_delete_conn(self, name):
        self._model.connections = [c for c in self._model.connections if c.name != name]
        self._refresh_all()

    # ─── 摄像机管理 ──────────────────────────────────────────────

    def _on_add_camera_default(self):
        """添加默认参数摄像机。"""
        name = self._model.next_camera_name()
        cam = IRCamera(name=name)
        self._model.cameras.append(cam)
        self._tree.rebuild(self._model)
        self._props.show_camera(name)

    def _on_add_camera_from_view(self):
        """根据当前视口视角创建摄像机。"""
        name = self._model.next_camera_name()
        pos, target, up, fov = self._viewport.get_current_view_camera_params()
        cam = IRCamera(name=name, position=pos, target=target, up=up, fov=fov)
        self._model.cameras.append(cam)
        self._tree.rebuild(self._model)
        self._props.show_camera(name)

    def _on_delete_camera(self, name):
        self._model.cameras = [c for c in self._model.cameras if c.name != name]
        self._tree.rebuild(self._model)
        self._props.show_empty()

    # ─── 光源管理 ────────────────────────────────────────────────

    def _on_tree_light_selected(self, name):
        self._viewport.clear_highlight()
        self._props.show_light(name)

    def _on_tree_ambient_selected(self):
        self._viewport.clear_highlight()
        self._props.show_ambient()

    def _on_add_default_light(self):
        """添加默认光源。"""
        name = self._model.next_light_name("DefaultLight")
        light = SceneLight(name=name, light_type=LightType.DEFAULT)
        self._model.lights.append(light)
        self._sync_lights_and_rebuild()
        self._props.show_light(name)

    def _on_add_spherical_source(self):
        """添加常量球面源。添加时禁用所有默认光源。"""
        name = self._model.next_light_name("SphericalSource")
        light = SceneLight(
            name=name,
            light_type=LightType.SPHERICAL_SOURCE,
            radius=1.0,
            position=(1.0, 1.0, 1.0),
            power=1.0,
            diffuse_radiance=0.0,
        )
        # 禁用所有默认光源
        for l in self._model.lights:
            if l.light_type == LightType.DEFAULT:
                l.enabled = False
        self._model.lights.append(light)
        self._sync_lights_and_rebuild()
        self._props.show_light(name)

    def _on_add_spherical_source_prog(self):
        """添加可编程球面源（占位，需手动编辑原始行）。"""
        name = self._model.next_light_name("SphericalSourceProg")
        light = SceneLight(
            name=name,
            light_type=LightType.SPHERICAL_SOURCE_PROG,
            raw_line="SPHERICAL_SOURCE_PROG 1.0 prog_name PROG_PARAMS",
        )
        self._model.lights.append(light)
        self._sync_lights_and_rebuild()
        self._props.show_light(name)

    def _on_delete_light(self, name):
        """删除光源。若删除后无光源则自动创建默认光源。"""
        self._model.lights = [l for l in self._model.lights if l.name != name]
        self._model.ensure_default_light()
        self._sync_lights_and_rebuild()
        self._props.show_empty()

    def _sync_lights_and_rebuild(self):
        """同步光源到视口并刷新场景树。"""
        self._viewport.sync_lights(self._model.lights)
        self._tree.rebuild(self._model)

    def _apply_and_refresh_lights(self):
        """光源属性变化后写回模型并同步视口。"""
        self._props.apply_current()
        self._viewport.sync_lights(self._model.lights)
        self._tree.rebuild(self._model)

    def _apply_and_refresh_ambient(self):
        """环境光照强度变化后写回模型并同步视口。"""
        self._props.apply_current()
        self._viewport.set_ambient_intensity(self._model.ambient_intensity)
        self._tree.rebuild(self._model)

    def _on_apply_camera_to_view(self, name):
        """双击摄像机节点 → 将该摄像机参数应用到视口。"""
        cam = self._model.get_camera_by_name(name)
        if cam:
            self._viewport.apply_camera_to_view(cam.position, cam.target, cam.up, cam.fov)

    # ─── 涂选 ────────────────────────────────────────────────────

    def _on_enter_paint(self, body_name):
        self._viewport.enter_paint_mode(body_name)

    def _on_vp_paint_entered(self, body_name):
        """视口双击进入涂选模式 → 同步树和属性面板。"""
        self._tree.select_body(body_name)
        self._props.show_body(body_name)

    def _on_paint_changed(self, body_name, zone_dict):
        """涂选结果写回模型后刷新树。"""
        self._tree.rebuild(self._model)

    # ─── 验证 (stub) ────────────────────────────────────────────

    def _on_validate(self):
        ok, msgs = self._model.validate()
        if ok:
            QMessageBox.information(self, "验证结果", "✅ 场景验证通过 (stub)")
        else:
            QMessageBox.warning(self, "验证结果", "\n".join(msgs))

    # ─── 刷新 ────────────────────────────────────────────────────

    def _refresh_all(self):
        self._props.set_model(self._model)
        self._tree.rebuild(self._model)
        self._viewport.load_scene(self._model)
        self._props.show_empty()

    def _apply_and_refresh_tree(self):
        """属性面板值变化后写回模型并刷新树。"""
        self._props.apply_current()
        self._tree.rebuild(self._model)


# ─── 入口 ────────────────────────────────────────────────────────

def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Stardis Scene Editor")
    editor = SceneEditor()
    editor.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
