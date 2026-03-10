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

from models.task_model import TaskQueue, task_queue_to_dict, dict_to_task_queue


# ─── 枚举 ───────────────────────────────────────────────────────

class BodyType(Enum):
    SOLID = "SOLID"
    FLUID = "FLUID"


class Side(Enum):
    FRONT = "FRONT"
    BACK = "BACK"
    BOTH = "BOTH"


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
    volume: VolumeProperties = field(default_factory=VolumeProperties)
    next_zone_id: int = 1                   # 区域 ID 分配计数器（单调递增，删除后不重用）
    surface_zones: List[SurfaceZone] = field(default_factory=list)

    def allocate_zone_id(self) -> int:
        """分配下一个 zone_id 并递增计数器。"""
        zid = self.next_zone_id
        self.next_zone_id += 1
        return zid


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
