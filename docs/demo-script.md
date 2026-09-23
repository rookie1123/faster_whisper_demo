# Faster Whisper 四分钟现场演示脚本

## 演示目标

用本地 `faster-whisper-small` 模型在 CPU 上转写一段 2 分 43 秒的原创中文技术录音，并生成 UTF-8 SRT 字幕。演示重点是长音频处理速度、中文字幕输出和无网络运行能力。

正式演示前需确认 `.venv`、`models/faster-whisper-small` 和音频都已在本机。不要把模型下载安排在现场演示中。

## 四分钟流程

### 0:00-0:30：介绍素材与目标

口播：

> 这是一段 2 分 43 秒的原创中文技术录音，包含 Faster Whisper、OpenAI、CTranslate2、模型参数和数字。接下来使用本地 small 模型，在 CPU 上完成转写并输出 SRT 字幕。整个推理过程不依赖网络。

### 0:30-0:45：环境自检

```powershell
run.bat -c "import sys; from pathlib import Path; print('python='+sys.version.split()[0]); print('model_ready='+str(Path(r'models\faster-whisper-small\model.bin').is_file())); print('audio_ready='+str(Path(r'samples\demo\demo_speech.wav').is_file()))"
```

预期看到 Python `3.12.x`，并且 `model_ready`、`audio_ready` 都是 `True`。实测耗时约 0.09 秒。

### 0:45-1:40：执行长音频转写

```powershell
run.bat transcribe.py samples\demo\demo_speech.wav --model faster-whisper-small --srt
```

命令运行时口播：

> `run.bat` 会固定使用项目内的 Python 3.12 环境。当前默认设备是 CPU，计算类型是 int8；模型和音频都来自本地。`--srt` 会在音频旁生成带时间轴的字幕文件。

本机联网彩排的命令总耗时为 47.23 秒，离线彩排为 48.88 秒，因此给此步骤预留 55 秒。

### 1:40-2:25：解释结果

指出终端中的四个数字：

- 检测语言：`zh`，概率 `1.00`
- 音频时长：`163.0s`
- 识别耗时：联网 `46.0s`，离线 `47.7s`
- 速度倍率：联网 `3.5x`，离线 `3.4x`

口播：

> 163 秒音频不到 49 秒就完成，速度约为实时的 3.4 到 3.5 倍。输出共有 102 条字幕，时间轴一直覆盖到 2 分 43 秒。

### 2:25-3:10：检查字幕

PowerShell 查看开头和结尾；Python 程序仍统一通过 `run.bat` 启动。

```powershell
Get-Content samples\demo\demo_speech.srt -Encoding utf8 -TotalCount 20
Get-Content samples\demo\demo_speech.srt -Encoding utf8 -Tail 8
```

口播：

> SRT 文件使用 UTF-8 编码，每条字幕都包含序号、开始时间、结束时间和文本，可以直接导入播放器或剪辑软件。录音中的英文技术词更容易出现拼写误差，这也说明专有名词词表仍有优化空间。

### 3:10-3:40：总结

口播：

> 这次演示证明 Faster Whisper 可以在普通 CPU 上离线处理长中文音频：2 分 43 秒音频约 49 秒完成，同时直接生成可用的 SRT。联网与离线输出的 SHA-256 完全一致，说明推理没有依赖在线服务。

### 3:40-4:00：缓冲

预留 20 秒用于切换窗口、等待机器波动或回答一个简短问题。若转写提前结束，不要继续堆参数，直接进入结果说明。

## 救场方案

| 现场问题 | 处理方式 |
| --- | --- |
| 提示 `.venv` 不存在或缺少 `av` | 说明启动了错误解释器，改用 `run.bat`；演示前必须完成依赖安装，不在现场临时安装。 |
| 提示模型目录不存在 | 演示前运行 `run.bat download_model.py small`；现场优先展示预先生成的 SRT，不等待下载。 |
| small 模型超过 75 秒仍未完成 | 按 `Ctrl+C`，改用 `run.bat transcribe.py samples\demo\demo_speech.wav --model faster-whisper-tiny --srt`，或展示预生成字幕。 |
| CPU 报 `float16` 不支持 | 使用默认 `int8`，不要在 CPU 演示中添加 `--compute-type float16`。 |
| 终端中文乱码 | 字幕文件本身仍是 UTF-8；用 `Get-Content ... -Encoding utf8` 展示，不根据终端乱码判断文件损坏。 |
| 现场没有网络 | 不处理；模型已经在 `models/` 中，正式命令使用本地路径，可直接离线运行。 |
| 音频路径错误 | 回到仓库根目录，并确认 `samples\demo\demo_speech.wav` 存在。 |

## 演示前最终检查

```powershell
git status --short --branch
run.bat transcribe.py samples\demo\demo_speech.wav --model faster-whisper-small --srt
```

确认命令成功后保留本地生成的 `samples/demo/demo_speech.srt` 作为救场文件。该字幕被 `.gitignore` 排除，不提交到仓库。
