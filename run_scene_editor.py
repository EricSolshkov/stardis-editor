"""
Stardis 场景编辑器独立启动脚本
"""
import sys
import os

# 确保 src/ 在路径上
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from scene_editor import main

if __name__ == "__main__":
    main()
