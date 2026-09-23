# 词表对比汇总

数字取自各次评测报告中 `faster-whisper-small` 的「规范化 CER」（越低越好）。

| 说话人 | 不加词表 | tech 词表 | ml 词表 |
|--------|----------|-----------|---------|
| fujian | 5.2% | 6.0% | 1.7% |
| daiyipeng | 7.8% | 6.0% | 5.2% |
| huangsiyang | 9.5% | 7.8% | 5.2% |
| gaojinglin | 7.8% | 7.8% | 3.4% |
| wenglekang | 10.3% | 8.6% | 4.3% |

## 对应报告

| 说话人 | 不加词表 | tech | ml |
|--------|----------|------|-----|
| fujian | `20260923-210954_speaker_fujian_noprompt.md` | `20260923-211007_speaker_fujian_prompt-tech.md` | `20260923-211018_speaker_fujian_prompt-ml.md` |
| daiyipeng | `20260923-211026_speaker_daiyipeng_noprompt.md` | `20260923-211036_speaker_daiyipeng_prompt-tech.md` | `20260923-211047_speaker_daiyipeng_prompt-ml.md` |
| huangsiyang | `20260923-211058_speaker_huangsiyang_noprompt.md` | `20260923-211110_speaker_huangsiyang_prompt-tech.md` | `20260923-211123_speaker_huangsiyang_prompt-ml.md` |
| gaojinglin | `20260923-211134_speaker_gaojinglin_noprompt.md` | `20260923-211146_speaker_gaojinglin_prompt-tech.md` | `20260923-211159_speaker_gaojinglin_prompt-ml.md` |
| wenglekang | `20260923-211210_speaker_wenglekang_noprompt.md` | `20260923-211223_speaker_wenglekang_prompt-tech.md` | `20260923-211236_speaker_wenglekang_prompt-ml.md` |

## 结论

词表有用。`ml` 词表更有用（五人都明显下降）；`tech` 多数略好，但提升不如 `ml`，且 fujian 上甚至略差。朗读稿偏机器学习场景，所以 `ml` 更对口。
