# AGENTS.md — StardisEditor 项目指南

## 技术栈

| 技术 | 用途 |
|------|------|
| **Python 3** | 主语言 |
| **PyQt5** | GUI 框架（窗口、控件、信号/槽机制、QProcess 子进程管理） |
| **VTK** | 3D 可视化引擎（STL 渲染、鼠标交互、单元拾取、硬件选择器） |
| **dataclasses** | 数据模型定义（Body、SurfaceZone、BoundaryCondition 等） |
| **json** | 配置文件序列化/反序列化 |

无 requirements.txt，依赖安装：`pip install PyQt5 vtk`

---

## 项目架构

项目包含两大子系统：

### 1. Stardis 控制面板（v1 核心）
用于配置和运行 Stardis 仿真工具，包括参数填表、配置管理、STL 预览、进程执行。

### 2. Scene Editor v2（几何中心化场景编辑器）
采用 **Model-View** 架构，以几何体为核心组织边界条件与表面区域。支持：
- 场景树（层级浏览）、属性面板（动态编辑）、3D 视口（VTK 渲染 + 画笔模式）
- `.txt` 场景文件解析与写出、STL 导出
- 边界条件画笔（BoundaryLabel 单元标注）+ 撤销/重做

---

## 目录结构与文件功能

### 根目录

| 文件 | 功能 |
|------|------|
| `run_scene_editor.py` | Scene Editor v2 启动入口，将 `src/` 加入路径后启动 `SceneEditor` |
| `example_stardis_config.json` | Stardis 配置示例模板 |
| `user_settings.json` | 用户持久化偏好设置（最近路径、可执行文件位置等） |
| `config_examples/` | 示例配置文件（城市红外渲染、多孔介质红外渲染等） |
| `config_library/` | 用户保存的配置库（模板） |

### src/ — 顶层模块

| 文件 | 功能 |
|------|------|
| `main.py` | v1 主窗口 `MainWindow`，组合 STL 视口 + Stardis 控制面板 |
| `scene_editor.py` | v2 主窗口 `SceneEditor`，用 QSplitter 组合场景树/3D 视口/属性面板 |
| `StlViewport.py` | 独立 STL 查看器 `StlViewport(QVTKRenderWindowInteractor)`，支持旋转/平移/缩放交互 |
| `StardisConfig.py` | 基础配置类 `StardisConfig`，支持 JSON 保存/加载 |
| `StardisConfigEnhanced.py` | 增强配置类 `StardisConfigEnhanced`，含元数据管理 `StardisConfigMetadata` 和配置库 `ConfigLibrary` |
| `StardisControlPanel.py` | Stardis 控制面板 `StardisControlPanel(QWidget)`，4 个标签页（参数/执行/配置管理/日志） |
| `ConfigManagerDialog.py` | 配置管理对话框 `ConfigManagerDialog(QDialog)`，3 个标签页（库/最近/模板） |
| `HtppControlPanel.py` | 后处理图像工具面板 `HtppControlPanel(QWidget)`，调色板映射与进程执行 |
| `run_stardis_panel.py` | Stardis 控制面板独立启动脚本 |
| `run_htpp_panel.py` | HTPP 后处理面板独立启动脚本 |

### src/models/ — 数据模型

| 文件 | 功能 |
|------|------|
| `scene_model.py` | 几何中心化数据模型，定义 `SceneModel`、`Body`、`SurfaceZone`、`Probe`、`IRCamera`，以及边界条件数据类（`TemperatureBC`、`ConvectionBC`、`FluxBC`、`CombinedBC`） |

### src/parsers/ — 场景文件解析器

| 文件 | 功能 |
|------|------|
| `scene_parser.py` | `SceneParser`：将 `.txt` 场景文件解析为 `SceneModel`，支持关键字驱动解析（SOLID、FLUID、T_BOUNDARY、H_BOUNDARY、F_BOUNDARY 等） |
| `scene_writer.py` | `SceneWriter`：将 `SceneModel` 写出为 `.txt` 场景文件 + STL 导出 + `.stardis_project.json` 工程文件 |

### src/panels/ — UI 面板

| 文件 | 功能 |
|------|------|
| `scene_tree_panel.py` | `SceneTreePanel(QTreeWidget)`：场景层级树，按边界类型着色显示，通过信号通知选中项变化 |
| `property_panel.py` | `PropertyPanel`：动态属性编辑器（QStackedWidget），包含 `GlobalSettingsEditor`、`BodyEditor`、`SurfaceZoneEditor` 等子编辑器 |

### src/viewport/ — 3D 渲染视口

| 文件 | 功能 |
|------|------|
| `scene_viewport.py` | `SceneViewport(QWidget)`：多物体 VTK 3D 视口，支持导航模式和画笔模式切换、单元拾取、探针显示、法线可视化 |
| `surface_painter.py` | `SurfacePainter`：BoundaryLabel 画笔系统，通过 `vtkIntArray` 标注网格单元所属区域，支持 50 步撤销/重做栈 |

---

## 关键设计模式

- **信号/槽 MVC**：各组件通过 PyQt5 信号解耦通信
- **Model-View**：`SceneModel`（数据）↔ SceneTree（层级）/ SceneViewport（3D）/ PropertyPanel（编辑）
- **命令模式**：SurfacePainter 使用命令栈实现撤销/重做
- **关键字驱动格式**：场景 `.txt` 文件使用 SOLID / FLUID / T_BOUNDARY 等关键字，人类可读

---

## 场景文件格式（.txt）

```
SOLID: name λ ρ cp δ|AUTO T_init T_imposed|UNKNOWN power FRONT|BACK|BOTH stl...
FLUID: name ρ cp T_init T_imposed|UNKNOWN FRONT|BACK|BOTH stl...
T_BOUNDARY_FOR_SOLID: name temperature stl...
H_BOUNDARY_FOR_SOLID: name Tref ε spec hc T_env stl...
F_BOUNDARY_FOR_SOLID: name flux stl...
HF_BOUNDARY_FOR_SOLID: name Tref ε spec hc T_env flux stl...
```

---

## 数据流概览

```
scene.txt ──[SceneParser]──▶ SceneModel ──┬──▶ SceneTreePanel (层级树)
                                           ├──▶ PropertyPanel   (属性编辑)
                                           └──▶ SceneViewport   (3D 渲染)
                                                    │
                                           SurfacePainter (画笔标注)
                                                    │
                              SceneModel ◀──────────┘
                                   │
                            [SceneWriter]
                                   │
                              scene.txt + STL + .stardis_project.json
```

---

## 测试

### 运行测试

项目使用 **pytest** 作为测试框架（兼容 `unittest` 风格）。在项目根目录下执行：

```bash
# 运行全部测试
python -m pytest tests/ -v

# 运行指定测试模块
python -m pytest tests/paint_tests/test_roundtrip.py -v

# 运行指定测试类或方法
python -m pytest tests/paint_tests/test_roundtrip.py::TestRoundtripWithJson::test_cell_ids_recovered -v
```

### 测试目录结构

每个测试子目录包含自己的 `AGENTS.md`，记录该目录的具体测试覆盖与 fixtures 说明。

```
tests/
├── __init__.py
└── paint_tests/         # 模块功能的测试目录
    ├── AGENTS.md        # 该功能的详细测试说明
    ├── ...              # 具体测试文件
...                      # 其他模块的测试目录
```

### 新功能测试设计指导

- 按功能模块分组，放在 `tests/` 下对应子目录，每个子目录需包含 `__init__.py` 和 `AGENTS.md`
- 测试文件命名：`test_<模块名>.py`，共享 fixtures 放入 `conftest.py`
- **往返验证**：序列化/反序列化功能必须编写「写出 → 读回 → 对比」测试
- **临时目录**：使用 `tmp_path` 或 `tempfile.mkdtemp()` 管理测试文件
- **无头运行**：VTK 测试不弹窗；Qt 测试需创建 `QApplication` 但不调用 `exec_()`
- **断言明确**：每个测试方法验证一个明确行为

| 测试分层 | 对象 | 策略 |
|----------|------|------|
| 数据模型 (`models/`) | `SceneModel`、`Body`、边界条件 dataclass | 纯 Python 单元测试，无需 VTK/Qt |
| 解析器 (`parsers/`) | `SceneParser`、`SceneWriter`、`triangle_hash_matcher` | 临时文件 + fixtures，往返一致性 |
| 画笔系统 (`viewport/`) | `SurfacePainter` 标注与撤销/重做 | 构造 VTK PolyData，验证标注结果 |
| UI 面板 (`panels/`) | `SceneTreePanel`、`PropertyPanel` | 需 `QApplication`，验证信号/槽 |

---

## 更新维护

项目根目录下的 `CHANGE_LOG` 文件是 LLM 的本地工作日志，记录两次 Git 提交之间的累积变更。已被 `.gitignore` 忽略以打破循环依赖。每完成一项变更或 Git 提交后，按 `CHANGE_LOG` 文件头部的规则追加记录。若文件丢失，LLM 应自动重建。
