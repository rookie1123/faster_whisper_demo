"""转写任意音频/视频文件——不需要标准答案，只想看内容时用这个。

想评测准确率（有标准答案、算字错率）请用 eval_zh.py。

用法:
    python transcribe.py samples/speaker/speaker_fujian.mp3
    python transcribe.py samples/speaker               # 目录里的所有音视频
    python transcribe.py a.mp3 b.m4a --model faster-whisper-tiny
    python transcribe.py samples/speaker --srt         # 顺便输出 .srt 字幕
    python transcribe.py samples/speaker/speaker_fujian.mp3 --confidence-threshold 0.7
        # 给可能识别错的句子加 [?] 前缀，人只需要看这几句
    python transcribe.py samples/speaker --reference samples/reading_script.txt
        # 有标准答案时顺带算出标记的准确率/召回率，看这套标记到底灵不灵
"""

import argparse
import sys
import time
from pathlib import Path

# 解释器自检：系统 PATH 里可能排着别的 Python 版本，一旦用错解释器，
# 报错会是看不懂的 "No module named 'av'"。这里提前拦下来。
if sys.version_info < (3, 9):
    _venv_python = Path(__file__).resolve().parent / ".venv" / "Scripts" / "python.exe"
    sys.exit(
        "[错误] 解释器版本不对：faster-whisper 要求 Python >= 3.9。\n"
        f"       当前解释器：Python {sys.version.split()[0]}  ({sys.executable})\n"
        f"       请改用项目内的虚拟环境：{_venv_python}\n"
        "       或直接运行：run.bat transcribe.py <音频> [--srt]"
    )

try:
    from faster_whisper import WhisperModel
except ImportError as _exc:
    sys.exit(
        f"[错误] 导入 faster_whisper 失败：{_exc}\n"
        f"       当前解释器：{sys.executable}\n"
        "       请用 run.bat 或 faster-whisper 环境运行本脚本。"
    )

PROJECT = Path(__file__).parent

# 标准答案的对齐与对错判定和 tools/confidence_probe.py 共用同一份实现。
# 放在 faster_whisper 检查之后导入：confidence 会连带导入 eval_zh，
# 而 eval_zh 也要用 faster_whisper，先过上面的友好报错更省事。
if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))
from confidence import (  # noqa: E402
    DEFAULT_THRESHOLD,
    fmt_metrics,
    label_words,
    prf,
    sentence_flags,
)

MEDIA_EXT = {
    ".mp3", ".wav", ".m4a", ".flac", ".aac", ".wma", ".ogg", ".opus",
    ".mp4", ".mkv", ".mov", ".avi", ".webm",
}


def srt_time(seconds: float) -> str:
    """把秒数转成 SRT 的时间格式 00:00:01,234"""
    ms = int(round(seconds * 1000))
    h, ms = divmod(ms, 3600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def collect_files(paths):
    """把命令行给的文件/目录展开成待转写的文件列表。"""
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


def suspicious_reason(segment, threshold):
    """判断这一句要不要人工核对，返回 (是否可疑, 最低置信度的词, 该词置信度)。

    用的是逐词置信度 `segment.words[].probability`。

    不要改用 `segment.avg_logprob`：那个数按 30 秒解码窗口算，
    同一窗口里的句子拿到的是同一个值 —— 实测 26.5 秒的音频跑出 9 句，
    9 句的 avg_logprob 全是 -0.223（no_speech_prob 也全是 0.069），
    区分不出哪句有问题。逐词置信度才是逐句可用的信号。
    """
    words = [w for w in (segment.words or []) if w.probability is not None]
    if not words:
        # 拿不到词级信息（例如整段静音），没有依据就不乱标
        return False, None, None
    worst = min(words, key=lambda w: w.probability)
    return worst.probability < threshold, worst.word.strip(), worst.probability


def main():
    parser = argparse.ArgumentParser(
        description="音频/视频转文字",
        epilog=(
            "示例:\n"
            "  python transcribe.py samples/speaker/speaker_fujian.mp3\n"
            "  python transcribe.py samples/speaker/speaker_fujian.mp3 --srt\n"
            "  python transcribe.py samples/speaker --model faster-whisper-small\n"
            "  python transcribe.py samples/speaker/speaker_fujian.mp3 --prompt-name tech\n"
            "  python transcribe.py samples/test1.m4a --models faster-whisper-tiny faster-whisper-small faster-whisper-medium\n"
            "  python transcribe.py samples/speaker/speaker_fujian.mp3 --confidence-threshold 0.7\n"
            "  python transcribe.py samples/speaker --reference samples/reading_script.txt\n"
            "\n"
            "用 run.bat 启动可避免选错解释器:\n"
            "  run.bat transcribe.py <音频> [--models a b c] [--srt] [--confidence-threshold 0.7]"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("paths", nargs="+", help="音频/视频文件或目录")
    parser.add_argument("--model", default=None, help="models 目录下的模型名（默认 faster-whisper-small）")
    parser.add_argument(
        "--models",
        nargs="+",
        default=None,
        help="要对比的多个模型，会依次加载并转写（传了它就忽略 --model）",
    )
    parser.add_argument("--language", default=None, help="zh / en / ja…；不填则自动检测")
    parser.add_argument("--device", default="cpu", help="cpu 或 cuda")
    parser.add_argument("--compute-type", default="int8", help="int8 / float16 / int8_float16")
    parser.add_argument("--prompt", default=None, help="initial_prompt，可放专有名词表")
    parser.add_argument("--prompt-name", default=None, help="prompts.py 里预置的词表名，如 zh / tech")
    parser.add_argument("--srt", action="store_true", help="同时输出 .srt 字幕文件")
    parser.add_argument(
        "--confidence-threshold",
        type=float,
        default=None,
        metavar="P",
        help=(
            "给「需要校对」的句子打标记：句内只要有词的逐词置信度低于 P（0~1），"
            "就给这句加 [?] 前缀，并在结尾统计句数。"
            "在 5 段真人录音上实测，推荐 0.70（召回 0.89 / 准确 0.68）。"
            "默认关闭；打开会额外计算词级时间戳，稍慢一点。"
        ),
    )
    parser.add_argument(
        "--reference",
        default=None,
        metavar="PATH",
        help=(
            "标准答案文本。给了它才能算「[?] 标记的准确率/召回率」——"
            "把识别结果和标准答案逐字对齐，看标出来的句子是不是真错、有没有漏掉。"
            "一批音频必须读的是同一份稿。"
            "不给就只标记、不算指标；给了它却没给 --confidence-threshold 时按 0.70 开标记。"
        ),
    )

    # 不带任何参数时直接给出帮助，而不是抛一句干巴巴的 "arguments are required"
    if len(sys.argv) == 1:
        parser.print_help()
        return

    args = parser.parse_args()

    # 要算「标出的句子里有多少是真错」，前提是先得有标记。
    # 所以给了标准答案却没给阈值时，按实测推荐的 0.70 自动把标记打开。
    if args.reference is not None and args.confidence_threshold is None:
        args.confidence_threshold = DEFAULT_THRESHOLD

    if args.confidence_threshold is not None and not (0.0 < args.confidence_threshold < 1.0):
        print(f"[错误] --confidence-threshold 要给 0 到 1 之间的数（收到 {args.confidence_threshold}）")
        return

    if args.prompt_name:
        from prompts import PROMPTS

        if args.prompt_name not in PROMPTS:
            print(f"[错误] 没有名为 {args.prompt_name} 的词表。可用: {', '.join(PROMPTS)}")
            return
        args.prompt = PROMPTS[args.prompt_name]

    files = collect_files(args.paths)
    if not files:
        print("没有找到可转写的文件")
        return

    # 标准答案：有它才能算标记的准确率/召回率，没有就只标记
    reference = None
    ref_path = None
    if args.reference:
        ref_path = Path(args.reference)
        if not ref_path.is_absolute():
            ref_path = PROJECT / ref_path
        if not ref_path.exists():
            print(f"[错误] 找不到标准答案文件：{ref_path}")
            return
        reference = ref_path.read_text(encoding="utf-8").strip()
        if not reference:
            print(f"[错误] 标准答案文件是空的：{ref_path}")
            return

    # --models 优先；否则用 --model；都没传就默认 small
    model_names = args.models or [args.model or "faster-whisper-small"]
    multi = len(model_names) > 1

    # 要判断"哪句可能错"，就必须拿到逐词置信度
    check_confidence = args.confidence_threshold is not None
    print_threshold = args.confidence_threshold if check_confidence else 0.0

    flagged_total = 0
    sentences_total = 0

    if reference is not None:
        print(
            f"标准答案: {ref_path.name}（{len(reference)} 字）   "
            f"标记阈值 {print_threshold:.2f}\n"
        )

    for name in model_names:
        model_dir = PROJECT / "models" / name
        if not model_dir.exists():
            print(f"模型目录不存在: {model_dir}")
            print("可用的模型: " + ", ".join(sorted(p.name for p in (PROJECT / 'models').iterdir())))
            return

        print(f"模型: {name}   设备: {args.device}   待转写: {len(files)} 个文件\n")
        model = WhisperModel(str(model_dir), device=args.device, compute_type=args.compute_type)
        model_flags = []  # 有标准答案时，攒起各音频的句级判定算合计

        for audio in files:
            started = time.time()
            segments, info = model.transcribe(
                str(audio),
                language=args.language,
                beam_size=5,
                vad_filter=True,
                initial_prompt=args.prompt,
                word_timestamps=check_confidence,
            )
            segs = list(segments)
            elapsed = time.time() - started

            print("=" * 72)
            print(
                f"{audio.name}" + (f"   [{name}]" if multi else "") + "\n"
                f"  语言 {info.language} ({info.language_probability:.2f})   "
                f"时长 {info.duration:.1f}s   耗时 {elapsed:.1f}s   "
                f"倍率 {info.duration / max(elapsed, 1e-6):.1f}x"
            )
            if not segs:
                print("  (没有识别出内容——可能是纯静音)")

            flagged = 0
            flagged_marks = []  # 与 segs 一一对应，给 .srt 用
            for s in segs:
                mark, hint = "", ""
                if check_confidence:
                    suspect, bad_word, bad_prob = suspicious_reason(s, print_threshold)
                    if suspect:
                        flagged += 1
                        mark = "[?] "
                        if bad_word is not None:
                            hint = f"   <- 最低 {bad_prob:.2f} {bad_word!r}"
                flagged_marks.append(mark)
                print(f"  [{s.start:7.2f} -> {s.end:7.2f}] {mark}{s.text.strip()}{hint}")

            if check_confidence and segs:
                print(f"  共 {len(segs)} 句，其中 {flagged} 句需要人工核对")
                flagged_total += flagged
                sentences_total += len(segs)

            if reference is not None and segs:
                # 转成 confidence.py 认得的形状。判定规则和上面打 [?] 的完全同源，
                # 否则会出现"这行没标 [?]、指标却把它算成漏标"的自相矛盾。
                seg_words = [
                    [{"word": w.word, "probability": w.probability} for w in (s.words or [])]
                    for s in segs
                ]
                label_words(seg_words, reference)
                flags = sentence_flags(seg_words, print_threshold)
                model_flags += flags
                m = prf(flags)
                print(
                    f"  与标准答案比对：标出 {m['flagged']} 句，其中 {m['tp']} 句确实有错；"
                    f"另有 {m['fn']} 句有错但没标出"
                )
                print(f"    TP={m['tp']}  FP={m['fp']}  FN={m['fn']}   {fmt_metrics(m)}")

            if args.srt and segs:
                # 多模型对比时给字幕加上模型名，避免三个模型互相覆盖
                srt_path = audio.with_suffix(f".{name}.srt") if multi else audio.with_suffix(".srt")
                lines = []
                for i, s in enumerate(segs, 1):
                    lines += [
                        str(i),
                        f"{srt_time(s.start)} --> {srt_time(s.end)}",
                        flagged_marks[i - 1] + s.text.strip(),
                        "",
                    ]
                srt_path.write_text("\n".join(lines), encoding="utf-8")
                print(f"  字幕已写入 {srt_path.name}")
            print()

        # 多文件时给这个模型的合计指标（单文件在上面已经报过了）
        if reference is not None and model_flags and len(files) > 1:
            total = prf(model_flags)
            prefix = f"[{name}] " if multi else ""
            print(
                f"{prefix}合计：标出 {total['flagged']}/{total['n']} 句，"
                f"其中 {total['tp']} 句确实有错、漏标 {total['fn']} 句   "
                f"{fmt_metrics(total)}"
            )
            print()

    # 转写了多个文件时，再给一个总数，方便一眼看到工作量。
    # 有标准答案时上面那道「合计」已经报过句数了，不重复。
    if check_confidence and sentences_total and len(files) > 1 and reference is None:
        print(f"全部文件合计：共 {sentences_total} 句，其中 {flagged_total} 句需要人工核对")


if __name__ == "__main__":
    main()
