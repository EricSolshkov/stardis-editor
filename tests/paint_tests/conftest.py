"""
conftest.py — paint_tests 测试夹具

提供可复用的 VTK PolyData 和临时场景目录。
"""

import json
import os
import shutil
import tempfile

import pytest
import vtk

# 确保 src/ 可导入
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), os.pardir, os.pardir, "src"))


# ─── VTK 辅助 ────────────────────────────────────────────────────

def _make_triangulated_cube() -> vtk.vtkPolyData:
    """返回一个三角化的单位立方体 (12 三角面)。"""
    cube = vtk.vtkCubeSource()
    cube.Update()
    tri = vtk.vtkTriangleFilter()
    tri.SetInputConnection(cube.GetOutputPort())
    tri.Update()
    poly = vtk.vtkPolyData()
    poly.DeepCopy(tri.GetOutput())
    return poly


def _extract_cells(parent_poly: vtk.vtkPolyData, cell_ids: list) -> vtk.vtkPolyData:
    """从 parent_poly 中提取指定 cell_ids 的子网格。"""
    labels = vtk.vtkIntArray()
    labels.SetName("BoundaryLabel")
    labels.SetNumberOfTuples(parent_poly.GetNumberOfCells())
    labels.Fill(0)
    for cid in cell_ids:
        labels.SetValue(cid, 1)
    parent_poly.GetCellData().AddArray(labels)

    threshold = vtk.vtkThreshold()
    threshold.SetInputData(parent_poly)
    threshold.SetInputArrayToProcess(
        0, 0, 0, vtk.vtkDataObject.FIELD_ASSOCIATION_CELLS, "BoundaryLabel")
    threshold.SetLowerThreshold(1)
    threshold.SetUpperThreshold(1)
    threshold.Update()

    surface = vtk.vtkDataSetSurfaceFilter()
    surface.SetInputConnection(threshold.GetOutputPort())
    surface.Update()

    poly = vtk.vtkPolyData()
    poly.DeepCopy(surface.GetOutput())
    # 清理临时数组，防止污染后续测试
    parent_poly.GetCellData().RemoveArray("BoundaryLabel")
    return poly


def _write_stl(poly: vtk.vtkPolyData, path: str):
    """将 vtkPolyData 写为二进制 STL。"""
    writer = vtk.vtkSTLWriter()
    writer.SetFileName(path)
    writer.SetInputData(poly)
    writer.SetFileTypeToBinary()
    writer.Write()


# ─── Fixtures ────────────────────────────────────────────────────

@pytest.fixture
def parent_poly():
    """12 三角面的三角化立方体。"""
    return _make_triangulated_cube()


@pytest.fixture
def scene_dir(parent_poly):
    """
    创建一个临时场景目录，包含:
      S_FOAM.stl (父体, 12 三角面)
      B_LAT.stl  (子区域, cell 0-3)
      B_TOP.stl  (子区域, cell 4-5)
      scene.txt
    测试结束后自动清理。
    """
    tmpdir = tempfile.mkdtemp(prefix="stardis_test_")

    parent_path = os.path.join(tmpdir, "S_FOAM.stl")
    _write_stl(parent_poly, parent_path)

    child_lat = _extract_cells(parent_poly, [0, 1, 2, 3])
    _write_stl(child_lat, os.path.join(tmpdir, "B_LAT.stl"))

    child_top = _extract_cells(parent_poly, [4, 5])
    _write_stl(child_top, os.path.join(tmpdir, "B_TOP.stl"))

    scene_txt = os.path.join(tmpdir, "scene.txt")
    with open(scene_txt, "w") as f:
        f.write("TRAD 300 300\n")
        f.write("SOLID FOAM 1.0 1.0 1.0 AUTO 300.0 UNKNOWN 0.0 FRONT S_FOAM.stl\n")
        f.write("H_BOUNDARY_FOR_SOLID LAT 300 0.9 0.0 0.0 300.0 B_LAT.stl\n")
        f.write("T_BOUNDARY_FOR_SOLID TOP 500 B_TOP.stl\n")

    yield tmpdir
    shutil.rmtree(tmpdir, ignore_errors=True)


@pytest.fixture
def scene_dir_with_json(scene_dir):
    """在 scene_dir 基础上添加 .stardis_project.json (含 zone_parent_map)。"""
    proj = {
        "zone_parent_map": {"LAT": "FOAM", "TOP": "FOAM"},
        "body_zone_ids": {
            "FOAM": {
                "next_zone_id": 3,
                "zones": [
                    {"zone_id": 1, "name": "LAT"},
                    {"zone_id": 2, "name": "TOP"},
                ],
            }
        },
        "probes": [],
        "cameras": [],
        "lights": [],
        "ambient_intensity": 0.15,
    }
    with open(os.path.join(scene_dir, ".stardis_project.json"), "w") as f:
        json.dump(proj, f)
    return scene_dir
