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
| `user_settings.json` | v1 用户持久化偏好设置（最近路径、可执行文件位置等），v2 首次启动时自动迁移 |
| `editor_settings.json` | v2 编辑器偏好设置（搜索目录、最近 exe/工作目录/工程、启动行为） |
| `config_examples/` | 示例配置文件（城市红外渲染、多孔介质红外渲染等） |
| `config_library/` | 用户保存的配置库（模板） |

### src/ — 顶层模块

| 文件 | 功能 |
|------|------|
| `main.py` | v1 主窗口 `MainWindow`，组合 STL 视口 + Stardis 控制面板 |
| `scene_editor.py` | v2 主窗口 `SceneEditor`，用 QSplitter 组合场景树/3D 视口/属性面板，集成偏好设置与最近工程 |
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
| `task_model.py` | 任务执行数据模型，定义 `Task`、`TaskQueue`、`StardisParams`、`HtppParams`、枚举（`TaskType`、`ComputeMode`、`HtppMode`、`ErrorAction`）及 JSON 序列化/反序列化 |
| `material_database.py` | 物理材质数据库，定义 `Material`（dataclass）和 `MaterialDatabase`（QObject），内置 25 种材质（金属/绝缘体/流体/其他），支持 CRUD、JSON 持久化、导入/导出 |
| `editor_preferences.py` | 编辑器偏好设置 `EditorPreferences`（dataclass），管理搜索目录、最近 exe/工作目录/工程文件、启动行为、exe 标签映射，支持从 v1 `user_settings.json` 迁移 |

### src/parsers/ — 场景文件解析器

| 文件 | 功能 |
|------|------|
| `scene_parser.py` | `SceneParser`：将 `.txt` 场景文件解析为 `SceneModel`，支持关键字驱动解析（SOLID、FLUID、T_BOUNDARY、H_BOUNDARY、F_BOUNDARY 等） |
| `scene_writer.py` | `SceneWriter`：将 `SceneModel` 写出为 `.txt` 场景文件 + STL 导出 + `.stardis_project.json` 工程文件 |

### src/panels/ — UI 面板

| 文件 | 功能 |
|------|------|
| `scene_tree_panel.py` | `SceneTreePanel(QTreeWidget)`：场景层级树，按边界类型着色显示，支持任务分组节点和右键快捷创建任务，Body 右键支持应用材质/保存材质 |
| `property_panel.py` | `PropertyPanel`：动态属性编辑器（QStackedWidget），包含 `GlobalSettingsEditor`、`BodyEditor`（含材质选择器）、`SurfaceZoneEditor`、`TaskQueueEditor`、`TaskEditor` 等子编辑器 |
| `material_manager_dialog.py` | `MaterialManagerDialog(QDialog)`：材质库 CRUD 管理对话框（分类筛选/表格浏览/详情编辑/导入导出），`SaveMaterialDialog`：从 Body 快速保存材质 |
| `task_editors.py` | 任务编辑器面板，`TaskQueueEditor`（错误策略/队列环境变量/运行按钮）和 `TaskEditor`（Stardis/HTPP 参数配置、命令预览） |
| `preferences_dialog.py` | `PreferencesDialog(QDialog)`：编辑器偏好设置对话框，3 个标签页（常规/可执行文件标签/最近工程） |

### src/viewport/ — 3D 渲染视口

| 文件 | 功能 |
|------|------|
| `scene_viewport.py` | `SceneViewport(QWidget)`：多物体 VTK 3D 视口，支持导航模式和画笔模式切换、单元拾取、探针显示、法线可视化 |
| `surface_painter.py` | `SurfacePainter`：BoundaryLabel 画笔系统，通过 `vtkIntArray` 标注网格单元所属区域，支持 50 步撤销/重做栈 |

### src/task_runner/ — 任务执行引擎

| 文件 | 功能 |
|------|------|
| `command_builder.py` | `CommandBuilder`：将任务参数转为 stardis/htpp CLI 参数列表（-M/-R/-p/-P/-f/-m/-s/-S/-F/-i/-m 等） |
| `task_runner.py` | `TaskRunner(QObject)`：队列调度器，管理引用求值（`resolve_all`）、QProcess 生命周期、错误处理（重试/跳过/暂停/取消） |

---

## 关键设计模式

- **信号/槽 MVC**：各组件通过 PyQt5 信号解耦通信
- **Model-View**：`SceneModel`（数据）↔ SceneTree（层级）/ SceneViewport（3D）/ PropertyPanel（编辑）
- **命令模式**：SurfacePainter 使用命令栈实现撤销/重做
- **关键字驱动格式**：场景 `.txt` 文件使用 SOLID / FLUID / T_BOUNDARY 等关键字，人类可读
- **偏好设置持久化**：`EditorPreferences` 管理编辑器级别设置（搜索目录、最近工程、启动行为、exe_tags 标签化可执行文件管理），JSON 序列化到 `editor_settings.json`，首次启动自动从 v1 `user_settings.json` 迁移，设计文档：`design/editor_preferences/`
- **物理材质数据库**：`MaterialDatabase` 管理可复用的物理材质参数（λ/ρ/cp），采用值拷贝语义——选择材质时将参数复制到 Body 的 `MaterialRef`，手动修改参数自动解除材质关联。内置 25 种常用材质，用户可新增/编辑/删除/导入/导出。JSON 持久化到 `material_database.json`，设计文档：`design/material_database/`

### 3. Task Runner（任务执行系统）
在 Scene Editor v2 中集成计算任务配置与执行，取代 v1 独立控制面板的手动工作流。支持：
- **任务队列**：有序任务列表，支持 Stardis（探针求解/场求解/IR 渲染）和 HTPP（图像/映射）两类任务
- **引用语义**：任务通过名称引用场景中的 Camera/Probe，启动时求值锁定
- **场景树集成**（A3 方案）：Tasks 作为顶层分组节点，选中时 PropertyPanel 切换到任务编辑器
- **右键快捷创建**：Camera 右键创建渲染任务组（Stardis IR + HTPP），Probe 右键创建探针计算任务
- **队列调度与错误处理**：重试/暂停/跳过/取消策略，HTPP 依赖 Stardis IR 输出的自动推导
- **场景验证**：通过 `stardis -d` 检查场景定义正确性，读取输出展示
- **持久化**：任务配置存储在 `.stardis_project.json` 的 `task_queue` 字段中

**参数体系**（v2.1.0+ 对齐 htpp C 源码实现）：
- **HTPP 参数** — `HtppParams` 完全对应 htpp C 实现的 `struct args`，包括：
  - IMAGE 模式：exposure (default 1.0) / white (auto or manual, default auto)
  - MAP 模式：pixcpnt (0-7，default 0) / palette (str，default "inferno") / range (auto or manual, default auto) / gnuplot (flag)
  - 通用：threads (-t，default 4) / force_overwrite (-f) / verbose (-v) / output_file (-o)
- **参数序列化**：仅传递非默认值给 `-i/-m` 标志，与 C 实现的 shell 命令语义一致；默认值不生成多余参数
- **UI 交互**（PropertyPanel HTPP 部分）：
  - 像素分量和调色板用下拉框预设选择
  - 白色缩放和范围支持自动/手动切换，与对应输入框实时联动禁用/启用
  - 每个参数附带 tooltip 说明 htpp C 源码行为

设计文档：`design/task_runner/`

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
                                   │
                            [TaskRunner]  ← 从 SceneModel.task_queue 读取
                                   │        引用 Camera/Probe 求值锁定
                                   │        CommandBuilder 构建参数
                                   ▼
                              QProcess (stardis / htpp) → stdout/stderr → 日志面板
```

---

## 测试

### 运行测试

项目使用 **pytest** 作为测试框架（兼容 `unittest` 风格）。在项目根目录下执行：

```bash
# NOTE: 使用venv环境的python.
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
| 材质数据库 (`models/`) | `Material`、`MaterialDatabase` CRUD/持久化/信号 | 需 `QApplication`，JSON 临时文件 |
| 解析器 (`parsers/`) | `SceneParser`、`SceneWriter`、`triangle_hash_matcher` | 临时文件 + fixtures，往返一致性 |
| 画笔系统 (`viewport/`) | `SurfacePainter` 标注与撤销/重做 | 构造 VTK PolyData，验证标注结果 |
| UI 面板 (`panels/`) | `SceneTreePanel`、`PropertyPanel` | 需 `QApplication`，验证信号/槽 |

---

## 更新维护

项目根目录下的 `CHANGE_LOG` 文件是 LLM 的本地工作日志，记录两次 Git 提交之间的累积变更。已被 `.gitignore` 忽略以打破循环依赖。每完成一项变更或 Git 提交后，按 `CHANGE_LOG` 文件头部的规则追加记录。若文件丢失，LLM 应自动重建。

当更新涉及新系统或模块时，要在 `AGENTS.md` 中添加对应章节，简要描述该模块的功能、设计模式等信息。并在 `/design/` 下创建新的设计文档目录，详细记录设计细节。按**渐进式披露**原则分层组织信息，保持每个文档的聚焦和可读性。
