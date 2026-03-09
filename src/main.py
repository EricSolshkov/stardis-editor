
import sys
from PyQt5.QtWidgets import (QApplication, QMainWindow, QHBoxLayout, QVBoxLayout, 
                             QWidget, QPushButton, QFileDialog, QMenuBar, QAction)
from StlViewport import StlViewport, Inspector
from StardisControlPanel import StardisControlPanel

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('Stardis Editor - STL 查看器')
        self.resize(1200, 800)
        
        # 创建菜单栏
        self.create_menu_bar()
        
        # 中央部件
        central = QWidget()
        main_layout = QHBoxLayout(central)
        
        # 左侧: STL视图
        self.stl_viewport = StlViewport(self)
        main_layout.addWidget(self.stl_viewport, stretch=3)
        
        # 右侧: 控制区域
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        
        # Inspector
        self.inspector = Inspector(self)
        right_layout.addWidget(self.inspector)
        
        # 按钮区域
        btn_load = QPushButton('加载STL', self)
        btn_load.clicked.connect(self.open_stl)
        right_layout.addWidget(btn_load)

        btn_clear = QPushButton('清空模型', self)
        btn_clear.clicked.connect(self.clear_models)
        right_layout.addWidget(btn_clear)
        
        btn_stardis = QPushButton('打开 Stardis 控制面板', self)
        btn_stardis.clicked.connect(self.open_stardis_panel)
        btn_stardis.setStyleSheet("background-color: #2196F3; color: white; font-weight: bold; padding: 10px;")
        right_layout.addWidget(btn_stardis)
        
        right_layout.addStretch()
        
        main_layout.addWidget(right_panel, stretch=1)
        self.setCentralWidget(central)
        
        # Stardis控制面板（初始时不显示）
        self.stardis_panel = None
    
    def create_menu_bar(self):
        """创建菜单栏"""
        menubar = self.menuBar()
        
        # 文件菜单
        file_menu = menubar.addMenu('文件')
        
        open_stl_action = QAction('打开 STL...', self)
        open_stl_action.setShortcut('Ctrl+O')
        open_stl_action.triggered.connect(self.open_stl)
        file_menu.addAction(open_stl_action)
        
        clear_action = QAction('清空模型', self)
        clear_action.setShortcut('Ctrl+L')
        clear_action.triggered.connect(self.clear_models)
        file_menu.addAction(clear_action)
        
        file_menu.addSeparator()
        
        exit_action = QAction('退出', self)
        exit_action.setShortcut('Ctrl+Q')
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # Stardis菜单
        stardis_menu = menubar.addMenu('Stardis')
        
        open_panel_action = QAction('打开控制面板', self)
        open_panel_action.setShortcut('Ctrl+P')
        open_panel_action.triggered.connect(self.open_stardis_panel)
        stardis_menu.addAction(open_panel_action)

    def open_stl(self):
        """打开STL文件"""
        paths, _ = QFileDialog.getOpenFileNames(self, '选择STL文件', '', 'STL Files (*.stl)')
        for path in paths:
            if path:
                self.stl_viewport.load_stl(path)

    def clear_models(self):
        """清空所有模型"""
        self.stl_viewport.clear_models()
    
    def open_stardis_panel(self):
        """打开Stardis控制面板"""
        if self.stardis_panel is None:
            self.stardis_panel = StardisControlPanel()
        self.stardis_panel.show()
        self.stardis_panel.raise_()
        self.stardis_panel.activateWindow()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
