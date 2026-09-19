# faster-whisper 中文识别实验项目

> 基于 [SYSTRAN/faster-whisper](https://github.com/SYSTRAN/faster-whisper) 的中文语音识别实验与工程化实践。
> 上游项目采用 MIT 协议，原始说明保留在 [README.md](README.md)（本文件不影响它）。

## 一、项目简介

[faster-whisper](https://github.com/SYSTRAN/faster-whisper) 是用 CTranslate2 重新实现的 OpenAI Whisper，
在保持识别精度的前提下比原版快数倍。它本身是一个**通用推理库**：给你一个 API，你调用它转写音频。

本项目在它之上做三件事：

1. **评测**中文场景下的真实表现——不只是"能跑"，而是量化到底错在哪里、错多少
2. **工程化**成可直接使用的工具——转写任意音视频、输出 SRT 字幕、批量处理
3. **沉淀实验记录**——每次实验的条件和结论都留档，可复现、可对比

核心目标是把"这个模型准不准"从一句主观感受，变成一个有数字支撑的结论。

## 二、快速开始

```powershell
# 1. 建环境（Python 3.12；不要用 3.13/3.14，ctranslate2 等包还没有对应 wheel）
uv venv .venv --python 3.12 --seed
.\.venv\Scripts\python.exe -m pip install -e . -i https://pypi.tuna.tsinghua.edu.cn/simple

# 2. 下载模型到 models/faster-whisper-small/（国内建议用镜像，4 个文件缺一不可）
#    https://hf-mirror.com/Systran/faster-whisper-small/resolve/main/model.bin
#    .../config.json   .../tokenizer.json   .../vocabulary.txt

# 3. 环境自检（识别仓库自带的英文测试音频）
.\.venv\Scripts\python.exe demo.py

# 4. 评测中文准确率（需要一段音频 + 对应的标准答案文本）
.\.venv\Scripts\python.exe eval_zh.py samples\my_audio.mp3 samples\my_audio.txt

# 5. 转写任意音视频，并输出字幕
.\.venv\Scripts\python.exe transcribe.py samples\my_audio.mp3 --srt --prompt-name tech
```

在 VSCode 里也可以用 `F5` 直接运行：`.vscode/launch.json` 预置了评测、带词表评测、转写、自检四套配置。

## 三、与原项目的差异

**上游代码零修改。** `faster_whisper/`、`tests/`、`benchmark/`、`setup.py` 等文件保持原样，
这样日后同步上游更新时 `git diff` 是干净的，一眼就能看出哪些是本项目新增的内容。

新增内容如下：

| 文件 | 作用 | 为什么需要它 |
|---|---|---|
| `eval_zh.py` | 中文识别评测：算 CER 字错率、对比多个模型 | 上游只给 API，不给评测方法；判断"准不准"必须有量化指标 |
| `transcribe.py` | 转写任意音频/视频，支持 `--srt` 输出字幕 | 上游只有库接口，缺一个能直接用的命令行工具 |
| `prompts.py` | initial_prompt 词表（通用中文 / 技术场景等） | 专有名词是当前最大的错误来源，需要统一的词表管理 |
| `demo.py` | 最小示例，识别英文测试音频 | 新人 clone 下来先跑这个，确认环境没问题 |
| `EXPERIMENTS.md` | 实验记录：环境、方法、结论、复现步骤 | 让实验结论脱离聊天记录独立存在 |
| `demo_readme.md` | 本文件 | 说明本项目相对上游做了什么 |
| `COLLABORATION.md` | 协作指南：环境准备、分支流程、PR 清单、冲突处理 | 新人上手的第一个摩擦点不是写代码，而是环境和流程 |
| `samples/` | 测试素材（2 段合成音频 + 标准答案） | 让任何人 clone 下来都能立刻复现评测，不必先自己录音 |
| `reports/` | 每次评测的时间戳归档 | 实验历史不再互相覆盖 |
| `.gitignore` | 排除 `.venv/`、`models/`、个人录音、派生字幕 | 仓库只放"人与人需要共享的东西"，机器生成的一律不入库 |

## 四、实验结果

### 4.1 tiny vs small：小模型在中文上不可用

测试条件：一段真实的约 25 秒中文朗读录音（去标点后 104 字），CPU + int8 量化，`beam_size=5`、开启 VAD。

| 模型 | 参数量 | 原始 CER | 规范化 CER | 识别耗时 | 速度倍率 |
|---|---|---|---|---|---|
| faster-whisper-tiny | 39M | 37.5% | 27.1% | 0.9s | 28.0x |
| faster-whisper-small | 244M | 28.8% | **10.4%** | 3.2s | 7.7x |

结论：

- **small 可用**（10.4% 属于"人工校对一遍就能交付"的水平），tiny 不可用
- tiny 慢不慢不是问题（28 倍实时），问题是**错得没规律**：服务器→服务**器商**、
  准确率→**据**确率、脚本→**角度**、登录→**登入**，这类错误无法用后处理补救
- small 的错误则**高度集中在特定类型**上，因此有明确的优化路径（见 4.3）
- tiny 还会输出**繁体字**并把数字识别崩坏（"百分之九十二" → "9%12%"），
  这是小模型区分不了简繁、以及数字建模能力不足的典型表现

用合成语音（答案 100% 已知）做的对照实验结论相同：small 一字不差，tiny 错 4 处。

### 4.2 一个关键的方法论问题：CER 必须先做文本规范化

第一轮评测时 small 的 CER 是 28.8%，看起来"勉强可用"。但逐条核对错误后发现，
**三分之二的"错误"是假的**——标准答案写的是汉字数字（"百分之九十一"），
而 Whisper 输出阿拉伯数字（"91%"），逐字比较时 6 个字对 3 个字，一个词就产生 5-6 个"错误"。

把两边统一成阿拉伯数字后再算：

| 模型 | 原始 CER | 规范化 CER | 说明 |
|---|---|---|---|
| tiny | 37.5% | 27.1% | 略降，本质仍然不可用 |
| small | 28.8% | **10.4%** | 真实水平，虚高被挤出 18 个百分点 |

这件事的教训比数字本身重要：**没有定义"什么算对"的评测，结论会严重失真**。
正式的语音评测集（AISHELL、LibriSpeech 等）都配有严格的文本规范化规则，原因就在这里。

### 4.3 错误分析：错在哪里，为什么

规范化之后，small 一共还剩 10 处错误（脚本统计：替换 4 / 漏字 2 / 多字 4），
集中在 4 个地方：

| 错误 | 类型 | 说明 | 优化方向 |
|---|---|---|---|
| GitHub → VTOP | 英文专有名词 | 单这一个词就占了全部错误的一半以上 | initial_prompt 词表 |
| 79% → "71% 79%" | 数字幻觉 | 凭空多出一个数字 | 更大模型 |
| 登录 → 登陆 | 同音字 | 同音不同字 | 词表 / 后处理 |
| 我们 → 我们的 | 多字 | 概率性错误 | 难以根除 |

可见**一半以上的错误来自一个英文专有名词**。这解释了为什么下一步要做词表提示。

### 4.4 initial_prompt 词表

Whisper 支持 `initial_prompt`：把一段文本当作"前文"喂给模型，引导它的解码方向。
把会议里可能出现的人名、项目代号、英文术语写进去，可以显著降低同音词和生造词错误。

本项目已把词表集中到 `prompts.py`，两个脚本都支持 `--prompt-name` 参数：

```powershell
.\.venv\Scripts\python.exe eval_zh.py samples\my_audio.mp3 samples\my_audio.txt --prompt-name tech
```

> **状态说明**：词表机制已实现（`prompts.py`），但**效果尚未验证**——
> 带 `--prompt-name tech` 的对照实验还没跑。已列入下一步计划。

## 五、目录结构

```
faster-whisper/
├── faster_whisper/          # 上游核心代码（未修改）
├── tests/ benchmark/ docker/  # 上游测试与基准（未修改）
├── README.md                # 上游原始说明（保留）
├── demo_readme.md           # 本文件
├── COLLABORATION.md         # 协作指南（队友先读这个）
├── EXPERIMENTS.md           # 实验记录
├── demo.py                  # 环境自检
├── transcribe.py            # 转写工具（支持 --srt）
├── eval_zh.py               # 中文评测（CER）
├── prompts.py               # initial_prompt 词表
├── samples/                 # 测试素材（个人录音已在 .gitignore 中排除）
├── reports/                 # 历次评测归档
├── models/                  # 模型权重，不入库
└── .venv/                   # 虚拟环境，不入库
```

## 六、下一步优化方向

按"收益 ÷ 成本"排序，前两项是当前最值得做的。

**1. 验证并完善 prompt 词表（成本低，收益直接）**
用 `--prompt-name tech` 重跑评测，看 CER 能否从 10.4% 降到 7% 以下、GitHub 能否被修正。
若有效，进一步做成"每个领域一个词表"（医疗、法律、你的课题），并在转写前自动选择。

**2. 换用更大的模型（成本中，收益明确）**
`medium`（769M，约 1.5 GB）预计能把 CER 压到 5% 以下，尤其能改善数字幻觉。
你的 4 GB 显存跑 `medium` 需要 `int8_float16` 量化；`large-v3`（约 3 GB 权重）则需要 GPU + 更大显存。

**3. 实时转写（成本高，体验提升大）**
当前是"录完再转"的离线模式。实时字幕需要把音频切成小块流式送入，
并处理块边界的上下文衔接问题。faster-whisper 本身支持增量式的 `transcribe` 调用，
但要做出好用的实时界面（麦克风采集 → 分块 → 增量解码 → 滚动显示）工作量不小。

**4. 引入外部知识增强（成本中高，天花板最高）**
专有名词是当前最大错误来源，而模型本身不可能知道你的项目代号。可以做三层：

- **热词表**：把领域词汇通过 `initial_prompt` 注入（已实现，待验证效果）
- **后处理纠错**：用同音字词典 + 语言模型对输出做二次校正，专门修"登陆/登录"这类错误
- **RAG 检索增强**：检索相关文档，为转写提供领域上下文，甚至让 LLM 结合全文做一致性校正

**5. GPU 加速（成本中）**
CPU 上 small 已是 7.7x 实时（1 小时音频约 8 分钟），够用但不够快。
启用 GPU 需要装 cuDNN 9 和 cuBLAS 12，之后预计能到 20-30x 实时。

**6. 工程化补齐（成本低）**
批量处理整个目录、字幕时间轴后处理（合并碎句、控制每行长度）、
说话人分离（需配合 `pyannote.audio` 等方案，用于会议记录）。

## 七、已知限制

- **样本量小**：结论基于 1 段真实录音 + 2 段合成音频，只能作为方向性参考，
  不足以支撑严格的模型对比结论
- **未测真实噪声场景**：测试音频是安静环境下的近场朗读，实际会议、电话、
  远场录音的 CER 会明显更高
- **只算了 CER，没算 WER**：中文没有天然的词边界，CER 更适合，
  但如果要和其他研究对比，需要补充分词后再算 WER
- **未在 GPU 上验证**：所有数据均来自 CPU + int8 量化
- **合成音频的局限**：语音合成的音频干净无噪声，代表的是效果上限而非平均水平

## 八、致谢与许可

- 核心实现来自 [SYSTRAN/faster-whisper](https://github.com/SYSTRAN/faster-whisper)，感谢原作者 Guillaume Klein
- 模型权重来自 HuggingFace 上的 `Systran/faster-whisper-*` 系列
- 本项目遵循上游的 MIT 协议，详见 [LICENSE](LICENSE)
