"""resolve_exe_ref / resolve_all 逻辑测试。"""

import os
import tempfile
import pytest

from models.task_model import (
    Task, TaskQueue, TaskType, ComputeMode, HtppMode,
    ErrorPolicy, ErrorAction,
    StardisParams, HtppParams, FieldSolveConfig, FieldSolveType,
    InputFromTask, InputFromFile,
)
from models.scene_model import SceneModel, IRCamera, Probe, ProbeType
from models.editor_preferences import EditorPreferences
from task_runner.task_runner import resolve_exe_ref, resolve_all, ValidationError


class TestResolveExeRef:
    """解析可执行文件引用。"""

    def test_absolute_path_exists(self, tmp_path):
        exe = tmp_path / "stardis.exe"
        exe.write_text("fake")
        result = resolve_exe_ref(str(exe), EditorPreferences())
        assert result == str(exe)

    def test_absolute_path_not_exists(self):
        with pytest.raises(ValidationError, match="不存在"):
            resolve_exe_ref("/no/such/file", EditorPreferences())

    def test_tag_lookup(self, tmp_path):
        exe = tmp_path / "stardis"
        exe.write_text("fake")
        prefs = EditorPreferences(exe_tags={"stardis": str(exe)})
        result = resolve_exe_ref("stardis", prefs)
        assert result == str(exe)

    def test_tag_not_found(self):
        with pytest.raises(ValidationError, match="找不到"):
            resolve_exe_ref("unknown_tag", EditorPreferences())

    def test_empty_ref(self):
        with pytest.raises(ValidationError, match="未指定"):
            resolve_exe_ref("", EditorPreferences())


class TestResolveAll:
    """resolve_all 完整链路测试。"""

    def _make_exe(self, tmp_path, name="stardis"):
        exe = tmp_path / name
        exe.write_text("fake")
        return str(exe)

    def test_ir_render_resolve(self, tmp_path):
        exe = self._make_exe(tmp_path)
        cam = IRCamera(name="Cam1", position=(1, 2, 3), target=(0, 0, 0),
                       up=(0, 0, 1), fov=30, spp=32, resolution=(320, 240))
        model = SceneModel()
        model.cameras = [cam]

        task = Task(
            id="t1", name="IR", task_type=TaskType.STARDIS,
            compute_mode=ComputeMode.IR_RENDER,
            exe_ref=exe, working_dir=str(tmp_path),
            stardis_params=StardisParams(model_file="scene.txt", camera_ref="Cam1"),
        )
        queue = TaskQueue(tasks=[task])
        prefs = EditorPreferences()

        resolved = resolve_all(queue, model, prefs, str(tmp_path))
        assert len(resolved) == 1
        rt = resolved[0]
        assert rt.exe_path == exe
        assert '-R' in rt.args
        assert rt.output_file is not None
        assert "320x240x32" in rt.output_file

    def test_htpp_depends_on_ir(self, tmp_path):
        stardis_exe = self._make_exe(tmp_path, "stardis")
        htpp_exe = self._make_exe(tmp_path, "htpp")
        cam = IRCamera(name="C1", resolution=(320, 240), spp=32)
        model = SceneModel()
        model.cameras = [cam]

        ir_task = Task(
            id="ir1", name="IR", task_type=TaskType.STARDIS,
            compute_mode=ComputeMode.IR_RENDER,
            exe_ref=stardis_exe, working_dir=str(tmp_path),
            stardis_params=StardisParams(model_file="s.txt", camera_ref="C1"),
        )
        htpp_task = Task(
            id="htpp1", name="HTPP", task_type=TaskType.HTPP,
            htpp_mode=HtppMode.IMAGE, exe_ref=htpp_exe,
            working_dir=str(tmp_path),
            input_source=InputFromTask(task_id="ir1"),
            htpp_params=HtppParams(exposure=1.0),
        )
        queue = TaskQueue(tasks=[ir_task, htpp_task])

        resolved = resolve_all(queue, model, EditorPreferences(), str(tmp_path))
        assert len(resolved) == 2
        # HTPP 的 input_file 应该是 IR 的 output_file
        assert resolved[1].input_file == resolved[0].output_file

    def test_htpp_missing_dependency_error(self, tmp_path):
        htpp_exe = self._make_exe(tmp_path, "htpp")
        model = SceneModel()

        htpp_task = Task(
            id="htpp1", name="HTPP", task_type=TaskType.HTPP,
            htpp_mode=HtppMode.IMAGE, exe_ref=htpp_exe,
            working_dir=str(tmp_path),
            input_source=InputFromTask(task_id="nonexistent"),
            htpp_params=HtppParams(),
        )
        queue = TaskQueue(tasks=[htpp_task])

        with pytest.raises(ValidationError, match="未找到"):
            resolve_all(queue, model, EditorPreferences(), str(tmp_path))

    def test_disabled_tasks_skipped(self, tmp_path):
        exe = self._make_exe(tmp_path)
        model = SceneModel()

        task = Task(
            id="t1", name="Disabled", enabled=False,
            task_type=TaskType.STARDIS, exe_ref=exe,
            working_dir=str(tmp_path),
            stardis_params=StardisParams(model_file="s.txt"),
        )
        queue = TaskQueue(tasks=[task])
        resolved = resolve_all(queue, model, EditorPreferences(), str(tmp_path))
        assert len(resolved) == 0

    def test_missing_camera_ref_error(self, tmp_path):
        exe = self._make_exe(tmp_path)
        model = SceneModel()

        task = Task(
            id="t1", name="IR", task_type=TaskType.STARDIS,
            compute_mode=ComputeMode.IR_RENDER, exe_ref=exe,
            working_dir=str(tmp_path),
            stardis_params=StardisParams(model_file="s.txt", camera_ref="NoSuchCam"),
        )
        queue = TaskQueue(tasks=[task])

        with pytest.raises(ValidationError, match="不存在"):
            resolve_all(queue, model, EditorPreferences(), str(tmp_path))

    def test_probe_solve_resolve(self, tmp_path):
        exe = self._make_exe(tmp_path)
        probe = Probe(name="P1", probe_type=ProbeType.VOLUME_TEMP,
                      position=(1, 2, 3), time=5.0)
        model = SceneModel()
        model.probes = [probe]

        task = Task(
            id="t1", name="Probe", task_type=TaskType.STARDIS,
            compute_mode=ComputeMode.PROBE_SOLVE, exe_ref=exe,
            working_dir=str(tmp_path),
            stardis_params=StardisParams(model_file="s.txt", samples=1000,
                                         probe_refs=["P1"]),
        )
        queue = TaskQueue(tasks=[task])
        resolved = resolve_all(queue, model, EditorPreferences(), str(tmp_path))
        assert len(resolved) == 1
        assert '-p' in resolved[0].args

    def test_field_solve_resolve(self, tmp_path):
        exe = self._make_exe(tmp_path)
        model = SceneModel()

        task = Task(
            id="t1", name="Field", task_type=TaskType.STARDIS,
            compute_mode=ComputeMode.FIELD_SOLVE, exe_ref=exe,
            working_dir=str(tmp_path),
            stardis_params=StardisParams(
                model_file="s.txt", samples=100,
                field_solve=FieldSolveConfig(
                    solve_type=FieldSolveType.MEDIUM_TEMP, medium_name="air",
                ),
            ),
        )
        queue = TaskQueue(tasks=[task])
        resolved = resolve_all(queue, model, EditorPreferences(), str(tmp_path))
        assert len(resolved) == 1
        assert '-m' in resolved[0].args
        assert 'air' in resolved[0].args

    def test_htpp_from_file(self, tmp_path):
        exe = self._make_exe(tmp_path, "htpp")
        model = SceneModel()

        task = Task(
            id="t1", name="HTPP File", task_type=TaskType.HTPP,
            htpp_mode=HtppMode.MAP, exe_ref=exe,
            working_dir=str(tmp_path),
            input_source=InputFromFile(file_path="render.ht"),
            htpp_params=HtppParams(pixel_component=0),
        )
        queue = TaskQueue(tasks=[task])
        resolved = resolve_all(queue, model, EditorPreferences(), str(tmp_path))
        assert len(resolved) == 1
        expected_input = os.path.join(str(tmp_path), "render.ht")
        assert resolved[0].input_file == expected_input

    def test_env_vars_merged(self, tmp_path):
        exe = self._make_exe(tmp_path)
        cam = IRCamera(name="C1")
        model = SceneModel()
        model.cameras = [cam]

        task = Task(
            id="t1", name="Env", task_type=TaskType.STARDIS,
            compute_mode=ComputeMode.IR_RENDER, exe_ref=exe,
            working_dir=str(tmp_path),
            env_vars={"TASK_VAR": "task_val"},
            stardis_params=StardisParams(model_file="s.txt", camera_ref="C1"),
        )
        queue = TaskQueue(
            tasks=[task],
            env_vars={"QUEUE_VAR": "queue_val", "TASK_VAR": "queue_val"},
        )
        resolved = resolve_all(queue, model, EditorPreferences(), str(tmp_path))
        # Task-level env_vars should override queue-level
        assert resolved[0].env_vars["TASK_VAR"] == "task_val"
        assert resolved[0].env_vars["QUEUE_VAR"] == "queue_val"

    def test_stderr_redirect_resolve(self, tmp_path):
        exe = self._make_exe(tmp_path)
        cam = IRCamera(name="C1")
        model = SceneModel()
        model.cameras = [cam]

        task = Task(
            id="t1", name="WithStderr", task_type=TaskType.STARDIS,
            compute_mode=ComputeMode.IR_RENDER, exe_ref=exe,
            working_dir=str(tmp_path),
            stderr_redirect="errors.log",
            stardis_params=StardisParams(model_file="s.txt", camera_ref="C1"),
        )
        queue = TaskQueue(tasks=[task])
        resolved = resolve_all(queue, model, EditorPreferences(), str(tmp_path))
        assert len(resolved) == 1
        expected = os.path.join(str(tmp_path), "errors.log")
        assert resolved[0].stderr_file == expected

    def test_no_stderr_redirect_by_default(self, tmp_path):
        exe = self._make_exe(tmp_path)
        cam = IRCamera(name="C1")
        model = SceneModel()
        model.cameras = [cam]

        task = Task(
            id="t1", name="NoStderr", task_type=TaskType.STARDIS,
            compute_mode=ComputeMode.IR_RENDER, exe_ref=exe,
            working_dir=str(tmp_path),
            stardis_params=StardisParams(model_file="s.txt", camera_ref="C1"),
        )
        queue = TaskQueue(tasks=[task])
        resolved = resolve_all(queue, model, EditorPreferences(), str(tmp_path))
        assert resolved[0].stderr_file is None
