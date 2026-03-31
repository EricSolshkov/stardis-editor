# 05 — Green 函数路径录制与重放工作流

## 1. 理论基础

### 1.1 来源

基于 Bati et al. 2023 "Coupling conduction, convection and radiative transfer in a single path-space: application to infrared rendering"（ACM TOG）§4.4 "Storing and displaying path information"。

### 1.2 核心原理

在 stardis 的耦合蒙特卡洛算法中，每条热传输路径从观测点出发，经过辐射/传导/对流子路径的交替，**最终到达已知温度处终止**（imposed boundary condition 或 initial condition）。路径的 MC 权重就是终点温度值。

由于物理模型是**线性**的：

$$T_{\text{pixel}} = \frac{1}{N}\sum_{k=1}^{N} T_{\text{end}}^{(k)}$$

路径的**几何拓扑**（怎么走、经过哪些介质）完全由随机数决定，与边界温度值无关。因此：

- **录制**：运行一次完整 MC 仿真，将每条路径的终端信息（到达了哪个边界/初始条件）存储下来
- **重放**：改变边界温度后，直接替换终端温度值重新加权求和，**无需重新采样路径**

### 1.3 性能数据（论文 Table 1）

| 场景 | 三角形 | 分辨率 | SPP | MC 仿真时间 | 重放时间 | 加速比 |
|------|--------|--------|-----|-------------|---------|--------|
| Teaser (a) | 13k | 1024² | 256 | 59min | 6s | ~600× |
| Farm (probe) | 380 | — | 10000 | 15s | 8μs | ~**2×10⁶**× |

### 1.4 两种存储粒度

| 级别 | 存储内容 | 重放能力 | 存储量 |
|------|---------|---------|--------|
| **终点存储** | 每条路径的终端边界标识 + 权重 | 改变 imposed 温度 → 即时重渲染 | 较小 |
| **全程存储** | 路径经过的所有表面交点 + 时间戳 | 改变观测时间 → 生成瞬态动画 | 较大 |

---

## 2. stardis CLI 现状

### 2.1 当前 -G 支持

stardis 通过 `-G` 和 `-g` 标志导出 Green 函数：

| 标志 | 功能 | 使用方式 |
|------|------|---------|
| `-g` | Green 函数 ASCII 输出（stdout） | `stardis -M scene.txt -p x,y,z -n N -g` |
| `-G file[,end_paths]` | Green 函数二进制导出 | `stardis -M scene.txt -p x,y,z -n N -G probe.green` |

**当前限制**：`-G` 只与探针模式 (`-p`) 配合使用，不支持 IR 渲染模式 (`-R`)。

### 2.2 重放机制（待确认）

根据论文和代码推测，stardis 的重放通过以下方式之一实现：

1. **内置重放**：stardis 读取 Green 文件 + 新的边界条件文件 → 直接输出结果
2. **外部重放**：Green 文件是路径终端的结构化数据，由外部脚本/工具加权求和

> **TODO**: 需要确认 stardis 是否有 `--green-input` 或类似的重放 CLI 标志。
> 如果 stardis 内置了重放，只需在 task_model 中增加对应参数；
> 如果重放是外部工具，需要新增一种 TaskType 或 ComputeMode。

---

## 3. 工作流设计

### 3.1 使用场景

#### 场景 A：探针参数扫描
固定几何和材质，扫描不同边界温度下探针点的温度响应。

```
步骤 1: stardis -M scene.txt -p 0.5,0.5,0.5 -n 100000 -G probe.green
步骤 2: 改变 scene.txt 中的 T_BOUNDARY 温度值
步骤 3: stardis 重放 probe.green → 即时得到新温度（无需重新采样）
```

#### 场景 B：IR 图像边界条件探索
固定几何和相机，改变建筑外墙温度/保温方案，观察红外图像变化。

```
步骤 1: stardis -M scene.txt -R ... -G render.green  (如果 -R 支持 -G)
步骤 2: 修改边界温度
步骤 3: 重放 render.green → 毫秒级重新渲染
步骤 4: htpp 后处理 → 输出图像
```

#### 场景 C：瞬态红外动画
固定几何和相机，从稳态 MC 路径生成不同观测时间的瞬态 IR 图像序列。

```
步骤 1: stardis -M scene.txt -R ... -G render.green (存储所有表面交点)
步骤 2: 对每个时间点 t_obs，重放生成 IR_t.ht
步骤 3: htpp 批量后处理 → 图像序列 / 视频
```

### 3.2 任务队列编排

在 Scene Editor 的任务系统中，Green 工作流表现为**多步任务链**：

```
TaskQueue
├── Task[0]: Stardis IR Render + Green 录制
│   ├── mode: IR_RENDER
│   ├── green_output: "render.green"     ← 新增字段
│   └── output_redirect: "IR_base.ht"
│
├── Task[1]: HTPP 基准图像
│   ├── input: from_task[0]
│   └── output: "IR_base.ppm"
│
├── Task[2]: Stardis Green 重放 (变更温度 A)
│   ├── mode: GREEN_REPLAY                ← 新增 ComputeMode
│   ├── green_input: "render.green"       ← 引用 Task[0] 产出
│   ├── scene_override: "scene_A.txt"     ← 修改后的场景文件
│   └── output_redirect: "IR_A.ht"
│
├── Task[3]: HTPP 变更 A 图像
│   ├── input: from_task[2]
│   └── output: "IR_A.ppm"
│
├── Task[4]: Stardis Green 重放 (变更温度 B)
│   └── ...同 Task[2]，不同的 scene_override
│
└── Task[5]: HTPP 变更 B 图像
    └── ...
```

---

## 4. 数据模型变更方案

### 4.1 新增 ComputeMode

```python
class ComputeMode(Enum):
    PROBE_SOLVE  = "probe_solve"
    FIELD_SOLVE  = "field_solve"
    IR_RENDER    = "ir_render"
    GREEN_REPLAY = "green_replay"    # ← 新增：Green 函数重放
```

### 4.2 StardisParams 扩展

```python
@dataclass
class GreenConfig:
    """Green 函数录制/重放配置"""
    # 录制（与 IR_RENDER/PROBE_SOLVE 配合）
    output_file: str = ""              # -G file: 录制输出路径
    output_ascii: bool = False         # -g: ASCII 格式输出到 stdout
    end_paths_file: str = ""           # -G file,end_paths: 可选终止路径文件

    # 重放（GREEN_REPLAY 模式专用）
    input_file: str = ""               # 读取已录制的 Green 文件
    scene_file: str = ""               # 重放时使用的（变更后的）场景文件


@dataclass
class StardisParams:
    model_file: str = ""
    samples: int = 1000000
    threads: int = 4
    verbosity: int = 1

    probe_refs: List[str] = field(default_factory=list)
    camera_ref: Optional[str] = None
    field_solve: Optional[FieldSolveConfig] = None

    green: GreenConfig = field(default_factory=GreenConfig)    # ← 新增
    advanced: AdvancedOptions = field(default_factory=AdvancedOptions)
```

### 4.3 CommandBuilder 变更

```python
# 录制模式：在现有 IR_RENDER / PROBE_SOLVE 命令后追加 -G/-g
if params.green.output_file:
    green_arg = params.green.output_file
    if params.green.end_paths_file:
        green_arg += f',{params.green.end_paths_file}'
    args.extend(['-G', green_arg])
if params.green.output_ascii:
    args.append('-g')

# 重放模式：GREEN_REPLAY 的参数构建
# （具体 CLI 取决于 stardis 的重放接口，待确认）
```

### 4.4 任务间依赖

Green 重放任务需要引用录制任务的输出文件。复用现有的 `InputSource` 机制：

```python
@dataclass
class GreenFromTask:
    """引用队列中某个录制任务的 Green 输出文件"""
    task_id: str = ""

@dataclass
class GreenFromFile:
    """直接指定已有 Green 文件路径"""
    file_path: str = ""

GreenSource = Union[GreenFromTask, GreenFromFile]
```

---

## 5. UI 设计

### 5.1 录制入口

在现有的 TaskEditor Stardis 面板中，为 **IR_RENDER** 和 **PROBE_SOLVE** 模式增加 Green 录制选项：

```
┌── Green 函数录制 ─────────────────────────┐
│ [✓] 启用 Green 录制                       │
│ 输出文件: [render.green ] [浏览...]       │
│ [  ] 同时 ASCII 输出到 stdout (-g)        │
│ 终止路径文件 (可选): [         ] [浏览...] │
└───────────────────────────────────────────┘
```

### 5.2 重放任务创建

在场景树中，右键 Green 录制任务 → "创建重放任务…"

TaskEditor 中选择 ComputeMode = GREEN_REPLAY 时显示：

```
┌── Green 函数重放 ─────────────────────────┐
│ Green 文件来源:                           │
│   (●) 引用任务: [Task 0: IR Base ▼]      │
│   ( ) 指定文件: [              ] [浏览...]│
│                                           │
│ 场景文件 (变更后):                         │
│   [scene_hot_walls.txt      ] [浏览...]   │
│                                           │
│ 输出文件: [IR_hot.ht] (stdout 重定向)      │
└───────────────────────────────────────────┘
```

### 5.3 快捷工作流

为常见使用模式提供一键创建：

| 入口 | 动作 | 创建的任务 |
|------|------|-----------|
| Camera 右键 → "创建 IR + Green 录制任务组" | 一键创建 | Stardis IR (-R + -G) + HTPP |
| Green 录制任务右键 → "添加重放变体" | 快速添加 | Stardis Replay + HTPP |
| Probe 右键 → "创建探针 + Green 录制任务" | 一键创建 | Stardis Probe (-p + -G) |

---

## 6. 实施路线

### Phase 1：探针 Green 录制（最小可用）
- 在 `StardisParams` 中添加 `GreenConfig`
- `CommandBuilder` 支持 `-G`/`-g` 参数构建
- TaskEditor UI 增加 Green 录制复选框（IR_RENDER / PROBE_SOLVE）
- 序列化/反序列化

### Phase 2：Green 重放任务
- 确认 stardis 的重放 CLI 接口
- 添加 `GREEN_REPLAY` ComputeMode
- 实现 `GreenSource` 任务间依赖
- TaskEditor 重放 UI
- 右键快捷创建

### Phase 3：瞬态动画工作流
- 支持时间序列重放（批量 t_obs 参数）
- 批量 HTPP 后处理
- 图像序列输出管理

---

## 7. 开放问题

1. **stardis 重放 CLI**：stardis 是否有内置的 Green 重放命令？如果没有，重放逻辑需要在编辑器侧实现（读取 Green 二进制 + 加权求和）。

2. **-R + -G 兼容性**：当前 `-G` 只支持 `-p`（探针）。IR 渲染的 Green 录制需要 stardis 侧的支持。论文表明 Stardis 的原型实现已支持此功能，但可能未暴露为 CLI 标志。

3. **Green 文件格式**：需要了解 `.green` / `.bin` 文件的内部结构（header + 路径终端数据），以便在编辑器中显示文件信息（路径数、关联场景、录制时间等）。

4. **场景兼容性验证**：重放时需验证新场景文件与录制时的几何一致性（几何变化会使路径失效）。stardis 是否内置了此检查？

5. **存储量估算**：对于大分辨率 IR 图像（如 1024² × 1024 spp），Green 文件大小需要评估是否可接受。
