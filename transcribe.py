"""转写任意音频/视频文件——不需要标准答案，只想看内容时用这个。

想评测准确率（有标准答案、算字错率）请用 eval_zh.py。

用法:
    python transcribe.py samples/my_audio.mp3
    python transcribe.py samples                      # 目录里的所有音视频
    python transcribe.py a.mp3 b.m4a --model faster-whisper-tiny
    python transcribe.py samples --srt                # 顺便输出 .srt 字幕
"""

import argparse
import sys
import time
from pathlib import Path

# 解释器自检：本机的系统 PATH 里 D:\python3.6.8 排在 conda 环境前面，
# 一旦用错解释器，报错会是看不懂的 "No module named 'av'"。这里提前拦下来。
if sys.version_info < (3, 9):
    _cmd = " ".join(
        [r"D:\miniconda\envs\faster-whisper\python.exe", sys.argv[0], *sys.argv[1:]]
    )
    sys.exit(
        "[错误] 解释器版本不对：faster-whisper 要求 Python >= 3.9。\n"
        f"       当前解释器：Python {sys.version.split()[0]}  ({sys.executable})\n"
        f"       请改用：{_cmd}\n"
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


def main():
    parser = argparse.ArgumentParser(
        description="音频/视频转文字",
        epilog=(
            "示例:\n"
            "  python transcribe.py samples/zh_tts_1.wav\n"
            "  python transcribe.py samples/zh_tts_1.wav --srt\n"
            "  python transcribe.py samples --model faster-whisper-small\n"
            "  python transcribe.py samples/zh_tts_1.wav --prompt-name tech\n"
            "  python transcribe.py samples/test1.m4a --models faster-whisper-tiny faster-whisper-small faster-whisper-medium\n"
            "\n"
            "用 run.bat 启动可避免选错解释器:\n"
            "  run.bat transcribe.py <音频> [--models a b c] [--srt]"
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

    # 不带任何参数时直接给出帮助，而不是抛一句干巴巴的 "arguments are required"
    if len(sys.argv) == 1:
        parser.print_help()
        return

    args = parser.parse_args()

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

    # --models 优先；否则用 --model；都没传就默认 small
    model_names = args.models or [args.model or "faster-whisper-small"]
    multi = len(model_names) > 1

    for name in model_names:
        model_dir = PROJECT / "models" / name
        if not model_dir.exists():
            print(f"模型目录不存在: {model_dir}")
            print("可用的模型: " + ", ".join(sorted(p.name for p in (PROJECT / 'models').iterdir())))
            return

        print(f"模型: {name}   设备: {args.device}   待转写: {len(files)} 个文件\n")
        model = WhisperModel(str(model_dir), device=args.device, compute_type=args.compute_type)

        for audio in files:
            started = time.time()
            segments, info = model.transcribe(
                str(audio),
                language=args.language,
                beam_size=5,
                vad_filter=True,
                initial_prompt=args.prompt,
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
            for s in segs:
                print(f"  [{s.start:7.2f} -> {s.end:7.2f}] {s.text.strip()}")

            if args.srt and segs:
                # 多模型对比时给字幕加上模型名，避免三个模型互相覆盖
                srt_path = audio.with_suffix(f".{name}.srt") if multi else audio.with_suffix(".srt")
                lines = []
                for i, s in enumerate(segs, 1):
                    lines += [str(i), f"{srt_time(s.start)} --> {srt_time(s.end)}", s.text.strip(), ""]
                srt_path.write_text("\n".join(lines), encoding="utf-8")
                print(f"  字幕已写入 {srt_path.name}")
            print()


if __name__ == "__main__":
    main()
