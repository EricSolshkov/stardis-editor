"""共享 fixtures for task_runner_tests."""

import sys
import os
import pytest

# 确保 src/ 在 sys.path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from models.task_model import (
    Task, TaskQueue, TaskType, ComputeMode, HtppMode,
    ErrorAction, ErrorPolicy,
    StardisParams, HtppParams, AdvancedOptions, FieldSolveConfig, FieldSolveType,
    InputFromTask, InputFromFile,
    create_stardis_task, create_htpp_task,
)
from models.scene_model import SceneModel, Probe, IRCamera, ProbeType


@pytest.fixture
def sample_camera():
    return IRCamera(
        name="Cam1",
        position=(10.0, 20.0, 30.0),
        target=(0.0, 0.0, 0.0),
        up=(0.0, 0.0, 1.0),
        fov=45.0,
        spp=64,
        resolution=(640, 480),
    )


@pytest.fixture
def sample_probe():
    return Probe(
        name="Probe1",
        probe_type=ProbeType.VOLUME_TEMP,
        position=(1.0, 2.0, 3.0),
        time=10.0,
    )


@pytest.fixture
def sample_scene_model(sample_camera, sample_probe):
    model = SceneModel()
    model.cameras = [sample_camera]
    model.probes = [sample_probe]
    return model


@pytest.fixture
def ir_render_task():
    return Task(
        id="task-ir-001",
        name="IR Render",
        task_type=TaskType.STARDIS,
        compute_mode=ComputeMode.IR_RENDER,
        exe_ref="/path/to/stardis",
        working_dir="/work",
        stardis_params=StardisParams(
            model_file="scene.txt",
            samples=100000,
            threads=8,
            verbosity=2,
            camera_ref="Cam1",
        ),
    )


@pytest.fixture
def probe_solve_task():
    return Task(
        id="task-probe-001",
        name="Probe Solve",
        task_type=TaskType.STARDIS,
        compute_mode=ComputeMode.PROBE_SOLVE,
        exe_ref="/path/to/stardis",
        working_dir="/work",
        stardis_params=StardisParams(
            model_file="scene.txt",
            samples=500000,
            threads=4,
            probe_refs=["Probe1"],
        ),
    )


@pytest.fixture
def htpp_image_task():
    return Task(
        id="task-htpp-001",
        name="HTPP Image",
        task_type=TaskType.HTPP,
        htpp_mode=HtppMode.IMAGE,
        exe_ref="/path/to/htpp",
        working_dir="/work",
        input_source=InputFromTask(task_id="task-ir-001"),
        htpp_params=HtppParams(
            threads=4,
            exposure=2.0,
            white_scale=5000.0,
            output_file="output.png",
        ),
    )


@pytest.fixture
def sample_task_queue(ir_render_task, htpp_image_task):
    return TaskQueue(
        tasks=[ir_render_task, htpp_image_task],
        error_policy=ErrorPolicy(retry_count=2, after_retries_exhausted=ErrorAction.SKIP),
        env_vars={"OMP_NUM_THREADS": "8"},
    )
