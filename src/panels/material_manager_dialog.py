"""
材质库管理对话框。

提供材质的浏览、新增、编辑、删除、复制、导入、导出功能。
"""

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel,
    QDoubleSpinBox, QComboBox, QLineEdit, QGroupBox,
    QPushButton, QListWidget, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView, QFileDialog, QMessageBox,
    QSplitter, QWidget,
)
from PyQt5.QtCore import Qt
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from models.material_database import MaterialDatabase, Material, is_valid_material_name


def _spin(value=0.0, lo=-1e9, hi=1e9, decimals=4, suffix=""):
    s = QDoubleSpinBox()
    s.setRange(lo, hi)
    s.setDecimals(decimals)
    s.setValue(value)
    if suffix:
        s.setSuffix(f" {suffix}")
    return s


class MaterialManagerDialog(QDialog):
    """材质库管理对话框。"""

    def __init__(self, database: MaterialDatabase, parent=None):
        super().__init__(parent)
        self.setWindowTitle("材质库管理")
        self.resize(700, 550)
        self._db = database
        self._current_name = ""   # 当前选中的材质名
        self._is_new = False      # 是否处于新建模式

        self._build_ui()
        self._connect_signals()
        self._refresh_categories()
        self._refresh_table()

    def _build_ui(self):
        main_layout = QVBoxLayout(self)

        # 上部: 分类 + 列表
        top_splitter = QSplitter(Qt.Horizontal)

        # 左: 分类列表
        cat_widget = QWidget()
        cat_layout = QVBoxLayout(cat_widget)
        cat_layout.setContentsMargins(0, 0, 0, 0)
        cat_layout.addWidget(QLabel("分类"))
        self._cat_list = QListWidget()
        cat_layout.addWidget(self._cat_list)
        cat_widget.setMinimumWidth(80)
        top_splitter.addWidget(cat_widget)

        # 右: 材质表格
        table_widget = QWidget()
        table_layout = QVBoxLayout(table_widget)
        table_layout.setContentsMargins(0, 0, 0, 0)
        table_layout.addWidget(QLabel("材质列表"))
        self._table = QTableWidget(0, 5)
        self._table.setHorizontalHeaderLabels(["", "名称", "λ W/m/K", "ρ kg/m³", "cp J/kg/K"])
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self._table.setColumnWidth(0, 24)
        self._table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SingleSelection)
        table_layout.addWidget(self._table)
        table_widget.setMinimumWidth(200)
        top_splitter.addWidget(table_widget)
        top_splitter.setCollapsible(0, False)
        top_splitter.setCollapsible(1, False)
        top_splitter.setSizes([120, 550])

        main_layout.addWidget(top_splitter, 1)

        # 下部: 详情编辑区
        detail_grp = QGroupBox("材质详情")
        detail_form = QFormLayout(detail_grp)

        self._name_edit = QLineEdit()
        detail_form.addRow("名称:", self._name_edit)

        self._cat_combo = QComboBox()
        self._cat_combo.setEditable(True)
        detail_form.addRow("分类:", self._cat_combo)

        self._lam = _spin(1, 0, 1e6, 4, "W/m/K")
        detail_form.addRow("导热系数 λ:", self._lam)

        self._rho = _spin(1, 0, 1e9, 2, "kg/m³")
        detail_form.addRow("密度 ρ:", self._rho)

        self._cp = _spin(1, 0, 1e9, 2, "J/kg/K")
        detail_form.addRow("比热容 cp:", self._cp)

        self._desc_edit = QLineEdit()
        detail_form.addRow("备注:", self._desc_edit)

        self._readonly_hint = QLabel()
        self._readonly_hint.setStyleSheet("color: gray; font-style: italic;")
        detail_form.addRow("", self._readonly_hint)

        save_row = QHBoxLayout()
        self._save_btn = QPushButton("保存修改")
        save_row.addStretch()
        save_row.addWidget(self._save_btn)
        detail_form.addRow("", save_row)

        main_layout.addWidget(detail_grp)

        # 底部按钮
        btn_row = QHBoxLayout()
        self._new_btn = QPushButton("新建材质")
        self._dup_btn = QPushButton("复制")
        self._del_btn = QPushButton("删除")
        self._import_btn = QPushButton("从文件导入...")
        self._export_btn = QPushButton("导出到文件...")
        btn_row.addWidget(self._new_btn)
        btn_row.addWidget(self._dup_btn)
        btn_row.addWidget(self._del_btn)
        btn_row.addStretch()
        btn_row.addWidget(self._import_btn)
        btn_row.addWidget(self._export_btn)

        close_btn = QPushButton("关闭")
        btn_row.addWidget(close_btn)
        close_btn.clicked.connect(self.accept)

        main_layout.addLayout(btn_row)

        self._set_detail_enabled(False)

    def _connect_signals(self):
        self._cat_list.currentRowChanged.connect(self._on_category_changed)
        self._table.currentCellChanged.connect(self._on_table_selection_changed)
        self._save_btn.clicked.connect(self._on_save)
        self._new_btn.clicked.connect(self._on_new)
        self._dup_btn.clicked.connect(self._on_duplicate)
        self._del_btn.clicked.connect(self._on_delete)
        self._import_btn.clicked.connect(self._on_import)
        self._export_btn.clicked.connect(self._on_export)

    # ── 刷新 ──

    def _refresh_categories(self):
        self._cat_list.blockSignals(True)
        self._cat_list.clear()
        self._cat_list.addItem("全部")
        for cat in self._db.categories():
            self._cat_list.addItem(cat)
        self._cat_list.setCurrentRow(0)
        self._cat_list.blockSignals(False)

        # 也刷新详情区的分类下拉
        self._cat_combo.blockSignals(True)
        self._cat_combo.clear()
        for cat in self._db.categories():
            self._cat_combo.addItem(cat)
        self._cat_combo.addItem("自定义")
        self._cat_combo.blockSignals(False)

    def _refresh_table(self, category: str = ""):
        self._table.setRowCount(0)
        if category and category != "全部":
            mats = self._db.list_by_category(category)
        else:
            mats = self._db.list_all()

        self._table.setRowCount(len(mats))
        for r, mat in enumerate(mats):
            icon = "●" if mat.is_builtin else "○"
            self._table.setItem(r, 0, QTableWidgetItem(icon))
            self._table.setItem(r, 1, QTableWidgetItem(mat.name))
            self._table.setItem(r, 2, QTableWidgetItem(str(mat.conductivity)))
            self._table.setItem(r, 3, QTableWidgetItem(str(mat.density)))
            self._table.setItem(r, 4, QTableWidgetItem(str(mat.specific_heat)))

    def _load_detail(self, mat: Material):
        self._current_name = mat.name
        self._is_new = False
        is_builtin = mat.is_builtin

        self._name_edit.setText(mat.name)
        self._name_edit.setEnabled(not is_builtin)

        idx = self._cat_combo.findText(mat.category)
        if idx >= 0:
            self._cat_combo.setCurrentIndex(idx)
        else:
            self._cat_combo.setCurrentText(mat.category)
        self._cat_combo.setEnabled(not is_builtin)

        self._lam.setValue(mat.conductivity)
        self._lam.setEnabled(not is_builtin)

        self._rho.setValue(mat.density)
        self._rho.setEnabled(not is_builtin)

        self._cp.setValue(mat.specific_heat)
        self._cp.setEnabled(not is_builtin)

        self._desc_edit.setText(mat.description)
        # 备注始终可编辑

        self._save_btn.setEnabled(True)
        self._del_btn.setEnabled(not is_builtin)
        self._dup_btn.setEnabled(True)

        if is_builtin:
            self._readonly_hint.setText("内置材质不可修改。可使用\"复制\"创建自定义副本。")
        else:
            self._readonly_hint.setText("")

    def _set_detail_enabled(self, enabled):
        for w in (self._name_edit, self._cat_combo, self._lam, self._rho, self._cp, self._desc_edit):
            w.setEnabled(enabled)
        self._save_btn.setEnabled(enabled)
        self._del_btn.setEnabled(enabled)
        self._dup_btn.setEnabled(enabled)

    # ── 事件处理 ──

    def _on_category_changed(self, row):
        if row < 0:
            return
        cat = self._cat_list.item(row).text()
        self._refresh_table(cat)

    def _on_table_selection_changed(self, row, col, prev_row, prev_col):
        if row < 0:
            self._set_detail_enabled(False)
            return
        name_item = self._table.item(row, 1)
        if not name_item:
            return
        mat = self._db.get(name_item.text())
        if mat:
            self._load_detail(mat)

    def _on_save(self):
        name = self._name_edit.text().strip()
        if not is_valid_material_name(name):
            QMessageBox.warning(self, "名称无效", "材质名称只能包含字母、数字和下划线。")
            return

        mat = Material(
            name=name,
            conductivity=self._lam.value(),
            density=self._rho.value(),
            specific_heat=self._cp.value(),
            category=self._cat_combo.currentText().strip() or "自定义",
            description=self._desc_edit.text().strip(),
            is_builtin=False,
        )

        if self._is_new:
            if not self._db.add(mat):
                QMessageBox.warning(self, "添加失败", f"名称 '{name}' 已存在或无效。")
                return
            self._is_new = False
        else:
            existing = self._db.get(self._current_name)
            if existing and existing.is_builtin:
                # 内置材质只保存描述
                existing.description = self._desc_edit.text().strip()
                self._db.material_updated.emit(existing.name)
            else:
                if not self._db.update(self._current_name, mat):
                    QMessageBox.warning(self, "保存失败", "名称冲突或材质不存在。")
                    return

        self._current_name = name
        self._refresh_categories()
        cat = self._cat_list.currentItem().text() if self._cat_list.currentItem() else ""
        self._refresh_table(cat)

    def _on_new(self):
        self._is_new = True
        self._current_name = ""
        self._set_detail_enabled(True)
        self._name_edit.setText("New_Material")
        self._name_edit.setEnabled(True)
        self._cat_combo.setCurrentText("自定义")
        self._cat_combo.setEnabled(True)
        self._lam.setValue(1.0)
        self._lam.setEnabled(True)
        self._rho.setValue(1.0)
        self._rho.setEnabled(True)
        self._cp.setValue(1.0)
        self._cp.setEnabled(True)
        self._desc_edit.setText("")
        self._readonly_hint.setText("")
        self._name_edit.setFocus()
        self._name_edit.selectAll()

    def _on_duplicate(self):
        if not self._current_name:
            return
        src = self._db.get(self._current_name)
        if not src:
            return
        # 生成唯一名称
        base = self._current_name + "_copy"
        new_name = base
        i = 2
        while self._db.contains(new_name):
            new_name = f"{base}_{i}"
            i += 1
        dup = self._db.duplicate(self._current_name, new_name)
        if dup:
            self._refresh_categories()
            cat = self._cat_list.currentItem().text() if self._cat_list.currentItem() else ""
            self._refresh_table(cat)
            self._load_detail(dup)

    def _on_delete(self):
        if not self._current_name:
            return
        mat = self._db.get(self._current_name)
        if not mat or mat.is_builtin:
            return
        reply = QMessageBox.question(
            self, "确认删除",
            f"确定删除材质 '{self._current_name}' 吗？",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return
        self._db.remove(self._current_name)
        self._current_name = ""
        self._set_detail_enabled(False)
        self._refresh_categories()
        cat = self._cat_list.currentItem().text() if self._cat_list.currentItem() else ""
        self._refresh_table(cat)

    def _on_import(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "导入材质", "", "JSON 文件 (*.json)")
        if not path:
            return
        imported = self._db.import_materials(path)
        if imported:
            QMessageBox.information(self, "导入成功", f"已导入 {len(imported)} 种材质。")
            self._refresh_categories()
            cat = self._cat_list.currentItem().text() if self._cat_list.currentItem() else ""
            self._refresh_table(cat)
        else:
            QMessageBox.information(self, "导入结果", "没有新材质被导入（可能全部已存在）。")

    def _on_export(self):
        # 导出所有用户自定义材质
        user_names = [m.name for m in self._db.list_all() if not m.is_builtin]
        if not user_names:
            QMessageBox.information(self, "导出", "没有用户自定义材质可导出。")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "导出材质", "materials.json", "JSON 文件 (*.json)")
        if not path:
            return
        self._db.export_materials(path, user_names)
        QMessageBox.information(self, "导出成功", f"已导出 {len(user_names)} 种材质。")


class SaveMaterialDialog(QDialog):
    """快速保存材质对话框（从 Body 右键触发）。"""

    def __init__(self, conductivity: float, density: float, specific_heat: float,
                 database: MaterialDatabase, parent=None):
        super().__init__(parent)
        self.setWindowTitle("保存当前材质到库")
        self._db = database

        layout = QFormLayout(self)
        self._name_edit = QLineEdit("New_Material")
        layout.addRow("名称:", self._name_edit)

        self._cat_combo = QComboBox()
        self._cat_combo.setEditable(True)
        for cat in database.categories():
            self._cat_combo.addItem(cat)
        self._cat_combo.addItem("自定义")
        self._cat_combo.setCurrentText("自定义")
        layout.addRow("分类:", self._cat_combo)

        layout.addRow("导热系数 λ:", QLabel(f"{conductivity} W/m/K"))
        layout.addRow("密度 ρ:", QLabel(f"{density} kg/m³"))
        layout.addRow("比热容 cp:", QLabel(f"{specific_heat} J/kg/K"))

        self._conductivity = conductivity
        self._density = density
        self._specific_heat = specific_heat

        from PyQt5.QtWidgets import QDialogButtonBox
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def _on_accept(self):
        name = self._name_edit.text().strip()
        if not is_valid_material_name(name):
            QMessageBox.warning(self, "名称无效", "名称只能包含字母、数字和下划线。")
            return
        mat = Material(
            name=name,
            conductivity=self._conductivity,
            density=self._density,
            specific_heat=self._specific_heat,
            category=self._cat_combo.currentText().strip() or "自定义",
            is_builtin=False,
        )
        if not self._db.add(mat):
            QMessageBox.warning(self, "添加失败", f"名称 '{name}' 已存在。")
            return
        self.accept()

    @property
    def material_name(self) -> str:
        return self._name_edit.text().strip()
