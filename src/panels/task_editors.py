"""
Task Runner UI 编辑器组件。

TaskQueueEditor：任务队列总览（选中 Tasks 分组节点时显示）
TaskEditor：单任务编辑器（选中具体任务节点时显示）
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel,
    QDoubleSpinBox, QSpinBox, QComboBox, QLineEdit, QGroupBox,
    QPushButton, QTableWidget, QTableWidgetItem, QHeaderView,
    QAbstractItemView, QCheckBox, QRadioButton, QButtonGroup,
    QListWidget, QListWidgetItem, QTextEdit, QFileDialog,
)
from PyQt5.QtCore import pyqtSignal, Qt
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from models.task_model import (
    Task, TaskQueue, TaskType, ComputeMode, FieldSolveType,
    HtppMode, ErrorAction, ErrorPolicy,
    InputFromTask, InputFromFile,
    StardisParams, HtppParams, AdvancedOptions, FieldSolveConfig,
)
from models.scene_model import SceneModel
from task_runner.variable_expander import list_available_variables


# ─── HTPP 常量（与 v1 HtppControlPanel 对齐）──────────────────

HTTP_PALETTES = [
    # scmap 库全部预设调色板（按字母排序，共 48 个）
    "accent", "blues", "brbg", "bugn", "bupu",
    "chromajs", "dark2",
    "gnbu", "gnpu", "greens", "greys",
    "inferno", "jet",
    "magma", "moreland",
    "oranges", "orrd",
    "paired", "parula", "pastel1", "pastel2", "piyg", "plasma",
    "prgn", "pubu", "pubugn", "puor", "purd", "purples",
    "rdbu", "rdgy", "rdpu", "rdylbu", "rdylgn", "reds",
    "sand", "set1", "set2", "set3", "spectral",
    "viridis",
    "whgnbu", "whylrd",
    "ylgn", "ylgnbu", "ylorbr", "ylorrd", "ylrd",
]

HTTP_PIXEL_COMPONENTS = [
    "0 - X / R",
    "1 - X_stderr",
    "2 - Y / G",
    "3 - Y_stderr",
    "4 - Z / B",
    "5 - Z_stderr",
    "6 - Time",
    "7 - Time_stderr",
]


def _spin(value=0.0, lo=-1e9, hi=1e9, decimals=4, suffix=""):
    s = QDoubleSpinBox()
    s.setRange(lo, hi)
    s.setDecimals(decimals)
    s.setValue(value)
    if suffix:
        s.setSuffix(f" {suffix}")
    return s


def _set_form_row_visible(form_layout, widget, visible):
    """QFormLayout 行显隐：同时处理字段控件和自动生成的行标签。"""
    widget.setVisible(visible)
    label = form_layout.labelForField(widget)
    if label:
        label.setVisible(visible)


def _ispin(value=0, lo=0, hi=999999999):
    s = QSpinBox()
    s.setRange(lo, hi)
    s.setValue(value)
    return s


# ═══════════════════════════════════════════════════════════════
# 变量模板输入框
# ═══════════════════════════════════════════════════════════════

class VariableLineEdit(QLineEdit):
    """支持 {VAR} 变量自动补全的输入框。

    当用户输入 '{' 时弹出变量列表，支持过滤、方向键导航、
    Enter/点击插入。
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._variables: list = []  # [(name, description), ...]
        self._popup = QListWidget()
        self._popup.setWindowFlags(Qt.ToolTip)
        self._popup.setMaximumHeight(200)
        self._popup.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._popup.itemClicked.connect(self._insert_selected)
        self.textChanged.connect(self._on_text_changed)

    def set_available_variables(self, variables):
        """设置可用变量列表。variables: [(name, description), ...]"""
        self._variables = list(variables)

    def _on_text_changed(self, text):
        cursor_pos = self.cursorPosition()

        # 查找光标前最近的未关闭 '{'
        prefix_text = text[:cursor_pos]
        brace_pos = prefix_text.rfind('{')
        if brace_pos < 0:
            self._popup.hide()
            return

        # 检查 '{' 和光标之间是否有 '}'（已关闭则不弹出）
        between = prefix_text[brace_pos + 1:]
        if '}' in between:
            self._popup.hide()
            return

        # 检查是否是转义 '{{' 
        if brace_pos > 0 and prefix_text[brace_pos - 1] == '{':
            self._popup.hide()
            return

        # 提取过滤前缀（'{' 后面已输入的字符）
        filter_text = between.upper()

        self._popup.clear()
        for name, desc in self._variables:
            if filter_text and filter_text not in name.upper():
                continue
            item = QListWidgetItem(f"{{{name}}}  —  {desc}")
            item.setData(Qt.UserRole, name)
            self._popup.addItem(item)

        if self._popup.count() == 0:
            self._popup.hide()
            return

        self._popup.setCurrentRow(0)

        # 定位弹窗
        rect = self.rect()
        global_pos = self.mapToGlobal(rect.bottomLeft())
        self._popup.move(global_pos)
        self._popup.setFixedWidth(max(rect.width(), 300))
        self._popup.show()

    def _insert_selected(self, item=None):
        if item is None:
            item = self._popup.currentItem()
        if item is None:
            return

        var_name = item.data(Qt.UserRole)
        text = self.text()
        cursor_pos = self.cursorPosition()

        # 找到光标前的 '{' 位置
        prefix_text = text[:cursor_pos]
        brace_pos = prefix_text.rfind('{')
        if brace_pos < 0:
            return

        # 替换 '{...' 为 '{VAR_NAME}'
        new_text = text[:brace_pos] + '{' + var_name + '}' + text[cursor_pos:]
        self.setText(new_text)
        self.setCursorPosition(brace_pos + len(var_name) + 2)
        self._popup.hide()

    def keyPressEvent(self, event):
        if self._popup.isVisible():
            if event.key() == Qt.Key_Down:
                row = self._popup.currentRow()
                if row < self._popup.count() - 1:
                    self._popup.setCurrentRow(row + 1)
                return
            elif event.key() == Qt.Key_Up:
                row = self._popup.currentRow()
                if row > 0:
                    self._popup.setCurrentRow(row - 1)
                return
            elif event.key() in (Qt.Key_Return, Qt.Key_Enter):
                self._insert_selected()
                return
            elif event.key() == Qt.Key_Escape:
                self._popup.hide()
                return

        super().keyPressEvent(event)

    def focusOutEvent(self, event):
        # 延迟隐藏以允许点击 popup 项
        from PyQt5.QtCore import QTimer
        QTimer.singleShot(200, self._popup.hide)
        super().focusOutEvent(event)


# ═══════════════════════════════════════════════════════════════
# 环境变量编辑表格
# ═══════════════════════════════════════════════════════════════

class EnvVarTable(QWidget):
    """环境变量键值对编辑器。"""
    changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._table = QTableWidget(0, 2)
        self._table.setHorizontalHeaderLabels(["变量名", "值"])
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setMaximumHeight(120)
        layout.addWidget(self._table)

        btn_row = QHBoxLayout()
        btn_add = QPushButton("+ 添加")
        btn_add.clicked.connect(self._add_row)
        btn_del = QPushButton("- 删除选中")
        btn_del.clicked.connect(self._del_selected)
        btn_row.addWidget(btn_add)
        btn_row.addWidget(btn_del)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        self._table.cellChanged.connect(lambda: self.changed.emit())

    def load(self, env_vars: dict):
        self._table.blockSignals(True)
        self._table.setRowCount(0)
        for k, v in env_vars.items():
            row = self._table.rowCount()
            self._table.insertRow(row)
            self._table.setItem(row, 0, QTableWidgetItem(k))
            self._table.setItem(row, 1, QTableWidgetItem(v))
        self._table.blockSignals(False)

    def get_env_vars(self) -> dict:
        result = {}
        for row in range(self._table.rowCount()):
            k_item = self._table.item(row, 0)
            v_item = self._table.item(row, 1)
            k = k_item.text().strip() if k_item else ""
            v = v_item.text() if v_item else ""
            if k:
                result[k] = v
        return result

    def _add_row(self):
        row = self._table.rowCount()
        self._table.insertRow(row)
        self._table.setItem(row, 0, QTableWidgetItem(""))
        self._table.setItem(row, 1, QTableWidgetItem(""))

    def _del_selected(self):
        rows = sorted(set(i.row() for i in self._table.selectedItems()), reverse=True)
        for r in rows:
            self._table.removeRow(r)
        self.changed.emit()


# ═══════════════════════════════════════════════════════════════
# TaskQueueEditor — 队列总览
# ═══════════════════════════════════════════════════════════════

class TaskQueueEditor(QWidget):
    """任务队列总览编辑器。"""
    property_changed = pyqtSignal()
    request_run_queue = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)

        # 运行按钮
        btn_row = QHBoxLayout()
        self._btn_run = QPushButton("▶ 运行全部")
        self._btn_run.clicked.connect(self.request_run_queue.emit)
        btn_row.addStretch()
        btn_row.addWidget(self._btn_run)
        layout.addLayout(btn_row)

        # 错误处理策略
        policy_grp = QGroupBox("错误处理策略")
        policy_form = QFormLayout(policy_grp)
        self._retry_count = _ispin(0, 0, 10)
        policy_form.addRow("重试次数:", self._retry_count)

        self._policy_cancel = QRadioButton("取消队列")
        self._policy_skip = QRadioButton("跳过继续")
        self._policy_pause = QRadioButton("暂停等待")
        self._policy_cancel.setChecked(True)
        self._policy_group = QButtonGroup(self)
        self._policy_group.addButton(self._policy_cancel, 0)
        self._policy_group.addButton(self._policy_skip, 1)
        self._policy_group.addButton(self._policy_pause, 2)
        policy_form.addRow("重试耗尽:", self._policy_cancel)
        policy_form.addRow("", self._policy_skip)
        policy_form.addRow("", self._policy_pause)
        layout.addWidget(policy_grp)

        # 队列级环境变量
        env_grp = QGroupBox("环境变量（队列级）")
        env_layout = QVBoxLayout(env_grp)
        self._env_table = EnvVarTable()
        env_layout.addWidget(self._env_table)
        layout.addWidget(env_grp)

        # 状态标签
        self._status_label = QLabel("队列空闲")
        layout.addWidget(self._status_label)

        # 日志输出
        log_grp = QGroupBox("运行日志")
        log_layout = QVBoxLayout(log_grp)
        self._log_output = QTextEdit()
        self._log_output.setReadOnly(True)
        self._log_output.setFont(__import__('PyQt5.QtGui', fromlist=['QFont']).QFont("Consolas", 9))
        self._log_output.setMinimumHeight(120)
        log_layout.addWidget(self._log_output)
        log_btn_row = QHBoxLayout()
        btn_clear_log = QPushButton("清除日志")
        btn_clear_log.clicked.connect(self.clear_log)
        log_btn_row.addStretch()
        log_btn_row.addWidget(btn_clear_log)
        log_layout.addLayout(log_btn_row)
        layout.addWidget(log_grp)

        layout.addStretch()

        # 信号
        self._retry_count.valueChanged.connect(self.property_changed.emit)
        self._policy_group.buttonClicked.connect(lambda: self.property_changed.emit())
        self._env_table.changed.connect(self.property_changed.emit)

    def load(self, queue: TaskQueue):
        self.blockSignals(True)
        self._retry_count.setValue(queue.error_policy.retry_count)
        action = queue.error_policy.after_retries_exhausted
        if action == ErrorAction.CANCEL:
            self._policy_cancel.setChecked(True)
        elif action == ErrorAction.SKIP:
            self._policy_skip.setChecked(True)
        elif action == ErrorAction.PAUSE:
            self._policy_pause.setChecked(True)
        self._env_table.load(queue.env_vars)
        self._status_label.setText(f"共 {len(queue.tasks)} 个任务")
        self.blockSignals(False)

    def apply_to(self, queue: TaskQueue):
        queue.error_policy.retry_count = self._retry_count.value()
        btn_id = self._policy_group.checkedId()
        queue.error_policy.after_retries_exhausted = {
            0: ErrorAction.CANCEL, 1: ErrorAction.SKIP, 2: ErrorAction.PAUSE,
        }.get(btn_id, ErrorAction.CANCEL)
        queue.env_vars = self._env_table.get_env_vars()

    def set_status(self, text: str):
        self._status_label.setText(text)

    def append_log(self, task_name: str, text: str, is_error: bool = False):
        """追加日志文本。is_error=True 时 stderr 用红色显示。"""
        cursor = self._log_output.textCursor()
        cursor.movePosition(cursor.End)
        if is_error:
            fmt = cursor.charFormat()
            fmt.setForeground(__import__('PyQt5.QtGui', fromlist=['QColor']).QColor("#cc0000"))
            cursor.setCharFormat(fmt)
            cursor.insertText(f"[{task_name}|stderr] {text}")
            fmt.setForeground(__import__('PyQt5.QtGui', fromlist=['QColor']).QColor("#000000"))
            cursor.setCharFormat(fmt)
        else:
            cursor.insertText(f"[{task_name}] {text}")
        self._log_output.setTextCursor(cursor)
        self._log_output.ensureCursorVisible()

    def append_system_log(self, text: str):
        """追加系统消息（如任务开始/结束状态）。"""
        cursor = self._log_output.textCursor()
        cursor.movePosition(cursor.End)
        fmt = cursor.charFormat()
        fmt.setForeground(__import__('PyQt5.QtGui', fromlist=['QColor']).QColor("#0066cc"))
        cursor.setCharFormat(fmt)
        cursor.insertText(f">>> {text}\n")
        fmt.setForeground(__import__('PyQt5.QtGui', fromlist=['QColor']).QColor("#000000"))
        cursor.setCharFormat(fmt)
        self._log_output.setTextCursor(cursor)
        self._log_output.ensureCursorVisible()

    def clear_log(self):
        self._log_output.clear()


# ═══════════════════════════════════════════════════════════════
# TaskEditor — 单任务编辑器
# ═══════════════════════════════════════════════════════════════

class TaskEditor(QWidget):
    """单任务编辑器，根据任务类型动态显示对应参数。"""
    property_changed = pyqtSignal()
    request_run_task = pyqtSignal(str)   # task_id

    def __init__(self, parent=None):
        super().__init__(parent)
        self._task_id = ""
        self._model: SceneModel = SceneModel()
        self._prefs = None
        self._exe_ref_prev_idx = 0
        layout = QVBoxLayout(self)

        # 运行按钮
        btn_row = QHBoxLayout()
        self._btn_run = QPushButton("▶ 运行此任务")
        self._btn_run.clicked.connect(lambda: self.request_run_task.emit(self._task_id))
        btn_row.addStretch()
        btn_row.addWidget(self._btn_run)
        layout.addLayout(btn_row)

        # ── 通用区域 ──
        common_grp = QGroupBox("基本信息")
        common_form = QFormLayout(common_grp)
        self._name_edit = QLineEdit()
        common_form.addRow("名称:", self._name_edit)
        self._type_label = QLabel()
        common_form.addRow("类型:", self._type_label)
        self._enabled_chk = QCheckBox("启用")
        self._enabled_chk.setChecked(True)
        common_form.addRow("", self._enabled_chk)
        layout.addWidget(common_grp)

        # ── 执行环境 ──
        exec_grp = QGroupBox("执行环境")
        exec_form = QFormLayout(exec_grp)
        self._exe_ref = QComboBox()
        self._exe_ref.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        exec_form.addRow("程序:", self._exe_ref)
        self._working_dir = QLineEdit()
        self._working_dir.setPlaceholderText("默认使用场景目录")
        exec_form.addRow("工作目录:", self._working_dir)
        layout.addWidget(exec_grp)

        # ── 任务级环境变量 ──
        env_grp = QGroupBox("环境变量（任务级）")
        env_layout = QVBoxLayout(env_grp)
        self._env_table = EnvVarTable()
        env_layout.addWidget(self._env_table)
        layout.addWidget(env_grp)

        # ── Stardis 参数区 ──
        self._stardis_grp = QGroupBox("Stardis 参数")
        stardis_form = QFormLayout(self._stardis_grp)
        self._model_file = QLineEdit()
        self._model_file.setPlaceholderText("场景文件路径 (-M)")
        stardis_form.addRow("模型文件:", self._model_file)
        self._samples = _ispin(1000000, 1, 999999999)
        stardis_form.addRow("样本数 (-n):", self._samples)
        self._threads = _ispin(4, 1, 256)
        stardis_form.addRow("线程 (-t):", self._threads)
        self._verbosity = _ispin(1, 0, 5)
        stardis_form.addRow("详细度 (-V):", self._verbosity)

        # 传导步算法 (-a)
        self._diff_algo = QComboBox()
        self._diff_algo.addItems(["dsphere", "wos"])
        self._diff_algo.setToolTip("传导步算法 (-a):\nδ-Sphere (dsphere) — 默认\nWalk on Spheres (wos)")
        stardis_form.addRow("传导算法 (-a):", self._diff_algo)

        # 相机引用 (IR_RENDER)
        self._camera_ref_label = QLabel("相机引用:")
        self._camera_ref = QComboBox()
        stardis_form.addRow(self._camera_ref_label, self._camera_ref)

        # 探针列表 (PROBE_SOLVE)
        self._probe_list_label = QLabel("探针列表:")
        self._probe_list = QListWidget()
        self._probe_list.setMaximumHeight(100)
        stardis_form.addRow(self._probe_list_label, self._probe_list)

        # 场求解配置 (FIELD_SOLVE)
        self._field_type_label = QLabel("求解类型:")
        self._field_type = QComboBox()
        self._field_type.addItems(["介质平均温度", "面平均温度", "面温度映射", "面通量"])
        stardis_form.addRow(self._field_type_label, self._field_type)
        self._medium_name_label = QLabel("介质名称:")
        self._medium_name = QLineEdit()
        stardis_form.addRow(self._medium_name_label, self._medium_name)
        self._surface_stl_label = QLabel("表面 STL (-s/-S/-F):")
        self._surface_stl = QLineEdit()
        self._surface_stl.setToolTip(
            "输入 STL 文件路径，定义计算表面（必须是模型几何的子集）。\n"
            "计算结果输出到 stdout，需配合 stdout 输出文件捕获。")
        stardis_form.addRow(self._surface_stl_label, self._surface_stl)
        self._field_time_chk = QCheckBox("启用时间范围")
        self._field_time_chk.setToolTip("勾选后指定可选时间范围 [t_start, t_end]")
        stardis_form.addRow("", self._field_time_chk)
        self._field_time_start_label = QLabel("起始时间 (s):")
        self._field_time_start = _spin(0.0, 0, 1e12, 6)
        stardis_form.addRow(self._field_time_start_label, self._field_time_start)
        self._field_time_end_label = QLabel("结束时间 (s):")
        self._field_time_end = _spin(0.0, 0, 1e12, 6)
        stardis_form.addRow(self._field_time_end_label, self._field_time_end)
        self._field_time_chk.toggled.connect(self._on_field_time_toggled)

        # 输出重定向
        self._output_redirect = VariableLineEdit()
        self._output_redirect.setPlaceholderText("stdout 重定向文件名（支持 {变量}）")
        stardis_form.addRow("stdout 输出文件:", self._output_redirect)
        self._stderr_redirect = VariableLineEdit()
        self._stderr_redirect.setPlaceholderText("stderr 重定向文件名（支持 {变量}）")
        stardis_form.addRow("stderr 输出文件:", self._stderr_redirect)

        layout.addWidget(self._stardis_grp)

        # ── HTPP 参数区 ──
        self._htpp_grp = QGroupBox("HTPP 参数")
        htpp_form = QFormLayout(self._htpp_grp)

        # 输入来源
        self._input_from_task_radio = QRadioButton("从任务:")
        self._input_from_file_radio = QRadioButton("指定文件:")
        self._input_group = QButtonGroup(self)
        self._input_group.addButton(self._input_from_task_radio, 0)
        self._input_group.addButton(self._input_from_file_radio, 1)
        self._input_task_combo = QComboBox()
        self._input_file_edit = QLineEdit()
        self._input_file_edit.setPlaceholderText(".ht 文件路径")
        htpp_form.addRow(self._input_from_task_radio, self._input_task_combo)
        htpp_form.addRow(self._input_from_file_radio, self._input_file_edit)

        # HTPP 通用
        self._htpp_threads = _ispin(4, 1, 256)
        htpp_form.addRow("线程:", self._htpp_threads)
        self._force_overwrite = QCheckBox("强制覆盖 (-f)")
        htpp_form.addRow("", self._force_overwrite)
        self._htpp_verbose = QCheckBox("详细 (-v)")
        htpp_form.addRow("", self._htpp_verbose)
        self._htpp_output = VariableLineEdit()
        self._htpp_output.setPlaceholderText("输出文件名 (-o, 支持 {变量})")
        htpp_form.addRow("输出文件:", self._htpp_output)

        # IMAGE 模式
        self._exposure = _spin(1.0, 0, 1e6, 2)
        self._exposure.setToolTip("曝光度乘数，范围 [0, ∞)，默认 1.0")
        htpp_form.addRow("曝光度:", self._exposure)
        self._white_auto = QCheckBox("自动白色缩放")
        self._white_auto.setToolTip("自动时使用图像亮度 99.5% 分位数作为白点")
        self._white_auto.setChecked(True)
        self._white_auto.toggled.connect(self._on_white_auto_toggled)
        htpp_form.addRow("", self._white_auto)
        self._white_scale = _spin(1.0, 0.001, 1e6, 4)
        self._white_scale.setToolTip("手动指定白色缩放因子，范围 (0, ∞)")
        self._white_scale.setEnabled(False)
        htpp_form.addRow("白色缩放:", self._white_scale)

        # MAP 模式
        self._pixel_comp = QComboBox()
        self._pixel_comp.addItems(HTTP_PIXEL_COMPONENTS)
        self._pixel_comp.setToolTip(
            "选择可视化的像素分量:\n"
            "0=X/R, 1=X_stderr, 2=Y/G, 3=Y_stderr,\n"
            "4=Z/B, 5=Z_stderr, 6=Time, 7=Time_stderr"
        )
        htpp_form.addRow("像素分量:", self._pixel_comp)
        self._palette = QComboBox()
        self._palette.addItems(HTTP_PALETTES)
        self._palette.setToolTip("映射可视化使用的调色板（默认 inferno）")
        htpp_form.addRow("调色板:", self._palette)
        self._range_auto = QCheckBox("自动范围")
        self._range_auto.setToolTip("自动时由加载图像数据的最小/最大值决定")
        self._range_auto.setChecked(True)
        self._range_auto.toggled.connect(self._on_range_auto_toggled)
        htpp_form.addRow("", self._range_auto)
        self._range_min = _spin(0, -1e9, 1e9, 4)
        self._range_min.setEnabled(False)
        htpp_form.addRow("最小值:", self._range_min)
        self._range_max = _spin(1, -1e9, 1e9, 4)
        self._range_max.setEnabled(False)
        htpp_form.addRow("最大值:", self._range_max)
        self._gnuplot = QCheckBox("Gnuplot")
        self._gnuplot.setToolTip("输出为 Gnuplot 脚本而非 PPM 图像")
        htpp_form.addRow("", self._gnuplot)

        layout.addWidget(self._htpp_grp)

        # 命令预览
        preview_grp = QGroupBox("命令预览")
        preview_layout = QVBoxLayout(preview_grp)
        self._cmd_preview = QTextEdit()
        self._cmd_preview.setReadOnly(True)
        self._cmd_preview.setMaximumHeight(60)
        preview_layout.addWidget(self._cmd_preview)
        layout.addWidget(preview_grp)

        # 日志输出
        log_grp = QGroupBox("运行日志")
        log_layout = QVBoxLayout(log_grp)
        self._log_output = QTextEdit()
        self._log_output.setReadOnly(True)
        self._log_output.setFont(__import__('PyQt5.QtGui', fromlist=['QFont']).QFont("Consolas", 9))
        self._log_output.setMinimumHeight(100)
        log_layout.addWidget(self._log_output)
        log_btn_row = QHBoxLayout()
        btn_clear_log = QPushButton("清除日志")
        btn_clear_log.clicked.connect(self.clear_log)
        log_btn_row.addStretch()
        log_btn_row.addWidget(btn_clear_log)
        log_layout.addLayout(log_btn_row)
        layout.addWidget(log_grp)

        layout.addStretch()

        # 信号连接 — 通用区域
        self._name_edit.textChanged.connect(self.property_changed.emit)
        self._enabled_chk.toggled.connect(self.property_changed.emit)
        self._exe_ref.activated.connect(self._on_exe_ref_activated)
        self._working_dir.textChanged.connect(self.property_changed.emit)
        self._env_table.changed.connect(self.property_changed.emit)

        # 信号连接 — Stardis 参数
        self._model_file.textChanged.connect(self.property_changed.emit)
        for w in (self._samples, self._threads, self._verbosity):
            w.valueChanged.connect(self.property_changed.emit)
        self._diff_algo.currentIndexChanged.connect(self.property_changed.emit)
        self._camera_ref.currentIndexChanged.connect(self.property_changed.emit)
        self._probe_list.itemChanged.connect(self.property_changed.emit)
        self._field_type.currentIndexChanged.connect(self.property_changed.emit)
        self._medium_name.textChanged.connect(self.property_changed.emit)
        self._surface_stl.textChanged.connect(self.property_changed.emit)
        self._field_time_start.valueChanged.connect(self.property_changed.emit)
        self._field_time_end.valueChanged.connect(self.property_changed.emit)
        self._output_redirect.textChanged.connect(self.property_changed.emit)
        self._stderr_redirect.textChanged.connect(self.property_changed.emit)

        # 信号连接 — HTPP 参数
        self._input_group.buttonClicked.connect(lambda: self.property_changed.emit())
        self._input_task_combo.currentIndexChanged.connect(self.property_changed.emit)
        self._input_file_edit.textChanged.connect(self.property_changed.emit)
        self._htpp_threads.valueChanged.connect(self.property_changed.emit)
        self._force_overwrite.toggled.connect(self.property_changed.emit)
        self._htpp_verbose.toggled.connect(self.property_changed.emit)
        self._htpp_output.textChanged.connect(self.property_changed.emit)
        self._exposure.valueChanged.connect(self.property_changed.emit)
        # _white_auto.toggled 已在 _on_white_auto_toggled 中 emit property_changed，不重复连接
        self._white_scale.valueChanged.connect(self.property_changed.emit)
        self._pixel_comp.currentIndexChanged.connect(self.property_changed.emit)
        self._palette.currentIndexChanged.connect(self.property_changed.emit)
        # _range_auto.toggled 已在 _on_range_auto_toggled 中 emit property_changed，不重复连接
        self._range_min.valueChanged.connect(self.property_changed.emit)
        self._range_max.valueChanged.connect(self.property_changed.emit)
        self._gnuplot.toggled.connect(self.property_changed.emit)

        # 连接命令预览更新
        self.property_changed.connect(self._update_preview)

    def set_model(self, model: SceneModel):
        self._model = model

    def set_preferences(self, prefs):
        """设置编辑器偏好（用于可执行文件下拉列表）。"""
        self._prefs = prefs

    def _populate_exe_combo(self, current_ref: str):
        """根据 exe_tags 填充可执行文件下拉列表。"""
        self._exe_ref.blockSignals(True)
        self._exe_ref.clear()
        if not current_ref:
            self._exe_ref.addItem("（未选择）", "")
        if self._prefs:
            for label in self._prefs.exe_tags:
                self._exe_ref.addItem(label, label)
        if current_ref and (not self._prefs or current_ref not in self._prefs.exe_tags):
            self._exe_ref.addItem(current_ref, current_ref)
        self._exe_ref.addItem("浏览…", "__browse__")
        if current_ref:
            idx = self._exe_ref.findData(current_ref)
            if idx >= 0:
                self._exe_ref.setCurrentIndex(idx)
                self._exe_ref_prev_idx = idx
        else:
            self._exe_ref.setCurrentIndex(0)
            self._exe_ref_prev_idx = 0
        self._exe_ref.blockSignals(False)

    def _on_exe_ref_activated(self, index):
        """处理可执行文件下拉选择，包括"浏览…"文件对话框。"""
        if self._exe_ref.itemData(index) == "__browse__":
            path, _ = QFileDialog.getOpenFileName(
                self, "选择可执行文件", "",
                "可执行文件 (*.exe);;所有文件 (*)")
            if path:
                browse_idx = self._exe_ref.count() - 1
                self._exe_ref.insertItem(browse_idx, path, path)
                self._exe_ref.setCurrentIndex(browse_idx)
                self._exe_ref_prev_idx = browse_idx
                self.property_changed.emit()
            else:
                self._exe_ref.setCurrentIndex(self._exe_ref_prev_idx)
        else:
            self._exe_ref_prev_idx = index
            self.property_changed.emit()

    def load(self, task: Task, model: SceneModel):
        """加载任务数据到编辑器。"""
        self.blockSignals(True)
        self._task_id = task.id
        self._model = model

        # 通用
        self._name_edit.setText(task.name)
        self._enabled_chk.setChecked(task.enabled)
        self._populate_exe_combo(task.exe_ref)
        self._working_dir.setText(task.working_dir)
        self._env_table.load(task.env_vars)

        # 类型标签
        is_stardis = task.task_type == TaskType.STARDIS
        self._stardis_grp.setVisible(is_stardis)
        self._htpp_grp.setVisible(not is_stardis)

        if is_stardis:
            self._load_stardis(task, model)
        else:
            self._load_htpp(task, model)

        self.blockSignals(False)
        self._update_preview()

    def _load_stardis(self, task: Task, model: SceneModel):
        sp = task.stardis_params or StardisParams()
        mode = task.compute_mode

        # 类型标签文本
        mode_labels = {
            ComputeMode.PROBE_SOLVE: "Stardis / 探针求解",
            ComputeMode.FIELD_SOLVE: "Stardis / 场求解",
            ComputeMode.IR_RENDER:   "Stardis / IR 渲染",
        }
        self._type_label.setText(mode_labels.get(mode, "Stardis"))

        self._model_file.setText(sp.model_file)
        self._samples.setValue(sp.samples)
        self._threads.setValue(sp.threads)
        self._verbosity.setValue(sp.verbosity)
        self._output_redirect.setText(task.output_redirect or "")
        self._stderr_redirect.setText(task.stderr_redirect or "")

        # 设置变量自动补全
        avail_vars = list_available_variables(TaskType.STARDIS, mode)
        self._output_redirect.set_available_variables(avail_vars)
        self._stderr_redirect.set_available_variables(avail_vars)

        # 高级选项
        algo = sp.advanced.diff_algorithm or "dsphere"
        idx = self._diff_algo.findText(algo)
        self._diff_algo.setCurrentIndex(idx if idx >= 0 else 0)

        # 按模式显示/隐藏子控件
        is_ir = mode == ComputeMode.IR_RENDER
        is_probe = mode == ComputeMode.PROBE_SOLVE
        is_field = mode == ComputeMode.FIELD_SOLVE

        self._camera_ref_label.setVisible(is_ir)
        self._camera_ref.setVisible(is_ir)
        self._probe_list_label.setVisible(is_probe)
        self._probe_list.setVisible(is_probe)
        self._field_type_label.setVisible(is_field)
        self._field_type.setVisible(is_field)
        self._medium_name_label.setVisible(is_field)
        self._medium_name.setVisible(is_field)
        self._surface_stl_label.setVisible(is_field)
        self._surface_stl.setVisible(is_field)
        self._field_time_chk.setVisible(is_field)
        self._field_time_start_label.setVisible(is_field)
        self._field_time_start.setVisible(is_field)
        self._field_time_end_label.setVisible(is_field)
        self._field_time_end.setVisible(is_field)

        if is_ir:
            self._camera_ref.clear()
            for cam in model.cameras:
                self._camera_ref.addItem(cam.name)
            if sp.camera_ref:
                idx = self._camera_ref.findText(sp.camera_ref)
                if idx >= 0:
                    self._camera_ref.setCurrentIndex(idx)

        elif is_probe:
            self._probe_list.clear()
            for probe in model.probes:
                item = QListWidgetItem(f"{probe.name}")
                item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
                item.setCheckState(Qt.Checked if probe.name in sp.probe_refs else Qt.Unchecked)
                self._probe_list.addItem(item)

        elif is_field:
            fs = sp.field_solve or FieldSolveConfig()
            type_map = {
                FieldSolveType.MEDIUM_TEMP: 0,
                FieldSolveType.SURF_MEAN_TEMP: 1,
                FieldSolveType.SURF_TEMP_MAP: 2,
                FieldSolveType.SURF_FLUX: 3,
            }
            self._field_type.setCurrentIndex(type_map.get(fs.solve_type, 0))
            self._medium_name.setText(fs.medium_name)
            self._surface_stl.setText(fs.surface_stl)
            has_time = fs.time_start is not None
            self._field_time_chk.setChecked(has_time)
            self._field_time_start.setValue(fs.time_start if fs.time_start is not None else 0.0)
            self._field_time_end.setValue(fs.time_end if fs.time_end is not None else 0.0)
            self._field_time_start.setEnabled(has_time)
            self._field_time_end.setEnabled(has_time)
            self._field_time_start_label.setEnabled(has_time)
            self._field_time_end_label.setEnabled(has_time)

    def _load_htpp(self, task: Task, model: SceneModel):
        hp = task.htpp_params or HtppParams()
        mode = task.htpp_mode

        mode_labels = {
            HtppMode.IMAGE: "HTPP / 图像",
            HtppMode.MAP:   "HTPP / 映射",
        }
        self._type_label.setText(mode_labels.get(mode, "HTPP"))

        # 输入来源
        self._input_task_combo.clear()
        # 列出队列中的 IR_RENDER 任务
        for t in model.task_queue.tasks:
            if t.task_type == TaskType.STARDIS and t.compute_mode == ComputeMode.IR_RENDER:
                self._input_task_combo.addItem(t.name, t.id)

        if isinstance(task.input_source, InputFromTask):
            self._input_from_task_radio.setChecked(True)
            idx = self._input_task_combo.findData(task.input_source.task_id)
            if idx >= 0:
                self._input_task_combo.setCurrentIndex(idx)
        elif isinstance(task.input_source, InputFromFile):
            self._input_from_file_radio.setChecked(True)
            self._input_file_edit.setText(task.input_source.file_path)
        else:
            self._input_from_task_radio.setChecked(True)

        self._htpp_threads.setValue(hp.threads)
        self._force_overwrite.setChecked(hp.force_overwrite)
        self._htpp_verbose.setChecked(hp.verbose)
        self._htpp_output.setText(hp.output_file)

        # 设置变量自动补全
        avail_vars = list_available_variables(TaskType.HTPP, htpp_mode=mode)
        self._htpp_output.set_available_variables(avail_vars)

        # IMAGE 模式控件
        is_image = mode == HtppMode.IMAGE
        is_map = mode == HtppMode.MAP
        form = self._htpp_grp.layout()
        _set_form_row_visible(form, self._exposure, is_image)
        _set_form_row_visible(form, self._white_auto, is_image)
        _set_form_row_visible(form, self._white_scale, is_image)
        _set_form_row_visible(form, self._pixel_comp, is_map)
        _set_form_row_visible(form, self._palette, is_map)
        _set_form_row_visible(form, self._range_auto, is_map)
        _set_form_row_visible(form, self._range_min, is_map)
        _set_form_row_visible(form, self._range_max, is_map)
        _set_form_row_visible(form, self._gnuplot, is_map)

        if is_image:
            self._exposure.setValue(hp.exposure)
            self._white_auto.setChecked(hp.white_scale is None)
            self._white_scale.setValue(hp.white_scale or 1.0)
            self._white_scale.setEnabled(hp.white_scale is not None)
        elif is_map:
            self._pixel_comp.setCurrentIndex(hp.pixel_component)
            self._palette.setCurrentText(hp.palette if hp.palette else "inferno")
            self._range_auto.setChecked(hp.range_min is None)
            self._range_min.setValue(hp.range_min or 0)
            self._range_max.setValue(hp.range_max or 1)
            self._range_min.setEnabled(hp.range_min is not None)
            self._range_max.setEnabled(hp.range_min is not None)
            self._gnuplot.setChecked(hp.gnuplot)

    def apply_to(self, task: Task):
        """将编辑器中的值写回任务对象。"""
        task.name = self._name_edit.text()
        task.enabled = self._enabled_chk.isChecked()
        data = self._exe_ref.currentData()
        task.exe_ref = data if data and data != "__browse__" else ""
        task.working_dir = self._working_dir.text()
        task.env_vars = self._env_table.get_env_vars()

        if task.task_type == TaskType.STARDIS:
            self._apply_stardis(task)
        else:
            self._apply_htpp(task)

    def _apply_stardis(self, task: Task):
        if not task.stardis_params:
            task.stardis_params = StardisParams()
        sp = task.stardis_params
        sp.model_file = self._model_file.text()
        sp.samples = self._samples.value()
        sp.threads = self._threads.value()
        sp.verbosity = self._verbosity.value()
        sp.advanced.diff_algorithm = self._diff_algo.currentText()
        task.output_redirect = self._output_redirect.text() or None
        task.stderr_redirect = self._stderr_redirect.text() or None

        if task.compute_mode == ComputeMode.IR_RENDER:
            sp.camera_ref = self._camera_ref.currentText() or None
        elif task.compute_mode == ComputeMode.PROBE_SOLVE:
            refs = []
            for i in range(self._probe_list.count()):
                item = self._probe_list.item(i)
                if item.checkState() == Qt.Checked:
                    refs.append(item.text())
            sp.probe_refs = refs
        elif task.compute_mode == ComputeMode.FIELD_SOLVE:
            if not sp.field_solve:
                sp.field_solve = FieldSolveConfig()
            fs = sp.field_solve
            idx = self._field_type.currentIndex()
            fs.solve_type = [FieldSolveType.MEDIUM_TEMP, FieldSolveType.SURF_MEAN_TEMP,
                             FieldSolveType.SURF_TEMP_MAP, FieldSolveType.SURF_FLUX][idx]
            fs.medium_name = self._medium_name.text()
            fs.surface_stl = self._surface_stl.text()
            if self._field_time_chk.isChecked():
                fs.time_start = self._field_time_start.value()
                fs.time_end = self._field_time_end.value() if self._field_time_end.value() > 0 else None
            else:
                fs.time_start = None
                fs.time_end = None

    def _apply_htpp(self, task: Task):
        if not task.htpp_params:
            task.htpp_params = HtppParams()
        hp = task.htpp_params

        # 输入来源
        if self._input_from_task_radio.isChecked():
            tid = self._input_task_combo.currentData()
            task.input_source = InputFromTask(task_id=tid) if tid else None
        else:
            task.input_source = InputFromFile(file_path=self._input_file_edit.text())

        hp.threads = self._htpp_threads.value()
        hp.force_overwrite = self._force_overwrite.isChecked()
        hp.verbose = self._htpp_verbose.isChecked()
        hp.output_file = self._htpp_output.text()

        if task.htpp_mode == HtppMode.IMAGE:
            hp.exposure = self._exposure.value()
            hp.white_scale = None if self._white_auto.isChecked() else self._white_scale.value()
        elif task.htpp_mode == HtppMode.MAP:
            hp.pixel_component = self._pixel_comp.currentIndex()
            palette = self._palette.currentText()
            hp.palette = "" if palette == "inferno" else palette
            if self._range_auto.isChecked():
                hp.range_min = None
                hp.range_max = None
            else:
                hp.range_min = self._range_min.value()
                hp.range_max = self._range_max.value()
            hp.gnuplot = self._gnuplot.isChecked()

    # ─── HTPP 联动槽 ────────────────────────────────────────────

    def _on_field_time_toggled(self, checked):
        self._field_time_start.setEnabled(checked)
        self._field_time_end.setEnabled(checked)
        self._field_time_start_label.setEnabled(checked)
        self._field_time_end_label.setEnabled(checked)
        self.property_changed.emit()

    def _on_white_auto_toggled(self, checked):
        self._white_scale.setEnabled(not checked)
        self.property_changed.emit()

    def _on_range_auto_toggled(self, checked):
        self._range_min.setEnabled(not checked)
        self._range_max.setEnabled(not checked)
        self.property_changed.emit()

    def append_log(self, text: str, is_error: bool = False):
        """追加日志文本。is_error=True 时 stderr 用红色显示。"""
        cursor = self._log_output.textCursor()
        cursor.movePosition(cursor.End)
        if is_error:
            fmt = cursor.charFormat()
            fmt.setForeground(__import__('PyQt5.QtGui', fromlist=['QColor']).QColor("#cc0000"))
            cursor.setCharFormat(fmt)
            cursor.insertText(text)
            fmt.setForeground(__import__('PyQt5.QtGui', fromlist=['QColor']).QColor("#000000"))
            cursor.setCharFormat(fmt)
        else:
            cursor.insertText(text)
        self._log_output.setTextCursor(cursor)
        self._log_output.ensureCursorVisible()

    def append_system_log(self, text: str):
        """追加系统消息（如任务开始/结束状态）。"""
        cursor = self._log_output.textCursor()
        cursor.movePosition(cursor.End)
        fmt = cursor.charFormat()
        fmt.setForeground(__import__('PyQt5.QtGui', fromlist=['QColor']).QColor("#0066cc"))
        cursor.setCharFormat(fmt)
        cursor.insertText(f">>> {text}\n")
        fmt.setForeground(__import__('PyQt5.QtGui', fromlist=['QColor']).QColor("#000000"))
        cursor.setCharFormat(fmt)
        self._log_output.setTextCursor(cursor)
        self._log_output.ensureCursorVisible()

    def clear_log(self):
        self._log_output.clear()

    def _update_preview(self):
        """根据当前编辑器状态更新命令预览。"""
        try:
            from task_runner.command_builder import CommandBuilder as _CB

            # 查找当前任务
            task = None
            for t in self._model.task_queue.tasks:
                if t.id == self._task_id:
                    task = t
                    break
            if task is None:
                self._cmd_preview.setPlainText("")
                return

            # 从编辑器读回当前值到临时副本
            import copy
            tmp = copy.deepcopy(task)
            self.apply_to(tmp)

            # 构建简化 preview
            parts = [tmp.exe_ref or "<exe>"]

            if tmp.task_type == TaskType.STARDIS and tmp.stardis_params:
                sp = tmp.stardis_params
                args = _CB.build_stardis(
                    sp.model_file, tmp.compute_mode, sp)
                parts.extend(args)
            elif tmp.task_type == TaskType.HTPP and tmp.htpp_params:
                args = _CB.build_htpp(
                    tmp.htpp_mode, tmp.htpp_params, "<input>")
                parts.extend(args)

            cmd = ' '.join(parts)

            # 显示输出重定向（模板原样显示）
            if tmp.output_redirect:
                cmd += f" > {tmp.output_redirect}"
            if tmp.stderr_redirect:
                cmd += f" 2> {tmp.stderr_redirect}"

            self._cmd_preview.setPlainText(cmd)
        except Exception:
            self._cmd_preview.setPlainText("")
