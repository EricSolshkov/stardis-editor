"""
test_detect_orientation.py — 法线朝向检测函数测试

覆盖:
  - 封闭网格（VTK 立方体）→ OUTWARD
  - 开放网格 → UNKNOWN
  - 文件不存在 → UNKNOWN
  - 空 PolyData → UNKNOWN
"""

import os
import sys

import pytest
import vtk

sys.path.insert(0, os.path.join(os.path.dirname(__file__), os.pardir, os.pardir, "src"))

from models.scene_model import (
    NormalOrientation,
    detect_normal_orientation,
    detect_normal_orientation_from_polydata,
)


class TestDetectFromPolyData:
    """直接对 vtkPolyData 检测。"""

    def test_closed_cube_is_outward(self, closed_cube_poly):
        """VTK CubeSource 法线默认朝外。"""
        result = detect_normal_orientation_from_polydata(closed_cube_poly)
        assert result == NormalOrientation.OUTWARD

    def test_open_mesh_is_unknown(self, open_mesh_poly):
        """开放网格不封闭，应返回 UNKNOWN。"""
        result = detect_normal_orientation_from_polydata(open_mesh_poly)
        assert result == NormalOrientation.UNKNOWN

    def test_empty_polydata_is_unknown(self):
        """空 PolyData 应返回 UNKNOWN。"""
        poly = vtk.vtkPolyData()
        result = detect_normal_orientation_from_polydata(poly)
        assert result == NormalOrientation.UNKNOWN

    def test_none_polydata_is_unknown(self):
        """None 输入应返回 UNKNOWN。"""
        result = detect_normal_orientation_from_polydata(None)
        assert result == NormalOrientation.UNKNOWN

    def test_inverted_normals_is_inward(self, closed_cube_poly):
        """翻转法线后应检测为 INWARD。"""
        reverse = vtk.vtkReverseSense()
        reverse.SetInputData(closed_cube_poly)
        reverse.ReverseCellsOn()
        reverse.ReverseNormalsOn()
        reverse.Update()
        inverted = vtk.vtkPolyData()
        inverted.DeepCopy(reverse.GetOutput())
        result = detect_normal_orientation_from_polydata(inverted)
        assert result == NormalOrientation.INWARD


class TestDetectFromFile:
    """从 STL 文件检测。"""

    def test_closed_cube_stl(self, closed_cube_stl):
        result = detect_normal_orientation(closed_cube_stl)
        assert result == NormalOrientation.OUTWARD

    def test_open_mesh_stl(self, open_mesh_stl):
        result = detect_normal_orientation(open_mesh_stl)
        assert result == NormalOrientation.UNKNOWN

    def test_nonexistent_file(self):
        result = detect_normal_orientation("/nonexistent/path.stl")
        assert result == NormalOrientation.UNKNOWN
