"""Task/TaskQueue 序列化往返 + 工厂方法测试。"""

import uuid
from models.task_model import (
    Task, TaskQueue, TaskType, ComputeMode, HtppMode,
    ErrorAction, ErrorPolicy,
    StardisParams, HtppParams, AdvancedOptions, FieldSolveConfig, FieldSolveType,
    InputFromTask, InputFromFile,
    task_to_dict, dict_to_task,
    task_queue_to_dict, dict_to_task_queue,
    create_stardis_task, create_htpp_task,
)


class TestTaskSerialization:
    """Task 单个任务的序列化往返。"""

    def test_stardis_ir_roundtrip(self, ir_render_task):
        d = task_to_dict(ir_render_task)
        recovered = dict_to_task(d)
        assert recovered.id == ir_render_task.id
        assert recovered.name == "IR Render"
        assert recovered.task_type == TaskType.STARDIS
        assert recovered.compute_mode == ComputeMode.IR_RENDER
        assert recovered.stardis_params.camera_ref == "Cam1"
        assert recovered.stardis_params.threads == 8
        assert recovered.stardis_params.samples == 100000

    def test_probe_solve_roundtrip(self, probe_solve_task):
        d = task_to_dict(probe_solve_task)
        recovered = dict_to_task(d)
        assert recovered.compute_mode == ComputeMode.PROBE_SOLVE
        assert recovered.stardis_params.probe_refs == ["Probe1"]
        assert recovered.stardis_params.samples == 500000

    def test_htpp_image_roundtrip(self, htpp_image_task):
        d = task_to_dict(htpp_image_task)
        recovered = dict_to_task(d)
        assert recovered.task_type == TaskType.HTPP
        assert recovered.htpp_mode == HtppMode.IMAGE
        assert isinstance(recovered.input_source, InputFromTask)
        assert recovered.input_source.task_id == "task-ir-001"
        assert recovered.htpp_params.exposure == 2.0
        assert recovered.htpp_params.white_scale == 5000.0

    def test_htpp_file_input_roundtrip(self):
        task = Task(
            name="HTPP from file",
            task_type=TaskType.HTPP,
            htpp_mode=HtppMode.MAP,
            input_source=InputFromFile(file_path="data/render.ht"),
            htpp_params=HtppParams(palette="jet", range_min=200.0, range_max=400.0),
        )
        d = task_to_dict(task)
        recovered = dict_to_task(d)
        assert isinstance(recovered.input_source, InputFromFile)
        assert recovered.input_source.file_path == "data/render.ht"
        assert recovered.htpp_params.palette == "jet"
        assert recovered.htpp_params.range_min == 200.0

    def test_field_solve_roundtrip(self):
        task = Task(
            name="Field Solve",
            task_type=TaskType.STARDIS,
            compute_mode=ComputeMode.FIELD_SOLVE,
            stardis_params=StardisParams(
                model_file="scene.txt",
                field_solve=FieldSolveConfig(
                    solve_type=FieldSolveType.SURF_TEMP_MAP,
                    solve_file="surf_temp.dat",
                ),
            ),
        )
        d = task_to_dict(task)
        recovered = dict_to_task(d)
        assert recovered.compute_mode == ComputeMode.FIELD_SOLVE
        fs = recovered.stardis_params.field_solve
        assert fs.solve_type == FieldSolveType.SURF_TEMP_MAP
        assert fs.solve_file == "surf_temp.dat"

    def test_advanced_options_roundtrip(self):
        adv = AdvancedOptions(
            diff_algorithm="mc",
            picard_order=3,
            initial_time=100.0,
            disable_intrad=True,
            extended_results=True,
            rng_state_in="rng_in.dat",
            rng_state_out="rng_out.dat",
        )
        task = Task(
            name="Adv",
            task_type=TaskType.STARDIS,
            compute_mode=ComputeMode.PROBE_SOLVE,
            stardis_params=StardisParams(
                model_file="scene.txt",
                probe_refs=["P1"],
                advanced=adv,
            ),
        )
        d = task_to_dict(task)
        recovered = dict_to_task(d)
        a = recovered.stardis_params.advanced
        assert a.diff_algorithm == "mc"
        assert a.picard_order == 3
        assert a.initial_time == 100.0
        assert a.disable_intrad is True
        assert a.extended_results is True
        assert a.rng_state_in == "rng_in.dat"
        assert a.rng_state_out == "rng_out.dat"

    def test_env_vars_roundtrip(self):
        task = Task(
            name="EnvTask",
            task_type=TaskType.STARDIS,
            env_vars={"PATH": "/usr/local/bin", "MY_VAR": "abc"},
        )
        d = task_to_dict(task)
        recovered = dict_to_task(d)
        assert recovered.env_vars == {"PATH": "/usr/local/bin", "MY_VAR": "abc"}

    def test_enabled_false_roundtrip(self):
        task = Task(name="Disabled", enabled=False)
        d = task_to_dict(task)
        recovered = dict_to_task(d)
        assert recovered.enabled is False

    def test_stderr_redirect_roundtrip(self):
        task = Task(
            name="WithRedirects",
            task_type=TaskType.STARDIS,
            output_redirect="stdout.log",
            stderr_redirect="stderr.log",
        )
        d = task_to_dict(task)
        assert d["output_redirect"] == "stdout.log"
        assert d["stderr_redirect"] == "stderr.log"
        recovered = dict_to_task(d)
        assert recovered.output_redirect == "stdout.log"
        assert recovered.stderr_redirect == "stderr.log"

    def test_stderr_redirect_none_by_default(self):
        task = Task(name="NoRedirect")
        d = task_to_dict(task)
        assert d["stderr_redirect"] is None
        recovered = dict_to_task(d)
        assert recovered.stderr_redirect is None

    def test_missing_id_generates_new(self):
        d = {"name": "NoID", "task_type": "stardis"}
        recovered = dict_to_task(d)
        assert recovered.id  # should have a non-empty UUID
        assert recovered.name == "NoID"


class TestTaskQueueSerialization:
    """TaskQueue 整体序列化往返。"""

    def test_full_queue_roundtrip(self, sample_task_queue):
        d = task_queue_to_dict(sample_task_queue)
        recovered = dict_to_task_queue(d)
        assert len(recovered.tasks) == 2
        assert recovered.error_policy.retry_count == 2
        assert recovered.error_policy.after_retries_exhausted == ErrorAction.SKIP
        assert recovered.env_vars == {"OMP_NUM_THREADS": "8"}

    def test_empty_queue_roundtrip(self):
        q = TaskQueue()
        d = task_queue_to_dict(q)
        recovered = dict_to_task_queue(d)
        assert len(recovered.tasks) == 0
        assert recovered.error_policy.retry_count == 0
        assert recovered.error_policy.after_retries_exhausted == ErrorAction.CANCEL

    def test_default_error_policy(self):
        d = {"tasks": []}
        recovered = dict_to_task_queue(d)
        assert recovered.error_policy.retry_count == 0
        assert recovered.error_policy.after_retries_exhausted == ErrorAction.CANCEL


class TestFactoryMethods:
    """create_stardis_task / create_htpp_task 工厂方法。"""

    def test_create_stardis_ir_task(self):
        task = create_stardis_task(
            "My IR", ComputeMode.IR_RENDER,
            camera_ref="Cam1", samples=50000,
            exe_ref="stardis_tag",
        )
        assert task.task_type == TaskType.STARDIS
        assert task.compute_mode == ComputeMode.IR_RENDER
        assert task.name == "My IR"
        assert task.stardis_params.camera_ref == "Cam1"
        assert task.stardis_params.samples == 50000
        assert task.exe_ref == "stardis_tag"

    def test_create_htpp_image_task(self):
        src = InputFromFile(file_path="render.ht")
        task = create_htpp_task(
            "My HTPP", HtppMode.IMAGE,
            input_source=src,
            exposure=1.5, output_file="out.png",
        )
        assert task.task_type == TaskType.HTPP
        assert task.htpp_mode == HtppMode.IMAGE
        assert task.input_source is src
        assert task.htpp_params.exposure == 1.5
        assert task.htpp_params.output_file == "out.png"

    def test_create_stardis_probe_task(self):
        task = create_stardis_task(
            "Probe", ComputeMode.PROBE_SOLVE,
            probe_refs=["P1", "P2"],
        )
        assert task.stardis_params.probe_refs == ["P1", "P2"]
