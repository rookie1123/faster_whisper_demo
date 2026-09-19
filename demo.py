import time
from pathlib import Path

from faster_whisper import WhisperModel

# 用 __file__ 定位，不管从哪里启动脚本都能找对路径
PROJECT_DIR = Path(__file__).parent
MODEL_DIR = PROJECT_DIR / "models" / "faster-whisper-tiny"
AUDIO = PROJECT_DIR / "tests" / "data" / "jfk.flac"

t0 = time.time()
model = WhisperModel(str(MODEL_DIR), device="cpu", compute_type="int8")
print(f"model loaded in {time.time() - t0:.1f}s")

segments, info = model.transcribe(str(AUDIO), language="en")
print(info.language, info.duration)
for s in segments:
    print(f"[{s.start:.2f} -> {s.end:.2f}] {s.text}")
