"""SceneModel 含 task_queue 的 save/load 往返测试。"""

import json
import os

from models.task_model import (
    Task, TaskQueue, TaskType, ComputeMode, HtppMode,
    ErrorPolicy, ErrorAction,
    StardisParams, HtppParams,
    InputFromTask,
    task_queue_to_dict, dict_to_task_queue,
)
from models.scene_model import SceneModel, IRCamera


class TestSceneModelTaskQueue:
    """SceneModel save_project / load_project 含 task_queue 的往返测试。"""

    def test_save_load_with_tasks(self, tmp_path):
        """保存含任务队列的工程并读回，task_queue 内容一致。"""
        model = SceneModel()
        cam = IRCamera(name="Cam1")
        model.cameras = [cam]

        ir_task = Task(
            id="t1", name="IR Render", task_type=TaskType.STARDIS,
            compute_mode=ComputeMode.IR_RENDER,
            stardis_params=StardisParams(model_file="scene.txt", camera_ref="Cam1"),
        )
        htpp_task = Task(
            id="t2", name="HTPP Post", task_type=TaskType.HTPP,
            htpp_mode=HtppMode.IMAGE,
            input_source=InputFromTask(task_id="t1"),
            htpp_params=HtppParams(exposure=2.0),
        )
        model.task_queue = TaskQueue(
            tasks=[ir_task, htpp_task],
            error_policy=ErrorPolicy(retry_count=1, after_retries_exhausted=ErrorAction.PAUSE),
            env_vars={"MY_VAR": "value"},
        )

        # 保存
        project_path = str(tmp_path / "test.stardis_project.json")
        model.save_project(project_path)

        # 读回
        loaded = SceneModel()
        loaded.load_project(project_path)
        assert len(loaded.task_queue.tasks) == 2
        assert loaded.task_queue.tasks[0].name == "IR Render"
        assert loaded.task_queue.tasks[1].name == "HTPP Post"
        assert loaded.task_queue.error_policy.retry_count == 1
        assert loaded.task_queue.error_policy.after_retries_exhausted == ErrorAction.PAUSE
        assert loaded.task_queue.env_vars == {"MY_VAR": "value"}

    def test_backward_compat_no_task_queue(self, tmp_path):
        """加载旧版工程文件（不含 task_queue 字段），应得到空队列。"""
        # 手动写一个不含 task_queue 的工程文件
        project_data = {
            "version": 1,
            "scene_file": "",
            "bodies": [],
        }
        project_path = str(tmp_path / "old.stardis_project.json")
        with open(project_path, 'w', encoding='utf-8') as f:
            json.dump(project_data, f)

        loaded = SceneModel()
        loaded.load_project(project_path)
        assert len(loaded.task_queue.tasks) == 0
        assert loaded.task_queue.error_policy.retry_count == 0

    def test_empty_task_queue_save_load(self, tmp_path):
        """空任务队列的保存/读回。"""
        model = SceneModel()
        model.task_queue = TaskQueue()

        project_path = str(tmp_path / "empty.stardis_project.json")
        model.save_project(project_path)

        loaded = SceneModel()
        loaded.load_project(project_path)
        assert len(loaded.task_queue.tasks) == 0
