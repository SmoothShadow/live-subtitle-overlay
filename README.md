# Live Subtitle Overlay

一个仅面向 Windows 的桌面实时字幕叠加层 MVP，用来在观看外语视频时，把中文字幕以透明悬浮窗的形式显示在桌面最上层。

## 项目目标

- 使用 `WASAPI loopback` 捕获系统播放音频
- 使用本地 `faster-whisper` 做语音识别
- 使用 `Azure AI Translator` 做翻译
- 使用透明、置顶的桌面窗口显示字幕，而不是注入浏览器页面

## 当前功能

当前仓库已经不是空骨架，已具备以下能力：

- 透明置顶字幕窗口
- Azure 翻译接入
- Windows 下真实可用的 `PyAudioWPatch` 回环采集
- `faster-whisper` 识别适配
- 回环设备列出、选择与保存
- 静音过滤与可选 `webrtcvad`
- 短间隔分段合并
- 基础字幕去重与修正抑制
- 叠加层快捷键与基础控制
- 本地设置持久化
- `--demo` 演示模式
- 启动诊断与启动失败可视化提示

目前仍然需要在真实 Windows 机器上继续调优音频分块、VAD、缓冲、字幕平滑和整体延迟。

## 目录结构

- `audio.py`：Windows 回环采集
- `asr.py`：本地语音识别适配
- `translation.py`：Azure Translator 客户端
- `pipeline.py`：后台字幕流水线
- `ui.py`：透明字幕窗口
- `settings.py`：本地设置持久化

## 推荐环境

- Windows 10 / 11
- Python `3.11` 到 `3.13`

说明：

- `PyAudioWPatch` 官方 Windows wheel 支持 Python 3.7 到 3.13
- 如果你打算用 GPU 跑 Whisper，需要机器上的 NVIDIA 驱动和对应运行环境正常

## 安装

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e .[dev]
Copy-Item .env.example .env
```

然后在 `.env` 中填写 Azure Translator 配置，至少要替换：

- `AZURE_TRANSLATOR_KEY`

如果你是东亚资源、日文转简体中文，下面这些值是合理的：

```dotenv
AZURE_TRANSLATOR_REGION=eastasia
AZURE_TRANSLATOR_ENDPOINT=https://api.cognitive.microsofttranslator.com
SOURCE_LANGUAGE=ja
TARGET_LANGUAGE=zh-Hans
```

## 运行

UI 演示模式：

```powershell
live-subtitle-overlay --demo
```

真实字幕流水线：

```powershell
live-subtitle-overlay
```

常用命令：

```powershell
live-subtitle-overlay --demo --show-source
live-subtitle-overlay --config-check
live-subtitle-overlay --diagnostics
live-subtitle-overlay --list-devices
live-subtitle-overlay --choose-device
live-subtitle-overlay --device-index 6
live-subtitle-overlay --settings C:\path\to\settings.json
```

Windows 一键首次联调脚本：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\windows-first-run.ps1
```

## 首次在 Windows 真机联调

第一次在目标 Windows 机器上跑真实链路时，建议按这个顺序：

1. 先跑诊断：

```powershell
live-subtitle-overlay --diagnostics
```

2. 选择回环设备：

```powershell
live-subtitle-overlay --choose-device
```

3. 启动程序：

```powershell
live-subtitle-overlay
```

完整步骤见 [docs/WINDOWS_FIRST_RUN.md](/Users/SmoothShadow/vibeCoding/live-subtitle-overlay/docs/WINDOWS_FIRST_RUN.md:1)。

## 主要参数说明

### Azure 相关

- `AZURE_TRANSLATOR_KEY`
- `AZURE_TRANSLATOR_REGION`
- `AZURE_TRANSLATOR_ENDPOINT`
- `TARGET_LANGUAGE`
- `SOURCE_LANGUAGE`

### Whisper 相关

- `WHISPER_MODEL`
- `WHISPER_DEVICE`
- `WHISPER_COMPUTE_TYPE`

如果 GPU 侧初始化不稳定，可以先临时切到 CPU：

```dotenv
WHISPER_DEVICE=cpu
WHISPER_COMPUTE_TYPE=int8
```

### 音频相关

- `CHUNK_SECONDS`
- `FRAMES_PER_BUFFER`
- `WASAPI_LOOPBACK_DEVICE_INDEX`
- `ENABLE_VAD`
- `VAD_AGGRESSIVENESS`
- `SILENCE_RMS_THRESHOLD`

### UI 相关

- `OVERLAY_FONT_SIZE`
- `OVERLAY_OPACITY`
- `OVERLAY_WIDTH`
- `OVERLAY_HEIGHT`
- `SUBTITLE_TIMEOUT_SECONDS`
- `SHOW_SOURCE_TEXT`

## 快捷键与控制

- `Ctrl+Shift+S`：暂停或恢复监听
- `Ctrl+Shift+L`：锁定或解锁窗口拖动
- `Ctrl+Shift+T`：显示或隐藏原文行
- `Ctrl+Shift+H`：Windows 下全局显示或隐藏叠加层

此外，窗口内也提供了：

- `Pause / Resume` 按钮
- `Source` 按钮
- `Lock` 按钮

## 使用说明与注意事项

- 视频播放器建议使用窗口模式或无边框全屏。独占全屏可能会挡住叠加层。
- 如果 Azure 没有正确配置，程序会退化为只显示原文识别结果。
- 如果系统默认输出设备在运行期间发生变化，建议重启程序。
- 如果默认输出设备不是你想要的，可以使用 `--choose-device`，或者先 `--list-devices` 再配合 `--device-index N`。
- 窗口位置、锁定状态、原文显示状态，以及最近一次选择的回环设备索引都会保存在本地设置中。
- 如果启动校验失败，窗口会保留错误信息，不再直接静默退出。

## 常见问题

### 1. `--diagnostics` 提示 `PyAudioWPatch is not available`

通常说明你当前不是 Windows 环境，或者依赖没有安装完整。先确认在 Windows 下使用项目虚拟环境重新执行：

```powershell
pip install -e .[dev]
```

### 2. `--diagnostics` 提示 Whisper 初始化失败

先尝试把 `.env` 改为 CPU 模式：

```dotenv
WHISPER_DEVICE=cpu
WHISPER_COMPUTE_TYPE=int8
```

再重新执行：

```powershell
live-subtitle-overlay --diagnostics
```

### 3. 程序启动了，但只显示原文

优先检查：

- `AZURE_TRANSLATOR_KEY` 是否已替换成真实 key
- `AZURE_TRANSLATOR_REGION` 是否与你的 Azure 资源一致
- `AZURE_TRANSLATOR_ENDPOINT` 是否可用

### 4. 播放视频时没有字幕

优先检查：

- 选中的回环设备是否就是当前播放器实际输出的设备
- 是否误开了过强的静音阈值或 VAD

可以先尝试：

```dotenv
ENABLE_VAD=false
SILENCE_RMS_THRESHOLD=0.006
```

## 当前状态说明

这个项目当前已经能支撑首次 Windows 真机联调，但以下事项仍未在当前环境中完成：

- Windows 真机音频采集验证
- CUDA 推理实测
- Azure 真实凭据联调
- 真实视频内容下的延迟与可读性调优
