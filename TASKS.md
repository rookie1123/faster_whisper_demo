# 任务表

五个人，一人一件事，做完各交一个 PR。

---

## 一、先做这四件事

**1. 拉最新代码**（仓库结构刚调整过，不拉的话路径全是错的）

```
git checkout main
git pull
```

**2. 开自己的分支**

```
git checkout -b exp/你的任务名
```

**3. 干完推上去，然后开 PR**

```
git add -A
git status                    # 看一眼有没有加进不该加的文件
git commit -m "说清楚你做了什么"
git push -u origin exp/你的任务名
```

推完打开仓库网页，点 **Compare & pull request** → 再点 **Create pull request**。
**必须点两次**，只点第一次的话 PR 没建成，别人收不到通知。

**4. 不要提交 `eval_report.md`**

那是本地临时文件，每次运行都会被覆盖。

---

## 二、环境（跑不通才看这一段）

```powershell
uv venv .venv --python 3.12 --seed
.\.venv\Scripts\python.exe -m pip install -e . -i https://pypi.tuna.tsinghua.edu.cn/simple
.\.venv\Scripts\python.exe download_model.py small
run.bat demo.py
```

最后一步能识别出英文句子，就说明环境好了。

**注意事项：**

- Python 必须用 3.12，别用系统默认的 3.14
- 模型下载走的是 hf-mirror，直连 huggingface.co 会超时
- 所有命令都用 `run.bat` 开头（如 `run.bat eval_zh.py ...`），它会自动用项目里的 `.venv`

**卡住了就问 AI**：把**完整的报错**复制给 Codex 或 ChatGPT，它会告诉你怎么修。
只说"跑不起来"没用，要把红字给全。

---

## 三、怎么让 AI 帮你干活

你可以直接把下面这段发给 Codex（或 ChatGPT），它就能接着往下做：

```
我在复现 faster-whisper，项目在当前目录。
请先读 TASKS.md 里「成员 A」那一节（换成你自己的编号），
再读一遍当前目录结构，然后一步步帮我把任务做完。
每跑完一步告诉我结果，最后把表格整理好给我。
```

**用 AI 可以，但有三条底线：**

1. **命令要在你自己的电脑上跑**——结果得是你自己跑出来的
2. **数字要自己看懂**——知道每个数字是什么、从哪来，老师会随机提问
3. **提交前自己过一遍**——`git status` 看一眼加了什么，别把临时文件传上去

---

## 四、五个人的任务

### 成员 A：词表对比

**干什么**：五段录音，每段跑三次（不加词表 / 加 `tech` 词表 / 加 `ml` 词表），看词表有没有用。

**怎么做**——以 fujian 为例，跑三条命令：

```powershell
run.bat eval_zh.py samples\speaker\speaker_fujian.mp3 samples\reading_script.txt
run.bat eval_zh.py samples\speaker\speaker_fujian.mp3 samples\reading_script.txt --prompt-name tech
run.bat eval_zh.py samples\speaker\speaker_fujian.mp3 samples\reading_script.txt --prompt-name ml
```

把 `speaker_fujian.mp3` 换成另外四个文件名，再跑一遍（一共 15 次）。

**交什么**：

1. `reports/` 里会自动生成 15 份报告
2. 一张表（数字从报告的"规范化后"那一列抄）：

| 说话人 | 不加词表 | tech 词表 | ml 词表 |
|---|---|---|---|
| fujian | | | |
| daiyipeng | | | |
| huangsiyang | | | |
| gaojinglin | | | |
| wenglekang | | | |

3. 一句结论：词表有用吗？哪种词表更有用？

---

### 成员 B：模型大小 vs 数值档位

**干什么**：回答一个问题——算力有限时，应该"用小模型但保精度"，还是"用大模型但量化"？

**先说一件事：CPU 上跑不了 float16**，会直接报错。可用的只有 `int8`、`int8_float32`、`float32` 三档。

**怎么做**——同一段音频，跑六个组合：

```powershell
run.bat eval_zh.py samples\speaker\speaker_fujian.mp3 samples\reading_script.txt --models faster-whisper-tiny --compute-type int8
run.bat eval_zh.py samples\speaker\speaker_fujian.mp3 samples\reading_script.txt --models faster-whisper-tiny --compute-type int8_float32
run.bat eval_zh.py samples\speaker\speaker_fujian.mp3 samples\reading_script.txt --models faster-whisper-tiny --compute-type float32
run.bat eval_zh.py samples\speaker\speaker_fujian.mp3 samples\reading_script.txt --models faster-whisper-small --compute-type int8
run.bat eval_zh.py samples\speaker\speaker_fujian.mp3 samples\reading_script.txt --models faster-whisper-small --compute-type int8_float32
run.bat eval_zh.py samples\speaker\speaker_fujian.mp3 samples\reading_script.txt --models faster-whisper-small --compute-type float32
```

**交什么**：

1. 6 份报告
2. 一张表：

| 模型 | 数值档位 | 规范化 CER | 识别耗时 | 速度倍率 |
|---|---|---|---|---|
| tiny | int8 | | | |
| tiny | int8_float32 | | | |
| tiny | float32 | | | |
| small | int8 | | | |
| small | int8_float32 | | | |
| small | float32 | | | |

3. 一句结论：**"tiny + float32" 和 "small + int8" 哪个更好？** 用数字说明。

---

### 成员 C：给转写工具加"需要校对"标记

**干什么**：现在的转写结果是一整段文字，用户不知道哪儿可能错，只能通读校对。加上标记之后，人只需要看标出来的那几句。

**先说一个坑，别走错路**：

`segment.avg_logprob` 这个字段**不能用**。它其实是按 30 秒解码窗口算的，
同一窗口里所有句子数值完全一样（26 秒的音频跑出来全是 -0.222），
区分不出哪句有问题。

**真正能用的是逐词置信度**，加 `word_timestamps=True` 就能拿到：

```powershell
run.bat -c "from faster_whisper import WhisperModel; m=WhisperModel('models/faster-whisper-small',device='cpu',compute_type='int8'); segs,info=m.transcribe('samples/speaker/speaker_fujian.mp3',language='zh',vad_filter=True,word_timestamps=True); [print(round(w.probability,3), w.word) for s in segs for w in (s.words or [])]"
```

**怎么判断这个信号靠不靠谱**：拿 `samples/speaker/speaker_fujian.mp3` 试，
对照 `samples/reading_script.txt` 看哪些词是错的。已知 reference 里
「训练日志」会被识别成「训练日子」、「TensorRT」会被识别成「Tonser RT」，
看这些错词的置信度落在什么区间、对的词又落在什么区间。

**具体步骤**：

1. 跑上面那条命令，把每个字的置信度列出来
2. 对照标准答案标出哪些是错的，**选出能分开"对"和"错"的阈值**（要有数据依据，别拍脑袋）
3. 给 `transcribe.py` 加参数：句子里只要有一个词的置信度低于阈值，就给这句加 `[?]` 前缀
4. 结尾打印"共 N 句，其中 M 句需要人工核对"
5. **验证效果**：数一下被标出来的句子里有多少真的包含错误（准确率），
   以及实际出错的句子有多少被标出来（召回率）

**交什么**：

1. `transcribe.py` 的新参数（在 `--help` 里能看到）
2. 一份验证记录：阈值定在多少、为什么这么定、准确率和召回率各是多少

---

### 成员 D：长音频 + 演示脚本 + 彩排

**干什么**：现场有 4 分钟演示，现在只有 30 秒的素材，撑不起来。你负责把演示准备好。

**怎么做**：

1. 录一段 **2 到 3 分钟**的中文音频（自己念技术类文字就行，含数字和英文词）
   放到 `samples/demo/`，**不要用有版权的素材**（仓库是公开的）
2. 跑一遍长音频转写，确认能出字幕：

```powershell
run.bat transcribe.py samples\demo\你的音频.m4a --model faster-whisper-small --srt
```

3. 写 `docs/demo-script.md`：现场要跑哪几条命令、每条大概多久、**如果报错了怎么救场**
4. **完整彩排一次，记录每步实际耗时**（4 分钟要塞得下）
5. **把网络关掉再跑一遍**——现场的网络你控制不了

**交什么**：

1. 2-3 分钟的音频
2. `docs/demo-script.md`
3. 彩排记录：每步耗时、遇到的问题、怎么解决的

---

### 组长

- 把四个人的数据汇总成最终表格
- 维护 `EXPERIMENTS.md`
- 做 PPT 和讲稿
- 审核并合并 PR
- 汇报前一天晚上**冻结代码**，之后谁都不再改

---

## 五、PR 里必须有这三样

1. **做了什么**——一句话
2. **怎么验证的**——命令 + 数字
3. **结论**——要有具体数字，不能只写"效果变好了"

**只写"加了词表之后效果提升"的 PR 会被打回去**，必须写成"从 10.4% 降到 2.1%"这种能核对的。
