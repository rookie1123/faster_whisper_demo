# 分工与任务说明

五个人各自做什么、为什么做、怎么做。

课程的个人贡献系数看三类材料：**Git commit、文档记录、实验记录**（课件第 27 页）。
所以每个人的任务都包含"自己跑、自己记录、自己提交"三个环节，缺一不可。

## 总览

| 成员 | 任务 | 关键产出 | 预估耗时 |
|---|---|---|---|
| 组长 | 数据汇总、PPT、讲稿、合并 PR | 汇报材料 | 持续 |
| A | prompt 词表 A/B 对照实验 | 对照表 + 若干份实验报告 | 1.5 小时 |
| B | 量化档位对比实验 | 精度与速度对照表 | 1 小时 |
| C | 低置信度标记功能 | `transcribe.py` 新参数 + 演示 | 2 小时 |
| D | 真实音频素材 + demo 脚本 + 彩排 | 素材 + 脚本 + 彩排记录 | 2 小时 |

## 共同约定

**目录与命名**（已经在仓库里定好，别再另起炉灶）：

- 录音放 `samples/speaker/`，命名 `speaker_<你的名字>.m4a`
- 标准答案统一用 `samples/reading_script.txt`，**不要每人各传一份**
- 实验报告会自动生成到 `reports/`，文件名带时间戳和条件标签

**提交流程**：

1. 一个任务一个分支，命名 `exp/<任务名>` 或 `feat/<任务名>`
2. 提交信息说清楚"做了什么、为什么这么做"，不要写"更新""修改"
3. 推完分支后**必须开 Pull Request**（点两次：`Compare & pull request` → `Create pull request`）
4. **不要提交 `eval_report.md`**，那是本地临时文件

**环境**（跑不起来先看这条）：

```powershell
git clone https://github.com/rookie1123/faster_whisper_demo.git
cd faster_whisper_demo
uv venv .venv --python 3.12 --seed
.\.venv\Scripts\python.exe -m pip install -e . -i https://pypi.tuna.tsinghua.edu.cn/simple
.\.venv\Scripts\python.exe download_model.py small   # 自动走 hf-mirror
run.bat demo.py                                       # 能识别出英文句子就说明环境没问题
```

---

## 成员 A：prompt 词表 A/B 对照实验

### 为什么做

前期的实验已经证明词表有效——同一段录音，small 模型加词表后规范化字错率从 **6.9% 降到 1.7%**。
但这只是**一段录音、一份词表**的结果，说服力有限。要回答的是两个更硬的问题：

1. 这个效果在**不同说话人**身上稳定吗，还是只对某一个人有效？
2. **通用的词表**（为别的内容写的）能不能拿来就用？

这两个问题决定了"词表"到底是一项可推广的方法，还是一次碰巧的调参。
对应课程要求里的"消融实验"和"对照设计"。

### 怎么做

对 `samples/speaker/` 下的**每一段**录音，跑三个条件：

```powershell
cd "你的仓库目录"

# 条件一：基线（不加任何提示）
.\.venv\Scripts\python.exe eval_zh.py samples\speaker\speaker_<名字>.m4a samples\reading_script.txt

# 条件二：旧词表（tech，为第一轮内容写的，与本轮朗读稿无关）
.\.venv\Scripts\python.exe eval_zh.py samples\speaker\speaker_<名字>.m4a samples\reading_script.txt --prompt-name tech

# 条件三：本轮定制的词表（ml，针对朗读稿里的专有名词）
.\.venv\Scripts\python.exe eval_zh.py samples\speaker\speaker_<名字>.m4a samples\reading_script.txt --prompt-name ml
```

每段录音 3 条命令，把 `<名字>` 换成实际文件名。

### 产出物

1. `reports/` 里新增的实验报告（每跑一次自动生成一份）
2. **一张对照表**，写到 `EXPERIMENTS.md` 里，形如：

```
| 说话人 | 无词表 | tech 词表 | ml 词表 | 结论 |
|---|---|---|---|---|
| speaker_fujian | ? | ? | ? | |
| speaker_daiyipeng | ? | ? | ? | |
| speaker_huangsiyang | ? | ? | ? | |
```

### 注意

- **词表要在跑之前定好**，不许跑完看着错误再回头改词表——那样结论就不成立了。
  这一点在汇报时要主动说明，否则会被老师问住。
- 三个条件必须用**同一段音频、同一个模型**，只改词表这一个变量。

---

## 成员 B：量化档位对比实验

### 为什么做

目前所有实验都跑在 `compute_type=int8` 上，但**从来没有人验证过这个选择是否合理**。
量化是"精度换速度"的取舍：int8 把权重压成 8 位整数，省内存、跑得快，
代价是可能损失精度；float32 精度最高但最慢。

这正好对应课件的"部署与评测"模块——**指标、消融、失败分析**。
做完能回答一个实际问题：**在 CPU 上跑中文识别，哪种量化档位性价比最高。**

### 怎么做

用同一段音频，换不同量化档位各跑一次：

```powershell
# 三个档位，都用同一段音频和同一个模型，只改 --compute-type
.\.venv\Scripts\python.exe eval_zh.py samples\speaker\speaker_fujian.mp3 samples\reading_script.txt --models faster-whisper-small --compute-type int8
.\.venv\Scripts\python.exe eval_zh.py samples\speaker\speaker_fujian.mp3 samples\reading_script.txt --models faster-whisper-small --compute-type int8_float32
.\.venv\Scripts\python.exe eval_zh.py samples\speaker\speaker_fujian.mp3 samples\reading_script.txt --models faster-whisper-small --compute-type float32
```

再把模型从 small 换成 tiny 重复一遍，就得到 2 × 3 的完整矩阵。
非默认档位会自动写进报告文件名（如 `..._noprompt_float32.md`），方便区分。

### 产出物

一张表：

```
| 模型 | 量化档位 | 规范化 CER | 识别耗时 | 速度倍率 |
|---|---|---|---|---|
| tiny | int8 | | | |
| tiny | float32 | | | |
| small | int8 | | | |
| small | float32 | | | |
```

### 注意（重要）

**float16 在 CPU 上跑不了。** CTranslate2 的 CPU 后端不支持 float16 计算，
直接传 `--compute-type float16` 会报错。脚本已经加了友好提示，但你要知道原因：
float16 需要 GPU 才算得动。

**这本身就是一条值得写进报告的结论**：它说明"模型精度选择"不是随便挑的，
而是被硬件后端限制死的。如果老师问"你们为什么不用 float16"，这就是答案。

另外 float32 在 CPU 上明显更慢，跑之前先用短音频试一下（`samples/reading_script_tts.wav` 只有 30 秒，适合先摸底）。

---

## 成员 C：低置信度标记功能

### 为什么做

这是把项目从"评测脚本"变成"**能用的工具**"的关键一步。

现在的转写结果是"一视同仁"的一整段文字，用户不知道哪里可能错，只能通读校对。
但 faster-whisper 的每个片段其实都带一个 `avg_logprob`（平均对数概率）——
**模型自己知道它哪里没把握**。把这个信号用起来，就可以标出需要重点核对的句子，
把"通读全文"变成"只看标出来的几句"。

课程明确写了不接受"只调用 API 做壳"，这一条就是让工具真正有自己东西的地方。

### 怎么做

1. 先摸清 API：跑一个小脚本，打印每段的 `avg_logprob` 和无把握的片段长什么样

```python
from faster_whisper import WhisperModel
model = WhisperModel("models/faster-whisper-small", device="cpu", compute_type="int8")
segments, info = model.transcribe("samples/speaker/speaker_fujian.mp3", language="zh", vad_filter=True)
for s in segments:
    print(f"{s.avg_logprob:+.3f}  {s.text.strip()}")
```

2. 观察正常片段和出错片段的 `avg_logprob` 分布，**据此选一个阈值**
   （不要拍脑袋定，要用数据说话——这就是一条消融证据）
3. 给 `transcribe.py` 加参数，默认关闭，打开后：
   - 终端输出里给低置信度片段加标记（例如前缀 `[?]`）
   - 结尾打印"共 N 段，其中 M 段需要人工核对"
4. 用同一段音频验证：标记出来的片段里，**真的包含识别错误**吗？

### 产出物

1. `transcribe.py` 的新参数 + 使用说明（写在 `--help` 里）
2. 一份验证记录：随便挑一段录音，列出"被标记的片段"和"实际出错的片段"，
   说明标记的命中率高不高

### 注意

- 阈值别定得太严（标出一半以上的句子，等于没标）也别太松（漏掉真错误）
- 改完 `transcribe.py` 后**要把 `demo.py` 和 `eval_zh.py` 也跑一遍**，
  确认没改坏别的东西

---

## 成员 D：真实音频素材 + demo 脚本 + 现场彩排

### 为什么做

现场 4 分钟演示是整个汇报最容易出彩、也最容易翻车的环节。
目前手上的素材只有 30 秒的朗读录音，**太短，撑不起演示**，
而且没有一份"照着念就不会出错"的脚本。

课程交付物里明确要求"展示材料"，而演示翻车比讲不好更伤分数。

### 怎么做

1. **准备一段 2 到 3 分钟的音频**：自己念一段长文最省事，内容自定（技术类最好，
   含数字和英文术语）。放到 `samples/demo/`。
   **不要用有版权的素材**（比如新闻联播片段），仓库是公开的。
2. **写 `docs/demo-script.md`**：现场要执行的每一条命令、每条的预期输出、
   以及"如果这条报错该怎么办"的兜底方案。
3. **完整彩排一次**，记录每一步实际耗时（4 分钟要装得下）。
4. **关掉网络再跑一遍**——现场的网络你控制不了，要确保全程离线可用。

### 产出物

- 一段 2–3 分钟的中文音频
- `docs/demo-script.md`
- 一份彩排记录：每步耗时、遇到的问题、解决办法

### 注意

- 演示**不要放录屏**，现场跑才有说服力
- 但**必须准备一份兜底的录屏**，万一现场环境出问题可以顶上
- 汇报前 1 小时再验证一次环境

---

## 组长（你）

- 汇总四人的数据，出最终对照表
- 维护 `EXPERIMENTS.md`
- 准备 PPT 与讲稿
- Review 并合并 PR，把关质量
- 汇报前一天晚上**冻结代码**，之后任何人不再改动

## 时间线

| 时间 | 谁 | 做什么 |
|---|---|---|
| 第一天 | 全体 | 环境检查（20 分钟内跑通 `run.bat demo.py`） |
| 第一天 | A/B/C/D | 各自的任务，各自提交 PR |
| 第一天晚 | 组长 | 合并 PR，汇总数据 |
| 第二天上午 | 组长 | 填 PPT、写讲稿 |
| 汇报前 1 小时 | D + 全体 | 现场彩排 |
