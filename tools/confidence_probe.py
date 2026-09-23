"""探针：用标准答案给逐词置信度打标签，找出能分开「对」和「错」的阈值。

为什么要这个脚本：
    transcribe.py 的 `--confidence-threshold` 依赖一个阈值，
    阈值不能拍脑袋定，必须由数据推出来。这个脚本就是用来导出那个数的。

做法：
    1. 用 word_timestamps=True 拿到每个词的 probability；
    2. 把识别结果和标准答案做逐字编辑距离对齐，标出哪些词含错字
       （对齐与判定逻辑在 confidence.py，和 transcribe.py 的 --reference 共用）；
    3. 统计对/错词的置信度分布，扫一遍候选阈值，算句级与词级的准确率/召回率。

和 transcribe.py 的 --reference 怎么分工：
    想「选一个阈值」——扫全区间、留一说话人交叉验证——用本脚本；
    想「看手上这段音频标得准不准」——直接对一段音频给个准确率/召回率——用 --reference。

用法:
    run.bat tools/confidence_probe.py samples/reading_script.txt samples/speaker/speaker_fujian.mp3
    run.bat tools/confidence_probe.py samples/reading_script.txt samples/speaker/*.mp3 --dump
    run.bat tools/confidence_probe.py samples/reading_script.txt samples/speaker --model faster-whisper-small
"""

import argparse
import sys
import time
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT))

# 对齐与对错判定都在根目录的 confidence.py 里，和 transcribe.py 的 --reference
# 共用同一份实现 —— 口径必须一致，否则会出现「探针说该标，标记却没标」的矛盾。
from confidence import label_words as label_words_of  # noqa: E402

try:
    from faster_whisper import WhisperModel
except ImportError as _exc:  # pragma: no cover
    sys.exit(
        f"[错误] 导入 faster_whisper 失败：{_exc}\n"
        f"       当前解释器：{sys.executable}\n"
        "       请用 run.bat 或 faster-whisper 环境运行本脚本。"
    )

MEDIA_EXT = {".mp3", ".wav", ".m4a", ".flac", ".aac", ".wma", ".ogg", ".opus"}


def collect_files(paths):
    files = []
    for raw in paths:
        p = Path(raw)
        if not p.is_absolute():
            p = PROJECT / p
        if p.is_dir():
            files += sorted(f for f in p.rglob("*") if f.suffix.lower() in MEDIA_EXT)
        elif p.exists():
            files.append(p)
        else:
            print(f"[跳过] 找不到 {p}")
    return files


def run_model(model, audio):
    """返回 (segments, info)；segments 是 dict 列表，词级信息保留 probability。"""
    raw_segments, info = model.transcribe(
        str(audio),
        language="zh",
        beam_size=5,
        vad_filter=True,
        word_timestamps=True,
    )
    segments = []
    for s in raw_segments:
        words = [
            {"word": w.word, "prob": float(w.probability), "start": w.start, "end": w.end}
            for w in (s.words or [])
        ]
        segments.append(
            {"text": s.text.strip(), "start": s.start, "end": s.end, "words": words}
        )
    return segments, info


def label_words(segments, reference):
    """把每个词标成 True(对) / False(错)。

    判定逻辑在根目录 confidence.py 里（与 transcribe.py 的 --reference 共用一份），
    这里只负责把探针自己的 segments 结构拆成按句分组的词列表喂进去。
    """
    return label_words_of([s["words"] for s in segments], reference)


def sweep(records, thresholds):
    """在给定阈值上算句级 / 词级的准确率与召回率。

    records: [(prob, correct, seg_key)]，correct 为 None 表示不参与判定。
    句级：句内只要有词被标 -> 该句被标；句内有任一词判错 -> 该句算"真有错"。
    """
    rows = []
    for t in thresholds:
        # ---- 词级 ----
        tp = fp = fn = 0
        for prob, correct, _ in records:
            if correct is None:
                continue
            flagged = prob < t
            if flagged and not correct:
                tp += 1
            elif flagged and correct:
                fp += 1
            elif not flagged and not correct:
                fn += 1
        wp = tp / (tp + fp) if tp + fp else float("nan")
        wr = tp / (tp + fn) if tp + fn else float("nan")
        # F1 的分母是 wp+wr。tp 为 0 时 wp、wr 也全是 0，直接算会除零 ——
        # 短音频（词数少）在扫描中间阈值时很容易撞上，所以按 tp 判断。
        wf = 2 * wp * wr / (wp + wr) if tp else 0.0

        # ---- 句级 ----
        by_seg = {}
        for prob, correct, key in records:
            if correct is None:
                continue
            d = by_seg.setdefault(key, {"flag": False, "err": False})
            d["flag"] = d["flag"] or prob < t
            d["err"] = d["err"] or (not correct)
        stp = sum(1 for d in by_seg.values() if d["flag"] and d["err"])
        sfp = sum(1 for d in by_seg.values() if d["flag"] and not d["err"])
        sfn = sum(1 for d in by_seg.values() if not d["flag"] and d["err"])
        sp = stp / (stp + sfp) if stp + sfp else float("nan")
        sr = stp / (stp + sfn) if stp + sfn else float("nan")
        # 同词级：stp 为 0 时 sp、sr 都是 0，会除零
        sf = 2 * sp * sr / (sp + sr) if stp else 0.0

        rows.append(
            {"t": t, "tp": tp, "fp": fp, "fn": fn, "wp": wp, "wr": wr, "wf": wf,
             "stp": stp, "sfp": sfp, "sfn": sfn, "sp": sp, "sr": sr, "sf": sf,
             "n_seg": len(by_seg)}
        )
    return rows


def loocv(records, thresholds):
    """留一说话人交叉验证：在一个说话人以外的数据上选阈值，再拿到这个人身上评。

    直接在同批数据上挑 F1 最高的阈值，有"自己出题自己答"的嫌疑。
    这里按音频分组，每次留出一个音频不参与选阈值，看选出的阈值在新人身上还灵不灵。
    """
    groups = sorted({key[0] for _, _, key in records})
    folds = []
    for g in groups:
        train = [r for r in records if r[2][0] != g]
        test = [r for r in records if r[2][0] == g]
        if not train or not test:
            continue
        best_t = max(thresholds, key=lambda t: sweep(train, [t])[0]["sf"])
        row = sweep(test, [best_t])[0]
        folds.append((g, best_t, row))

    tp = sum(r["stp"] for _, _, r in folds)
    fp = sum(r["sfp"] for _, _, r in folds)
    fn = sum(r["sfn"] for _, _, r in folds)
    p = tp / (tp + fp) if tp + fp else float("nan")
    rc = tp / (tp + fn) if tp + fn else float("nan")
    return folds, tp, fp, fn, p, rc


def main():
    ap = argparse.ArgumentParser(description="逐词置信度阈值探针")
    ap.add_argument("reference", help="标准答案文本")
    ap.add_argument("paths", nargs="+", help="音频文件或目录")
    ap.add_argument("--model", default="faster-whisper-small", help="models 下的模型名")
    ap.add_argument("--compute-type", default="int8")
    ap.add_argument("--device", default="cpu")
    ap.add_argument("--dump", action="store_true", help="逐词打印置信度与对错判定")
    ap.add_argument("--json", default=None, help="把逐词原始数据另存为 JSON，便于离线分析")
    ap.add_argument("--step", type=float, default=0.02, help="阈值扫描步长")
    args = ap.parse_args()

    ref_path = Path(args.reference)
    if not ref_path.is_absolute():
        ref_path = PROJECT / ref_path
    reference = ref_path.read_text(encoding="utf-8").strip()

    files = collect_files(args.paths)
    if not files:
        print("没有找到音频")
        return

    model_dir = PROJECT / "models" / args.model
    if not model_dir.exists():
        print(f"模型目录不存在: {model_dir}")
        return
    model = WhisperModel(str(model_dir), device=args.device, compute_type=args.compute_type)

    records = []  # (prob, correct, (audio名, seg 序号))
    raw = []      # 逐词原始数据，给 --json 用
    seg_meta = {}  # (audio名, seg 序号) -> {"text":.., "min":..}
    per_audio = []
    for audio in files:
        t0 = time.time()
        segments, info = run_model(model, audio)
        elapsed = time.time() - t0
        ref_norm, hyp_norm = label_words(segments, reference)

        n_err_seg = n_flagged_words = n_words = n_err_words = 0
        for si, s in enumerate(segments):
            probs = [w["prob"] for w in s["words"] if w["correct"] is not None]
            seg_meta[(audio.name, si)] = {
                "text": s["text"],
                "min": min(probs) if probs else 1.0,
                "err": any((w["correct"] is False) for w in s["words"]),
            }
            if any((w["correct"] is False) for w in s["words"]):
                n_err_seg += 1
            for w in s["words"]:
                if w["correct"] is None:
                    continue
                n_words += 1
                if not w["correct"]:
                    n_err_words += 1
                records.append((w["prob"], w["correct"], (audio.name, si)))
                raw.append({
                    "audio": audio.name, "seg": si, "seg_text": s["text"],
                    "word": w["word"], "prob": round(w["prob"], 6),
                    "correct": w["correct"], "start": round(w["start"], 3),
                })

        per_audio.append(
            {"name": audio.name, "segments": segments, "info": info, "elapsed": elapsed,
             "n_seg": len(segments), "n_err_seg": n_err_seg,
             "n_words": n_words, "n_err_words": n_err_words,
             "hyp_norm": hyp_norm}
        )

        print("=" * 78)
        print(
            f"{audio.name}   时长 {info.duration:.1f}s  识别 {elapsed:.1f}s  "
            f"({info.duration / max(elapsed, 1e-6):.1f}x)"
        )
        print(
            f"  句数 {len(segments)}（其中 {n_err_seg} 句含错字）   "
            f"词数 {n_words}（其中 {n_err_words} 个词含错字）"
        )
        if args.dump:
            for si, s in enumerate(segments):
                print(f"  [{s['start']:6.2f} -> {s['end']:6.2f}] {s['text']}")
                for w in s["words"]:
                    mark = {True: "对", False: "错", None: "--"}[w["correct"]]
                    print(f"        {w['prob']:.3f}  {mark}  {w['word']!r}")
        print()

    if not records:
        print("没有可用的词级数据")
        return

    if args.json:
        import json

        out = Path(args.json)
        if not out.is_absolute():
            out = PROJECT / out
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(
            json.dumps({"reference": reference, "words": raw}, ensure_ascii=False, indent=1),
            encoding="utf-8",
        )
        print(f"逐词原始数据已写入 {out}\n")

    # ---------------- 分布 ----------------
    good = sorted(p for p, c, _ in records if c)
    bad = sorted(p for p, c, _ in records if not c)
    print("=" * 78)
    print(f"总计 {len(records)} 个词：对的 {len(good)} 个，错的 {len(bad)} 个")
    for name, arr in (("对的词", good), ("错的词", bad)):
        if not arr:
            print(f"  {name}: 无")
            continue
        def pct(q):
            return arr[min(len(arr) - 1, int(q * (len(arr) - 1)))]
        print(
            f"  {name}: min={arr[0]:.3f}  p25={pct(0.25):.3f}  中位={pct(0.5):.3f}  "
            f"p75={pct(0.75):.3f}  max={arr[-1]:.3f}"
        )

    # ---------------- 阈值扫描 ----------------
    thresholds = []
    t = args.step
    while t < 1.0:
        thresholds.append(round(t, 4))
        t += args.step
    rows = sweep(records, thresholds)

    print("\n--- 阈值扫描（句级）---")
    print("  阈值   标出句  真含错且标出  误标  漏标   准确率  召回率   F1")
    for r in rows:
        print(
            "  %.2f   %5d   %11d  %4d  %4d   %6s  %6s  %5.3f"
            % (
                r["t"], r["stp"] + r["sfp"], r["stp"], r["sfp"], r["sfn"],
                "%.2f" % r["sp"] if r["stp"] + r["sfp"] else "  -  ",
                "%.2f" % r["sr"] if r["stp"] + r["sfn"] else "  -  ",
                r["sf"],
            )
        )

    best = max(rows, key=lambda r: (r["sf"], r["wf"]))
    print(
        "\n句级 F1 最高的阈值 = %.2f  "
        "（准确率 %.2f，召回率 %.2f，标出 %d 句，漏标 %d 句）"
        % (best["t"], best["sp"], best["sr"], best["stp"] + best["sfp"], best["sfn"])
    )
    best_w = max(rows, key=lambda r: r["wf"])
    print(
        "词级 F1 最高的阈值 = %.2f  （准确率 %.2f，召回率 %.2f）"
        % (best_w["t"], best_w["wp"], best_w["wr"])
    )

    # ---------------- 留一说话人交叉验证 ----------------
    print("\n--- 留一说话人交叉验证（阈值在其余音频上选，在留出的那位身上评）---")
    folds, tp, fp, fn, p, rc = loocv(records, thresholds)
    if not folds:
        # 只有一段音频时留不出训练集。这不是错误，直接说明比打一张空表好。
        print("  至少要 2 段音频才谈得上「留一」，当前只有 1 段，跳过。")
        print("  单段音频看上面的阈值扫描就够了；要选阈值请把同一份稿的多段录音一起传进来。")
    else:
        print("  留出音频                    选出阈值  标出  真含错且标出  误标  漏标  准确率  召回率")
        for g, t, r in folds:
            print("  %-26s %.2f   %4d   %11d  %4d  %4d  %s  %s"
                  % (g[:26], t, r["stp"] + r["sfp"], r["stp"], r["sfp"], r["sfn"],
                     "%.2f" % r["sp"] if r["stp"] + r["sfp"] else "  -  ",
                     "%.2f" % r["sr"] if r["stp"] + r["sfn"] else "  -  "))
        print(
            "  合计: TP=%d FP=%d FN=%d  ->  准确率 %.2f，召回率 %.2f"
            % (tp, fp, fn, p, rc)
        )

    # ---------------- 推荐工作点 ----------------
    print("\n--- 推荐工作点 ---")
    print("  阈值  标出句/总句  准确率  召回率   F1    （准确率=标出的句子里真有错的占比）")
    for r in rows:
        if round(r["t"] * 100) in (60, 64, 66, 68, 70, 72, 76, 80, 84):
            print("  %.2f     %2d/%-2d     %s   %s   %.3f"
                  % (r["t"], r["stp"] + r["sfp"], r["n_seg"],
                     "%.2f" % r["sp"] if r["stp"] + r["sfp"] else " -  ",
                     "%.2f" % r["sr"] if r["stp"] + r["sfn"] else " -  ",
                     r["sf"]))

    # ---------------- 失败样例 ----------------
    print("\n--- 推荐阈值 %.2f 下的误报与漏报 ---" % best["t"])
    print("[误报] 被标出但其实没错（占用了人工复核时间）：")
    for k, m in sorted(seg_meta.items()):
        if m["min"] < best["t"] and not m["err"]:
            print("   %-24s min=%.3f  %s" % (k[0][:24], m["min"], m["text"][:44]))
    print("[漏报] 有错但没被标出（更危险）：")
    for k, m in sorted(seg_meta.items()):
        if m["min"] >= best["t"] and m["err"]:
            print("   %-24s min=%.3f  %s" % (k[0][:24], m["min"], m["text"][:44]))


if __name__ == "__main__":
    main()
