"""把识别结果和标准答案对齐，判断哪些词、哪些句子是真的错了。

给谁用：
    transcribe.py                 给 `--reference` 算「[?] 标记的准确率/召回率」
    tools/confidence_probe.py     给逐词置信度打对错标签、扫阈值

两边共用同一套归一化与对齐规则，口径和 eval_zh.py 的 CER 完全一致 ——
否则会出现「CER 说这句错了，标记却说它干净」这种自相矛盾的结论。

判定规则：
    - 两侧都先过 normalize + normalize_numbers，所以「百分之四十」和「40%」
      这种纯写法差异不算错。
    - 落在「替换 / 多字」上的字判错。
    - 「漏字」在识别侧没有对应的字。如果不管它，有漏字的句子会被误判成干净句，
      所以把这个错记在紧邻的那个词头上（错就丢在它身上）。
    - 一个词只要有任何一个字判错，整个词判错 —— 宁可多标，不漏标。
"""

from eval_zh import align, normalize, normalize_numbers

# 在 5 段真人录音上做留一说话人交叉验证选出来的工作点。
# 详见 docs/confidence-flagging.md。
DEFAULT_THRESHOLD = 0.70


def _flatten(text):
    """按「字」摊平，去掉标点、空白和数字写法差异。"""
    return normalize_numbers(normalize(text)).replace("\x00", "")


def label_words(segment_words, reference):
    """给每个词标上 correct：True 对 / False 错 / None 不参与判定。

    segment_words: 按句分组的词列表，形如 [[{"word": "上周", ...}, ...], ...]。
                   就地在每个词的 dict 里写入 "has_ref" 和 "correct"。
    reference:     标准答案原文。

    返回 (ref_norm, hyp_norm)——两侧摊平后的字串，便于排查对齐结果。
    """
    ref_norm = _flatten(reference)

    flat = []  # [(字, 句下标, 词下标)]
    for si, words in enumerate(segment_words):
        for wi, w in enumerate(words):
            for ch in _flatten(w["word"]):
                flat.append((ch, si, wi))
    hyp_norm = "".join(ch for ch, _, _ in flat)

    _, ops = align(ref_norm, hyp_norm)

    labels = {}  # (句下标, 词下标) -> [每个字的对错]
    j = 0
    for tag, _r, _h in ops:
        if tag in ("ok", "替换", "多字"):
            _, si, wi = flat[j]
            labels.setdefault((si, wi), []).append(tag == "ok")
            j += 1
        elif j < len(flat):
            # "漏字"：识别侧少了一个字，它不落在任何词上。
            # 把这个错记到紧跟其后的那个词头上，避免含漏字的句子被判成干净句。
            _, si, wi = flat[j]
            labels.setdefault((si, wi), []).append(False)
        elif flat:
            # 漏字发生在末尾，归到最后一个词
            _, si, wi = flat[-1]
            labels.setdefault((si, wi), []).append(False)

    for si, words in enumerate(segment_words):
        for wi, w in enumerate(words):
            marks = labels.get((si, wi), [])
            # 纯标点/纯空白会被 normalize 掉，marks 为空 —— 不参与对错判定
            w["has_ref"] = bool(marks)
            w["correct"] = all(marks) if marks else None

    return ref_norm, hyp_norm


def sentence_flags(segment_words, threshold):
    """算出每句的「被标记」和「真有错」，用来做混淆矩阵。

    标记规则必须和 transcribe.py 的 suspicious_reason 完全一致：
    句内有任一词的逐词置信度低于 threshold，整句就打 [?]。

    注意不要改用 segment.avg_logprob —— 那个值按 30 秒解码窗口算，
    同一窗口里的句子拿到的是同一个数，区分不出哪句有问题。

    返回 [(被标记, 真有错), ...]，与 segment_words 一一对应。
    """
    flags = []
    for words in segment_words:
        probs = [w["probability"] for w in words if w.get("probability") is not None]
        flagged = any(p < threshold for p in probs)
        has_error = any(w.get("correct") is False for w in words)
        flags.append((flagged, has_error))
    return flags


def prf(flags):
    """(被标记, 真有错) 的列表 -> TP/FP/FN/TN 与准确率、召回率、F1。

    这里说的「准确率」是 precision：标出来的句子里，真有错的占多少 ——
    也就是「人工复核的命中率」。在一份全是正确识别的音频上，TP+FP 为 0，
    此时准确率无意义，返回 nan，展示时写成 "-"。
    """
    tp = sum(1 for f, e in flags if f and e)
    fp = sum(1 for f, e in flags if f and not e)
    fn = sum(1 for f, e in flags if not f and e)
    tn = sum(1 for f, e in flags if not f and not e)

    precision = tp / (tp + fp) if tp + fp else float("nan")
    recall = tp / (tp + fn) if tp + fn else float("nan")
    f1 = 2 * precision * recall / (precision + recall) if (tp + fp) and (tp + fn) else 0.0

    return {
        "tp": tp, "fp": fp, "fn": fn, "tn": tn,
        "precision": precision, "recall": recall, "f1": f1,
        "n": len(flags), "flagged": tp + fp, "truth": tp + fn,
    }


def fmt_metrics(m):
    """"准确率 0.86  召回率 0.86" 这样的一段文本；分母为 0 时写 "-"。"""

    def ratio(value, denom):
        return f"{value:.2f}" if denom else "-"

    return (
        f"准确率 {ratio(m['precision'], m['tp'] + m['fp'])}   "
        f"召回率 {ratio(m['recall'], m['tp'] + m['fn'])}   "
        f"F1 {m['f1']:.3f}"
    )
