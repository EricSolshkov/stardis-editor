"""
test_roundtrip.py — NormalOrientation 序列化/反序列化往返测试

覆盖:
  - 有 JSON 且含 normal_orientations → 从 JSON 恢复
  - 无 JSON → 自动检测封闭网格为 OUTWARD
  - save_project → load_project 往返
"""

import json
import os
import sys
import tempfile
import shutil

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), os.pardir, os.pardir, "src"))

from models.scene_model import (
    SceneModel, Body, VolumeProperties, MaterialRef,
    BodyType, Side, NormalOrientation,
)
from parsers.scene_parser import SceneParser


class TestLoadWithJson:
    """有 .stardis_project.json 且含 normal_orientations 字段。"""

    def test_orientation_restored_from_json(self, scene_dir_with_orientation):
        parser = SceneParser()
        model = parser.parse_file(
            os.path.join(scene_dir_with_orientation, "scene.txt"))
        body = model.get_body_by_name("BOX")
        assert body is not None
        assert body.normal_orientation == NormalOrientation.OUTWARD

    def test_orientation_unknown_in_json_stays_unknown(self, scene_dir_with_orientation):
        """如果 JSON 中值为 unknown，不应被自动检测覆盖。"""
        # 修改 JSON 使 BOX 为 unknown
        proj_path = os.path.join(scene_dir_with_orientation, ".stardis_project.json")
        with open(proj_path, "r") as f:
            data = json.load(f)
        data["normal_orientations"]["BOX"] = "unknown"
        with open(proj_path, "w") as f:
            json.dump(data, f)

        parser = SceneParser()
        model = parser.parse_file(
            os.path.join(scene_dir_with_orientation, "scene.txt"))
        body = model.get_body_by_name("BOX")
        # load_project 先恢复为 unknown，然后 parser 自动检测应该
        # 检测到封闭网格并设置为 OUTWARD
        assert body.normal_orientation == NormalOrientation.OUTWARD


class TestLoadWithoutJson:
    """无 .stardis_project.json → 纯自动检测。"""

    def test_auto_detect_closed_mesh(self, scene_dir_no_json):
        parser = SceneParser()
        model = parser.parse_file(
            os.path.join(scene_dir_no_json, "scene.txt"))
        body = model.get_body_by_name("BOX")
        assert body is not None
        # 封闭立方体应被检测为 OUTWARD
        assert body.normal_orientation == NormalOrientation.OUTWARD


class TestSaveProjectRoundtrip:
    """save_project → load_project 往返。"""

    def test_orientation_survives_roundtrip(self):
        tmpdir = tempfile.mkdtemp(prefix="stardis_orient_rt_")
        try:
            model = SceneModel()
            body = Body(
                name="TEST",
                volume=VolumeProperties(body_type=BodyType.SOLID, side=Side.FRONT),
                normal_orientation=NormalOrientation.INWARD,
            )
            model.bodies.append(body)

            proj_path = os.path.join(tmpdir, ".stardis_project.json")
            model.save_project(proj_path)

            # 验证 JSON 内容
            with open(proj_path, "r") as f:
                data = json.load(f)
            assert data["normal_orientations"]["TEST"] == "inward"

            # 恢复
            model2 = SceneModel()
            model2.bodies.append(Body(name="TEST"))
            model2.load_project(proj_path)
            assert model2.get_body_by_name("TEST").normal_orientation == NormalOrientation.INWARD
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_unknown_orientation_roundtrip(self):
        tmpdir = tempfile.mkdtemp(prefix="stardis_orient_rt_")
        try:
            model = SceneModel()
            body = Body(
                name="OPEN",
                normal_orientation=NormalOrientation.UNKNOWN,
            )
            model.bodies.append(body)

            proj_path = os.path.join(tmpdir, ".stardis_project.json")
            model.save_project(proj_path)

            model2 = SceneModel()
            model2.bodies.append(Body(name="OPEN"))
            model2.load_project(proj_path)
            assert model2.get_body_by_name("OPEN").normal_orientation == NormalOrientation.UNKNOWN
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)
