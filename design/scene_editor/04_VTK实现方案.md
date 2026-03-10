# Scene Editor v2：VTK 实现方案

> **阅读层次**：实现细节层，仅实现者需要阅读。
> 本文档回答：如何用 VTK API 实现各类渲染、拾取和导出功能？
> 行为规约见 [02_UI行为规约.md](02_UI行为规约.md)，组件信号见 [03_组件通信协议.md](03_组件通信协议.md)。

---

## §1 选择高亮

### 1.1 Silhouette 轮廓线（Body 选中 / Zone 选中）

```python
# 每次选中 Body 时动态创建，取消选中时销毁
silhouette = vtkPolyDataSilhouette()
silhouette.SetInputData(body_polydata)
silhouette.SetCamera(renderer.GetActiveCamera())  # 自动跟随视角

mapper = vtkPolyDataMapper()
mapper.SetInputConnection(silhouette.GetOutputPort())

silhouette_actor = vtkActor()
silhouette_actor.SetMapper(mapper)
silhouette_actor.GetProperty().SetColor(1.0, 1.0, 0.0)  # 黄色
silhouette_actor.GetProperty().SetLineWidth(3.0)

renderer.AddActor(silhouette_actor)
```

选中效果规则：
- Body 选中 → 仅 Silhouette 轮廓线高亮
- Zone 选中 → Silhouette 轮廓线 + LUT 临时替换（见 §1.2）
- 取消选中 → 移除 Silhouette，恢复原始 LUT
- 进入涂选模式时自动清除所有高亮效果

### 1.2 LUT 区域着色高亮（SurfaceZone 选中）

```python
# 保存原始 LUT
original_lut = vtkLookupTable()
original_lut.DeepCopy(mapper.GetLookupTable())

# 构建高亮 LUT
highlight_lut = vtkLookupTable()
highlight_lut.DeepCopy(original_lut)
for label in range(total_zones + 1):
    if label == selected_zone_label:
        pass  # 保持原色
    else:
        highlight_lut.SetTableValue(label, 0.45, 0.45, 0.45, 1.0)  # 暗灰
highlight_lut.Build()
mapper.SetLookupTable(highlight_lut)

# 取消选择时
mapper.SetLookupTable(original_lut)
```

---

## §2 法线显示

```python
# 计算面法线
normals = vtkPolyDataNormals()
normals.SetInputData(body_polydata)
normals.ComputeCellNormalsOn()
normals.ComputePointNormalsOff()
normals.Update()

# 提取面中心点
cell_centers = vtkCellCenters()
cell_centers.SetInputConnection(normals.GetOutputPort())

# 从面中心沿法线方向生成线段
hedgehog = vtkHedgeHog()
hedgehog.SetInputConnection(cell_centers.GetOutputPort())
hedgehog.SetVectorModeToUseNormal()
hedgehog.SetScaleFactor(normal_length)  # 初始值 1.0，可通过 +/- 键调整

mapper = vtkPolyDataMapper()
mapper.SetInputConnection(hedgehog.GetOutputPort())

normal_actor = vtkActor()
normal_actor.SetMapper(mapper)
normal_actor.GetProperty().SetColor(1.0, 0.0, 0.0)  # 红色
normal_actor.GetProperty().SetLineWidth(1.0)

renderer.AddActor(normal_actor)
```

`+` / `-` 键调整时，仅需修改 `hedgehog.SetScaleFactor()` 并触发重渲染，对所有已显示法线的几何体同时生效。

---

## §3 几何体 Actor 结构

```
Body "FOAM" 的渲染组件:
  │
  ├── body_actor (主体，常驻)
  │   ├── vtkPolyData ← vtkSTLReader
  │   │   └── CellData: "BoundaryLabel" (vtkIntArray)
  │   │       0 = 未分配；值 = zone_id（Body.next_zone_id 自增，不重用）
  │   │       LUT 按 zone_id 直接索引，范围 [0, max_zone_id]
  │   ├── vtkPolyDataMapper
  │   │   ├── ScalarMode = SetScalarModeToUseCellData()
  │   │   ├── ColorMode = SetColorModeToMapScalars()
  │   │   └── LookupTable = zone_lut
  │   └── vtkActor
  │       └── 属性: 默认不透明
  │
  └── silhouette_actor (选中时动态创建/销毁，导航模式专属)
      ├── vtkPolyDataSilhouette
      ├── vtkPolyDataMapper
      └── vtkActor  (Color=黄色, LineWidth=3)
```

---

## §4 探针 Actor 结构

```
Probe "P1" 的渲染组件:
  │
  ├── marker_actor (探针标记)
  │   ├── vtkSphereSource (体积温度)
  │   │   或 vtkConeSource (表面温度,底部贴面)
  │   │   或 vtkArrowSource (表面通量)
  │   │   半径 = 场景包围盒对角线 × 0.01
  │   └── vtkActor (始终在最前层渲染: DepthPeelingOn 或 high render order)
  │
  ├── label_actor (文字标签)
  │   └── vtkBillboardTextActor3D
  │       文字: "P1 (0.500, 0.500, 0.500)"
  │
  └── axis_actor (可选: 局部坐标轴，帮助判断探针朝向)
      └── vtkAxesActor (短轴)
```

---

## §5 探针位置检测

判断探针与几何体的空间关系，用于属性面板中的警告提示：

```python
def check_probe_in_body(probe_pos: tuple, body_polydata: vtkPolyData) -> bool:
    """判断点是否在闭合 mesh 内部 (需要 mesh 是闭合的)"""
    select_enclosed = vtkSelectEnclosedPoints()
    select_enclosed.SetSurfaceData(body_polydata)
    select_enclosed.Initialize()
    return bool(select_enclosed.IsInsideSurface(*probe_pos))
```

---

## §6 颜色查找表 (LookupTable) 管理

`BoundaryLabel` 现在存储 `zone_id`（唯一、不重用的整数），LUT 按 zone_id 直接寻址。

```python
import colorsys

class ZoneColorManager:
    """为每个 Body 管理一个 zone_id → 颜色的 LookupTable"""

    # BC 类型 → 基础色调 (HSV H 值, 0~1)
    TYPE_BASE_HUES = {
        'T_BOUNDARY':  0.60,   # 蓝色系 (H=216°)
        'H_BOUNDARY':  0.05,   # 红/橙系 (H=18°)
        'F_BOUNDARY':  0.33,   # 绿色系 (H=120°)
        'HF_BOUNDARY': 0.80,   # 紫色系 (H=288°)
    }

    def default_color_for_zone(self, zone, same_type_index: int) -> tuple:
        """
        为新建区域生成默认颜色。
        same_type_index: 该 zone 在同 BC 类型中的序号（0-based），
        用于在基色调内偏移明度/饱和度，避免同类颜色雷同。
        """
        h = self.TYPE_BASE_HUES[zone.boundary.type]
        # 同类型第 N 个：在色调 ±0.06 范围内偏移，不超出可辨识边界
        h = (h + (same_type_index % 5) * 0.04) % 1.0
        s = 0.80 - (same_type_index // 5) * 0.12  # 第2轮降低饱和度
        v = 0.85
        r, g, b = colorsys.hsv_to_rgb(h, max(0.3, s), v)
        return (r, g, b)

    def build_lut(self, zones: list) -> 'vtkLookupTable':
        """
        根据当前 body 的 surface_zones 构建 zone_id → 颜色 LUT。
        zones 中每个 zone 的 color 属性优先使用；若为 None 则调用 default_color_for_zone。
        LUT 大小 = max(zone_id) + 1，zone_id 为稀疏时仍正确（未使用的槽位为黑色透明）。
        """
        if not zones:
            lut = vtkLookupTable()
            lut.SetNumberOfTableValues(1)
            lut.SetTableValue(0, 0.7, 0.7, 0.7, 0.5)
            lut.Build()
            return lut

        max_id = max(z.zone_id for z in zones)
        lut = vtkLookupTable()
        lut.SetNumberOfTableValues(max_id + 1)
        lut.SetTableRange(0, max_id)

        # 槽位 0：未分配
        lut.SetTableValue(0, 0.7, 0.7, 0.7, 0.5)

        # 按类型统计序号，用于同类型内的颜色偏移
        type_counters: dict = {}
        for zone in zones:
            bc_type = zone.boundary.type
            idx = type_counters.get(bc_type, 0)
            type_counters[bc_type] = idx + 1

            if zone.color is not None:
                r, g, b = zone.color.redF(), zone.color.greenF(), zone.color.blueF()
            else:
                r, g, b = self.default_color_for_zone(zone, idx)

            lut.SetTableValue(zone.zone_id, r, g, b, 1.0)

        lut.Build()
        return lut
```

**LUT 更新时机**：
- 新建区域 → 重建 LUT（新 zone_id 加入）
- 删除区域 → 重建 LUT（zone_id 不回收，对应槽位置为透明；BoundaryLabel 数组中该 zone_id 的单元标记清零）
- 用户修改颜色 → 重建 LUT
- 进入高亮模式时临时替换 LUT（见 §1.2），退出时恢复

---

## §7 涂选：Cell 拾取与画刷

### 7.1 BrushMode 枚举

```python
from enum import Enum

class BrushMode(Enum):
    BRUSH        = "brush"    # 屏幕空间拖拽画刷（原有模式）
    FILL_ALL     = "fill_all" # 全部填充：填充当前几何体所有单元
    FLOOD_FILL   = "flood"    # 洪泛填充：BFS 连通扩散（相同 zone_id 的相邻单元）
    REPLACE_FILL = "replace"  # 替换填充：替换所有相同 zone_id 的单元（不限连通性）
```

### 7.2 SurfacePainter

```python
from collections import deque
from vtk import (
    vtkHardwareSelector, vtkIdList, vtkIntArray, vtkPolyData,
    vtkActor, vtkRenderer, vtkDataObject, vtkSelectionNode
)

class SurfacePainter:
    """涂选模式核心：支持四种互斥画刷模式 + 50 步撤销/重做"""

    def __init__(self, body_polydata: vtkPolyData, body_actor: vtkActor,
                 renderer: vtkRenderer):
        self.poly       = body_polydata
        self.body_actor = body_actor
        self.renderer   = renderer
        self.labels     = body_polydata.GetCellData().GetArray("BoundaryLabel")

        self.brush_mode: BrushMode = BrushMode.BRUSH
        self.brush_radius_px: int  = 20

        self._adjacency: list | None = None  # List[List[int]], 懒构建

        # 撤销/重做栈
        self.undo_stack: list = []   # List[vtkIntArray]
        self.redo_stack: list = []

    # ------------------------------------------------------------------ #
    # 邻接图（洪泛填充使用）                                                #
    # ------------------------------------------------------------------ #

    def _build_adjacency(self):
        """
        构建 cell → 邻接 cell 列表（共享边，即≥2 个共同顶点）。
        调用 BuildLinks() 后使用 GetCellEdgeNeighbors() 逐边查询。
        构建一次后缓存；几何体不变则无需重建。
        """
        self.poly.BuildLinks()
        n_cells = self.poly.GetNumberOfCells()
        adj = [[] for _ in range(n_cells)]
        neighbor_ids = vtkIdList()

        for cid in range(n_cells):
            cell = self.poly.GetCell(cid)
            n_edges = cell.GetNumberOfEdges()
            for eid in range(n_edges):
                edge = cell.GetEdge(eid)
                pid0 = edge.GetPointId(0)
                pid1 = edge.GetPointId(1)
                neighbor_ids.Reset()
                self.poly.GetCellEdgeNeighbors(cid, pid0, pid1, neighbor_ids)
                for j in range(neighbor_ids.GetNumberOfIds()):
                    adj[cid].append(neighbor_ids.GetId(j))

        self._adjacency = adj

    # ------------------------------------------------------------------ #
    # 主交互入口                                                           #
    # ------------------------------------------------------------------ #

    def on_press(self, screen_x: int, screen_y: int, erase: bool = False):
        """
        鼠标按下时调用。
        - BRUSH 模式：记录撤销点，开始拖拽（拖拽过程由 on_drag 处理）
        - 其余模式：单击即执行，完整操作在此完成并记录撤销点
        """
        label = 0 if erase else self._current_label()
        self.save_undo_point()

        if self.brush_mode == BrushMode.FILL_ALL:
            self._fill_all(label)

        elif self.brush_mode == BrushMode.FLOOD_FILL:
            cell_id = self._pick_single_cell(screen_x, screen_y)
            if cell_id >= 0:
                self._flood_fill(cell_id, label)

        elif self.brush_mode == BrushMode.REPLACE_FILL:
            cell_id = self._pick_single_cell(screen_x, screen_y)
            if cell_id >= 0:
                self._replace_fill(cell_id, label)

        # BRUSH 模式的首笔也在此处理
        elif self.brush_mode == BrushMode.BRUSH:
            self._paint_brush(screen_x, screen_y, label)

    def on_drag(self, screen_x: int, screen_y: int, erase: bool = False):
        """仅 BRUSH 模式响应拖拽；其余模式忽略。"""
        if self.brush_mode != BrushMode.BRUSH:
            return
        label = 0 if erase else self._current_label()
        self._paint_brush(screen_x, screen_y, label)

    def on_release(self):
        """鼠标抬起；BRUSH 模式在此时可额外记录撤销点（可选）。"""
        pass  # 撤销点在 on_press 时已记录

    # ------------------------------------------------------------------ #
    # 具体画刷实现                                                         #
    # ------------------------------------------------------------------ #

    def _paint_brush(self, screen_x: int, screen_y: int, label: int):
        """
        屏幕空间矩形区域拾取，将画刷覆盖范围内所有可见 cell 标记为 label。
        """
        selector = vtkHardwareSelector()
        selector.SetRenderer(self.renderer)

        r = self.brush_radius_px
        x0 = max(0, screen_x - r)
        y0 = max(0, screen_y - r)
        x1 = screen_x + r
        y1 = screen_y + r
        selector.SetArea(x0, y0, x1, y1)
        selector.SetFieldAssociation(vtkDataObject.FIELD_ASSOCIATION_CELLS)

        result = selector.Select()
        if result is None:
            return

        for node_idx in range(result.GetNumberOfNodes()):
            node = result.GetNode(node_idx)
            if node.GetProperties().Get(vtkSelectionNode.PROP()) is not self.body_actor:
                continue
            sel_ids = node.GetSelectionList()
            for i in range(sel_ids.GetNumberOfTuples()):
                self.labels.SetValue(sel_ids.GetValue(i), label)

        self.poly.Modified()

    def _fill_all(self, label: int):
        """将当前几何体的所有单元设为 label。O(n)。"""
        n = self.poly.GetNumberOfCells()
        for i in range(n):
            self.labels.SetValue(i, label)
        self.poly.Modified()

    def _flood_fill(self, start_cell_id: int, label: int):
        """
        BFS 洪泛填充：从 start_cell_id 出发，遍历所有与其相连（共享边）
        且当前 zone_id 相同的单元，将其标记为 label。
        不同 zone_id 的相邻单元作为洪泛边界，不会被越过。
        """
        if self._adjacency is None:
            self._build_adjacency()

        source_label = self.labels.GetValue(start_cell_id)
        visited = set()
        queue = deque([start_cell_id])

        while queue:
            cid = queue.popleft()
            if cid in visited:
                continue
            if self.labels.GetValue(cid) != source_label:
                continue
            visited.add(cid)
            self.labels.SetValue(cid, label)
            for nb in self._adjacency[cid]:
                if nb not in visited:
                    queue.append(nb)

        self.poly.Modified()

    def _replace_fill(self, cell_id: int, label: int):
        """
        替换填充：找到所有与 cell_id 具有相同 zone_id 的单元（无论是否连通），
        统一替换为 label。O(n)。
        """
        source_label = self.labels.GetValue(cell_id)
        n = self.poly.GetNumberOfCells()
        for i in range(n):
            if self.labels.GetValue(i) == source_label:
                self.labels.SetValue(i, label)
        self.poly.Modified()

    def _pick_single_cell(self, screen_x: int, screen_y: int) -> int:
        """用 1×1 像素区域拾取单个 cell，返回 cell_id；无命中返回 -1。"""
        selector = vtkHardwareSelector()
        selector.SetRenderer(self.renderer)
        selector.SetArea(screen_x, screen_y, screen_x, screen_y)
        selector.SetFieldAssociation(vtkDataObject.FIELD_ASSOCIATION_CELLS)
        result = selector.Select()
        if result is None:
            return -1
        for node_idx in range(result.GetNumberOfNodes()):
            node = result.GetNode(node_idx)
            if node.GetProperties().Get(vtkSelectionNode.PROP()) is not self.body_actor:
                continue
            sel_ids = node.GetSelectionList()
            if sel_ids.GetNumberOfTuples() > 0:
                return sel_ids.GetValue(0)
        return -1

    def _current_label(self) -> int:
        """返回当前 SurfacePainter 激活的 zone_id（由外部在模式切换时设置）。"""
        return getattr(self, 'current_zone_id', 0)

    # ------------------------------------------------------------------ #
    # 撤销 / 重做                                                          #
    # ------------------------------------------------------------------ #

    def save_undo_point(self):
        snapshot = vtkIntArray()
        snapshot.DeepCopy(self.labels)
        self.undo_stack.append(snapshot)
        self.redo_stack.clear()
        if len(self.undo_stack) > 50:
            self.undo_stack.pop(0)

    def undo(self):
        if not self.undo_stack:
            return
        current = vtkIntArray()
        current.DeepCopy(self.labels)
        self.redo_stack.append(current)
        self.labels.DeepCopy(self.undo_stack.pop())
        self.poly.Modified()

    def redo(self):
        if not self.redo_stack:
            return
        current = vtkIntArray()
        current.DeepCopy(self.labels)
        self.undo_stack.append(current)
        self.labels.DeepCopy(self.redo_stack.pop())
        self.poly.Modified()
```

**性能说明**

| 模式 | 复杂度 | 典型 (~200k cells) |
|------|--------|--------------------|
| 画刷 | O(命中数) | < 2 ms |
| 全部填充 | O(n) | ~5 ms |
| 洪泛填充 | O(k), k≤n | ~5–30 ms |
| 替换填充 | O(n) | ~5 ms |
| 邻接图构建 | O(n·e/cell) | 首次 ~100 ms; 之后 `_adjacency` 已缓存 |

---

## §8 涂选区域导出 STL

```python
def export_zone_stl(body_poly: vtkPolyData, label_value: int, output_path: str):
    """将指定 label 的三角面提取并导出为 STL"""

    threshold = vtkThreshold()
    threshold.SetInputData(body_poly)
    threshold.SetInputArrayToProcess(
        0, 0, 0,
        vtkDataObject.FIELD_ASSOCIATION_CELLS,
        "BoundaryLabel"
    )
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

## §9 三角形哈希匹配：子 STL → 父 STL 单元映射

加载场景时，需要从 `B_*.stl`（子 STL）还原涂选状态，即确定子 STL 的每个三角面对应父 Body STL 中的哪个 cell_id。

### 9.1 原理

STL 三角面由三个顶点坐标唯一确定。对顶点坐标排序后取哈希，可在 O(1) 内实现父子三角面匹配。

```
父 STL (Body):  triangle → 顶点排序 → hash → 建 dict { hash: cell_id }
子 STL (B_*.stl): triangle → 顶点排序 → hash → 查 dict → parent_cell_id
```

### 9.2 实现

```python
import hashlib
from vtk import vtkSTLReader, vtkPolyData


def _triangle_hash(poly: vtkPolyData, cell_id: int, precision: int = 6) -> str:
    """
    计算单个三角面的哈希值。
    将三个顶点坐标四舍五入到 precision 位小数后，按字典序排序，
    拼接为字符串取 SHA-256 摘要。
    """
    cell = poly.GetCell(cell_id)
    pts = []
    for i in range(3):
        pid = cell.GetPointId(i)
        x, y, z = poly.GetPoint(pid)
        pts.append((round(x, precision), round(y, precision), round(z, precision)))
    pts.sort()
    key = str(pts)
    return hashlib.sha256(key.encode()).hexdigest()


def build_parent_hash_map(parent_poly: vtkPolyData, precision: int = 6) -> dict:
    """
    为父 STL 构建哈希表: { triangle_hash → cell_id }
    复杂度: O(n_parent)
    """
    hash_map = {}
    for cid in range(parent_poly.GetNumberOfCells()):
        h = _triangle_hash(parent_poly, cid, precision)
        hash_map[h] = cid
    return hash_map


def match_child_to_parent(parent_poly: vtkPolyData,
                          child_poly: vtkPolyData,
                          precision: int = 6) -> tuple:
    """
    通过三角形哈希匹配，返回子 STL 在父 STL 中对应的 cell_id 集合。

    Returns:
        (matched_cell_ids: set[int], unmatched_count: int)
        matched_cell_ids: 子三角面在父 STL 中的 cell_id 集合
        unmatched_count: 未匹配的子三角面数量（用于警告）
    """
    parent_map = build_parent_hash_map(parent_poly, precision)
    matched = set()
    unmatched = 0

    for cid in range(child_poly.GetNumberOfCells()):
        h = _triangle_hash(child_poly, cid, precision)
        parent_cid = parent_map.get(h)
        if parent_cid is not None:
            matched.add(parent_cid)
        else:
            unmatched += 1

    return matched, unmatched
```

### 9.3 使用场景

| 场景 | 流程 |
|------|------|
| **加载已保存项目** | 从 JSON 读取 `zone_parent_map` → 知道 B_LAT.stl 属于 FOAM body → 调用 `match_child_to_parent(foam_poly, b_lat_poly)` → 恢复 cell_ids |
| **导入外部场景（无 JSON）** | 弹窗让用户为每个 B_*.stl 选择父 Body → 同上 |
| **保存** | 从 BoundaryLabel 数组中按 zone_id 导出子 STL（见 §8）→ 同时在 JSON 中写入 `zone_parent_map` |

### 9.4 性能

| 阶段 | 复杂度 | 100 万面父 STL |
|------|--------|--------------|
| 构建父哈希表 | O(n_parent) | ~300 ms |
| 匹配子 STL | O(n_child) | ~50 ms (10 万面子 STL) |
| 总内存 | 64 字节/hash × n_parent | ~60 MB |

> 哈希构建只需在加载 Body 时执行一次，后续所有该 Body 下的 zone 均复用同一哈希表。
