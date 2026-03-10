"""
三角形哈希匹配器 — 通过顶点坐标哈希建立父子 STL 之间的单元映射。

用途:
  加载场景时，从子 STL (B_*.stl) 还原涂选状态，即确定子 STL 的每个三角面
  对应父 Body STL 中的哪个 cell_id。

原理:
  STL 三角面由三个顶点坐标唯一确定。对顶点坐标排序后取哈希，
  可在 O(1) 内实现父子三角面匹配。
"""

import hashlib
from typing import Dict, Set, Tuple

import vtk


def _triangle_hash(poly: vtk.vtkPolyData, cell_id: int, precision: int = 6) -> str:
    """
    计算单个三角面的哈希值。
    将三个顶点坐标四舍五入到 precision 位小数后，按字典序排序，
    拼接为字符串取 SHA-256 摘要。
    """
    cell = poly.GetCell(cell_id)
    pts = []
    for i in range(cell.GetNumberOfPoints()):
        pid = cell.GetPointId(i)
        x, y, z = poly.GetPoint(pid)
        pts.append((round(x, precision), round(y, precision), round(z, precision)))
    pts.sort()
    key = str(pts)
    return hashlib.sha256(key.encode()).hexdigest()


def build_parent_hash_map(parent_poly: vtk.vtkPolyData,
                          precision: int = 6) -> Dict[str, int]:
    """
    为父 STL 构建哈希表: { triangle_hash → cell_id }
    复杂度: O(n_parent)
    """
    hash_map: Dict[str, int] = {}
    for cid in range(parent_poly.GetNumberOfCells()):
        h = _triangle_hash(parent_poly, cid, precision)
        hash_map[h] = cid
    return hash_map


def match_child_to_parent(parent_poly: vtk.vtkPolyData,
                          child_poly: vtk.vtkPolyData,
                          precision: int = 6,
                          parent_hash_map: Dict[str, int] = None,
                          ) -> Tuple[Set[int], int]:
    """
    通过三角形哈希匹配，返回子 STL 在父 STL 中对应的 cell_id 集合。

    Args:
        parent_poly: 父 Body 的 vtkPolyData
        child_poly: 子边界 STL 的 vtkPolyData
        precision: 坐标舍入精度（小数位数）
        parent_hash_map: 可选，预构建的父哈希表（多个子 STL 共享同一父体时复用）

    Returns:
        (matched_cell_ids, unmatched_count)
        matched_cell_ids: 子三角面在父 STL 中的 cell_id 集合
        unmatched_count: 未匹配的子三角面数量（用于警告）
    """
    if parent_hash_map is None:
        parent_hash_map = build_parent_hash_map(parent_poly, precision)

    matched: Set[int] = set()
    unmatched = 0

    for cid in range(child_poly.GetNumberOfCells()):
        h = _triangle_hash(child_poly, cid, precision)
        parent_cid = parent_hash_map.get(h)
        if parent_cid is not None:
            matched.add(parent_cid)
        else:
            unmatched += 1

    return matched, unmatched


def load_stl_polydata(stl_path: str) -> vtk.vtkPolyData:
    """加载 STL 文件并返回 vtkPolyData。"""
    reader = vtk.vtkSTLReader()
    reader.SetFileName(stl_path)
    reader.Update()
    poly = vtk.vtkPolyData()
    poly.DeepCopy(reader.GetOutput())
    return poly
