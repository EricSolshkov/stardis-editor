"""
htpp 控制面板 - 用于后处理 htrdr-image 格式图像的 GUI 工具
htpp: High-Tune Post-Process

命令行格式:
  htpp [-fhVv] [-i image_option[:image_option ...]]
       [-m map_option[:map_option ...]] [-o output]
       [-t threads_count] [input]
"""

import os
import json

from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
                             QPushButton, QLineEdit, QLabel, QComboBox,
                             QSpinBox, QDoubleSpinBox, QCheckBox, QFileDialog,
                             QTextEdit, QScrollArea, QTabWidget, QMessageBox,
                             QRadioButton, QButtonGroup, QFrame)
from PyQt5.QtCore import QProcess


class HtppControlPanel(QWidget):
    """htpp 后处理工具控制面板"""

    # 内置调色板列表 (来自 scmap 库，共 48 个，按字母排序)
    PALETTES = [
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

    # 像素分量映射
    PIXEL_COMPONENTS = {
        "0 - X / R": 0,
        "1 - X_stderr": 1,
        "2 - Y / G": 2,
        "3 - Y_stderr": 3,
        "4 - Z / B": 4,
        "5 - Z_stderr": 5,
        "6 - Time": 6,
        "7 - Time_stderr": 7,
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("htpp 控制面板 - 图像后处理")
        self.setMinimumSize(750, 700)

        # 默认路径
        self.htpp_exe_path = ""
        self.working_directory = ""
        self.user_settings = {}
        self.user_settings_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'htpp_user_settings.json'
        )

        # QProcess
        self.process = QProcess(self)
        self.process.readyReadStandardOutput.connect(self.handle_stdout)
        self.process.readyReadStandardError.connect(self.handle_stderr)
        self.process.finished.connect(self.process_finished)

        self.initUI()
        self._load_user_settings()

    def initUI(self):
        """初始化界面"""
        main_layout = QVBoxLayout()

        # 可执行文件和工作目录
        main_layout.addWidget(self.create_exe_group())

        # 标签页
        tabs = QTabWidget()
        
        # 基本参数标签页
        basic_tab = QWidget()
        basic_tab.setLayout(self.create_basic_params_layout())
        tabs.addTab(basic_tab, "基本参数")

        # 图像模式标签页
        image_tab = QWidget()
        image_tab.setLayout(self.create_image_mode_layout())
        tabs.addTab(image_tab, "图像模式 (-i)")

        # 映射模式标签页
        map_tab = QWidget()
        map_tab.setLayout(self.create_map_mode_layout())
        tabs.addTab(map_tab, "映射模式 (-m)")

        main_layout.addWidget(tabs)

        # 命令预览
        main_layout.addWidget(self.create_command_preview_group())

        # 控制按钮
        main_layout.addLayout(self.create_control_buttons())

        # 日志输出
        main_layout.addWidget(self.create_log_group())

        self.setLayout(main_layout)

    # ==================== UI 创建方法 ====================

    def create_exe_group(self):
        """创建可执行文件和工作目录区域"""
        group = QGroupBox("程序设置")
        layout = QVBoxLayout()

        # htpp 可执行文件路径
        exe_layout = QHBoxLayout()
        exe_layout.addWidget(QLabel("htpp 路径:"))
        self.exe_path_edit = QComboBox()
        self.exe_path_edit.setEditable(True)
        self.exe_path_edit.setInsertPolicy(QComboBox.InsertAtTop)
        self.exe_path_edit.setToolTip("选择或输入 htpp 可执行文件路径")
        exe_layout.addWidget(self.exe_path_edit)
        browse_exe_btn = QPushButton("浏览...")
        browse_exe_btn.clicked.connect(self.browse_htpp_exe)
        exe_layout.addWidget(browse_exe_btn)

        search_btn = QPushButton("搜索")
        search_btn.setToolTip("在预配置目录中搜索 htpp.exe")
        search_btn.clicked.connect(self._on_search_exes_clicked)
        exe_layout.addWidget(search_btn)
        layout.addLayout(exe_layout)

        try:
            self.exe_path_edit.currentTextChanged.connect(self._on_exe_changed)
        except Exception:
            pass

        # 工作目录
        work_dir_layout = QHBoxLayout()
        work_dir_layout.addWidget(QLabel("工作目录:"))
        self.work_dir_edit = QComboBox()
        self.work_dir_edit.setEditable(True)
        self.work_dir_edit.setInsertPolicy(QComboBox.InsertAtTop)
        self.work_dir_edit.setToolTip("从下拉选择或输入工作目录")
        work_dir_layout.addWidget(self.work_dir_edit)
        browse_dir_btn = QPushButton("浏览...")
        browse_dir_btn.clicked.connect(self.browse_working_directory)
        work_dir_layout.addWidget(browse_dir_btn)
        try:
            self.work_dir_edit.currentTextChanged.connect(self._on_workdir_changed)
        except Exception:
            pass
        layout.addLayout(work_dir_layout)

        group.setLayout(layout)
        return group

    def create_basic_params_layout(self):
        """创建基本参数布局"""
        layout = QVBoxLayout()

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)

        # 输入文件
        input_group = QGroupBox("输入文件 [input]")
        input_layout = QHBoxLayout()
        input_layout.addWidget(QLabel("输入文件:"))
        self.input_file_edit = QLineEdit()
        self.input_file_edit.setPlaceholderText("选择 htrdr-image 文件 (留空则从 stdin 读取)")
        input_layout.addWidget(self.input_file_edit)
        browse_input_btn = QPushButton("浏览...")
        browse_input_btn.clicked.connect(self.browse_input_file)
        input_layout.addWidget(browse_input_btn)
        input_group.setLayout(input_layout)
        scroll_layout.addWidget(input_group)

        # 输出文件 (-o)
        output_group = QGroupBox("输出文件 (-o)")
        output_layout = QHBoxLayout()
        output_layout.addWidget(QLabel("输出文件:"))
        self.output_file_edit = QLineEdit()
        self.output_file_edit.setPlaceholderText("选择输出文件路径 (留空则输出至 stdout)")
        output_layout.addWidget(self.output_file_edit)
        browse_output_btn = QPushButton("浏览...")
        browse_output_btn.clicked.connect(self.browse_output_file)
        output_layout.addWidget(browse_output_btn)
        output_group.setLayout(output_layout)
        scroll_layout.addWidget(output_group)

        # 后处理类型选择
        pp_type_group = QGroupBox("后处理类型")
        pp_type_layout = QVBoxLayout()
        self.pp_type_group_btn = QButtonGroup(self)
        self.pp_image_radio = QRadioButton("图像模式 (Image) - 色调映射 + sRGB 转换")
        self.pp_map_radio = QRadioButton("映射模式 (Map) - 使用调色板可视化像素分量")
        self.pp_image_radio.setChecked(True)
        self.pp_type_group_btn.addButton(self.pp_image_radio, 0)
        self.pp_type_group_btn.addButton(self.pp_map_radio, 1)
        pp_type_layout.addWidget(self.pp_image_radio)
        pp_type_layout.addWidget(self.pp_map_radio)
        pp_hint = QLabel("提示: 图像模式使用 -i 选项，映射模式使用 -m 选项")
        pp_hint.setStyleSheet("color: gray; font-style: italic;")
        pp_type_layout.addWidget(pp_hint)
        pp_type_group.setLayout(pp_type_layout)
        scroll_layout.addWidget(pp_type_group)

        # 线程数 (-t)
        threads_group = QGroupBox("并行计算 (-t)")
        threads_layout = QHBoxLayout()
        threads_layout.addWidget(QLabel("线程数:"))
        self.threads_spin = QSpinBox()
        self.threads_spin.setRange(1, 256)
        self.threads_spin.setValue(4)
        self.threads_spin.setToolTip("并行计算使用的线程数 (默认为 CPU 核心数)")
        threads_layout.addWidget(self.threads_spin)
        threads_layout.addStretch()
        threads_group.setLayout(threads_layout)
        scroll_layout.addWidget(threads_group)

        # 通用选项
        options_group = QGroupBox("通用选项")
        options_layout = QVBoxLayout()

        self.force_overwrite_check = QCheckBox("强制覆盖输出文件 (-f)")
        self.force_overwrite_check.setToolTip("如果输出文件已存在，则覆盖它")
        options_layout.addWidget(self.force_overwrite_check)

        self.verbose_check = QCheckBox("详细输出 (-v)")
        self.verbose_check.setToolTip("在 stderr 中输出额外信息 (如 white scale、色图等)")
        options_layout.addWidget(self.verbose_check)

        options_group.setLayout(options_layout)
        scroll_layout.addWidget(options_group)

        scroll_layout.addStretch()
        scroll.setWidget(scroll_widget)
        layout.addWidget(scroll)

        return layout

    def create_image_mode_layout(self):
        """创建图像模式参数布局 (-i)"""
        layout = QVBoxLayout()

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)

        info_label = QLabel(
            "图像模式 (-i): 对 XYZ 像素数据进行色调映射 (Filmic Tone Mapping)，\n"
            "然后转换为 sRGB 色彩空间并输出为 PPM 图像。"
        )
        info_label.setStyleSheet("color: #2196F3; padding: 5px;")
        scroll_layout.addWidget(info_label)

        # 曝光度 (exposure)
        exposure_group = QGroupBox("曝光度 (exposure)")
        exposure_layout = QHBoxLayout()
        exposure_layout.addWidget(QLabel("曝光值:"))
        self.exposure_spin = QDoubleSpinBox()
        self.exposure_spin.setRange(0.0, 1e10)
        self.exposure_spin.setDecimals(4)
        self.exposure_spin.setValue(1.0)
        self.exposure_spin.setSingleStep(0.1)
        self.exposure_spin.setToolTip("曝光度乘数，范围 [0, ∞)，默认 1.0")
        exposure_layout.addWidget(self.exposure_spin)
        exposure_layout.addStretch()
        exposure_group.setLayout(exposure_layout)
        scroll_layout.addWidget(exposure_group)

        # 白色缩放因子 (white)
        white_group = QGroupBox("白色缩放因子 (white)")
        white_layout = QVBoxLayout()

        self.white_auto_check = QCheckBox("自动计算 (使用 99.5% 亮度分位数)")
        self.white_auto_check.setChecked(True)
        self.white_auto_check.setToolTip("自动时，htpp 将使用图像亮度 99.5% 分位数作为白点")
        self.white_auto_check.toggled.connect(self._on_white_auto_toggled)
        white_layout.addWidget(self.white_auto_check)

        white_val_layout = QHBoxLayout()
        white_val_layout.addWidget(QLabel("白色值:"))
        self.white_spin = QDoubleSpinBox()
        self.white_spin.setRange(0.001, 1e10)
        self.white_spin.setDecimals(4)
        self.white_spin.setValue(1.0)
        self.white_spin.setSingleStep(0.1)
        self.white_spin.setEnabled(False)
        self.white_spin.setToolTip("手动指定白色缩放因子，范围 (0, ∞)")
        white_val_layout.addWidget(self.white_spin)
        white_val_layout.addStretch()
        white_layout.addLayout(white_val_layout)

        white_group.setLayout(white_layout)
        scroll_layout.addWidget(white_group)

        # 重置为默认
        reset_btn = QPushButton("重置图像参数为默认值")
        reset_btn.clicked.connect(self.reset_image_params)
        scroll_layout.addWidget(reset_btn)

        scroll_layout.addStretch()
        scroll.setWidget(scroll_widget)
        layout.addWidget(scroll)

        return layout

    def create_map_mode_layout(self):
        """创建映射模式参数布局 (-m)"""
        layout = QVBoxLayout()

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)

        info_label = QLabel(
            "映射模式 (-m): 将选定的像素分量映射到调色板上进行可视化。\n"
            "可用于查看不确定度、时间估计等数据。"
        )
        info_label.setStyleSheet("color: #FF9800; padding: 5px;")
        scroll_layout.addWidget(info_label)

        # 像素分量选择 (pixcpnt)
        pixcpnt_group = QGroupBox("像素分量 (pixcpnt)")
        pixcpnt_layout = QHBoxLayout()
        pixcpnt_layout.addWidget(QLabel("分量:"))
        self.pixcpnt_combo = QComboBox()
        for name in self.PIXEL_COMPONENTS.keys():
            self.pixcpnt_combo.addItem(name)
        self.pixcpnt_combo.setToolTip(
            "选择需要可视化的像素分量:\n"
            "0=X/R, 1=X_stderr, 2=Y/G, 3=Y_stderr,\n"
            "4=Z/B, 5=Z_stderr, 6=Time, 7=Time_stderr"
        )
        pixcpnt_layout.addWidget(self.pixcpnt_combo)
        pixcpnt_layout.addStretch()
        pixcpnt_group.setLayout(pixcpnt_layout)
        scroll_layout.addWidget(pixcpnt_group)

        # 调色板 (palette)
        palette_group = QGroupBox("调色板 (palette)")
        palette_layout = QHBoxLayout()
        palette_layout.addWidget(QLabel("调色板:"))
        self.palette_combo = QComboBox()
        self.palette_combo.addItems(self.PALETTES)
        self.palette_combo.setCurrentText("inferno")
        self.palette_combo.setToolTip("选择映射可视化使用的调色板")
        palette_layout.addWidget(self.palette_combo)
        palette_layout.addStretch()
        palette_group.setLayout(palette_layout)
        scroll_layout.addWidget(palette_group)

        # 数据范围 (range)
        range_group = QGroupBox("数据范围 (range)")
        range_layout = QVBoxLayout()

        self.range_auto_check = QCheckBox("自动范围 (使用数据的最小/最大值)")
        self.range_auto_check.setChecked(True)
        self.range_auto_check.setToolTip("自动时，范围由加载的图像数据决定")
        self.range_auto_check.toggled.connect(self._on_range_auto_toggled)
        range_layout.addWidget(self.range_auto_check)

        range_val_layout = QHBoxLayout()
        range_val_layout.addWidget(QLabel("最小值:"))
        self.range_min_spin = QDoubleSpinBox()
        self.range_min_spin.setRange(-1e20, 1e20)
        self.range_min_spin.setDecimals(6)
        self.range_min_spin.setValue(0.0)
        self.range_min_spin.setEnabled(False)
        range_val_layout.addWidget(self.range_min_spin)

        range_val_layout.addWidget(QLabel("最大值:"))
        self.range_max_spin = QDoubleSpinBox()
        self.range_max_spin.setRange(-1e20, 1e20)
        self.range_max_spin.setDecimals(6)
        self.range_max_spin.setValue(1.0)
        self.range_max_spin.setEnabled(False)
        range_val_layout.addWidget(self.range_max_spin)
        range_layout.addLayout(range_val_layout)

        range_group.setLayout(range_layout)
        scroll_layout.addWidget(range_group)

        # Gnuplot 输出
        gnuplot_group = QGroupBox("Gnuplot 输出")
        gnuplot_layout = QVBoxLayout()
        self.gnuplot_check = QCheckBox("输出为 Gnuplot 脚本 (gnuplot)")
        self.gnuplot_check.setToolTip(
            "启用后，结果以 Gnuplot 脚本格式输出，\n"
            "该脚本可生成带有嵌入色条的 PNG 图像"
        )
        gnuplot_layout.addWidget(self.gnuplot_check)
        gnuplot_group.setLayout(gnuplot_layout)
        scroll_layout.addWidget(gnuplot_group)

        # 重置为默认
        reset_btn = QPushButton("重置映射参数为默认值")
        reset_btn.clicked.connect(self.reset_map_params)
        scroll_layout.addWidget(reset_btn)

        scroll_layout.addStretch()
        scroll.setWidget(scroll_widget)
        layout.addWidget(scroll)

        return layout

    def create_command_preview_group(self):
        """创建命令预览区域"""
        group = QGroupBox("命令预览")
        layout = QVBoxLayout()

        self.command_preview = QTextEdit()
        self.command_preview.setReadOnly(True)
        self.command_preview.setMaximumHeight(80)
        self.command_preview.setStyleSheet("font-family: Consolas, monospace;")
        layout.addWidget(self.command_preview)

        btn_layout = QHBoxLayout()
        update_btn = QPushButton("更新预览")
        update_btn.clicked.connect(self.update_command_preview)
        btn_layout.addWidget(update_btn)

        copy_btn = QPushButton("复制命令")
        copy_btn.clicked.connect(self.copy_command_to_clipboard)
        btn_layout.addWidget(copy_btn)

        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        group.setLayout(layout)
        return group

    def create_log_group(self):
        """创建日志输出区域"""
        group = QGroupBox("运行日志")
        layout = QVBoxLayout()

        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setStyleSheet("font-family: Consolas, monospace;")
        layout.addWidget(self.log_output)

        clear_log_btn = QPushButton("清除日志")
        clear_log_btn.clicked.connect(self.log_output.clear)
        layout.addWidget(clear_log_btn)

        group.setLayout(layout)
        return group

    def create_control_buttons(self):
        """创建控制按钮"""
        layout = QHBoxLayout()

        self.run_btn = QPushButton("运行 htpp")
        self.run_btn.clicked.connect(self.run_htpp)
        self.run_btn.setStyleSheet(
            "background-color: #4CAF50; color: white; "
            "font-weight: bold; padding: 10px;"
        )
        layout.addWidget(self.run_btn)

        self.stop_btn = QPushButton("停止")
        self.stop_btn.clicked.connect(self.stop_htpp)
        self.stop_btn.setEnabled(False)
        self.stop_btn.setStyleSheet(
            "background-color: #f44336; color: white; "
            "font-weight: bold; padding: 10px;"
        )
        layout.addWidget(self.stop_btn)

        return layout

    # ==================== 参数构建 ====================

    def build_args(self):
        """构建传递给 QProcess.start 的参数列表"""
        args = []

        # 线程数 (-t)
        if self.threads_spin.value() > 0:
            args.extend(['-t', str(self.threads_spin.value())])

        # 强制覆盖 (-f)
        if self.force_overwrite_check.isChecked():
            args.append('-f')

        # 详细输出 (-v)
        if self.verbose_check.isChecked():
            args.append('-v')

        # 后处理类型
        if self.pp_image_radio.isChecked():
            # 图像模式 (-i)
            img_opts = self._build_image_options()
            if img_opts:
                args.extend(['-i', img_opts])
        elif self.pp_map_radio.isChecked():
            # 映射模式 (-m)
            map_opts = self._build_map_options()
            if map_opts:
                args.extend(['-m', map_opts])

        # 输出文件 (-o)
        output = self.output_file_edit.text().strip()
        if output:
            args.extend(['-o', output])

        # 输入文件 (位置参数，放在最后)
        input_file = self.input_file_edit.text().strip()
        if input_file:
            args.append(input_file)

        return args

    def _build_image_options(self):
        """构建图像模式选项字符串"""
        parts = []

        # exposure
        exposure = self.exposure_spin.value()
        if exposure != 1.0:
            parts.append(f'exposure={exposure}')

        # white
        if not self.white_auto_check.isChecked():
            white = self.white_spin.value()
            parts.append(f'white={white}')

        return ':'.join(parts) if parts else ''

    def _build_map_options(self):
        """构建映射模式选项字符串"""
        parts = []

        # pixcpnt
        pixcpnt_text = self.pixcpnt_combo.currentText()
        pixcpnt_val = self.PIXEL_COMPONENTS.get(pixcpnt_text, 0)
        if pixcpnt_val != 0:
            parts.append(f'pixcpnt={pixcpnt_val}')

        # palette
        palette = self.palette_combo.currentText()
        if palette != "inferno":
            parts.append(f'palette={palette}')

        # range
        if not self.range_auto_check.isChecked():
            rmin = self.range_min_spin.value()
            rmax = self.range_max_spin.value()
            parts.append(f'range={rmin},{rmax}')

        # gnuplot
        if self.gnuplot_check.isChecked():
            parts.append('gnuplot')

        return ':'.join(parts) if parts else ''

    def build_command_display(self):
        """构建用于显示的命令字符串"""
        args = []
        for a in self.build_args():
            if ' ' in a or (',' in a and '"' not in a):
                args.append(f'"{a}"')
            else:
                args.append(a)
        return ' '.join(args)

    # ==================== 交互事件 ====================

    def _on_white_auto_toggled(self, checked):
        """白色自动计算切换"""
        self.white_spin.setEnabled(not checked)

    def _on_range_auto_toggled(self, checked):
        """范围自动计算切换"""
        self.range_min_spin.setEnabled(not checked)
        self.range_max_spin.setEnabled(not checked)

    def reset_image_params(self):
        """重置图像参数为默认值"""
        self.exposure_spin.setValue(1.0)
        self.white_auto_check.setChecked(True)
        self.white_spin.setValue(1.0)

    def reset_map_params(self):
        """重置映射参数为默认值"""
        self.pixcpnt_combo.setCurrentIndex(0)
        self.palette_combo.setCurrentText("inferno")
        self.range_auto_check.setChecked(True)
        self.range_min_spin.setValue(0.0)
        self.range_max_spin.setValue(1.0)
        self.gnuplot_check.setChecked(False)

    # ==================== 文件浏览 ====================

    def browse_htpp_exe(self):
        """浏览 htpp 可执行文件"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择 htpp 可执行文件", "",
            "可执行文件 (*.exe);;所有文件 (*.*)"
        )
        if file_path:
            try:
                self.exe_path_edit.setCurrentText(file_path)
            except Exception:
                try:
                    self.exe_path_edit.setEditText(file_path)
                except Exception:
                    pass
            self.htpp_exe_path = file_path
            self._add_recent_exe(file_path)
            self._save_user_settings()

    def browse_working_directory(self):
        """浏览工作目录"""
        dir_path = QFileDialog.getExistingDirectory(self, "选择工作目录")
        if dir_path:
            try:
                self.work_dir_edit.setCurrentText(dir_path)
            except Exception:
                try:
                    self.work_dir_edit.setEditText(dir_path)
                except Exception:
                    pass
            self.working_directory = dir_path
            self._add_recent_workdir(dir_path)
            self._save_user_settings()

    def browse_input_file(self):
        """浏览输入文件"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择输入文件 (htrdr-image)", "",
            "所有文件 (*.*)"
        )
        if file_path:
            self.input_file_edit.setText(file_path)

    def browse_output_file(self):
        """浏览输出文件"""
        file_path, _ = QFileDialog.getSaveFileName(
            self, "保存输出文件", "",
            "PPM 图像 (*.ppm);;Gnuplot 脚本 (*.gp *.gnu);;所有文件 (*.*)"
        )
        if file_path:
            self.output_file_edit.setText(file_path)

    # ==================== 命令预览与复制 ====================

    def update_command_preview(self):
        """更新命令预览"""
        exe_path = self.exe_path_edit.currentText() or "htpp.exe"
        command_args = self.build_command_display()
        full_command = f'"{exe_path}" {command_args}'
        self.command_preview.setPlainText(full_command)

    def copy_command_to_clipboard(self):
        """复制命令到剪贴板"""
        from PyQt5.QtWidgets import QApplication
        self.update_command_preview()
        text = self.command_preview.toPlainText()
        clipboard = QApplication.clipboard()
        clipboard.setText(text)
        self.log_output.append("[信息] 命令已复制到剪贴板")

    # ==================== 运行控制 ====================

    def run_htpp(self):
        """运行 htpp"""
        # 验证可执行文件
        exe_text = self.exe_path_edit.currentText()
        if not exe_text:
            QMessageBox.warning(self, "错误", "请指定 htpp 可执行文件路径！")
            return

        if not os.path.exists(exe_text):
            QMessageBox.warning(self, "错误", f"htpp 可执行文件不存在:\n{exe_text}")
            return

        # 验证输入文件（可选，因为 htpp 可以从 stdin 读取）
        input_file = self.input_file_edit.text().strip()
        if input_file and not os.path.exists(input_file):
            QMessageBox.warning(self, "错误", f"输入文件不存在:\n{input_file}")
            return

        # 设置工作目录
        wd = self.work_dir_edit.currentText()
        if wd and os.path.exists(wd):
            self.process.setWorkingDirectory(wd)
        else:
            wd = None

        # 构建参数
        argv = self.build_args()

        # 清除日志并输出运行信息
        self.log_output.clear()
        self.log_output.append(f"[启动] 运行目录: {wd or '未设置'}")
        self.log_output.append(f"[启动] 可执行文件: {exe_text}")
        self.log_output.append(f"[启动] 参数: {' '.join(argv)}")
        self.log_output.append("-" * 80)

        # 启动进程
        self.process.start(exe_text, argv)

        # 更新按钮状态
        self.run_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)

    def stop_htpp(self):
        """停止 htpp 进程"""
        if self.process.state() == QProcess.Running:
            self.process.kill()
            self.log_output.append("\n[终止] 进程已被用户终止")

    def handle_stdout(self):
        """处理标准输出"""
        data = self.process.readAllStandardOutput()
        text = bytes(data).decode('utf-8', errors='ignore')
        self.log_output.append(text)
        self.log_output.moveCursor(self.log_output.textCursor().End)

    def handle_stderr(self):
        """处理标准错误"""
        data = self.process.readAllStandardError()
        text = bytes(data).decode('utf-8', errors='ignore')
        self.log_output.append(f"[stderr] {text}")
        self.log_output.moveCursor(self.log_output.textCursor().End)

    def process_finished(self, exit_code, exit_status):
        """进程结束"""
        self.log_output.append("-" * 80)
        if exit_code == 0:
            self.log_output.append(f"[完成] 进程成功结束 (退出码: {exit_code})")
        else:
            self.log_output.append(f"[错误] 进程异常结束 (退出码: {exit_code})")

        # 恢复按钮状态
        self.run_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)

    # ==================== 配置保存/加载 ====================

    def save_configuration(self):
        """保存当前配置到文件"""
        file_path, _ = QFileDialog.getSaveFileName(
            self, "保存 htpp 配置", "",
            "JSON 文件 (*.json);;所有文件 (*.*)"
        )
        if not file_path:
            return

        config = {
            'htpp_config_version': '1.0',
            'input_file': self.input_file_edit.text(),
            'output_file': self.output_file_edit.text(),
            'threads': self.threads_spin.value(),
            'force_overwrite': self.force_overwrite_check.isChecked(),
            'verbose': self.verbose_check.isChecked(),
            'pp_type': 'image' if self.pp_image_radio.isChecked() else 'map',
            'image': {
                'exposure': self.exposure_spin.value(),
                'white_auto': self.white_auto_check.isChecked(),
                'white': self.white_spin.value(),
            },
            'map': {
                'pixcpnt': self.pixcpnt_combo.currentIndex(),
                'palette': self.palette_combo.currentText(),
                'range_auto': self.range_auto_check.isChecked(),
                'range_min': self.range_min_spin.value(),
                'range_max': self.range_max_spin.value(),
                'gnuplot': self.gnuplot_check.isChecked(),
            }
        }

        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
            QMessageBox.information(self, "成功", f"配置已保存:\n{file_path}")
        except Exception as e:
            QMessageBox.warning(self, "错误", f"保存失败:\n{str(e)}")

    def load_configuration(self):
        """从文件加载配置"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "加载 htpp 配置", "",
            "JSON 文件 (*.json);;所有文件 (*.*)"
        )
        if not file_path:
            return

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                config = json.load(f)

            # 基本参数
            self.input_file_edit.setText(config.get('input_file', ''))
            self.output_file_edit.setText(config.get('output_file', ''))
            self.threads_spin.setValue(config.get('threads', 4))
            self.force_overwrite_check.setChecked(config.get('force_overwrite', False))
            self.verbose_check.setChecked(config.get('verbose', False))

            # 后处理类型
            pp_type = config.get('pp_type', 'image')
            if pp_type == 'map':
                self.pp_map_radio.setChecked(True)
            else:
                self.pp_image_radio.setChecked(True)

            # 图像参数
            img = config.get('image', {})
            self.exposure_spin.setValue(img.get('exposure', 1.0))
            self.white_auto_check.setChecked(img.get('white_auto', True))
            self.white_spin.setValue(img.get('white', 1.0))

            # 映射参数
            mp = config.get('map', {})
            self.pixcpnt_combo.setCurrentIndex(mp.get('pixcpnt', 0))
            palette = mp.get('palette', 'inferno')
            idx = self.palette_combo.findText(palette)
            if idx >= 0:
                self.palette_combo.setCurrentIndex(idx)
            self.range_auto_check.setChecked(mp.get('range_auto', True))
            self.range_min_spin.setValue(mp.get('range_min', 0.0))
            self.range_max_spin.setValue(mp.get('range_max', 1.0))
            self.gnuplot_check.setChecked(mp.get('gnuplot', False))

            # 更新预览
            self.update_command_preview()
            QMessageBox.information(self, "成功", f"配置已加载:\n{file_path}")
        except Exception as e:
            QMessageBox.warning(self, "错误", f"加载失败:\n{str(e)}")

    # ==================== 用户设置管理 ====================

    def _load_user_settings(self):
        """从磁盘加载用户设置"""
        try:
            if os.path.exists(self.user_settings_path):
                with open(self.user_settings_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.user_settings.update(data)

            # 填充 combobox
            exes = list(dict.fromkeys(self.user_settings.get('recent_exes', [])))
            works = list(dict.fromkeys(self.user_settings.get('recent_work_dirs', [])))

            self.exe_path_edit.clear()
            for e in exes:
                self.exe_path_edit.addItem(e)

            self.work_dir_edit.clear()
            for w in works:
                self.work_dir_edit.addItem(w)

            # 自动选择最近一次
            if works:
                try:
                    self.work_dir_edit.setCurrentText(works[0])
                except Exception:
                    pass
                self.working_directory = works[0]

            if exes:
                try:
                    self.exe_path_edit.setCurrentText(exes[0])
                except Exception:
                    pass
                self.htpp_exe_path = exes[0]

            self._save_user_settings()
        except Exception:
            pass

    def _save_user_settings(self):
        """保存用户设置到磁盘"""
        try:
            self.user_settings['recent_exes'] = list(
                dict.fromkeys(self.user_settings.get('recent_exes', []))
            )
            self.user_settings['recent_work_dirs'] = list(
                dict.fromkeys(self.user_settings.get('recent_work_dirs', []))
            )
            with open(self.user_settings_path, 'w', encoding='utf-8') as f:
                json.dump(self.user_settings, f, indent=2, ensure_ascii=False)
        except Exception:
            pass

    def _add_recent_workdir(self, path):
        """添加最近工作目录"""
        if not path:
            return
        lst = self.user_settings.setdefault('recent_work_dirs', [])
        if path in lst:
            lst.remove(path)
        lst.insert(0, path)
        self.user_settings['recent_work_dirs'] = lst[:20]

    def _add_recent_exe(self, path):
        """添加最近可执行文件"""
        if not path:
            return
        lst = self.user_settings.setdefault('recent_exes', [])
        if path in lst:
            lst.remove(path)
        lst.insert(0, path)
        self.user_settings['recent_exes'] = lst[:50]

    def _on_exe_changed(self, text):
        """可执行文件路径变更"""
        try:
            if text:
                self.htpp_exe_path = text
                self._add_recent_exe(text)
                self._save_user_settings()
        except Exception:
            pass

    def _on_workdir_changed(self, text):
        """工作目录变更"""
        try:
            if text:
                self.working_directory = text
                if os.path.isdir(text):
                    self._add_recent_workdir(text)
                    self._save_user_settings()
        except Exception:
            pass

    def _on_search_exes_clicked(self):
        """搜索 htpp.exe"""
        try:
            found = self._search_exes_in_dirs()
            if not found:
                QMessageBox.information(
                    self, "搜索结果",
                    "未在配置的搜索目录中找到 htpp.exe。\n"
                    "请检查 htpp_user_settings.json 中的 search_dirs。"
                )
                return
            for p in found:
                self._add_recent_exe(p)
            exes = list(dict.fromkeys(self.user_settings.get('recent_exes', [])))
            self.exe_path_edit.clear()
            for e in exes:
                self.exe_path_edit.addItem(e)
            try:
                self.exe_path_edit.setCurrentText(exes[0])
            except Exception:
                pass
            self._save_user_settings()
            QMessageBox.information(
                self, "搜索完成",
                f"找到 {len(found)} 个 htpp.exe，已加入下拉列表。"
            )
        except Exception as e:
            QMessageBox.warning(self, "搜索失败", str(e))

    def _search_exes_in_dirs(self):
        """在配置目录下搜索 htpp.exe"""
        results = []
        try:
            dirs = self.user_settings.get('search_dirs', []) or []
            for d in dirs:
                if not os.path.exists(d):
                    continue
                for root, _, files in os.walk(d):
                    for name in files:
                        if name.lower() == 'htpp.exe':
                            results.append(os.path.join(root, name))
        except Exception:
            pass
        return results


if __name__ == '__main__':
    import sys
    from PyQt5.QtWidgets import QApplication

    app = QApplication(sys.argv)
    app.setApplicationName("htpp Control Panel")
    panel = HtppControlPanel()
    panel.show()
    sys.exit(app.exec_())
