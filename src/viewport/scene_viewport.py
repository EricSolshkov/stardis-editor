"""
S3: 多对象 VTK 场景渲染视口
S4 (部分): 视口侧的选择信号
S6 (集成): 涂选模式

功能:
- 多 Body 渲染 + BoundaryLabel 着色
- 导航模式: 左键选择, 中键旋转, 双击进入边界编辑模式
- 涂选模式: 画刷涂色, Ctrl 擦除, 撤销/重做, 中键旋转
- 编辑模式: 聚焦物体以实体+线框渲染, 其余半透明
- 探针可视化 (球体 + 标签)
"""

import math
import vtk
from vtk.qt.QVTKRenderWindowInteractor import QVTKRenderWindowInteractor
from PyQt5.QtCore import pyqtSignal, Qt, QTimer
from PyQt5.QtWidgets import QWidget, QHBoxLayout, QToolBar, QAction, QComboBox, QPushButton, QVBoxLayout, QActionGroup, QLabel, QSlider
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from models.scene_model import (
    SceneModel, Body, Probe, ProbeType, BoundaryType, SurfaceZone,
    PaintedRegion, ConvectionBC, SceneLight, LightType,
)
from viewport.surface_painter import SurfacePainter, BrushMode, build_zone_lut

# ─── 模式枚举 ───────────────────────────────────────────────────

MODE_NAVIGATE = 0
MODE_PAINT = 1


class SceneViewport(QWidget):
    """场景 3D 视口，封装 VTK 渲染和交互。"""

    # ─── 信号 ────────────────────────────────────────────────────
    body_picked   = pyqtSignal(str)
    probe_picked  = pyqtSignal(str)
    nothing_picked = pyqtSignal()
    paint_changed = pyqtSignal(str, dict)   # body_name, {zone_name: cell_ids}
    probe_placed  = pyqtSignal(str, float, float, float)  # body_name, x, y, z
    paint_mode_entered = pyqtSignal(str)     # body_name — 双击进入编辑模式时发射

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 涂选工具栏 (初始隐藏)
        self._paint_toolbar = self._create_paint_toolbar()
        layout.addWidget(self._paint_toolbar)
        self._paint_toolbar.hide()

        # VTK 控件
        self._vtk_widget = QVTKRenderWindowInteractor(self)
        layout.addWidget(self._vtk_widget)

        self.renderer = vtk.vtkRenderer()
        self.renderer.SetBackground(0.15, 0.15, 0.18)
        self._vtk_widget.GetRenderWindow().AddRenderer(self.renderer)
        self._interactor = self._vtk_widget.GetRenderWindow().GetInteractor()
        self._interactor.SetInteractorStyle(None)

        # 状态
        self._mode = MODE_NAVIGATE
        self._model: SceneModel = SceneModel()
        self._body_actors: dict = {}       # body_name → vtkActor
        self._body_polydatas: dict = {}    # body_name → vtkPolyData
        self._probe_actors: dict = {}      # probe_name → (marker_actor, label_actor)
        self._selected_body: str = ""
        self._selected_probe: str = ""
        self._wireframe_actors: dict = {}  # body_name → vtkActor (线框叠加)

        # 轮廓高亮 (Silhouette)
        self._silhouette_actor: vtk.vtkActor = None
        self._silhouette_filter = None
        self._highlight_color = (1.0, 1.0, 0.0)   # 默认黄色
        self._highlight_line_width = 3.0

        # 区域 LUT 高亮
        self._zone_hl_body: str = ""                 # 当前有区域高亮的 body
        self._zone_hl_saved_lut = None               # 保存的原始 LUT

        # 法线显示
        self._normal_actors: dict = {}     # body_name → vtkActor
        self._normal_length: float = 1.0   # 当前法线显示长度

        # VTK 光源
        self._vtk_lights: dict = {}        # light_name → vtkLight
        self._ambient_intensity: float = 0.15  # 环境基本光照强度

        # 涂选
        self._painter: SurfacePainter = None
        self._paint_body_name: str = ""
        self._paint_dragging = False

        # 导航 / 旋转 (中键在所有模式下通用)
        self._mid_drag = False
        self._last_pos = None
        self._double_click_timer = QTimer()
        self._double_click_timer.setSingleShot(True)
        self._double_click_timer.setInterval(250)
        self._pending_click_pos = None

        # 轨道相机 (球坐标)
        self._orbit_target = [0.0, 0.0, 0.0]   # 注视点
        self._orbit_azimuth = math.radians(45)   # 方位角 (rad, XY 平面从 +X 逆时针)
        self._orbit_elevation = math.radians(30)  # 仰角 (rad, 从 XY 平面向 +Z)
        self._orbit_distance = 10.0               # 到 target 距离
        self._orbit_roll = 0.0                     # 滚转角 (deg)

        # 键盘持续移动
        self._pressed_keys: set = set()
        self._move_timer = QTimer(self)
        self._move_timer.setInterval(16)   # ~60 fps
        self._move_timer.timeout.connect(self._on_move_tick)
        self._move_speed = 0.01            # 实际速度 = _move_speed * distance

        # Picker
        self._cell_picker = vtk.vtkCellPicker()
        self._cell_picker.SetTolerance(0.005)

        # 让 widget 能接收键盘事件
        self._vtk_widget.setFocusPolicy(Qt.StrongFocus)

    # ─── 公共接口 ────────────────────────────────────────────────

    def load_scene(self, model: SceneModel):
        """从 SceneModel 加载所有几何体和探针到视口。"""
        self._clear_all()
        self._model = model

        for body in model.bodies:
            self._add_body_actor(body)

        for probe in model.probes:
            self._add_probe_actor(probe)

        self.renderer.ResetCamera()
        self._init_orbit_from_camera()
        # 确保所有物体以实体模式渲染 + 线框叠加
        for actor in self._body_actors.values():
            actor.GetProperty().SetOpacity(1.0)
            actor.ForceOpaqueOn()
            actor.ForceTranslucentOff()
        self._add_all_wireframe_overlays()
        # 同步光源
        self.sync_lights(model.lights)
        self._ambient_intensity = model.ambient_intensity
        self._apply_ambient()
        self._render()

    def highlight_body(self, body_name: str):
        """选中指定几何体: 轮廓线高亮 (Silhouette) + 启用该几何体的区域着色。"""
        self._selected_body = body_name
        self._selected_probe = ""
        self._restore_zone_lut()
        for name, actor in self._body_actors.items():
            actor.GetProperty().SetOpacity(1.0)
            actor.ForceOpaqueOn()
            actor.ForceTranslucentOff()
            # 仅选中几何体启用区域着色
            if name == body_name:
                actor.GetMapper().ScalarVisibilityOn()
            else:
                actor.GetMapper().ScalarVisibilityOff()
        if self._mode == MODE_NAVIGATE:
            self._add_silhouette(body_name)
        self._render()

    def highlight_zone(self, body_name: str, zone_name: str):
        """高亮表面区域: 轮廓线 + 仅启用该几何体区域着色 + 选中区域突出。"""
        self._selected_body = body_name
        self._selected_probe = ""
        self._restore_zone_lut()
        for name, actor in self._body_actors.items():
            actor.GetProperty().SetOpacity(1.0)
            actor.ForceOpaqueOn()
            actor.ForceTranslucentOff()
            # 仅选中几何体启用区域着色
            if name == body_name:
                actor.GetMapper().ScalarVisibilityOn()
            else:
                actor.GetMapper().ScalarVisibilityOff()
        if self._mode == MODE_NAVIGATE:
            self._add_silhouette(body_name)
            self._apply_zone_lut_highlight(body_name, zone_name)
        self._render()

    def highlight_probe(self, probe_name: str):
        """高亮指定探针。"""
        self._selected_body = ""
        self._selected_probe = probe_name
        self._remove_silhouette()
        self._restore_zone_lut()
        for name, actor in self._body_actors.items():
            actor.GetProperty().SetOpacity(1.0)
            actor.ForceOpaqueOn()
            actor.ForceTranslucentOff()
            actor.GetMapper().ScalarVisibilityOff()
        for name, (marker, label) in self._probe_actors.items():
            if name == probe_name:
                marker.GetProperty().SetColor(1, 0.5, 0)
                marker.SetScale(1.5, 1.5, 1.5)
            else:
                marker.GetProperty().SetColor(*self._model.get_probe_by_name(name).color[:3])
                marker.SetScale(1, 1, 1)
        self._render()

    def clear_highlight(self):
        """恢复所有对象正常渲染，关闭区域着色，恢复线框。"""
        self._selected_body = ""
        self._selected_probe = ""
        self._remove_silhouette()
        self._restore_zone_lut()
        for actor in self._body_actors.values():
            actor.GetProperty().SetOpacity(1.0)
            actor.ForceOpaqueOn()
            actor.ForceTranslucentOff()
            actor.GetMapper().ScalarVisibilityOff()
        self._add_all_wireframe_overlays()
        self._render()

    # ─── 涂选模式 ────────────────────────────────────────────────

    def enter_paint_mode(self, body_name: str):
        """进入涂选模式: 聚焦物体以实体+线框渲染, 其余半透明。"""
        if body_name not in self._body_polydatas:
            return
        # 清除导航模式高亮
        self._remove_silhouette()
        self._restore_zone_lut()

        self._mode = MODE_PAINT
        self._paint_body_name = body_name
        poly = self._body_polydatas[body_name]
        actor = self._body_actors[body_name]
        self._painter = SurfacePainter(poly, self.renderer, actor)
        self._painter.save_undo_point()

        # 聚焦物体: 实体 + 线框叠加 + 区域着色; 其余半透明 + 无线框 + 无区域着色
        self._remove_all_wireframe_overlays()
        for name, act in self._body_actors.items():
            if name == body_name:
                act.GetProperty().SetOpacity(1.0)
                act.ForceOpaqueOn()
                act.ForceTranslucentOff()
                act.GetMapper().ScalarVisibilityOn()
                self._add_wireframe_overlay(name)
            else:
                act.GetProperty().SetOpacity(0.15)
                act.ForceOpaqueOff()
                act.ForceTranslucentOn()
                act.GetMapper().ScalarVisibilityOff()

        # 更新工具栏下拉
        self._update_paint_toolbar(body_name)
        self._paint_toolbar.show()
        self._render()

    def exit_paint_mode(self, confirm: bool = True):
        """退出涂选模式。confirm=True 保存修改, False 取消。"""
        if self._mode != MODE_PAINT:
            return
        if confirm and self._painter:
            self._emit_paint_result()
        elif not confirm and self._painter and self._painter.undo_stack:
            # 恢复到进入时的第一个撤销点
            first = self._painter.undo_stack[0]
            self._painter.labels.DeepCopy(first)
            self._painter.poly.Modified()

        self._mode = MODE_NAVIGATE
        self._painter = None
        self._paint_body_name = ""
        self._paint_toolbar.hide()
        self._remove_all_wireframe_overlays()
        self.clear_highlight()

    # ─── Qt 鼠标事件 ─────────────────────────────────────────────

    def _forward_mouse_press(self, event):
        # 中键旋转在所有模式下通用
        if event.button() == Qt.MiddleButton:
            self._mid_drag = True
            self._last_pos = event.pos()
            return
        if self._mode == MODE_NAVIGATE:
            self._nav_mouse_press(event)
        else:
            self._paint_mouse_press(event)

    def _forward_mouse_release(self, event):
        if event.button() == Qt.MiddleButton:
            self._mid_drag = False
            self._last_pos = None
            return
        if self._mode == MODE_NAVIGATE:
            self._nav_mouse_release(event)
        else:
            self._paint_mouse_release(event)

    def _forward_mouse_move(self, event):
        # 中键旋转在所有模式下通用
        if self._mid_drag and self._last_pos:
            dx = event.x() - self._last_pos.x()
            dy = event.y() - self._last_pos.y()
            self._orbit_azimuth -= dx * 0.005
            self._orbit_elevation += dy * 0.005
            half_pi = math.pi / 2
            self._orbit_elevation = max(-half_pi, min(half_pi, self._orbit_elevation))
            self._last_pos = event.pos()
            self._update_camera_from_orbit()
            return
        if self._mode == MODE_NAVIGATE:
            self._nav_mouse_move(event)
        else:
            self._paint_mouse_move(event)

    def _forward_wheel(self, event):
        delta = event.angleDelta().y()
        factor = 1.0 - delta / 1200.0
        self._orbit_distance = max(0.01, self._orbit_distance * factor)
        self._update_camera_from_orbit()

    def _forward_mouse_double_click(self, event):
        if self._mode == MODE_NAVIGATE and event.button() == Qt.LeftButton:
            self._on_double_click_enter_paint(event.x(), self._vtk_widget.height() - event.y())

    def _forward_key_press(self, event):
        key = event.key()
        if key == Qt.Key_B and self._mode == MODE_NAVIGATE and self._selected_body:
            self.enter_paint_mode(self._selected_body)
            return
        elif key == Qt.Key_N and self._mode == MODE_NAVIGATE and self._selected_body:
            self._toggle_normals(self._selected_body)
            return
        elif key == Qt.Key_Plus and self._mode == MODE_NAVIGATE:
            self._scale_normals(10.0)
            return
        elif key == Qt.Key_Minus and self._mode == MODE_NAVIGATE:
            self._scale_normals(0.1)
            return
        elif key == Qt.Key_Escape and self._mode == MODE_PAINT:
            self.exit_paint_mode(confirm=False)
            return
        elif key == Qt.Key_Z and event.modifiers() & Qt.ControlModifier and self._mode == MODE_PAINT:
            if self._painter:
                self._painter.undo()
                self._render()
            return
        elif key == Qt.Key_Y and event.modifiers() & Qt.ControlModifier and self._mode == MODE_PAINT:
            if self._painter:
                self._painter.redo()
                self._render()
            return

        # 移动/滚转按键
        move_keys = {
            Qt.Key_W, Qt.Key_A, Qt.Key_S, Qt.Key_D,
            Qt.Key_Space, Qt.Key_Shift,
            Qt.Key_Q, Qt.Key_E,
        }
        if key in move_keys and not event.isAutoRepeat():
            self._pressed_keys.add(key)
            if not self._move_timer.isActive():
                self._move_timer.start()

    def _forward_key_release(self, event):
        key = event.key()
        if not event.isAutoRepeat():
            self._pressed_keys.discard(key)
            if not self._pressed_keys and self._move_timer.isActive():
                self._move_timer.stop()

    # ─── 安装事件过滤 ────────────────────────────────────────────

    def showEvent(self, event):
        super().showEvent(event)
        self._vtk_widget.installEventFilter(self)
        self._interactor.Initialize()

    def eventFilter(self, obj, event):
        if obj is not self._vtk_widget:
            return False
        from PyQt5.QtCore import QEvent
        t = event.type()
        if t == QEvent.MouseButtonPress:
            self._forward_mouse_press(event)
            return True
        elif t == QEvent.MouseButtonRelease:
            self._forward_mouse_release(event)
            return True
        elif t == QEvent.MouseMove:
            self._forward_mouse_move(event)
            return True
        elif t == QEvent.Wheel:
            self._forward_wheel(event)
            return True
        elif t == QEvent.MouseButtonDblClick:
            self._forward_mouse_double_click(event)
            return True
        elif t == QEvent.KeyPress:
            self._forward_key_press(event)
            return True
        elif t == QEvent.KeyRelease:
            self._forward_key_release(event)
            return True
        return False

    # ─── 导航模式交互 ────────────────────────────────────────────

    def _nav_mouse_press(self, event):
        # 左键仅用于拾取 (在 release 中处理)
        pass

    def _nav_mouse_release(self, event):
        if event.button() == Qt.LeftButton:
            sx = event.x()
            sy = self._vtk_widget.height() - event.y()
            self._on_pick(sx, sy)

    def _nav_mouse_move(self, event):
        pass

    # ─── 轨道相机核心 ────────────────────────────────────────────

    def _update_camera_from_orbit(self):
        """从球坐标参数重建 VTK 相机位姿。"""
        az = self._orbit_azimuth
        el = self._orbit_elevation
        d = self._orbit_distance
        t = self._orbit_target

        cos_el = math.cos(el)
        cam_x = t[0] + d * cos_el * math.cos(az)
        cam_y = t[1] + d * cos_el * math.sin(az)
        cam_z = t[2] + d * math.sin(el)

        camera = self.renderer.GetActiveCamera()
        camera.SetPosition(cam_x, cam_y, cam_z)
        camera.SetFocalPoint(*t)
        camera.SetViewUp(0, 0, 1)
        if self._orbit_roll != 0.0:
            camera.Roll(self._orbit_roll)
        self.renderer.ResetCameraClippingRange()
        self._render()

    def _init_orbit_from_camera(self):
        """从当前 VTK 相机状态反推轨道参数。"""
        camera = self.renderer.GetActiveCamera()
        fp = camera.GetFocalPoint()
        pos = camera.GetPosition()
        self._orbit_target = [fp[0], fp[1], fp[2]]
        dx = pos[0] - fp[0]
        dy = pos[1] - fp[1]
        dz = pos[2] - fp[2]
        dist = math.sqrt(dx * dx + dy * dy + dz * dz)
        self._orbit_distance = max(dist, 0.01)
        self._orbit_azimuth = math.atan2(dy, dx)
        horiz = math.sqrt(dx * dx + dy * dy)
        self._orbit_elevation = math.atan2(dz, horiz) if horiz > 1e-12 else (
            math.pi / 2 if dz >= 0 else -math.pi / 2
        )
        self._orbit_roll = 0.0

    def get_current_view_camera_params(self):
        """获取当前视口相机参数，返回 (position, target, up, fov)。"""
        camera = self.renderer.GetActiveCamera()
        pos = camera.GetPosition()
        fp = camera.GetFocalPoint()
        up = camera.GetViewUp()
        fov = camera.GetViewAngle()
        return (
            (pos[0], pos[1], pos[2]),
            (fp[0], fp[1], fp[2]),
            (up[0], up[1], up[2]),
            fov,
        )

    def apply_camera_to_view(self, position, target, up, fov):
        """将 IRCamera 参数应用到当前视口。"""
        camera = self.renderer.GetActiveCamera()
        camera.SetPosition(*position)
        camera.SetFocalPoint(*target)
        camera.SetViewUp(*up)
        camera.SetViewAngle(fov)
        self.renderer.ResetCameraClippingRange()
        self._init_orbit_from_camera()
        self._render()

    def _on_move_tick(self):
        """QTimer 回调: 根据按下的键持续移动 target + 相机。"""
        if not self._pressed_keys:
            return

        az = self._orbit_azimuth
        el = self._orbit_elevation
        speed = self._move_speed * self._orbit_distance

        cos_el_abs = abs(math.cos(el))

        if cos_el_abs > 1e-4:
            # 正常情况: 视线水平投影
            fwd = [-math.cos(az), -math.sin(az), 0.0]
            rgt = [-math.sin(az),  math.cos(az), 0.0]
        else:
            # 在 ±90° 高度角, 用相机 ViewUp 的水平投影作为 forward
            camera = self.renderer.GetActiveCamera()
            vu = list(camera.GetViewUp())
            # 水平投影
            h = math.sqrt(vu[0] * vu[0] + vu[1] * vu[1])
            if h > 1e-8:
                fwd = [vu[0] / h, vu[1] / h, 0.0]
            else:
                fwd = [-math.cos(az), -math.sin(az), 0.0]
            rgt = [-fwd[1], fwd[0], 0.0]

        dt = [0.0, 0.0, 0.0]
        if Qt.Key_W in self._pressed_keys:
            dt = [dt[i] + fwd[i] * speed for i in range(3)]
        if Qt.Key_S in self._pressed_keys:
            dt = [dt[i] - fwd[i] * speed for i in range(3)]
        if Qt.Key_A in self._pressed_keys:
            dt = [dt[i] - rgt[i] * speed for i in range(3)]
        if Qt.Key_D in self._pressed_keys:
            dt = [dt[i] + rgt[i] * speed for i in range(3)]
        if Qt.Key_Space in self._pressed_keys:
            dt[2] += speed
        if Qt.Key_Shift in self._pressed_keys:
            dt[2] -= speed

        self._orbit_target = [self._orbit_target[i] + dt[i] for i in range(3)]

        # Q / E 滚转
        if Qt.Key_Q in self._pressed_keys:
            self._orbit_roll -= 2.0
        if Qt.Key_E in self._pressed_keys:
            self._orbit_roll += 2.0

        self._update_camera_from_orbit()

    # ─── 涂选模式交互 ────────────────────────────────────────────

    def _paint_mouse_press(self, event):
        if event.button() == Qt.LeftButton:
            self._paint_dragging = True
            if self._painter:
                sx = event.x()
                sy = self._vtk_widget.height() - event.y()
                ctrl = bool(event.modifiers() & Qt.ControlModifier)
                self._painter.on_press(sx, sy, erase=ctrl)
                self._render()
        elif event.button() == Qt.RightButton:
            self.exit_paint_mode(confirm=True)

    def _paint_mouse_release(self, event):
        if event.button() == Qt.LeftButton:
            self._paint_dragging = False

    def _paint_mouse_move(self, event):
        if self._paint_dragging and self._painter:
            sx = event.x()
            sy = self._vtk_widget.height() - event.y()
            ctrl = bool(event.modifiers() & Qt.ControlModifier)
            self._painter.on_drag(sx, sy, erase=ctrl)
            self._render()

    # ─── 拾取 ────────────────────────────────────────────────────

    def _on_pick(self, sx, sy):
        """导航模式下左键单击拾取。"""
        self._cell_picker.Pick(sx, sy, 0, self.renderer)
        picked_actor = self._cell_picker.GetActor()

        if picked_actor is None:
            self.clear_highlight()
            self.nothing_picked.emit()
            return

        # 检查是否命中 Body
        for name, actor in self._body_actors.items():
            if actor is picked_actor:
                self.highlight_body(name)
                self.body_picked.emit(name)
                return

        # 检查是否命中 Probe
        for name, (marker, _label) in self._probe_actors.items():
            if marker is picked_actor:
                self.highlight_probe(name)
                self.probe_picked.emit(name)
                return

        self.clear_highlight()
        self.nothing_picked.emit()

    def _on_double_click_enter_paint(self, sx, sy):
        """导航模式下双击几何体 → 进入边界编辑 (涂选) 模式。"""
        self._cell_picker.Pick(sx, sy, 0, self.renderer)
        picked_actor = self._cell_picker.GetActor()
        if picked_actor is None:
            return
        for name, actor in self._body_actors.items():
            if actor is picked_actor:
                self.enter_paint_mode(name)
                self.paint_mode_entered.emit(name)
                return

    # ─── Body Actor 管理 ─────────────────────────────────────────

    def _add_body_actor(self, body: Body):
        """加载 Body 的 STL 并创建 Actor。"""
        if not body.stl_files:
            return
        stl_path = body.stl_files[0]
        if not os.path.isfile(stl_path):
            return

        reader = vtk.vtkSTLReader()
        reader.SetFileName(stl_path)
        reader.Update()
        poly = vtk.vtkPolyData()
        poly.DeepCopy(reader.GetOutput())

        # 初始化 BoundaryLabel
        n_cells = poly.GetNumberOfCells()
        labels = vtk.vtkIntArray()
        labels.SetName("BoundaryLabel")
        labels.SetNumberOfTuples(n_cells)
        labels.Fill(0)

        # 从 surface_zones 填充标签 (使用 zone_id)
        for zone in body.surface_zones:
            if isinstance(zone.source, PaintedRegion) and zone.source.cell_ids:
                for cid in zone.source.cell_ids:
                    if cid < n_cells:
                        labels.SetValue(cid, zone.zone_id)

        poly.GetCellData().AddArray(labels)
        poly.GetCellData().SetActiveScalars("BoundaryLabel")

        lut = build_zone_lut(body.surface_zones)
        max_id = max((z.zone_id for z in body.surface_zones), default=1)

        mapper = vtk.vtkPolyDataMapper()
        mapper.SetInputData(poly)
        mapper.SetScalarModeToUseCellData()
        mapper.SelectColorArray("BoundaryLabel")
        mapper.SetColorModeToMapScalars()
        mapper.SetLookupTable(lut)
        mapper.SetScalarRange(0, max(max_id, 1))

        actor = vtk.vtkActor()
        actor.SetMapper(mapper)
        # 默认不显示区域着色，使用统一灰色
        mapper.ScalarVisibilityOff()
        actor.GetProperty().SetColor(0.7, 0.7, 0.7)

        self.renderer.AddActor(actor)
        self._body_actors[body.name] = actor
        self._body_polydatas[body.name] = poly

    # ─── Probe Actor 管理 ────────────────────────────────────────

    def _add_probe_actor(self, probe: Probe):
        """创建探针可视化。"""
        # 球体标记
        sphere = vtk.vtkSphereSource()
        sphere.SetRadius(self._auto_probe_radius())
        sphere.SetCenter(*probe.position)
        sphere.SetThetaResolution(16)
        sphere.SetPhiResolution(16)

        mapper = vtk.vtkPolyDataMapper()
        mapper.SetInputConnection(sphere.GetOutputPort())
        marker = vtk.vtkActor()
        marker.SetMapper(mapper)
        marker.GetProperty().SetColor(*probe.color[:3])
        self.renderer.AddActor(marker)

        # 文字标签
        label = vtk.vtkBillboardTextActor3D()
        label.SetInput(probe.name)
        label.SetPosition(*probe.position)
        label.GetTextProperty().SetFontSize(14)
        label.GetTextProperty().SetColor(1, 1, 1)
        self.renderer.AddActor(label)

        self._probe_actors[probe.name] = (marker, label)

    def add_probe_visual(self, probe: Probe):
        """公共接口: 添加新探针的可视化。"""
        self._add_probe_actor(probe)
        self._render()

    def remove_probe_visual(self, probe_name: str):
        """移除探针可视化。"""
        if probe_name in self._probe_actors:
            marker, label = self._probe_actors.pop(probe_name)
            self.renderer.RemoveActor(marker)
            self.renderer.RemoveActor(label)
            self._render()

    def update_probe_position(self, probe_name: str, x: float, y: float, z: float):
        """更新探针标记位置。"""
        if probe_name in self._probe_actors:
            marker, label = self._probe_actors[probe_name]
            # 更新球体位置
            mapper = marker.GetMapper()
            source = mapper.GetInputAlgorithm()
            if hasattr(source, 'SetCenter'):
                source.SetCenter(x, y, z)
                source.Update()
            label.SetPosition(x, y, z)
            self._render()

    def _auto_probe_radius(self) -> float:
        """根据场景包围盒计算探针标记半径。"""
        bounds = self.renderer.ComputeVisiblePropBounds()
        if bounds[0] > bounds[1]:
            return 0.01
        diag = ((bounds[1] - bounds[0]) ** 2 +
                (bounds[3] - bounds[2]) ** 2 +
                (bounds[5] - bounds[4]) ** 2) ** 0.5
        return max(diag * 0.01, 0.001)

    # ─── VTK 光源管理 ────────────────────────────────────────────

    def sync_lights(self, lights: list):
        """根据 SceneLight 列表同步 VTK 光源。"""
        from models.scene_model import LightType
        # 移除旧光源
        for vtk_light in self._vtk_lights.values():
            self.renderer.RemoveLight(vtk_light)
        self._vtk_lights.clear()

        # 关闭 VTK 默认的自动头灯
        self.renderer.AutomaticLightCreationOff()
        self.renderer.RemoveAllLights()

        # 添加新光源
        for light in lights:
            # PROG 类型不参与 VTK 光照
            if light.light_type == LightType.SPHERICAL_SOURCE_PROG:
                continue
            vtk_light = vtk.vtkLight()
            vtk_light.SetColor(*light.color)
            vtk_light.SetSwitch(light.enabled)

            if light.light_type == LightType.SPHERICAL_SOURCE:
                # 球面点光源
                vtk_light.SetPositional(True)
                vtk_light.SetPosition(*light.position)
                vtk_light.SetFocalPoint(0.0, 0.0, 0.0)
                vtk_light.SetIntensity(light.power if light.power > 0 else 1.0)
            else:
                # DEFAULT: 场景灯 / 头灯
                vtk_light.SetPositional(False)
                vtk_light.SetPosition(*light.position)
                vtk_light.SetFocalPoint(0.0, 0.0, 0.0)
                vtk_light.SetIntensity(1.0)

            self.renderer.AddLight(vtk_light)
            self._vtk_lights[light.name] = vtk_light

        self._render()

    def set_ambient_intensity(self, intensity: float):
        """设置环境基本光照强度并立即应用。"""
        self._ambient_intensity = intensity
        self._apply_ambient()
        self._render()

    def _apply_ambient(self):
        """将环境光照强度应用到所有几何体 Actor。"""
        for actor in self._body_actors.values():
            actor.GetProperty().SetAmbient(self._ambient_intensity)

    def update_lights(self, lights: list):
        """更新现有光源参数（无需重建 Actor）。"""
        self.sync_lights(lights)

    # ─── 涂选工具栏 ─────────────────────────────────────────────

    def _create_paint_toolbar(self) -> QToolBar:
        bar = QToolBar()
        bar.setMovable(False)

        self._zone_combo = QComboBox()
        self._zone_combo.setMinimumWidth(160)
        self._zone_combo.currentIndexChanged.connect(self._on_zone_combo_changed)
        bar.addWidget(self._zone_combo)

        self._add_zone_btn = QPushButton("+ 新建区域")
        self._add_zone_btn.clicked.connect(self._on_add_zone)
        bar.addWidget(self._add_zone_btn)

        bar.addSeparator()

        # 四种互斥画笔模式
        self._brush_mode_group = QActionGroup(bar)
        self._brush_mode_group.setExclusive(True)

        brush_act = QAction("🖌 画笔", bar)
        brush_act.setCheckable(True)
        brush_act.setChecked(True)
        brush_act.setData(BrushMode.BRUSH)
        self._brush_mode_group.addAction(brush_act)
        bar.addAction(brush_act)

        fill_all_act = QAction("▣ 全部", bar)
        fill_all_act.setCheckable(True)
        fill_all_act.setData(BrushMode.FILL_ALL)
        self._brush_mode_group.addAction(fill_all_act)
        bar.addAction(fill_all_act)

        flood_act = QAction("🌊 洪泛", bar)
        flood_act.setCheckable(True)
        flood_act.setData(BrushMode.FLOOD_FILL)
        self._brush_mode_group.addAction(flood_act)
        bar.addAction(flood_act)

        replace_act = QAction("◈ 替换", bar)
        replace_act.setCheckable(True)
        replace_act.setData(BrushMode.REPLACE_FILL)
        self._brush_mode_group.addAction(replace_act)
        bar.addAction(replace_act)

        self._brush_mode_group.triggered.connect(self._on_brush_mode_changed)

        bar.addSeparator()

        undo_act = QAction("↩ 撤销", bar)
        undo_act.triggered.connect(lambda: self._painter and self._painter.undo() and self._render())
        bar.addAction(undo_act)

        redo_act = QAction("↪ 重做", bar)
        redo_act.triggered.connect(lambda: self._painter and self._painter.redo() and self._render())
        bar.addAction(redo_act)

        return bar

    def _on_brush_mode_changed(self, action):
        """Brush mode action triggered."""
        if self._painter:
            self._painter.brush_mode = action.data()

    def _update_paint_toolbar(self, body_name: str):
        self._zone_combo.blockSignals(True)
        self._zone_combo.clear()
        body = self._model.get_body_by_name(body_name)
        if body:
            for zone in body.surface_zones:
                self._zone_combo.addItem(f"{zone.name}", zone.zone_id)
        self._zone_combo.blockSignals(False)
        if self._painter and self._zone_combo.count() > 0:
            self._painter.current_label = self._zone_combo.currentData() or 1

    def _on_zone_combo_changed(self, index):
        if self._painter and index >= 0:
            label = self._zone_combo.itemData(index)
            if label is not None:
                self._painter.current_label = label

    def _on_add_zone(self):
        """在涂选模式中新建区域。"""
        body = self._model.get_body_by_name(self._paint_body_name)
        if not body:
            return
        # 自动命名
        existing = {z.name for z in body.surface_zones}
        idx = len(body.surface_zones) + 1
        while f"Zone{idx}" in existing:
            idx += 1
        name = f"Zone{idx}"

        zone_id = body.allocate_zone_id()
        zone = SurfaceZone(
            zone_id=zone_id,
            name=name,
            source=PaintedRegion(),
            boundary_type=BoundaryType.H_BOUNDARY,
            boundary=ConvectionBC(),
        )
        body.surface_zones.append(zone)
        # 更新 LUT
        self._rebuild_body_lut(body)
        self._update_paint_toolbar(self._paint_body_name)
        # 选中新建区域
        self._zone_combo.setCurrentIndex(self._zone_combo.count() - 1)

    def _rebuild_body_lut(self, body: Body):
        """重建 Body 的颜色查找表（zone_id 直接寻址）。"""
        lut = build_zone_lut(body.surface_zones)
        actor = self._body_actors.get(body.name)
        if actor:
            max_id = max((z.zone_id for z in body.surface_zones), default=1)
            mapper = actor.GetMapper()
            mapper.SetLookupTable(lut)
            mapper.SetScalarRange(0, max(max_id, 1))
        self._render()

    def _emit_paint_result(self):
        """退出涂选时发射涂选结果。"""
        if not self._painter or not self._paint_body_name:
            return
        body = self._model.get_body_by_name(self._paint_body_name)
        if not body:
            return
        result = {}
        for zone in body.surface_zones:
            cell_ids = self._painter.get_zone_cell_ids(zone.zone_id)
            zone.source = PaintedRegion(cell_ids=cell_ids) if cell_ids else PaintedRegion()
            result[zone.name] = cell_ids
        self.paint_changed.emit(self._paint_body_name, result)

    # ─── 轮廓线高亮 (Silhouette) ────────────────────────────────

    def _add_silhouette(self, body_name: str):
        """为指定几何体添加轮廓线高亮 Actor。"""
        self._remove_silhouette()
        poly = self._body_polydatas.get(body_name)
        if poly is None:
            return

        sil = vtk.vtkPolyDataSilhouette()
        sil.SetInputData(poly)
        sil.SetCamera(self.renderer.GetActiveCamera())

        mapper = vtk.vtkPolyDataMapper()
        mapper.SetInputConnection(sil.GetOutputPort())

        actor = vtk.vtkActor()
        actor.SetMapper(mapper)
        actor.GetProperty().SetColor(*self._highlight_color)
        actor.GetProperty().SetLineWidth(self._highlight_line_width)

        self.renderer.AddActor(actor)
        self._silhouette_actor = actor
        self._silhouette_filter = sil

    def _remove_silhouette(self):
        """移除轮廓线高亮 Actor。"""
        if self._silhouette_actor is not None:
            self.renderer.RemoveActor(self._silhouette_actor)
            self._silhouette_actor = None
            self._silhouette_filter = None

    # ─── 区域 LUT 高亮 ───────────────────────────────────────────

    def _apply_zone_lut_highlight(self, body_name: str, zone_name: str):
        """修改 LUT 使选中区域以其颜色突出显示, 其余区域变灰。"""
        self._restore_zone_lut()

        body = self._model.get_body_by_name(body_name)
        actor = self._body_actors.get(body_name)
        if not body or not actor:
            return

        mapper = actor.GetMapper()
        current_lut = mapper.GetLookupTable()

        # 查找选中区域的 zone_id
        zone_id = -1
        for z in body.surface_zones:
            if z.name == zone_name:
                zone_id = z.zone_id
                break
        if zone_id < 0:
            return

        # 保存原始 LUT
        saved = vtk.vtkLookupTable()
        saved.DeepCopy(current_lut)
        self._zone_hl_saved_lut = saved
        self._zone_hl_body = body_name

        # 获取选中区域在 LUT 中的颜色
        zone_rgba = [0.0] * 4
        if zone_id < current_lut.GetNumberOfTableValues():
            current_lut.GetTableValue(zone_id, zone_rgba)

        # 构建高亮 LUT: 选中区域保持颜色, 其余变暗灰
        n = current_lut.GetNumberOfTableValues()
        hl_lut = vtk.vtkLookupTable()
        hl_lut.SetNumberOfTableValues(n)
        for i in range(n):
            if i == zone_id:
                hl_lut.SetTableValue(i, zone_rgba[0], zone_rgba[1], zone_rgba[2], 1.0)
            else:
                hl_lut.SetTableValue(i, 0.45, 0.45, 0.45, 1.0)
        hl_lut.SetTableRange(current_lut.GetTableRange())
        hl_lut.Build()

        mapper.SetLookupTable(hl_lut)

    def _restore_zone_lut(self):
        """恢复区域 LUT 为高亮前的状态。"""
        if self._zone_hl_body and self._zone_hl_saved_lut:
            actor = self._body_actors.get(self._zone_hl_body)
            if actor:
                actor.GetMapper().SetLookupTable(self._zone_hl_saved_lut)
            self._zone_hl_body = ""
            self._zone_hl_saved_lut = None

    # ─── 线框叠加 ────────────────────────────────────────────────

    def _add_wireframe_overlay(self, body_name: str):
        """为指定几何体添加黑色线框叠加 Actor。"""
        if body_name in self._wireframe_actors:
            return
        poly = self._body_polydatas.get(body_name)
        if poly is None:
            return
        mapper = vtk.vtkPolyDataMapper()
        mapper.SetInputData(poly)
        mapper.ScalarVisibilityOff()
        wire_actor = vtk.vtkActor()
        wire_actor.SetMapper(mapper)
        wire_actor.GetProperty().SetRepresentationToWireframe()
        wire_actor.GetProperty().SetColor(0.0, 0.0, 0.0)
        wire_actor.GetProperty().SetLineWidth(1.0)
        self.renderer.AddActor(wire_actor)
        self._wireframe_actors[body_name] = wire_actor

    def _add_all_wireframe_overlays(self):
        """为所有几何体添加线框叠加。"""
        for name in self._body_polydatas:
            self._add_wireframe_overlay(name)

    def _remove_all_wireframe_overlays(self):
        """移除所有线框叠加 Actor。"""
        for wire_actor in self._wireframe_actors.values():
            self.renderer.RemoveActor(wire_actor)
        self._wireframe_actors.clear()

    # ─── 清理 ────────────────────────────────────────────────────

    # ─── 法线显示 ─────────────────────────────────────────────

    def _toggle_normals(self, body_name: str):
        """切换指定 Body 的法线显示。"""
        if body_name in self._normal_actors:
            self.renderer.RemoveActor(self._normal_actors.pop(body_name))
            self._render()
            return
        poly = self._body_polydatas.get(body_name)
        if poly is None:
            return
        actor = self._build_normal_actor(poly, self._normal_length)
        self.renderer.AddActor(actor)
        self._normal_actors[body_name] = actor
        self._render()

    def _build_normal_actor(self, poly: "vtk.vtkPolyData", length: float) -> "vtk.vtkActor":
        """根据 PolyData 的面法线构建线段 Actor。"""
        normals_filter = vtk.vtkPolyDataNormals()
        normals_filter.SetInputData(poly)
        normals_filter.ComputeCellNormalsOn()
        normals_filter.ComputePointNormalsOff()
        normals_filter.Update()

        cell_centers = vtk.vtkCellCenters()
        cell_centers.SetInputConnection(normals_filter.GetOutputPort())
        cell_centers.Update()
        centers_poly = cell_centers.GetOutput()

        cell_normals = normals_filter.GetOutput().GetCellData().GetNormals()
        n_pts = centers_poly.GetNumberOfPoints()

        # 将面法线赋给点数据 (vtkHedgeHog 需要点向量)
        vectors = vtk.vtkFloatArray()
        vectors.SetNumberOfComponents(3)
        vectors.SetNumberOfTuples(n_pts)
        for i in range(n_pts):
            vectors.SetTuple3(i, *cell_normals.GetTuple3(i))
        centers_poly.GetPointData().SetVectors(vectors)

        hedgehog = vtk.vtkHedgeHog()
        hedgehog.SetInputData(centers_poly)
        hedgehog.SetScaleFactor(length)

        mapper = vtk.vtkPolyDataMapper()
        mapper.SetInputConnection(hedgehog.GetOutputPort())
        mapper.ScalarVisibilityOff()

        actor = vtk.vtkActor()
        actor.SetMapper(mapper)
        actor.GetProperty().SetColor(1.0, 0.0, 0.0)
        actor.GetProperty().SetLineWidth(1.0)
        return actor

    def _scale_normals(self, factor: float):
        """缩放所有已显示法线的长度 (乘以 factor)。"""
        if not self._normal_actors:
            return
        self._normal_length *= factor
        for body_name in list(self._normal_actors):
            old_actor = self._normal_actors[body_name]
            self.renderer.RemoveActor(old_actor)
            poly = self._body_polydatas.get(body_name)
            if poly is None:
                del self._normal_actors[body_name]
                continue
            new_actor = self._build_normal_actor(poly, self._normal_length)
            self.renderer.AddActor(new_actor)
            self._normal_actors[body_name] = new_actor
        self._render()

    def _remove_all_normal_actors(self):
        """移除所有法线 Actor。"""
        for actor in self._normal_actors.values():
            self.renderer.RemoveActor(actor)
        self._normal_actors.clear()

    def _clear_all(self):
        self._remove_silhouette()
        self._restore_zone_lut()
        self._remove_all_wireframe_overlays()
        self._remove_all_normal_actors()
        for actor in self._body_actors.values():
            self.renderer.RemoveActor(actor)
        for marker, label in self._probe_actors.values():
            self.renderer.RemoveActor(marker)
            self.renderer.RemoveActor(label)
        for vtk_light in self._vtk_lights.values():
            self.renderer.RemoveLight(vtk_light)
        self._body_actors.clear()
        self._body_polydatas.clear()
        self._probe_actors.clear()
        self._vtk_lights.clear()

    def _render(self):
        self._vtk_widget.GetRenderWindow().Render()
