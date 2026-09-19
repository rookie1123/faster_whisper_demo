"""中文识别测试：对比不同模型在同一批音频上的识别效果与速度。

用法:
    python zh_test.py faster-whisper-tiny faster-whisper-small
"""

import sys
import time
from pathlib import Path

from faster_whisper import WhisperModel

PROJECT = Path(__file__).parent

# (音频文件, 是否强制指定中文) —— 合成音频用 zh，真实录音用 None 自动检测
AUDIOS = [
    (PROJECT / "samples" / "zh_female.wav", "zh"),
    (PROJECT / "samples" / "zh_male.wav", "zh"),
]

# 你自己的录屏（用 glob 避免文件名里的特殊字符）
captures = Path(r"C:\Users\30756\Videos\Captures")
if captures.exists():
    AUDIOS += [(p, None) for p in sorted(captures.glob("*.mp4"))[:2]]

model_names = sys.argv[1:] or ["faster-whisper-tiny"]

for name in model_names:
    model_dir = PROJECT / "models" / name
    if not model_dir.exists():
        print(f"[跳过] 模型目录不存在: {model_dir}")
        continue

    print("=" * 72)
    print(f"模型: {name}")
    print("=" * 72)

    t0 = time.time()
    model = WhisperModel(str(model_dir), device="cpu", compute_type="int8")
    print(f"加载耗时 {time.time() - t0:.1f}s\n")

    for audio, lang in AUDIOS:
        if not audio.exists():
            print(f"[跳过] 找不到 {audio}")
            continue

        t0 = time.time()
        segments, info = model.transcribe(
            str(audio),
            language=lang,
            beam_size=5,
            vad_filter=True,
        )
        segs = list(segments)  # segments 是生成器，必须消费完
        elapsed = time.time() - t0

        print("-" * 72)
        print(
            f"{audio.name}\n"
            f"  检测语言: {info.language} (置信度 {info.language_probability:.2f})  "
            f"音频时长: {info.duration:.1f}s  识别耗时: {elapsed:.1f}s  "
            f"速度倍率: {info.duration / max(elapsed, 1e-6):.1f}x"
        )
        if not segs:
            print("  (没有识别出任何内容——可能是纯静音的录音)")
        for s in segs:
            print(f"  [{s.start:7.2f} -> {s.end:7.2f}] {s.text.strip()}")
        print()
