"""转写任意音频/视频文件——不需要标准答案，只想看内容时用这个。

想评测准确率（有标准答案、算字错率）请用 eval_zh.py。

用法:
    python transcribe.py samples/my_audio.mp3
    python transcribe.py samples                      # 目录里的所有音视频
    python transcribe.py a.mp3 b.m4a --model faster-whisper-tiny
    python transcribe.py samples --srt                # 顺便输出 .srt 字幕
"""

import argparse
import time
from pathlib import Path

from faster_whisper import WhisperModel

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
    parser = argparse.ArgumentParser(description="音频/视频转文字")
    parser.add_argument("paths", nargs="+", help="音频/视频文件或目录")
    parser.add_argument("--model", default="faster-whisper-small", help="models 目录下的模型名")
    parser.add_argument("--language", default=None, help="zh / en / ja…；不填则自动检测")
    parser.add_argument("--device", default="cpu", help="cpu 或 cuda")
    parser.add_argument("--compute-type", default="int8", help="int8 / float16 / int8_float16")
    parser.add_argument("--prompt", default=None, help="initial_prompt，可放专有名词表")
    parser.add_argument("--srt", action="store_true", help="同时输出 .srt 字幕文件")
    args = parser.parse_args()

    files = collect_files(args.paths)
    if not files:
        print("没有找到可转写的文件")
        return

    model_dir = PROJECT / "models" / args.model
    if not model_dir.exists():
        print(f"模型目录不存在: {model_dir}")
        print("可用的模型: " + ", ".join(sorted(p.name for p in (PROJECT / 'models').iterdir())))
        return

    print(f"模型: {args.model}   设备: {args.device}   待转写: {len(files)} 个文件\n")
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
            f"{audio.name}\n"
            f"  语言 {info.language} ({info.language_probability:.2f})   "
            f"时长 {info.duration:.1f}s   耗时 {elapsed:.1f}s   "
            f"倍率 {info.duration / max(elapsed, 1e-6):.1f}x"
        )
        if not segs:
            print("  (没有识别出内容——可能是纯静音)")
        for s in segs:
            print(f"  [{s.start:7.2f} -> {s.end:7.2f}] {s.text.strip()}")

        if args.srt and segs:
            srt_path = audio.with_suffix(".srt")
            lines = []
            for i, s in enumerate(segs, 1):
                lines += [str(i), f"{srt_time(s.start)} --> {srt_time(s.end)}", s.text.strip(), ""]
            srt_path.write_text("\n".join(lines), encoding="utf-8")
            print(f"  字幕已写入 {srt_path.name}")
        print()


if __name__ == "__main__":
    main()
