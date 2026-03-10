"""
编辑器偏好设置对话框。

提供可执行文件标签管理、启动行为、最近工程管理等编辑器级设置的 UI。
"""

import os

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTabWidget, QWidget,
    QGroupBox, QFormLayout, QComboBox, QListWidget, QPushButton,
    QFileDialog, QMessageBox, QLabel, QDialogButtonBox, QListWidgetItem,
    QTableWidget, QTableWidgetItem, QHeaderView, QInputDialog,
)
from PyQt5.QtCore import Qt

from models.editor_preferences import EditorPreferences, StartupBehavior


class PreferencesDialog(QDialog):
    """编辑器偏好设置对话框。"""

    def __init__(self, prefs: EditorPreferences, parent=None):
        super().__init__(parent)
        self.setWindowTitle("偏好设置")
        self.resize(560, 480)
        self._prefs = prefs
        self._build_ui()
        self._load_from_prefs()

    # ─── UI 构建 ─────────────────────────────────────────────────

    def _build_ui(self):
        layout = QVBoxLayout(self)
        tabs = QTabWidget()
        layout.addWidget(tabs)

        tabs.addTab(self._build_general_tab(), "常规")
        tabs.addTab(self._build_exe_tags_tab(), "可执行文件")
        tabs.addTab(self._build_recent_tab(), "最近工程")

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self._on_accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _build_general_tab(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)

        self._startup_combo = QComboBox()
        self._startup_combo.addItem("无操作（空白场景）", StartupBehavior.NONE.value)
        self._startup_combo.addItem("打开上次关闭的工程", StartupBehavior.OPEN_LAST.value)
        form.addRow("启动时默认行为：", self._startup_combo)

        return w

    def _build_exe_tags_tab(self) -> QWidget:
        w = QWidget()
        vbox = QVBoxLayout(w)

        # 可执行文件标签表格
        grp = QGroupBox("可执行文件标签")
        g_layout = QVBoxLayout(grp)

        self._tag_table = QTableWidget(0, 2)
        self._tag_table.setHorizontalHeaderLabels(["标签名", "路径"])
        self._tag_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Interactive)
        self._tag_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self._tag_table.setColumnWidth(0, 150)
        self._tag_table.setSelectionBehavior(QTableWidget.SelectRows)
        g_layout.addWidget(self._tag_table)

        btn_row = QHBoxLayout()
        add_btn = QPushButton("添加...")
        add_btn.clicked.connect(self._on_add_tag)
        btn_row.addWidget(add_btn)

        rm_btn = QPushButton("删除选中")
        rm_btn.clicked.connect(self._on_remove_tag)
        btn_row.addWidget(rm_btn)

        browse_btn = QPushButton("修改路径...")
        browse_btn.clicked.connect(self._on_browse_tag_path)
        btn_row.addWidget(browse_btn)

        btn_row.addStretch()
        g_layout.addLayout(btn_row)
        vbox.addWidget(grp)

        # 搜索目录
        grp2 = QGroupBox("搜索目录")
        g2_layout = QVBoxLayout(grp2)
        self._dir_list = QListWidget()
        g2_layout.addWidget(self._dir_list)

        btn_row2 = QHBoxLayout()
        add_dir_btn = QPushButton("添加目录...")
        add_dir_btn.clicked.connect(self._on_add_search_dir)
        btn_row2.addWidget(add_dir_btn)

        rm_dir_btn = QPushButton("移除选中")
        rm_dir_btn.clicked.connect(self._on_remove_search_dir)
        btn_row2.addWidget(rm_dir_btn)

        scan_btn = QPushButton("扫描发现...")
        scan_btn.clicked.connect(self._on_scan)
        btn_row2.addWidget(scan_btn)

        btn_row2.addStretch()
        g2_layout.addLayout(btn_row2)
        vbox.addWidget(grp2)

        return w

    def _build_recent_tab(self) -> QWidget:
        w = QWidget()
        vbox = QVBoxLayout(w)

        vbox.addWidget(QLabel("最近打开的工程文件（双击可复制路径）："))
        self._recent_list = QListWidget()
        vbox.addWidget(self._recent_list)

        btn_row = QHBoxLayout()
        clear_btn = QPushButton("清空列表")
        clear_btn.clicked.connect(self._on_clear_recent)
        btn_row.addWidget(clear_btn)
        btn_row.addStretch()
        vbox.addLayout(btn_row)

        return w

    # ─── 数据 ←→ UI ─────────────────────────────────────────────

    def _load_from_prefs(self):
        p = self._prefs

        # 启动行为
        idx = self._startup_combo.findData(p.startup_behavior.value)
        if idx >= 0:
            self._startup_combo.setCurrentIndex(idx)

        # 可执行文件标签
        self._tag_table.setRowCount(0)
        for tag, path in p.exe_tags.items():
            row = self._tag_table.rowCount()
            self._tag_table.insertRow(row)
            self._tag_table.setItem(row, 0, QTableWidgetItem(tag))
            self._tag_table.setItem(row, 1, QTableWidgetItem(path))

        # 搜索目录
        self._dir_list.clear()
        for d in p.search_dirs:
            self._dir_list.addItem(d)

        # 最近工程
        self._recent_list.clear()
        for r in p.recent_projects:
            self._recent_list.addItem(r)

    def _write_to_prefs(self):
        p = self._prefs

        sb_val = self._startup_combo.currentData()
        try:
            p.startup_behavior = StartupBehavior(sb_val)
        except ValueError:
            p.startup_behavior = StartupBehavior.NONE

        # 可执行文件标签
        tags = {}
        for row in range(self._tag_table.rowCount()):
            tag_item = self._tag_table.item(row, 0)
            path_item = self._tag_table.item(row, 1)
            if tag_item and path_item:
                tag = tag_item.text().strip()
                path = path_item.text().strip()
                if tag and path:
                    tags[tag] = path
        p.exe_tags = tags

        p.search_dirs = [
            self._dir_list.item(i).text()
            for i in range(self._dir_list.count())
        ]
        p.recent_projects = [
            self._recent_list.item(i).text()
            for i in range(self._recent_list.count())
        ]

    # ─── 可执行文件标签操作 ────────────────────────────────────

    def _on_add_tag(self):
        tag, ok = QInputDialog.getText(self, "添加标签", "标签名（如 stardis-v3）：")
        if not ok or not tag.strip():
            return
        tag = tag.strip()
        # 检查重复
        for row in range(self._tag_table.rowCount()):
            if self._tag_table.item(row, 0).text() == tag:
                QMessageBox.warning(self, "重复", f"标签 '{tag}' 已存在。")
                return
        path, _ = QFileDialog.getOpenFileName(
            self, f"选择 '{tag}' 的可执行文件", "",
            "可执行文件 (*.exe);;所有文件 (*)")
        if not path:
            return
        row = self._tag_table.rowCount()
        self._tag_table.insertRow(row)
        self._tag_table.setItem(row, 0, QTableWidgetItem(tag))
        self._tag_table.setItem(row, 1, QTableWidgetItem(path))

    def _on_remove_tag(self):
        rows = sorted({idx.row() for idx in self._tag_table.selectedIndexes()},
                      reverse=True)
        for row in rows:
            self._tag_table.removeRow(row)

    def _on_browse_tag_path(self):
        rows = sorted({idx.row() for idx in self._tag_table.selectedIndexes()})
        if not rows:
            return
        row = rows[0]
        tag = self._tag_table.item(row, 0).text()
        path, _ = QFileDialog.getOpenFileName(
            self, f"选择 '{tag}' 的可执行文件", "",
            "可执行文件 (*.exe);;所有文件 (*)")
        if path:
            self._tag_table.setItem(row, 1, QTableWidgetItem(path))

    # ─── 搜索目录操作 ───────────────────────────────────────────

    def _on_add_search_dir(self):
        d = QFileDialog.getExistingDirectory(self, "选择搜索目录")
        if d:
            # 去重
            existing = {self._dir_list.item(i).text() for i in range(self._dir_list.count())}
            if d not in existing:
                self._dir_list.addItem(d)

    def _on_remove_search_dir(self):
        for item in self._dir_list.selectedItems():
            self._dir_list.takeItem(self._dir_list.row(item))

    def _on_scan(self):
        """先把 UI 上的搜索目录写回 prefs 再扫描。"""
        self._write_to_prefs()
        found = self._prefs.scan_stardis_exes()
        if not found:
            QMessageBox.information(self, "扫描完成", "未发现 stardis.exe，请检查搜索目录。")
            return
        # 对新发现的 exe 提示用户添加标签
        existing_paths = set(self._prefs.exe_tags.values())
        new_count = 0
        for exe_path in found:
            if exe_path in existing_paths:
                continue
            basename = os.path.splitext(os.path.basename(exe_path))[0]
            tag, ok = QInputDialog.getText(
                self, "命名标签",
                f"发现: {exe_path}\n请输入标签名：",
                text=basename)
            if ok and tag.strip():
                tag = tag.strip()
                self._prefs.exe_tags[tag] = exe_path
                new_count += 1
        # 刷新标签表
        self._tag_table.setRowCount(0)
        for tag, path in self._prefs.exe_tags.items():
            row = self._tag_table.rowCount()
            self._tag_table.insertRow(row)
            self._tag_table.setItem(row, 0, QTableWidgetItem(tag))
            self._tag_table.setItem(row, 1, QTableWidgetItem(path))
        QMessageBox.information(
            self, "扫描完成",
            f"找到 {len(found)} 个 stardis.exe，新增 {new_count} 个标签。")

    # ─── 最近工程 ───────────────────────────────────────────────

    def _on_clear_recent(self):
        self._recent_list.clear()

    # ─── 确认 ───────────────────────────────────────────────────

    def _on_accept(self):
        self._write_to_prefs()
        self.accept()
