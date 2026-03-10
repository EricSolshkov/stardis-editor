"""
test_triangle_hash_matcher.py — 三角形哈希匹配器单元测试

覆盖:
  - 哈希确定性
  - 父子 STL 精确匹配
  - 部分匹配 / 零匹配场景
  - 预构建哈希表复用
"""

import os
import sys

import pytest
import vtk

sys.path.insert(0, os.path.join(os.path.dirname(__file__), os.pardir, os.pardir, "src"))

from parsers.triangle_hash_matcher import (
    _triangle_hash,
    build_parent_hash_map,
    match_child_to_parent,
    load_stl_polydata,
)
from tests.paint_tests.conftest import _make_triangulated_cube, _extract_cells, _write_stl


class TestTriangleHash:
    """_triangle_hash 确定性与正确性。"""

    def test_same_cell_same_hash(self, parent_poly):
        h1 = _triangle_hash(parent_poly, 0)
        h2 = _triangle_hash(parent_poly, 0)
        assert h1 == h2

    def test_different_cells_different_hash(self, parent_poly):
        h0 = _triangle_hash(parent_poly, 0)
        h1 = _triangle_hash(parent_poly, 1)
        assert h0 != h1

    def test_hash_is_sha256_hex(self, parent_poly):
        h = _triangle_hash(parent_poly, 0)
        assert len(h) == 64  # SHA-256 hex digest


class TestBuildParentHashMap:
    """build_parent_hash_map 构建正确性。"""

    def test_map_size_equals_cell_count(self, parent_poly):
        hmap = build_parent_hash_map(parent_poly)
        assert len(hmap) == parent_poly.GetNumberOfCells()

    def test_all_cell_ids_present(self, parent_poly):
        hmap = build_parent_hash_map(parent_poly)
        cell_ids = set(hmap.values())
        expected = set(range(parent_poly.GetNumberOfCells()))
        assert cell_ids == expected


class TestMatchChildToParent:
    """match_child_to_parent 匹配场景。"""

    def test_full_match(self, parent_poly):
        """子网格所有三角面都能在父体中找到。"""
        child = _extract_cells(parent_poly, [0, 1, 2, 3])
        matched, unmatched = match_child_to_parent(parent_poly, child)
        assert matched == {0, 1, 2, 3}
        assert unmatched == 0

    def test_single_cell_match(self, parent_poly):
        """只有一个三角面的子网格。"""
        child = _extract_cells(parent_poly, [7])
        matched, unmatched = match_child_to_parent(parent_poly, child)
        assert matched == {7}
        assert unmatched == 0

    def test_all_cells_match(self, parent_poly):
        """子网格 == 父网格（全覆盖）。"""
        all_ids = list(range(parent_poly.GetNumberOfCells()))
        child = _extract_cells(parent_poly, all_ids)
        matched, unmatched = match_child_to_parent(parent_poly, child)
        assert matched == set(all_ids)
        assert unmatched == 0

    def test_empty_child(self, parent_poly):
        """空子网格。"""
        empty = vtk.vtkPolyData()
        matched, unmatched = match_child_to_parent(parent_poly, empty)
        assert matched == set()
        assert unmatched == 0

    def test_reuse_parent_hash_map(self, parent_poly):
        """预构建的哈希表可以被多个子网格复用。"""
        hmap = build_parent_hash_map(parent_poly)

        child_a = _extract_cells(parent_poly, [0, 1])
        child_b = _extract_cells(parent_poly, [4, 5, 6])

        ma, ua = match_child_to_parent(parent_poly, child_a, parent_hash_map=hmap)
        mb, ub = match_child_to_parent(parent_poly, child_b, parent_hash_map=hmap)

        assert ma == {0, 1} and ua == 0
        assert mb == {4, 5, 6} and ub == 0

    def test_foreign_child_no_match(self):
        """子网格来自完全不同的几何体，应全部 unmatched。"""
        cube = _make_triangulated_cube()
        sphere_src = vtk.vtkSphereSource()
        sphere_src.SetRadius(5.0)
        sphere_src.SetThetaResolution(8)
        sphere_src.SetPhiResolution(8)
        sphere_src.Update()
        sphere = sphere_src.GetOutput()

        matched, unmatched = match_child_to_parent(cube, sphere)
        assert len(matched) == 0
        assert unmatched == sphere.GetNumberOfCells()


class TestLoadStlPolydata:
    """load_stl_polydata 文件读取。"""

    def test_roundtrip(self, parent_poly, tmp_path):
        stl_path = str(tmp_path / "test.stl")
        _write_stl(parent_poly, stl_path)
        loaded = load_stl_polydata(stl_path)
        assert loaded.GetNumberOfCells() == parent_poly.GetNumberOfCells()
