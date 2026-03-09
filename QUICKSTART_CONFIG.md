# Stardis 配置管理快速开始

## 5分钟上手配置管理

### 步骤 1: 启动控制面板

```bash
cd src
python main.py
```

或直接启动控制面板：
```bash
cd src
python run_stardis_panel.py
```

### 步骤 2: 打开配置管理器

在控制面板中，点击"配置管理"区域的 **"配置管理器"** 按钮（蓝色大按钮）。

### 步骤 3: 尝试预设模板

1. 切换到 **"配置模板"** 标签页
2. 点击任意模板按钮，例如：
   - "Cube - 探针温度计算"
   - "Heatsink - 介质平均温度"
3. 配置自动加载到面板并保存到配置库
4. 关闭配置管理器

### 步骤 4: 修改配置

在控制面板中：
1. 修改 **"Stardis.exe 路径"** 为您的 stardis 可执行文件位置
2. 修改 **"工作目录"** 为您的项目目录
3. 修改 **"模型文件"** 为您的模型文件路径
4. 调整其他参数（样本数、线程数等）

### 步骤 5: 保存您的配置

1. 点击"配置管理"区域的 **"快速保存"** 按钮
2. 输入配置名称，例如："我的第一个配置"
3. 输入描述（可选），例如："测试散热器模型"
4. 点击确定

### 步骤 6: 加载已保存的配置

下次使用时：
1. 打开配置管理器
2. 在 **"配置库"** 或 **"最近使用"** 标签页中
3. 选择您的配置
4. 点击 **"加载到面板"** 按钮

## 从现有脚本创建配置

### 示例：转换 Shell 脚本

假设您有一个脚本 `my_analysis.sh`:

```bash
#!/bin/bash
SAMPLES=50000
THREADS=8
MODEL="heatsink_model.txt"

stardis -V 2 -M "${MODEL}" -m chip,INF -n "${SAMPLES}" -t "${THREADS}" -e
```

### 手动创建配置文件

创建文件 `config_library/my_heatsink_analysis.json`:

```json
{
    "metadata": {
        "name": "散热器芯片温度分析",
        "description": "计算散热器芯片的平均温度\n使用50000样本，8线程",
        "tags": ["heatsink", "chip", "temperature"],
        "source": "scripts/my_analysis.sh"
    },
    "config": {
        "executable": {
            "stardis_exe_path": "D:/stardis/stardis.exe",
            "working_directory": "D:/projects/heatsink"
        },
        "basic": {
            "model_file": "heatsink_model.txt",
            "samples": 50000,
            "threads": 8,
            "verbosity": 2
        },
        "compute_modes": {
            "medium_temp": {
                "enabled": true,
                "name": "chip"
            }
        },
        "advanced": {
            "extended_results": true
        },
        "output": {}
    }
}
```

### 加载您的配置

1. 打开配置管理器
2. 点击"刷新"按钮
3. 您的配置出现在列表中
4. 选择并加载

## 常用操作

### 复制配置创建变体

1. 打开配置管理器
2. 选择要复制的配置
3. 点击"复制配置"
4. 输入新名称，如："原配置_高分辨率"
5. 加载新配置并修改参数
6. 保存

### 编辑配置信息

1. 选择配置
2. 点击"编辑信息"
3. 修改名称或描述
4. 更新的信息立即保存

### 批量参数研究

创建多个配置，针对不同参数值：
- `analysis_1k_samples.json` (1,000 样本)
- `analysis_10k_samples.json` (10,000 样本)
- `analysis_100k_samples.json` (100,000 样本)

依次加载并运行，比较结果。

## 参数映射快速参考

| Shell 脚本 | 配置 JSON 路径 |
|-----------|----------------|
| `-M file` | `config.basic.model_file` |
| `-n 10000` | `config.basic.samples` |
| `-t 8` | `config.basic.threads` |
| `-V 2` | `config.basic.verbosity` |
| `-p x,y,z` | `config.compute_modes.probe_vol.{x,y,z}` |
| `-P x,y,z:side` | `config.compute_modes.probe_surf.*` |
| `-m medium` | `config.compute_modes.medium_temp.name` |
| `-s file` | `config.compute_modes.surf_mean_temp.file` |
| `-e` | `config.advanced.extended_results` |
| `-d file` | `config.output.dump_model.file` |

完整对照表见 [配置管理指南](CONFIG_MANAGEMENT_GUIDE.md#参数对照表)。

## 实用技巧

### 1. 使用有意义的名称
❌ 不好: `config1.json`, `test.json`
✅ 好: `heatsink_50k_samples.json`, `cube_probe_analysis.json`

### 2. 添加详细描述
在描述中包含：
- 配置用途
- 关键参数
- 预期运行时间
- 源脚本或参考

### 3. 使用标签分类
```json
"tags": ["project-alpha", "heatsink", "validated", "production"]
```

### 4. 记录源脚本
```json
"source": "Stardis-Starter-Pack/heatsink/run_medium_computation.sh"
```

### 5. 工作目录使用技巧
- 使用绝对路径确保一致性
- 或在配置描述中说明相对路径基准

## 故障排除

### 配置加载失败
**问题**: 点击"加载到面板"后没有反应或报错

**解决**:
1. 检查 JSON 格式是否正确（使用 JSON 验证器）
2. 确认文件包含 `metadata` 和 `config` 两个顶层键
3. 查看错误消息提示

### 配置列表为空
**问题**: 配置管理器中看不到任何配置

**解决**:
1. 确认 `config_library/` 目录存在
2. 检查目录内是否有 `.json` 文件
3. 点击"刷新"按钮
4. 尝试加载模板，会自动创建示例配置

### 路径问题
**问题**: 加载配置后，文件路径不正确

**解决**:
1. 使用绝对路径
2. 或在配置中使用相对路径，确保工作目录正确
3. 加载配置后手动调整路径

## 下一步

- 阅读完整文档：[配置管理指南](CONFIG_MANAGEMENT_GUIDE.md)
- 了解控制面板：[控制面板使用说明](STARDIS_CONTROL_PANEL_README.md)
- 查看示例配置：[example_stardis_config.json](example_stardis_config.json)

## 视频教程（待制作）

- [ ] 快速开始：配置管理器基本使用
- [ ] 进阶：从脚本创建配置
- [ ] 技巧：配置模板和批量运行

---

**遇到问题？** 请查看 [CONFIG_MANAGEMENT_GUIDE.md](CONFIG_MANAGEMENT_GUIDE.md) 中的故障排除章节。
