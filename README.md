# Stardis Editor - STL 查看器与 Stardis 控制面板

## 项目概述

Stardis Editor 是一个集成的工具集，提供 STL 3D 模型查看和 Stardis 热辐射计算软件的图形化控制界面。

## 项目结构

```
StardisEditor/
├── src/
│   ├── main.py                      # 主程序入口
│   ├── StlViewport.py               # STL 3D 视图组件
│   ├── StardisControlPanel.py       # Stardis 控制面板
│   ├── StardisConfigEnhanced.py     # 增强配置管理模块
│   ├── ConfigManagerDialog.py       # 配置管理器对话框
│   └── run_stardis_panel.py         # 控制面板独立启动脚本
├── config_library/                  # 配置库目录（自动创建）
├── example_stardis_config.json      # 示例配置文件
├── STARDIS_CONTROL_PANEL_README.md  # 控制面板详细文档
├── CONFIG_MANAGEMENT_GUIDE.md       # 配置管理指南
└── README.md                        # 本文件
```

## 主要功能

### 1. STL 3D 模型查看器
- 加载和显示多个 STL 文件
- 交互式 3D 视图（旋转、缩放、平移）
- 模型管理（清空、重新加载）

### 2. Stardis 控制面板
- 图形化配置所有 Stardis 命令行参数
- 可视化参数管理
- 实时命令预览
- 进程运行和日志监控
- 配置保存/加载（JSON 格式）

### 3. 配置管理系统 ⭐ 新功能
- **配置库**: 集中管理所有配置文件
- **配置模板**: 预设 Stardis Starter Pack 示例
- **最近使用**: 快速访问常用配置
- **元数据管理**: 为配置添加名称、描述、标签等
- **配置分享**: 轻松导出导入配置文件
- **脚本转换**: 从 Shell 脚本提取参数创建配置

## 快速开始

想要快速上手配置管理？查看 [配置管理快速开始指南](QUICKSTART_CONFIG.md)！

### 5分钟快速体验

1. 启动控制面板
2. 点击"配置管理器"按钮
3. 在"配置模板"标签页选择一个模板
4. 调整可执行文件路径
5. 开始运行！

详细步骤请参考 [快速开始指南](QUICKSTART_CONFIG.md)。

## 安装依赖

```bash
pip install PyQt5 vtk
```

### 依赖说明
- **PyQt5**: GUI 框架
- **vtk**: 3D 可视化库（用于 STL 查看）

## 使用方法

### 启动主程序

```bash
cd src
python main.py
```

主窗口包含：
- 左侧: STL 3D 视图区域
- 右侧: 控制面板
  - 加载 STL 按钮
  - 清空模型按钮
  - 打开 Stardis 控制面板按钮

### 独立启动 Stardis 控制面板

```bash
cd src
python run_stardis_panel.py
```

### 使用 Stardis 控制面板

1. **配置可执行文件**
   - 指定 `stardis.exe` 路径
   - 设置工作目录

2. **配置参数**
   - 在各个标签页中配置所需参数
   - 基本参数（必需）
   - 计算模式
   - 高级选项
   - 输出选项

3. **保存/加载配置**
   - 使用"配置管理"区域的按钮
   - 配置以 JSON 格式存储
   - 可重复使用之前的配置

4. **预览命令**
   - 点击"更新预览"查看完整命令行
   - 验证参数是否正确

5. **运行计算**
   - 点击"运行 Stardis"启动计算
   - 在日志区域查看实时输出
   - 需要时可点击"停止"终止进程

## 配置管理系统

### 配置管理器

点击控制面板的"配置管理器"按钮打开配置库管理界面。

#### 主要功能

**1. 配置库**
- 浏览所有已保存的配置
- 查看配置详细信息（名称、描述、标签、修改时间）
- 加载、编辑、复制、删除配置

**2. 最近使用**
- 自动记录最近加载的 10 个配置
- 快速访问常用配置
- 双击即可加载

**3. 配置模板**
预设的 Stardis Starter Pack 示例配置：
- **Cube - 探针温度计算**: 体积温度探针示例
- **Cube - 路径导出**: 热传输路径分析
- **Heatsink - 介质平均温度**: 散热器温度计算
- **Cube - Green 函数**: Green 函数计算

### 从脚本创建配置

如果您有现有的 Shell 脚本（如 Stardis-Starter-Pack 中的示例），可以手动提取参数创建配置：

**示例脚本**:
```bash
NREAL=10000
stardis -V 3 -M model.txt -p 0.5,0.5,0.5,100 -n ${NREAL}
```

**对应配置** (`config_library/my_config.json`):
```json
{
    "metadata": {
        "name": "我的配置",
        "description": "从脚本转换的配置",
        "tags": ["custom"],
        "source": "my_script.sh"
    },
    "config": {
        "basic": {
            "model_file": "model.txt",
            "samples": 10000,
            "verbosity": 3
        },
        "compute_modes": {
            "probe_vol": {
                "enabled": true,
                "x": 0.5,
                "y": 0.5,
                "z": 0.5,
                "t1": 100,
                "t2": 100
            }
        }
    }
}
```

详细的脚本转换指南请参考 [配置管理指南](CONFIG_MANAGEMENT_GUIDE.md)。

### 配置文件格式

配置文件采用 JSON 格式，包含两部分：
- **metadata**: 配置元数据（名称、描述、标签等）
- **config**: Stardis 参数配置

完整格式参考 [example_stardis_config.json](example_stardis_config.json)。

### 配置分享与协作

**导出配置**:
1. 配置文件位于 `config_library/` 目录
2. 直接复制相应的 JSON 文件

**导入配置**:
1. 将 JSON 文件复制到 `config_library/` 目录
2. 在配置管理器中点击"刷新"
3. 或使用"快速加载"直接加载任意位置的配置

## 详细文档

**入门指南**
- 🚀 [配置管理快速开始](QUICKSTART_CONFIG.md) - 5分钟上手
- 📘 [Stardis 控制面板详细使用说明](STARDIS_CONTROL_PANEL_README.md)

**配置管理**
- ⭐ [配置管理系统完整指南](CONFIG_MANAGEMENT_GUIDE.md) - 推荐阅读
- 📄 [示例配置文件](example_stardis_config.json)

**更新日志**
- 📋 [v1.1 更新详情](CHANGELOG_V1.1.md)

## Stardis 参数快速参考

### 必需参数
- **-M**: 模型文件路径

### 常用参数
- **-n**: Monte Carlo 样本数
- **-t**: 并行线程数
- **-V**: 日志详细度 (0-3)
- **-p**: 体积温度探针
- **-P**: 表面温度探针
- **-f**: 表面通量密度探针
- **-s**: 表面平均温度
- **-S**: 表面温度图
- **-F**: 表面通量
- **-R**: 红外图像渲染

### 高级参数
- **-a**: 扩散算法 (dsphere/wos)
- **-o**: Picard 迭代阶数
- **-I**: 初始时间
- **-i**: 禁用内部辐射
- **-e**: 扩展结果

### 输出参数
- **-d**: 导出模型
- **-c**: 导出 C chunks
- **-D**: 导出路径
- **-g**: Green 函数 ASCII
- **-G**: Green 函数二进制

完整参数说明请查看 [控制面板文档](STARDIS_CONTROL_PANEL_README.md)。

## 配置文件格式

配置文件使用 JSON 格式，示例：

```json
{
    "executable": {
        "stardis_exe_path": "D:/path/to/stardis.exe",
        "working_directory": "D:/working/dir"
    },
    "basic": {
        "model_file": "model.stl",
        "samples": 1000000,
        "threads": 8,
        "verbosity": 2
    },
    "compute_modes": {
        "probe_vol": {
            "enabled": true,
            "x": 0.0, "y": 0.0, "z": 1.5,
            "t1": 0.0, "t2": 100.0
        }
    }
}
```

完整配置示例见 [example_stardis_config.json](example_stardis_config.json)。

## 快捷键

### 主窗口
- **Ctrl+O**: 打开 STL 文件
- **Ctrl+L**: 清空模型
- **Ctrl+P**: 打开 Stardis 控制面板
- **Ctrl+Q**: 退出程序

### STL 视图交互
- **左键拖动**: 旋转视图
- **中键拖动**: 缩放视图
- **滚轮**: 缩放视图

## 常见问题

### Q: 如何指定 Stardis 可执行文件？
A: 在控制面板顶部"Stardis 可执行文件配置"区域，点击"浏览..."按钮选择 stardis.exe。

### Q: 工作目录有什么作用？
A: 工作目录是命令行运行的基准目录，所有相对路径都基于此目录。如果不设置，默认为当前程序所在目录。

### Q: 配置文件保存在哪里？
A: 配置文件可以保存到任意位置，推荐保存在项目目录或模型目录中便于管理。

### Q: 如何查看完整的命令行？
A: 在控制面板底部的"命令预览"区域点击"更新预览"按钮。

### Q: 运行出错怎么办？
A: 检查"运行日志"区域的错误信息，常见问题包括：
   - 可执行文件路径不正确
   - 模型文件不存在
   - 参数配置冲突
   - 权限问题

### Q: 能否同时运行多个计算？
A: 当前版本一次只支持运行一个 Stardis 进程。如需同时运行多个计算，请打开多个控制面板实例。

## 开发信息

### 技术栈
- **Python 3.x**
- **PyQt5**: GUI 框架
- **VTK**: 3D 可视化
- **JSON**: 配置文件格式

### 代码架构
- **main.py**: 主窗口，集成 STL 查看器和控制面板
- **StlViewport.py**: VTK 封装，提供 3D 视图组件
- **StardisControlPanel.py**: 控制面板 UI 和逻辑
- **StardisConfig.py**: 配置序列化/反序列化

### 扩展开发
如需添加新功能：
1. 在 `StardisControlPanel.py` 中添加 UI 组件
2. 在 `build_command()` 方法中添加命令行参数构建逻辑
3. 在 `StardisConfig.py` 中更新配置结构

## 更新日志

### v1.1 (2026-02-10) ⭐ 最新
- **配置管理系统增强**
  - 新增配置管理器对话框
  - 配置库集中管理
  - 配置元数据支持（名称、描述、标签）
  - 最近使用配置快速访问
  - Stardis Starter Pack 预设模板
  - 配置复制、编辑、删除功能
- **配置文件格式升级**
  - 支持元数据和配置分离
  - 向后兼容旧格式
- **文档完善**
  - 新增配置管理完整指南
  - 脚本转换参数对照表

### v1.0 (2026-02-10)
- 初始版本发布
- STL 3D 查看器
- Stardis 完整参数控制面板
- 配置保存/加载功能
- 实时日志监控

## 许可证

本项目遵循与 Stardis 相同的许可协议。

## 联系方式

如有问题或建议，请联系开发团队。

---

**项目主页**: https://github.com/yourusername/StardisEditor  
**Stardis 官方**: https://www.meso-star.com/
