"""
物理材质数据库管理。

提供命名材质 (Material) 和材质库管理器 (MaterialDatabase)。
内置常用工程材质，支持用户自定义材质的 CRUD 与 JSON 持久化。
"""

import json
import os
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from PyQt5.QtCore import QObject, pyqtSignal


@dataclass
class Material:
    """可复用的命名物理材质。"""
    name: str = ""
    conductivity: float = 1.0      # λ (W/m/K)
    density: float = 1.0           # ρ (kg/m³)
    specific_heat: float = 1.0     # cp (J/kg/K)
    category: str = ""             # 分类标签
    description: str = ""          # 可选备注
    is_builtin: bool = False


# ─── 名称校验 ───────────────────────────────────────────────────

_NAME_RE = re.compile(r'^[A-Za-z0-9_]+$')


def is_valid_material_name(name: str) -> bool:
    return bool(name) and _NAME_RE.match(name) is not None


# ─── 内置材质 ───────────────────────────────────────────────────

_BUILTIN_MATERIALS: List[Material] = [
    # 金属
    Material("Copper",            400,  8960,  385,  "金属", "纯铜",           True),
    Material("Aluminum",          237,  2700,  900,  "金属", "纯铝",           True),
    Material("Steel_Mild",         50,  7850,  500,  "金属", "低碳钢",         True),
    Material("Steel_Stainless",    16,  7900,  500,  "金属", "不锈钢 304",     True),
    Material("Titanium",           22,  4500,  520,  "金属", "钛合金 Ti-6Al-4V", True),
    Material("Gold",              317, 19300,  129,  "金属", "纯金",           True),
    Material("Silver",            429, 10500,  235,  "金属", "纯银",           True),
    Material("Iron",               80,  7870,  450,  "金属", "纯铁",           True),
    Material("Nickel",             91,  8900,  444,  "金属", "纯镍",           True),
    Material("Brass",             109,  8500,  380,  "金属", "黄铜",           True),
    # 绝缘体
    Material("Fiberglass",       0.04,    12,  840,  "绝缘体", "玻璃纤维毡",     True),
    Material("Polystyrene_EPS",  0.035,   25, 1200,  "绝缘体", "膨胀聚苯乙烯",   True),
    Material("Polyurethane_Foam", 0.025,  30, 1500,  "绝缘体", "聚氨酯泡沫",     True),
    Material("Ceramic_Alumina",    30,  3950,  775,  "绝缘体", "氧化铝陶瓷",     True),
    Material("Glass",             1.0,  2500,  840,  "绝缘体", "普通玻璃",       True),
    Material("Wood_Oak",         0.17,   700, 2400,  "绝缘体", "橡木",           True),
    Material("Concrete",          1.4,  2300,  880,  "绝缘体", "混凝土",         True),
    Material("Rubber",           0.16,  1200, 2010,  "绝缘体", "天然橡胶",       True),
    # 流体
    Material("Air_300K",        0.026, 1.177, 1005,  "流体", "空气 (300K, 1atm)", True),
    Material("Water_300K",       0.61,   996, 4180,  "流体", "水 (300K)",         True),
    Material("Oil_Engine",      0.145,   880, 1900,  "流体", "发动机润滑油",      True),
    # 其他
    Material("Graphite",          120,  2200,  710,  "其他", "石墨",             True),
    Material("Silicon",           150,  2330,  700,  "其他", "单晶硅",           True),
    Material("Epoxy",             0.2,  1200, 1000,  "其他", "环氧树脂",         True),
]


# ─── MaterialDatabase ──────────────────────────────────────────

class MaterialDatabase(QObject):
    """材质数据库，管理内置 + 用户自定义材质。"""

    material_added   = pyqtSignal(str)   # name
    material_removed = pyqtSignal(str)   # name
    material_updated = pyqtSignal(str)   # name

    def __init__(self, parent=None):
        super().__init__(parent)
        self._materials: Dict[str, Material] = {}

    # ── 查询 ──

    def get(self, name: str) -> Optional[Material]:
        return self._materials.get(name)

    def list_all(self) -> List[Material]:
        return sorted(self._materials.values(), key=lambda m: (m.category, m.name))

    def list_by_category(self, category: str) -> List[Material]:
        return sorted(
            [m for m in self._materials.values() if m.category == category],
            key=lambda m: m.name,
        )

    def categories(self) -> List[str]:
        cats = sorted({m.category for m in self._materials.values() if m.category})
        return cats

    def contains(self, name: str) -> bool:
        return name in self._materials

    def all_names(self) -> List[str]:
        return sorted(self._materials.keys())

    # ── 修改 ──

    def add(self, material: Material) -> bool:
        if not is_valid_material_name(material.name):
            return False
        if material.name in self._materials:
            return False
        self._materials[material.name] = material
        self.material_added.emit(material.name)
        return True

    def update(self, name: str, material: Material) -> bool:
        existing = self._materials.get(name)
        if not existing:
            return False
        if existing.is_builtin:
            # 内置材质只允许修改 description
            existing.description = material.description
        else:
            if material.name != name:
                if material.name in self._materials:
                    return False
                del self._materials[name]
            self._materials[material.name] = material
        self.material_updated.emit(material.name)
        return True

    def remove(self, name: str) -> bool:
        m = self._materials.get(name)
        if not m or m.is_builtin:
            return False
        del self._materials[name]
        self.material_removed.emit(name)
        return True

    def duplicate(self, name: str, new_name: str) -> Optional[Material]:
        src = self._materials.get(name)
        if not src or not is_valid_material_name(new_name):
            return None
        if new_name in self._materials:
            return None
        dup = Material(
            name=new_name,
            conductivity=src.conductivity,
            density=src.density,
            specific_heat=src.specific_heat,
            category="自定义",
            description=src.description,
            is_builtin=False,
        )
        self._materials[new_name] = dup
        self.material_added.emit(new_name)
        return dup

    # ── 持久化 ──

    def save(self, path: str):
        user_mats = [m for m in self._materials.values() if not m.is_builtin]
        data = {
            "version": 1,
            "materials": [
                {
                    "name": m.name,
                    "conductivity": m.conductivity,
                    "density": m.density,
                    "specific_heat": m.specific_heat,
                    "category": m.category,
                    "description": m.description,
                }
                for m in sorted(user_mats, key=lambda m: m.name)
            ],
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def load(self, path: str):
        if not os.path.isfile(path):
            return
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        for md in data.get("materials", []):
            name = md.get("name", "")
            if not is_valid_material_name(name):
                continue
            if name in self._materials:
                continue  # 不覆盖内置材质
            self._materials[name] = Material(
                name=name,
                conductivity=md.get("conductivity", 1.0),
                density=md.get("density", 1.0),
                specific_heat=md.get("specific_heat", 1.0),
                category=md.get("category", "自定义"),
                description=md.get("description", ""),
                is_builtin=False,
            )

    # ── 导入/导出 ──

    def export_materials(self, path: str, names: List[str]):
        mats = [self._materials[n] for n in names if n in self._materials]
        data = {
            "version": 1,
            "materials": [
                {
                    "name": m.name,
                    "conductivity": m.conductivity,
                    "density": m.density,
                    "specific_heat": m.specific_heat,
                    "category": m.category,
                    "description": m.description,
                }
                for m in mats
            ],
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def import_materials(self, path: str) -> List[str]:
        """导入材质文件，返回成功导入的名称列表。"""
        if not os.path.isfile(path):
            return []
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        imported = []
        for md in data.get("materials", []):
            name = md.get("name", "")
            if not is_valid_material_name(name):
                continue
            if name in self._materials:
                continue
            m = Material(
                name=name,
                conductivity=md.get("conductivity", 1.0),
                density=md.get("density", 1.0),
                specific_heat=md.get("specific_heat", 1.0),
                category=md.get("category", "自定义"),
                description=md.get("description", ""),
                is_builtin=False,
            )
            self._materials[name] = m
            self.material_added.emit(name)
            imported.append(name)
        return imported

    # ── 工厂方法 ──

    @staticmethod
    def create_default(parent=None) -> 'MaterialDatabase':
        db = MaterialDatabase(parent)
        for m in _BUILTIN_MATERIALS:
            db._materials[m.name] = Material(
                name=m.name,
                conductivity=m.conductivity,
                density=m.density,
                specific_heat=m.specific_heat,
                category=m.category,
                description=m.description,
                is_builtin=True,
            )
        return db
