"""
test_save_project.py — save_project / zone_parent_map 序列化测试

覆盖:
  - zone_parent_map 正确写入
  - cell_ids 不在 JSON 中
  - body_zone_ids 结构正确
"""

import json
import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), os.pardir, os.pardir, "src"))

from models.scene_model import (
    SceneModel, Body, SurfaceZone, PaintedRegion, ImportedSTL,
    BoundaryType, ConvectionBC, TemperatureBC,
)


class TestSaveProject:
    """save_project 输出格式验证。"""

    @pytest.fixture
    def model_with_painted_zones(self):
        model = SceneModel()
        body = Body(name="FOAM", stl_files=["S_FOAM.stl"])
        body.next_zone_id = 3
        body.surface_zones = [
            SurfaceZone(
                zone_id=1, name="LAT",
                source=PaintedRegion(cell_ids={0, 1, 2, 3}),
                boundary_type=BoundaryType.H_BOUNDARY,
                boundary=ConvectionBC(),
            ),
            SurfaceZone(
                zone_id=2, name="TOP",
                source=PaintedRegion(cell_ids={4, 5}),
                boundary_type=BoundaryType.T_BOUNDARY,
                boundary=TemperatureBC(temperature=500),
            ),
        ]
        model.bodies.append(body)
        return model

    def test_zone_parent_map_present(self, model_with_painted_zones, tmp_path):
        path = str(tmp_path / ".stardis_project.json")
        model_with_painted_zones.save_project(path)
        with open(path) as f:
            data = json.load(f)
        assert "zone_parent_map" in data
        assert data["zone_parent_map"]["LAT"] == "FOAM"
        assert data["zone_parent_map"]["TOP"] == "FOAM"

    def test_cell_ids_not_in_json(self, model_with_painted_zones, tmp_path):
        path = str(tmp_path / ".stardis_project.json")
        model_with_painted_zones.save_project(path)
        with open(path) as f:
            data = json.load(f)
        for zone_data in data["body_zone_ids"]["FOAM"]["zones"]:
            assert "cell_ids" not in zone_data

    def test_body_zone_ids_structure(self, model_with_painted_zones, tmp_path):
        path = str(tmp_path / ".stardis_project.json")
        model_with_painted_zones.save_project(path)
        with open(path) as f:
            data = json.load(f)
        bdata = data["body_zone_ids"]["FOAM"]
        assert bdata["next_zone_id"] == 3
        zone_names = {z["name"] for z in bdata["zones"]}
        assert zone_names == {"LAT", "TOP"}
        zone_ids = {z["zone_id"] for z in bdata["zones"]}
        assert zone_ids == {1, 2}

    def test_imported_stl_zone_also_in_parent_map(self, tmp_path):
        """ImportedSTL 类型的 zone 也应出现在 zone_parent_map 中。"""
        model = SceneModel()
        body = Body(name="WALL", stl_files=["S_WALL.stl"])
        body.surface_zones.append(SurfaceZone(
            zone_id=1, name="EXT",
            source=ImportedSTL(stl_file="B_EXT.stl"),
            boundary_type=BoundaryType.H_BOUNDARY,
        ))
        body.next_zone_id = 2
        model.bodies.append(body)

        path = str(tmp_path / ".stardis_project.json")
        model.save_project(path)
        with open(path) as f:
            data = json.load(f)
        assert data["zone_parent_map"]["EXT"] == "WALL"

    def test_multi_body_parent_map(self, tmp_path):
        """多几何体场景下 zone_parent_map 正确区分归属。"""
        model = SceneModel()
        b1 = Body(name="WALL", stl_files=["S_WALL.stl"])
        b1.surface_zones.append(SurfaceZone(zone_id=1, name="WALL_EXT"))
        b1.next_zone_id = 2
        b2 = Body(name="ROOF", stl_files=["S_ROOF.stl"])
        b2.surface_zones.append(SurfaceZone(zone_id=1, name="ROOF_TOP"))
        b2.next_zone_id = 2
        model.bodies.extend([b1, b2])

        path = str(tmp_path / ".stardis_project.json")
        model.save_project(path)
        with open(path) as f:
            data = json.load(f)
        assert data["zone_parent_map"]["WALL_EXT"] == "WALL"
        assert data["zone_parent_map"]["ROOF_TOP"] == "ROOF"
