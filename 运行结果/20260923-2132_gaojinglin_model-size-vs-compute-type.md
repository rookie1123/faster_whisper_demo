# 模型大小 vs 数值档位（高敬琳）

- 时间: 2026-09-23 21:28–21:29
- 音频: `samples/speaker/speaker_fujian.mp3`（约 26 秒）
- 标准答案: `samples/reading_script.txt`
- 解码参数: `beam_size=5, vad_filter=True, device=cpu`
- 说明: CPU 后端不支持 float16，按 TASKS.md 只测 `int8 / int8_float32 / float32` 三档

## 结果

| 模型 | 数值档位 | 规范化 CER | 识别耗时 | 速度倍率 |
| ----- | ------------ | ------- | ---- | ---- |
| tiny  | int8         | 48.3% | 1.1s | 23.1x |
| tiny  | int8_float32 | 48.3% | 1.0s | 26.3x |
| tiny  | float32      | 44.8% | 1.5s | 17.1x |
| small | int8         | 6.9%  | 4.6s | 5.7x  |
| small | int8_float32 | 6.9%  | 4.6s | 5.7x  |
| small | float32      | 6.9%  | 7.7s | 3.4x  |

对应报告：

- tiny: `20260923-212810_speaker_fujian_noprompt.md`（int8）、`20260923-212841_speaker_fujian_noprompt_int8_float32.md`、`20260923-212852_speaker_fujian_noprompt_float32.md`
- small: `20260923-212910_speaker_fujian_noprompt.md`（int8）、`20260923-212926_speaker_fujian_noprompt_int8_float32.md`、`20260923-212951_speaker_fujian_noprompt_float32.md`

## 结论

**应该选"大模型但量化"：`small + int8` 明显优于 `tiny + float32`。**

数字依据：

1. **精度**：`small + int8` 规范化 CER **6.9%**（替换 8、漏字 0、多字 0），
   `tiny + float32` 为 **44.8%**——tiny 即使不量化也错近一半，small 量化后仍有 6.9% 的绝对优势
   （错误率从 44.8% 降到 6.9%，相对下降约 85%）。
2. **量化几乎无损**：small 三种档位 CER 都是 6.9%；`int8` 与 `int8_float32` 耗时相同（4.6s），
   `float32` 反而更慢（7.7s）——CPU 上量化既省内存又更快，不牺牲精度。
3. **速度可接受**：`small + int8` 4.6s vs `tiny + float32` 1.5s，慢约 3 倍，
   但仍比实时快 **5.7 倍**（26 秒音频 4.6 秒跑完），算力有限时这个代价值得。
4. 反证：tiny 的三档之间也印证"模型容量 > 数值档位"——tiny 从 int8 换到 float32 只把 CER
   从 48.3% 降到 44.8%（+3.5 个百分点），远不如换成 small（降到 6.9%）。

**算力有限时优先保证模型容量（small + int8 量化），而不是用小模型保精度（tiny + float32）。**
