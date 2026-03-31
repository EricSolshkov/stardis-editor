"""MaterialRef.source_material 序列化往返测试。"""

import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from models.scene_model import (
    SceneModel, Body, VolumeProperties, MaterialRef, BodyType, Side,
)


class TestSourceMaterialField:
    def test_default_empty(self):
        m = MaterialRef()
        assert m.source_material == ""

    def test_assigned(self):
        m = MaterialRef(conductivity=400, density=8960, specific_heat=385,
                        source_material="Copper")
        assert m.source_material == "Copper"


class TestProjectJsonRoundtrip:
    def _make_model(self):
        model = SceneModel()
        model.bodies = [
            Body(name="SHELL", stl_files=["S_SHELL.stl"],
                 volume=VolumeProperties(
                     body_type=BodyType.SOLID,
                     material=MaterialRef(50, 7850, 500, "Steel_Mild"),
                     side=Side.FRONT,
                 )),
            Body(name="AIR", stl_files=["S_AIR.stl"],
                 volume=VolumeProperties(
                     body_type=BodyType.FLUID,
                     material=MaterialRef(0, 1.177, 1005, ""),
                     side=Side.FRONT,
                 )),
        ]
        return model

    def test_save_project_includes_body_materials(self, tmp_path):
        model = self._make_model()
        path = str(tmp_path / "test.stardis_project.json")
        model.save_project(path)

        with open(path, encoding="utf-8") as f:
            data = json.load(f)

        assert "body_materials" in data
        assert data["body_materials"]["SHELL"] == "Steel_Mild"
        assert "AIR" not in data["body_materials"]  # 空串不保存

    def test_load_project_restores_source_material(self, tmp_path):
        # 先保存
        model1 = self._make_model()
        path = str(tmp_path / "test.stardis_project.json")
        model1.save_project(path)

        # 新模型加载（模拟从 scene.txt 解析后再加载 project.json）
        model2 = SceneModel()
        model2.bodies = [
            Body(name="SHELL", stl_files=["S_SHELL.stl"],
                 volume=VolumeProperties(
                     body_type=BodyType.SOLID,
                     material=MaterialRef(50, 7850, 500),
                     side=Side.FRONT,
                 )),
            Body(name="AIR", stl_files=["S_AIR.stl"],
                 volume=VolumeProperties(
                     body_type=BodyType.FLUID,
                     material=MaterialRef(0, 1.177, 1005),
                     side=Side.FRONT,
                 )),
        ]
        model2.load_project(path)

        assert model2.get_body_by_name("SHELL").volume.material.source_material == "Steel_Mild"
        assert model2.get_body_by_name("AIR").volume.material.source_material == ""

    def test_load_old_project_without_body_materials(self, tmp_path):
        """旧项目文件无 body_materials 字段 → 向后兼容。"""
        path = str(tmp_path / "old.stardis_project.json")
        with open(path, "w") as f:
            json.dump({"probes": [], "cameras": [], "body_zone_ids": {}}, f)

        model = SceneModel()
        model.bodies = [
            Body(name="SHELL", volume=VolumeProperties(
                material=MaterialRef(50, 7850, 500))),
        ]
        model.load_project(path)
        assert model.get_body_by_name("SHELL").volume.material.source_material == ""
