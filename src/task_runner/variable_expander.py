"""
变量模板展开引擎。

支持在任务字符串字段（输出文件名等）中使用 {VAR_NAME} 语法引用变量，
在任务执行前由 resolve_all() 展开为实际值。

语法：
  - {VAR_NAME}     → 替换为变量值
  - {env.XXX}      → 替换为环境变量 XXX
  - {{              → 字面量 {
  - }}              → 字面量 }
"""

import os
import re
from typing import Dict, List, Optional, Tuple

from models.task_model import (
    Task, TaskType, ComputeMode, HtppMode, StardisParams, HtppParams,
)


class VariableError(Exception):
    """变量展开失败（未知变量名等）。"""
    pass


# ─── 变量注册表构建 ─────────────────────────────────────────────

def build_variable_registry(
    task: Task,
    task_index: int,
    resolved_camera: Optional[dict] = None,
    resolved_probes: Optional[list] = None,
    merged_env: Optional[Dict[str, str]] = None,
) -> Dict[str, str]:
    """
    从任务上下文收集所有可用变量，返回 {name: value} 字典。

    Parameters
    ----------
    task : Task
        当前任务对象。
    task_index : int
        任务在队列中的 1-based 索引。
    resolved_camera : dict, optional
        已解析的相机快照（IR_RENDER 模式下由 _resolve_camera 返回）。
    resolved_probes : list, optional
        已解析的探针快照列表。
    merged_env : dict, optional
        合并后的环境变量（队列级 + 任务级）。
    """
    registry: Dict[str, str] = {}

    # ── 任务元数据 ──
    registry["TASK_NAME"] = task.name
    registry["TASK_INDEX"] = str(task_index)
    if task.exe_ref:
        ref = task.exe_ref
        if '/' in ref or '\\' in ref:
            # 绝对路径 → 取 basename 无扩展名，避免路径字符污染文件名
            registry["EXE_TAG"] = os.path.splitext(os.path.basename(ref))[0]
        else:
            # 标签名 → 原样
            registry["EXE_TAG"] = ref

    # ── Stardis 参数 ──
    if task.task_type == TaskType.STARDIS and task.stardis_params:
        sp = task.stardis_params
        registry["THREADS"] = str(sp.threads)
        registry["VERBOSITY"] = str(sp.verbosity)
        registry["ALGO"] = sp.advanced.diff_algorithm or "dsphere"
        registry["PICARD"] = str(sp.advanced.picard_order)

        if sp.model_file:
            base = os.path.splitext(os.path.basename(sp.model_file))[0]
            registry["MODEL"] = base

        if sp.camera_ref:
            registry["CAMERA"] = sp.camera_ref

        # 相机参数（仅当已解析时可用）
        if resolved_camera:
            res = resolved_camera.get("resolution", (0, 0))
            registry["WIDTH"] = str(res[0])
            registry["HEIGHT"] = str(res[1])
            registry["FOV"] = str(resolved_camera.get("fov", 0))
            # IR_RENDER: SPP 来自相机 spp（-R 模式不使用 -n）
            registry["SPP"] = str(resolved_camera.get("spp", 0))
        else:
            # PROBE_SOLVE / FIELD_SOLVE: SPP 来自 -n 参数
            registry["SPP"] = str(sp.samples)

    # ── HTPP 参数 ──
    if task.task_type == TaskType.HTPP and task.htpp_params:
        hp = task.htpp_params
        registry["PALETTE"] = hp.palette or "inferno"
        registry["PIXCPNT"] = str(hp.pixel_component)
        registry["EXPOSURE"] = str(hp.exposure)
        registry["THREADS"] = str(hp.threads)

        # 输入文件 basename（从 input_source 无法直接获取，
        # 但 resolve_all 会在展开前设置 input_file）
        # INPUT 变量由调用者在知道 input_file 后注入

    # ── 环境变量 ──
    if merged_env:
        for key, value in merged_env.items():
            registry[f"env.{key}"] = value

    return registry


def inject_input_variable(registry: Dict[str, str], input_file: Optional[str]):
    """将输入文件 basename（无扩展名）注入变量注册表。"""
    if input_file:
        base = os.path.splitext(os.path.basename(input_file))[0]
        registry["INPUT"] = base


# ─── 变量展开 ───────────────────────────────────────────────────

# 匹配 {VAR_NAME} 或 {env.XXX}，但不匹配 {{ 或 }}
_VAR_PATTERN = re.compile(r'\{(\w+(?:\.\w+)?)\}')


def expand_variables(template: str, registry: Dict[str, str]) -> str:
    """
    将模板字符串中的 {VAR} 引用替换为注册表中的值。

    - {{  → 字面量 {
    - }}  → 字面量 }
    - {VAR} → registry[VAR]（未找到则抛 VariableError）
    """
    if not template:
        return template

    # 先处理转义：{{ → 临时占位符，}} → 临时占位符
    LBRACE = "\x00LBRACE\x00"
    RBRACE = "\x00RBRACE\x00"
    text = template.replace("{{", LBRACE).replace("}}", RBRACE)

    def _replace(match):
        var_name = match.group(1)
        if var_name not in registry:
            raise VariableError(
                f"未知变量 '{{{var_name}}}'，"
                f"可用变量: {', '.join(sorted(registry.keys()))}"
            )
        return registry[var_name]

    result = _VAR_PATTERN.sub(_replace, text)

    # 还原转义占位符
    result = result.replace(LBRACE, "{").replace(RBRACE, "}")
    return result


# ─── 可用变量列表（UI 自动补全用）──────────────────────────────

# (变量名, 描述, 适用条件函数)
_VARIABLE_DEFINITIONS: List[Tuple[str, str]] = [
    # 任务元数据（始终可用）
    ("TASK_NAME",  "任务名称"),
    ("TASK_INDEX", "任务在队列中的序号 (1-based)"),
    ("EXE_TAG",    "可执行文件标签名（路径时取文件名）"),

    # Stardis 参数
    ("SPP",       "采样数 (-n)"),
    ("THREADS",   "线程数 (-t)"),
    ("VERBOSITY", "详细度 (-V)"),
    ("MODEL",     "模型文件名 (无扩展名)"),
    ("ALGO",      "传导步算法 (-a)"),
    ("PICARD",    "Picard 阶数 (-o)"),

    # 相机参数（IR_RENDER）
    ("CAMERA",    "相机名称"),
    ("WIDTH",     "图像宽度 (像素)"),
    ("HEIGHT",    "图像高度 (像素)"),
    ("FOV",       "视场角 (度)"),

    # HTPP 参数
    ("PALETTE",   "调色板名称"),
    ("PIXCPNT",   "像素分量 (0-7)"),
    ("EXPOSURE",  "曝光度"),
    ("INPUT",     "输入文件名 (无扩展名)"),
]


def list_available_variables(
    task_type: TaskType,
    compute_mode: Optional[ComputeMode] = None,
    htpp_mode: Optional[HtppMode] = None,
) -> List[Tuple[str, str]]:
    """
    返回给定任务上下文中可用的变量列表 [(name, description), ...]。
    用于 UI 自动补全，不需要实际值。
    """
    result: List[Tuple[str, str]] = []

    # 元数据始终可用
    result.append(("TASK_NAME", "任务名称"))
    result.append(("TASK_INDEX", "任务在队列中的序号 (1-based)"))
    result.append(("EXE_TAG", "可执行文件标签名（路径时取文件名）"))

    if task_type == TaskType.STARDIS:
        result.append(("SPP", "采样数 (-n)"))
        result.append(("THREADS", "线程数 (-t)"))
        result.append(("VERBOSITY", "详细度 (-V)"))
        result.append(("MODEL", "模型文件名 (无扩展名)"))
        result.append(("ALGO", "传导步算法 (-a)"))
        result.append(("PICARD", "Picard 阶数 (-o)"))

        if compute_mode == ComputeMode.IR_RENDER:
            result.append(("CAMERA", "相机名称"))
            result.append(("WIDTH", "图像宽度 (像素)"))
            result.append(("HEIGHT", "图像高度 (像素)"))
            result.append(("FOV", "视场角 (度)"))

    elif task_type == TaskType.HTPP:
        result.append(("THREADS", "线程数 (-t)"))
        result.append(("PALETTE", "调色板名称"))
        result.append(("PIXCPNT", "像素分量 (0-7)"))
        result.append(("EXPOSURE", "曝光度"))
        result.append(("INPUT", "输入文件名 (无扩展名)"))

    # 环境变量提示（通用）
    result.append(("env.XXX", "自定义环境变量 (env.变量名)"))

    return result
