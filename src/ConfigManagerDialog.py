"""
Stardis 配置管理对话框
提供配置库浏览、加载、保存、管理等功能
"""

from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
                             QListWidget, QListWidgetItem, QLabel, QLineEdit,
                             QTextEdit, QGroupBox, QMessageBox, QInputDialog,
                             QSplitter, QWidget, QFormLayout, QTabWidget)
from PyQt5.QtCore import Qt, pyqtSignal
from StardisConfigEnhanced import StardisConfigEnhanced, ConfigLibrary
import os


class ConfigManagerDialog(QDialog):
    """配置管理器对话框"""
    
    config_loaded = pyqtSignal(str)  # 配置文件路径
    
    def __init__(self, parent=None, library_dir="config_library"):
        super().__init__(parent)
        self.setWindowTitle("Stardis 配置管理器")
        self.resize(900, 600)
        
        self.library = ConfigLibrary(library_dir)
        self.current_config = None
        self.current_filepath = None
        
        self.init_ui()
        self.refresh_config_list()
    
    def init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)
        
        # 创建标签页
        tab_widget = QTabWidget()
        
        # 配置库标签页
        library_tab = QWidget()
        library_tab.setLayout(self.create_library_layout())
        tab_widget.addTab(library_tab, "配置库")
        
        # 最近使用标签页
        recent_tab = QWidget()
        recent_tab.setLayout(self.create_recent_layout())
        tab_widget.addTab(recent_tab, "最近使用")
        
        # 模板标签页
        template_tab = QWidget()
        template_tab.setLayout(self.create_template_layout())
        tab_widget.addTab(template_tab, "配置模板")
        
        layout.addWidget(tab_widget)
        
        # 底部按钮
        button_layout = QHBoxLayout()
        
        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(self.reject)
        button_layout.addStretch()
        button_layout.addWidget(close_btn)
        
        layout.addLayout(button_layout)
    
    def create_library_layout(self):
        """创建配置库布局"""
        layout = QVBoxLayout()
        
        # 主分割器
        splitter = QSplitter(Qt.Horizontal)
        
        # 左侧：配置列表
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        
        left_layout.addWidget(QLabel("配置列表:"))
        
        self.config_list = QListWidget()
        self.config_list.currentItemChanged.connect(self.on_config_selected)
        left_layout.addWidget(self.config_list)
        
        # 列表操作按钮
        list_btn_layout = QHBoxLayout()
        refresh_btn = QPushButton("刷新")
        refresh_btn.clicked.connect(self.refresh_config_list)
        list_btn_layout.addWidget(refresh_btn)
        
        new_btn = QPushButton("新建")
        new_btn.clicked.connect(self.new_config)
        list_btn_layout.addWidget(new_btn)
        
        left_layout.addLayout(list_btn_layout)
        
        splitter.addWidget(left_widget)
        
        # 右侧：配置详情和操作
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        
        # 配置信息区域
        info_group = QGroupBox("配置信息")
        info_layout = QFormLayout()
        
        self.config_name_label = QLabel("--")
        info_layout.addRow("名称:", self.config_name_label)
        
        self.config_desc_text = QTextEdit()
        self.config_desc_text.setMaximumHeight(100)
        self.config_desc_text.setReadOnly(True)
        info_layout.addRow("描述:", self.config_desc_text)
        
        self.config_time_label = QLabel("--")
        info_layout.addRow("修改时间:", self.config_time_label)
        
        self.config_tags_label = QLabel("--")
        info_layout.addRow("标签:", self.config_tags_label)
        
        info_group.setLayout(info_layout)
        right_layout.addWidget(info_group)
        
        # 操作按钮区域
        action_group = QGroupBox("操作")
        action_layout = QVBoxLayout()
        
        load_btn = QPushButton("加载到面板")
        load_btn.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold; padding: 8px;")
        load_btn.clicked.connect(self.load_config)
        action_layout.addWidget(load_btn)
        
        save_btn = QPushButton("从面板保存")
        save_btn.clicked.connect(self.save_from_panel)
        action_layout.addWidget(save_btn)
        
        duplicate_btn = QPushButton("复制配置")
        duplicate_btn.clicked.connect(self.duplicate_config)
        action_layout.addWidget(duplicate_btn)
        
        edit_info_btn = QPushButton("编辑信息")
        edit_info_btn.clicked.connect(self.edit_config_info)
        action_layout.addWidget(edit_info_btn)
        
        delete_btn = QPushButton("删除配置")
        delete_btn.setStyleSheet("background-color: #f44336; color: white;")
        delete_btn.clicked.connect(self.delete_config)
        action_layout.addWidget(delete_btn)
        
        action_layout.addStretch()
        action_group.setLayout(action_layout)
        right_layout.addWidget(action_group)
        
        splitter.addWidget(right_widget)
        splitter.setSizes([400, 500])
        
        layout.addWidget(splitter)
        return layout
    
    def create_recent_layout(self):
        """创建最近使用布局"""
        layout = QVBoxLayout()
        
        layout.addWidget(QLabel("最近使用的配置:"))
        
        self.recent_list = QListWidget()
        self.recent_list.itemDoubleClicked.connect(self.load_recent_config)
        layout.addWidget(self.recent_list)
        
        btn_layout = QHBoxLayout()
        refresh_recent_btn = QPushButton("刷新")
        refresh_recent_btn.clicked.connect(self.refresh_recent_list)
        btn_layout.addWidget(refresh_recent_btn)
        
        load_recent_btn = QPushButton("加载选中配置")
        load_recent_btn.clicked.connect(self.load_recent_config)
        btn_layout.addWidget(load_recent_btn)
        
        btn_layout.addStretch()
        layout.addLayout(btn_layout)
        
        self.refresh_recent_list()
        
        return layout
    
    def create_template_layout(self):
        """创建模板布局"""
        layout = QVBoxLayout()
        
        layout.addWidget(QLabel("预设配置模板:"))
        
        templates_group = QGroupBox("Stardis Starter Pack 示例")
        templates_layout = QVBoxLayout()
        
        # Cube 探针计算
        cube_probe_btn = QPushButton("Cube - 探针温度计算")
        cube_probe_btn.setToolTip("基于 Stardis-Starter-Pack/cube/run_probe_computation.sh")
        cube_probe_btn.clicked.connect(lambda: self.load_template("cube_probe"))
        templates_layout.addWidget(cube_probe_btn)
        
        # Cube 路径导出
        cube_path_btn = QPushButton("Cube - 路径导出")
        cube_path_btn.setToolTip("基于 Stardis-Starter-Pack/cube/run_dump_path.sh")
        cube_path_btn.clicked.connect(lambda: self.load_template("cube_path"))
        templates_layout.addWidget(cube_path_btn)
        
        # Heatsink 介质温度
        heatsink_btn = QPushButton("Heatsink - 介质平均温度")
        heatsink_btn.setToolTip("基于 Stardis-Starter-Pack/heatsink/run_medium_computation.sh")
        heatsink_btn.clicked.connect(lambda: self.load_template("heatsink_medium"))
        templates_layout.addWidget(heatsink_btn)
        
        # Green 函数
        green_btn = QPushButton("Cube - Green 函数计算")
        green_btn.setToolTip("基于 Stardis-Starter-Pack/cube/run_green_evaluation.sh")
        green_btn.clicked.connect(lambda: self.load_template("cube_green"))
        templates_layout.addWidget(green_btn)
        
        # City IR 渲染
        city_ir_btn = QPushButton("City - 红外图像渲染")
        city_ir_btn.setToolTip("基于 Stardis-Starter-Pack/city/run_IR_rendering.sh\n城市模型红外图像渲染，640x480，1024 SPP")
        city_ir_btn.clicked.connect(lambda: self.load_template("city_ir_render"))
        templates_layout.addWidget(city_ir_btn)
        
        # Porous IR 渲染
        porous_ir_btn = QPushButton("Porous - 红外图像渲染")
        porous_ir_btn.setToolTip("基于 Stardis-Starter-Pack/porous/run_IR_rendering.sh\n多孔介质红外图像渲染，320x320，32 SPP")
        porous_ir_btn.clicked.connect(lambda: self.load_template("porous_ir_render"))
        templates_layout.addWidget(porous_ir_btn)
        
        templates_layout.addStretch()
        templates_group.setLayout(templates_layout)
        layout.addWidget(templates_group)
        
        return layout
    
    def refresh_config_list(self):
        """刷新配置列表"""
        self.config_list.clear()
        configs = self.library.list_configs()
        
        for config in configs:
            item = QListWidgetItem(config["metadata"]["name"])
            item.setData(Qt.UserRole, config["filepath"])
            item.setToolTip(f"描述: {config['metadata'].get('description', '无')}\n"
                          f"修改时间: {config['metadata'].get('modified_time', '')}")
            self.config_list.addItem(item)
    
    def refresh_recent_list(self):
        """刷新最近使用列表"""
        self.recent_list.clear()
        recent = self.library.get_recent()
        
        for filepath in recent:
            try:
                config = StardisConfigEnhanced()
                success, _ = config.load_from_file(filepath)
                if success:
                    item = QListWidgetItem(config.metadata.name)
                    item.setData(Qt.UserRole, filepath)
                    item.setToolTip(filepath)
                    self.recent_list.addItem(item)
            except:
                pass
    
    def on_config_selected(self, current, previous):
        """配置选中事件"""
        if current is None:
            self.current_config = None
            self.current_filepath = None
            self.config_name_label.setText("--")
            self.config_desc_text.setText("")
            self.config_time_label.setText("--")
            self.config_tags_label.setText("--")
            return
        
        filepath = current.data(Qt.UserRole)
        config = StardisConfigEnhanced()
        success, msg = config.load_from_file(filepath)
        
        if success:
            self.current_config = config
            self.current_filepath = filepath
            
            # 更新显示
            self.config_name_label.setText(config.metadata.name)
            self.config_desc_text.setText(config.metadata.description)
            self.config_time_label.setText(config.metadata.modified_time)
            
            tags_text = ", ".join(config.metadata.tags) if config.metadata.tags else "无"
            self.config_tags_label.setText(tags_text)
        else:
            QMessageBox.warning(self, "错误", f"加载配置失败:\n{msg}")
    
    def load_config(self):
        """加载配置到面板"""
        if self.current_filepath:
            self.library.add_recent(self.current_filepath)
            self.config_loaded.emit(self.current_filepath)
            self.refresh_recent_list()
    
    def load_recent_config(self):
        """加载最近使用的配置"""
        item = self.recent_list.currentItem()
        if item:
            filepath = item.data(Qt.UserRole)
            self.library.add_recent(filepath)
            self.config_loaded.emit(filepath)
    
    def save_from_panel(self):
        """从面板保存配置"""
        name, ok = QInputDialog.getText(self, "保存配置", "配置名称:")
        if not ok or not name:
            return
        
        desc, ok = QInputDialog.getText(self, "保存配置", "配置描述 (可选):")
        if not ok:
            return
        
        # 需要父窗口提供当前面板状态
        if hasattr(self.parent(), 'stardis_panel') and self.parent().stardis_panel:
            panel = self.parent().stardis_panel
            config = StardisConfigEnhanced()
            config.metadata.name = name
            config.metadata.description = desc
            config.from_panel(panel)
            
            filename = name.replace(' ', '_') + '.json'
            filepath = os.path.join(self.library.library_dir, filename)
            
            success, msg = config.save_to_file(filepath)
            if success:
                self.library.add_recent(filepath)
                self.refresh_config_list()
                self.refresh_recent_list()
                QMessageBox.information(self, "成功", f"配置已保存:\n{filepath}")
            else:
                QMessageBox.warning(self, "错误", msg)
        else:
            QMessageBox.warning(self, "错误", "无法访问控制面板")
    
    def duplicate_config(self):
        """复制配置"""
        if not self.current_filepath:
            QMessageBox.warning(self, "提示", "请先选择一个配置")
            return
        
        new_name, ok = QInputDialog.getText(self, "复制配置", "新配置名称:",
                                           text=self.current_config.metadata.name + "_副本")
        if ok and new_name:
            success, result = self.library.duplicate_config(self.current_filepath, new_name)
            if success:
                self.refresh_config_list()
                QMessageBox.information(self, "成功", f"配置已复制:\n{result}")
            else:
                QMessageBox.warning(self, "错误", result)
    
    def edit_config_info(self):
        """编辑配置信息"""
        if not self.current_config or not self.current_filepath:
            QMessageBox.warning(self, "提示", "请先选择一个配置")
            return
        
        # 编辑名称
        name, ok = QInputDialog.getText(self, "编辑配置", "配置名称:",
                                       text=self.current_config.metadata.name)
        if not ok:
            return
        
        # 编辑描述
        desc, ok = QInputDialog.getMultiLineText(self, "编辑配置", "配置描述:",
                                                text=self.current_config.metadata.description)
        if not ok:
            return
        
        self.current_config.metadata.name = name
        self.current_config.metadata.description = desc
        
        success, msg = self.current_config.save_to_file(self.current_filepath)
        if success:
            self.refresh_config_list()
            self.on_config_selected(self.config_list.currentItem(), None)
            QMessageBox.information(self, "成功", "配置信息已更新")
        else:
            QMessageBox.warning(self, "错误", msg)
    
    def delete_config(self):
        """删除配置"""
        if not self.current_filepath:
            QMessageBox.warning(self, "提示", "请先选择一个配置")
            return
        
        reply = QMessageBox.question(self, "确认删除",
                                    f"确定要删除配置 '{self.current_config.metadata.name}' 吗？\n"
                                    f"此操作不可恢复！",
                                    QMessageBox.Yes | QMessageBox.No)
        
        if reply == QMessageBox.Yes:
            success, msg = self.library.delete_config(self.current_filepath)
            if success:
                self.refresh_config_list()
                QMessageBox.information(self, "成功", "配置已删除")
            else:
                QMessageBox.warning(self, "错误", msg)
    
    def new_config(self):
        """新建配置"""
        self.save_from_panel()
    
    def load_template(self, template_name):
        """加载模板"""
        templates = self.get_templates()
        if template_name in templates:
            config = templates[template_name]
            
            # 保存为临时配置
            temp_name = f"模板_{template_name}"
            filename = temp_name.replace(' ', '_') + '.json'
            filepath = os.path.join(self.library.library_dir, filename)
            
            enhanced_config = StardisConfigEnhanced()
            enhanced_config.metadata.name = config["metadata"]["name"]
            enhanced_config.metadata.description = config["metadata"]["description"]
            enhanced_config.metadata.tags = config["metadata"]["tags"]
            enhanced_config.config = config["config"]
            
            success, msg = enhanced_config.save_to_file(filepath)
            if success:
                self.library.add_recent(filepath)
                self.config_loaded.emit(filepath)
                self.refresh_config_list()
                self.refresh_recent_list()
                QMessageBox.information(self, "成功", f"模板已加载并保存:\n{filepath}")
            else:
                QMessageBox.warning(self, "错误", msg)
        else:
            QMessageBox.warning(self, "错误", f"未找到模板: {template_name}")
    
    def get_templates(self):
        """获取预设模板"""
        return {
            "cube_probe": {
                "metadata": {
                    "name": "Cube - 探针温度计算",
                    "description": "在立方体中心位置计算不同时间点的温度\n基于 Stardis-Starter-Pack/cube/run_probe_computation.sh",
                    "tags": ["starter-pack", "probe", "temperature"]
                },
                "config": {
                    "executable": {
                        "stardis_exe_path": "",
                        "working_directory": ""
                    },
                    "basic": {
                        "model_file": "model.txt",
                        "samples": 10000,
                        "threads": 4,
                        "verbosity": 3
                    },
                    "compute_modes": {
                        "probe_vol": {
                            "enabled": True,
                            "x": 0.5,
                            "y": 0.5,
                            "z": 0.5,
                            "t1": 10,
                            "t2": 400
                        }
                    },
                    "advanced": {},
                    "output": {}
                }
            },
            "cube_path": {
                "metadata": {
                    "name": "Cube - 路径导出",
                    "description": "导出热传输路径用于分析\n基于 Stardis-Starter-Pack/cube/run_dump_path.sh",
                    "tags": ["starter-pack", "path", "dump"]
                },
                "config": {
                    "executable": {
                        "stardis_exe_path": "",
                        "working_directory": ""
                    },
                    "basic": {
                        "model_file": "model.txt",
                        "samples": 100,
                        "threads": 1,
                        "verbosity": 3
                    },
                    "compute_modes": {
                        "probe_vol": {
                            "enabled": True,
                            "x": 0.5,
                            "y": 0.5,
                            "z": 0.5,
                            "t1": 0,
                            "t2": 0
                        }
                    },
                    "advanced": {},
                    "output": {
                        "dump_paths": {
                            "enabled": True,
                            "type": 0,  # all
                            "file": "paths.txt"
                        }
                    }
                }
            },
            "heatsink_medium": {
                "metadata": {
                    "name": "Heatsink - 介质平均温度",
                    "description": "计算散热器中芯片介质的平均温度\n基于 Stardis-Starter-Pack/heatsink/run_medium_computation.sh",
                    "tags": ["starter-pack", "medium", "temperature", "heatsink"]
                },
                "config": {
                    "executable": {
                        "stardis_exe_path": "",
                        "working_directory": ""
                    },
                    "basic": {
                        "model_file": "model.txt",
                        "samples": 1000,
                        "threads": 4,
                        "verbosity": 3
                    },
                    "compute_modes": {
                        "medium_temp": {
                            "enabled": True,
                            "name": "SIPw"
                        }
                    },
                    "advanced": {
                        "extended_results": True
                    },
                    "output": {
                        "dump_model": {
                            "enabled": True,
                            "file": "chip.vtk"
                        }
                    }
                }
            },
            "cube_green": {
                "metadata": {
                    "name": "Cube - Green 函数",
                    "description": "计算Green函数用于快速评估\n基于 Stardis-Starter-Pack/cube/run_green_evaluation.sh",
                    "tags": ["starter-pack", "green", "function"]
                },
                "config": {
                    "executable": {
                        "stardis_exe_path": "",
                        "working_directory": ""
                    },
                    "basic": {
                        "model_file": "model.txt",
                        "samples": 10000,
                        "threads": 4,
                        "verbosity": 3
                    },
                    "compute_modes": {
                        "probe_vol": {
                            "enabled": True,
                            "x": 0.5,
                            "y": 0.5,
                            "z": 0.5,
                            "t1": 0,
                            "t2": 0
                        }
                    },
                    "advanced": {
                        "picard_order": 1
                    },
                    "output": {
                        "green_bin": {
                            "enabled": True,
                            "file": "green.bin",
                            "end_paths": ""
                        }
                    }
                }
            },
            "city_ir_render": {
                "metadata": {
                    "name": "City - 红外图像渲染",
                    "description": "城市模型红外图像渲染\n基于 Stardis-Starter-Pack/city/run_IR_rendering.sh\n分辨率: 640x480, SPP: 1024\n相机位置: (0,-150,30), 目标: (50,30,0)",
                    "tags": ["starter-pack", "IR", "render", "city", "imaging"]
                },
                "config": {
                    "executable": {
                        "stardis_exe_path": "",
                        "working_directory": ""
                    },
                    "basic": {
                        "model_file": "model.txt",
                        "samples": 0,
                        "threads": 4,
                        "verbosity": 3
                    },
                    "compute_modes": {
                        "ir_image": {
                                    "enabled": True,
                                    "camera": {
                                        "spp": 1024,
                                        "img": {"w": 640, "h": 480},
                                        "fov": 30,
                                        "pos": [0, -150, 30],
                                        "tgt": [50, 30, 0],
                                        "up": [0, 0, 1]
                                    }
                                }
                    },
                    "advanced": {},
                    "output": {}
                }
            },
            "porous_ir_render": {
                "metadata": {
                    "name": "Porous - 红外图像渲染",
                    "description": "多孔介质红外图像渲染\n基于 Stardis-Starter-Pack/porous/run_IR_rendering.sh\n分辨率: 320x320, SPP: 32\n相机位置: (0.05,0.01,0), 目标: (0,0,0)",
                    "tags": ["starter-pack", "IR", "render", "porous", "imaging"]
                },
                "config": {
                    "executable": {
                        "stardis_exe_path": "",
                        "working_directory": ""
                    },
                    "basic": {
                        "model_file": "porous.txt",
                        "samples": 0,
                        "threads": 4,
                        "verbosity": 3
                    },
                    "compute_modes": {
                        "ir_image": {
                                    "enabled": True,
                                    "camera": {
                                        "spp": 32,
                                        "img": {"w": 320, "h": 320},
                                        "fov": 30,
                                        "pos": [0.05, 0.01, 0],
                                        "tgt": [0, 0, 0],
                                        "up": [0, 0, 1]
                                    }
                                }
                    },
                    "advanced": {},
                    "output": {}
                }
            }
        }
