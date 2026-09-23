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
        "       或直接运行：run.bat demo.py"
    )

try:
    from faster_whisper import WhisperModel
except ImportError as _exc:
    sys.exit(
        f"[错误] 导入 faster_whisper 失败：{_exc}\n"
        f"       当前解释器：{sys.executable}\n"
        "       请用 run.bat 或 faster-whisper 环境运行本脚本。"
    )

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
