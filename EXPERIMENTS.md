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
| `COLLABORATION.md` | 协作指南：环境准备、分支流程、PR 检查清单 |
| `demo.py` | 最小示例，识别仓库自带的英文 `tests/data/jfk.flac`，用来验证环境 |
| `transcribe.py` | 转写任意音频/视频，不需要标准答案；`--models` 可一次对比多个模型，`--srt` 输出字幕 |
| `eval_zh.py` | 正式评测：给定音频和标准答案，计算 CER 字错率，对比多个模型 |
| `prompts.py` | initial_prompt 词表（通用中文 / 技术场景），用 `--prompt-name` 调用 |
| `download_model.py` | 下载模型权重到 `models/`（默认走 hf-mirror，支持断点续传） |
| `run.bat` | 统一入口，固定使用项目内的 `.venv`，避免系统 PATH 里别的 Python 抢先 |
| `samples/` | 测试素材，目录结构见下 |
| `reports/` | 每次评测的归档报告（带时间戳，不互相覆盖） |
| `eval_report.md` | 最新一次评测结果（每次运行被覆盖；本地文件，不入库） |
| `.vscode/` | 本地 IDE 配置，含 F5 运行配置（已被 gitignore） |

### 素材目录结构

```
samples/
├── reading_script.txt         # 朗读稿，也是唯一的评测标准答案
├── reading_script_tts.wav     # 同一段文字的合成语音，作为"干净音频"对照组
├── speaker/                   # 真人录音，命名 speaker_<名字>.<后缀>
└── round1/                    # 第一轮实验素材（已归档，音频不入库）
```

三条约定：

1. **所有真人录音统一放 `samples/speaker/`**，命名成 `speaker_<名字>.mp3|m4a`，
   不再散落在仓库根目录或 `tests/data/` 里。
2. **标准答案统一用 `samples/reading_script.txt`**，不要每个人各传一份
   （内容相同，多份来源会让人不知道该信哪个）。
3. 第一轮实验用的音频归档在 `samples/round1/`，其中音频文件被 `.gitignore` 排除，
   只保留当时的答案文本；对应的实验结论见下方"实验一、实验二"。

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

三模型对照（CPU int8，beam_size=5，vad_filter=True；两段音频去标点后均为 50 字）：

**`zh_tts_1.wav`** — 含百分比数字（"百分之八十七"→"87%"）

| 模型 | 原始 CER | 规范化 CER | 替换 | 漏字 | 多字 | 识别耗时 | 速度倍率 |
|---|---|---|---|---|---|---|---|
| faster-whisper-tiny | 55.4% | 42.0% | 18 | 1 | 2 | 3.3s | 4.5x |
| faster-whisper-small | 21.4% | **0.0%** | 0 | 0 | 0 | 2.4s | 6.2x |
| faster-whisper-medium | 21.4% | **0.0%** | 0 | 0 | 0 | 6.5s | 2.3x |

**`zh_tts_2.wav`** — 含英文专有名词 GitHub

| 模型 | 原始 CER | 规范化 CER | 替换 | 漏字 | 多字 | 识别耗时 | 速度倍率 |
|---|---|---|---|---|---|---|---|
| faster-whisper-tiny | 28.6% | 32.0% | 15 | 1 | 0 | 0.6s | 19.2x |
| faster-whisper-small | 4.1% | **0.0%** | 0 | 0 | 0 | 2.3s | 5.4x |
| faster-whisper-medium | 4.1% | **0.0%** | 0 | 0 | 0 | 6.0s | 2.1x |

观察：

- `small` 与 `medium` 在两段合成音频上**都是规范化 CER 0.0%**，`medium` 没有任何提升，
  耗时却是 `small` 的 **2.5~2.7 倍**。
- `tiny` 的错误很稳定：一律输出**繁体字**（项→項、码→碼、响→響），
  且数字会崩（"百分之八十七"→"8%"、"九十二"→"9%12%"；"十点"→"十點"）。
  规范化后 CER 甚至可能**升高**（`zh_tts_2`: 28.6% → 32.0%）。
- `medium` 把 GitHub 写成了 `Github`；因为评测归一化里有 `lower()`，
  大小写差异不计入错误（见 `eval_zh.py` 的 `normalize()`）。
- 结论：**干净合成语音区分不出 small 和 medium**，天花板太低。
  要评估 medium 的价值，必须用真实录音（见实验二）或多噪声、多口音的素材。

> 样本 2 的标准答案原先埋在 `zh_ground_truth.txt`（带 `#` 注释行），
> 直接当 reference 会让 CER 虚高。现已拆出干净的 `samples/zh_tts_2.txt`。

### 实验二：真实录音

朗读 `samples/my_audio.txt` 并录音，用同一套脚本评测。

> ⚠️ 注意：录音文件 `samples/my_audio.mp3` 已被 gitignore（未入库）。
> 当前工作区里**只有答案文本 `my_audio.txt`，没有音频文件**，
> 所以实验二暂时无法复现——需要重新录一遍，或把原音频放回 `samples/`。
> 想立刻做「medium 能否把 CER 压到 5% 以下」的对照，得先补上这段录音。

结论：

- `small` 规范化 CER 10.4%，属于"可用，人工校对一遍"的水平
- `tiny` 规范化 CER 28.1%，错误随机且不成规律，不可用
- `small` 剩下的错误集中在**英文专有名词**（GitHub → VTOP），其次是一处数字幻觉
  和一处同音字（登录 → 登陆）

### 实验三：initial_prompt 词表对照

针对实验二暴露的"英文专有名词识别错"问题，测试 `prompts.py` 里的词表机制。
`--prompt-name zh` 只传 `"以下是普通话的句子。"`；
`--prompt-name tech` 在其后追加词表（GitHub、服务器、模型、克隆、会议室…）。

**样本 `zh_tts_2.wav`**（含 GitHub，50 字）：

| 模型 | 无提示 | `--prompt-name zh` | `--prompt-name tech` |
|---|---|---|---|
| faster-whisper-tiny | 32.0% | 2.0% | **0.0%** |
| faster-whisper-small | 0.0% | 0.0% | 0.0% |
| faster-whisper-medium | 0.0% | 0.0% | 0.0% |

从 tiny 的识别原文能清楚看出两步各自的贡献：

| 配置 | tiny 输出 |
|---|---|
| 无提示 | 這個項目的代碼我已經上傳到`Github`了你可以直接`克龍`下來跑一下如果遇到問題我們明天上午`十點`再討論 |
| `zh` | 这个项目的代码我已经上传到`Github`了,你可以直接`克龙`下来跑一下。如果遇到问题,我们明天上午`十点`再讨论。 |
| `tech` | 这个项目的代码我已经上传到`GitHub`了,你可以直接`克隆`下来跑一下。如果遇到问题,我们明天上午`十点`再讨论。 |

- **`zh` 那一句单独就修掉了全部繁体字**（這個→这个、項→项、龍→龙、點→点），
  tiny 的 CER 从 32.0% 降到 2.0% —— 这是本项目收益最大的单项改动。
- **再叠加 `tech` 词表，才修掉剩下两处**：`Github`→`GitHub`、`克龙`→`克隆`
  （两个词都在词表里）。CER 2.0% → **0.0%，tiny 直接打平 small**。

但词表不是万能药 —— 换到 `zh_tts_1.wav`（内容是百分比数字，词表里的词一个都没出现）：

| 模型 | 无提示 | `--prompt-name zh` | `--prompt-name tech` |
|---|---|---|---|
| faster-whisper-tiny | 42.0% | **6.0%** | 10.0% |
| faster-whisper-small | 0.0% | 0.0% | 0.0% |
| faster-whisper-medium | 0.0% | 0.0% | 0.0% |

- `zh` 依然大幅有效（42.0% → 6.0%，同样是修繁体字）。
- **`tech` 反而回退到 10.0%**：词表里没有一个词出现在这段音频里，
  凭空多出的候选词反而干扰了解码（数字崩成 `9%12%`，响→想、应→用）。

**结论**

1. 不管什么场景，`--prompt-name zh` 都值得默认加上 —— 几乎零成本，专治繁体输出。
2. 词表（`tech`）**只在音频里真的会出现那些词时才用**。硬套一个不相关的词表，
   效果可能反而变差（10.0% > 6.0%）。换领域前先想想这段话里到底有哪些专有名词。
3. `small` / `medium` 在所有配置下都是 0.0%，本来就没问题 ——
   提示词的价值主要体现在 `tiny` 这类弱模型上。

### 实验四：真实录音（`samples/test1.m4a`，36.3s 技术周会）

> 这是本仓库当前**唯一能拿到的真实录音**（`my_audio.mp3` 缺失，见实验二）。
> 内容是技术周会汇报，含 `TensorRT`、显存、训练日志等专有名词。
> 没有配套标准答案 txt，所以本实验只能对比「识别原文」，暂算不出 CER。

用 `transcribe.py`（不需要标准答案）跑出来的三段原文对比：

| 配置 | 识别原文（节选，错误用 `代码体` 标出） |
|---|---|
| small / 无提示 | 上周我们组的`张启禀`老师看了`训练日子`,发现`显存账用`比预期高出将近`3成`,我换用了`Tenso RT`做推理加速…放在`仓户`的文档里…我们`单面讨论` |
| medium / 无提示 | 张启**明**、训练**日志**、显存**占用**、将近**三成**、**仓库** —— 全部修对；仍错 `Tenso RT`、`单面讨论` |
| medium / 扩展词表 | `TensorRT`、`当面讨论` 也修对 —— 只剩人名（张启明/张启平）不确定 |

扩展词表是用 `--prompt` 一次性传入的（未落进 `prompts.py`）：

```
以下是普通话的句子。可能出现的词：TensorRT、显存、训练日志、仓库、推理加速、半精度、当面讨论。
```

**结论**

1. **真实录音上 `medium` 显著优于 `small`** —— 这正是两段合成语音里看不到的差距。
   `small` 至少 5 处错，`medium` 只剩 2 处，叠加词表后只剩 1 处人名。
   实验二那条待办「medium 能否把 CER 压到 5% 以下」，在真实录音上**大概率成立**。
2. **词表在真实录音上收益极大**（`Tenso RT`→`TensorRT`、`单面讨论`→`当面讨论`），
   与实验三的结论一致：词表要贴合音频里真实出现的专有名词。
3. **但 `zh` 提示在 `medium` 上反而引入了繁体**：`仓库` → `倉库`，
   人名也从「张启明」漂到「张启平」。说明 `zh` 的"治繁体"作用不是绝对的 ——
   在较长的真实录音上，`medium` 可能被这句引导带偏。`tech`（词表含"仓库"）则无此问题。
4. 耗时（36.3s 音频，CPU int8）：`small` 7.8s（4.7x 实时）、`medium` 20.5s（1.8x 实时）。

一条命令跑完三个模型（`transcribe.py` 的 `--models` 会依次加载并转写）：

```powershell
.\run.bat transcribe.py samples\test1.m4a --models faster-whisper-tiny faster-whisper-small faster-whisper-medium
```

`tiny` 在这段录音上的输出完全不可用（通篇繁体 + 生造词）：
`上週我們主的張錦勞斯康勒訓練日日`、`顯存掌用筆預期高出將近三場`、`倉戶的溫檔`。

### 实验五：多说话人与词表对照（待成员 A 完成）

**这一节留给成员 A 的任务产出**，要求是：
对 `samples/speaker/` 下的五段录音，各跑三个条件（不加词表 / `tech` 词表 / `ml` 词表），
整理成一张"说话人 × 词表"对照表，并给出结论。

详细步骤和产出格式见 `TASKS.md` 的成员 A 一节。

> 说明：多说话人基线数据由成员 A 在自己的分支上跑出来并提交，
> 这样每个人的实验记录都出自本人，汇报时经得起追问。

## 复现方法

```powershell
# 1. 建环境（Python 3.12）
uv venv .venv --python 3.12 --seed
.\.venv\Scripts\python.exe -m pip install -e . -i https://pypi.tuna.tsinghua.edu.cn/simple

# 2. 下载模型到 models/faster-whisper-<size>/
.\.venv\Scripts\python.exe download_model.py small
.\.venv\Scripts\python.exe download_model.py medium
#    （默认走 https://hf-mirror.com，直连 huggingface.co 会超时；
#      已下载完整的模型会自动跳过，中断后重跑即断点续传）

# 3. 环境自检
.\.venv\Scripts\python.exe demo.py

# 4. 评测（有标准答案）
#    真人录音示例（仓库内已有三段，见 samples/speaker/）
.\.venv\Scripts\python.exe eval_zh.py samples\speaker\speaker_fujian.mp3 samples\reading_script.txt
#    三模型对照
.\.venv\Scripts\python.exe eval_zh.py samples\speaker\speaker_fujian.mp3 samples\reading_script.txt --models faster-whisper-tiny faster-whisper-small faster-whisper-medium
#    用合成音频做对照（排除录音质量的影响）
.\.venv\Scripts\python.exe eval_zh.py samples\reading_script_tts.wav samples\reading_script.txt

# 5. 转写（没有标准答案，只想看内容）
.\.venv\Scripts\python.exe transcribe.py samples\speaker\speaker_fujian.mp3 --srt

# 也可以用 run.bat 包一层，它会自动使用项目内的 .venv
run.bat eval_zh.py samples\speaker\speaker_fujian.mp3 samples\reading_script.txt
```

## 待办

- ~~用 `--prompt` 传入专有名词表，看能否修正 GitHub 这类错误~~ →
  已完成，见实验三。`zh` 引导修繁体（tiny 42.0%→6.0%），`tech` 词表再修专有名词
  （tiny 32.0%→0.0%）；但词表要不相关就会轻微回退，别硬套
- 在 `transcribe.py` 里给 `--prompt-name` 加一个"默认用 zh"的选项，
  免得每次都要手动传
  ⚠️ 但实验四发现：`zh` 在 `medium` + 长录音上会**引入繁体**（仓库 → 倉库）。
  所以设默认值之前要想清楚，也许默认应该是不传或 `tech`，而不是 `zh`
- ~~尝试 medium 模型~~ → 已就位（`models/faster-whisper-medium`，1.46 GB），
  并在真实录音 `samples/test1.m4a` 上验证：medium 明显优于 small（见实验四）。
  剩下的：
  1) 给 `samples/test1.m4a` 补一份标准答案 txt（照录音把正确文本写下来），
     才能算出真实 CER，把「medium 能否压到 5% 以下」从"大概率"变成确数
  2) 把实验四用的扩展词表固化进 `prompts.py` —— 建议**新增一条**，
     不要改 `tech`，否则实验三的历史数据不可复现
- 启用 GPU（需要 cuDNN 9 + cuBLAS 12），对比 CPU/GPU 速度
