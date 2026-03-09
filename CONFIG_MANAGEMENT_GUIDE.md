# Stardis 配置管理指南

## 概述

Stardis 配置管理系统提供了一个完整的配置库来管理您的 Stardis 计算参数。您可以从现有的 Shell 脚本中提取参数，创建可重用的配置，并轻松地在不同项目间切换配置。

## 配置文件格式

配置文件采用 JSON 格式，包含两个主要部分：

### 1. 元数据 (metadata)
```json
{
    "metadata": {
        "name": "配置名称",
        "description": "配置描述（可多行）",
        "tags": ["标签1", "标签2"],
        "created_time": "创建时间（ISO格式）",
        "modified_time": "修改时间（ISO格式）",
        "author": "作者",
        "source": "源脚本路径"
    }
}
```

### 2. 配置数据 (config)
包含所有 Stardis 参数，详见 [example_stardis_config.json](example_stardis_config.json)。

## 从 Shell 脚本提取配置

### 步骤 1: 识别脚本中的参数

以 `Stardis-Starter-Pack/cube/run_probe_computation.sh` 为例：

```bash
### USER PARAMETERS SECTION
NREAL=10000
TIME="10 50 100 200 300 400"
FILE="stardis_result_N${NREAL}.txt"
### END USER PARAMETERS SECTION

# 实际命令
stardis -V 3 -M model.txt -p 0.5,0.5,0.5,"${i}" -n "${NREAL}"
```

### 步骤 2: 映射参数到 JSON 配置

创建对应的 JSON 配置：

```json
{
    "metadata": {
        "name": "Cube - 探针温度计算",
        "description": "在立方体中心位置计算不同时间点的温度",
        "tags": ["cube", "probe", "temperature"],
        "source": "Stardis-Starter-Pack/cube/run_probe_computation.sh"
    },
    "config": {
        "executable": {
            "stardis_exe_path": "path/to/stardis.exe",
            "working_directory": "path/to/cube"
        },
        "basic": {
            "model_file": "model.txt",
            "samples": 10000,          // NREAL
            "threads": 4,
            "verbosity": 3             // -V 3
        },
        "compute_modes": {
            "probe_vol": {
                "enabled": true,
                "x": 0.5,              // -p 0.5,0.5,0.5
                "y": 0.5,
                "z": 0.5,
                "t1": 10,              // TIME 第一个值
                "t2": 400              // TIME 最后一个值
            }
        }
    }
}
```

### 参数对照表

| Shell 脚本参数 | JSON 配置路径 | 说明 |
|---------------|--------------|------|
| `-M model.txt` | `config.basic.model_file` | 模型文件 |
| `-n ${NREAL}` | `config.basic.samples` | 样本数 |
| `-V 3` | `config.basic.verbosity` | 详细度 (0-3) |
| `-t 8` | `config.basic.threads` | 线程数 |
| `-p x,y,z` | `config.compute_modes.probe_vol.{x,y,z}` | 体积探针位置 |
| `-p x,y,z,t` | `...probe_vol.{x,y,z,t1}` | 单一时间 |
| `-p x,y,z,t1,t2` | `...probe_vol.{x,y,z,t1,t2}` | 时间范围 |
| `-P x,y,z:side` | `config.compute_modes.probe_surf.*` | 表面探针 |
| `-f x,y,z` | `config.compute_modes.flux_surf.*` | 通量探针 |
| `-m medium` | `config.compute_modes.medium_temp.name` | 介质名称 |
| `-s file` | `config.compute_modes.surf_mean_temp.file` | 表面文件 |
| `-S file` | `config.compute_modes.surf_temp_map.file` | 温度图 |
| `-F file` | `config.compute_modes.surf_flux.file` | 通量文件 |
| `-R camera` | `config.compute_modes.ir_image.camera` | 相机配置 |
| `-a algo` | `config.advanced.diff_algo` | 扩散算法 (0=无, 1=dsphere, 2=wos) |
| `-o order` | `config.advanced.picard_order` | Picard 阶数 |
| `-I time` | `config.advanced.initial_time` | 初始时间 |
| `-i` | `config.advanced.disable_intrad` | 禁用内辐射 (true/false) |
| `-e` | `config.advanced.extended_results` | 扩展结果 |
| `-d file` | `config.output.dump_model.file` | 导出模型 |
| `-D type,file` | `config.output.dump_paths.*` | 导出路径 |
| `-g` | `config.output.green_ascii.enabled` | Green ASCII |
| `-G file` | `config.output.green_bin.file` | Green 二进制 |

## 使用配置管理器

### 打开配置管理器

1. 启动 Stardis 控制面板
2. 点击"配置管理"区域的"配置管理器"按钮
3. 或使用快捷键（如果已配置）

### 配置管理器功能

#### 1. 配置库标签页

**浏览配置**
- 左侧列表显示所有已保存的配置
- 点击配置查看详细信息
- 双击配置快速加载

**配置操作**
- **加载到面板**: 将选中配置应用到控制面板
- **从面板保存**: 将当前面板参数保存为新配置
- **复制配置**: 创建配置副本
- **编辑信息**: 修改配置名称、描述等元数据
- **删除配置**: 永久删除配置（谨慎操作）

#### 2. 最近使用标签页

- 显示最近加载的 10 个配置
- 快速访问常用配置
- 双击即可加载

#### 3. 配置模板标签页

预设的 Stardis Starter Pack 示例配置：

- **Cube - 探针温度计算**: 基本温度探针示例
- **Cube - 路径导出**: 热传输路径分析
- **Heatsink - 介质平均温度**: 散热器温度分析
- **Cube - Green 函数**: Green 函数计算

点击任意模板按钮即可加载到面板并自动保存到配置库。

## 配置库管理

### 配置库位置

默认配置库位置：`config_library/`

所有配置文件存储在此目录下，以 `.json` 格式保存。

### 配置文件命名

- 文件名根据配置名称自动生成
- 空格替换为下划线
- 添加 `.json` 扩展名
- 例如："Cube 探针计算" → `Cube_探针计算.json`

### 手动添加配置

1. 在配置库目录创建新的 JSON 文件
2. 按照配置文件格式编写
3. 在配置管理器中点击"刷新"

### 导入导出配置

**导出配置**
1. 在配置管理器中选择配置
2. 配置文件位于 `config_library/` 目录
3. 直接复制 JSON 文件到其他位置

**导入配置**
1. 将 JSON 配置文件复制到 `config_library/` 目录
2. 在配置管理器中点击"刷新"
3. 或使用"快速加载"直接加载任意位置的配置

### 配置共享

要与团队成员共享配置：

1. 在配置管理器中确认配置已保存
2. 复制 `config_library/` 目录下的对应 JSON 文件
3. 发送给团队成员
4. 团队成员将文件放入其 `config_library/` 目录
5. 刷新配置列表即可使用

## 实战示例

### 示例 1: 从 Starter Pack 脚本创建配置

假设您有一个自定义脚本：

```bash
#!/bin/bash
# 我的散热器分析脚本
SAMPLES=50000
THREADS=16
MODEL="my_heatsink_model.txt"

stardis -V 2 -M "${MODEL}" -m heatsink_body,INF -n "${SAMPLES}" -t "${THREADS}" -e
```

创建对应配置 `my_heatsink_config.json`:

```json
{
    "metadata": {
        "name": "我的散热器分析",
        "description": "自定义散热器介质温度分析\n使用50000样本，16线程",
        "tags": ["heatsink", "custom", "medium-temp"],
        "source": "scripts/my_heatsink_analysis.sh"
    },
    "config": {
        "executable": {
            "stardis_exe_path": "D:/stardis/stardis.exe",
            "working_directory": "D:/projects/heatsink"
        },
        "basic": {
            "model_file": "my_heatsink_model.txt",
            "samples": 50000,
            "threads": 16,
            "verbosity": 2
        },
        "compute_modes": {
            "medium_temp": {
                "enabled": true,
                "name": "heatsink_body"
            }
        },
        "advanced": {
            "extended_results": true
        }
    }
}
```

将此文件保存到 `config_library/` 目录，即可在配置管理器中使用。

### 示例 2: 批量计算不同参数

创建多个配置文件用于参数研究：

**配置 1**: `cube_samples_1k.json` (1000 样本)
```json
{
    "metadata": {
        "name": "Cube 1K 样本",
        "tags": ["cube", "param-study", "1k"]
    },
    "config": {
        "basic": {
            "samples": 1000,
            ...
        }
    }
}
```

**配置 2**: `cube_samples_10k.json` (10000 样本)
```json
{
    "metadata": {
        "name": "Cube 10K 样本",
        "tags": ["cube", "param-study", "10k"]
    },
    "config": {
        "basic": {
            "samples": 10000,
            ...
        }
    }
}
```

然后在配置管理器中依次加载和运行。

### 示例 3: 复用配置基础模板

1. 加载一个基础配置（如模板）
2. 在面板中修改特定参数（如模型文件路径）
3. 使用"快速保存"保存为新配置
4. 为新配置添加描述性名称

## 最佳实践

### 1. 配置命名规范

建议使用清晰的命名：
- 包含项目名称：`ProjectX_heatsink_analysis`
- 包含关键参数：`cube_1M_samples_16threads`
- 包含日期版本：`thermal_model_v2_2026-02`

### 2. 使用标签分类

有效的标签示例：
- 项目标签：`project-alpha`, `heatsink-study`
- 参数标签：`high-resolution`, `quick-test`
- 状态标签：`validated`, `draft`, `production`

### 3. 填写详细描述

描述应包含：
- 配置用途
- 关键参数说明
- 预期结果
- 运行时间估计
- 源脚本或参考文档

### 4. 配置版本管理

对于重要配置：
- 使用版本号：`heatsink_analysis_v1.0`
- 记录修改历史在描述中
- 保留旧版本作为备份

### 5. 团队协作

配置库的组织建议：
```
config_library/
├── templates/          # 通用模板
├── projects/          # 按项目分类
│   ├── project_x/
│   └── project_y/
└── validated/         # 已验证的配置
```

## 高级技巧

### 批量配置生成

使用 Python 脚本批量生成配置：

```python
import json
from datetime import datetime

base_config = {...}  # 基础配置

for samples in [1000, 10000, 100000]:
    config = base_config.copy()
    config["metadata"]["name"] = f"Cube {samples} samples"
    config["config"]["basic"]["samples"] = samples
    
    filename = f"config_library/cube_{samples}_samples.json"
    with open(filename, 'w') as f:
        json.dump(config, f, indent=4)
```

### 配置验证

添加验证脚本检查配置完整性：
- 必需字段检查
- 路径存在性验证
- 参数合理性检查

### 配置迁移

在不同机器间迁移配置时：
- 使用相对路径（相对于工作目录）
- 或在导入时批量替换路径前缀

## 故障排除

### 问题：配置加载失败

**原因**: JSON 格式错误

**解决**:
1. 使用 JSON 验证器检查格式
2. 确认所有引号、括号匹配
3. 查看错误消息定位问题行

### 问题：配置列表不显示新文件

**原因**: 文件命名或位置问题

**解决**:
1. 确认文件在 `config_library/` 目录
2. 文件扩展名必须是 `.json`
3. 不要以 `.` 开头（系统文件）
4. 点击"刷新"按钮

### 问题：配置应用后参数不正确

**原因**: 配置格式版本不匹配

**解决**:
1. 检查配置文件是否包含 `metadata` 和 `config` 两个顶层键
2. 旧格式配置会自动兼容，但建议更新为新格式
3. 使用示例配置作为参考

## 相关资源

- [Stardis 控制面板使用说明](STARDIS_CONTROL_PANEL_README.md)
- [示例配置文件](example_stardis_config.json)
- [Stardis 官方文档](https://www.meso-star.com/)

---

更新时间: 2026-02-10
