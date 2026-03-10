"""
test_scene_writer.py — SceneWriter 统一 B_*.stl 导出测试

覆盖:
  - PaintedRegion zone → B_<name>.stl（通过 vtkThreshold 提取）
  - ImportedSTL zone → B_<name>.stl（直接拷贝）
  - zone_parent_map 写入 JSON
  - B_*.stl 文件命名规范
"""

import json
import os
import sys
import tempfile
import shutil

import pytest
import vtk

sys.path.insert(0, os.path.join(os.path.dirname(__file__), os.pardir, os.pardir, "src"))

from models.scene_model import (
    SceneModel, Body, SurfaceZone,
    PaintedRegion, ImportedSTL,
    TemperatureBC,
)
from parsers.scene_writer import SceneWriter


def _make_simple_poly(n_triangles=4):
    """创建一个带 n 个三角形的简单 vtkPolyData。"""
    points = vtk.vtkPoints()
    cells = vtk.vtkCellArray()
    for i in range(n_triangles):
        p0 = points.InsertNextPoint(0, 0, i)
        p1 = points.InsertNextPoint(1, 0, i)
        p2 = points.InsertNextPoint(0, 1, i)
        tri = vtk.vtkTriangle()
        tri.GetPointIds().SetId(0, p0)
        tri.GetPointIds().SetId(1, p1)
        tri.GetPointIds().SetId(2, p2)
        cells.InsertNextCell(tri)
    poly = vtk.vtkPolyData()
    poly.SetPoints(points)
    poly.SetPolys(cells)
    return poly


def _write_temp_stl(poly, path):
    writer = vtk.vtkSTLWriter()
    writer.SetFileName(path)
    writer.SetInputData(poly)
    writer.Write()


@pytest.fixture
def output_dir():
    d = tempfile.mkdtemp(prefix="writer_test_")
    yield d
    shutil.rmtree(d, ignore_errors=True)


@pytest.fixture
def model_painted(output_dir):
    """带 PaintedRegion zone 的 SceneModel。"""
    parent_poly = _make_simple_poly(6)
    parent_stl = os.path.join(output_dir, "S_BLOCK.stl")
    _write_temp_stl(parent_poly, parent_stl)

    m = SceneModel()
    body = Body(name="BLOCK")
    body.stl_files = [parent_stl]

    zone = SurfaceZone(name="HOT", zone_id=1)
    zone.bc = TemperatureBC(temperature=500.0)
    zone.source = PaintedRegion(cell_ids={0, 1, 2})
    body.surface_zones.append(zone)
    body.next_zone_id = 2

    m.bodies.append(body)
    return m


@pytest.fixture
def model_imported(output_dir):
    """带 ImportedSTL zone 的 SceneModel。"""
    parent_poly = _make_simple_poly(6)
    parent_stl = os.path.join(output_dir, "S_WALL.stl")
    _write_temp_stl(parent_poly, parent_stl)

    child_poly = _make_simple_poly(3)
    child_stl = os.path.join(output_dir, "B_WARM.stl")
    _write_temp_stl(child_poly, child_stl)

    m = SceneModel()
    body = Body(name="WALL")
    body.stl_files = [parent_stl]

    zone = SurfaceZone(name="WARM", zone_id=1)
    zone.bc = TemperatureBC(temperature=300.0)
    zone.source = ImportedSTL(stl_file=child_stl)
    body.surface_zones.append(zone)
    body.next_zone_id = 2

    m.bodies.append(body)
    return m


class TestWriterPaintedRegion:
    """PaintedRegion → B_*.stl 导出。"""

    def test_boundary_stl_created(self, model_painted, output_dir):
        writer = SceneWriter()
        writer.save(model_painted, output_dir, "scene.txt")
        assert os.path.isfile(os.path.join(output_dir, "B_HOT.stl"))

    def test_boundary_stl_triangle_count(self, model_painted, output_dir):
        """导出的 B_HOT.stl 应包含 3 个三角形（cell_ids = {0,1,2}）。"""
        writer = SceneWriter()
        writer.save(model_painted, output_dir, "scene.txt")

        reader = vtk.vtkSTLReader()
        reader.SetFileName(os.path.join(output_dir, "B_HOT.stl"))
        reader.Update()
        assert reader.GetOutput().GetNumberOfCells() == 3

    def test_zone_parent_map_in_json(self, model_painted, output_dir):
        writer = SceneWriter()
        writer.save(model_painted, output_dir, "scene.txt")

        json_path = os.path.join(output_dir, ".stardis_project.json")
        assert os.path.isfile(json_path)
        with open(json_path) as f:
            proj = json.load(f)
        assert proj["zone_parent_map"]["HOT"] == "BLOCK"


class TestWriterImportedSTL:
    """ImportedSTL → B_*.stl 拷贝。"""

    def test_boundary_stl_created(self, model_imported, output_dir):
        writer = SceneWriter()
        writer.save(model_imported, output_dir, "scene.txt")
        assert os.path.isfile(os.path.join(output_dir, "B_WARM.stl"))

    def test_zone_parent_map_includes_imported(self, model_imported, output_dir):
        writer = SceneWriter()
        writer.save(model_imported, output_dir, "scene.txt")

        with open(os.path.join(output_dir, ".stardis_project.json")) as f:
            proj = json.load(f)
        assert proj["zone_parent_map"]["WARM"] == "WALL"
