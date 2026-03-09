"""
htpp 控制面板独立启动脚本
可以独立运行控制面板，无需启动主窗口
"""

import sys
from PyQt5.QtWidgets import QApplication
from HtppControlPanel import HtppControlPanel


def main():
    """主函数"""
    app = QApplication(sys.argv)
    app.setApplicationName("htpp Control Panel")
    
    # 创建并显示控制面板
    panel = HtppControlPanel()
    panel.show()
    
    # 运行应用
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
