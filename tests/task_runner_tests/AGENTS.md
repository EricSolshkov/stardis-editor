# AGENTS.md — task_runner_tests

## 测试覆盖

| 文件 | 覆盖内容 |
|------|----------|
| `test_task_model.py` | Task/TaskQueue 序列化往返、factory 方法、InputSource 多态 |
| `test_command_builder.py` | Stardis IR/Probe/Field 命令生成、HTPP Image/Map、高级选项 |
| `test_task_runner.py` | `resolve_exe_ref`、`resolve_all` 校验、HTPP 依赖链 |
| `test_scene_model_tasks.py` | SceneModel 含 task_queue 的 save/load 往返、向后兼容 |

## Fixtures

- `conftest.py`：提供 `sample_stardis_task`、`sample_htpp_task`、`sample_scene_model` 等 fixtures
- 所有测试纯 Python 单元测试，不依赖 Qt 或 VTK
