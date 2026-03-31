"""
变量模板展开引擎的单元测试。

覆盖：
- expand_variables: 基本替换、环境变量、无变量、未知变量、转义大括号
- build_variable_registry: IR_RENDER / PROBE_SOLVE / HTPP 任务的变量注册
- inject_input_variable: INPUT 变量注入
- list_available_variables: 按上下文过滤变量列表
- 集成: resolve_all 中的变量展开
"""

import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from task_runner.variable_expander import (
    VariableError,
    expand_variables,
    build_variable_registry,
    inject_input_variable,
    list_available_variables,
)
from models.task_model import (
    Task, TaskQueue, TaskType, ComputeMode, HtppMode,
    StardisParams, HtppParams, InputFromFile,
)


# ═══════════════════════════════════════════════════════════════
# expand_variables
# ═══════════════════════════════════════════════════════════════

class TestExpandVariables:
    def test_expand_simple(self):
        registry = {"WIDTH": "640", "HEIGHT": "480"}
        result = expand_variables("IRR_{WIDTH}x{HEIGHT}.ht", registry)
        assert result == "IRR_640x480.ht"

    def test_expand_multiple_vars(self):
        registry = {"WIDTH": "640", "HEIGHT": "480", "SPP": "1000000"}
        result = expand_variables("IRR_{WIDTH}x{HEIGHT}x{SPP}.ht", registry)
        assert result == "IRR_640x480x1000000.ht"

    def test_expand_env_var(self):
        registry = {"env.MY_VAR": "value"}
        result = expand_variables("{env.MY_VAR}_output.ht", registry)
        assert result == "value_output.ht"

    def test_expand_no_vars(self):
        registry = {"WIDTH": "640"}
        result = expand_variables("plain_file.ht", registry)
        assert result == "plain_file.ht"

    def test_expand_empty_template(self):
        result = expand_variables("", {"WIDTH": "640"})
        assert result == ""

    def test_expand_none_template(self):
        result = expand_variables(None, {"WIDTH": "640"})
        assert result is None

    def test_expand_unknown_var_raises(self):
        registry = {"WIDTH": "640"}
        with pytest.raises(VariableError, match="NONEXIST"):
            expand_variables("{NONEXIST}", registry)

    def test_expand_escaped_braces(self):
        registry = {"WIDTH": "640"}
        result = expand_variables("{{literal}}", registry)
        assert result == "{literal}"

    def test_expand_mixed_escaped_and_var(self):
        registry = {"WIDTH": "640"}
        result = expand_variables("{{not_a_var}}_{WIDTH}.ht", registry)
        assert result == "{not_a_var}_640.ht"

    def test_expand_single_var(self):
        registry = {"TASK_NAME": "MyTask"}
        result = expand_variables("{TASK_NAME}.log", registry)
        assert result == "MyTask.log"

    def test_expand_adjacent_vars(self):
        registry = {"A": "x", "B": "y"}
        result = expand_variables("{A}{B}", registry)
        assert result == "xy"


# ═══════════════════════════════════════════════════════════════
# build_variable_registry
# ═══════════════════════════════════════════════════════════════

class TestBuildVariableRegistry:
    def test_registry_ir_render(self):
        task = Task(
            name="IR Render",
            task_type=TaskType.STARDIS,
            compute_mode=ComputeMode.IR_RENDER,
            stardis_params=StardisParams(
                model_file="scene.txt",
                samples=1000000,
                threads=8,
                verbosity=2,
                camera_ref="Cam1",
            ),
        )
        camera = {
            "resolution": (640, 480),
            "fov": 45.0,
            "spp": 64,
        }
        registry = build_variable_registry(
            task, task_index=1,
            resolved_camera=camera,
        )

        assert registry["SPP"] == "64"  # IR_RENDER: SPP 来自相机 spp，非 -n
        assert registry["THREADS"] == "8"
        assert registry["VERBOSITY"] == "2"
        assert registry["MODEL"] == "scene"
        assert registry["CAMERA"] == "Cam1"
        assert registry["WIDTH"] == "640"
        assert registry["HEIGHT"] == "480"
        assert registry["FOV"] == "45.0"
        assert registry["TASK_NAME"] == "IR Render"
        assert registry["TASK_INDEX"] == "1"
        assert registry["ALGO"] == "dsphere"
        assert registry["PICARD"] == "1"

    def test_registry_probe_solve(self):
        task = Task(
            name="Probe Solve",
            task_type=TaskType.STARDIS,
            compute_mode=ComputeMode.PROBE_SOLVE,
            stardis_params=StardisParams(
                model_file="model.txt",
                samples=500000,
                threads=4,
                probe_refs=["Probe1"],
            ),
        )
        registry = build_variable_registry(task, task_index=2)

        assert registry["SPP"] == "500000"
        assert registry["THREADS"] == "4"
        assert registry["MODEL"] == "model"
        assert "WIDTH" not in registry  # No camera → no WIDTH
        assert "HEIGHT" not in registry

    def test_registry_htpp(self):
        task = Task(
            name="HTPP Image",
            task_type=TaskType.HTPP,
            htpp_mode=HtppMode.IMAGE,
            htpp_params=HtppParams(
                threads=4,
                exposure=2.0,
                palette="viridis",
                pixel_component=3,
            ),
        )
        registry = build_variable_registry(task, task_index=3)

        assert registry["PALETTE"] == "viridis"
        assert registry["PIXCPNT"] == "3"
        assert registry["EXPOSURE"] == "2.0"
        assert registry["THREADS"] == "4"
        assert "SPP" not in registry  # Not a Stardis task

    def test_registry_env_vars(self):
        task = Task(name="Test", task_type=TaskType.STARDIS,
                    stardis_params=StardisParams())
        registry = build_variable_registry(
            task, task_index=1,
            merged_env={"OMP_THREADS": "8", "MY_VAR": "hello"},
        )
        assert registry["env.OMP_THREADS"] == "8"
        assert registry["env.MY_VAR"] == "hello"

    def test_registry_task_metadata(self):
        task = Task(name="任务1", task_type=TaskType.STARDIS,
                    stardis_params=StardisParams())
        registry = build_variable_registry(task, task_index=5)
        assert registry["TASK_NAME"] == "任务1"
        assert registry["TASK_INDEX"] == "5"


# ═══════════════════════════════════════════════════════════════
# inject_input_variable
# ═══════════════════════════════════════════════════════════════

class TestInjectInputVariable:
    def test_inject_with_path(self):
        registry = {}
        inject_input_variable(registry, "/work/IRR_640x480x1000000.ht")
        assert registry["INPUT"] == "IRR_640x480x1000000"

    def test_inject_with_none(self):
        registry = {}
        inject_input_variable(registry, None)
        assert "INPUT" not in registry

    def test_inject_basename_only(self):
        registry = {}
        inject_input_variable(registry, "output.ht")
        assert registry["INPUT"] == "output"


# ═══════════════════════════════════════════════════════════════
# list_available_variables
# ═══════════════════════════════════════════════════════════════

class TestListAvailableVariables:
    def test_stardis_ir_render(self):
        vars_ = list_available_variables(TaskType.STARDIS, ComputeMode.IR_RENDER)
        names = [v[0] for v in vars_]
        assert "SPP" in names
        assert "WIDTH" in names
        assert "HEIGHT" in names
        assert "CAMERA" in names
        assert "TASK_NAME" in names

    def test_stardis_probe_solve(self):
        vars_ = list_available_variables(TaskType.STARDIS, ComputeMode.PROBE_SOLVE)
        names = [v[0] for v in vars_]
        assert "SPP" in names
        assert "THREADS" in names
        assert "WIDTH" not in names  # No camera variables in probe mode
        assert "CAMERA" not in names

    def test_htpp(self):
        vars_ = list_available_variables(TaskType.HTPP, htpp_mode=HtppMode.IMAGE)
        names = [v[0] for v in vars_]
        assert "PALETTE" in names
        assert "EXPOSURE" in names
        assert "INPUT" in names
        assert "SPP" not in names  # Not a Stardis var

    def test_env_hint_always_present(self):
        for tt in (TaskType.STARDIS, TaskType.HTPP):
            vars_ = list_available_variables(tt)
            names = [v[0] for v in vars_]
            assert "env.XXX" in names


# ═══════════════════════════════════════════════════════════════
# 集成测试：变量展开 + 注册表
# ═══════════════════════════════════════════════════════════════

class TestIntegration:
    def test_ir_render_output_filename(self):
        """端到端：IR_RENDER 任务的模板输出文件名展开。"""
        task = Task(
            name="IR Render",
            task_type=TaskType.STARDIS,
            compute_mode=ComputeMode.IR_RENDER,
            stardis_params=StardisParams(
                model_file="scene.txt",
                samples=1000000,
                camera_ref="Cam1",
            ),
            output_redirect="IRR_{WIDTH}x{HEIGHT}x{SPP}.ht",
        )
        camera = {"resolution": (640, 480), "fov": 45.0, "spp": 1000000}
        registry = build_variable_registry(
            task, task_index=1, resolved_camera=camera,
        )
        result = expand_variables(task.output_redirect, registry)
        assert result == "IRR_640x480x1000000.ht"

    def test_htpp_output_with_input_var(self):
        """HTPP 任务使用 {INPUT} 变量。"""
        task = Task(
            name="HTPP Map",
            task_type=TaskType.HTPP,
            htpp_mode=HtppMode.MAP,
            htpp_params=HtppParams(
                output_file="{INPUT}_{PALETTE}.ppm",
                palette="viridis",
            ),
        )
        registry = build_variable_registry(task, task_index=1)
        inject_input_variable(registry, "/work/IRR_640x480.ht")
        result = expand_variables(task.htpp_params.output_file, registry)
        assert result == "IRR_640x480_viridis.ppm"

    def test_stderr_with_task_name(self):
        """stderr 使用 {TASK_NAME} 和 {ALGO}。"""
        task = Task(
            name="MyTask",
            task_type=TaskType.STARDIS,
            compute_mode=ComputeMode.PROBE_SOLVE,
            stardis_params=StardisParams(
                model_file="scene.txt",
                advanced=__import__('models.task_model', fromlist=['AdvancedOptions']).AdvancedOptions(
                    diff_algorithm="wos"),
            ),
            stderr_redirect="{TASK_NAME}_{ALGO}.log",
        )
        registry = build_variable_registry(task, task_index=1)
        result = expand_variables(task.stderr_redirect, registry)
        assert result == "MyTask_wos.log"

    def test_env_var_in_filename(self):
        """环境变量用于文件名。"""
        task = Task(
            name="Test",
            task_type=TaskType.STARDIS,
            stardis_params=StardisParams(),
        )
        registry = build_variable_registry(
            task, task_index=1,
            merged_env={"RUN_ID": "run42"},
        )
        result = expand_variables("{env.RUN_ID}_output.ht", registry)
        assert result == "run42_output.ht"
