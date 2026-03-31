"""
TaskRunner — 任务队列调度器。

管理队列执行：引用求值、进程启动、错误处理。
"""

import os
import subprocess
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from PyQt5.QtCore import QObject, QProcess, QProcessEnvironment, pyqtSignal

from models.task_model import (
    Task, TaskQueue, TaskType, ComputeMode, HtppMode,
    ErrorPolicy, ErrorAction,
    InputFromTask, InputFromFile,
    StardisParams,
)
from models.scene_model import SceneModel
from models.editor_preferences import EditorPreferences
from task_runner.command_builder import CommandBuilder
from task_runner.variable_expander import (
    build_variable_registry, inject_input_variable,
    expand_variables, VariableError,
)


class ValidationError(Exception):
    """任务校验失败。"""
    pass


@dataclass
class ResolvedTask:
    """引用已解析、参数已锁定的任务快照。"""
    task: Task
    exe_path: str
    working_dir: str
    env_vars: Dict[str, str]
    args: List[str]
    output_file: Optional[str] = None      # stdout 重定向文件绝对路径
    stderr_file: Optional[str] = None      # stderr 重定向文件绝对路径
    input_file: Optional[str] = None


# ─── 引用解析 ───────────────────────────────────────────────────

def resolve_exe_ref(exe_ref: str, prefs: EditorPreferences) -> str:
    """将 exe_ref（标签名或绝对路径）解析为已验证的绝对路径。"""
    if not exe_ref:
        raise ValidationError("可执行文件未指定")
    if '/' in exe_ref or '\\' in exe_ref:
        path = exe_ref
    else:
        path = prefs.exe_tags.get(exe_ref)
        if not path:
            raise ValidationError(f"找不到可执行文件标签 '{exe_ref}'，"
                                  "请在编辑器首选项中配置")
    if not os.path.isfile(path):
        raise ValidationError(f"可执行文件不存在: {path}")
    return path


def _resolve_camera(camera_ref: str, model: SceneModel) -> dict:
    cam = model.get_camera_by_name(camera_ref)
    if cam is None:
        raise ValidationError(f"相机 '{camera_ref}' 不存在")
    return {
        "position": cam.position,
        "target": cam.target,
        "up": cam.up,
        "fov": cam.fov,
        "spp": cam.spp,
        "resolution": cam.resolution,
    }


def _resolve_probes(probe_refs: List[str], model: SceneModel) -> List[dict]:
    result = []
    for name in probe_refs:
        p = model.get_probe_by_name(name)
        if p is None:
            raise ValidationError(f"探针 '{name}' 不存在")
        result.append({
            "name": p.name,
            "probe_type": p.probe_type.value,
            "position": p.position,
            "time": p.time,
            "side": p.side,
        })
    return result


def resolve_all(queue: TaskQueue, model: SceneModel,
                prefs: EditorPreferences,
                scene_dir: str = "") -> List[ResolvedTask]:
    """
    遍历队列中所有 enabled=True 的任务，解引用并构建命令行。
    返回可直接执行的 ResolvedTask 列表。
    """
    resolved = []
    output_map: Dict[str, str] = {}  # task_id → output_file_path
    queue_env = dict(queue.env_vars)

    for task in queue.tasks:
        if not task.enabled:
            continue

        # 0. 解析 exe_ref
        exe_path = resolve_exe_ref(task.exe_ref, prefs)

        # 1. 确定 working_dir
        working_dir = task.working_dir or scene_dir
        if not working_dir:
            raise ValidationError(f"任务 '{task.name}' 的工作目录未指定")

        # 2. 合并环境变量
        merged_env = {**queue_env, **task.env_vars}

        # 3. 解引用并构建命令行
        output_file = None
        stderr_file = None
        input_file = None
        args = []
        task_index = queue.tasks.index(task) + 1  # 1-based
        camera_snapshot = None
        probe_snapshots = None

        if task.task_type == TaskType.STARDIS:
            if not task.stardis_params:
                raise ValidationError(f"任务 '{task.name}' 缺少 stardis 参数")
            sp = task.stardis_params
            model_file = sp.model_file
            if not model_file:
                raise ValidationError(f"任务 '{task.name}' 未指定模型文件 (-M)")

            if task.compute_mode == ComputeMode.IR_RENDER:
                if not sp.camera_ref:
                    raise ValidationError(f"任务 '{task.name}' 未指定相机引用")
                camera_snapshot = _resolve_camera(sp.camera_ref, model)
                # 输出文件名
                if not task.output_redirect:
                    task.output_redirect = CommandBuilder.build_ir_output_filename(camera_snapshot)
            elif task.compute_mode == ComputeMode.PROBE_SOLVE:
                if not sp.probe_refs:
                    raise ValidationError(f"任务 '{task.name}' 未指定探针引用")
                probe_snapshots = _resolve_probes(sp.probe_refs, model)
            elif task.compute_mode == ComputeMode.FIELD_SOLVE:
                if not sp.field_solve:
                    raise ValidationError(f"任务 '{task.name}' 缺少场求解配置")

            args = CommandBuilder.build_stardis(
                model_file, task.compute_mode, sp,
                camera_snapshot=camera_snapshot,
                probe_snapshots=probe_snapshots,
            )

        elif task.task_type == TaskType.HTPP:
            if not task.htpp_params:
                raise ValidationError(f"任务 '{task.name}' 缺少 htpp 参数")
            if not task.htpp_mode:
                raise ValidationError(f"任务 '{task.name}' 未指定 htpp 模式")
            if not task.input_source:
                raise ValidationError(f"任务 '{task.name}' 未指定输入来源")

            # 解析输入文件
            src = task.input_source
            if isinstance(src, InputFromTask):
                if src.task_id not in output_map:
                    raise ValidationError(
                        f"HTPP 任务 '{task.name}' 引用的 Stardis 任务未找到或未产出 .ht 文件")
                input_file = output_map[src.task_id]
            elif isinstance(src, InputFromFile):
                input_file = os.path.join(working_dir, src.file_path)

            # 确定输出文件名，并确保传给 -o 的是绝对路径
            if not task.htpp_params.output_file and input_file:
                base = os.path.splitext(os.path.basename(input_file))[0]
                task.htpp_params.output_file = f"{base}.ppm"

        # 4. 变量模板展开
        var_registry = build_variable_registry(
            task, task_index,
            resolved_camera=camera_snapshot,
            resolved_probes=probe_snapshots,
            merged_env=merged_env,
        )
        inject_input_variable(var_registry, input_file)

        try:
            if task.output_redirect:
                expanded = expand_variables(task.output_redirect, var_registry)
                output_file = os.path.join(working_dir, expanded)
            if task.stderr_redirect:
                expanded = expand_variables(task.stderr_redirect, var_registry)
                stderr_file = os.path.join(working_dir, expanded)
            if (task.task_type == TaskType.HTPP and task.htpp_params
                    and task.htpp_params.output_file):
                expanded = expand_variables(task.htpp_params.output_file, var_registry)
                task.htpp_params.output_file = os.path.abspath(
                    os.path.join(working_dir, expanded)
                )
        except VariableError as e:
            raise ValidationError(
                f"任务 '{task.name}' 变量展开失败: {e}"
            ) from e

        # 5. HTPP 命令行构建（在变量展开之后，使用已展开的绝对路径）
        if task.task_type == TaskType.HTPP:
            args = CommandBuilder.build_htpp(
                task.htpp_mode, task.htpp_params, input_file,
            )

        rt = ResolvedTask(
            task=task, exe_path=exe_path,
            working_dir=working_dir,
            env_vars=merged_env,
            args=args,
            output_file=output_file,
            stderr_file=stderr_file,
            input_file=input_file,
        )

        if task.compute_mode == ComputeMode.IR_RENDER and output_file:
            output_map[task.id] = output_file

        resolved.append(rt)

    return resolved


# ─── TaskRunner 调度器 ──────────────────────────────────────────

class TaskRunner(QObject):
    """任务队列调度器，管理顺序执行和错误处理。"""

    queue_started     = pyqtSignal()
    queue_finished    = pyqtSignal(bool)                # all_success
    task_started      = pyqtSignal(str)                 # task_id
    task_finished     = pyqtSignal(str, int)            # task_id, exit_code
    task_output       = pyqtSignal(str, str)            # task_id, text (stdout)
    task_error_output = pyqtSignal(str, str)            # task_id, text (stderr)
    task_skipped      = pyqtSignal(str, str)            # task_id, reason
    queue_paused      = pyqtSignal(str)                 # task_id

    def __init__(self, parent=None):
        super().__init__(parent)
        self._process = QProcess(self)
        self._resolved: List[ResolvedTask] = []
        self._current_index: int = -1
        self._retry_remaining: int = 0
        self._error_policy: ErrorPolicy = ErrorPolicy()
        self._running: bool = False
        self._paused: bool = False
        self._all_success: bool = True
        self._stdout_file = None   # 当前 stdout 重定向文件句柄
        self._stderr_file = None   # 当前 stderr 重定向文件句柄

        self._process.readyReadStandardOutput.connect(self._on_stdout)
        self._process.readyReadStandardError.connect(self._on_stderr)
        self._process.finished.connect(self._on_process_finished)

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def is_paused(self) -> bool:
        return self._paused

    @property
    def current_task_id(self) -> Optional[str]:
        if 0 <= self._current_index < len(self._resolved):
            return self._resolved[self._current_index].task.id
        return None

    # ─── 队列执行 ────────────────────────────────────────────────

    def run_queue(self, resolved: List[ResolvedTask], policy: ErrorPolicy):
        """启动队列执行。"""
        self._resolved = resolved
        self._error_policy = policy
        self._current_index = -1
        self._running = True
        self._paused = False
        self._all_success = True
        self.queue_started.emit()
        self._run_next()

    def run_single(self, resolved_task: ResolvedTask):
        """单任务执行（不走队列策略）。"""
        self._resolved = [resolved_task]
        self._error_policy = ErrorPolicy(retry_count=0, after_retries_exhausted=ErrorAction.CANCEL)
        self._current_index = -1
        self._running = True
        self._paused = False
        self._all_success = True
        self.queue_started.emit()
        self._run_next()

    def cancel(self):
        """取消当前执行。"""
        if self._running:
            if self._process.state() != QProcess.NotRunning:
                self._process.kill()
            self._close_redirect_files()
            self._running = False
            self._all_success = False
            self.queue_finished.emit(False)

    def resume_skip(self):
        """暂停后选择跳过继续。"""
        if self._paused:
            self._paused = False
            rt = self._resolved[self._current_index]
            self._skip_current_and_dependents(rt)
            self._run_next()

    def resume_retry(self):
        """暂停后选择重试。"""
        if self._paused:
            self._paused = False
            rt = self._resolved[self._current_index]
            self._start_task(rt)

    def resume_cancel(self):
        """暂停后选择取消。"""
        if self._paused:
            self._paused = False
            self._cancel_remaining("用户取消")

    # ─── 内部 ────────────────────────────────────────────────────

    def _run_next(self):
        self._current_index += 1
        # 跳过已标记为 None 的任务（被依赖跳过的）
        while (self._current_index < len(self._resolved)
               and self._resolved[self._current_index] is None):
            self._current_index += 1
        if self._current_index >= len(self._resolved):
            self._running = False
            self.queue_finished.emit(self._all_success)
            return
        rt = self._resolved[self._current_index]
        self._retry_remaining = self._error_policy.retry_count
        self._start_task(rt)

    def _start_task(self, rt: ResolvedTask):
        self.task_started.emit(rt.task.id)

        # 打印任务名称 + 完整命令行
        full_cmd = subprocess.list2cmdline([rt.exe_path] + rt.args)
        self.task_output.emit(rt.task.id,
                              f"[任务] {rt.task.name}\n[命令] {full_cmd}\n")

        if rt.env_vars:
            env = QProcessEnvironment.systemEnvironment()
            for k, v in rt.env_vars.items():
                env.insert(k, v)
            self._process.setProcessEnvironment(env)

        self._process.setWorkingDirectory(rt.working_dir)

        # 不使用 setStandardOutputFile，改为手动写入文件，
        # 这样 readyReadStandardOutput 仍然能触发，同时实现重定向和 UI 显示。
        self._close_redirect_files()
        if rt.output_file:
            self._stdout_file = open(rt.output_file, 'w', encoding='utf-8')
        if rt.stderr_file:
            self._stderr_file = open(rt.stderr_file, 'w', encoding='utf-8')

        self._process.start(rt.exe_path, rt.args)

    def _on_stdout(self):
        rt = self._resolved[self._current_index]
        data = self._process.readAllStandardOutput().data().decode('utf-8', errors='replace')
        if self._stdout_file:
            # 文本重定向：写入文件，不发 UI（避免日志面板刺屏 stardis 大量输出）
            self._stdout_file.write(data)
            self._stdout_file.flush()
        else:
            # 无重定向时才发送到 UI
            self.task_output.emit(rt.task.id, data)

    def _on_stderr(self):
        rt = self._resolved[self._current_index]
        data = self._process.readAllStandardError().data().decode('utf-8', errors='replace')
        if self._stderr_file:
            self._stderr_file.write(data)
            self._stderr_file.flush()
        self.task_error_output.emit(rt.task.id, data)

    def _on_process_finished(self, exit_code, _exit_status):
        self._close_redirect_files()
        if not self._running:
            return
        rt = self._resolved[self._current_index]
        self.task_finished.emit(rt.task.id, exit_code)

        if exit_code == 0:
            self._run_next()
        else:
            self._all_success = False
            self._handle_failure(rt, exit_code)

    def _close_redirect_files(self):
        """关闭当前打开的重定向文件句柄。"""
        if self._stdout_file:
            self._stdout_file.close()
            self._stdout_file = None
        if self._stderr_file:
            self._stderr_file.close()
            self._stderr_file = None

    def _handle_failure(self, rt: ResolvedTask, exit_code: int):
        if self._retry_remaining > 0:
            self._retry_remaining -= 1
            self._start_task(rt)
            return

        action = self._error_policy.after_retries_exhausted
        if action == ErrorAction.CANCEL:
            self._cancel_remaining(f"任务 '{rt.task.name}' 失败 (exit={exit_code})")
        elif action == ErrorAction.SKIP:
            self._skip_current_and_dependents(rt)
            self._run_next()
        elif action == ErrorAction.PAUSE:
            self._paused = True
            self.queue_paused.emit(rt.task.id)

    def _cancel_remaining(self, reason: str):
        for i in range(self._current_index + 1, len(self._resolved)):
            self.task_skipped.emit(self._resolved[i].task.id, reason)
        self._running = False
        self.queue_finished.emit(False)

    def _skip_current_and_dependents(self, rt: ResolvedTask):
        self.task_skipped.emit(rt.task.id, "跳过")
        # 跳过依赖此任务的 HTPP 任务
        for i in range(self._current_index + 1, len(self._resolved)):
            next_rt = self._resolved[i]
            src = next_rt.task.input_source
            if isinstance(src, InputFromTask) and src.task_id == rt.task.id:
                self.task_skipped.emit(next_rt.task.id, f"依赖的任务 '{rt.task.name}' 已跳过")
                # 标记为已处理（在 resolved 列表中移除以避免执行）
                self._resolved[i] = None  # type: ignore


# ─── SceneValidator ─────────────────────────────────────────────

class SceneValidator(QObject):
    """用 stardis -M <scene> -d <dump> 执行场景定义验证。

    调用 validate() 后异步执行，完成时发射 validation_finished 信号。
    """

    validation_finished = pyqtSignal(str, int)  # (output_text, exit_code)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._process = QProcess(self)
        self._process.readyReadStandardOutput.connect(self._on_stdout)
        self._process.readyReadStandardError.connect(self._on_stderr)
        self._process.finished.connect(self._on_finished)
        self._dump_file: str = ""
        self._out_buf: str = ""

    @property
    def is_running(self) -> bool:
        return self._process.state() != QProcess.NotRunning

    def validate(self, stardis_exe: str, scene_file: str, working_dir: str):
        """启动 stardis -M scene_file -d dump_file 进行验证。

        scene_file 可以是相对于 working_dir 的文件名，也可以是绝对路径。
        """
        if self.is_running:
            return
        self._dump_file = os.path.join(working_dir, ".scene_validation.txt")
        self._out_buf = ""
        self._process.setWorkingDirectory(working_dir)
        self._process.start(stardis_exe, ['-M', scene_file, '-d', self._dump_file])

    def _on_stdout(self):
        data = self._process.readAllStandardOutput().data().decode('utf-8', errors='replace')
        self._out_buf += data

    def _on_stderr(self):
        data = self._process.readAllStandardError().data().decode('utf-8', errors='replace')
        self._out_buf += data

    def _on_finished(self, exit_code, _exit_status):
        # 优先使用 dump 文件内容；若无则回退到 stdout/stderr
        text = ""
        if os.path.isfile(self._dump_file):
            try:
                with open(self._dump_file, 'r', encoding='utf-8', errors='replace') as f:
                    text = f.read()
            except OSError:
                pass
        if self._out_buf.strip():
            if text:
                text += "\n\n--- 控制台输出 ---\n" + self._out_buf
            else:
                text = self._out_buf
        if not text.strip():
            text = "(stardis 无输出)"
        self.validation_finished.emit(text, exit_code)
