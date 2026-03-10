# 场景树与 VTK 交互系统设计（已归档）

> ⚠️ **本文档已拆分归档**，请使用 [`design/scene_editor/`](scene_editor/README.md) 目录下的分层文档：
>
> | 文件 | 对应原文内容 |
> |------|------------|
> | [01_概念与数据模型.md](scene_editor/01_概念与数据模型.md) | §一（心智模型）、§二（数据模型、序列化）|
> | [02_UI行为规约.md](scene_editor/02_UI行为规约.md) | §三（场景树）、§四（视口行为）、§五（属性面板）、§八（工作流）|
> | [03_组件通信协议.md](scene_editor/03_组件通信协议.md) | §六（信号定义、联动矩阵）|
> | [04_VTK实现方案.md](scene_editor/04_VTK实现方案.md) | §七（VTK 渲染架构）+ §四中的 VTK 代码块 |
> | [05_工程规划.md](scene_editor/05_工程规划.md) | §九（性能考量）、§十（实施分步）|
>
> 本文件保留为历史参考，不再维护。

---

# （历史存档）场景树与 VTK 交互系统设计

本文档详细规定场景树面板、3D 视口和属性编辑面板三者如何协作，构成场景编辑器的核心交互循环。

---

## 一、核心心智模型

用户的思维过程：

```
"我有一组几何体（STL）"
  → "每个几何体的内部是什么材质？"
  → "每个几何体的表面各区域是什么边界条件？"
  → "几何体之间的接触关系是什么？"
```

编辑器以**几何体为中心**组织所有信息。边界条件是几何体表面的**面属性**，不是独立实体。探针是场景中的**空间标记点**，用于指定求解器在何处提取温度/通量等物理量。

---

## 二、数据模型（几何中心视角）

### 2.1 逻辑结构

```
SceneModel
├── global_settings
│   ├── trad: (T_ambient, T_reference)
│   └── scale: float
│
├── bodies: List[Body]                     # 几何体列表（核心组织单元）
│   └── Body
│       ├── name: str                      # 唯一标识（如 "FOAM"）
│       ├── stl_files: List[str]           # 组成几何体的 STL 文件
│       ├── volume: VolumeProperties       # 体积属性（材质）
│       │   ├── type: SOLID | FLUID
│       │   ├── material: MaterialRef      # λ, ρ, cp
│       │   ├── delta: float | "AUTO"      # 仅 SOLID
│       │   ├── initial_temp: float
│       │   ├── imposed_temp: float | "UNKNOWN"
│       │   ├── volumetric_power: float    # 仅 SOLID
│       │   └── side: FRONT | BACK | BOTH  # 材质在法线哪一侧
│       │
│       └── surface_zones: List[SurfaceZone]  # 表面区域（边界条件）
│           └── SurfaceZone
│               ├── name: str              # 如 "LAT", "T0"
│               ├── source: ImportedSTL | PaintedRegion
│               │   ├── ImportedSTL        # 来源方式 A：导入已有 STL
│               │   │   └── stl_file: str
│               │   └── PaintedRegion      # 来源方式 B：涂选生成
│               │       └── cell_ids: Set[int]  # 母体上被选中的三角面 ID
│               ├── boundary: BoundaryCondition
│               │   ├── TemperatureBC      # T_BOUNDARY_FOR_SOLID
│               │   │   └── temperature: float
│               │   ├── ConvectionBC       # H_BOUNDARY_FOR_SOLID
│               │   │   ├── Tref, emissivity, specular_fraction
│               │   │   └── hc, T_env
│               │   ├── FluxBC             # F_BOUNDARY_FOR_SOLID
│               │   │   └── flux: float
│               │   └── CombinedBC         # HF_BOUNDARY_FOR_SOLID
│               │       └── ConvectionBC 字段 + flux
│               └── color: QColor          # 显示颜色（自动分配或用户自定义）
│
├── connections: List[Connection]          # 几何体间接触关系
│   ├── SolidFluidConnection
│   │   ├── name, Tref, emissivity, specular_fraction, hc
│   │   ├── body_a: Body ref              # 参与连接的几何体 A
│   │   ├── body_b: Body ref              # 参与连接的几何体 B
│   │   └── stl_files: List[str]          # 界面几何
│   └── SolidSolidConnection
│       ├── name, contact_resistance
│       ├── body_a, body_b
│       └── stl_files: List[str]
│
├── probes: List[Probe]                    # 探针列表（求解器采样点）
│   └── Probe
│       ├── name: str                      # 用户自定义标签 (如 "P1", "中心点")
│       ├── type: VolumeTemp | SurfaceTemp | SurfaceFlux
│       │   ├── VolumeTemp                 # CLI: -p X,Y,Z[,T]
│       │   │   └── time: float | "INF"    # 采样时刻（稳态用 INF）
│       │   ├── SurfaceTemp                # CLI: -P X,Y,Z,SIDE
│       │   │   └── side: str              # 面标识
│       │   └── SurfaceFlux                # CLI: -f X,Y,Z
│       ├── position: (x, y, z)            # 世界坐标
│       └── color: QColor                  # 显示颜色
│
├── cameras: List[IRCamera]               # IR 渲染摄像机
│   └── IRCamera
│       ├── name: str                      # 摄像机标签 (如 "Camera1")
│       ├── position: (x, y, z)            # 摄像机世界坐标
│       ├── target: (x, y, z)              # 注视点世界坐标
│       ├── up: (x, y, z)                  # 向上方向 (默认 0,0,1)
│       ├── fov: float                     # 视场角 (°)，默认 30
│       ├── spp: int                       # 每像素采样数，默认 32
│       └── resolution: (w, h)             # 渲染分辨率，默认 320×320
│
├── lights: List[SceneLight]              # 光源列表
│   └── SceneLight
│       ├── name: str                      # 光源标签 (如 "DefaultLight")
│       ├── light_type: LightType          # DEFAULT | SPHERICAL_SOURCE | SPHERICAL_SOURCE_PROG
│       ├── color: (r, g, b)               # VTK 显示颜色 (0~1)
│       ├── position: (x, y, z)            # 世界坐标位置
│       ├── enabled: bool                  # 是否启用
│       ├── radius: float                  # 球面源半径 (m)，仅 SPHERICAL_SOURCE
│       ├── power: float                   # 功率 (W)，仅 SPHERICAL_SOURCE
│       ├── diffuse_radiance: float        # 漫射辐亮度 (W/m²/sr)，仅 SPHERICAL_SOURCE
│       └── raw_line: str                  # 原始行，仅 SPHERICAL_SOURCE_PROG (原样读写)
│
└── ambient_intensity: float = 0.15       # 环境基本光照强度 (恒存在，不受其他光源影响)
```

**光源类型说明**：

| LightType | 场景文件关键字 | 含义 | VTK 渲染 |
|-----------|---------------|------|----------|
| DEFAULT | (不写入 scene.txt) | 编辑器默认场景光 | 非位置光 (headlight) |
| SPHERICAL_SOURCE | `SPHERICAL_SOURCE radius px py pz power diffuse_radiance` | 常量球面源 | 位置点光源 |
| SPHERICAL_SOURCE_PROG | `SPHERICAL_SOURCE_PROG radius prog_name PROG_PARAMS args...` | 可编程球面源，原样读写 | 不参与 VTK 光照 |

**光源自动管理规则**：
- `ensure_default_light()`：若场景中无 DEFAULT 和 SPHERICAL_SOURCE（仅 PROG 不算），自动创建一个 DEFAULT 光源
- 添加 SPHERICAL_SOURCE 时，自动禁用所有 DEFAULT 光源
- 删除所有光源后，自动重建 DEFAULT 光源
- `ambient_intensity` 始终存在，通过 `actor.GetProperty().SetAmbient()` 施加到所有几何体 Actor，不受光源增删影响

### 2.2 场景的序列化与反序列化

编辑器需在运行时 SceneModel 与磁盘文件之间双向转换。

#### 2.2.1 序列化（保存）：SceneModel → 文件夹

保存时，以用户指定的目标文件夹为根，生成以下产物：

```
输出文件夹/
├── scene.txt                  # stardis 场景描述文件
├── S_FOAM.stl                 # Body 几何 STL (原文件拷贝或涂选母体)
├── B_LAT.stl                  # 边界区域 STL
├── B_T0.stl                   # 边界区域 STL
├── B_T1.stl                   # 边界区域 STL
└── .stardis_project.json      # 编辑器项目元数据 (探针、摄像机等非场景数据)
```

**序列化流程**：

```
SceneModel
  │
  ├── 1. 生成 scene.txt
  │     ├── global_settings → TRAD / SCALE 行
  │     ├── Body → SOLID/FLUID 行 (引用 STL 文件的相对路径)
  │     ├── SurfaceZone → *_BOUNDARY_FOR_SOLID 行
  │     └── Connection → *_CONNECTION 行
  │
  ├── 2. 导出边界 STL
  │     ├── SurfaceZone(ImportedSTL) → 将原 STL 拷贝到输出文件夹
  │     └── SurfaceZone(PaintedRegion) → 从母体 PolyData 按 BoundaryLabel
  │           提取子网格 → vtkSTLWriter 写入 B_<name>.stl
  │
  ├── 3. 拷贝/链接几何 STL
  │     └── Body 的 stl_files → 拷贝到输出文件夹 (若不在同一目录)
  │
  └── 4. 保存项目文件 (.stardis_project.json)
        ├── 探针列表 (位置、类型、参数)
        ├── 摄像机列表
        └── 涂选状态 (BoundaryLabel 数组, 便于下次打开时恢复涂选)
```

scene.txt 中所有 STL 路径均为**相对于 scene.txt 所在目录的相对路径**。

#### 2.2.2 反序列化（打开）：文件夹 → SceneModel

从用户选取的 `.txt` 文件所在文件夹读取场景：

```
用户选择 scene.txt
  │
  ├── 1. 解析 scene.txt
  │     ├── TRAD / SCALE → global_settings
  │     ├── SOLID/FLUID → 创建 Body 列表, 加载对应 STL 几何
  │     ├── *_BOUNDARY_FOR_SOLID → 创建临时 Boundary 列表
  │     └── *_CONNECTION → 创建 Connection 列表
  │
  ├── 2. 几何匹配: 将 Boundary 归入 Body
  │     对每个 Boundary 的 stl_file:
  │       ├── 策略 A (快速): 文件名前缀匹配
  │       │   "B_lateral.stl" → 找 "S_*.stl" → 不可靠但作为首选启发式
  │       │
  │       ├── 策略 B (精确): 几何包含检测
  │       │   加载 boundary.stl 的所有顶点
  │       │   对每个 body.stl, 检查顶点是否在其表面上
  │       │   使用 vtkCellLocator.FindClosestPoint()
  │       │   若所有顶点距离 < ε → boundary ⊂ body
  │       │
  │       └── 策略 C (交互): 无法自动匹配时，提示用户手动指定归属
  │
  ├── 3. 为每个 Body 的已匹配 boundary 创建 SurfaceZone
  │     source = ImportedSTL(stl_file)
  │
  ├── 4. 若同目录存在 .stardis_project.json → 恢复探针、摄像机、涂选状态
  │
  └── 5. 计算覆盖率，显示在属性面板中
```

#### 2.2.3 匹配歧义处理

| 情况 | 处理 |
|------|------|
| 一个 boundary STL 精确匹配到一个 body | 自动归入 |
| 一个 boundary STL 匹配到多个 body (嵌套几何体的共享面) | 提示用户选择归属 |
| 一个 boundary STL 不匹配任何 body | 标记为"游离边界"，放在顶级节点下，提示用户处理 |
| 多个 body 的覆盖率不足 100% | 仅在属性面板中显示，不阻塞导入 |

---

## 三、场景树面板

### 3.1 树形结构

```
场景树 (Porous 场景示例)
├── 🌐 全局设置
│   ├── TRAD: 680 / 800
│   └── SCALE: 1.0
│
├── 🧊 几何体
│   └── FOAM [SOLID]
│       ├── 🔴 LAT [对流] (780 △)
│       ├── 🔵 T0 [固定温度 750K] (212 △)
│       └── 🔵 T1 [固定温度 850K] (212 △)
│
├── 🔗 连接 (0)
│
├── 📍 探针 (3)
│   ├── 📍 P1 [体积温度] (0.5, 0.5, 0.5) t=INF
│   ├── 📍 P2 [表面温度] (0.1, 0.0, 0.05) side=FRONT
│   └── 📍 F1 [表面通量] (0.0, 0.05, 0.05)
│
├── 📷 摄像机 (IR 模式)
│   └── Camera1: pos → tgt
│
└── 💡 光源 (1)
    ├── ☀ 环境光照 (强度 0.15)
    └── DefaultLight [默认]

场景树 (City 场景示例)
├── 🌐 全局设置
│   ├── TRAD: 300 / 300
│   └── SCALE: 1.0
│
├── 🧊 几何体
│   ├── WALL [SOLID]
│   │   ├── 🔴 EXTERNAL [对流 T=273K]
│   │   └── 🔴 INTERNAL [对流 T=293K]
│   ├── INSULATOR [SOLID]
│   │   └── ...
│   ├── GLAZING [SOLID]
│   │   ├── 🟠 EXT_GLAZING [对流 ε=0.15 spec=0.8]
│   │   └── 🟠 INT_GLAZING [对流 ε=0.15 spec=0.8]
│   └── GROUND [SOLID]
│       └── ...
│
├── 🔗 连接 (0)
├── 📍 探针 (0)
├── 📷 摄像机
│   └── Camera1
│
└── 💡 光源 (2)
    ├── ☀ 环境光照 (强度 0.15)
    ├── SphericalSource1 [常量球面源]
    └── SphericalSourceProg1 [可编程球面源]
```

**要点**：
- 表面区域节点直接挂在 Body 下，无表面区域组节点
- 表面区域节点由涂选编辑自动生成，不手动创建/删除
- 覆盖率等统计信息显示在属性面板中，不作为树节点

### 3.2 树节点类型与操作

| 节点类型 | 图标 | 单击 | 双击 | 右键菜单 |
|---------|------|------|------|---------|
| 全局设置 | 🌐 | 属性面板显示全局参数 | — | — |
| 几何体组 | 📁 | — | — | 添加几何体 |
| 几何体 (Body) | 🧊 | 3D 高亮整个几何体 + 属性面板显示体积属性 | 重命名 | 进入涂选编辑、删除 |
| 表面区域 | 🔴🔵🟢🟣 | 3D 高亮该区域 + 属性面板显示边界参数 | 重命名 | — (不可删除/不可修改范围) |
| 连接 | 🔗 | 高亮界面几何 + 显示连接参数 | 重命名 | 删除 |
| 探针组 | 📍 | — | — | 添加探针 |
| 探针 | 📍 | 属性面板显示参数 + 3D 视口高亮 | 重命名 | 删除 |
| 摄像机 | 📷 | 显示摄像机锥体 + 属性面板显示参数 | 重命名 | 删除、使用当前视角 |
| 光源组 | 💡 | — | — | 添加默认光源、添加常量球面源、添加可编程球面源 |
| 环境光照 | ☀ | 属性面板显示环境光照强度 | — | — (不可删除，恒存在) |
| 光源 (SceneLight) | — | 属性面板显示光源参数 | — | 删除 |

**关键约束**：
- 几何体的 STL 设置、材质赋值等均在**属性面板**中完成，不在右键菜单
- 表面区域节点由涂选模式退出时**自动生成**（根据 BoundaryLabel 数组中的不同值），不支持手动添加或删除
- 表面区域的范围（包含哪些三角面）只能通过重新进入涂选模式修改，不能在树中直接操作
- 表面区域节点可查看和修改边界条件类型及参数（在属性面板中）
- 几何体不支持复制

### 3.3 拖拽操作

| 操作 | 效果 |
|------|------|
| 外部 STL 文件拖入「几何体」组 | 创建新几何体 |

不支持：拖入 STL 到几何体创建表面区域（表面区域只能通过涂选模式生成）、拖拽排序、拖动表面区域。

### 3.4 覆盖率信息

覆盖率统计显示在属性面板中（选中 Body 时的「表面区域概览」部分），不作为场景树节点。

```
覆盖率计算 = Σ(所有 surface_zone 的三角面数) / 母体总三角面数
```

| 状态 | 显示 | 含义 |
|------|------|------|
| 100% | ✅ | 所有表面已分配边界条件 |
| 0% < x < 100% | ⚠️ 78% | 部分表面未分配（灰色区域可见） |
| 0% | ❌ | 无任何边界条件 |
| > 100% | ⛔ | 区域有重叠 |

**注意**：覆盖率不足 100% 不一定是错误。某些面可能不需要边界条件（由 stardis 的域划分自动处理为内部界面），但编辑器应提醒用户检查。

---

## 四、3D 视口交互

### 4.1 视口模式

视口有两种互斥的工作模式，通过工具栏按钮切换：

| 模式 | 鼠标操作 | 用途 |
|------|---------|------|
| **导航模式** (默认) | 中键按住旋转、WASD+Shift/Ctrl 平移导航、滚轮缩放、左键点选、双击放置探针 | 浏览场景、选择对象、放置探针 |
| **涂选模式** | 左键拖拽涂选、Ctrl+左键擦除、中键按住旋转、滚轮缩放 | 在几何体表面划分边界区域 |

### 4.2 导航模式下的交互

#### 4.2.1 选择（Picking）

| 操作 | 行为 |
|------|------|
| 左键单击几何体 | 选中该 Body → 场景树同步高亮 + 属性面板切换 |
| 左键单击探针标记 | 选中该 Probe → 场景树同步 + 属性面板切换 |
| 左键单击空白 | 取消选择 |
| 双击几何体表面 | 在命中点放置新探针 |

不支持多选。左键点选仅覆盖 Body 和 Probe，不直接选中表面区域（表面区域通过场景树查看）。

#### 4.2.2 高亮反馈

高亮效果**仅在导航模式下显示**，进入涂选模式时自动清除。

| 选中对象 | 3D 视觉效果 |
|---------|------------|
| 几何体 (Body) | **轮廓线高亮 (Silhouette)**：使用 `vtkPolyDataSilhouette` 绘制黄色轮廓线（默认颜色 (1,1,0)，线宽 3），自动跟随相机视角更新 |
| 表面区域 (SurfaceZone) | **轮廓线 + 区域着色高亮**：所属 Body 显示轮廓线；同时临时修改 LUT，选中区域以其分配的颜色实体着色显示，其余区域变为暗灰色 (0.45, 0.45, 0.45)，取消选择时恢复原始 LUT |
| 探针 | 标记图标放大 + 坐标标注 |
| 无选中 | 所有对象恢复正常渲染 |

```
VTK 实现 (Silhouette):
  vtkPolyDataSilhouette
    .SetInputData(body_polydata)
    .SetCamera(renderer.GetActiveCamera())
  vtkPolyDataMapper → vtkActor
    .GetProperty().SetColor(1.0, 1.0, 0.0)  # 黄色
    .GetProperty().SetLineWidth(3.0)

VTK 实现 (区域 LUT 高亮):
  保存当前 LUT (DeepCopy)
  构建高亮 LUT:
    选中区域 label → 保持原色
    其余所有 label → 暗灰 (0.45, 0.45, 0.45)
  取消选择时恢复保存的 LUT
```

#### 4.2.3 法线显示

选中几何体后，可切换其面法线可视化，用于检查法线朝向是否正确（影响材质 `side` 设置）。

| 操作 | 行为 |
|------|------|
| `N` 键 | 切换选中几何体的法线显示（开/关） |
| `+` 键 | 法线显示长度 × 10 |
| `-` 键 | 法线显示长度 × 0.1 |

**视觉效果**：每个三角面中心向法线方向延伸一条红色线段（默认长度 1）。长度缩放对所有已显示法线的几何体同时生效。切换场景或清除选择时自动移除所有法线显示。

```
VTK 实现:
  vtkPolyDataNormals → 计算面法线
  vtkCellCenters     → 提取面中心点
  vtkHedgeHog        → 从面中心沿法线方向生成线段 (scaleFactor = length)
  vtkActor           → 红色 (1,0,0), 线宽 1
```

#### 4.2.4 悬停提示 (Tooltip)

鼠标悬停在 3D 对象上时显示对象名称：

```
FOAM
```

或悬停在探针上：

```
P1
```

### 4.3 涂选模式（Surface Painting）

这是几何中心模型的核心交互功能，允许用户在 3D 视口中直接在几何体表面上划分边界条件区域，无需手动拆分 STL 文件。

#### 4.3.1 进入与退出

**前提条件**：必须先选中一个几何体 (Body)。

**进入方式**：
- 快捷键 `B` (Brush)
- 右键菜单「涂选编辑」

**进入后**：
- 场景中其他几何体自动变为半透明，仅当前几何体可操作
- 几何体表面按已有 SurfaceZone 着色，未分配区域显示为灰色
- 工具条出现（见 §4.3.2）

**退出方式**：
- 右键单击 → 退出涂选模式，确认修改，更新 SceneModel 中的 surface_zones
- ESC 键 → 取消涂选，丢弃所有修改，恢复进入前状态

#### 4.3.2 工具条

涂选模式下，视口顶部显示简化工具条：

```
┌──────────────────────────────────────────────────────────────┐
│ 当前区域: [LAT - 对流 ▼] [+ 新建区域] │ [↩ 撤销] [↪ 重做] │
└──────────────────────────────────────────────────────────────┘
```

- **当前区域下拉**: 选择要涂选的目标 SurfaceZone
- **新建区域**: 创建一个新 SurfaceZone 并自动设为当前区域
- **撤销/重做**: 回退涂选操作（等同 Ctrl+Z / Ctrl+Y）

#### 4.3.3 画刷工具

涂选模式仅提供**画刷工具**（后续版本可扩展区域生长、框选等）。

**操作方式**：
- 左键按住拖拽 → 画刷覆盖范围内的三角面标记为当前区域
- Ctrl + 左键拖拽 → 擦除（将三角面恢复为"未分配"，label = 0）
- 滚轮 → 调整画刷大小

**画刷覆盖范围**：以屏幕空间像素为单位的圆形区域，最小为单个三角面（点选）。
画刷大小指的是屏幕上的像素半径，不是世界坐标距离——这样在任何缩放级别下操作感一致。

```
VTK 实现:
  鼠标拖拽过程中:
    1. 取鼠标屏幕坐标 (sx, sy)
    2. 遍历画刷屏幕圆内的像素采样点（或使用 vtkHardwareSelector 区域拾取）
       → 得到画刷覆盖的所有 cell_id
    3. 对每个 cell_id，设置 BoundaryLabel[cell_id] = current_zone_label
       (若 Ctrl 按下，则设为 0)
    4. poly.Modified() → mapper 标量着色自动刷新
```

#### 4.3.4 涂选视觉反馈

```
颜色方案:
  未分配          → 浅灰色 (0.7, 0.7, 0.7)，半透明 α=0.5
  T_BOUNDARY      → 蓝色系 (0.2, 0.4, 0.9)    "恒温 — 冷色调"
  H_BOUNDARY      → 红/橙系 (0.9, 0.3, 0.1)    "换热 — 暖色调"
  F_BOUNDARY      → 绿色系 (0.2, 0.8, 0.3)    "能量输入"
  HF_BOUNDARY     → 紫色系 (0.7, 0.2, 0.8)    "组合"
  当前画刷覆盖区域 → 当前颜色 + 脉动高亮            "实时预览"
```

每个 SurfaceZone 的颜色在同一类型内自动分配不同色调（如两个 T_BOUNDARY 区域分别用深蓝和浅蓝），避免相邻区域混淆。

#### 4.3.5 撤销/重做

涂选操作支持完整的撤销/重做栈：

- 每次鼠标释放 (mouseUp) 生成一个撤销点
- 存储内容：完整的 `BoundaryLabel` 数组快照（对于万级三角面，int 数组拷贝成本极低）
- Ctrl+Z / Ctrl+Y 或工具栏按钮触发
- 撤销栈深度：50 步

### 4.4 探针放置与交互

探针是 3D 空间中的标记点，用于指定求解器在何处采样物理量。探针在导航模式下操作，不需要进入涂选模式，也不需要专门的放置子状态。

#### 4.4.1 放置探针

在导航模式下，**双击几何体表面**即可在该位置放置一个探针：

- 双击几何体表面 → 在命中点创建新探针，自动递增名称（P1, P2, P3...）
- 默认类型为体积温度探针（`-p`），可在属性面板中切换

**体积温度探针** (`-p`)：
- 放置在命中点（表面上），用户可在属性面板微调坐标使其位于体内部
- 编辑器提示：「注意：体积探针应在几何体内部，当前在表面上」

**表面温度/通量探针** (`-P` / `-f`)：
- 放置在命中点，自动吸附到最近的三角面中心（表面探针必须在表面上）

#### 4.4.2 探针拖拽

选中探针后，可在 3D 视口中拖拽移动：

- 左键按住探针标记 → 拖拽
- 拖拽时探针沿鼠标投影方向移动（投影到与相机平面平行的平面上）
- 可选约束：Shift + 拖拽 → 仅沿 X/Y/Z 轴移动（最近轴）
- 松开鼠标 → 更新坐标，属性面板实时同步

#### 4.4.3 探针可视化

```
探针标记样式:
  📌 体积温度探针 → 球体 (黄色)，vtkBillboardTextActor3D 显示标签
  📌 表面温度探针 → 圆锥底部贴表面 (橙色)，指示法线方向
  📌 表面通量探针 → 箭头 (青色)，指向法线方向

自适应尺寸:
  标记半径 = 场景包围盒对角线 × 0.01
  保证无论场景尺度如何，探针始终可见且不会过大

选中态:
  标记放大 + 坐标标注
```

#### 4.4.4 探针与几何体的关系提示

编辑器在属性面板中自动计算并显示探针与几何体的关系：

| 提示 | 含义 |
|------|------|
| 在 FOAM 内部 (距表面 0.023m) | 体积探针位置合理 |
| 在 FOAM 表面上 | 表面探针位置合理 |
| 不在任何几何体内 | 体积探针可能无效，警告 |
| 在两个几何体的重叠区 | 提示可能存在歧义 |

检测方法：`vtkSelectEnclosedPoints` 判断点是否在闭合 mesh 内部。

---

## 五、属性面板联动

属性面板根据场景树/3D视口中选中的对象**动态切换**内容。

### 5.1 选中几何体 (Body) 时

```
┌─ 几何体: FOAM ────────────────────────────────┐
│                                                │
│ ── 体积属性 ──                                 │
│ 类型: [SOLID ▼]                               │
│ 材质: [铝 6061 ▼] [从库选择...]               │
│ 导热系数 λ: [237.0] W/m/K                     │
│ 密度 ρ: [2700.0] kg/m³                        │
│ 比热容 cp: [890.0] J/kg/K                     │
│ 随机行走步长 δ: [AUTO ▼] / [0.0002]           │
│ 初始温度: [750.0] K                            │
│ 施加温度: [UNKNOWN ▼] / [     ] K             │
│ 体积热源: [0.0] W/m³                          │
│ 法线朝向: [FRONT ▼]                           │
│   FRONT = 材质在法线正方向一侧                  │
│   BACK  = 材质在法线反方向一侧                  │
│   BOTH  = 材质占据两侧（实心体）               │
│                                                │
│ ── 几何信息 ──                                 │
│ STL 文件: S_porous.stl [更换...]               │
│ 三角面数: 1,204                                │
│ 包围盒: 0.10 × 0.10 × 0.10 m                  │
│ 表面积: 0.06 m²                                │
│ 闭合: ✅                                       │
│                                                │
│ ── 表面区域概览 ──                              │
│ ┌─────────────────────────────────────────┐    │
│ │ 区域      类型       三角面   占比       │    │
│ │ LAT       对流       780     64.8%      │    │
│ │ T0        固定温度   212     17.6%      │    │
│ │ T1        固定温度   212     17.6%      │    │
│ │ ─────────────────────────────────       │    │
│ │ 合计                 1,204   100% ✅    │    │
│ └─────────────────────────────────────────┘    │
│                                                │
│ [🎨 编辑表面区域]                               │
└────────────────────────────────────────────────┘
```

### 5.2 选中表面区域 (SurfaceZone) 时

```
┌─ 表面区域: LAT ───────────────────────────────┐
│                                                │
│ 归属几何体: FOAM (点击跳转)                     │
│                                                │
│ ── 边界条件 ──                                 │
│ 类型: [对流+辐射 (H_BOUNDARY) ▼]              │
│ ┌─────────────────────────────────────────┐    │
│ │ 参考温度 Tref: [300.0] K                │    │
│ │ 发射率 ε: [0.9] ━━━━━━━━━●━  0~1       │    │
│ │ 镜面分数:  [0.5] ━━━━━●━━━━━  0~1       │    │
│ │ 对流系数 hc: [0.0] W/m²/K              │    │
│ │ 环境温度 T_env: [300.0] K               │    │
│ └─────────────────────────────────────────┘    │
│                                                │
│ ── 区域信息 ──                                 │
│ 来源: 导入 STL (B_lateral.stl)                 │
│ 三角面数: 780                                   │
│ 占母体: 64.8%                                   │
│ 显示颜色: [🔴] [修改...]                       │
│                                                │
└────────────────────────────────────────────────┘
```

### 5.3 切换边界类型时的参数变化

当用户在属性面板中切换「类型」下拉框时，参数区域动态变化：

| 切换到类型 | 显示的参数 |
|-----------|-----------|
| 固定温度 (T_BOUNDARY) | 仅：温度 T |
| 对流+辐射 (H_BOUNDARY) | Tref、ε、镜面分数、hc、T_env |
| 热通量 (F_BOUNDARY) | 仅：通量 flux (W/m²) |
| 组合 (HF_BOUNDARY) | H_BOUNDARY 全部参数 + flux |

### 5.4 选中探针 (Probe) 时

```
┌─ 探针: P1 ─────────────────────────────────────┐
│                                                │
│ ── 探针类型 ──                                  │
│ 类型: [体积温度探针 ▼]                          │
│   体积温度探针  → stardis -p X,Y,Z[,T]         │
│   表面温度探针  → stardis -P X,Y,Z,SIDE        │
│   表面通量探针  → stardis -f X,Y,Z             │
│                                                │
│ ── 位置 ──                                     │
│ X: [0.500]  Y: [0.500]  Z: [0.500]            │
│ [从3D视口拾取位置]                              │
│                                                │
│ ── 类型专属参数 ──                              │
│ 采样时刻: [INF ▼] / [100.0] s                  │
│   INF = 稳态, 数值 = 瞬态指定时刻              │
│                                                │
│ ── 显示 ──                                     │
│ 标签: [P1]                                     │
│ 颜色: [🟡] [修改...]                           │
│ 显示坐标轴: [✓]                                │
│                                                │
│ ── 所在位置信息 ──                              │
│ 最近几何体: FOAM (距表面 0.023m)                │
│ 在几何体内部: ✅                                │
│                                                │
└────────────────────────────────────────────────┘
```

**类型切换时参数变化**：

| 类型 | 显示参数 |
|------|----------|
| 体积温度探针 | 位置 (x,y,z) + 采样时刻 (float \| INF) |
| 表面温度探针 | 位置 (x,y,z) + 面标识 (SIDE) |
| 表面通量探针 | 仅位置 (x,y,z) |

### 5.5 选中连接 (Connection) 时

```
┌─ 连接: CONTACT_1 ─────────────────────────────┐
│                                                │
│ 类型: [SOLID_SOLID ▼]                         │
│ 几何体 A: [WALL ▼]                            │
│ 几何体 B: [INSULATOR ▼]                       │
│ 接触热阻: [0.001] m²·K/W                      │
│ 界面 STL: contact.stl [更换...]               │
│                                                │
└────────────────────────────────────────────────┘
```

### 5.6 选中摄像机 (IRCamera) 时

```
┌─ 摄像机: Camera1 ──────────────────────────────┐
│                                                │
│ ── 空间参数 ──                                 │
│ 位置 pos: X [1.000] Y [1.000] Z [1.000]       │
│ 目标 tgt: X [0.000] Y [0.000] Z [0.000]       │
│ 向上 up:  X [0.000] Y [0.000] Z [1.000]       │
│ FOV: [30.0] °                                  │
│                                                │
│ ── 渲染参数 ──                                 │
│ SPP (每像素采样): [32]                          │
│ 分辨率: [320] × [320]                          │
│                                                │
│ [使用当前视角] ← 从 3D 视口复制相机位姿        │
│                                                │
└────────────────────────────────────────────────┘
```

**「使用当前视角」按钮**：将 3D 视口当前相机的 position、target、up 填入摄像机参数，方便用户在视口中调整好角度后一键同步。

### 5.7 选中光源 (SceneLight) 时

属性面板根据光源类型动态显示不同字段：

**DEFAULT（默认光源）**

```
┌─ 光源: DefaultLight [默认光源] ────────────────┐
│                                                │
│ 名称: [DefaultLight]                           │
│ 类型: 默认光源                                  │
│ 位置: X [1.000] Y [1.000] Z [1.000]           │
│ 颜色: R [1.0] G [1.0] B [1.0]                 │
│                                                │
└────────────────────────────────────────────────┘
```

**SPHERICAL_SOURCE（常量球面源）**

```
┌─ 光源: SphericalSource1 [常量球面源] ──────────┐
│                                                │
│ 名称: [SphericalSource1]                       │
│ 类型: 常量球面源                                │
│ 位置: X [1.000] Y [2.000] Z [3.000]           │
│ 半径: [0.500] m                                │
│ 功率: [100.0] W                                │
│ 漫射辐亮度: [50.5] W/m²/sr                     │
│ 颜色: R [1.0] G [1.0] B [1.0]                 │
│                                                │
└────────────────────────────────────────────────┘
```

**SPHERICAL_SOURCE_PROG（可编程球面源）**

```
┌─ 光源: SphericalSourceProg1 [可编程球面源] ────┐
│                                                │
│ 名称: SphericalSourceProg1 (只读)              │
│ 类型: 可编程球面源                              │
│ 原始定义: [SPHERICAL_SOURCE_PROG 0.3 ...]      │
│           (只读，原样保存)                       │
│                                                │
└────────────────────────────────────────────────┘
```

**字段显隐规则**：

| 字段 | DEFAULT | SPHERICAL_SOURCE | SPHERICAL_SOURCE_PROG |
|------|---------|------------------|----------------------|
| 名称 | 可编辑 | 可编辑 | 只读 |
| 位置 | ✓ | ✓ | — |
| 半径/功率/辐亮度 | — | ✓ | — |
| 颜色 | ✓ | ✓ | — |
| 原始定义 | — | — | ✓ (只读) |

### 5.8 选中环境光照时

```
┌─ 环境基本光照 ─────────────────────────────────┐
│                                                │
│ 环境基本光照始终存在，不受其他光源影响。          │
│                                                │
│ 强度: [0.15] ← 范围 0.0 ~ 1.0                 │
│                                                │
└────────────────────────────────────────────────┘
```

通过 `actor.GetProperty().SetAmbient(intensity)` 施加到所有几何体 Actor。

### 5.9 选中全局设置时

```
┌─ 全局设置 ────────────────────────────────────┐
│                                                │
│ 环境辐射温度 T_ambient: [680.0] K              │
│ 线性化参考温度 T_reference: [800.0] K          │
│ 几何缩放 SCALE: [1.0]                         │
│   1.0 = 米, 0.001 = 毫米                      │
│                                                │
│ ── 场景统计 ──                                 │
│ 几何体数: 1                                    │
│ 表面区域数: 3                                   │
│ 连接数: 0                                      │
│ 总三角面数: 1,204                              │
│                                                │
└────────────────────────────────────────────────┘
```

---

## 六、场景树 ↔ 3D 视口 双向联动协议

所有联动通过 Qt 信号/槽机制实现，场景树和视口不直接引用对方。

### 6.1 信号定义

```python
# 场景树发出的信号
class SceneTreePanel(QTreeWidget):
    body_selected      = pyqtSignal(str)         # body name
    zone_selected      = pyqtSignal(str, str)    # body name, zone name
    connection_selected = pyqtSignal(str)         # connection name
    probe_selected     = pyqtSignal(str)         # probe name
    global_selected    = pyqtSignal()
    camera_selected    = pyqtSignal(str)         # camera name
    light_selected     = pyqtSignal(str)         # light name
    ambient_selected   = pyqtSignal()            # 环境光照节点被选中
    selection_cleared  = pyqtSignal()

    # 右键操作信号
    request_add_default_light        = pyqtSignal()   # 添加默认光源
    request_add_spherical_source     = pyqtSignal()   # 添加常量球面源
    request_add_spherical_source_prog = pyqtSignal()  # 添加可编程球面源
    request_delete_light             = pyqtSignal(str) # 删除光源

# 3D 视口发出的信号
class SceneViewport(QVTKRenderWindowInteractor):
    body_picked        = pyqtSignal(str)         # body name (左键单击)
    probe_picked       = pyqtSignal(str)         # probe name (左键单击)
    nothing_picked     = pyqtSignal()             # 点击空白
    paint_changed      = pyqtSignal(str, dict)   # body name, {zone_name: cell_ids}
    probe_placed       = pyqtSignal(str, float, float, float)  # body name, x, y, z (双击几何体)

# 属性面板发出的信号
class PropertyPanel(QWidget):
    property_changed   = pyqtSignal(str, str, object)  # body/zone name, property key, new value
    boundary_type_changed = pyqtSignal(str, str, str)   # body name, zone name, new type
```

### 6.2 联动矩阵

| 触发事件 | 场景树响应 | 3D 视口响应 | 属性面板响应 |
|---------|-----------|------------|------------|
| 树中单击 Body | 高亮该节点 | Silhouette 轮廓线高亮 (黄色线宽3) | 显示体积属性 |
| 树中单击 Zone | 高亮该节点 | Silhouette 轮廓线 + LUT 区域着色高亮 (选中区域原色，其余暗灰) | 显示边界参数 |
| 树中勾选可见性 | 复选框状态更新 | 对应 actor 显示/隐藏 | — |
| 3D 中单击几何体 | 自动展开并选中对应节点 | Silhouette 轮廓线高亮 | 显示体积属性 |
| 3D 中单击探针 | 选中对应 Probe 节点 | 探针标记放大 | 显示探针参数 |
| 3D 中双击几何体 | 在探针组下创建新节点 | 在命中点显示探针标记 | 显示新探针参数 |
| 3D 中拖拽探针 | — | 探针跟随移动 | 实时更新坐标值 |
| 3D 中单击空白 | 取消选中 | 所有对象恢复正常渲染 | 清空或显示全局 |
| 属性面板修改探针坐标 | — | 探针标记移动到新位置 | — |
| 属性面板修改参数 | — | 若影响外观则刷新 | — |
| 属性面板改边界类型 | 更新节点图标/文字 | 更新区域颜色 | 切换参数面板 |
| 树中单击光源 | 高亮该节点 | — | 显示光源参数 (按类型动态显隐字段) |
| 树中单击环境光照 | 高亮该节点 | — | 显示环境光照强度编辑器 |
| 属性面板修改光源参数 | 刷新光源显示文字 | VTK 光源同步更新 | — |
| 属性面板修改环境光照强度 | 刷新强度数值显示 | 所有 Actor 的 Ambient 同步更新 | — |
| 右键光源组→添加 | 创建新光源节点 | VTK 添加对应光源 | 显示新光源参数 |
| 右键光源→删除 | 移除节点，可能触发 ensure_default | VTK 移除对应光源 | 清空属性面板 |

---

## 七、VTK 渲染架构

### 7.1 每个几何体的 Actor 结构

```
Body "FOAM" 的渲染组件:
  │
  ├── body_actor (主体)
  │   ├── vtkPolyData ← vtkSTLReader
  │   │   └── CellData: "BoundaryLabel" (vtkIntArray)
  │   ├── vtkPolyDataMapper
  │   │   ├── ScalarMode = CellData
  │   │   ├── ColorMode = MapScalars
  │   │   └── LookupTable = zone_lut (选中区域时临时替换为高亮 LUT)
  │   └── vtkActor
  │       └── 属性: 默认不透明
  │
  └── silhouette_actor (选中时动态创建/销毁, 导航模式专属)
      ├── vtkPolyDataSilhouette
      │   ├── InputData = body_polydata
      │   └── Camera = renderer.GetActiveCamera() (自动跟随视角)
      ├── vtkPolyDataMapper
      └── vtkActor
          ├── Color = (1.0, 1.0, 0.0)  # 黄色
          └── LineWidth = 3.0

选中效果 (导航模式):
  Body 选中 → Silhouette 轮廓线高亮
  Zone 选中 → Silhouette 轮廓线 + LUT 临时替换 (选中区域原色, 其余暗灰)
  取消选中 → 移除 Silhouette, 恢复原始 LUT
涂选模式下不显示高亮效果。

Probe "P1" 的渲染组件:
  │
  ├── marker_actor (探针标记)
  │   ├── vtkSphereSource (半径自适应场景尺度)
  │   └── vtkActor (颜色=探针颜色, 始终在最前层渲染)
  │
  ├── label_actor (文字标签)
  │   ├── vtkBillboardTextActor3D
  │   └── 显示: "P1 (0.5, 0.5, 0.5)"
  │
  └── axis_actor (可选: 局部坐标轴)
      └── vtkAxesActor (短轴, 帮助判断探针朝向)
```

### 7.2 颜色查找表 (LookupTable) 管理

```python
class ZoneColorManager:
    """为每个 Body 管理一个 LookupTable"""
    
    # BoundaryLabel 值定义:
    #   0 = 未分配 → 灰色半透明
    #   1, 2, 3, ... = 各 SurfaceZone 的索引

    # 类型 → 基础色调
    TYPE_BASE_HUES = {
        'T_BOUNDARY':  0.60,   # 蓝色系 (H=216°)
        'H_BOUNDARY':  0.05,   # 红/橙系 (H=18°)
        'F_BOUNDARY':  0.33,   # 绿色系 (H=120°)
        'HF_BOUNDARY': 0.80,   # 紫色系 (H=288°)
    }
    
    def build_lut(self, zones: List[SurfaceZone]) -> vtkLookupTable:
        """
        根据当前 body 的 surface_zones 构建颜色映射。
        同类型的多个 zone 在同一色调内偏移明度/饱和度以区分。
        """
        lut = vtkLookupTable()
        lut.SetNumberOfTableValues(len(zones) + 1)
        lut.SetTableValue(0, 0.7, 0.7, 0.7, 0.5)  # 未分配: 灰色半透明
        
        for i, zone in enumerate(zones, start=1):
            h = self.TYPE_BASE_HUES[zone.boundary.type]
            # 同类型内偏移: 按索引微调色调
            ...
            lut.SetTableValue(i, r, g, b, 1.0)
        
        lut.Build()
        return lut
```

### 7.3 涂选时的 Cell 拾取实现（屏幕空间画刷）

```python
class SurfacePainter:
    """涂选模式的核心逻辑 — 基于屏幕空间画刷"""
    
    def __init__(self, body_polydata: vtkPolyData, renderer: vtkRenderer):
        self.poly = body_polydata
        self.renderer = renderer
        self.labels = body_polydata.GetCellData().GetArray("BoundaryLabel")
        
        # 撤销栈
        self.undo_stack: List[vtkIntArray] = []
        self.redo_stack: List[vtkIntArray] = []
    
    def paint_at_screen(self, screen_x: int, screen_y: int,
                        brush_radius_px: int, label: int):
        """
        以屏幕坐标 (screen_x, screen_y) 为中心、brush_radius_px 像素
        半径内的所有可见 cell 上涂 label。
        
        使用 vtkHardwareSelector 进行区域拾取，精确获取画刷圆内的 cell。
        """
        selector = vtkHardwareSelector()
        selector.SetRenderer(self.renderer)
        # 画刷圆的外接矩形
        x0 = screen_x - brush_radius_px
        y0 = screen_y - brush_radius_px
        x1 = screen_x + brush_radius_px
        y1 = screen_y + brush_radius_px
        selector.SetArea(x0, y0, x1, y1)
        selector.SetFieldAssociation(vtkDataObject.FIELD_ASSOCIATION_CELLS)
        result = selector.Select()
        
        for node_idx in range(result.GetNumberOfNodes()):
            node = result.GetNode(node_idx)
            if node.GetProperties().Get(vtkSelectionNode.PROP()) != self.body_actor:
                continue
            sel_ids = node.GetSelectionList()
            for i in range(sel_ids.GetNumberOfTuples()):
                cell_id = sel_ids.GetValue(i)
                # 可选: 进一步检查 cell 中心的屏幕投影是否在圆内
                self.labels.SetValue(cell_id, label)
        
        self.poly.Modified()  # 触发渲染更新
    
    def save_undo_point(self):
        """保存当前状态到撤销栈"""
        snapshot = vtkIntArray()
        snapshot.DeepCopy(self.labels)
        self.undo_stack.append(snapshot)
        self.redo_stack.clear()
    
    def undo(self):
        if not self.undo_stack:
            return
        current = vtkIntArray()
        current.DeepCopy(self.labels)
        self.redo_stack.append(current)
        prev = self.undo_stack.pop()
        self.labels.DeepCopy(prev)
        self.poly.Modified()
    
    def redo(self):
        if not self.redo_stack:
            return
        current = vtkIntArray()
        current.DeepCopy(self.labels)
        self.undo_stack.append(current)
        nxt = self.redo_stack.pop()
        self.labels.DeepCopy(nxt)
        self.poly.Modified()
```

### 7.4 涂选区域导出为 STL

```python
def export_zone_stl(body_poly: vtkPolyData, label_value: int, output_path: str):
    """将指定 label 的三角面提取并导出为 STL"""
    
    threshold = vtkThreshold()
    threshold.SetInputData(body_poly)
    threshold.SetInputArrayToProcess(0, 0, 0,
        vtkDataObject.FIELD_ASSOCIATION_CELLS, "BoundaryLabel")
    threshold.SetLowerThreshold(label_value)
    threshold.SetUpperThreshold(label_value)
    threshold.Update()
    
    # vtkThreshold 输出 UnstructuredGrid，需转回 PolyData
    surface = vtkDataSetSurfaceFilter()
    surface.SetInputConnection(threshold.GetOutputPort())
    surface.Update()
    
    writer = vtkSTLWriter()
    writer.SetFileName(output_path)
    writer.SetInputConnection(surface.GetOutputPort())
    writer.SetFileTypeToBinary()
    writer.Write()
```

---

> **注**: 场景导入（从 stardis `.txt` 反向构建几何中心模型）的流程已在 §2.2.2 反序列化中详述，此处不再重复。

---

## 八、从零新建场景的完整工作流

```
1. 新建空场景
   → 全局设置默认值: TRAD 300 300, SCALE 1.0
   → 场景树仅显示「全局设置」节点

2. 导入几何体
   → 文件对话框 / 拖拽 STL 进入视口
   → 创建 Body 节点，type 默认 SOLID
   → 几何体在 3D 视口中显示为灰色（无边界条件）

3. 设置体积属性
   → 选中几何体 → 属性面板
   → 选择材质（从库或手动输入 λ/ρ/cp）
   → 设置温度、法线朝向等

4. 划分表面区域（两种方式）

   方式 A: 导入已有边界 STL
   → 右键几何体 →「导入边界 STL」→ 选择 B_*.stl
   → 自动创建 SurfaceZone，着色显示
   → 属性面板设置边界类型和参数

   方式 B: 涂选模式
   → 选中几何体 → 按 B 进入涂选模式
   → 新建区域 "T0"，选择类型「固定温度」
   → 用画刷涂选底面
   → 新建区域 "T1"，选择类型「固定温度」
   → 画刷涂选顶面
   → 新建区域 "LAT"，选择类型「对流」
   → 画刷涂选剩余所有面
   → 检查覆盖率 100%
   → 右键退出涂选模式（确认）

5. 添加探针 (可选)
   → 在 3D 视口中双击几何体表面 → 自动放置探针
   → 选择探针类型（体积温度/表面温度/表面通量）
   → 设置参数（时刻/面标识）
   → 可拖拽调整位置，属性面板实时更新坐标

6. 添加连接 (可选)
   → 右键「连接」节点 →「新建连接」
   → 选择两个几何体 + 导入界面 STL

7. 验证 → 保存
   → 编辑器序列化:
     Body → SOLID/FLUID 行
     SurfaceZone(ImportedSTL) → BOUNDARY 行 (引用原 STL)
     SurfaceZone(PaintedRegion) → 导出新 STL → BOUNDARY 行
     Connection → CONNECTION 行
     Probe → 不写入 scene.txt (探针属于任务域参数)
            → 保存到编辑器项目文件 (.stardis_project.json)
            → 提交求解时由任务面板读取并生成 CLI 参数
```

> **注意**：探针不属于 stardis 场景文件 (`.txt`)，而是求解器命令行参数 (`-p`/`-P`/`-f`)。
> 但它们的**空间位置**与场景几何强相关，因此在场景树中统一管理、在 3D 视口中可视化是合理的。
> 探针数据持久化在编辑器项目文件中，提交求解任务时由任务面板自动读取。

---

## 九、性能考量

### 9.1 大模型优化

| 三角面规模 | 措施 |
|-----------|------|
| < 10K | 无需特殊处理，一切流畅 |
| 10K ~ 100K | 涂选时使用 `vtkCellLocator` (O(log n) 查询) |
| 100K ~ 1M | 考虑 LOD 降低非焦点几何体的细节、使用硬件选择器 |
| > 1M | 涂选时仅对可见面操作 (视锥裁剪)、分块加载 |

### 9.2 内存管理

- `BoundaryLabel` 数组：每个三角面 1 个 int (4 字节)，100 万面 = 4MB，完全可接受
- 撤销栈：每个快照 4MB (100 万面)，50 步 = 200MB → 可设上限，超过时丢弃最旧的
- 多个几何体同时加载：每个 body 独立的 polydata + actor，VTK 数据共享机制自动优化

---

## 十、实施分步

本功能系统建议按以下顺序增量实现：

| 步骤 | 内容 | 交付验证 |
|------|------|---------|
| **S1** | SceneModel 数据模型 (几何中心版) | 单元测试：创建/序列化/反序列化 |
| **S2** | 场景树面板 (只读) | 从 SceneModel 渲染出正确的树结构 |
| **S3** | 多对象 VTK 渲染 + 按 BoundaryLabel 着色 | 加载 porous 场景，表面按区域着色 |
| **S4** | 场景树 ↔ 视口双向选择联动 | 点树→高亮3D, 点3D→树同步 |
| **S5** | 属性面板动态切换 | 选中不同对象类型，面板内容正确切换 |
| **S6** | 涂选模式: 画刷 + 撤销/重做 | 屏幕空间画刷涂色 + Ctrl 擦除 + Ctrl+Z 撤销 |
| **S7** | 涂选区域导出为 STL + 场景保存 | 涂选 → 保存 → stardis 能正确读取 |
| **S8** | 从 .txt 导入 + 几何匹配 | 导入现有场景 → 正确显示几何中心树结构 |
| **S9** | 覆盖率检查 + 视觉提示 | 未覆盖区域灰色显示，覆盖率数值正确 |
| **S10** | 探针系统: 双击放置 + 拖拽 + 属性面板 | 双击几何体放置探针，拖拽移动，属性面板编辑参数 |
| **S11** | 探针与任务面板联动 | 探针列表自动填充到求解任务的 -p/-P/-f 参数 |
