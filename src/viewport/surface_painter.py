"""
S6: 涂选模式核心逻辑

支持四种互斥画刷模式 + zone_id 直接寻址 LUT + 完整撤销/重做。
"""

import colorsys
from collections import deque
from enum import Enum
from typing import List, Optional

import vtk


class BrushMode(Enum):
    """涂选画刷模式。"""
    BRUSH        = "brush"      # 屏幕空间拖拽画刷
    FILL_ALL     = "fill_all"   # 全部填充
    FLOOD_FILL   = "flood"      # 洪泛填充 (BFS 同 zone_id 连通)
    REPLACE_FILL = "replace"    # 替换填充 (全局同 zone_id)


class SurfacePainter:
    """管理单个 Body 的涂选状态和操作。"""

    MAX_UNDO = 50

    def __init__(self, body_polydata: vtk.vtkPolyData, renderer: vtk.vtkRenderer, body_actor: vtk.vtkActor):
        self.poly = body_polydata
        self.renderer = renderer
        self.body_actor = body_actor

        # 确保 BoundaryLabel 数组存在
        self.labels = body_polydata.GetCellData().GetArray("BoundaryLabel")
        if self.labels is None:
            self.labels = vtk.vtkIntArray()
            self.labels.SetName("BoundaryLabel")
            self.labels.SetNumberOfTuples(body_polydata.GetNumberOfCells())
            self.labels.Fill(0)
            body_polydata.GetCellData().AddArray(self.labels)
            body_polydata.GetCellData().SetActiveScalars("BoundaryLabel")

        self.undo_stack: List[vtk.vtkIntArray] = []
        self.redo_stack: List[vtk.vtkIntArray] = []

        self.current_label: int = 1
        self.brush_radius_px: int = 20
        self.brush_mode: BrushMode = BrushMode.BRUSH

        self._adjacency: Optional[List[List[int]]] = None  # 懒构建

    # ─── 邻接图 (洪泛填充使用) ───────────────────────────────────

    def _build_adjacency(self):
        """构建 cell 邻接表 (共享边 = ≥2 共同顶点)，缓存结果。"""
        self.poly.BuildLinks()
        n_cells = self.poly.GetNumberOfCells()
        adj: List[List[int]] = [[] for _ in range(n_cells)]
        neighbor_ids = vtk.vtkIdList()

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

    # ─── 主交互入口 ──────────────────────────────────────────────

    def on_press(self, screen_x: int, screen_y: int, erase: bool = False):
        """
        鼠标按下：所有模式都先保存撤销点。
        FILL_ALL / FLOOD_FILL / REPLACE_FILL 单击即完成操作。
        BRUSH 模式画第一笔。
        """
        label = 0 if erase else self.current_label
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
        else:  # BRUSH
            self._paint_brush(screen_x, screen_y, label)

    def on_drag(self, screen_x: int, screen_y: int, erase: bool = False):
        """仅 BRUSH 模式响应拖拽。"""
        if self.brush_mode != BrushMode.BRUSH:
            return
        label = 0 if erase else self.current_label
        self._paint_brush(screen_x, screen_y, label)

    # ─── 具体画刷实现 ────────────────────────────────────────────

    def _paint_brush(self, screen_x: int, screen_y: int, label: int):
        """屏幕空间画刷：将 brush_radius_px 范围内所有可见 cell 设为 label。"""
        cell_ids = self._pick_cells_in_brush(screen_x, screen_y)
        for cid in cell_ids:
            self.labels.SetValue(cid, label)
        if cell_ids:
            self.poly.Modified()

    def _fill_all(self, label: int):
        """全部填充：将当前几何体所有 cell 设为 label。"""
        n = self.poly.GetNumberOfCells()
        for i in range(n):
            self.labels.SetValue(i, label)
        self.poly.Modified()

    def _flood_fill(self, start_cell_id: int, label: int):
        """洪泛填充：BFS 遍历与 start_cell 相同 zone_id 的连通 cell。"""
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
        """替换填充：所有与 cell_id 相同 zone_id 的 cell (无论连通性) 替换为 label。"""
        source_label = self.labels.GetValue(cell_id)
        n = self.poly.GetNumberOfCells()
        for i in range(n):
            if self.labels.GetValue(i) == source_label:
                self.labels.SetValue(i, label)
        self.poly.Modified()

    # ─── 向后兼容接口 ────────────────────────────────────────────

    def paint_at_screen(self, screen_x: int, screen_y: int, label: int):
        """旧接口：等价 BRUSH 模式画一笔。"""
        self._paint_brush(screen_x, screen_y, label)

    def erase_at_screen(self, screen_x: int, screen_y: int):
        """擦除：将画刷内 cell 标记为 0。"""
        self._paint_brush(screen_x, screen_y, 0)

    # ─── 撤销/重做 ──────────────────────────────────────────────

    def save_undo_point(self):
        """保存当前标签状态快照。"""
        snapshot = vtk.vtkIntArray()
        snapshot.DeepCopy(self.labels)
        self.undo_stack.append(snapshot)
        if len(self.undo_stack) > self.MAX_UNDO:
            self.undo_stack.pop(0)
        self.redo_stack.clear()

    def undo(self) -> bool:
        if not self.undo_stack:
            return False
        current = vtk.vtkIntArray()
        current.DeepCopy(self.labels)
        self.redo_stack.append(current)
        prev = self.undo_stack.pop()
        self.labels.DeepCopy(prev)
        self.poly.Modified()
        return True

    def redo(self) -> bool:
        if not self.redo_stack:
            return False
        current = vtk.vtkIntArray()
        current.DeepCopy(self.labels)
        self.undo_stack.append(current)
        nxt = self.redo_stack.pop()
        self.labels.DeepCopy(nxt)
        self.poly.Modified()
        return True

    # ─── 区域查询 ────────────────────────────────────────────────

    def get_zone_cell_ids(self, label: int) -> set:
        """获取指定 label (zone_id) 的所有 cell ID。"""
        ids = set()
        for i in range(self.labels.GetNumberOfTuples()):
            if self.labels.GetValue(i) == label:
                ids.add(i)
        return ids

    def get_all_zone_labels(self) -> set:
        """获取所有非零 label 值。"""
        labels = set()
        for i in range(self.labels.GetNumberOfTuples()):
            v = self.labels.GetValue(i)
            if v != 0:
                labels.add(v)
        return labels

    def set_label_array_from_zones(self, zone_map: dict):
        """
        从 {zone_id: set_of_cell_ids} 恢复标签数组。
        """
        self.labels.Fill(0)
        for label_val, cell_ids in zone_map.items():
            for cid in cell_ids:
                if cid < self.labels.GetNumberOfTuples():
                    self.labels.SetValue(cid, label_val)
        self.poly.Modified()

    # ─── 区域 STL 导出 ──────────────────────────────────────────

    def export_zone_stl(self, label_value: int, output_path: str) -> bool:
        """将指定 label 的三角面提取并导出为 STL。"""
        threshold = vtk.vtkThreshold()
        threshold.SetInputData(self.poly)
        threshold.SetInputArrayToProcess(
            0, 0, 0, vtk.vtkDataObject.FIELD_ASSOCIATION_CELLS, "BoundaryLabel")
        threshold.SetLowerThreshold(label_value)
        threshold.SetUpperThreshold(label_value)
        threshold.Update()

        surface = vtk.vtkDataSetSurfaceFilter()
        surface.SetInputConnection(threshold.GetOutputPort())
        surface.Update()

        if surface.GetOutput().GetNumberOfCells() == 0:
            return False

        writer = vtk.vtkSTLWriter()
        writer.SetFileName(output_path)
        writer.SetInputConnection(surface.GetOutputPort())
        writer.SetFileTypeToBinary()
        writer.Write()
        return True

    # ─── 内部: 硬件拾取 ─────────────────────────────────────────

    def _pick_cells_in_brush(self, sx: int, sy: int) -> List[int]:
        """使用 vtkHardwareSelector 拾取画刷圆内的 cell。"""
        r = self.brush_radius_px
        selector = vtk.vtkHardwareSelector()
        selector.SetRenderer(self.renderer)
        selector.SetArea(sx - r, sy - r, sx + r, sy + r)
        selector.SetFieldAssociation(vtk.vtkDataObject.FIELD_ASSOCIATION_CELLS)

        result = selector.Select()
        if result is None:
            return []

        cell_ids = []
        for node_idx in range(result.GetNumberOfNodes()):
            node = result.GetNode(node_idx)
            if node is None:
                continue
            prop = node.GetProperties().Get(vtk.vtkSelectionNode.PROP())
            if prop is not None and prop != self.body_actor:
                continue
            sel_ids = node.GetSelectionList()
            if sel_ids is None:
                continue
            for i in range(sel_ids.GetNumberOfTuples()):
                cell_ids.append(sel_ids.GetValue(i))
        return cell_ids

    def _pick_single_cell(self, screen_x: int, screen_y: int) -> int:
        """用 1×1 像素区域拾取单个 cell，返回 cell_id；无命中返回 -1。"""
        selector = vtk.vtkHardwareSelector()
        selector.SetRenderer(self.renderer)
        selector.SetArea(screen_x, screen_y, screen_x, screen_y)
        selector.SetFieldAssociation(vtk.vtkDataObject.FIELD_ASSOCIATION_CELLS)
        result = selector.Select()
        if result is None:
            return -1
        for node_idx in range(result.GetNumberOfNodes()):
            node = result.GetNode(node_idx)
            if node is None:
                continue
            prop = node.GetProperties().Get(vtk.vtkSelectionNode.PROP())
            if prop is not None and prop != self.body_actor:
                continue
            sel_ids = node.GetSelectionList()
            if sel_ids and sel_ids.GetNumberOfTuples() > 0:
                return sel_ids.GetValue(0)
        return -1


# ─── zone_id 直接寻址 LUT ───────────────────────────────────────

TYPE_BASE_HUES = {
    'T_BOUNDARY_FOR_SOLID':  0.60,
    'H_BOUNDARY_FOR_SOLID':  0.05,
    'F_BOUNDARY_FOR_SOLID':  0.33,
    'HF_BOUNDARY_FOR_SOLID': 0.80,
}


def _default_zone_color(boundary_type_value: str, same_type_index: int):
    """为区域生成默认 RGBA (0-1) 颜色。"""
    h = TYPE_BASE_HUES.get(boundary_type_value, 0.5)
    h = (h + (same_type_index % 5) * 0.04) % 1.0
    s = 0.80 - (same_type_index // 5) * 0.12
    v = 0.85
    r, g, b = colorsys.hsv_to_rgb(h, max(0.3, s), v)
    return (r, g, b, 1.0)


def build_zone_lut(zones: list, zone_types: Optional[List[str]] = None) -> vtk.vtkLookupTable:
    """
    根据 SurfaceZone 列表构建 zone_id 直接寻址 LUT。

    参数:
        zones: SurfaceZone 列表 (需具有 zone_id, boundary_type, color 属性)
        zone_types: (向后兼容) 如提供且 zones 为 int，按旧逻辑处理
    """
    # 向后兼容: 旧调用方式 build_zone_lut(count, types)
    if isinstance(zones, int):
        return _build_zone_lut_legacy(zones, zone_types)

    if not zones:
        lut = vtk.vtkLookupTable()
        lut.SetNumberOfTableValues(2)
        lut.SetTableValue(0, 0.7, 0.7, 0.7, 1.0)
        lut.SetTableValue(1, 0.7, 0.7, 0.7, 1.0)
        lut.SetTableRange(0, 1)
        lut.Build()
        return lut

    max_id = max(z.zone_id for z in zones)
    lut = vtk.vtkLookupTable()
    lut.SetNumberOfTableValues(max(max_id + 1, 2))
    lut.SetTableValue(0, 0.7, 0.7, 0.7, 1.0)  # 未分配

    # 按 BC 类型统计序号
    type_counters: dict = {}
    for zone in zones:
        bt = zone.boundary_type.value
        idx = type_counters.get(bt, 0)
        type_counters[bt] = idx + 1

        # 使用 zone.color，若为默认灰色则自动生成
        c = zone.color
        if c == (0.7, 0.7, 0.7, 1.0):
            c = _default_zone_color(bt, idx)
        r, g, b = c[0], c[1], c[2]
        lut.SetTableValue(zone.zone_id, r, g, b, 1.0)

    lut.SetTableRange(0, max(max_id, 1))
    lut.Build()
    return lut


def _build_zone_lut_legacy(zone_count: int, zone_types: Optional[List[str]] = None) -> vtk.vtkLookupTable:
    """向后兼容旧版 build_zone_lut(count, types) 调用。"""
    DEFAULT_HUES = [0.60, 0.05, 0.33, 0.80, 0.15, 0.45, 0.70, 0.95]

    n = zone_count + 1
    lut = vtk.vtkLookupTable()
    lut.SetNumberOfTableValues(max(n, 2))
    lut.SetTableValue(0, 0.7, 0.7, 0.7, 1.0)

    for i in range(1, n):
        if zone_types and i - 1 < len(zone_types):
            h = TYPE_BASE_HUES.get(zone_types[i - 1], DEFAULT_HUES[(i - 1) % len(DEFAULT_HUES)])
        else:
            h = DEFAULT_HUES[(i - 1) % len(DEFAULT_HUES)]

        s = 0.7 + 0.2 * ((i - 1) % 3) / 2.0
        v = 0.9 - 0.15 * ((i - 1) % 3)
        r, g, b = colorsys.hsv_to_rgb(h, s, v)
        lut.SetTableValue(i, r, g, b, 1.0)

    lut.SetTableRange(0, max(n - 1, 1))
    lut.Build()
    return lut
