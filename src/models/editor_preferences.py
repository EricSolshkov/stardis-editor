"""
编辑器偏好设置管理。

管理 stardis 可执行文件路径、搜索目录、最近工程、启动行为等用户级设置。
设置持久化到项目根目录下的 editor_settings.json。
"""

import json
import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional


class StartupBehavior(Enum):
    """启动时默认行为"""
    NONE = "none"               # 无操作（空白场景）
    OPEN_LAST = "open_last"     # 打开上次关闭的工程


@dataclass
class EditorPreferences:
    """编辑器级别偏好设置，与场景数据无关。"""

    # stardis 自动搜索目录列表
    search_dirs: List[str] = field(default_factory=list)
    # 最近使用的 stardis 可执行文件路径
    recent_exes: List[str] = field(default_factory=list)
    # 最近使用的工作目录
    recent_work_dirs: List[str] = field(default_factory=list)
    # 最近打开的工程文件（.txt 场景文件路径）
    recent_projects: List[str] = field(default_factory=list)
    # 上次关闭时正在编辑的工程文件路径
    last_project_path: str = ""
    # 启动行为
    startup_behavior: StartupBehavior = StartupBehavior.NONE
    # 可执行文件标签（标签名 → 绝对路径）
    exe_tags: Dict[str, str] = field(default_factory=dict)

    # ── 列表容量上限 ──
    MAX_RECENT_EXES = 50
    MAX_RECENT_WORK_DIRS = 20
    MAX_RECENT_PROJECTS = 20

    # ── 最近列表操作 ──

    def add_recent_exe(self, path: str):
        if not path:
            return
        self._push_to_list("recent_exes", path, self.MAX_RECENT_EXES)

    def add_recent_workdir(self, path: str):
        if not path:
            return
        self._push_to_list("recent_work_dirs", path, self.MAX_RECENT_WORK_DIRS)

    def add_recent_project(self, path: str):
        if not path:
            return
        self._push_to_list("recent_projects", path, self.MAX_RECENT_PROJECTS)

    def _push_to_list(self, attr: str, value: str, limit: int):
        lst: list = getattr(self, attr)
        if value in lst:
            lst.remove(value)
        lst.insert(0, value)
        setattr(self, attr, lst[:limit])

    # ── stardis 可执行文件自动搜索 ──

    def scan_stardis_exes(self) -> List[str]:
        """在 search_dirs 下递归搜索 stardis.exe，返回新发现的路径列表。"""
        found: List[str] = []
        for d in self.search_dirs:
            if not os.path.isdir(d):
                continue
            for root, _, files in os.walk(d):
                for name in files:
                    if name.lower() == "stardis.exe":
                        full = os.path.join(root, name)
                        found.append(full)
        # 添加到 recent_exes
        for p in found:
            self.add_recent_exe(p)
        return found

    # ── 序列化 ──

    def to_dict(self) -> dict:
        return {
            "search_dirs": self.search_dirs,
            "recent_exes": self.recent_exes,
            "recent_work_dirs": self.recent_work_dirs,
            "recent_projects": self.recent_projects,
            "last_project_path": self.last_project_path,
            "startup_behavior": self.startup_behavior.value,
            "exe_tags": self.exe_tags,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "EditorPreferences":
        sb_str = data.get("startup_behavior", "none")
        try:
            sb = StartupBehavior(sb_str)
        except ValueError:
            sb = StartupBehavior.NONE
        return cls(
            search_dirs=data.get("search_dirs", []),
            recent_exes=data.get("recent_exes", []),
            recent_work_dirs=data.get("recent_work_dirs", []),
            recent_projects=data.get("recent_projects", []),
            last_project_path=data.get("last_project_path", ""),
            startup_behavior=sb,
            exe_tags=data.get("exe_tags", {}),
        )

    # ── 文件 I/O ──

    def save(self, path: str):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)

    @classmethod
    def load(cls, path: str) -> "EditorPreferences":
        if not os.path.isfile(path):
            return cls()
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return cls.from_dict(data)

    @classmethod
    def load_or_migrate(cls, editor_path: str, legacy_path: str) -> "EditorPreferences":
        """加载偏好设置；若 editor_settings.json 不存在则尝试从 v1 user_settings.json 迁移。"""
        if os.path.isfile(editor_path):
            return cls.load(editor_path)
        prefs = cls()
        if os.path.isfile(legacy_path):
            with open(legacy_path, "r", encoding="utf-8") as f:
                legacy = json.load(f)
            prefs.search_dirs = legacy.get("search_dirs", [])
            prefs.recent_exes = legacy.get("recent_exes", [])
            prefs.recent_work_dirs = legacy.get("recent_work_dirs", [])
            prefs.save(editor_path)
        return prefs
