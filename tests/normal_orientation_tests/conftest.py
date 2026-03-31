"""
conftest.py — normal_orientation_tests 测试夹具
"""

import json
import os
import shutil
import tempfile

import pytest
import vtk

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), os.pardir, os.pardir, "src"))


def _make_triangulated_cube() -> vtk.vtkPolyData:
    """返回一个三角化的单位立方体 (12 三角面，法线朝外)。"""
    cube = vtk.vtkCubeSource()
    cube.Update()
    tri = vtk.vtkTriangleFilter()
    tri.SetInputConnection(cube.GetOutputPort())
    tri.Update()
    poly = vtk.vtkPolyData()
    poly.DeepCopy(tri.GetOutput())
    return poly


def _make_open_mesh() -> vtk.vtkPolyData:
    """返回一个开放网格（从立方体移除部分三角面）。"""
    cube = _make_triangulated_cube()
    # 提取前 8 个面 (12 面立方体去掉 4 面变为开放)
    ids = vtk.vtkIdTypeArray()
    ids.SetNumberOfTuples(8)
    for i in range(8):
        ids.SetValue(i, i)

    selection_node = vtk.vtkSelectionNode()
    selection_node.SetFieldType(vtk.vtkSelectionNode.CELL)
    selection_node.SetContentType(vtk.vtkSelectionNode.INDICES)
    selection_node.SetSelectionList(ids)

    selection = vtk.vtkSelection()
    selection.AddNode(selection_node)

    extractor = vtk.vtkExtractSelection()
    extractor.SetInputData(0, cube)
    extractor.SetInputData(1, selection)
    extractor.Update()

    surface = vtk.vtkDataSetSurfaceFilter()
    surface.SetInputConnection(extractor.GetOutputPort())
    surface.Update()

    poly = vtk.vtkPolyData()
    poly.DeepCopy(surface.GetOutput())
    return poly


def _write_stl(poly: vtk.vtkPolyData, path: str):
    writer = vtk.vtkSTLWriter()
    writer.SetFileName(path)
    writer.SetInputData(poly)
    writer.SetFileTypeToBinary()
    writer.Write()


@pytest.fixture
def closed_cube_poly():
    """12 三角面的三角化立方体（封闭，法线朝外）。"""
    return _make_triangulated_cube()


@pytest.fixture
def open_mesh_poly():
    """开放网格（不封闭）。"""
    return _make_open_mesh()


@pytest.fixture
def closed_cube_stl(closed_cube_poly):
    """封闭立方体的临时 STL 文件路径。"""
    tmpdir = tempfile.mkdtemp(prefix="stardis_normal_test_")
    path = os.path.join(tmpdir, "cube.stl")
    _write_stl(closed_cube_poly, path)
    yield path
    shutil.rmtree(tmpdir, ignore_errors=True)


@pytest.fixture
def open_mesh_stl(open_mesh_poly):
    """开放网格的临时 STL 文件路径。"""
    tmpdir = tempfile.mkdtemp(prefix="stardis_normal_test_")
    path = os.path.join(tmpdir, "open.stl")
    _write_stl(open_mesh_poly, path)
    yield path
    shutil.rmtree(tmpdir, ignore_errors=True)


@pytest.fixture
def scene_dir_with_orientation(closed_cube_poly):
    """
    临时场景目录，含:
      S_BOX.stl (封闭立方体)
      scene.txt
      .stardis_project.json (含 normal_orientations)
    """
    tmpdir = tempfile.mkdtemp(prefix="stardis_orient_test_")

    parent_path = os.path.join(tmpdir, "S_BOX.stl")
    _write_stl(closed_cube_poly, parent_path)

    scene_txt = os.path.join(tmpdir, "scene.txt")
    with open(scene_txt, "w") as f:
        f.write("TRAD 300 300\n")
        f.write("SOLID BOX 1.0 1.0 1.0 AUTO 300.0 UNKNOWN 0.0 FRONT S_BOX.stl\n")

    proj = {
        "zone_parent_map": {},
        "body_zone_ids": {
            "BOX": {"next_zone_id": 1, "zones": []}
        },
        "probes": [],
        "cameras": [],
        "lights": [],
        "ambient_intensity": 0.15,
        "normal_orientations": {"BOX": "outward"},
    }
    with open(os.path.join(tmpdir, ".stardis_project.json"), "w") as f:
        json.dump(proj, f)

    yield tmpdir
    shutil.rmtree(tmpdir, ignore_errors=True)


@pytest.fixture
def scene_dir_no_json(closed_cube_poly):
    """
    临时场景目录，无 project JSON（测试自动检测）:
      S_BOX.stl (封闭立方体)
      scene.txt
    """
    tmpdir = tempfile.mkdtemp(prefix="stardis_orient_test_")

    parent_path = os.path.join(tmpdir, "S_BOX.stl")
    _write_stl(closed_cube_poly, parent_path)

    scene_txt = os.path.join(tmpdir, "scene.txt")
    with open(scene_txt, "w") as f:
        f.write("TRAD 300 300\n")
        f.write("SOLID BOX 1.0 1.0 1.0 AUTO 300.0 UNKNOWN 0.0 FRONT S_BOX.stl\n")

    yield tmpdir
    shutil.rmtree(tmpdir, ignore_errors=True)
