"""
S5: 动态属性编辑面板

根据场景树/3D 视口中选中对象类型，动态切换显示面板内容。
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel,
    QDoubleSpinBox, QSpinBox, QComboBox, QLineEdit, QGroupBox,
    QStackedWidget, QScrollArea, QPushButton, QTableWidget,
    QTableWidgetItem, QHeaderView, QAbstractItemView,
)
from PyQt5.QtCore import pyqtSignal, Qt
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from models.scene_model import (
    SceneModel, GlobalSettings, Body, VolumeProperties, MaterialRef,
    SurfaceZone, TemperatureBC, ConvectionBC, FluxBC, CombinedBC,
    SolidFluidConnection, SolidSolidConnection,
    Probe, IRCamera,
    BodyType, Side, BoundaryType, ProbeType,
    BOUNDARY_TYPE_LABELS,
    SceneLight, LightType,
)
from panels.task_editors import TaskQueueEditor, TaskEditor


def _spin(value=0.0, lo=-1e9, hi=1e9, decimals=4, suffix=""):
    s = QDoubleSpinBox()
    s.setRange(lo, hi)
    s.setDecimals(decimals)
    s.setValue(value)
    if suffix:
        s.setSuffix(f" {suffix}")
    return s


def _ispin(value=0, lo=0, hi=999999999):
    s = QSpinBox()
    s.setRange(lo, hi)
    s.setValue(value)
    return s


# ═══════════════════════════════════════════════════════════════
# 各类型属性编辑器
# ═══════════════════════════════════════════════════════════════

class GlobalSettingsEditor(QWidget):
    property_changed = pyqtSignal()

    def __init__(self):
        super().__init__()
        layout = QFormLayout(self)
        self.t_amb = _spin(300, 0, 1e6, 1, "K")
        self.t_ref = _spin(300, 0, 1e6, 1, "K")
        self.scale = _spin(1.0, 1e-9, 1e9, 6)
        layout.addRow("环境辐射温度 T_ambient:", self.t_amb)
        layout.addRow("线性化参考温度 T_reference:", self.t_ref)
        layout.addRow("几何缩放 SCALE:", self.scale)

        self.stats_label = QLabel()
        layout.addRow("", self.stats_label)

        for w in (self.t_amb, self.t_ref, self.scale):
            w.valueChanged.connect(self.property_changed.emit)

    def load(self, gs: GlobalSettings, model: SceneModel):
        self.blockSignals(True)
        self.t_amb.setValue(gs.t_ambient)
        self.t_ref.setValue(gs.t_reference)
        self.scale.setValue(gs.scale)
        total_zones = sum(len(b.surface_zones) for b in model.bodies)
        self.stats_label.setText(
            f"几何体: {len(model.bodies)}  表面区域: {total_zones}  "
            f"连接: {len(model.connections)}")
        self.blockSignals(False)

    def apply_to(self, gs: GlobalSettings):
        gs.t_ambient = self.t_amb.value()
        gs.t_reference = self.t_ref.value()
        gs.scale = self.scale.value()


class BodyEditor(QWidget):
    property_changed = pyqtSignal()
    request_paint_mode = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)

        # 体积属性组
        vol_grp = QGroupBox("体积属性")
        vol_form = QFormLayout(vol_grp)

        self.type_combo = QComboBox()
        self.type_combo.addItems(["SOLID", "FLUID"])
        vol_form.addRow("类型:", self.type_combo)

        self.lam = _spin(1, 0, 1e6, 4, "W/m/K")
        self.rho = _spin(1, 0, 1e9, 2, "kg/m³")
        self.cp = _spin(1, 0, 1e9, 2, "J/kg/K")
        vol_form.addRow("导热系数 λ:", self.lam)
        vol_form.addRow("密度 ρ:", self.rho)
        vol_form.addRow("比热容 cp:", self.cp)

        self.delta_combo = QComboBox()
        self.delta_combo.addItems(["AUTO", "自定义"])
        self.delta_spin = _spin(0.001, 0, 1e6, 6, "m")
        dh = QHBoxLayout()
        dh.addWidget(self.delta_combo)
        dh.addWidget(self.delta_spin)
        vol_form.addRow("随机行走步长 δ:", dh)

        self.t_init = _spin(300, 0, 1e6, 1, "K")
        vol_form.addRow("初始温度:", self.t_init)

        self.imposed_combo = QComboBox()
        self.imposed_combo.addItems(["UNKNOWN", "自定义"])
        self.imposed_spin = _spin(300, 0, 1e6, 1, "K")
        ih = QHBoxLayout()
        ih.addWidget(self.imposed_combo)
        ih.addWidget(self.imposed_spin)
        vol_form.addRow("施加温度:", ih)

        self.power = _spin(0, 0, 1e12, 2, "W/m³")
        vol_form.addRow("体积热源:", self.power)

        self.side_combo = QComboBox()
        self.side_combo.addItems(["FRONT", "BACK", "BOTH"])
        vol_form.addRow("法线朝向:", self.side_combo)

        layout.addWidget(vol_grp)

        # 几何信息
        geo_grp = QGroupBox("几何信息")
        geo_form = QFormLayout(geo_grp)
        self.stl_label = QLabel("-")
        geo_form.addRow("STL 文件:", self.stl_label)
        self.geo_info = QLabel()
        geo_form.addRow("", self.geo_info)
        layout.addWidget(geo_grp)

        # 表面区域概览
        zone_grp = QGroupBox("表面区域概览")
        zone_layout = QVBoxLayout(zone_grp)
        self.zone_table = QTableWidget(0, 3)
        self.zone_table.setHorizontalHeaderLabels(["区域", "类型", "三角面"])
        self.zone_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.zone_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.zone_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        zone_layout.addWidget(self.zone_table)

        self.paint_btn = QPushButton("🎨 编辑表面区域")
        zone_layout.addWidget(self.paint_btn)
        layout.addWidget(zone_grp)

        layout.addStretch()

        self._body_name = ""
        self.paint_btn.clicked.connect(lambda: self.request_paint_mode.emit(self._body_name))
        for w in (self.lam, self.rho, self.cp, self.delta_spin, self.t_init, self.imposed_spin, self.power):
            w.valueChanged.connect(self.property_changed.emit)
        for w in (self.type_combo, self.delta_combo, self.imposed_combo, self.side_combo):
            w.currentIndexChanged.connect(self.property_changed.emit)

    def load(self, body: Body):
        self.blockSignals(True)
        self._body_name = body.name
        v = body.volume
        m = v.material

        self.type_combo.setCurrentText(v.body_type.value)
        self.lam.setValue(m.conductivity)
        self.rho.setValue(m.density)
        self.cp.setValue(m.specific_heat)
        if v.delta is None:
            self.delta_combo.setCurrentIndex(0)
            self.delta_spin.setEnabled(False)
        else:
            self.delta_combo.setCurrentIndex(1)
            self.delta_spin.setEnabled(True)
            self.delta_spin.setValue(v.delta)
        self.t_init.setValue(v.initial_temp)
        if v.imposed_temp is None:
            self.imposed_combo.setCurrentIndex(0)
            self.imposed_spin.setEnabled(False)
        else:
            self.imposed_combo.setCurrentIndex(1)
            self.imposed_spin.setEnabled(True)
            self.imposed_spin.setValue(v.imposed_temp)
        self.power.setValue(v.volumetric_power)
        self.side_combo.setCurrentText(v.side.value)

        stl = body.stl_files[0] if body.stl_files else "-"
        self.stl_label.setText(os.path.basename(stl))

        # 表面区域表格
        self.zone_table.setRowCount(len(body.surface_zones))
        for r, zone in enumerate(body.surface_zones):
            self.zone_table.setItem(r, 0, QTableWidgetItem(zone.name))
            self.zone_table.setItem(r, 1, QTableWidgetItem(
                BOUNDARY_TYPE_LABELS.get(zone.boundary_type, "?")))
            ncells = len(zone.source.cell_ids) if hasattr(zone.source, 'cell_ids') else "N/A"
            self.zone_table.setItem(r, 2, QTableWidgetItem(str(ncells)))

        self.blockSignals(False)

    def apply_to(self, body: Body):
        v = body.volume
        v.body_type = BodyType(self.type_combo.currentText())
        v.material.conductivity = self.lam.value()
        v.material.density = self.rho.value()
        v.material.specific_heat = self.cp.value()
        v.delta = None if self.delta_combo.currentIndex() == 0 else self.delta_spin.value()
        v.initial_temp = self.t_init.value()
        v.imposed_temp = None if self.imposed_combo.currentIndex() == 0 else self.imposed_spin.value()
        v.volumetric_power = self.power.value()
        v.side = Side(self.side_combo.currentText())


class SurfaceZoneEditor(QWidget):
    property_changed = pyqtSignal()
    boundary_type_changed = pyqtSignal(str, str, str)  # body_name, zone_name, new_type

    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)

        self.parent_label = QLabel()
        layout.addWidget(self.parent_label)

        # 边界条件组
        bc_grp = QGroupBox("边界条件")
        self._bc_layout = QFormLayout(bc_grp)

        self.bc_type_combo = QComboBox()
        for bt in BoundaryType:
            self.bc_type_combo.addItem(BOUNDARY_TYPE_LABELS[bt], bt.value)
        self._bc_layout.addRow("类型:", self.bc_type_combo)

        # 参数栈
        self._params_stack = QStackedWidget()
        self._bc_layout.addRow(self._params_stack)

        # T_BOUNDARY
        self._t_page = QWidget()
        t_form = QFormLayout(self._t_page)
        self.t_temp = _spin(300, 0, 1e6, 1, "K")
        t_form.addRow("温度:", self.t_temp)
        self._params_stack.addWidget(self._t_page)

        # H_BOUNDARY
        self._h_page = QWidget()
        h_form = QFormLayout(self._h_page)
        self.h_tref = _spin(300, 0, 1e6, 1, "K")
        self.h_emissivity = _spin(0.9, 0, 1, 4)
        self.h_specular = _spin(0, 0, 1, 4)
        self.h_hc = _spin(0, 0, 1e6, 2, "W/m²/K")
        self.h_tenv = _spin(300, 0, 1e6, 1, "K")
        h_form.addRow("参考温度 Tref:", self.h_tref)
        h_form.addRow("发射率 ε:", self.h_emissivity)
        h_form.addRow("镜面分数:", self.h_specular)
        h_form.addRow("对流系数 hc:", self.h_hc)
        h_form.addRow("环境温度 T_env:", self.h_tenv)
        self._params_stack.addWidget(self._h_page)

        # F_BOUNDARY
        self._f_page = QWidget()
        f_form = QFormLayout(self._f_page)
        self.f_flux = _spin(0, -1e9, 1e9, 2, "W/m²")
        f_form.addRow("通量 flux:", self.f_flux)
        self._params_stack.addWidget(self._f_page)

        # HF_BOUNDARY
        self._hf_page = QWidget()
        hf_form = QFormLayout(self._hf_page)
        self.hf_tref = _spin(300, 0, 1e6, 1, "K")
        self.hf_emissivity = _spin(0.9, 0, 1, 4)
        self.hf_specular = _spin(0, 0, 1, 4)
        self.hf_hc = _spin(0, 0, 1e6, 2, "W/m²/K")
        self.hf_tenv = _spin(300, 0, 1e6, 1, "K")
        self.hf_flux = _spin(0, -1e9, 1e9, 2, "W/m²")
        hf_form.addRow("参考温度 Tref:", self.hf_tref)
        hf_form.addRow("发射率 ε:", self.hf_emissivity)
        hf_form.addRow("镜面分数:", self.hf_specular)
        hf_form.addRow("对流系数 hc:", self.hf_hc)
        hf_form.addRow("环境温度 T_env:", self.hf_tenv)
        hf_form.addRow("通量 flux:", self.hf_flux)
        self._params_stack.addWidget(self._hf_page)

        layout.addWidget(bc_grp)

        # 区域信息
        info_grp = QGroupBox("区域信息")
        info_form = QFormLayout(info_grp)
        self.source_label = QLabel()
        self.cells_label = QLabel()
        info_form.addRow("来源:", self.source_label)
        info_form.addRow("三角面数:", self.cells_label)
        layout.addWidget(info_grp)

        layout.addStretch()

        self._body_name = ""
        self._zone_name = ""

        self.bc_type_combo.currentIndexChanged.connect(self._on_type_changed)
        for w in (self.t_temp,
                  self.h_tref, self.h_emissivity, self.h_specular, self.h_hc, self.h_tenv,
                  self.f_flux,
                  self.hf_tref, self.hf_emissivity, self.hf_specular, self.hf_hc, self.hf_tenv, self.hf_flux):
            w.valueChanged.connect(self.property_changed.emit)

    def _on_type_changed(self, index):
        self._params_stack.setCurrentIndex(index)
        bt_val = self.bc_type_combo.currentData()
        if bt_val and self._body_name and self._zone_name:
            self.boundary_type_changed.emit(self._body_name, self._zone_name, bt_val)

    def load(self, body_name: str, zone: SurfaceZone):
        self.blockSignals(True)
        self._body_name = body_name
        self._zone_name = zone.name
        self.parent_label.setText(f"归属几何体: {body_name}")

        # 类型
        idx = list(BoundaryType).index(zone.boundary_type)
        self.bc_type_combo.setCurrentIndex(idx)
        self._params_stack.setCurrentIndex(idx)

        bc = zone.boundary
        if isinstance(bc, TemperatureBC):
            self.t_temp.setValue(bc.temperature)
        elif isinstance(bc, ConvectionBC):
            self.h_tref.setValue(bc.tref)
            self.h_emissivity.setValue(bc.emissivity)
            self.h_specular.setValue(bc.specular_fraction)
            self.h_hc.setValue(bc.hc)
            self.h_tenv.setValue(bc.t_env)
        elif isinstance(bc, FluxBC):
            self.f_flux.setValue(bc.flux)
        elif isinstance(bc, CombinedBC):
            self.hf_tref.setValue(bc.tref)
            self.hf_emissivity.setValue(bc.emissivity)
            self.hf_specular.setValue(bc.specular_fraction)
            self.hf_hc.setValue(bc.hc)
            self.hf_tenv.setValue(bc.t_env)
            self.hf_flux.setValue(bc.flux)

        src = zone.source
        if hasattr(src, 'stl_file'):
            self.source_label.setText(f"导入 STL ({os.path.basename(src.stl_file)})")
            self.cells_label.setText("N/A")
        elif hasattr(src, 'cell_ids'):
            self.source_label.setText("涂选")
            self.cells_label.setText(str(len(src.cell_ids)))

        self.blockSignals(False)

    def apply_to(self, zone: SurfaceZone):
        bt_val = self.bc_type_combo.currentData()
        zone.boundary_type = BoundaryType(bt_val)
        idx = self.bc_type_combo.currentIndex()
        if idx == 0:  # T
            zone.boundary = TemperatureBC(temperature=self.t_temp.value())
        elif idx == 1:  # H
            zone.boundary = ConvectionBC(
                tref=self.h_tref.value(), emissivity=self.h_emissivity.value(),
                specular_fraction=self.h_specular.value(), hc=self.h_hc.value(),
                t_env=self.h_tenv.value())
        elif idx == 2:  # F
            zone.boundary = FluxBC(flux=self.f_flux.value())
        elif idx == 3:  # HF
            zone.boundary = CombinedBC(
                tref=self.hf_tref.value(), emissivity=self.hf_emissivity.value(),
                specular_fraction=self.hf_specular.value(), hc=self.hf_hc.value(),
                t_env=self.hf_tenv.value(), flux=self.hf_flux.value())


class ConnectionEditor(QWidget):
    property_changed = pyqtSignal()

    def __init__(self):
        super().__init__()
        layout = QFormLayout(self)
        self.type_label = QLabel()
        self.body_a_label = QLabel()
        self.body_b_label = QLabel()
        layout.addRow("类型:", self.type_label)
        layout.addRow("几何体 A:", self.body_a_label)
        layout.addRow("几何体 B:", self.body_b_label)

        # Solid-Fluid 参数
        self.sf_tref = _spin(300, 0, 1e6, 1, "K")
        self.sf_emissivity = _spin(0.9, 0, 1, 4)
        self.sf_specular = _spin(0, 0, 1, 4)
        self.sf_hc = _spin(0, 0, 1e6, 2, "W/m²/K")
        layout.addRow("参考温度 Tref:", self.sf_tref)
        layout.addRow("发射率 ε:", self.sf_emissivity)
        layout.addRow("镜面分数:", self.sf_specular)
        layout.addRow("对流系数 hc:", self.sf_hc)

        # Solid-Solid 参数
        self.ss_resistance = _spin(0, 0, 1e6, 6, "m²·K/W")
        layout.addRow("接触热阻:", self.ss_resistance)

        self.stl_label = QLabel()
        layout.addRow("界面 STL:", self.stl_label)

        self._conn_name = ""
        for w in (self.sf_tref, self.sf_emissivity, self.sf_specular, self.sf_hc, self.ss_resistance):
            w.valueChanged.connect(self.property_changed.emit)

    def load(self, conn):
        self.blockSignals(True)
        self._conn_name = conn.name
        if isinstance(conn, SolidFluidConnection):
            self.type_label.setText("SOLID_FLUID")
            self.body_a_label.setText(conn.body_a)
            self.body_b_label.setText(conn.body_b)
            self.sf_tref.setValue(conn.tref)
            self.sf_emissivity.setValue(conn.emissivity)
            self.sf_specular.setValue(conn.specular_fraction)
            self.sf_hc.setValue(conn.hc)
            self.sf_tref.show(); self.sf_emissivity.show(); self.sf_specular.show(); self.sf_hc.show()
            self.ss_resistance.hide()
        elif isinstance(conn, SolidSolidConnection):
            self.type_label.setText("SOLID_SOLID")
            self.body_a_label.setText(conn.body_a)
            self.body_b_label.setText(conn.body_b)
            self.ss_resistance.setValue(conn.contact_resistance)
            self.ss_resistance.show()
            self.sf_tref.hide(); self.sf_emissivity.hide(); self.sf_specular.hide(); self.sf_hc.hide()
        stls = ", ".join(os.path.basename(s) for s in conn.stl_files)
        self.stl_label.setText(stls or "-")
        self.blockSignals(False)

    def apply_to(self, conn):
        if isinstance(conn, SolidFluidConnection):
            conn.tref = self.sf_tref.value()
            conn.emissivity = self.sf_emissivity.value()
            conn.specular_fraction = self.sf_specular.value()
            conn.hc = self.sf_hc.value()
        elif isinstance(conn, SolidSolidConnection):
            conn.contact_resistance = self.ss_resistance.value()


class ProbeEditor(QWidget):
    property_changed = pyqtSignal()

    def __init__(self):
        super().__init__()
        layout = QFormLayout(self)

        self.type_combo = QComboBox()
        self.type_combo.addItem("体积温度探针", ProbeType.VOLUME_TEMP.value)
        self.type_combo.addItem("表面温度探针", ProbeType.SURFACE_TEMP.value)
        self.type_combo.addItem("表面通量探针", ProbeType.SURFACE_FLUX.value)
        layout.addRow("类型:", self.type_combo)

        self.px = _spin(0, -1e9, 1e9, 6)
        self.py = _spin(0, -1e9, 1e9, 6)
        self.pz = _spin(0, -1e9, 1e9, 6)
        pos_h = QHBoxLayout()
        pos_h.addWidget(QLabel("X:")); pos_h.addWidget(self.px)
        pos_h.addWidget(QLabel("Y:")); pos_h.addWidget(self.py)
        pos_h.addWidget(QLabel("Z:")); pos_h.addWidget(self.pz)
        layout.addRow("位置:", pos_h)

        # 类型专属
        self.time_combo = QComboBox()
        self.time_combo.addItems(["INF (稳态)", "自定义"])
        self.time_spin = _spin(0, 0, 1e12, 4, "s")
        th = QHBoxLayout()
        th.addWidget(self.time_combo)
        th.addWidget(self.time_spin)
        layout.addRow("采样时刻:", th)

        self.side_edit = QLineEdit()
        layout.addRow("面标识 (SIDE):", self.side_edit)

        self.name_edit = QLineEdit()
        layout.addRow("标签:", self.name_edit)

        self._probe_name = ""
        self.type_combo.currentIndexChanged.connect(self._on_type_changed)
        for w in (self.px, self.py, self.pz, self.time_spin):
            w.valueChanged.connect(self.property_changed.emit)
        for w in (self.side_edit, self.name_edit):
            w.textChanged.connect(self.property_changed.emit)

    def _on_type_changed(self, index):
        pt = self.type_combo.currentData()
        is_vol = (pt == ProbeType.VOLUME_TEMP.value)
        is_surf_temp = (pt == ProbeType.SURFACE_TEMP.value)
        self.time_combo.setVisible(is_vol)
        self.time_spin.setVisible(is_vol)
        self.side_edit.setVisible(is_surf_temp)

    def load(self, probe: Probe):
        self.blockSignals(True)
        self._probe_name = probe.name
        idx = [ProbeType.VOLUME_TEMP, ProbeType.SURFACE_TEMP, ProbeType.SURFACE_FLUX].index(probe.probe_type)
        self.type_combo.setCurrentIndex(idx)
        self.px.setValue(probe.position[0])
        self.py.setValue(probe.position[1])
        self.pz.setValue(probe.position[2])
        if probe.time is None:
            self.time_combo.setCurrentIndex(0)
            self.time_spin.setEnabled(False)
        else:
            self.time_combo.setCurrentIndex(1)
            self.time_spin.setEnabled(True)
            self.time_spin.setValue(probe.time)
        self.side_edit.setText(probe.side)
        self.name_edit.setText(probe.name)
        self._on_type_changed(idx)
        self.blockSignals(False)

    def apply_to(self, probe: Probe):
        pt_val = self.type_combo.currentData()
        probe.probe_type = ProbeType(pt_val)
        probe.position = (self.px.value(), self.py.value(), self.pz.value())
        probe.time = None if self.time_combo.currentIndex() == 0 else self.time_spin.value()
        probe.side = self.side_edit.text()
        probe.name = self.name_edit.text()


class CameraEditor(QWidget):
    property_changed = pyqtSignal()

    def __init__(self):
        super().__init__()
        layout = QFormLayout(self)
        self.cam_name = QLineEdit()
        layout.addRow("名称:", self.cam_name)

        for coord, attr in [("位置 pos", "pos"), ("目标 tgt", "tgt"), ("向上 up", "up")]:
            x = _spin(0, -1e9, 1e9, 6)
            y = _spin(0, -1e9, 1e9, 6)
            z = _spin(0, -1e9, 1e9, 6)
            setattr(self, f"{attr}_x", x)
            setattr(self, f"{attr}_y", y)
            setattr(self, f"{attr}_z", z)
            h = QHBoxLayout()
            h.addWidget(x); h.addWidget(y); h.addWidget(z)
            layout.addRow(f"{coord}:", h)

        self.fov = _spin(30, 1, 180, 1, "°")
        self.spp = _ispin(32, 1, 1000000)
        self.res_w = _ispin(320, 1, 8192)
        self.res_h = _ispin(320, 1, 8192)
        layout.addRow("FOV:", self.fov)
        layout.addRow("SPP:", self.spp)
        rh = QHBoxLayout()
        rh.addWidget(self.res_w); rh.addWidget(QLabel("×")); rh.addWidget(self.res_h)
        layout.addRow("分辨率:", rh)

        self._cam_name = ""

        self.cam_name.textChanged.connect(self.property_changed.emit)
        for w in (self.pos_x, self.pos_y, self.pos_z,
                  self.tgt_x, self.tgt_y, self.tgt_z,
                  self.up_x, self.up_y, self.up_z,
                  self.fov, self.spp, self.res_w, self.res_h):
            w.valueChanged.connect(self.property_changed.emit)

    def load(self, cam: IRCamera):
        self.blockSignals(True)
        self._cam_name = cam.name
        self.cam_name.setText(cam.name)
        self.pos_x.setValue(cam.position[0])
        self.pos_y.setValue(cam.position[1])
        self.pos_z.setValue(cam.position[2])
        self.tgt_x.setValue(cam.target[0])
        self.tgt_y.setValue(cam.target[1])
        self.tgt_z.setValue(cam.target[2])
        self.up_x.setValue(cam.up[0])
        self.up_y.setValue(cam.up[1])
        self.up_z.setValue(cam.up[2])
        self.fov.setValue(cam.fov)
        self.spp.setValue(cam.spp)
        self.res_w.setValue(cam.resolution[0])
        self.res_h.setValue(cam.resolution[1])
        self.blockSignals(False)

    def apply_to(self, cam: IRCamera):
        cam.name = self.cam_name.text()
        cam.position = (self.pos_x.value(), self.pos_y.value(), self.pos_z.value())
        cam.target = (self.tgt_x.value(), self.tgt_y.value(), self.tgt_z.value())
        cam.up = (self.up_x.value(), self.up_y.value(), self.up_z.value())
        cam.fov = self.fov.value()
        cam.spp = self.spp.value()
        cam.resolution = (self.res_w.value(), self.res_h.value())


# ═══════════════════════════════════════════════════════════════
# 主属性面板 (QStackedWidget)
# ═══════════════════════════════════════════════════════════════

PAGE_EMPTY = 0
PAGE_GLOBAL = 1
PAGE_BODY = 2
PAGE_ZONE = 3
PAGE_CONN = 4
PAGE_PROBE = 5
PAGE_CAMERA = 6
PAGE_LIGHT = 7
PAGE_AMBIENT = 8
PAGE_TASK_QUEUE = 9
PAGE_TASK = 10


class LightEditor(QWidget):
    property_changed = pyqtSignal()

    def __init__(self):
        super().__init__()
        layout = QFormLayout(self)

        self.name_edit = QLineEdit()
        layout.addRow("名称:", self.name_edit)

        self.type_label = QLabel()
        layout.addRow("类型:", self.type_label)

        # 位置 (DEFAULT / SPHERICAL_SOURCE)
        self.pos_x = _spin(0, -1e9, 1e9, 6)
        self.pos_y = _spin(0, -1e9, 1e9, 6)
        self.pos_z = _spin(0, -1e9, 1e9, 6)
        ph = QHBoxLayout()
        ph.addWidget(self.pos_x); ph.addWidget(self.pos_y); ph.addWidget(self.pos_z)
        self._pos_label = QLabel("位置:")
        layout.addRow(self._pos_label, ph)

        # SPHERICAL_SOURCE 参数
        self.radius = _spin(1.0, 0, 1e9, 6, "m")
        self._radius_label = QLabel("半径:")
        layout.addRow(self._radius_label, self.radius)

        self.power = _spin(0.0, 0, 1e15, 4, "W")
        self._power_label = QLabel("功率:")
        layout.addRow(self._power_label, self.power)

        self.diffuse_radiance = _spin(0.0, 0, 1e15, 4, "W/m²/sr")
        self._diff_label = QLabel("漫射辐亮度:")
        layout.addRow(self._diff_label, self.diffuse_radiance)

        # 颜色 (仅 VTK 显示)
        self.color_r = _spin(1.0, 0, 1, 4)
        self.color_g = _spin(1.0, 0, 1, 4)
        self.color_b = _spin(1.0, 0, 1, 4)
        ch = QHBoxLayout()
        ch.addWidget(QLabel("R:")); ch.addWidget(self.color_r)
        ch.addWidget(QLabel("G:")); ch.addWidget(self.color_g)
        ch.addWidget(QLabel("B:")); ch.addWidget(self.color_b)
        self._color_label = QLabel("颜色:")
        layout.addRow(self._color_label, ch)

        # SPHERICAL_SOURCE_PROG 原始行 (只读)
        self.raw_line_edit = QLineEdit()
        self.raw_line_edit.setReadOnly(True)
        self._raw_label = QLabel("原始定义:")
        layout.addRow(self._raw_label, self.raw_line_edit)

        self._light_name = ""
        for w in (self.pos_x, self.pos_y, self.pos_z,
                  self.radius, self.power, self.diffuse_radiance,
                  self.color_r, self.color_g, self.color_b):
            w.valueChanged.connect(self.property_changed.emit)
        self.name_edit.textChanged.connect(self.property_changed.emit)

    def _set_field_visibility(self, light_type: LightType):
        """根据光源类型显隐字段。"""
        is_prog = (light_type == LightType.SPHERICAL_SOURCE_PROG)
        is_sphere = (light_type == LightType.SPHERICAL_SOURCE)
        is_default = (light_type == LightType.DEFAULT)

        # 位置: DEFAULT 和 SPHERICAL_SOURCE 可见
        for w in (self._pos_label, self.pos_x, self.pos_y, self.pos_z):
            w.setVisible(not is_prog)

        # 球面源参数: 仅 SPHERICAL_SOURCE
        for w in (self._radius_label, self.radius,
                  self._power_label, self.power,
                  self._diff_label, self.diffuse_radiance):
            w.setVisible(is_sphere)

        # 颜色: 非 PROG 类型
        for w in (self._color_label, self.color_r, self.color_g, self.color_b):
            w.setVisible(not is_prog)

        # 原始行: 仅 PROG
        self._raw_label.setVisible(is_prog)
        self.raw_line_edit.setVisible(is_prog)

        # 名称: PROG 不可编辑
        self.name_edit.setReadOnly(is_prog)

    def load(self, light: SceneLight):
        self.blockSignals(True)
        self._light_name = light.name
        self.name_edit.setText(light.name)
        _type_labels = {
            LightType.DEFAULT: "默认光源",
            LightType.SPHERICAL_SOURCE: "常量球面源",
            LightType.SPHERICAL_SOURCE_PROG: "可编程球面源",
        }
        self.type_label.setText(_type_labels.get(light.light_type, "?"))
        self._set_field_visibility(light.light_type)

        self.pos_x.setValue(light.position[0])
        self.pos_y.setValue(light.position[1])
        self.pos_z.setValue(light.position[2])
        self.radius.setValue(light.radius)
        self.power.setValue(light.power)
        self.diffuse_radiance.setValue(light.diffuse_radiance)
        self.color_r.setValue(light.color[0])
        self.color_g.setValue(light.color[1])
        self.color_b.setValue(light.color[2])
        self.raw_line_edit.setText(light.raw_line)
        self.blockSignals(False)

    def apply_to(self, light: SceneLight):
        light.name = self.name_edit.text()
        light.position = (self.pos_x.value(), self.pos_y.value(), self.pos_z.value())
        light.radius = self.radius.value()
        light.power = self.power.value()
        light.diffuse_radiance = self.diffuse_radiance.value()
        light.color = (self.color_r.value(), self.color_g.value(), self.color_b.value())


class AmbientEditor(QWidget):
    property_changed = pyqtSignal()

    def __init__(self):
        super().__init__()
        layout = QFormLayout(self)
        layout.addRow(QLabel("环境基本光照始终存在，不受其他光源影响。"))
        self.intensity = _spin(0.15, 0.0, 1.0, 4)
        layout.addRow("强度:", self.intensity)
        self.intensity.valueChanged.connect(self.property_changed.emit)

    def load(self, ambient_intensity: float):
        self.blockSignals(True)
        self.intensity.setValue(ambient_intensity)
        self.blockSignals(False)

    def apply_to_model(self, model):
        model.ambient_intensity = self.intensity.value()


class PropertyPanel(QWidget):
    """动态属性编辑面板，根据选中对象切换内容。"""

    property_changed = pyqtSignal(str, str, object)
    boundary_type_changed = pyqtSignal(str, str, str)
    request_paint_mode = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        self._title = QLabel("属性")
        self._title.setStyleSheet("font-weight: bold; font-size: 14px;")
        layout.addWidget(self._title)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self._stack = QStackedWidget()
        self._stack.setMinimumWidth(380)
        scroll.setWidget(self._stack)
        layout.addWidget(scroll)

        # 页
        self._empty = QLabel("选择一个场景对象以查看属性")
        self._empty.setAlignment(Qt.AlignCenter)
        self._stack.addWidget(self._empty)           # 0

        self.global_editor = GlobalSettingsEditor()
        self._stack.addWidget(self.global_editor)     # 1

        self.body_editor = BodyEditor()
        self._stack.addWidget(self.body_editor)       # 2

        self.zone_editor = SurfaceZoneEditor()
        self._stack.addWidget(self.zone_editor)       # 3

        self.conn_editor = ConnectionEditor()
        self._stack.addWidget(self.conn_editor)       # 4

        self.probe_editor = ProbeEditor()
        self._stack.addWidget(self.probe_editor)      # 5

        self.camera_editor = CameraEditor()
        self._stack.addWidget(self.camera_editor)     # 6

        self.light_editor = LightEditor()
        self._stack.addWidget(self.light_editor)      # 7

        self.ambient_editor = AmbientEditor()
        self._stack.addWidget(self.ambient_editor)    # 8

        self.task_queue_editor = TaskQueueEditor()
        self._stack.addWidget(self.task_queue_editor)  # 9

        self.task_editor = TaskEditor()
        self._stack.addWidget(self.task_editor)        # 10

        self._model: SceneModel = SceneModel()

        # 内部信号转发
        self.body_editor.request_paint_mode.connect(self.request_paint_mode.emit)
        self.zone_editor.boundary_type_changed.connect(self.boundary_type_changed.emit)

    def set_model(self, model: SceneModel):
        self._model = model

    def show_empty(self):
        self._title.setText("属性")
        self._stack.setCurrentIndex(PAGE_EMPTY)

    def show_global(self):
        self._title.setText("全局设置")
        self.global_editor.load(self._model.global_settings, self._model)
        self._stack.setCurrentIndex(PAGE_GLOBAL)

    def show_body(self, body_name: str):
        body = self._model.get_body_by_name(body_name)
        if not body:
            return
        self._title.setText(f"几何体: {body_name}")
        self.body_editor.load(body)
        self._stack.setCurrentIndex(PAGE_BODY)

    def show_zone(self, body_name: str, zone_name: str):
        zone = self._model.get_zone(body_name, zone_name)
        if not zone:
            return
        self._title.setText(f"表面区域: {zone_name}")
        self.zone_editor.load(body_name, zone)
        self._stack.setCurrentIndex(PAGE_ZONE)

    def show_connection(self, conn_name: str):
        conn = self._model.get_connection_by_name(conn_name)
        if not conn:
            return
        self._title.setText(f"连接: {conn_name}")
        self.conn_editor.load(conn)
        self._stack.setCurrentIndex(PAGE_CONN)

    def show_probe(self, probe_name: str):
        probe = self._model.get_probe_by_name(probe_name)
        if not probe:
            return
        self._title.setText(f"探针: {probe_name}")
        self.probe_editor.load(probe)
        self._stack.setCurrentIndex(PAGE_PROBE)

    def show_camera(self, cam_name: str):
        cam = self._model.get_camera_by_name(cam_name)
        if not cam:
            return
        self._title.setText(f"摄像机: {cam_name}")
        self.camera_editor.load(cam)
        self._stack.setCurrentIndex(PAGE_CAMERA)

    def show_light(self, light_name: str):
        light = self._model.get_light_by_name(light_name)
        if not light:
            return
        _type_labels = {
            LightType.DEFAULT: "默认光源",
            LightType.SPHERICAL_SOURCE: "常量球面源",
            LightType.SPHERICAL_SOURCE_PROG: "可编程球面源",
        }
        ltype = _type_labels.get(light.light_type, "?")
        self._title.setText(f"光源: {light_name} [{ltype}]")
        self.light_editor.load(light)
        self._stack.setCurrentIndex(PAGE_LIGHT)

    def show_ambient(self):
        self._title.setText("环境基本光照")
        self.ambient_editor.load(self._model.ambient_intensity)
        self._stack.setCurrentIndex(PAGE_AMBIENT)

    def show_task_queue(self):
        self._title.setText("任务队列")
        self.task_queue_editor.load(self._model.task_queue)
        self._stack.setCurrentIndex(PAGE_TASK_QUEUE)

    def show_task(self, task_id: str):
        task = self._find_task(task_id)
        if not task:
            return
        self._title.setText(f"任务: {task.name}")
        self.task_editor.load(task, self._model)
        self._stack.setCurrentIndex(PAGE_TASK)

    def _find_task(self, task_id: str):
        for t in self._model.task_queue.tasks:
            if t.id == task_id:
                return t
        return None

    def apply_current(self):
        """将当前编辑器中的值写回模型。"""
        page = self._stack.currentIndex()
        if page == PAGE_GLOBAL:
            self.global_editor.apply_to(self._model.global_settings)
        elif page == PAGE_BODY:
            body = self._model.get_body_by_name(self.body_editor._body_name)
            if body:
                self.body_editor.apply_to(body)
        elif page == PAGE_ZONE:
            zone = self._model.get_zone(self.zone_editor._body_name, self.zone_editor._zone_name)
            if zone:
                self.zone_editor.apply_to(zone)
        elif page == PAGE_CONN:
            conn = self._model.get_connection_by_name(self.conn_editor._conn_name)
            if conn:
                self.conn_editor.apply_to(conn)
        elif page == PAGE_PROBE:
            probe = self._model.get_probe_by_name(self.probe_editor._probe_name)
            if probe:
                self.probe_editor.apply_to(probe)
        elif page == PAGE_CAMERA:
            cam = self._model.get_camera_by_name(self.camera_editor._cam_name)
            if cam:
                self.camera_editor.apply_to(cam)
        elif page == PAGE_LIGHT:
            light = self._model.get_light_by_name(self.light_editor._light_name)
            if light:
                self.light_editor.apply_to(light)
        elif page == PAGE_AMBIENT:
            self.ambient_editor.apply_to_model(self._model)
        elif page == PAGE_TASK_QUEUE:
            self.task_queue_editor.apply_to(self._model.task_queue)
        elif page == PAGE_TASK:
            task = self._find_task(self.task_editor._task_id)
            if task:
                self.task_editor.apply_to(task)
