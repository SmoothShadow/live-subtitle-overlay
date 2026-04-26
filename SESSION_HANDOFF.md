# Session Handoff

Last updated: 2026-04-26

## 项目目标

做一个仅面向 Windows 的桌面实时字幕叠加层，用于观看外语视频时，在桌面最上层显示中文字幕。

目标链路：

1. 用 `WASAPI loopback` 抓系统播放音频
2. 用本地 `faster-whisper` 做 ASR
3. 用 `Azure AI Translator` 翻译成简体中文
4. 用透明、置顶的桌面窗口显示字幕

项目方向已经明确为独立 Windows 桌面叠加层，不再走浏览器注入路线。

## 当前状态

代码层面的 MVP 已基本成型，已经不是骨架状态。当前已经具备完整的主流程、基础交互、启动诊断和 Windows 首次联调辅助能力。

已实现：

- 可运行入口与项目基础打包结构
- 基于 `.env` 的配置加载
- `PyAudioWPatch` 的 Windows WASAPI 回环采集
- `faster-whisper` 本地识别适配
- Azure Translator HTTP 客户端
- 字幕流水线：
  - 静音过滤
  - 可选 `webrtcvad`
  - 短间隔分段合并
  - 重复/修正抑制
- `PySide6` 透明置顶字幕窗口
- 状态栏与启动错误可视化提示
- 叠加层快捷键：
  - `Ctrl+Shift+S` 暂停/恢复监听
  - `Ctrl+Shift+L` 锁定/解锁窗口拖动
  - `Ctrl+Shift+T` 显示/隐藏原文
  - `Ctrl+Shift+H` Windows 全局显示/隐藏叠加层
- 窗口内按钮控制：
  - `Pause / Resume`
  - `Source`
  - `Lock`
- 本地设置持久化：
  - 窗口位置
  - 大小
  - 锁定状态
  - 原文显示状态
  - 最近一次选择的回环设备索引
- 字幕超时自动清空
- `--demo` 演示模式
- 启动诊断能力：
  - 依赖/平台预检
  - 回环设备解析检查
  - Whisper 模型初始化检查
  - 启动失败时保留错误文本
  - `--diagnostics` CLI
- 设备选择能力：
  - `--list-devices`
  - `--device-index`
  - `--choose-device`
- Windows 首次联调辅助：
  - [README.md](/Users/SmoothShadow/vibeCoding/live-subtitle-overlay/README.md:1) 中文说明
  - [docs/WINDOWS_FIRST_RUN.md](/Users/SmoothShadow/vibeCoding/live-subtitle-overlay/docs/WINDOWS_FIRST_RUN.md:1) 真机联调手册
  - [scripts/windows-first-run.ps1](/Users/SmoothShadow/vibeCoding/live-subtitle-overlay/scripts/windows-first-run.ps1:1) 启动脚本
- 单元测试覆盖：
  - config
  - diagnostics
  - pipeline
  - settings

## 当前还没完成的，不是代码，而是真机验证

下面这些还没有在目标 Windows 机器上完成，因此现在还不能直接认为“已经可以打包交付”：

1. Windows 真机回环音频采集验证
2. Windows 真机 GUI 行为验证
3. Whisper 在目标机上的真实 CUDA / CPU 推理验证
4. Azure Translator 真实 key 的联调验证
5. 日语视频实际内容下的延迟、稳定性、可读性调优
6. 打包后的运行验证

## 当前 CLI

当前可用参数：

- `--demo`
- `--config-check`
- `--show-source`
- `--dotenv`
- `--list-devices`
- `--settings`
- `--device-index`
- `--diagnostics`
- `--choose-device`

常用命令：

```powershell
live-subtitle-overlay --diagnostics
live-subtitle-overlay --choose-device
live-subtitle-overlay
live-subtitle-overlay --demo
```

如果想走脚本化首跑：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\windows-first-run.ps1
```

## 当前配置重点

主要 `.env` 字段：

- `AZURE_TRANSLATOR_KEY`
- `AZURE_TRANSLATOR_REGION`
- `AZURE_TRANSLATOR_ENDPOINT`
- `TARGET_LANGUAGE`
- `SOURCE_LANGUAGE`
- `WHISPER_MODEL`
- `WHISPER_DEVICE`
- `WHISPER_COMPUTE_TYPE`
- `CHUNK_SECONDS`
- `FRAMES_PER_BUFFER`
- `WASAPI_LOOPBACK_DEVICE_INDEX`
- `ENABLE_VAD`
- `VAD_AGGRESSIVENESS`
- `SILENCE_RMS_THRESHOLD`
- `OVERLAY_FONT_SIZE`
- `OVERLAY_OPACITY`
- `OVERLAY_WIDTH`
- `OVERLAY_HEIGHT`
- `SUBTITLE_TIMEOUT_SECONDS`
- `SHOW_SOURCE_TEXT`

用户当前目标配置是：

- Azure 区域：`eastasia`
- 源语言：`ja`
- 目标语言：`zh-Hans`

这组配置在当前代码逻辑下是正确的。

## 当前依赖与目标运行环境

目标平台：

- Windows only

推荐 Python：

- Python `3.11` 到 `3.13`

关键依赖：

- `faster-whisper`
- `PySide6`
- `PyAudioWPatch`
- `webrtcvad-wheels`
- `numpy`

目标机器硬件：

- `RTX 4070 SUPER`
- `Ryzen 7 5800X`

## 本轮已经验证过的内容

在当前环境中已验证：

- `python3 -m compileall src`
- `PYTHONPATH=src python3 -m unittest discover -s tests`

以上检查通过。

当前环境中未验证：

- Windows 回环音频
- Windows GUI 实际行为
- CUDA 推理
- Azure 真实网络调用
- 打包后的行为

## 接下来最关键的是：等待用户的 Windows 真机测试结果

用户下一步应该在目标 Windows 机器上完成以下测试，然后把结果反馈回来。

建议测试顺序：

1. `live-subtitle-overlay --diagnostics`
2. `live-subtitle-overlay --choose-device`
3. `live-subtitle-overlay`
4. 播放真实日语视频
5. 测试快捷键与按钮

## 用户测试后，应该回报什么

用户测试完后，最好一次性反馈以下信息：

1. `--diagnostics` 的输出结果
   - 是否有 `[ERROR]`
   - 如果有，完整报错文本是什么

2. 设备选择情况
   - 选中的 loopback 设备名称
   - 选中后是否能稳定抓到播放器声音

3. 识别情况
   - 是否能稳定识别日语
   - 延迟大概多少秒
   - 有没有明显漏字、乱字、重复刷新的问题

4. 翻译情况
   - 是否成功出中文
   - 是否出现 Azure 相关错误

5. UI/交互情况
   - `Ctrl+Shift+S` 是否正常
   - `Ctrl+Shift+L` 是否正常
   - `Ctrl+Shift+T` 是否正常
   - `Ctrl+Shift+H` 是否正常
   - 窗口是否会被播放器遮挡

6. 稳定性情况
   - 是否崩溃
   - 是否卡死
   - 是否内存/显存异常增长

## 用户测试结果回来后，下一步怎么决策

收到真机测试结果后，下一步应按下面逻辑走：

1. 如果启动失败或诊断失败
   - 先修依赖、设备解析、Whisper 初始化或 Azure 配置问题

2. 如果能跑通，但字幕效果差
   - 优先调这些参数：
     - `CHUNK_SECONDS`
     - `ENABLE_VAD`
     - `VAD_AGGRESSIVENESS`
     - `SILENCE_RMS_THRESHOLD`
     - `SUBTITLE_TIMEOUT_SECONDS`
   - 必要时调整分段合并和去重逻辑

3. 如果真实使用已经稳定可接受
   - 进入打包准备阶段
   - 下一步开始接 `PyInstaller` 或其他 Windows 打包方案

## 重要文件

- [README.md](/Users/SmoothShadow/vibeCoding/live-subtitle-overlay/README.md:1)
  中文使用说明
- [docs/WINDOWS_FIRST_RUN.md](/Users/SmoothShadow/vibeCoding/live-subtitle-overlay/docs/WINDOWS_FIRST_RUN.md:1)
  Windows 首次联调手册
- [scripts/windows-first-run.ps1](/Users/SmoothShadow/vibeCoding/live-subtitle-overlay/scripts/windows-first-run.ps1:1)
  Windows 首跑脚本
- [src/live_subtitle_overlay/app.py](/Users/SmoothShadow/vibeCoding/live-subtitle-overlay/src/live_subtitle_overlay/app.py:1)
  CLI 入口和应用装配
- [src/live_subtitle_overlay/pipeline.py](/Users/SmoothShadow/vibeCoding/live-subtitle-overlay/src/live_subtitle_overlay/pipeline.py:1)
  字幕流水线与暂停逻辑
- [src/live_subtitle_overlay/ui.py](/Users/SmoothShadow/vibeCoding/live-subtitle-overlay/src/live_subtitle_overlay/ui.py:1)
  叠加层窗口、按钮和快捷键
- [src/live_subtitle_overlay/diagnostics.py](/Users/SmoothShadow/vibeCoding/live-subtitle-overlay/src/live_subtitle_overlay/diagnostics.py:1)
  启动诊断

## 给下一个 assistant 的明确说明

如果下一轮会话是基于用户的 Windows 真机测试反馈继续：

1. 先读本文件
2. 再读用户给出的测试结果
3. 再按需要查看：
   - `README.md`
   - `docs/WINDOWS_FIRST_RUN.md`
   - `src/live_subtitle_overlay/app.py`
   - `src/live_subtitle_overlay/pipeline.py`
   - `src/live_subtitle_overlay/ui.py`
4. 优先根据真实测试结果修复阻塞项或调参
5. 只有在真实使用已经稳定后，才进入打包工作

## 建议恢复提示词

用户下次可以直接这样说：

> 读取 `SESSION_HANDOFF.md`，再根据我这次 Windows 真机测试结果继续。以下是测试结果：...
