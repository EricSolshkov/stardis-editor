"""
S1: SceneModel — 几何中心数据模型

以 Body（几何体）为核心组织单元：
- 每个 Body 拥有体积属性和表面区域列表
- 表面区域包含边界条件
- 连接描述几何体间接触关系
- 探针和摄像机为辅助对象
"""

from enum import Enum
from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Set, Union
import json
import os
import copy

from models.task_model import TaskQueue, task_queue_to_dict, dict_to_task_queue


# ─── 枚举 ───────────────────────────────────────────────────────

class BodyType(Enum):
    SOLID = "SOLID"
    FLUID = "FLUID"


class Side(Enum):
    FRONT = "FRONT"
    BACK = "BACK"
    BOTH = "BOTH"


class NormalOrientation(Enum):
    """法线朝向语义标注。"""
    UNKNOWN = "unknown"   # 未确认（开放网格或未检测）
    OUTWARD = "outward"   # 法线指向外侧
    INWARD  = "inward"    # 法线指向内侧


class BoundaryType(Enum):
    T_BOUNDARY = "T_BOUNDARY_FOR_SOLID"
    H_BOUNDARY = "H_BOUNDARY_FOR_SOLID"
    F_BOUNDARY = "F_BOUNDARY_FOR_SOLID"
    HF_BOUNDARY = "HF_BOUNDARY_FOR_SOLID"


class ProbeType(Enum):
    VOLUME_TEMP = "VOLUME_TEMP"
    SURFACE_TEMP = "SURFACE_TEMP"
    SURFACE_FLUX = "SURFACE_FLUX"


class LightType(Enum):
    DEFAULT = "DEFAULT"
    SPHERICAL_SOURCE = "SPHERICAL_SOURCE"
    SPHERICAL_SOURCE_PROG = "SPHERICAL_SOURCE_PROG"


# ─── 材质 ───────────────────────────────────────────────────────

@dataclass
class MaterialRef:
    conductivity: float = 1.0    # λ (W/m/K) — SOLID only
    density: float = 1.0         # ρ (kg/m³)
    specific_heat: float = 1.0   # cp (J/kg/K)
    source_material: str = ""    # 来源材质名称（空串 = 手动输入）


# ─── 体积属性 ───────────────────────────────────────────────────

@dataclass
class VolumeProperties:
    body_type: BodyType = BodyType.SOLID
    material: MaterialRef = field(default_factory=MaterialRef)
    delta: Optional[float] = None        # None → AUTO
    initial_temp: float = 300.0
    imposed_temp: Optional[float] = None # None → UNKNOWN
    volumetric_power: float = 0.0        # SOLID only
    side: Side = Side.FRONT


def clone_volume(vol: VolumeProperties) -> VolumeProperties:
    """深拷贝 VolumeProperties，避免前后侧共享同一对象。"""
    return copy.deepcopy(vol)


# ─── 边界条件变体 ────────────────────────────────────────────────

@dataclass
class TemperatureBC:
    """T_BOUNDARY_FOR_SOLID: 固定温度"""
    temperature: float = 300.0


@dataclass
class ConvectionBC:
    """H_BOUNDARY_FOR_SOLID: 对流+辐射"""
    tref: float = 300.0
    emissivity: float = 0.9
    specular_fraction: float = 0.0
    hc: float = 0.0
    t_env: float = 300.0


@dataclass
class FluxBC:
    """F_BOUNDARY_FOR_SOLID: 热通量"""
    flux: float = 0.0


@dataclass
class CombinedBC:
    """HF_BOUNDARY_FOR_SOLID: 对流+辐射+通量"""
    tref: float = 300.0
    emissivity: float = 0.9
    specular_fraction: float = 0.0
    hc: float = 0.0
    t_env: float = 300.0
    flux: float = 0.0


BoundaryCondition = Union[TemperatureBC, ConvectionBC, FluxBC, CombinedBC]

BOUNDARY_TYPE_TO_CLASS = {
    BoundaryType.T_BOUNDARY: TemperatureBC,
    BoundaryType.H_BOUNDARY: ConvectionBC,
    BoundaryType.F_BOUNDARY: FluxBC,
    BoundaryType.HF_BOUNDARY: CombinedBC,
}

BOUNDARY_TYPE_LABELS = {
    BoundaryType.T_BOUNDARY: "固定温度",
    BoundaryType.H_BOUNDARY: "对流+辐射",
    BoundaryType.F_BOUNDARY: "热通量",
    BoundaryType.HF_BOUNDARY: "组合",
}


# ─── 表面区域来源 ────────────────────────────────────────────────

@dataclass
class ImportedSTL:
    """来源方式 A: 导入已有 STL 文件"""
    stl_file: str = ""


@dataclass
class PaintedRegion:
    """来源方式 B: 涂选生成"""
    cell_ids: Set[int] = field(default_factory=set)


SurfaceZoneSource = Union[ImportedSTL, PaintedRegion]


# ─── 表面区域 ───────────────────────────────────────────────────

@dataclass
class SurfaceZone:
    zone_id: int = 0                        # 区域唯一 ID（BoundaryLabel 中存储的值，0=未分配）
    name: str = ""
    source: SurfaceZoneSource = field(default_factory=ImportedSTL)
    boundary_type: BoundaryType = BoundaryType.H_BOUNDARY
    boundary: BoundaryCondition = field(default_factory=ConvectionBC)
    color: Tuple[float, float, float, float] = (0.7, 0.7, 0.7, 1.0)  # RGBA 0-1


# ─── 几何体 (核心组织单元) ────────────────────────────────────────

@dataclass
class Body:
    name: str = ""
    stl_files: List[str] = field(default_factory=list)
    # 兼容层: 旧代码仍可能通过 body.volume 读写
    volume: VolumeProperties = field(default_factory=VolumeProperties)
    # 新模型: 始终用 FRONT/BACK 表达底层介质
    front_volume: Optional[VolumeProperties] = None
    back_volume: Optional[VolumeProperties] = None
    front_enabled: bool = False
    back_enabled: bool = False
    sync_front_back: bool = False
    next_zone_id: int = 1                   # 区域 ID 分配计数器（单调递增，删除后不重用）
    surface_zones: List[SurfaceZone] = field(default_factory=list)
    normal_orientation: NormalOrientation = NormalOrientation.UNKNOWN  # 法线朝向语义标注

    def __post_init__(self):
        # 从 legacy volume 初始化 front/back（首次构建时）
        if self.front_volume is None and self.back_volume is None:
            legacy = clone_volume(self.volume)
            if legacy.side == Side.BOTH:
                self.front_volume = clone_volume(legacy)
                self.back_volume = clone_volume(legacy)
                self.front_enabled = True
                self.back_enabled = True
                self.sync_front_back = True
            elif legacy.side == Side.BACK:
                self.front_volume = clone_volume(legacy)
                self.back_volume = clone_volume(legacy)
                self.front_enabled = False
                self.back_enabled = True
                self.sync_front_back = False
            else:
                self.front_volume = clone_volume(legacy)
                self.back_volume = clone_volume(legacy)
                self.front_enabled = True
                self.back_enabled = False
                self.sync_front_back = False
        else:
            if self.front_volume is None and self.back_volume is not None:
                self.front_volume = clone_volume(self.back_volume)
            if self.back_volume is None and self.front_volume is not None:
                self.back_volume = clone_volume(self.front_volume)

            if not self.front_enabled and not self.back_enabled:
                # 默认启用 FRONT 侧
                self.front_enabled = True

        self._refresh_legacy_volume_view()

    def allocate_zone_id(self) -> int:
        """分配下一个 zone_id 并递增计数器。"""
        zid = self.next_zone_id
        self.next_zone_id += 1
        return zid

    def effective_side(self) -> Side:
        if self.front_enabled and self.back_enabled:
            return Side.BOTH
        if self.back_enabled:
            return Side.BACK
        return Side.FRONT

    def set_side_volume(self, side: Side, vol: VolumeProperties):
        """写入指定侧参数并更新启用状态。"""
        if side == Side.BOTH:
            self.front_volume = clone_volume(vol)
            self.back_volume = clone_volume(vol)
            self.front_enabled = True
            self.back_enabled = True
            self.sync_front_back = True
        elif side == Side.FRONT:
            self.front_volume = clone_volume(vol)
            self.front_enabled = True
            self.sync_front_back = False
        else:
            self.back_volume = clone_volume(vol)
            self.back_enabled = True
            self.sync_front_back = False
        self._refresh_legacy_volume_view()

    def get_side_volume(self, side: Side) -> VolumeProperties:
        if side == Side.BACK:
            return self.back_volume
        return self.front_volume

    def _refresh_legacy_volume_view(self):
        """更新 body.volume 兼容视图，供旧逻辑读取。"""
        side = self.effective_side()
        base = self.back_volume if side == Side.BACK else self.front_volume
        if base is None:
            base = VolumeProperties()
        self.volume = clone_volume(base)
        self.volume.side = side


# ─── 全局设置 ───────────────────────────────────────────────────

@dataclass
class GlobalSettings:
    t_ambient: float = 300.0
    t_reference: float = 300.0
    scale: float = 1.0


# ─── 连接 ───────────────────────────────────────────────────────

@dataclass
class SolidFluidConnection:
    name: str = ""
    tref: float = 300.0
    emissivity: float = 0.9
    specular_fraction: float = 0.0
    hc: float = 0.0
    body_a: str = ""   # body name
    body_b: str = ""   # body name
    stl_files: List[str] = field(default_factory=list)


@dataclass
class SolidSolidConnection:
    name: str = ""
    contact_resistance: float = 0.0
    body_a: str = ""
    body_b: str = ""
    stl_files: List[str] = field(default_factory=list)


Connection = Union[SolidFluidConnection, SolidSolidConnection]


# ─── 探针 ───────────────────────────────────────────────────────

@dataclass
class Probe:
    name: str = ""
    probe_type: ProbeType = ProbeType.VOLUME_TEMP
    position: Tuple[float, float, float] = (0.0, 0.0, 0.0)
    time: Optional[float] = None   # VOLUME_TEMP: None → INF
    side: str = ""                 # SURFACE_TEMP: face identifier
    color: Tuple[float, float, float, float] = (1.0, 1.0, 0.0, 1.0)


# ─── 光源 ───────────────────────────────────────────────────────

@dataclass
class SceneLight:
    name: str = "DefaultLight"
    light_type: LightType = LightType.DEFAULT
    # 通用参数
    color: Tuple[float, float, float] = (1.0, 1.0, 1.0)
    position: Tuple[float, float, float] = (1.0, 1.0, 1.0)
    enabled: bool = True
    # SPHERICAL_SOURCE 参数
    radius: float = 1.0          # 半径 (m)
    power: float = 0.0           # 功率 (W)
    diffuse_radiance: float = 0.0  # 漫射辐射亮度 (W/m²/sr)
    # SPHERICAL_SOURCE_PROG 原始行 (原样保存)
    raw_line: str = ""


# ─── IR 摄像机 ──────────────────────────────────────────────────

@dataclass
class IRCamera:
    name: str = "Camera1"
    position: Tuple[float, float, float] = (1.0, 1.0, 1.0)
    target: Tuple[float, float, float] = (0.0, 0.0, 0.0)
    up: Tuple[float, float, float] = (0.0, 0.0, 1.0)
    fov: float = 30.0
    spp: int = 32
    resolution: Tuple[int, int] = (320, 320)


# ─── 场景模型 ───────────────────────────────────────────────────

@dataclass
class SceneModel:
    global_settings: GlobalSettings = field(default_factory=GlobalSettings)
    bodies: List[Body] = field(default_factory=list)
    connections: List[Connection] = field(default_factory=list)
    probes: List[Probe] = field(default_factory=list)
    cameras: List[IRCamera] = field(default_factory=list)
    lights: List[SceneLight] = field(default_factory=list)
    ambient_intensity: float = 0.15  # 环境基本光照强度，恒存在
    task_queue: TaskQueue = field(default_factory=TaskQueue)

    def __post_init__(self):
        if not self.cameras:
            self.cameras.append(IRCamera())
        self.ensure_default_light()

    # ── 查询 ──

    def get_body_by_name(self, name: str) -> Optional[Body]:
        for body in self.bodies:
            if body.name == name:
                return body
        return None

    def get_zone(self, body_name: str, zone_name: str) -> Optional[SurfaceZone]:
        body = self.get_body_by_name(body_name)
        if body:
            for z in body.surface_zones:
                if z.name == zone_name:
                    return z
        return None

    def get_connection_by_name(self, name: str) -> Optional[Connection]:
        for c in self.connections:
            if c.name == name:
                return c
        return None

    def get_probe_by_name(self, name: str) -> Optional[Probe]:
        for p in self.probes:
            if p.name == name:
                return p
        return None

    def get_camera_by_name(self, name: str) -> Optional[IRCamera]:
        for c in self.cameras:
            if c.name == name:
                return c
        return None

    def next_probe_name(self) -> str:
        existing = {p.name for p in self.probes}
        i = 1
        while f"P{i}" in existing:
            i += 1
        return f"P{i}"

    def next_camera_name(self) -> str:
        existing = {c.name for c in self.cameras}
        i = 1
        while f"Camera{i}" in existing:
            i += 1
        return f"Camera{i}"

    def get_light_by_name(self, name: str) -> Optional[SceneLight]:
        for l in self.lights:
            if l.name == name:
                return l
        return None

    def next_light_name(self, prefix: str = "Light") -> str:
        existing = {l.name for l in self.lights}
        i = 1
        while f"{prefix}{i}" in existing:
            i += 1
        return f"{prefix}{i}"

    def has_active_light(self) -> bool:
        """是否存在参与光照的光源（DEFAULT 或 SPHERICAL_SOURCE）。"""
        return any(l.light_type in (LightType.DEFAULT, LightType.SPHERICAL_SOURCE)
                   for l in self.lights)

    def ensure_default_light(self):
        """若没有 DEFAULT 或 SPHERICAL_SOURCE 光源，创建一个默认光源。"""
        if not self.has_active_light():
            self.lights.append(SceneLight(
                name="DefaultLight",
                light_type=LightType.DEFAULT,
            ))

    # ── 验证 (stub — 始终通过) ──

    def validate(self) -> Tuple[bool, List[str]]:
        """几何/属性校验 stub — stardis 负责实际验证。"""
        return True, []

    def compute_coverage(self, body_name: str) -> float:
        """覆盖率 stub — 始终返回 1.0 (100%)。"""
        return 1.0

    # ── 序列化为项目 JSON ──

    def save_project(self, path: str):
        """保存编辑器项目元数据（探针、摄像机、光源、表面区域父子关系）。"""
        data = {
            "probes": [_probe_to_dict(p) for p in self.probes],
            "cameras": [_camera_to_dict(c) for c in self.cameras],
            "lights": [_light_to_dict(l) for l in self.lights],
            "ambient_intensity": self.ambient_intensity,
            "body_zone_ids": {},
            "zone_parent_map": {},
        }
        for body in self.bodies:
            zones_data = []
            for zone in body.surface_zones:
                zd = {"zone_id": zone.zone_id, "name": zone.name}
                zones_data.append(zd)
                # 记录表面区域→父几何体映射，加载时据此确定归属
                data["zone_parent_map"][zone.name] = body.name
            data["body_zone_ids"][body.name] = {
                "next_zone_id": body.next_zone_id,
                "zones": zones_data,
            }
        # task_queue
        if self.task_queue.tasks:
            data["task_queue"] = task_queue_to_dict(self.task_queue)

        # body_materials — 材质来源标记（兼容旧格式: body_name -> str）
        body_materials = {}
        for body in self.bodies:
            front_src = (body.front_volume.material.source_material
                         if body.front_enabled and body.front_volume else "")
            back_src = (body.back_volume.material.source_material
                        if body.back_enabled and body.back_volume else "")
            if not front_src and not back_src:
                continue
            if front_src == back_src or not back_src:
                # 两侧相同 或 仅 front 有材质 → 简写为字符串
                body_materials[body.name] = front_src
            elif not front_src:
                # 仅 back 有材质 → 仍需 dict 以区分侧
                body_materials[body.name] = {"front": "", "back": back_src}
            else:
                body_materials[body.name] = {
                    "front": front_src,
                    "back": back_src,
                }
        if body_materials:
            data["body_materials"] = body_materials

        # normal_orientations — 法线朝向语义标注
        data["normal_orientations"] = {
            body.name: body.normal_orientation.value
            for body in self.bodies
        }

        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def load_project(self, path: str):
        """从项目文件恢复探针、摄像机、光源、涂选状态。"""
        if not os.path.isfile(path):
            return
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.probes = [_dict_to_probe(d) for d in data.get("probes", [])]
        self.cameras = [_dict_to_camera(d) for d in data.get("cameras", [])]
        if "lights" in data:
            self.lights = [_dict_to_light(d) for d in data["lights"]]
        self.ambient_intensity = data.get("ambient_intensity", 0.15)

        # task_queue
        tq_data = data.get("task_queue")
        if tq_data:
            self.task_queue = dict_to_task_queue(tq_data)
        else:
            self.task_queue = TaskQueue()

        # 恢复 body_materials — 材质来源标记（兼容旧格式）
        body_materials = data.get("body_materials", {})
        for body in self.bodies:
            src = body_materials.get(body.name, "")
            if isinstance(src, str):
                if src:
                    if body.front_volume:
                        body.front_volume.material.source_material = src
                    if body.back_volume:
                        body.back_volume.material.source_material = src
            elif isinstance(src, dict):
                if body.front_volume:
                    body.front_volume.material.source_material = src.get("front", "")
                if body.back_volume:
                    body.back_volume.material.source_material = src.get("back", "")

            body._refresh_legacy_volume_view()

        # 恢复 normal_orientations — 法线朝向语义标注
        orientations = data.get("normal_orientations", {})
        for body in self.bodies:
            val = orientations.get(body.name, "unknown")
            try:
                body.normal_orientation = NormalOrientation(val)
            except ValueError:
                body.normal_orientation = NormalOrientation.UNKNOWN

        # 恢复 zone_id / next_zone_id（cell_ids 不在 JSON 中，由三角形哈希匹配恢复）
        body_zone_ids = data.get("body_zone_ids", {})
        for body in self.bodies:
            bdata = body_zone_ids.get(body.name)
            if bdata:
                body.next_zone_id = bdata.get("next_zone_id", body.next_zone_id)
                for zd in bdata.get("zones", []):
                    zone = self.get_zone(body.name, zd.get("name", ""))
                    if zone:
                        zone.zone_id = zd.get("zone_id", zone.zone_id)


# ─── 法线朝向检测 ────────────────────────────────────────────────

def detect_normal_orientation(stl_path: str) -> NormalOrientation:
    """
    检测 STL 网格的法线朝向。

    对封闭网格使用有符号体积法（散度定理）:
      V_signed = (1/6) Σ v0 · (v1 × v2)
      V > 0 → 法线朝外 (OUTWARD)
      V < 0 → 法线朝内 (INWARD)

    开放网格返回 UNKNOWN。
    """
    try:
        import vtk
    except ImportError:
        return NormalOrientation.UNKNOWN

    if not os.path.isfile(stl_path):
        return NormalOrientation.UNKNOWN

    reader = vtk.vtkSTLReader()
    reader.SetFileName(stl_path)
    reader.Update()
    poly = reader.GetOutput()

    if poly is None or poly.GetNumberOfCells() == 0:
        return NormalOrientation.UNKNOWN

    return detect_normal_orientation_from_polydata(poly)


def detect_normal_orientation_from_polydata(poly) -> NormalOrientation:
    """
    从 vtkPolyData 检测法线朝向。

    封闭网格 → OUTWARD / INWARD；开放网格 → UNKNOWN。
    """
    try:
        import vtk
    except ImportError:
        return NormalOrientation.UNKNOWN

    if poly is None or poly.GetNumberOfCells() == 0:
        return NormalOrientation.UNKNOWN

    # 合并重复顶点，确保拓扑正确（STL 常见重复顶点）
    clean = vtk.vtkCleanPolyData()
    clean.SetInputData(poly)
    clean.Update()
    cleaned = clean.GetOutput()

    # 检查是否封闭
    feature_edges = vtk.vtkFeatureEdges()
    feature_edges.BoundaryEdgesOn()
    feature_edges.NonManifoldEdgesOn()
    feature_edges.FeatureEdgesOff()
    feature_edges.ManifoldEdgesOff()
    feature_edges.SetInputData(cleaned)
    feature_edges.Update()

    if feature_edges.GetOutput().GetNumberOfCells() > 0:
        return NormalOrientation.UNKNOWN  # 开放网格

    # 计算有符号体积
    signed_volume = 0.0
    for i in range(poly.GetNumberOfCells()):
        cell = poly.GetCell(i)
        if cell.GetNumberOfPoints() != 3:
            continue
        p0 = poly.GetPoint(cell.GetPointId(0))
        p1 = poly.GetPoint(cell.GetPointId(1))
        p2 = poly.GetPoint(cell.GetPointId(2))
        # v0 · (v1 × v2)
        cross = (
            p1[1] * p2[2] - p1[2] * p2[1],
            p1[2] * p2[0] - p1[0] * p2[2],
            p1[0] * p2[1] - p1[1] * p2[0],
        )
        signed_volume += p0[0] * cross[0] + p0[1] * cross[1] + p0[2] * cross[2]

    signed_volume /= 6.0

    if signed_volume > 0:
        return NormalOrientation.OUTWARD
    elif signed_volume < 0:
        return NormalOrientation.INWARD
    else:
        return NormalOrientation.UNKNOWN


# ─── 序列化辅助 ─────────────────────────────────────────────────

def _probe_to_dict(p: Probe) -> dict:
    return {
        "name": p.name,
        "type": p.probe_type.value,
        "position": list(p.position),
        "time": p.time,
        "side": p.side,
        "color": list(p.color),
    }


def _dict_to_probe(d: dict) -> Probe:
    return Probe(
        name=d.get("name", ""),
        probe_type=ProbeType(d.get("type", "VOLUME_TEMP")),
        position=tuple(d.get("position", [0, 0, 0])),
        time=d.get("time"),
        side=d.get("side", ""),
        color=tuple(d.get("color", [1, 1, 0, 1])),
    )


def _camera_to_dict(c: IRCamera) -> dict:
    return {
        "name": c.name,
        "position": list(c.position),
        "target": list(c.target),
        "up": list(c.up),
        "fov": c.fov,
        "spp": c.spp,
        "resolution": list(c.resolution),
    }


def _dict_to_camera(d: dict) -> IRCamera:
    return IRCamera(
        name=d.get("name", "Camera1"),
        position=tuple(d.get("position", [1, 1, 1])),
        target=tuple(d.get("target", [0, 0, 0])),
        up=tuple(d.get("up", [0, 0, 1])),
        fov=d.get("fov", 30.0),
        spp=d.get("spp", 32),
        resolution=tuple(d.get("resolution", [320, 320])),
    )


def _light_to_dict(l: SceneLight) -> dict:
    return {
        "name": l.name,
        "light_type": l.light_type.value,
        "color": list(l.color),
        "position": list(l.position),
        "enabled": l.enabled,
        "radius": l.radius,
        "power": l.power,
        "diffuse_radiance": l.diffuse_radiance,
        "raw_line": l.raw_line,
    }


def _dict_to_light(d: dict) -> SceneLight:
    return SceneLight(
        name=d.get("name", "DefaultLight"),
        light_type=LightType(d.get("light_type", "DEFAULT")),
        color=tuple(d.get("color", [1.0, 1.0, 1.0])),
        position=tuple(d.get("position", [1.0, 1.0, 1.0])),
        enabled=d.get("enabled", True),
        radius=d.get("radius", 1.0),
        power=d.get("power", 0.0),
        diffuse_radiance=d.get("diffuse_radiance", 0.0),
        raw_line=d.get("raw_line", ""),
    )
