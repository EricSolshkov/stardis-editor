# StardisEditor v2.0 — 完整需求规格

## 核心理念

**两个独立域**：
- **场景域** = 物理世界描述 (对应 `.txt` 文件) — "世界长什么样"
- **任务域** = 求解器调用参数 (对应 `.ps1`/`.sh` 脚本) — "要算什么"

这两个域在 stardis 命令行中通过 `-M scene.txt` + 其他参数组合，但在编辑器中应**分开管理**。

---

## 一、场景域：场景管理系统

### 1.1 数据模型 (`SceneModel`)

```
SceneModel
├── global_settings
│   ├── trad: (T_ambient, T_reference)    # TRAD 指令
│   └── scale: float                       # SCALE 指令
├── media: List[Medium]
│   ├── SolidMedium                        # SOLID 指令
│   │   ├── name: str                      # 唯一标识
│   │   ├── material: MaterialRef          # 引用材质库或内联定义
│   │   │   ├── conductivity: float        # λ (W/m/K)
│   │   │   ├── density: float             # ρ (kg/m³)
│   │   │   └── specific_heat: float       # cp (J/kg/K)
│   │   ├── delta: float | "AUTO"          # 随机行走步长
│   │   ├── initial_temp: float            # 初始温度 (K)
│   │   ├── imposed_temp: float | "UNKNOWN"# 施加温度
│   │   ├── volumetric_power: float        # 体积热源 (W/m³)
│   │   ├── side: FRONT | BACK | BOTH      # 法线朝向
│   │   └── stl_files: List[str]           # 几何文件路径
│   └── FluidMedium                        # FLUID 指令
│       ├── name, density, specific_heat
│       ├── initial_temp, imposed_temp
│       ├── side, stl_files
│       └── (无 conductivity/delta/power)
├── boundaries: List[Boundary]
│   ├── TemperatureBoundary                # T_BOUNDARY_FOR_SOLID
│   │   ├── name, temperature, stl_files
│   ├── ConvectionBoundary                 # H_BOUNDARY_FOR_SOLID
│   │   ├── name, Tref, emissivity, specular_fraction
│   │   ├── hc, T_env, stl_files
│   ├── FluxBoundary                       # F_BOUNDARY_FOR_SOLID
│   │   ├── name, flux, stl_files
│   └── CombinedBoundary                   # HF_BOUNDARY_FOR_SOLID
│       └── (ConvectionBoundary 字段 + flux)
├── connections: List[Connection]
│   ├── SolidFluidConnection               # SOLID_FLUID_CONNECTION
│   └── SolidSolidConnection               # SOLID_SOLID_CONNECTION
└── comments: List[(line_no, text)]        # 保留原始注释用于回写
```

### 1.2 场景解析器 (`SceneParser`)

| 功能 | 说明 |
|------|------|
| 解析 `.txt` → `SceneModel` | 逐行 tokenize，按关键字分发解析 |
| 路径解析 | STL 路径相对于场景文件目录 |
| 注释保留 | 记录 `#` 注释的位置和内容，回写时还原 |
| 验证 | 名称唯一、imposed_temp == initial_temp 一致性、属性 > 0 |
| 容错 | 未知行发出警告但不中断，记录到解析报告 |

### 1.3 场景生成器 (`SceneWriter`)

| 功能 | 说明 |
|------|------|
| `SceneModel` → `.txt` | 按 TRAD → SCALE → #medium → SOLID/FLUID → #boundaries → 边界 → 连接 的顺序输出 |
| 保存 / 另存为 | 支持指定输出路径 |
| 路径处理 | STL 路径转为相对于输出文件的相对路径 |
| 完整性校验 | 生成前检查：至少一个介质、STL 文件存在性、物理量范围合理性 |
| 格式化 | 列对齐、分节注释，保持可读性 |

### 1.4 从零新建场景

支持空场景起步的完整创建流程：

```
新建空场景
  → 设置全局参数 (TRAD / SCALE)
  → 添加介质 (导入 STL + 赋材质 + 设热属性)
  → 添加边界条件 (选择类型 + 导入边界 STL + 设参数)
  → 添加连接 (可选)
  → 验证 → 保存
```

### 1.5 外部模型导入

| 格式 | 处理方式 |
|------|----------|
| `.stl` | 直接加载 |
| `.obj` | VTK 内置 `vtkOBJReader` 读取 → 导出为 STL |
| `.ply` | VTK 内置 `vtkPLYReader` 读取 → 导出为 STL |
| 其他 | 视 VTK 支持情况，提示用户手动转换 |

### 1.6 场景有效性验证 (Scene Validation)

场景验证是场景管理的内置功能，利用 stardis 自身的 `-d` (dump) 模式执行几何与属性一致性检查，确保编辑器的验证结果与求解器完全一致。

#### 1.6.1 stardis 内建的 4 类验证

| 检查类型 | 检测内容 | stardis 行为 |
|---------|---------|-------------|
| **退化三角形** | 面积为零的病态三角形 | 自动移除 + 警告，列出三角形 ID |
| **合并冲突 (Merge Conflict)** | 不同 STL 的三角形在共享边上存在介质归属冲突 (共边一致性 / conformal mesh) | 报告冲突三角形数量 |
| **重叠三角形 (Overlapping)** | 三角形之间的空间重叠 / 几何体交叉 | 报告重叠三角形数量 |
| **属性冲突 (Property Conflict)** | 边界条件与介质类型不匹配 (27 种错误码) | 报告冲突三角形数量 |

#### 1.6.2 调用方式

通过 stardis `-d` 模式 + `-V 3` 高详细度执行验证：

```bash
stardis -V 3 -M scene.txt -d output_base
```

此命令**不执行计算**，仅做几何加载 + 验证 + 导出，且**始终返回 EXIT_SUCCESS**，不会因错误而中断。

#### 1.6.3 stardis 输出的验证产物

**stderr 消息** (正则匹配解析)：
```
"File '<file>' included N degenerated triangles (removed)"
"Merge conflicts found reading file '<file>' (N triangles)."
"Scene contains N overlapping triangles."
"Property conflicts found in the model (N triangles)."
"Model contains hole(s)."
```

**文件输出** (问题图元精确定位)：

| 输出文件 | 内容 |
|---------|------|
| `<base>.vtk` | 完整几何，每个三角形携带标量场 |
| `<base>_merge_conflits.obj` | 仅包含有合并冲突的三角形 |
| `<base>_overlapping_triangles.obj` | 仅包含重叠的三角形 |
| `<base>_property_conflits.obj` | 仅包含属性冲突的三角形 |

**VTK 标量场** (逐三角形标记)：

| 标量字段 | 含义 |
|---------|------|
| `User_ID` | 映射回原始 STL 文件中的三角形索引 |
| `Unique_ID` | 去重后的全局唯一 ID |
| `Merge_conflict` | 0 = 正常，1 = 有合并冲突 |
| `Overlapping_triangles` | 0 = 正常，1 = 有重叠 |
| `Property_conflict` | 0 = 正常，1~24 = 具体冲突类型编码 |

#### 1.6.4 编辑器集成流程

```
用户点击「验证场景」/ 保存前自动触发
  │
  ├─ 1. SceneWriter 生成临时 scene.txt 到系统 temp 目录
  │
  ├─ 2. QProcess 调用: stardis -V 3 -M temp_scene.txt -d temp_output
  │
  ├─ 3. 解析 stderr: 正则提取各类错误的三角形数量
  │
  ├─ 4. 解析输出文件 (定位具体问题图元):
  │     ├─ vtkUnstructuredGridReader 读取 .vtk 标量场
  │     ├─ vtkOBJReader 加载 *_merge_conflits.obj
  │     ├─ vtkOBJReader 加载 *_overlapping_triangles.obj
  │     └─ vtkOBJReader 加载 *_property_conflits.obj
  │
  ├─ 5. 3D 视口可视化:
  │     ├─ 合并冲突三角形 → 红色叠加层
  │     ├─ 重叠三角形 → 橙色叠加层
  │     └─ 属性冲突三角形 → 紫色叠加层
  │
  ├─ 6. 验证报告面板:
  │     ├─ ✓ 退化三角形: 0 (已自动移除 2 个)
  │     ├─ ✗ 合并冲突: 15 个三角形 (S_porous.stl ↔ B_T0.stl)
  │     ├─ ✗ 重叠: 3 个三角形
  │     ├─ ✓ 属性一致性: 通过
  │     └─ ⚠ 模型包含孔洞
  │     点击某条 → 视口飞到对应三角形位置并高亮
  │
  └─ 7. 清理临时文件
```

#### 1.6.5 验证触发时机

| 时机 | 行为 |
|------|------|
| 用户手动点击「验证场景」按钮 | 完整验证 + 详细报告 |
| 保存场景前 | 自动验证，有错误时警告但不阻止保存 |
| 提交求解任务前 | 自动验证，有错误时阻止提交 (因 stardis 计算模式遇到几何错误会 EXIT_FAILURE) |
| 导入新 STL / 修改边界类型后 | 可选：轻量级本地检查 (名称唯一性、属性范围)，不调用 stardis |

#### 1.6.6 设计优势

- **零重复实现** — 几何验证逻辑完全委托给 stardis，不需要在编辑器中重写
- **结果一致性** — 编辑器验证结果与实际求解时的检查 100% 一致
- **精确到三角形** — 通过 VTK 标量场和 OBJ 导出，可定位每一个问题图元并在 3D 视口中高亮
- **不阻塞编辑** — dump 模式始终成功返回，错误仅作为报告呈现，用户可继续编辑修复

---

## 二、场景域：VTK 场景视口

### 2.1 多对象渲染

| 功能 | 说明 |
|------|------|
| 按角色着色 | 介质用暖色系 (红/橙/黄)，边界用冷色系 (蓝/绿/青)，连接用紫色 |
| 透明度控制 | 每个对象独立调节，支持全局「X-Ray 模式」半透明 |
| 可见性开关 | 场景树中逐项控制显隐 |
| 选择高亮 | 点击 3D 对象或场景树条目 → 高亮边框 + 属性面板联动 |
| 统计信息 | 三角形数、包围盒尺寸、体积(若闭合) |

### 2.2 摄像机控制 (IR 渲染模式)

| 功能 | 说明 |
|------|------|
| 可视化摄像机锥体 | 在 3D 场景中绘制半透明 frustum 表示渲染视野 |
| 交互式拖拽 | 拖动锥体顶点调整 pos，拖动底面调整 tgt |
| 参数面板双向同步 | 修改数值 → 锥体更新；拖锥体 → 数值更新 |
| 「使用当前视角」按钮 | 将 VTK 交互视角一键设为 IR 摄像机参数 |
| FOV 实时预览 | 调整 FOV 滑块时锥体实时变化 |

### 2.3 场景树面板 (`SceneTreePanel`)

```
场景树
├── 🌐 全局设置
│   ├── TRAD: 680, 800
│   └── SCALE: 0.001
├── 📦 介质 (3)
│   ├── FOAM [SOLID] — solid.stl
│   ├── PLATE [SOLID] — plate.stl
│   └── AIR [FLUID] — air_volume.stl
├── 🔲 边界条件 (3)
│   ├── LAT [H_BOUNDARY] — B_lateral.stl
│   ├── T0 [T_BOUNDARY] — B_T0.stl
│   └── T1 [T_BOUNDARY] — B_T1.stl
├── 🔗 连接 (0)
└── 📷 摄像机 (IR 模式)
    └── Camera1: pos=(0.05, 0.01, 0) → tgt=(0,0,0)
```

- 右键菜单：添加/删除/复制/重命名
- 拖拽排序
- 单击 → 属性面板显示该项详情，3D 视口高亮该对象
- 双击 → 进入重命名

### 2.4 属性编辑面板 (`PropertyPanel`)

根据场景树中选中的对象类型**动态切换**显示内容：

**选中 SOLID 时显示**：
```
┌─ 介质属性: FOAM ──────────────┐
│ 材质: [铝 6061 ▼] [从库选择] │  ← 材质库下拉 或 自定义
│ λ: [237.0] W/m/K              │
│ ρ: [2700.0] kg/m³             │
│ cp: [890.0] J/kg/K            │
│ 步长δ: [AUTO ▼] / [0.02] m   │
│ 初始温度: [800.0] K           │
│ 施加温度: [UNKNOWN ▼] / [K]  │
│ 体积功率: [0.0] W/m³          │
│ 法线朝向: [FRONT ▼]          │
│ STL文件: solid.stl [更换...]  │
│ 三角面数: 1,204               │
│ 包围盒: 0.1 x 0.1 x 0.1 m   │
└───────────────────────────────┘
```

**选中 H_BOUNDARY 时显示**：
```
┌─ 边界条件: LAT ───────────────┐
│ 类型: [H_BOUNDARY ▼]         │  ← 可切换类型
│ 参考温度 Tref: [300.0] K     │
│ 发射率 ε: [0.9] ━━━━━━━━●━  │  ← 0~1 滑块
│ 镜面分数: [0.5] ━━━━━●━━━━━  │  ← 0~1 滑块
│ 对流系数 hc: [10.0] W/m²/K   │
│ 环境温度: [300.0] K           │
│ STL文件: B_lateral.stl        │
└───────────────────────────────┘
```

**选中全局设置时显示**：
```
┌─ 全局设置 ────────────────────┐
│ 环境辐射温度: [680.0] K       │
│ 线性化参考温度: [800.0] K     │
│ 几何缩放: [1.0]  (1=m)       │
│                               │
│ ── 场景统计 ──                │
│ 介质数: 3                     │
│ 边界数: 3                     │
│ 连接数: 0                     │
│ 总三角面数: 8,542             │
└───────────────────────────────┘
```

---

## 三、材质数据库

### 3.1 材质模型

```python
Material:
    name: str               # "铝 6061-T6"
    category: str           # "金属" / "绝缘体" / "半导体" / "流体"
    conductivity: float     # λ (仅固体)
    density: float          # ρ
    specific_heat: float    # cp
    description: str        # 备注
    source: str             # 数据来源 / 参考文献
    tags: List[str]         # 用户标签
```

### 3.2 功能

| 功能 | 说明 |
|------|------|
| 内置预设 | 铝(237/2700/890)、铜(400/8960/385)、硅(148/2330/700)、不锈钢(16/8000/500)、泡沫(0.035/25/2)、空气(—/1.2/1005) 等 |
| 用户自定义 | 添加/编辑/删除自定义材质，持久化到 `material_library.json` |
| 赋予介质 | 从材质库选择 → 自动填入 λ/ρ/cp |
| 搜索与筛选 | 按名称/类别/标签搜索 |
| 导入/导出 | JSON 格式的材质库文件交换 |

### 3.3 材质库管理对话框

类似现有 `ConfigManagerDialog` 的设计：
- 左栏：分类树 + 材质列表
- 右栏：选中材质的详细属性 + 编辑/应用按钮
- 「应用到当前介质」一键赋值

---

## 四、任务域：求解任务管理系统

### 4.1 核心设计原则

**现有问题**：当前 `StardisControlPanel` 同时展示所有 8 种计算模式的参数 (probe_vol, probe_surf, flux_surf, medium_temp, surf_mean_temp, surf_temp_map, surf_flux, ir_image)，用户需要滚动大量不相关内容。

**新设计**：**「先选模式，再配参数」** — 一个任务只对应一种求解模式。

### 4.2 求解模式枚举

根据 Starter-Pack 脚本分析，stardis 支持以下互斥的求解模式：

| 模式 | CLI 标志 | 用户场景 | 关键参数 |
|------|----------|----------|----------|
| **体积温度探针** | `-p X,Y,Z[,T]` | 计算某点温度 | 探针坐标、时间(稳态/瞬态) |
| **表面温度探针** | `-P X,Y,Z,SIDE` | 计算表面某点温度 | 探针坐标、面标识 |
| **表面通量探针** | `-f X,Y,Z` | 计算表面某点热通量 | 探针坐标 |
| **介质平均温度** | `-m NAME,TIME` | 计算某介质的体平均温度 | 介质名称(从场景自动列出)、时间 |
| **表面平均温度** | `-s FILE` | 计算指定表面的面平均温度 | 输出文件 |
| **表面温度图** | `-S FILE` | 表面温度分布场 | 输出文件 |
| **表面通量** | `-F FILE` | 表面热通量分布 | 输出文件 |
| **IR 渲染** | `-R opts` | 热红外成像模拟 | 摄像机全部参数 |
| **Green 函数** | `-p ... -G FILE` | 导出 Green 函数供复用 | 探针坐标 + 输出文件 |
| **路径可视化** | `-p ... -D opts` | 导出热传输路径 VTK | 探针坐标 + 路径数 |
| **几何导出** | `-d` | 仅导出几何 VTK | 无额外参数 |

### 4.3 任务管理 UI 交互流

```
┌─ 求解任务 ──────────────────────────────────────────┐
│                                                      │
│  场景文件: [/path/to/scene.txt] [从场景编辑器获取]    │
│                                                      │
│  ┌──────────────────────────────────────┐            │
│  │ 求解模式:  [  IR 渲染 (红外成像)  ▼]  │            │
│  └──────────────────────────────────────┘            │
│                                                      │
│  ═══ 以下仅显示 IR 渲染的参数 ═══                     │
│                                                      │
│  SPP: [1024]  分辨率: [320] x [320]  FOV: [30.0]°   │
│  位置 pos: [0.05] [0.01] [0.0]  [从3D视口获取]      │
│  目标 tgt: [0.0]  [0.0]  [0.0]                      │
│  Up:       [0.0]  [0.0]  [1.0]                      │
│                                                      │
│  ═══ 通用参数 ═══                                     │
│  Monte Carlo 样本数: [—] (IR模式由SPP决定)           │
│  线程数: [16]    详细度: [3-调试 ▼]                   │
│  扩展输出: [✓]                                       │
│                                                      │
│  ── 命令预览 ──                                      │
│  stardis -V 3 -M scene.txt -t 16                    │
│    -R spp=1024:img=320x320:fov=30:pos=...           │
│                                                      │
│  [▶ 运行]  [⏹ 停止]                                 │
│                                                      │
│  ── 输出日志 ──                                      │
│  [实时日志...]                                       │
└──────────────────────────────────────────────────────┘
```

**关键交互**：
- 切换「求解模式」下拉 → 参数区**整体替换**为该模式的专属参数，无关参数完全隐藏
- 「介质平均温度」模式下，介质名称下拉自动从当前场景的介质列表填充
- 「IR 渲染」模式下，摄像机参数可从 3D 视口一键获取
- 「探针」类模式下，可在 3D 视口中点击设置探针位置

### 4.4 高级/输出选项

保留现有功能但按模式条件显示：

| 选项 | 适用模式 | CLI |
|------|----------|-----|
| 扩散算法 | 所有 | `--diff-algo` |
| Picard 迭代阶数 | 所有 | `--picard-order` |
| 初始时间 | 瞬态模式 | `--initial-time` |
| 禁用内辐射 | 所有 | `--disable-intrad` |
| RNG 状态读入/写出 | 所有 | `--rng-state-in/out` |
| 几何 Dump | 调试用 | `-d` |
| 路径 Dump | 探针模式 | `-D` |
| Green 函数导出 | 探针模式 | `-G` |

---

## 五、渲染结果回显

### 5.1 图像查看器 (`ImageViewer`)

| 功能 | 说明 |
|------|------|
| 支持格式 | PPM (htpp 输出)、PNG、BMP |
| 交互 | 缩放 (滚轮)、平移 (中键拖拽)、适应窗口、1:1 |
| 色温标尺 | 在图像旁显示 colormap 标尺 (温度 → 颜色) |
| 像素信息 | 鼠标悬停显示像素坐标和对应温度值 |

### 5.2 自动化流水线

```
stardis 运行完成
  → 检测到输出 .ht 文件
  → 自动调用 htpp 转换为 .ppm
  → 图像查看器自动加载显示
```

用户可配置：
- 是否自动后处理
- htpp 参数模板 (色板、温度范围等)
- 输出目录

### 5.3 渲染历史

- 每次渲染结果保存为记录：时间戳 + 参数快照 + 图像路径
- 缩略图列表，点击查看大图
- 支持两张图并排对比

---

## 六、主界面布局

```
┌─────────────────────────────────────────────────────────────────┐
│  菜单栏: 文件 | 场景 | 任务 | 视图 | 帮助                         │
├────────────────────────┬──────────────────┬─────────────────────┤
│                        │                  │                     │
│    3D 场景视口          │   属性编辑面板    │   任务面板           │
│    (VTK Viewport)      │   (PropertyPanel) │   (TaskPanel)       │
│                        │                  │                     │
│    - 多对象渲染         │  根据选中对象      │  求解模式选择        │
│    - 摄像机锥体         │  动态切换显示:     │  模式专属参数        │
│    - 点击选择           │  - 介质属性        │  通用参数           │
│    - 鼠标旋转/缩放      │  - 边界属性        │  命令预览           │
│                        │  - 全局设置        │  运行/停止          │
│                        │  - 摄像机参数      │  日志输出           │
│                        │                  │                     │
├────────────────────────┼──────────────────┴─────────────────────┤
│   场景树面板            │   底部面板 (可切换标签)                   │
│   (SceneTreePanel)     │   ┌─────┬──────┬──────┬──────┐         │
│                        │   │ 日志 │ 图像 │ 历史 │ htpp │         │
│   🌐 全局设置           │   └─────┴──────┴──────┴──────┘         │
│   📦 介质 (3)           │                                        │
│   🔲 边界 (3)           │   输出日志 / 渲染结果图像 /              │
│   🔗 连接 (0)           │   渲染历史缩略图 / htpp 控制             │
│   📷 摄像机             │                                        │
└────────────────────────┴────────────────────────────────────────┘
```

面板支持拖拽调整大小，可折叠/展开。

---

## 七、建议的文件结构

```
src/
├── main.py                          # 主窗口 + 多面板布局
├── models/
│   ├── scene_model.py               # SceneModel / Medium / Boundary / Connection
│   ├── material_database.py         # Material + MaterialLibrary (内置+用户)
│   └── task_model.py                # TaskConfig (求解模式 + 参数)
├── parsers/
│   ├── scene_parser.py              # .txt → SceneModel
│   └── scene_writer.py              # SceneModel → .txt
├── viewport/
│   ├── scene_viewport.py            # VTK 多对象渲染 (升级 StlViewport)
│   ├── camera_gizmo.py              # 摄像机锥体可视化 + 交互
│   └── object_picker.py             # 3D 拾取 / 高亮 / 探针定位
├── panels/
│   ├── scene_tree_panel.py          # QTreeWidget 场景树
│   ├── property_panel.py            # 动态属性编辑 (按选中类型切换)
│   ├── task_panel.py                # 求解任务面板 (替代旧 ControlPanel)
│   ├── material_manager_dialog.py   # 材质库管理对话框
│   └── camera_panel.py              # 摄像机参数 (嵌入属性面板)
├── viewers/
│   ├── image_viewer.py              # PPM/图像查看器
│   └── render_history.py            # 渲染历史管理
├── pipeline/
│   └── auto_postprocess.py          # stardis → htpp 自动后处理流水线
├── HtppControlPanel.py              # (已有，集成到底部面板)
├── ConfigManagerDialog.py           # (已有)
├── StardisConfig.py                 # (已有，兼容)
└── StardisConfigEnhanced.py         # (已有，扩展支持场景+任务)
```

---

## 八、实施路线

| 阶段 | 交付物 | 依赖 |
|------|--------|------|
| **P0 — 数据基础** | `SceneModel` + `SceneParser` + `SceneWriter` + 单元测试 (用 Starter-Pack 5个场景验证往返解析) | 无 |
| **P1 — 材质库** | `Material` 模型 + 内置预设 + JSON 持久化 + 管理对话框 | 无 |
| **P2 — 场景视口** | 多对象渲染 + 颜色区分 + 可见性/透明度 + 选择高亮 | P0 |
| **P3 — 场景树 + 属性面板** | 树形浏览 + 动态属性编辑 + 新建/删除对象 + 材质库集成 | P0, P1, P2 |
| **P4 — 主界面重构** | 多面板布局 + 面板拖拽/折叠 | P2, P3 |
| **P5 — 任务面板重设计** | 模式选择 → 动态参数 + 场景联动 (介质列表/摄像机同步) | P0, P4 |
| **P6 — 摄像机系统** | 锥体可视化 + 交互拖拽 + 双向同步 + 「使用当前视角」 | P2, P5 |
| **P7 — 图像回显** | ImageViewer + 自动后处理流水线 + 渲染历史 | P5 |
| **P8 — 模型导入** | OBJ/PLY → STL 转换 | P2 |

P0 和 P1 可并行开发，P2~P4 为场景域主线，P5~P7 为任务域主线。

---

## 附录 A：Stardis 场景文件格式参考

### 关键字语法

```
TRAD <T_ambient> <T_reference>
SCALE <factor>

SOLID <name> <λ> <ρ> <cp> <δ|AUTO> <T_init> <T_imposed|UNKNOWN> <power> <FRONT|BACK|BOTH> <stl_files...>
FLUID <name> <ρ> <cp> <T_init> <T_imposed|UNKNOWN> <FRONT|BACK|BOTH> <stl_files...>

T_BOUNDARY_FOR_SOLID <name> <temperature> <stl_files...>
H_BOUNDARY_FOR_SOLID <name> <Tref> <emissivity> <specular_fraction> <hc> <T_env> <stl_files...>
F_BOUNDARY_FOR_SOLID <name> <flux> <stl_files...>
HF_BOUNDARY_FOR_SOLID <name> <Tref> <emissivity> <specular_fraction> <hc> <T_env> <flux> <stl_files...>

SOLID_FLUID_CONNECTION <name> <Tref> <emissivity> <specular_fraction> <hc> <stl_files...>
SOLID_SOLID_CONNECTION <name> <contact_resistance> <stl_files...>
```

### 示例场景 (porous)

```
TRAD 680 800
# intermedia
SOLID    FOAM   237   2700   890   0.0002    750    UNKNOWN    0   FRONT S_porous.stl

# boundaries
H_BOUNDARY_FOR_SOLID   LAT    300   0.9     0.5   0  300  B_lateral.stl
T_BOUNDARY_FOR_SOLID   T0                            750  B_T0.stl
T_BOUNDARY_FOR_SOLID   T1                            850  B_T1.stl
```

### 示例场景 (city)

```
TRAD 300 300
#medium
SOLID    WALL        1.5     25    2   AUTO    300    UNKNOWN    0   FRONT S_walls.stl
SOLID    INSULATOR   0.035   25    2   AUTO    300    UNKNOWN    0   FRONT S_insulator.stl
SOLID    GLAZING     0.9     25    2   AUTO    300    UNKNOWN    0   FRONT S_glazing.stl
SOLID    GROUND      1       25    2   AUTO    300    UNKNOWN    0   FRONT S_ground.stl

#boundary conditions
H_BOUNDARY_FOR_SOLID   EXTERNAL      273  0.9   0.2   10    273   B_external_walls.stl
H_BOUNDARY_FOR_SOLID   INTERNAL      293  0.9   0     10    293   B_internal_walls.stl
H_BOUNDARY_FOR_SOLID   EXT_GROUND    273  0.9   0     10    273   B_external_ground.stl
H_BOUNDARY_FOR_SOLID   INT_GROUND    293  0.9   0     10    293   B_internal_ground.stl
H_BOUNDARY_FOR_SOLID   EXT_GLAZING   273  0.15  0.8    5    273   B_external_glazing.stl
H_BOUNDARY_FOR_SOLID   INT_GLAZING   293  0.15  0.8    5    293   B_internal_glazing.stl
H_BOUNDARY_FOR_SOLID   EXT_ROOF      273  0.9   0     10    273   B_external_roof.stl
H_BOUNDARY_FOR_SOLID   INT_ROOF      293  0.9   0     10    293   B_internal_roof.stl
```

## 附录 B：Stardis CLI 求解模式参考

### 通用参数
```
-M <scene.txt>      场景文件 (必需)
-n <N>              Monte Carlo 实现数
-t <threads>        线程数
-V <0|1|2|3>        详细度
-e                  扩展统计输出
--diff-algo <algo>  扩散算法
--picard-order <N>  Picard 迭代阶数
--initial-time <T>  初始时间 (瞬态)
--disable-intrad    禁用内辐射
--rng-state-in <F>  读入 RNG 状态
--rng-state-out <F> 写出 RNG 状态
```

### 模式专属参数
```
# 体积温度探针
-p X,Y,Z[,TIME]

# 表面温度探针
-P X,Y,Z,SIDE

# 表面通量探针
-f X,Y,Z

# 介质平均温度
-m MEDIUM_NAME,TIME

# 表面平均温度
-s OUTPUT_FILE

# 表面温度图
-S OUTPUT_FILE

# 表面通量
-F OUTPUT_FILE

# IR 渲染
-R spp=N:img=WxH:fov=ANGLE:pos=X,Y,Z:tgt=X,Y,Z:up=X,Y,Z:fmt=HT:file=PATH

# Green 函数导出 (需配合 -p)
-G OUTPUT_FILE

# 路径可视化 (需配合 -p)
-D all,"PREFIX"

# 几何导出
-d
```

### Starter-Pack 脚本示例

**Probe (cube):**
```bash
stardis -V 3 -M model.txt -p 0.5,0.5,0.5,"100" -n 10000
```

**Medium Temperature (heatsink):**
```bash
stardis -V 3 -M model.txt -m SIPw,INF -n 1000 -e
```

**IR Rendering (porous):**
```powershell
stardis -V 3 -M porous.txt -t 16 -R spp=32:img=320x320:fov=30:pos=0.05,0.01,0:tgt=0,0,0:up=0,0,1 > IR.ht
htpp -m default:range=650,850 -o IR.ppm IR.ht
```

**Green Function (cube):**
```bash
stardis -M model.txt -p 0.5,0.5,0.5 -n 10000 -G "probe.green"
```

**Path Dump (cube):**
```bash
stardis -V 3 -M model.txt -p 0.5,0.5,0.5,inf -n 10 -D all,"path"
```
