"""
S2: 场景树面板

以几何体为中心的只读树形显示，支持选择信号发射。
"""

from PyQt5.QtWidgets import QTreeWidget, QTreeWidgetItem, QMenu, QAction, QAbstractItemView
from PyQt5.QtCore import pyqtSignal, Qt
from PyQt5.QtGui import QIcon, QColor, QBrush
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from models.scene_model import (
    SceneModel, Body, SurfaceZone, BoundaryType, BodyType,
    SolidFluidConnection, SolidSolidConnection, Probe, ProbeType,
    IRCamera, BOUNDARY_TYPE_LABELS,
    SceneLight, LightType,
)


# ─── 节点角色常量 ────────────────────────────────────────────────

ROLE_NODE_TYPE = Qt.UserRole + 1
ROLE_NODE_NAME = Qt.UserRole + 2
ROLE_BODY_NAME = Qt.UserRole + 3   # 用于 SurfaceZone 归属

NODE_GLOBAL   = "global"
NODE_BODY_GRP = "body_group"
NODE_BODY     = "body"
NODE_ZONE     = "zone"
NODE_CONN_GRP = "conn_group"
NODE_CONN     = "connection"
NODE_PROBE_GRP = "probe_group"
NODE_PROBE    = "probe"
NODE_CAM_GRP  = "camera_group"
NODE_CAMERA   = "camera"
NODE_LIGHT_GRP = "light_group"
NODE_LIGHT     = "light"
NODE_AMBIENT   = "ambient"


# ─── 边界类型→颜色 ──────────────────────────────────────────────

_ZONE_COLORS = {
    BoundaryType.T_BOUNDARY:  QColor(50, 100, 230),
    BoundaryType.H_BOUNDARY:  QColor(230, 75, 25),
    BoundaryType.F_BOUNDARY:  QColor(50, 200, 75),
    BoundaryType.HF_BOUNDARY: QColor(180, 50, 200),
}


class SceneTreePanel(QTreeWidget):
    """几何中心场景树面板"""

    # ─── 信号 ────────────────────────────────────────────────────
    body_selected       = pyqtSignal(str)
    zone_selected       = pyqtSignal(str, str)
    connection_selected = pyqtSignal(str)
    probe_selected      = pyqtSignal(str)
    global_selected     = pyqtSignal()
    camera_selected     = pyqtSignal(str)
    light_selected      = pyqtSignal(str)
    ambient_selected    = pyqtSignal()
    selection_cleared   = pyqtSignal()

    request_add_body    = pyqtSignal()          # 右键「添加几何体」
    request_delete_body = pyqtSignal(str)
    request_paint_mode  = pyqtSignal(str)       # 右键「涂选编辑」
    request_add_probe   = pyqtSignal()
    request_delete_probe = pyqtSignal(str)
    request_delete_conn  = pyqtSignal(str)
    request_add_camera_default = pyqtSignal()      # 添加默认参数摄像机
    request_add_camera_from_view = pyqtSignal()    # 根据当前视角创建摄像机
    request_delete_camera = pyqtSignal(str)
    request_apply_camera_to_view = pyqtSignal(str) # 双击摄像机→应用到视角
    request_add_default_light = pyqtSignal()
    request_add_spherical_source = pyqtSignal()
    request_add_spherical_source_prog = pyqtSignal()
    request_delete_light = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setHeaderHidden(True)
        self.setSelectionMode(QAbstractItemView.SingleSelection)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._on_context_menu)
        self.currentItemChanged.connect(self._on_current_changed)
        self.itemDoubleClicked.connect(self._on_item_double_clicked)
        self._model: SceneModel = SceneModel()

    # ─── 从 SceneModel 重建树 ────────────────────────────────────

    def rebuild(self, model: SceneModel):
        self._model = model
        self.blockSignals(True)
        self.clear()

        # 1) 全局设置
        gl = self._make_item(
            f"🌐 全局设置  TRAD {model.global_settings.t_ambient}/{model.global_settings.t_reference}  "
            f"SCALE {model.global_settings.scale}",
            NODE_GLOBAL, ""
        )
        self.addTopLevelItem(gl)

        # 2) 几何体组
        body_grp = self._make_item(f"🧊 几何体 ({len(model.bodies)})", NODE_BODY_GRP, "")
        self.addTopLevelItem(body_grp)
        for body in model.bodies:
            btype = body.volume.body_type.value
            b_item = self._make_item(f"{body.name} [{btype}]", NODE_BODY, body.name)
            body_grp.addChild(b_item)
            for zone in body.surface_zones:
                label = BOUNDARY_TYPE_LABELS.get(zone.boundary_type, "?")
                z_item = self._make_item(f"{zone.name} [{label}]", NODE_ZONE, zone.name)
                z_item.setData(0, ROLE_BODY_NAME, body.name)
                color = _ZONE_COLORS.get(zone.boundary_type, QColor(160, 160, 160))
                z_item.setForeground(0, QBrush(color))
                b_item.addChild(z_item)
        body_grp.setExpanded(True)

        # 3) 连接组
        conn_grp = self._make_item(f"🔗 连接 ({len(model.connections)})", NODE_CONN_GRP, "")
        self.addTopLevelItem(conn_grp)
        for conn in model.connections:
            ctype = "固流" if isinstance(conn, SolidFluidConnection) else "固固"
            c_item = self._make_item(f"{conn.name} [{ctype}]", NODE_CONN, conn.name)
            conn_grp.addChild(c_item)

        # 4) 探针组
        probe_grp = self._make_item(f"📍 探针 ({len(model.probes)})", NODE_PROBE_GRP, "")
        self.addTopLevelItem(probe_grp)
        for probe in model.probes:
            plabel = {
                ProbeType.VOLUME_TEMP: "体积温度",
                ProbeType.SURFACE_TEMP: "表面温度",
                ProbeType.SURFACE_FLUX: "表面通量",
            }.get(probe.probe_type, "?")
            pos = probe.position
            p_item = self._make_item(
                f"📍 {probe.name} [{plabel}] ({pos[0]:.2f}, {pos[1]:.2f}, {pos[2]:.2f})",
                NODE_PROBE, probe.name
            )
            probe_grp.addChild(p_item)

        # 5) 摄像机组
        cam_grp = self._make_item(f"📷 摄像机 ({len(model.cameras)})", NODE_CAM_GRP, "")
        self.addTopLevelItem(cam_grp)
        for cam in model.cameras:
            cam_item = self._make_item(f"{cam.name}", NODE_CAMERA, cam.name)
            cam_grp.addChild(cam_item)

        # 6) 光源组
        light_grp = self._make_item(f"💡 光源 ({len(model.lights)})", NODE_LIGHT_GRP, "")
        self.addTopLevelItem(light_grp)
        # 环境基本光照（恒存在）
        amb_item = self._make_item(
            f"☀ 环境光照 (强度 {model.ambient_intensity:.2f})",
            NODE_AMBIENT, "ambient")
        light_grp.addChild(amb_item)
        for light in model.lights:
            _ltype_labels = {
                LightType.DEFAULT: "默认",
                LightType.SPHERICAL_SOURCE: "常量球面源",
                LightType.SPHERICAL_SOURCE_PROG: "可编程球面源",
            }
            ltype = _ltype_labels.get(light.light_type, "?")
            enabled = "" if light.enabled else " [已禁用]"
            l_item = self._make_item(f"{light.name} [{ltype}]{enabled}", NODE_LIGHT, light.name)
            if not light.enabled:
                l_item.setForeground(0, QBrush(QColor(120, 120, 120)))
            light_grp.addChild(l_item)

        self.blockSignals(False)
        self.expandAll()

    # ─── 同步选中 ────────────────────────────────────────────────

    def select_body(self, name: str):
        item = self._find_item(NODE_BODY, name)
        if item:
            self.setCurrentItem(item)

    def select_zone(self, body_name: str, zone_name: str):
        item = self._find_zone_item(body_name, zone_name)
        if item:
            self.setCurrentItem(item)

    def select_probe(self, name: str):
        item = self._find_item(NODE_PROBE, name)
        if item:
            self.setCurrentItem(item)

    # ─── 内部 ────────────────────────────────────────────────────

    def _make_item(self, text: str, node_type: str, node_name: str) -> QTreeWidgetItem:
        item = QTreeWidgetItem([text])
        item.setData(0, ROLE_NODE_TYPE, node_type)
        item.setData(0, ROLE_NODE_NAME, node_name)
        return item

    def _on_current_changed(self, current, _previous):
        if current is None:
            self.selection_cleared.emit()
            return
        ntype = current.data(0, ROLE_NODE_TYPE)
        nname = current.data(0, ROLE_NODE_NAME)
        if ntype == NODE_GLOBAL:
            self.global_selected.emit()
        elif ntype == NODE_BODY:
            self.body_selected.emit(nname)
        elif ntype == NODE_ZONE:
            body_name = current.data(0, ROLE_BODY_NAME)
            self.zone_selected.emit(body_name, nname)
        elif ntype == NODE_CONN:
            self.connection_selected.emit(nname)
        elif ntype == NODE_PROBE:
            self.probe_selected.emit(nname)
        elif ntype == NODE_CAMERA:
            self.camera_selected.emit(nname)
        elif ntype == NODE_LIGHT:
            self.light_selected.emit(nname)
        elif ntype == NODE_AMBIENT:
            self.ambient_selected.emit()
        else:
            self.selection_cleared.emit()

    def _on_context_menu(self, pos):
        item = self.itemAt(pos)
        if item is None:
            return
        ntype = item.data(0, ROLE_NODE_TYPE)
        nname = item.data(0, ROLE_NODE_NAME)
        menu = QMenu(self)

        if ntype == NODE_BODY_GRP:
            act = menu.addAction("添加几何体...")
            act.triggered.connect(lambda: self.request_add_body.emit())
        elif ntype == NODE_BODY:
            act_paint = menu.addAction("涂选编辑")
            act_paint.triggered.connect(lambda: self.request_paint_mode.emit(nname))
            menu.addSeparator()
            act_del = menu.addAction("删除")
            act_del.triggered.connect(lambda: self.request_delete_body.emit(nname))
        elif ntype == NODE_PROBE_GRP:
            act = menu.addAction("添加探针")
            act.triggered.connect(lambda: self.request_add_probe.emit())
        elif ntype == NODE_PROBE:
            act = menu.addAction("删除")
            act.triggered.connect(lambda: self.request_delete_probe.emit(nname))
        elif ntype == NODE_CONN:
            act = menu.addAction("删除")
            act.triggered.connect(lambda: self.request_delete_conn.emit(nname))
        elif ntype == NODE_CAM_GRP:
            act_def = menu.addAction("添加默认摄像机")
            act_def.triggered.connect(lambda: self.request_add_camera_default.emit())
            act_view = menu.addAction("从当前视角创建摄像机")
            act_view.triggered.connect(lambda: self.request_add_camera_from_view.emit())
        elif ntype == NODE_CAMERA:
            act = menu.addAction("删除")
            act.triggered.connect(lambda: self.request_delete_camera.emit(nname))
        elif ntype == NODE_LIGHT_GRP:
            act_def = menu.addAction("添加默认光源")
            act_def.triggered.connect(lambda: self.request_add_default_light.emit())
            act_src = menu.addAction("添加常量球面源")
            act_src.triggered.connect(lambda: self.request_add_spherical_source.emit())
            act_prog = menu.addAction("添加可编程球面源")
            act_prog.triggered.connect(lambda: self.request_add_spherical_source_prog.emit())
        elif ntype == NODE_LIGHT:
            act = menu.addAction("删除")
            act.triggered.connect(lambda: self.request_delete_light.emit(nname))
        else:
            return

        menu.exec_(self.mapToGlobal(pos))

    # ─── 查找辅助 ────────────────────────────────────────────────

    def _find_item(self, node_type: str, name: str) -> QTreeWidgetItem:
        it = self._iter_all_items()
        for item in it:
            if item.data(0, ROLE_NODE_TYPE) == node_type and item.data(0, ROLE_NODE_NAME) == name:
                return item
        return None

    def _on_item_double_clicked(self, item, column):
        """双击摄像机子节点 → 请求将该摄像机参数应用到视口。"""
        if item is None:
            return
        ntype = item.data(0, ROLE_NODE_TYPE)
        nname = item.data(0, ROLE_NODE_NAME)
        if ntype == NODE_CAMERA:
            self.request_apply_camera_to_view.emit(nname)

    def _find_zone_item(self, body_name: str, zone_name: str) -> QTreeWidgetItem:
        for item in self._iter_all_items():
            if (item.data(0, ROLE_NODE_TYPE) == NODE_ZONE
                    and item.data(0, ROLE_NODE_NAME) == zone_name
                    and item.data(0, ROLE_BODY_NAME) == body_name):
                return item
        return None

    def _iter_all_items(self):
        stack = [self.topLevelItem(i) for i in range(self.topLevelItemCount())]
        while stack:
            item = stack.pop()
            yield item
            for i in range(item.childCount()):
                stack.append(item.child(i))
