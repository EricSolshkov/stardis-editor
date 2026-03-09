from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, 
                             QPushButton, QLineEdit, QLabel, QComboBox, 
                             QSpinBox, QDoubleSpinBox, QCheckBox, QFileDialog,
                             QTextEdit, QScrollArea, QTabWidget, QMessageBox)
from PyQt5.QtCore import Qt, QProcess
import os
from StardisConfigEnhanced import StardisConfigEnhanced, ConfigLibrary


class StardisControlPanel(QWidget):
    """
    Stardis参数控制面板，用于配置和启动stardis计算
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Stardis Control Panel')
        self.setMinimumSize(800, 600)
        
        # Stardis可执行文件路径和工作目录
        self.stardis_exe_path = ""
        self.working_directory = ""

        # 用户设置（持久化）
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
        self.user_settings_path = os.path.join(project_root, 'user_settings.json')
        self.user_settings = {
            "search_dirs": [],
            "recent_work_dirs": [],
            "recent_exes": []
        }
        
        # QProcess用于运行命令行
        self.process = QProcess(self)
        self.process.readyReadStandardOutput.connect(self.handle_stdout)
        self.process.readyReadStandardError.connect(self.handle_stderr)
        self.process.finished.connect(self.process_finished)
        
        self.init_ui()
        # 保存上一次普通样本数以在 IR 模式切换时恢复
        self._last_samples = None
        # 加载用户设置并填充下拉选项
        try:
            self._load_user_settings()
        except Exception:
            pass
    
    def init_ui(self):
        """初始化UI"""
        main_layout = QVBoxLayout(self)
        
        # 1. Stardis可执行文件配置区域
        exe_group = self.create_executable_group()
        main_layout.addWidget(exe_group)
        
        # 2. 配置管理区域
        config_group = self.create_config_management_group()
        main_layout.addWidget(config_group)
        
        # 3. 创建标签页
        tab_widget = QTabWidget()
        
        # 基本参数标签页
        basic_tab = QWidget()
        basic_tab.setLayout(self.create_basic_params_layout())
        tab_widget.addTab(basic_tab, "基本参数")
        
        # 计算模式标签页
        compute_tab = QWidget()
        compute_tab.setLayout(self.create_compute_modes_layout())
        tab_widget.addTab(compute_tab, "计算模式")
        
        # 高级选项标签页
        advanced_tab = QWidget()
        advanced_tab.setLayout(self.create_advanced_options_layout())
        tab_widget.addTab(advanced_tab, "高级选项")
        
        # 输出选项标签页
        output_tab = QWidget()
        output_tab.setLayout(self.create_output_options_layout())
        tab_widget.addTab(output_tab, "输出选项")
        
        main_layout.addWidget(tab_widget)
        
        # 3. 命令预览区域
        preview_group = self.create_command_preview_group()
        main_layout.addWidget(preview_group)
        
        # 4. 输出日志区域
        log_group = self.create_log_group()
        main_layout.addWidget(log_group)
        
        # 5. 控制按钮
        button_layout = self.create_control_buttons()
        main_layout.addLayout(button_layout)
    
    def create_executable_group(self):
        """创建可执行文件配置区域"""
        group = QGroupBox("Stardis 可执行文件配置")
        layout = QVBoxLayout()
        
        # Stardis.exe路径（可编辑下拉）
        exe_layout = QHBoxLayout()
        exe_layout.addWidget(QLabel("Stardis.exe 路径:"))
        self.exe_path_edit = QComboBox()
        self.exe_path_edit.setEditable(True)
        self.exe_path_edit.setInsertPolicy(QComboBox.InsertAtTop)
        self.exe_path_edit.setToolTip("从下拉选择或输入 Stardis 可执行文件路径")
        exe_layout.addWidget(self.exe_path_edit)
        browse_exe_btn = QPushButton("浏览...")
        browse_exe_btn.clicked.connect(self.browse_stardis_exe)
        exe_layout.addWidget(browse_exe_btn)
        search_exe_btn = QPushButton("搜索 stardis.exe")
        search_exe_btn.setToolTip("在用户配置的搜索目录中查找 stardis.exe（需先在设置中配置搜索目录）")
        search_exe_btn.clicked.connect(self._on_search_exes_clicked)
        exe_layout.addWidget(search_exe_btn)
        # 当下拉内容变化时，更新当前值并持久化（选择或手工输入）
        try:
            self.exe_path_edit.currentTextChanged.connect(self._on_exe_changed)
        except Exception:
            pass
        layout.addLayout(exe_layout)
        
        # 工作目录（可编辑下拉）
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
    
    def create_config_management_group(self):
        """创建配置管理区域"""
        group = QGroupBox("配置管理")
        layout = QHBoxLayout()
        
        # 打开配置管理器
        manage_config_btn = QPushButton("配置管理器")
        manage_config_btn.setIcon(self.style().standardIcon(self.style().SP_DirIcon))
        manage_config_btn.clicked.connect(self.open_config_manager)
        manage_config_btn.setToolTip("打开配置库管理器，浏览、加载、管理所有配置")
        manage_config_btn.setStyleSheet("background-color: #2196F3; color: white; font-weight: bold; padding: 8px;")
        layout.addWidget(manage_config_btn)
        
        save_config_btn = QPushButton("快速保存")
        save_config_btn.setIcon(self.style().standardIcon(self.style().SP_DialogSaveButton))
        save_config_btn.clicked.connect(self.quick_save_configuration)
        save_config_btn.setToolTip("快速保存当前参数配置")
        layout.addWidget(save_config_btn)
        
        load_config_btn = QPushButton("快速加载")
        load_config_btn.setIcon(self.style().standardIcon(self.style().SP_DialogOpenButton))
        load_config_btn.clicked.connect(self.quick_load_configuration)
        load_config_btn.setToolTip("从文件快速加载参数配置")
        layout.addWidget(load_config_btn)
        
        layout.addStretch()
        
        group.setLayout(layout)
        return group
    
    def create_basic_params_layout(self):
        """创建基本参数布局"""
        layout = QVBoxLayout()
        
        # 创建滚动区域
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)
        
        # 模型文件 (-M) - 必需参数
        model_group = QGroupBox("模型文件 (-M) *必需")
        model_layout = QVBoxLayout()
        
        model_file_layout = QHBoxLayout()
        self.model_file_edit = QLineEdit()
        self.model_file_edit.setPlaceholderText("选择模型文件...")
        model_file_layout.addWidget(QLabel("模型文件:"))
        model_file_layout.addWidget(self.model_file_edit)
        browse_model_btn = QPushButton("浏览...")
        browse_model_btn.clicked.connect(self.browse_model_file)
        model_file_layout.addWidget(browse_model_btn)
        model_layout.addLayout(model_file_layout)
        
        model_group.setLayout(model_layout)
        scroll_layout.addWidget(model_group)
        
        # 样本数 (-n)
        samples_group = QGroupBox("Monte Carlo 样本数 (-n)")
        samples_layout = QHBoxLayout()
        samples_layout.addWidget(QLabel("样本数:"))
        self.samples_spin = QSpinBox()
        self.samples_spin.setRange(1, 1000000000)
        self.samples_spin.setValue(1000000)
        self.samples_spin.setToolTip("Monte Carlo模拟的样本数量")
        samples_layout.addWidget(self.samples_spin)
        samples_layout.addStretch()
        samples_group.setLayout(samples_layout)
        scroll_layout.addWidget(samples_group)
        
        # 线程数 (-t)
        threads_group = QGroupBox("并行计算 (-t)")
        threads_layout = QHBoxLayout()
        threads_layout.addWidget(QLabel("线程数:"))
        self.threads_spin = QSpinBox()
        self.threads_spin.setRange(1, 256)
        self.threads_spin.setValue(4)
        self.threads_spin.setToolTip("并行计算使用的线程数")
        threads_layout.addWidget(self.threads_spin)
        threads_layout.addStretch()
        threads_group.setLayout(threads_layout)
        scroll_layout.addWidget(threads_group)
        
        # 详细度 (-V)
        verbosity_group = QGroupBox("详细度 (-V)")
        verbosity_layout = QHBoxLayout()
        verbosity_layout.addWidget(QLabel("详细度级别:"))
        self.verbosity_combo = QComboBox()
        self.verbosity_combo.addItems(["0 - 静默", "1 - 基本", "2 - 详细", "3 - 调试"])
        self.verbosity_combo.setCurrentIndex(1)
        self.verbosity_combo.setToolTip("日志输出的详细程度")
        verbosity_layout.addWidget(self.verbosity_combo)
        verbosity_layout.addStretch()
        verbosity_group.setLayout(verbosity_layout)
        scroll_layout.addWidget(verbosity_group)
        
        scroll_layout.addStretch()
        scroll.setWidget(scroll_widget)
        layout.addWidget(scroll)
        
        return layout
    
    def create_compute_modes_layout(self):
        """创建计算模式布局"""
        layout = QVBoxLayout()
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)
        
        # 温度探针 - 体积 (-p)
        probe_vol_group = QGroupBox("体积温度探针 (-p)")
        probe_vol_layout = QVBoxLayout()
        self.probe_vol_enable = QCheckBox("启用体积温度探针")
        probe_vol_layout.addWidget(self.probe_vol_enable)
        
        pos_layout = QHBoxLayout()
        pos_layout.addWidget(QLabel("位置 (x,y,z):"))
        self.probe_vol_x = QDoubleSpinBox()
        self.probe_vol_x.setRange(-1e10, 1e10)
        self.probe_vol_x.setDecimals(6)
        self.probe_vol_y = QDoubleSpinBox()
        self.probe_vol_y.setRange(-1e10, 1e10)
        self.probe_vol_y.setDecimals(6)
        self.probe_vol_z = QDoubleSpinBox()
        self.probe_vol_z.setRange(-1e10, 1e10)
        self.probe_vol_z.setDecimals(6)
        pos_layout.addWidget(self.probe_vol_x)
        pos_layout.addWidget(self.probe_vol_y)
        pos_layout.addWidget(self.probe_vol_z)
        probe_vol_layout.addLayout(pos_layout)
        
        time_layout = QHBoxLayout()
        time_layout.addWidget(QLabel("时间范围 (可选):"))
        self.probe_vol_t1 = QDoubleSpinBox()
        self.probe_vol_t1.setRange(0, 1e10)
        self.probe_vol_t1.setDecimals(6)
        self.probe_vol_t1.setSpecialValueText("稳态")
        time_layout.addWidget(QLabel("t1:"))
        time_layout.addWidget(self.probe_vol_t1)
        self.probe_vol_t2 = QDoubleSpinBox()
        self.probe_vol_t2.setRange(0, 1e10)
        self.probe_vol_t2.setDecimals(6)
        self.probe_vol_t2.setSpecialValueText("稳态")
        time_layout.addWidget(QLabel("t2:"))
        time_layout.addWidget(self.probe_vol_t2)
        probe_vol_layout.addLayout(time_layout)
        
        probe_vol_group.setLayout(probe_vol_layout)
        scroll_layout.addWidget(probe_vol_group)
        
        # 温度探针 - 表面 (-P)
        probe_surf_group = QGroupBox("表面温度探针 (-P)")
        probe_surf_layout = QVBoxLayout()
        self.probe_surf_enable = QCheckBox("启用表面温度探针")
        probe_surf_layout.addWidget(self.probe_surf_enable)
        
        pos_surf_layout = QHBoxLayout()
        pos_surf_layout.addWidget(QLabel("位置 (x,y,z):"))
        self.probe_surf_x = QDoubleSpinBox()
        self.probe_surf_x.setRange(-1e10, 1e10)
        self.probe_surf_x.setDecimals(6)
        self.probe_surf_y = QDoubleSpinBox()
        self.probe_surf_y.setRange(-1e10, 1e10)
        self.probe_surf_y.setDecimals(6)
        self.probe_surf_z = QDoubleSpinBox()
        self.probe_surf_z.setRange(-1e10, 1e10)
        self.probe_surf_z.setDecimals(6)
        pos_surf_layout.addWidget(self.probe_surf_x)
        pos_surf_layout.addWidget(self.probe_surf_y)
        pos_surf_layout.addWidget(self.probe_surf_z)
        probe_surf_layout.addLayout(pos_surf_layout)
        
        side_layout = QHBoxLayout()
        side_layout.addWidget(QLabel("侧面标识:"))
        self.probe_surf_side = QLineEdit()
        self.probe_surf_side.setPlaceholderText("例如: +x, -y, +z")
        side_layout.addWidget(self.probe_surf_side)
        probe_surf_layout.addLayout(side_layout)
        
        probe_surf_group.setLayout(probe_surf_layout)
        scroll_layout.addWidget(probe_surf_group)
        
        # 通量密度探针 - 表面 (-f)
        flux_surf_group = QGroupBox("表面通量密度探针 (-f)")
        flux_surf_layout = QVBoxLayout()
        self.flux_surf_enable = QCheckBox("启用表面通量密度探针")
        flux_surf_layout.addWidget(self.flux_surf_enable)
        
        flux_pos_layout = QHBoxLayout()
        flux_pos_layout.addWidget(QLabel("位置 (x,y,z):"))
        self.flux_surf_x = QDoubleSpinBox()
        self.flux_surf_x.setRange(-1e10, 1e10)
        self.flux_surf_x.setDecimals(6)
        self.flux_surf_y = QDoubleSpinBox()
        self.flux_surf_y.setRange(-1e10, 1e10)
        self.flux_surf_y.setDecimals(6)
        self.flux_surf_z = QDoubleSpinBox()
        self.flux_surf_z.setRange(-1e10, 1e10)
        self.flux_surf_z.setDecimals(6)
        flux_pos_layout.addWidget(self.flux_surf_x)
        flux_pos_layout.addWidget(self.flux_surf_y)
        flux_pos_layout.addWidget(self.flux_surf_z)
        flux_surf_layout.addLayout(flux_pos_layout)
        
        flux_surf_group.setLayout(flux_surf_layout)
        scroll_layout.addWidget(flux_surf_group)
        
        # 介质平均温度 (-m)
        medium_temp_group = QGroupBox("介质平均温度 (-m)")
        medium_temp_layout = QVBoxLayout()
        self.medium_temp_enable = QCheckBox("启用介质平均温度计算")
        medium_temp_layout.addWidget(self.medium_temp_enable)
        
        medium_layout = QHBoxLayout()
        medium_layout.addWidget(QLabel("介质名称:"))
        self.medium_name = QLineEdit()
        self.medium_name.setPlaceholderText("输入介质名称...")
        medium_layout.addWidget(self.medium_name)
        medium_temp_layout.addLayout(medium_layout)
        
        medium_temp_group.setLayout(medium_temp_layout)
        scroll_layout.addWidget(medium_temp_group)
        
        # 表面平均温度 (-s)
        surf_mean_temp_group = QGroupBox("表面平均温度 (-s)")
        surf_mean_temp_layout = QVBoxLayout()
        self.surf_mean_temp_enable = QCheckBox("启用表面平均温度计算")
        surf_mean_temp_layout.addWidget(self.surf_mean_temp_enable)
        
        surf_mean_file_layout = QHBoxLayout()
        surf_mean_file_layout.addWidget(QLabel("求解文件:"))
        self.surf_mean_temp_file = QLineEdit()
        surf_mean_file_layout.addWidget(self.surf_mean_temp_file)
        browse_surf_mean_btn = QPushButton("浏览...")
        browse_surf_mean_btn.clicked.connect(lambda: self.browse_file(self.surf_mean_temp_file))
        surf_mean_file_layout.addWidget(browse_surf_mean_btn)
        surf_mean_temp_layout.addLayout(surf_mean_file_layout)
        
        surf_mean_temp_group.setLayout(surf_mean_temp_layout)
        scroll_layout.addWidget(surf_mean_temp_group)
        
        # 表面温度图 (-S)
        surf_temp_map_group = QGroupBox("表面温度图 (-S)")
        surf_temp_map_layout = QVBoxLayout()
        self.surf_temp_map_enable = QCheckBox("启用表面温度图计算")
        surf_temp_map_layout.addWidget(self.surf_temp_map_enable)
        
        surf_map_file_layout = QHBoxLayout()
        surf_map_file_layout.addWidget(QLabel("求解文件:"))
        self.surf_temp_map_file = QLineEdit()
        surf_map_file_layout.addWidget(self.surf_temp_map_file)
        browse_surf_map_btn = QPushButton("浏览...")
        browse_surf_map_btn.clicked.connect(lambda: self.browse_file(self.surf_temp_map_file))
        surf_map_file_layout.addWidget(browse_surf_map_btn)
        surf_temp_map_layout.addLayout(surf_map_file_layout)
        
        surf_temp_map_group.setLayout(surf_temp_map_layout)
        scroll_layout.addWidget(surf_temp_map_group)
        
        # 表面通量 (-F)
        surf_flux_group = QGroupBox("表面通量 (-F)")
        surf_flux_layout = QVBoxLayout()
        self.surf_flux_enable = QCheckBox("启用表面通量计算")
        surf_flux_layout.addWidget(self.surf_flux_enable)
        
        surf_flux_file_layout = QHBoxLayout()
        surf_flux_file_layout.addWidget(QLabel("求解文件:"))
        self.surf_flux_file = QLineEdit()
        surf_flux_file_layout.addWidget(self.surf_flux_file)
        browse_surf_flux_btn = QPushButton("浏览...")
        browse_surf_flux_btn.clicked.connect(lambda: self.browse_file(self.surf_flux_file))
        surf_flux_file_layout.addWidget(browse_surf_flux_btn)
        surf_flux_layout.addLayout(surf_flux_file_layout)
        
        surf_flux_group.setLayout(surf_flux_layout)
        scroll_layout.addWidget(surf_flux_group)
        
        # 红外图像 (-R)
        ir_image_group = QGroupBox("红外图像渲染 (-R)")
        ir_image_layout = QVBoxLayout()
        self.ir_image_enable = QCheckBox("启用红外图像渲染")
        ir_image_layout.addWidget(self.ir_image_enable)
        # 切换 IR 模式时禁用/启用样本数输入（IR 使用相机 SPP）
        try:
            self.ir_image_enable.toggled.connect(self._on_ir_image_toggled)
        except Exception:
            pass
        
        # 相机结构化配置
        cam_form_layout = QVBoxLayout()

        # 第一行: spp, imgWxH, fov
        cam_row1 = QHBoxLayout()
        cam_row1.addWidget(QLabel("SPP:"))
        self.ir_image_spp = QSpinBox()
        self.ir_image_spp.setRange(1, 1000000000)
        self.ir_image_spp.setValue(1024)
        cam_row1.addWidget(self.ir_image_spp)

        cam_row1.addWidget(QLabel("分辨率 W x H:"))
        self.ir_image_img_w = QSpinBox()
        self.ir_image_img_w.setRange(1, 10000)
        self.ir_image_img_w.setValue(640)
        self.ir_image_img_h = QSpinBox()
        self.ir_image_img_h.setRange(1, 10000)
        self.ir_image_img_h.setValue(480)
        cam_row1.addWidget(self.ir_image_img_w)
        cam_row1.addWidget(QLabel("x"))
        cam_row1.addWidget(self.ir_image_img_h)

        cam_row1.addWidget(QLabel("FOV:"))
        self.ir_image_fov = QDoubleSpinBox()
        self.ir_image_fov.setRange(0.1, 360.0)
        self.ir_image_fov.setDecimals(3)
        self.ir_image_fov.setValue(30.0)
        cam_row1.addWidget(self.ir_image_fov)
        cam_form_layout.addLayout(cam_row1)

        # 第二行: position
        cam_row2 = QHBoxLayout()
        cam_row2.addWidget(QLabel("位置 pos (x,y,z):"))
        self.ir_pos_x = QDoubleSpinBox()
        self.ir_pos_x.setRange(-1e12, 1e12)
        self.ir_pos_x.setDecimals(6)
        self.ir_pos_y = QDoubleSpinBox()
        self.ir_pos_y.setRange(-1e12, 1e12)
        self.ir_pos_y.setDecimals(6)
        self.ir_pos_z = QDoubleSpinBox()
        self.ir_pos_z.setRange(-1e12, 1e12)
        self.ir_pos_z.setDecimals(6)
        cam_row2.addWidget(self.ir_pos_x)
        cam_row2.addWidget(self.ir_pos_y)
        cam_row2.addWidget(self.ir_pos_z)
        cam_form_layout.addLayout(cam_row2)

        # 第三行: target
        cam_row3 = QHBoxLayout()
        cam_row3.addWidget(QLabel("目标 tgt (x,y,z):"))
        self.ir_tgt_x = QDoubleSpinBox()
        self.ir_tgt_x.setRange(-1e12, 1e12)
        self.ir_tgt_x.setDecimals(6)
        self.ir_tgt_y = QDoubleSpinBox()
        self.ir_tgt_y.setRange(-1e12, 1e12)
        self.ir_tgt_y.setDecimals(6)
        self.ir_tgt_z = QDoubleSpinBox()
        self.ir_tgt_z.setRange(-1e12, 1e12)
        self.ir_tgt_z.setDecimals(6)
        cam_row3.addWidget(self.ir_tgt_x)
        cam_row3.addWidget(self.ir_tgt_y)
        cam_row3.addWidget(self.ir_tgt_z)
        cam_form_layout.addLayout(cam_row3)

        # 第四行: up vector
        cam_row4 = QHBoxLayout()
        cam_row4.addWidget(QLabel("Up 向量 (x,y,z):"))
        self.ir_up_x = QDoubleSpinBox()
        self.ir_up_x.setRange(-1e12, 1e12)
        self.ir_up_x.setDecimals(6)
        self.ir_up_y = QDoubleSpinBox()
        self.ir_up_y.setRange(-1e12, 1e12)
        self.ir_up_y.setDecimals(6)
        self.ir_up_z = QDoubleSpinBox()
        self.ir_up_z.setRange(-1e12, 1e12)
        self.ir_up_z.setDecimals(6)
        self.ir_up_x.setValue(0.0)
        self.ir_up_y.setValue(0.0)
        self.ir_up_z.setValue(1.0)
        cam_row4.addWidget(self.ir_up_x)
        cam_row4.addWidget(self.ir_up_y)
        cam_row4.addWidget(self.ir_up_z)
        cam_form_layout.addLayout(cam_row4)

        ir_image_layout.addLayout(cam_form_layout)
        
        ir_image_group.setLayout(ir_image_layout)
        scroll_layout.addWidget(ir_image_group)
        
        scroll_layout.addStretch()
        scroll.setWidget(scroll_widget)
        layout.addWidget(scroll)
        
        return layout
    
    def create_advanced_options_layout(self):
        """创建高级选项布局"""
        layout = QVBoxLayout()
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)
        
        # 扩散算法 (-a)
        diff_algo_group = QGroupBox("扩散算法 (-a)")
        diff_algo_layout = QHBoxLayout()
        diff_algo_layout.addWidget(QLabel("算法:"))
        self.diff_algo_combo = QComboBox()
        self.diff_algo_combo.addItems(["无", "dsphere", "wos"])
        diff_algo_layout.addWidget(self.diff_algo_combo)
        diff_algo_layout.addStretch()
        diff_algo_group.setLayout(diff_algo_layout)
        scroll_layout.addWidget(diff_algo_group)
        
        # Picard 阶数 (-o)
        picard_group = QGroupBox("Picard 迭代阶数 (-o)")
        picard_layout = QHBoxLayout()
        picard_layout.addWidget(QLabel("阶数:"))
        self.picard_order_spin = QSpinBox()
        self.picard_order_spin.setRange(1, 100)
        self.picard_order_spin.setValue(1)
        picard_layout.addWidget(self.picard_order_spin)
        picard_layout.addStretch()
        picard_group.setLayout(picard_layout)
        scroll_layout.addWidget(picard_group)
        
        # 初始时间 (-I)
        initial_time_group = QGroupBox("初始时间 (-I)")
        initial_time_layout = QHBoxLayout()
        initial_time_layout.addWidget(QLabel("初始时间:"))
        self.initial_time_spin = QDoubleSpinBox()
        self.initial_time_spin.setRange(0, 1e10)
        self.initial_time_spin.setDecimals(6)
        self.initial_time_spin.setSpecialValueText("未设置")
        initial_time_layout.addWidget(self.initial_time_spin)
        initial_time_layout.addStretch()
        initial_time_group.setLayout(initial_time_layout)
        scroll_layout.addWidget(initial_time_group)
        
        # 禁用内部辐射 (-i)
        disable_intrad_group = QGroupBox("内部辐射 (-i)")
        disable_intrad_layout = QHBoxLayout()
        self.disable_intrad_check = QCheckBox("禁用内部辐射")
        disable_intrad_layout.addWidget(self.disable_intrad_check)
        disable_intrad_layout.addStretch()
        disable_intrad_group.setLayout(disable_intrad_layout)
        scroll_layout.addWidget(disable_intrad_group)
        
        # 随机数生成器状态
        rng_group = QGroupBox("随机数生成器状态")
        rng_layout = QVBoxLayout()
        
        rng_in_layout = QHBoxLayout()
        rng_in_layout.addWidget(QLabel("输入状态文件 (-x):"))
        self.rng_state_in = QLineEdit()
        rng_in_layout.addWidget(self.rng_state_in)
        browse_rng_in_btn = QPushButton("浏览...")
        browse_rng_in_btn.clicked.connect(lambda: self.browse_file(self.rng_state_in))
        rng_in_layout.addWidget(browse_rng_in_btn)
        rng_layout.addLayout(rng_in_layout)
        
        rng_out_layout = QHBoxLayout()
        rng_out_layout.addWidget(QLabel("输出状态文件 (-X):"))
        self.rng_state_out = QLineEdit()
        rng_out_layout.addWidget(self.rng_state_out)
        browse_rng_out_btn = QPushButton("浏览...")
        browse_rng_out_btn.clicked.connect(lambda: self.browse_file(self.rng_state_out))
        rng_out_layout.addWidget(browse_rng_out_btn)
        rng_layout.addLayout(rng_out_layout)
        
        rng_group.setLayout(rng_layout)
        scroll_layout.addWidget(rng_group)
        
        # 扩展结果 (-e)
        extended_results_group = QGroupBox("扩展结果 (-e)")
        extended_results_layout = QHBoxLayout()
        self.extended_results_check = QCheckBox("启用扩展结果输出")
        extended_results_layout.addWidget(self.extended_results_check)
        extended_results_layout.addStretch()
        extended_results_group.setLayout(extended_results_layout)
        scroll_layout.addWidget(extended_results_group)
        
        scroll_layout.addStretch()
        scroll.setWidget(scroll_widget)
        layout.addWidget(scroll)
        
        return layout
    
    def create_output_options_layout(self):
        """创建输出选项布局"""
        layout = QVBoxLayout()
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)
        
        # Dump 模型 (-d)
        dump_model_group = QGroupBox("导出模型 (-d)")
        dump_model_layout = QVBoxLayout()
        self.dump_model_enable = QCheckBox("启用模型导出")
        dump_model_layout.addWidget(self.dump_model_enable)
        
        dump_model_file_layout = QHBoxLayout()
        dump_model_file_layout.addWidget(QLabel("输出文件:"))
        self.dump_model_file = QLineEdit()
        dump_model_file_layout.addWidget(self.dump_model_file)
        browse_dump_model_btn = QPushButton("浏览...")
        browse_dump_model_btn.clicked.connect(lambda: self.browse_save_file(self.dump_model_file))
        dump_model_file_layout.addWidget(browse_dump_model_btn)
        dump_model_layout.addLayout(dump_model_file_layout)
        
        dump_model_group.setLayout(dump_model_layout)
        scroll_layout.addWidget(dump_model_group)
        
        # Dump C chunks (-c)
        dump_chunks_group = QGroupBox("导出 C Chunks (-c)")
        dump_chunks_layout = QVBoxLayout()
        self.dump_chunks_enable = QCheckBox("启用 C Chunks 导出")
        dump_chunks_layout.addWidget(self.dump_chunks_enable)
        
        dump_chunks_prefix_layout = QHBoxLayout()
        dump_chunks_prefix_layout.addWidget(QLabel("文件前缀:"))
        self.dump_chunks_prefix = QLineEdit()
        self.dump_chunks_prefix.setPlaceholderText("例如: chunk_")
        dump_chunks_prefix_layout.addWidget(self.dump_chunks_prefix)
        dump_chunks_layout.addLayout(dump_chunks_prefix_layout)
        
        dump_chunks_group.setLayout(dump_chunks_layout)
        scroll_layout.addWidget(dump_chunks_group)
        
        # Dump 路径 (-D)
        dump_paths_group = QGroupBox("导出路径 (-D)")
        dump_paths_layout = QVBoxLayout()
        self.dump_paths_enable = QCheckBox("启用路径导出")
        dump_paths_layout.addWidget(self.dump_paths_enable)
        
        dump_paths_type_layout = QHBoxLayout()
        dump_paths_type_layout.addWidget(QLabel("导出类型:"))
        self.dump_paths_type = QComboBox()
        self.dump_paths_type.addItems(["all", "error", "success"])
        dump_paths_type_layout.addWidget(self.dump_paths_type)
        dump_paths_layout.addLayout(dump_paths_type_layout)
        
        dump_paths_file_layout = QHBoxLayout()
        dump_paths_file_layout.addWidget(QLabel("输出文件:"))
        self.dump_paths_file = QLineEdit()
        dump_paths_file_layout.addWidget(self.dump_paths_file)
        browse_dump_paths_btn = QPushButton("浏览...")
        browse_dump_paths_btn.clicked.connect(lambda: self.browse_save_file(self.dump_paths_file))
        dump_paths_file_layout.addWidget(browse_dump_paths_btn)
        dump_paths_layout.addLayout(dump_paths_file_layout)
        
        dump_paths_group.setLayout(dump_paths_layout)
        scroll_layout.addWidget(dump_paths_group)
        
        # Green 函数 ASCII (-g)
        green_ascii_group = QGroupBox("Green 函数 ASCII 格式 (-g)")
        green_ascii_layout = QHBoxLayout()
        self.green_ascii_enable = QCheckBox("启用 Green 函数 ASCII 输出")
        green_ascii_layout.addWidget(self.green_ascii_enable)
        green_ascii_layout.addStretch()
        green_ascii_group.setLayout(green_ascii_layout)
        scroll_layout.addWidget(green_ascii_group)
        
        # Green 函数二进制 (-G)
        green_bin_group = QGroupBox("Green 函数二进制格式 (-G)")
        green_bin_layout = QVBoxLayout()
        self.green_bin_enable = QCheckBox("启用 Green 函数二进制输出")
        green_bin_layout.addWidget(self.green_bin_enable)
        
        green_bin_file_layout = QHBoxLayout()
        green_bin_file_layout.addWidget(QLabel("输出文件:"))
        self.green_bin_file = QLineEdit()
        green_bin_file_layout.addWidget(self.green_bin_file)
        browse_green_bin_btn = QPushButton("浏览...")
        browse_green_bin_btn.clicked.connect(lambda: self.browse_save_file(self.green_bin_file))
        green_bin_file_layout.addWidget(browse_green_bin_btn)
        green_bin_layout.addLayout(green_bin_file_layout)
        
        green_bin_end_paths_layout = QHBoxLayout()
        green_bin_end_paths_layout.addWidget(QLabel("结束路径文件 (可选):"))
        self.green_bin_end_paths = QLineEdit()
        green_bin_end_paths_layout.addWidget(self.green_bin_end_paths)
        browse_end_paths_btn = QPushButton("浏览...")
        browse_end_paths_btn.clicked.connect(lambda: self.browse_save_file(self.green_bin_end_paths))
        green_bin_end_paths_layout.addWidget(browse_end_paths_btn)
        green_bin_layout.addLayout(green_bin_end_paths_layout)
        
        green_bin_group.setLayout(green_bin_layout)
        scroll_layout.addWidget(green_bin_group)
        
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
        self.command_preview.setMaximumHeight(100)
        layout.addWidget(self.command_preview)
        
        update_btn = QPushButton("更新预览")
        update_btn.clicked.connect(self.update_command_preview)
        layout.addWidget(update_btn)
        
        group.setLayout(layout)
        return group
    
    def create_log_group(self):
        """创建日志输出区域"""
        group = QGroupBox("运行日志")
        layout = QVBoxLayout()
        
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        layout.addWidget(self.log_output)
        
        clear_log_btn = QPushButton("清除日志")
        clear_log_btn.clicked.connect(self.log_output.clear)
        layout.addWidget(clear_log_btn)
        
        group.setLayout(layout)
        return group
    
    def create_control_buttons(self):
        """创建控制按钮"""
        layout = QHBoxLayout()
        
        self.run_btn = QPushButton("运行 Stardis")
        self.run_btn.clicked.connect(self.run_stardis)
        self.run_btn.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold; padding: 10px;")
        layout.addWidget(self.run_btn)
        
        self.stop_btn = QPushButton("停止")
        self.stop_btn.clicked.connect(self.stop_stardis)
        self.stop_btn.setEnabled(False)
        self.stop_btn.setStyleSheet("background-color: #f44336; color: white; font-weight: bold; padding: 10px;")
        layout.addWidget(self.stop_btn)
        
        return layout
    
    # 文件浏览方法
    def browse_stardis_exe(self):
        """浏览Stardis可执行文件"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择 Stardis 可执行文件", "", 
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
            self.stardis_exe_path = file_path
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
    
    def browse_model_file(self):
        """浏览模型文件"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择模型文件", "", "所有文件 (*.*)"
        )
        if file_path:
            self.model_file_edit.setText(file_path)
    
    def browse_file(self, line_edit):
        """通用文件浏览"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择文件", "", "所有文件 (*.*)"
        )
        if file_path:
            line_edit.setText(file_path)
    
    def browse_save_file(self, line_edit):
        """通用保存文件浏览"""
        file_path, _ = QFileDialog.getSaveFileName(
            self, "保存文件", "", "所有文件 (*.*)"
        )
        if file_path:
            line_edit.setText(file_path)
    
    def build_command(self):
        """构建命令行参数列表（不含引号，供 QProcess 直接使用）"""
        args = []
        
        # 模型文件 (必需)
        if self.model_file_edit.text():
            args.extend(['-M', self.model_file_edit.text()])
        
        # 样本数
        # 如果启用了红外渲染模式，则 -n 无效（使用相机 SPP），因此跳过
        if not (hasattr(self, 'ir_image_enable') and self.ir_image_enable.isChecked()):
            if self.samples_spin.value() > 0:
                args.extend(['-n', str(self.samples_spin.value())])
        
        # 线程数
        if self.threads_spin.value() > 1:
            args.extend(['-t', str(self.threads_spin.value())])
        
        # 详细度
        verbosity = self.verbosity_combo.currentIndex()
        if verbosity > 0:
            args.extend(['-V', str(verbosity)])
        
        # 体积温度探针
        if self.probe_vol_enable.isChecked():
            x, y, z = self.probe_vol_x.value(), self.probe_vol_y.value(), self.probe_vol_z.value()
            t1, t2 = self.probe_vol_t1.value(), self.probe_vol_t2.value()
            probe_str = f'{x},{y},{z}'
            if t1 > 0:
                probe_str += f',{t1}'
                if t2 > t1:
                    probe_str += f',{t2}'
            args.extend(['-p', probe_str])
        
        # 表面温度探针
        if self.probe_surf_enable.isChecked():
            x, y, z = self.probe_surf_x.value(), self.probe_surf_y.value(), self.probe_surf_z.value()
            probe_str = f'{x},{y},{z}'
            side = self.probe_surf_side.text().strip()
            if side:
                probe_str += f':{side}'
            args.extend(['-P', probe_str])
        
        # 表面通量密度探针
        if self.flux_surf_enable.isChecked():
            x, y, z = self.flux_surf_x.value(), self.flux_surf_y.value(), self.flux_surf_z.value()
            args.extend(['-f', f'{x},{y},{z}'])
        
        # 介质平均温度
        if self.medium_temp_enable.isChecked() and self.medium_name.text():
            args.extend(['-m', self.medium_name.text()])
        
        # 表面平均温度
        if self.surf_mean_temp_enable.isChecked() and self.surf_mean_temp_file.text():
            args.extend(['-s', self.surf_mean_temp_file.text()])
        
        # 表面温度图
        if self.surf_temp_map_enable.isChecked() and self.surf_temp_map_file.text():
            args.extend(['-S', self.surf_temp_map_file.text()])
        
        # 表面通量
        if self.surf_flux_enable.isChecked() and self.surf_flux_file.text():
            args.extend(['-F', self.surf_flux_file.text()])
        
        # 红外图像 (-R) - 使用结构化字段组装
        if self.ir_image_enable.isChecked():
            try:
                spp = int(self.ir_image_spp.value())
                w = int(self.ir_image_img_w.value())
                h = int(self.ir_image_img_h.value())
                fov = float(self.ir_image_fov.value())
                px = float(self.ir_pos_x.value())
                py = float(self.ir_pos_y.value())
                pz = float(self.ir_pos_z.value())
                tx = float(self.ir_tgt_x.value())
                ty = float(self.ir_tgt_y.value())
                tz = float(self.ir_tgt_z.value())
                ux = float(self.ir_up_x.value())
                uy = float(self.ir_up_y.value())
                uz = float(self.ir_up_z.value())

                cam_parts = [
                    f'spp={spp}',
                    f'img={w}x{h}',
                    f'fov={fov}',
                    f'pos={px},{py},{pz}',
                    f'tgt={tx},{ty},{tz}',
                    f'up={ux},{uy},{uz}'
                ]
                cam_str = ':'.join(cam_parts)
                args.extend(['-R', cam_str])
            except Exception:
                pass
        
        # 扩散算法
        if self.diff_algo_combo.currentIndex() > 0:
            algo = self.diff_algo_combo.currentText()
            args.extend(['-a', algo])
        
        # Picard 阶数
        if self.picard_order_spin.value() > 1:
            args.extend(['-o', str(self.picard_order_spin.value())])
        
        # 初始时间
        if self.initial_time_spin.value() > 0:
            args.extend(['-I', str(self.initial_time_spin.value())])
        
        # 禁用内部辐射
        if self.disable_intrad_check.isChecked():
            args.append('-i')
        
        # 随机数生成器状态
        if self.rng_state_in.text():
            args.extend(['-x', self.rng_state_in.text()])
        if self.rng_state_out.text():
            args.extend(['-X', self.rng_state_out.text()])
        
        # 扩展结果
        if self.extended_results_check.isChecked():
            args.append('-e')
        
        # Dump 模型
        if self.dump_model_enable.isChecked() and self.dump_model_file.text():
            args.extend(['-d', self.dump_model_file.text()])
        
        # Dump C chunks
        if self.dump_chunks_enable.isChecked() and self.dump_chunks_prefix.text():
            args.extend(['-c', self.dump_chunks_prefix.text()])
        
        # Dump 路径
        if self.dump_paths_enable.isChecked() and self.dump_paths_file.text():
            dump_type = self.dump_paths_type.currentText()
            args.extend(['-D', f'{dump_type},{self.dump_paths_file.text()}'])
        
        # Green ASCII
        if self.green_ascii_enable.isChecked():
            args.append('-g')
        
        # Green 二进制
        if self.green_bin_enable.isChecked() and self.green_bin_file.text():
            green_arg = self.green_bin_file.text()
            if self.green_bin_end_paths.text():
                green_arg += f',{self.green_bin_end_paths.text()}'
            args.extend(['-G', green_arg])
        
        return args
    
    @staticmethod
    def _quote_arg(arg):
        """对含空格或特殊字符的参数加引号（用于命令预览显示）"""
        if ' ' in arg or '"' in arg or '\t' in arg:
            return f'"{arg}"'
        return arg

    def build_output_filename(self):
        """构建输出文件名（与原始脚本一致）：IR_rendering_{WIDTH}x{HEIGHT}x{SPP}.ht"""
        if self.ir_image_enable.isChecked():
            w = int(self.ir_image_img_w.value())
            h = int(self.ir_image_img_h.value())
            spp = int(self.ir_image_spp.value())
            return f'IR_rendering_{w}x{h}x{spp}.ht'
        return None

    def update_command_preview(self):
        """更新命令预览"""
        exe_path = (self.exe_path_edit.currentText() if hasattr(self.exe_path_edit, 'currentText') else self.exe_path_edit.text()) or "stardis.exe"
        command_args = self.build_command()
        args_str = ' '.join(self._quote_arg(a) for a in command_args)
        full_command = f'"{exe_path}" {args_str}'
        # 如果启用了红外渲染，显示输出重定向
        output_file = self.build_output_filename()
        if output_file:
            full_command += f' > "{output_file}"'
        self.command_preview.setPlainText(full_command)
    
    def run_stardis(self):
        """运行Stardis"""
        # 验证必需参数
        exe_text = self.exe_path_edit.currentText() if hasattr(self.exe_path_edit, 'currentText') else self.exe_path_edit.text()
        if not exe_text:
            QMessageBox.warning(self, "错误", "请指定 Stardis 可执行文件路径！")
            return
        
        if not os.path.exists(exe_text):
            QMessageBox.warning(self, "错误", "Stardis 可执行文件不存在！")
            return
        
        if not self.model_file_edit.text():
            QMessageBox.warning(self, "错误", "请指定模型文件！")
            return
        
        # 设置工作目录
        # 优先使用 combobox 的当前文本
        wd = self.working_directory
        try:
            wd = self.work_dir_edit.currentText()
        except Exception:
            pass
        if wd and os.path.exists(wd):
            self.process.setWorkingDirectory(wd)
        
        # 构建命令（返回参数列表）
        command_args = self.build_command()
        
        # 清除日志
        self.log_output.clear()
        # 输出实际环境信息，便于调试路径问题
        try:
            self.log_output.append(f"[环境] Python 当前工作目录: {os.getcwd()}")
        except Exception:
            pass
        args_display = ' '.join(self._quote_arg(a) for a in command_args)
        self.log_output.append(f"[启动] 运行目录: {wd or '未设置（将使用 Python 进程工作目录）'}")
        self.log_output.append(f"[启动] 可执行文件: {exe_text}")
        self.log_output.append(f"[启动] 参数: {args_display}")
        self.log_output.append("-" * 80)
        
        # 如果启用了红外渲染，将 stdout 重定向到输出文件
        output_file = self.build_output_filename()
        if output_file:
            # 构建输出文件的完整路径（相对于工作目录）
            output_dir = wd if wd and os.path.exists(wd) else os.getcwd()
            output_path = os.path.join(output_dir, output_file)
            self.process.setStandardOutputFile(output_path)
            self.log_output.append(f"[输出] 重定向到文件: {output_path}")
            self.log_output.append("-" * 80)
        else:
            # 未启用红外渲染时，清除之前可能设置的输出重定向
            self.process.setStandardOutputFile('')

        # 启动进程（直接传递参数列表，QProcess 会正确处理含空格的参数）
        self.process.start(exe_text, command_args)
        
        # 更新按钮状态
        self.run_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
    
    def stop_stardis(self):
        """停止Stardis进程"""
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
        self.log_output.append(f"[错误] {text}")
        self.log_output.moveCursor(self.log_output.textCursor().End)

    def _on_ir_image_toggled(self, checked: bool):
        """当启用/禁用红外渲染时，禁用或恢复 -n 的输入控件"""
        try:
            if checked:
                # 保存当前样本数并禁用
                try:
                    self._last_samples = int(self.samples_spin.value())
                except Exception:
                    self._last_samples = None
                try:
                    self.samples_spin.setValue(0)
                except Exception:
                    pass
                try:
                    self.samples_spin.setEnabled(False)
                except Exception:
                    pass
            else:
                # 恢复样本数并启用
                try:
                    self.samples_spin.setEnabled(True)
                except Exception:
                    pass
                if self._last_samples and self._last_samples > 0:
                    try:
                        self.samples_spin.setValue(self._last_samples)
                    except Exception:
                        pass
                else:
                    try:
                        self.samples_spin.setValue(1000000)
                    except Exception:
                        pass
        except Exception:
            pass
    
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
    
    def open_config_manager(self):
        """打开配置管理器"""
        from ConfigManagerDialog import ConfigManagerDialog
        
        dialog = ConfigManagerDialog(self.parent())
        dialog.config_loaded.connect(self.load_config_from_file)
        dialog.exec_()
    
    def quick_save_configuration(self):
        """快速保存当前配置到文件"""
        from PyQt5.QtWidgets import QInputDialog
        
        name, ok = QInputDialog.getText(self, "保存配置", "配置名称:")
        if not ok or not name:
            return
        
        desc, ok = QInputDialog.getText(self, "保存配置", "配置描述 (可选):")
        if not ok:
            return
        
        config = StardisConfigEnhanced()
        config.metadata.name = name
        config.metadata.description = desc
        config.from_panel(self)
        
        library = ConfigLibrary()
        filename = name.replace(' ', '_') + '.json'
        filepath = os.path.join(library.library_dir, filename)
        
        success, message = config.save_to_file(filepath)
        
        if success:
            library.add_recent(filepath)
            QMessageBox.information(self, "成功", f"配置已保存:\n{filepath}")
        else:
            QMessageBox.warning(self, "错误", message)
    
    def quick_load_configuration(self):
        """快速从文件加载配置"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "加载配置", "", 
            "JSON 文件 (*.json);;所有文件 (*.*)"
        )
        
        if file_path:
            self.load_config_from_file(file_path)
    
    def load_config_from_file(self, file_path):
        """从文件加载配置"""
        config = StardisConfigEnhanced()
        success, message = config.load_from_file(file_path)
        
        if success:
            success, message = config.to_panel(self)
            if success:
                library = ConfigLibrary()
                library.add_recent(file_path)
                self.log_output.append(f"[配置] 已加载: {file_path}")
                # 更新命令预览
                self.update_command_preview()
            else:
                self.log_output.append(f"[警告] 配置加载部分失败: {message}")
        else:
            QMessageBox.warning(self, "错误", message)
    
    def save_configuration(self):
        """保存当前配置到文件 (兼容旧方法)"""
        self.quick_save_configuration()
    
    def load_configuration(self):
        """从文件加载配置 (兼容旧方法)"""
        self.quick_load_configuration()

    # -------------------- 用户设置与最近目录管理 --------------------
    def _load_user_settings(self):
        """从磁盘加载用户设置并填充下拉列表"""
        try:
            if os.path.exists(self.user_settings_path):
                import json
                with open(self.user_settings_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.user_settings.update(data)

            # 不在启动时自动搜索可执行文件，搜索由用户手动触发
            # 填充 combobox
            exes = list(dict.fromkeys(self.user_settings.get('recent_exes', [])))
            works = list(dict.fromkeys(self.user_settings.get('recent_work_dirs', [])))

            self.exe_path_edit.clear()
            for e in exes:
                self.exe_path_edit.addItem(e)

            self.work_dir_edit.clear()
            for w in works:
                self.work_dir_edit.addItem(w)

            # 自动选择最近一次的目录
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
                self.stardis_exe_path = exes[0]

            # 保存合并后的设置
            self._save_user_settings()
        except Exception:
            pass

    def _on_search_exes_clicked(self):
        """用户点击搜索按钮时，在配置的搜索目录中查找 stardis.exe 并更新下拉列表"""
        try:
            found = self._search_exes_in_dirs()
            if not found:
                QMessageBox.information(self, "搜索结果", "未在配置的搜索目录中找到 stardis.exe。请检查 user_settings.json 中的 search_dirs。")
                return
            # prepend found entries to recent_exes
            for p in found:
                self._add_recent_exe(p)
            # 刷新 combobox 内容，保持去重顺序
            exes = list(dict.fromkeys(self.user_settings.get('recent_exes', [])))
            self.exe_path_edit.clear()
            for e in exes:
                self.exe_path_edit.addItem(e)
            try:
                self.exe_path_edit.setCurrentText(exes[0])
            except Exception:
                pass
            self._save_user_settings()
            QMessageBox.information(self, "搜索完成", f"找到 {len(found)} 个 stardis.exe，并已加入下拉列表。")
        except Exception as e:
            QMessageBox.warning(self, "搜索失败", str(e))

    def _save_user_settings(self):
        try:
            import json
            # Ensure lists
            self.user_settings['recent_exes'] = list(dict.fromkeys(self.user_settings.get('recent_exes', [])))
            self.user_settings['recent_work_dirs'] = list(dict.fromkeys(self.user_settings.get('recent_work_dirs', [])))
            with open(self.user_settings_path, 'w', encoding='utf-8') as f:
                json.dump(self.user_settings, f, indent=2, ensure_ascii=False)
        except Exception:
            pass

    def _add_recent_workdir(self, path):
        if not path:
            return
        lst = self.user_settings.setdefault('recent_work_dirs', [])
        if path in lst:
            lst.remove(path)
        lst.insert(0, path)
        # 限制长度
        self.user_settings['recent_work_dirs'] = lst[:20]

    def _add_recent_exe(self, path):
        if not path:
            return
        lst = self.user_settings.setdefault('recent_exes', [])
        if path in lst:
            lst.remove(path)
        lst.insert(0, path)
        self.user_settings['recent_exes'] = lst[:50]

    def _on_exe_changed(self, text):
        try:
            if text:
                self.stardis_exe_path = text
                self._add_recent_exe(text)
                self._save_user_settings()
        except Exception:
            pass

    def _on_workdir_changed(self, text):
        try:
            if text:
                self.working_directory = text
                # 仅当是有效目录时保存到最近
                if os.path.isdir(text):
                    self._add_recent_workdir(text)
                    self._save_user_settings()
        except Exception:
            pass

    def _search_exes_in_dirs(self):
        """在 user_settings.search_dirs 指定的目录下搜索 stardis.exe 文件"""
        results = []
        try:
            dirs = self.user_settings.get('search_dirs', []) or []
            for d in dirs:
                if not os.path.exists(d):
                    continue
                for root, _, files in os.walk(d):
                    for name in files:
                        if name.lower() == 'stardis.exe':
                            results.append(os.path.join(root, name))
        except Exception:
            pass
        return results


if __name__ == '__main__':
    import sys
    from PyQt5.QtWidgets import QApplication
    
    app = QApplication(sys.argv)
    panel = StardisControlPanel()
    panel.show()
    sys.exit(app.exec_())
