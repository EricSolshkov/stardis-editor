"""
test_roundtrip.py — 完整保存/加载往返测试

覆盖:
  - 有 JSON 时: zone_parent_map → 哈希匹配 → cell_ids 恢复
  - 无 JSON 时: 单 Body 自动归入 → 哈希匹配 → cell_ids 恢复
  - 多 zone 同 body 的恢复
  - zone_id / next_zone_id 持久化
  - 解析器 warnings 检查
"""

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), os.pardir, os.pardir, "src"))

from models.scene_model import PaintedRegion, ImportedSTL
from parsers.scene_parser import SceneParser


class TestRoundtripWithJson:
    """有 .stardis_project.json 的往返测试。"""

    def test_cell_ids_recovered(self, scene_dir_with_json):
        parser = SceneParser()
        model = parser.parse_file(os.path.join(scene_dir_with_json, "scene.txt"))
        body = model.get_body_by_name("FOAM")

        lat = model.get_zone("FOAM", "LAT")
        assert isinstance(lat.source, PaintedRegion)
        assert lat.source.cell_ids == {0, 1, 2, 3}

        top = model.get_zone("FOAM", "TOP")
        assert isinstance(top.source, PaintedRegion)
        assert top.source.cell_ids == {4, 5}

    def test_zone_ids_restored(self, scene_dir_with_json):
        parser = SceneParser()
        model = parser.parse_file(os.path.join(scene_dir_with_json, "scene.txt"))

        lat = model.get_zone("FOAM", "LAT")
        assert lat.zone_id == 1

        top = model.get_zone("FOAM", "TOP")
        assert top.zone_id == 2

    def test_next_zone_id_restored(self, scene_dir_with_json):
        parser = SceneParser()
        model = parser.parse_file(os.path.join(scene_dir_with_json, "scene.txt"))
        body = model.get_body_by_name("FOAM")
        assert body.next_zone_id == 3

    def test_no_warnings(self, scene_dir_with_json):
        parser = SceneParser()
        parser.parse_file(os.path.join(scene_dir_with_json, "scene.txt"))
        assert parser.warnings == []


class TestRoundtripWithoutJson:
    """无 .stardis_project.json 的往返测试 (单 Body 自动归入)。"""

    def test_cell_ids_recovered_single_body(self, scene_dir):
        """单 Body 场景无 JSON 时，所有 boundary 自动归入唯一 Body。"""
        parser = SceneParser()
        model = parser.parse_file(os.path.join(scene_dir, "scene.txt"))

        lat = model.get_zone("FOAM", "LAT")
        assert isinstance(lat.source, PaintedRegion)
        assert lat.source.cell_ids == {0, 1, 2, 3}

        top = model.get_zone("FOAM", "TOP")
        assert isinstance(top.source, PaintedRegion)
        assert top.source.cell_ids == {4, 5}

    def test_no_unresolved_single_body(self, scene_dir):
        parser = SceneParser()
        parser.parse_file(os.path.join(scene_dir, "scene.txt"))
        assert parser.unresolved_boundaries == []


class TestRoundtripSaveAndReload:
    """保存后重新加载，验证涂选数据完整往返。"""

    def test_paint_survives_save_reload(self, scene_dir_with_json):
        """涂选 → 保存 → 重新加载 → 涂选恢复。"""
        from parsers.scene_writer import SceneWriter

        # 1. 加载
        parser = SceneParser()
        model = parser.parse_file(os.path.join(scene_dir_with_json, "scene.txt"))

        # 验证初始加载正确
        lat = model.get_zone("FOAM", "LAT")
        assert isinstance(lat.source, PaintedRegion)
        original_ids = lat.source.cell_ids.copy()

        # 2. 保存到新目录
        import tempfile, shutil
        save_dir = tempfile.mkdtemp(prefix="stardis_save_")
        try:
            writer = SceneWriter()
            writer.save(model, save_dir, "scene.txt")

            # 验证 B_LAT.stl 存在
            assert os.path.isfile(os.path.join(save_dir, "B_LAT.stl"))
            assert os.path.isfile(os.path.join(save_dir, "B_TOP.stl"))

            # 验证 JSON 中有 zone_parent_map
            with open(os.path.join(save_dir, ".stardis_project.json")) as f:
                proj = json.load(f)
            assert proj["zone_parent_map"]["LAT"] == "FOAM"

            # 3. 重新加载
            parser2 = SceneParser()
            model2 = parser2.parse_file(os.path.join(save_dir, "scene.txt"))

            lat2 = model2.get_zone("FOAM", "LAT")
            assert isinstance(lat2.source, PaintedRegion)
            assert lat2.source.cell_ids == original_ids
        finally:
            shutil.rmtree(save_dir, ignore_errors=True)
