"""MaterialDatabase 单元测试。"""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from models.material_database import (
    Material, MaterialDatabase, is_valid_material_name, _BUILTIN_MATERIALS,
)


# ─── is_valid_material_name ─────────────────────────────────────

class TestNameValidation:
    def test_valid_names(self):
        assert is_valid_material_name("Copper")
        assert is_valid_material_name("Steel_Mild")
        assert is_valid_material_name("A123")
        assert is_valid_material_name("a")

    def test_invalid_names(self):
        assert not is_valid_material_name("")
        assert not is_valid_material_name("has space")
        assert not is_valid_material_name("has-dash")
        assert not is_valid_material_name("特殊字符")
        assert not is_valid_material_name("a.b")


# ─── MaterialDatabase 创建 ──────────────────────────────────────

class TestDatabaseCreation:
    def test_create_default_has_builtins(self):
        db = MaterialDatabase.create_default()
        assert db.contains("Copper")
        assert db.contains("Air_300K")
        assert len(db.list_all()) == len(_BUILTIN_MATERIALS)

    def test_builtin_are_marked(self):
        db = MaterialDatabase.create_default()
        copper = db.get("Copper")
        assert copper is not None
        assert copper.is_builtin is True

    def test_categories_present(self):
        db = MaterialDatabase.create_default()
        cats = db.categories()
        assert "金属" in cats
        assert "流体" in cats
        assert "绝缘体" in cats

    def test_list_by_category(self):
        db = MaterialDatabase.create_default()
        metals = db.list_by_category("金属")
        assert len(metals) > 0
        assert all(m.category == "金属" for m in metals)

    def test_all_names(self):
        db = MaterialDatabase.create_default()
        names = db.all_names()
        assert "Copper" in names
        assert names == sorted(names)


# ─── CRUD ────────────────────────────────────────────────────────

class TestCRUD:
    def _make_db(self):
        return MaterialDatabase.create_default()

    def test_add_custom(self):
        db = self._make_db()
        m = Material(name="TestAlloy", conductivity=45, density=7200, specific_heat=460,
                     category="自定义")
        assert db.add(m) is True
        assert db.contains("TestAlloy")
        assert db.get("TestAlloy").conductivity == 45

    def test_add_duplicate_fails(self):
        db = self._make_db()
        m = Material(name="Copper", conductivity=1, density=1, specific_heat=1)
        assert db.add(m) is False

    def test_add_invalid_name_fails(self):
        db = self._make_db()
        m = Material(name="bad name", conductivity=1, density=1, specific_heat=1)
        assert db.add(m) is False

    def test_remove_custom(self):
        db = self._make_db()
        db.add(Material(name="Temp", conductivity=1, density=1, specific_heat=1))
        assert db.remove("Temp") is True
        assert not db.contains("Temp")

    def test_remove_builtin_fails(self):
        db = self._make_db()
        assert db.remove("Copper") is False
        assert db.contains("Copper")

    def test_update_custom(self):
        db = self._make_db()
        db.add(Material(name="Alloy1", conductivity=10, density=100, specific_heat=200,
                        category="自定义"))
        updated = Material(name="Alloy1", conductivity=20, density=100, specific_heat=200,
                           category="自定义")
        assert db.update("Alloy1", updated) is True
        assert db.get("Alloy1").conductivity == 20

    def test_update_builtin_only_description(self):
        db = self._make_db()
        old_cond = db.get("Copper").conductivity
        updated = Material(name="Copper", conductivity=999, density=999, specific_heat=999,
                           description="modified note")
        db.update("Copper", updated)
        # 数值不应改变
        assert db.get("Copper").conductivity == old_cond
        assert db.get("Copper").description == "modified note"

    def test_update_rename(self):
        db = self._make_db()
        db.add(Material(name="OldName", conductivity=1, density=1, specific_heat=1))
        renamed = Material(name="NewName", conductivity=1, density=1, specific_heat=1)
        assert db.update("OldName", renamed) is True
        assert not db.contains("OldName")
        assert db.contains("NewName")

    def test_duplicate(self):
        db = self._make_db()
        dup = db.duplicate("Copper", "Copper_Custom")
        assert dup is not None
        assert dup.name == "Copper_Custom"
        assert dup.conductivity == db.get("Copper").conductivity
        assert dup.is_builtin is False
        assert dup.category == "自定义"

    def test_duplicate_name_conflict_fails(self):
        db = self._make_db()
        assert db.duplicate("Copper", "Aluminum") is None


# ─── 持久化 ─────────────────────────────────────────────────────

class TestPersistence:
    def test_save_load_roundtrip(self, tmp_path):
        db1 = MaterialDatabase.create_default()
        db1.add(Material(name="MyMat", conductivity=42, density=7000, specific_heat=500,
                         category="自定义", description="test"))
        path = str(tmp_path / "materials.json")
        db1.save(path)

        # 仅保存自定义材质
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        assert len(data["materials"]) == 1
        assert data["materials"][0]["name"] == "MyMat"

        # 加载到新数据库
        db2 = MaterialDatabase.create_default()
        db2.load(path)
        assert db2.contains("MyMat")
        assert db2.get("MyMat").conductivity == 42
        assert db2.contains("Copper")  # 内置仍在

    def test_load_nonexistent_file(self, tmp_path):
        db = MaterialDatabase.create_default()
        db.load(str(tmp_path / "nonexistent.json"))
        assert db.contains("Copper")

    def test_load_does_not_overwrite_builtin(self, tmp_path):
        path = str(tmp_path / "bad.json")
        with open(path, "w") as f:
            json.dump({"version": 1, "materials": [
                {"name": "Copper", "conductivity": 999, "density": 999, "specific_heat": 999}
            ]}, f)
        db = MaterialDatabase.create_default()
        db.load(path)
        assert db.get("Copper").conductivity == 400  # 原始值

    def test_export_import(self, tmp_path):
        db1 = MaterialDatabase.create_default()
        db1.add(Material(name="Export1", conductivity=1, density=2, specific_heat=3))
        db1.add(Material(name="Export2", conductivity=4, density=5, specific_heat=6))
        path = str(tmp_path / "export.json")
        db1.export_materials(path, ["Export1", "Export2"])

        db2 = MaterialDatabase.create_default()
        imported = db2.import_materials(path)
        assert len(imported) == 2
        assert db2.contains("Export1")
        assert db2.contains("Export2")

    def test_import_skip_existing(self, tmp_path):
        db = MaterialDatabase.create_default()
        path = str(tmp_path / "dup.json")
        with open(path, "w") as f:
            json.dump({"version": 1, "materials": [
                {"name": "Copper", "conductivity": 1, "density": 1, "specific_heat": 1},
                {"name": "NewMat", "conductivity": 2, "density": 2, "specific_heat": 2},
            ]}, f)
        imported = db.import_materials(path)
        assert len(imported) == 1
        assert "NewMat" in imported


# ─── 信号 ────────────────────────────────────────────────────────

class TestSignals:
    def test_add_emits_signal(self):
        from PyQt5.QtWidgets import QApplication
        app = QApplication.instance() or QApplication(sys.argv)
        db = MaterialDatabase.create_default()
        received = []
        db.material_added.connect(lambda name: received.append(name))
        db.add(Material(name="SigTest", conductivity=1, density=1, specific_heat=1))
        assert received == ["SigTest"]

    def test_remove_emits_signal(self):
        from PyQt5.QtWidgets import QApplication
        app = QApplication.instance() or QApplication(sys.argv)
        db = MaterialDatabase.create_default()
        db.add(Material(name="SigDel", conductivity=1, density=1, specific_heat=1))
        received = []
        db.material_removed.connect(lambda name: received.append(name))
        db.remove("SigDel")
        assert received == ["SigDel"]

    def test_update_emits_signal(self):
        from PyQt5.QtWidgets import QApplication
        app = QApplication.instance() or QApplication(sys.argv)
        db = MaterialDatabase.create_default()
        db.add(Material(name="SigUpd", conductivity=1, density=1, specific_heat=1))
        received = []
        db.material_updated.connect(lambda name: received.append(name))
        db.update("SigUpd", Material(name="SigUpd", conductivity=2, density=1, specific_heat=1))
        assert received == ["SigUpd"]
