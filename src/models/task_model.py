"""
Task Runner 数据模型。

定义任务（Task）、任务队列（TaskQueue）及其参数结构，
用于在 Scene Editor v2 中配置和管理 stardis/htpp 计算任务。
"""

import uuid
from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Union


# ─── 枚举 ───────────────────────────────────────────────────────

class TaskType(Enum):
    STARDIS = "stardis"
    HTPP = "htpp"


class ComputeMode(Enum):
    PROBE_SOLVE = "probe_solve"    # 探针求解 (-p/-P/-f)
    FIELD_SOLVE = "field_solve"    # 场求解 (-m/-s/-S/-F)
    IR_RENDER   = "ir_render"      # 红外渲染 (-R)


class FieldSolveType(Enum):
    MEDIUM_TEMP    = "medium_temp"       # -m name
    SURF_MEAN_TEMP = "surf_mean_temp"    # -s file
    SURF_TEMP_MAP  = "surf_temp_map"     # -S file
    SURF_FLUX      = "surf_flux"         # -F file


class HtppMode(Enum):
    IMAGE = "image"    # -i exposure:white=...
    MAP   = "map"      # -m pixcpnt=:palette=:range=:gnuplot


class ErrorAction(Enum):
    CANCEL = "cancel"    # 取消整个队列
    SKIP   = "skip"      # 跳过当前任务继续
    PAUSE  = "pause"     # 暂停队列，等待用户决定


# ─── HTPP 输入来源 ──────────────────────────────────────────────

@dataclass
class InputFromTask:
    """引用队列中某个 IR_RENDER 任务的输出 .ht 文件"""
    task_id: str = ""


@dataclass
class InputFromFile:
    """直接指定已有 .ht 文件路径"""
    file_path: str = ""    # 相对于 working_dir 的相对路径


InputSource = Union[InputFromTask, InputFromFile]


# ─── 错误处理策略 ───────────────────────────────────────────────

@dataclass
class ErrorPolicy:
    retry_count: int = 0
    after_retries_exhausted: ErrorAction = ErrorAction.CANCEL


# ─── Stardis 参数 ───────────────────────────────────────────────

@dataclass
class AdvancedOptions:
    diff_algorithm: str = ""           # -a: 扩散算法
    picard_order: int = 1              # -o: Picard 阶数
    initial_time: float = 0.0          # -I: 初始时间
    disable_intrad: bool = False       # -i: 禁用内部辐射
    extended_results: bool = False     # -e: 扩展结果
    rng_state_in: str = ""             # -x: RNG 状态输入
    rng_state_out: str = ""            # -X: RNG 状态输出


@dataclass
class FieldSolveConfig:
    solve_type: FieldSolveType = FieldSolveType.MEDIUM_TEMP
    medium_name: str = ""              # -m: 介质名称
    solve_file: str = ""               # -s/-S/-F: 求解文件路径


@dataclass
class StardisParams:
    model_file: str = ""                       # -M（场景文件路径）
    samples: int = 1000000                     # -n
    threads: int = 4                           # -t
    verbosity: int = 1                         # -V

    probe_refs: List[str] = field(default_factory=list)       # PROBE_SOLVE: Probe 名称列表
    camera_ref: Optional[str] = None                          # IR_RENDER: IRCamera 名称
    field_solve: Optional[FieldSolveConfig] = None            # FIELD_SOLVE: 子类型配置

    advanced: AdvancedOptions = field(default_factory=AdvancedOptions)


# ─── HTPP 参数 ──────────────────────────────────────────────────

@dataclass
class HtppParams:
    threads: int = 4                   # -t
    force_overwrite: bool = False      # -f
    verbose: bool = False              # -v
    output_file: str = ""              # -o

    # IMAGE 模式 (-i)
    exposure: float = 1.0
    white_scale: Optional[float] = None  # None = 自动

    # MAP 模式 (-m)
    pixel_component: int = 0           # 0-7
    palette: str = ""                  # 调色板名称
    range_min: Optional[float] = None  # None = 自动
    range_max: Optional[float] = None
    gnuplot: bool = False


# ─── Task — 单个任务 ────────────────────────────────────────────

@dataclass
class Task:
    # 标识
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    task_type: TaskType = TaskType.STARDIS
    enabled: bool = True

    # 执行环境
    exe_ref: str = ""                          # 标签名或绝对路径
    working_dir: str = ""                      # 默认场景目录
    env_vars: Dict[str, str] = field(default_factory=dict)

    # Stardis 专有
    compute_mode: Optional[ComputeMode] = None
    stardis_params: Optional[StardisParams] = None

    # HTPP 专有
    htpp_mode: Optional[HtppMode] = None
    htpp_params: Optional[HtppParams] = None
    input_source: Optional[InputSource] = None

    # 输出重定向
    output_redirect: Optional[str] = None      # stdout 重定向文件名
    stderr_redirect: Optional[str] = None      # stderr 重定向文件名


# ─── TaskQueue — 任务队列 ───────────────────────────────────────

@dataclass
class TaskQueue:
    tasks: List[Task] = field(default_factory=list)
    error_policy: ErrorPolicy = field(default_factory=ErrorPolicy)
    env_vars: Dict[str, str] = field(default_factory=dict)


# ─── 序列化 → dict ──────────────────────────────────────────────

def _advanced_to_dict(adv: AdvancedOptions) -> dict:
    return {
        "diff_algorithm": adv.diff_algorithm,
        "picard_order": adv.picard_order,
        "initial_time": adv.initial_time,
        "disable_intrad": adv.disable_intrad,
        "extended_results": adv.extended_results,
        "rng_state_in": adv.rng_state_in,
        "rng_state_out": adv.rng_state_out,
    }


def _field_solve_to_dict(fs: FieldSolveConfig) -> dict:
    return {
        "solve_type": fs.solve_type.value,
        "medium_name": fs.medium_name,
        "solve_file": fs.solve_file,
    }


def _stardis_params_to_dict(sp: StardisParams) -> dict:
    return {
        "model_file": sp.model_file,
        "samples": sp.samples,
        "threads": sp.threads,
        "verbosity": sp.verbosity,
        "probe_refs": sp.probe_refs,
        "camera_ref": sp.camera_ref,
        "field_solve": _field_solve_to_dict(sp.field_solve) if sp.field_solve else None,
        "advanced": _advanced_to_dict(sp.advanced),
    }


def _htpp_params_to_dict(hp: HtppParams) -> dict:
    return {
        "threads": hp.threads,
        "force_overwrite": hp.force_overwrite,
        "verbose": hp.verbose,
        "output_file": hp.output_file,
        "exposure": hp.exposure,
        "white_scale": hp.white_scale,
        "pixel_component": hp.pixel_component,
        "palette": hp.palette,
        "range_min": hp.range_min,
        "range_max": hp.range_max,
        "gnuplot": hp.gnuplot,
    }


def _input_source_to_dict(src: InputSource) -> dict:
    if isinstance(src, InputFromTask):
        return {"type": "from_task", "task_id": src.task_id}
    elif isinstance(src, InputFromFile):
        return {"type": "from_file", "file_path": src.file_path}
    return {}


def task_to_dict(task: Task) -> dict:
    return {
        "id": task.id,
        "name": task.name,
        "task_type": task.task_type.value,
        "enabled": task.enabled,
        "exe_ref": task.exe_ref,
        "working_dir": task.working_dir,
        "env_vars": task.env_vars,
        "compute_mode": task.compute_mode.value if task.compute_mode else None,
        "stardis_params": _stardis_params_to_dict(task.stardis_params) if task.stardis_params else None,
        "htpp_mode": task.htpp_mode.value if task.htpp_mode else None,
        "htpp_params": _htpp_params_to_dict(task.htpp_params) if task.htpp_params else None,
        "input_source": _input_source_to_dict(task.input_source) if task.input_source else None,
        "output_redirect": task.output_redirect,
        "stderr_redirect": task.stderr_redirect,
    }


def task_queue_to_dict(queue: TaskQueue) -> dict:
    return {
        "error_policy": {
            "retry_count": queue.error_policy.retry_count,
            "after_retries_exhausted": queue.error_policy.after_retries_exhausted.value,
        },
        "env_vars": queue.env_vars,
        "tasks": [task_to_dict(t) for t in queue.tasks],
    }


# ─── 反序列化 dict → dataclass ──────────────────────────────────

def _dict_to_advanced(d: dict) -> AdvancedOptions:
    return AdvancedOptions(
        diff_algorithm=d.get("diff_algorithm", ""),
        picard_order=d.get("picard_order", 1),
        initial_time=d.get("initial_time", 0.0),
        disable_intrad=d.get("disable_intrad", False),
        extended_results=d.get("extended_results", False),
        rng_state_in=d.get("rng_state_in", ""),
        rng_state_out=d.get("rng_state_out", ""),
    )


def _dict_to_field_solve(d: dict) -> FieldSolveConfig:
    return FieldSolveConfig(
        solve_type=FieldSolveType(d.get("solve_type", "medium_temp")),
        medium_name=d.get("medium_name", ""),
        solve_file=d.get("solve_file", ""),
    )


def _dict_to_stardis_params(d: dict) -> StardisParams:
    fs_data = d.get("field_solve")
    adv_data = d.get("advanced", {})
    return StardisParams(
        model_file=d.get("model_file", ""),
        samples=d.get("samples", 1000000),
        threads=d.get("threads", 4),
        verbosity=d.get("verbosity", 1),
        probe_refs=d.get("probe_refs", []),
        camera_ref=d.get("camera_ref"),
        field_solve=_dict_to_field_solve(fs_data) if fs_data else None,
        advanced=_dict_to_advanced(adv_data),
    )


def _dict_to_htpp_params(d: dict) -> HtppParams:
    return HtppParams(
        threads=d.get("threads", 4),
        force_overwrite=d.get("force_overwrite", False),
        verbose=d.get("verbose", False),
        output_file=d.get("output_file", ""),
        exposure=d.get("exposure", 1.0),
        white_scale=d.get("white_scale"),
        pixel_component=d.get("pixel_component", 0),
        palette=d.get("palette", ""),
        range_min=d.get("range_min"),
        range_max=d.get("range_max"),
        gnuplot=d.get("gnuplot", False),
    )


def _dict_to_input_source(d: dict) -> InputSource:
    if d["type"] == "from_task":
        return InputFromTask(task_id=d["task_id"])
    elif d["type"] == "from_file":
        return InputFromFile(file_path=d.get("file_path", ""))
    raise ValueError(f"Unknown input source type: {d['type']}")


def dict_to_task(d: dict) -> Task:
    sp_data = d.get("stardis_params")
    hp_data = d.get("htpp_params")
    is_data = d.get("input_source")
    cm_str = d.get("compute_mode")
    hm_str = d.get("htpp_mode")

    return Task(
        id=d.get("id", str(uuid.uuid4())),
        name=d.get("name", ""),
        task_type=TaskType(d.get("task_type", "stardis")),
        enabled=d.get("enabled", True),
        exe_ref=d.get("exe_ref", ""),
        working_dir=d.get("working_dir", ""),
        env_vars=d.get("env_vars", {}),
        compute_mode=ComputeMode(cm_str) if cm_str else None,
        stardis_params=_dict_to_stardis_params(sp_data) if sp_data else None,
        htpp_mode=HtppMode(hm_str) if hm_str else None,
        htpp_params=_dict_to_htpp_params(hp_data) if hp_data else None,
        input_source=_dict_to_input_source(is_data) if is_data else None,
        output_redirect=d.get("output_redirect"),
        stderr_redirect=d.get("stderr_redirect"),
    )


def dict_to_task_queue(d: dict) -> TaskQueue:
    ep_data = d.get("error_policy", {})
    action_str = ep_data.get("after_retries_exhausted", "cancel")
    return TaskQueue(
        tasks=[dict_to_task(td) for td in d.get("tasks", [])],
        error_policy=ErrorPolicy(
            retry_count=ep_data.get("retry_count", 0),
            after_retries_exhausted=ErrorAction(action_str),
        ),
        env_vars=d.get("env_vars", {}),
    )


# ─── 工厂方法 ───────────────────────────────────────────────────

def create_stardis_task(name: str, compute_mode: ComputeMode,
                        **kwargs) -> Task:
    """创建 Stardis 任务的便捷工厂。"""
    return Task(
        name=name,
        task_type=TaskType.STARDIS,
        compute_mode=compute_mode,
        stardis_params=StardisParams(**{k: v for k, v in kwargs.items()
                                        if k in StardisParams.__dataclass_fields__}),
        exe_ref=kwargs.get("exe_ref", ""),
        working_dir=kwargs.get("working_dir", ""),
    )


def create_htpp_task(name: str, htpp_mode: HtppMode,
                     input_source: Optional[InputSource] = None,
                     **kwargs) -> Task:
    """创建 HTPP 任务的便捷工厂。"""
    return Task(
        name=name,
        task_type=TaskType.HTPP,
        htpp_mode=htpp_mode,
        htpp_params=HtppParams(**{k: v for k, v in kwargs.items()
                                   if k in HtppParams.__dataclass_fields__}),
        input_source=input_source,
        exe_ref=kwargs.get("exe_ref", ""),
        working_dir=kwargs.get("working_dir", ""),
    )
