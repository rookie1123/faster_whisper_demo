# 本地实验记录

本仓库基于 [SYSTRAN/faster-whisper](https://github.com/SYSTRAN/faster-whisper)（MIT 协议），
下面记录的是我在这台机器上做的中文识别实验。上游代码未做修改，新增内容见"文件说明"。

## 环境

- 操作系统: Windows
- Python: 3.12（虚拟环境 `.venv`，由 uv 创建）
- 安装方式: `pip install -e .`（可编辑安装，走清华 PyPI 镜像）
- 硬件: NVIDIA GeForce RTX 3050 Laptop（4 GB 显存），实验均在 CPU 上完成
- 模型: 从 HuggingFace 镜像手动下载，放在 `models/` 下（不入库）

## 文件说明

上游原有文件：`faster_whisper/`、`tests/`、`benchmark/`、`docker/`、`setup.py` 等。

本地新增（不属于上游）：

| 文件 | 作用 |
|---|---|
| `demo_readme.md` | 项目说明：相对上游改了什么、实验结果、下一步方向 |
| `demo.py` | 最小示例，识别仓库自带的英文 `tests/data/jfk.flac`，用来验证环境 |
| `transcribe.py` | 转写任意音频/视频，不需要标准答案；支持 `--srt` 输出字幕 |
| `eval_zh.py` | 正式评测：给定音频和标准答案，计算 CER 字错率，对比多个模型 |
| `prompts.py` | initial_prompt 词表（通用中文 / 技术场景），用 `--prompt-name` 调用 |
| `samples/` | 测试素材（个人录音 `my_audio.mp3` 已被 gitignore，不会上传） |
| `reports/` | 每次评测的归档报告（带时间戳，不互相覆盖） |
| `eval_report.md` | 最新一次评测结果（每次运行被覆盖；本地文件，不入库） |
| `.vscode/` | 本地 IDE 配置，含 F5 运行配置（已被 gitignore） |

## 评测方法

指标用 **CER（字错率）**：

```
CER = (替换 + 删除 + 插入) / 标准答案字数
```

比较时忽略标点和空白，并做一次**数字规范化**——把"百分之九十一"和"91%"统一成同一种写法。
因为 Whisper 输出阿拉伯数字而标准答案常写成汉字数字，不做这一步会凭空多出大量假错误：

| 模型 | 原始 CER | 规范化 CER |
|---|---|---|
| faster-whisper-tiny | 37.5% | 28.1% |
| faster-whisper-small | 28.8% | **10.4%** |

（真实录音 `my_audio.mp3`，约 25 秒，去标点后 104 字）

## 实验记录

### 实验一：合成语音（已知答案的对照）

用 Windows 语音合成生成两段中文音频（`samples/zh_tts_1.wav`、`zh_tts_2.wav`），
文本见 `samples/zh_ground_truth.txt`。合成语音干净无噪声，代表效果上限。

结论：`small` 完全正确；`tiny` 错 4 处，且输出**繁体字**，数字识别崩溃
（"百分之九十二" → "9%12%"）。

### 实验二：真实录音

朗读 `samples/my_audio.txt` 并录音，用同一套脚本评测。

结论：

- `small` 规范化 CER 10.4%，属于"可用，人工校对一遍"的水平
- `tiny` 规范化 CER 28.1%，错误随机且不成规律，不可用
- `small` 剩下的错误集中在**英文专有名词**（GitHub → VTOP），其次是一处数字幻觉
  和一处同音字（登录 → 登陆）

## 复现方法

```powershell
# 1. 建环境（Python 3.12）
uv venv .venv --python 3.12 --seed
.\.venv\Scripts\python.exe -m pip install -e . -i https://pypi.tuna.tsinghua.edu.cn/simple

# 2. 下载模型（以 small 为例）到 models/faster-whisper-small/
#    https://hf-mirror.com/Systran/faster-whisper-small/resolve/main/{model.bin,config.json,tokenizer.json,vocabulary.txt}

# 3. 环境自检
.\.venv\Scripts\python.exe demo.py

# 4. 评测（有标准答案）
.\.venv\Scripts\python.exe eval_zh.py samples\my_audio.mp3 samples\my_audio.txt

# 5. 转写（没有标准答案，只想看内容）
.\.venv\Scripts\python.exe transcribe.py samples\my_audio.mp3 --srt
```

## 待办

- 用 `--prompt` 传入专有名词表，看能否修正 GitHub 这类错误
- 尝试 medium 模型，看能否把 CER 压到 5% 以下
- 启用 GPU（需要 cuDNN 9 + cuBLAS 12），对比 CPU/GPU 速度
