"""中文识别评测：拿有标准答案的音频对比不同模型，计算字错率 CER。

CER (Character Error Rate) = (替换 + 删除 + 插入) / 标准答案的字数
CER 越低越好：0 表示一字不差，0.1 表示大约每 10 个字错 1 个字。

用法:
    python eval_zh.py samples/speaker/speaker_fujian.mp3 samples/reading_script.txt
    python eval_zh.py samples/speaker/speaker_fujian.mp3 samples/reading_script.txt --prompt-name ml
"""

import argparse
import re
import sys
import time
import unicodedata
from pathlib import Path

# 解释器自检：系统 PATH 里可能排着别的 Python 版本，一旦用错解释器，
# 报错会是看不懂的 "No module named 'av'"。这里提前拦下来。
if sys.version_info < (3, 9):
    _venv_python = Path(__file__).resolve().parent / ".venv" / "Scripts" / "python.exe"
    sys.exit(
        "[错误] 解释器版本不对：faster-whisper 要求 Python >= 3.9。\n"
        f"       当前解释器：Python {sys.version.split()[0]}  ({sys.executable})\n"
        f"       请改用项目内的虚拟环境：{_venv_python}\n"
        "       或直接运行：run.bat eval_zh.py <音频> <标准答案>"
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

# 计算 CER 时忽略的字符：空白和常见中英文标点
IGNORED = re.compile(
    r"[\s，。、；：？！“”‘’（）《》〈〉【】「」,.!?;:\"'()\[\]<>~—…·\-_/\\|]+"
)

CN_DIGITS = {"零": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5,
             "六": 6, "七": 7, "八": 8, "九": 9}
CN_UNITS = {"十": 10, "百": 100, "千": 1000, "万": 10000}
CN_NUM = "[零一二三四五六七八九十百千万两]"


def normalize(text: str) -> str:
    """统一全角半角、去掉标点和空白，便于逐字比较。"""
    text = unicodedata.normalize("NFKC", text)
    return IGNORED.sub("", text).lower()


def cn2num(s: str) -> str:
    """把中文数字串转成阿拉伯数字，支持 零/一/两/十/百/千/万。"""
    total = section = number = 0
    for ch in s:
        if ch == "零":
            number = 0
        elif ch in CN_DIGITS:
            number = CN_DIGITS[ch]
        else:
            unit = CN_UNITS[ch]
            if unit == 10000:
                section = (section + number) * unit
                total += section
                section = 0
            else:
                section += (number or 1) * unit
            number = 0
    return str(total + section + number)


def normalize_numbers(text: str) -> str:
    """把中文数字写成阿拉伯数字，避免"百分之九十一"和"91%"被算成错。

    只在有明确语境的场合转换（后面跟着 点/分/个/年… 或前面有 百分之），
    避免把"一部分""十分重要"这类词误伤。
    """
    # "百分之"里的"百"也是数字字符，先用占位符隔开，避免被贪婪匹配吃掉
    marker = "\x00"
    text = text.replace("百分之", marker)
    text = re.sub(
        f"{marker}({CN_NUM}+)", lambda m: cn2num(m.group(1)) + "%", text
    )
    return re.sub(
        f"({CN_NUM}+)(?=[点分个元年月日时秒倍天周号层])",
        lambda m: cn2num(m.group(1)),
        text,
    )


def align(ref: str, hyp: str):
    """编辑距离 + 回溯，返回 (距离, 操作列表)。操作列表用来展示错在哪里。"""
    n, m = len(ref), len(hyp)
    d = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(n + 1):
        d[i][0] = i
    for j in range(m + 1):
        d[0][j] = j
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            cost = 0 if ref[i - 1] == hyp[j - 1] else 1
            d[i][j] = min(d[i - 1][j] + 1, d[i][j - 1] + 1, d[i - 1][j - 1] + cost)

    ops = []
    i, j = n, m
    while i > 0 or j > 0:
        if i > 0 and j > 0 and d[i][j] == d[i - 1][j - 1] + (ref[i - 1] != hyp[j - 1]):
            if ref[i - 1] == hyp[j - 1]:
                ops.append(("ok", ref[i - 1], hyp[j - 1]))
            else:
                ops.append(("替换", ref[i - 1], hyp[j - 1]))
            i -= 1
            j -= 1
        elif i > 0 and d[i][j] == d[i - 1][j] + 1:
            ops.append(("漏字", ref[i - 1], ""))
            i -= 1
        else:
            ops.append(("多字", "", hyp[j - 1]))
            j -= 1
    ops.reverse()
    return d[n][m], ops


def main():
    parser = argparse.ArgumentParser(
        description="中文识别评测（CER）",
        epilog=(
            "示例:\n"
            "  python eval_zh.py samples/speaker/speaker_fujian.mp3 samples/reading_script.txt\n"
            "  python eval_zh.py samples/speaker/speaker_fujian.mp3 samples/reading_script.txt --prompt-name ml\n"
            "  python eval_zh.py samples/speaker/speaker_fujian.mp3 samples/reading_script.txt "
            "--models faster-whisper-tiny faster-whisper-small\n"
            "\n"
            "用 run.bat 启动可避免选错解释器:\n"
            "  run.bat eval_zh.py <音频> <标准答案>"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("audio", help="要测试的音频文件")
    parser.add_argument("reference", help="标准答案文本文件")
    parser.add_argument(
        "--models",
        nargs="+",
        default=["faster-whisper-tiny", "faster-whisper-small"],
        help="要对比的模型目录名（models 目录下）",
    )
    parser.add_argument("--prompt", default=None, help="可选的 initial_prompt")
    parser.add_argument("--prompt-name", default=None, help="prompts.py 里预置的词表名，如 zh / tech")

    # 不带任何参数时直接给出帮助：最常见的坑就是忘了传音频和标准答案
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

    audio_path = Path(args.audio)
    if not audio_path.is_absolute():
        audio_path = PROJECT / audio_path
    ref_path = Path(args.reference)
    if not ref_path.is_absolute():
        ref_path = PROJECT / ref_path

    reference_raw = ref_path.read_text(encoding="utf-8").strip()
    reference = normalize(reference_raw)
    print(f"音频: {audio_path.name}")
    print(f"标准答案: {reference_raw}")
    print(f"（比较时忽略标点，实际比对 {len(reference)} 个字）\n")

    models_str = ", ".join(args.models)

    # 归档文件名的提示词标签：避免同一分钟内多次实验互相覆盖，也便于事后一眼区分。
    # 基线显式标成 _noprompt，方便在 reports/ 里直接区分"没加提示"和"加了提示"。
    prompt_tag = "_noprompt"
    if args.prompt_name:
        prompt_tag = f"_prompt-{args.prompt_name}"
    elif args.prompt:
        prompt_tag = "_prompt-custom"

    report = [
        "# 中文识别评测报告",
        "",
        f"- 时间: {time.strftime('%Y-%m-%d %H:%M:%S')}",
        f"- 音频文件: `{audio_path.name}`",
        f"- 标准答案: {reference_raw}",
        f"- 对比模型: {models_str}",
        f"- 词表(prompt-name): {args.prompt_name or '（未指定）'}",
        f"- initial_prompt: {args.prompt or '（未使用）'}",
        "- 解码参数: beam_size=5, vad_filter=True, device=cpu, compute_type=int8",
        "",
        "> 原始 CER 把「中文数字」和「阿拉伯数字」的写法差异也算作错误；",
        "> 规范化 CER 会先把两边统一成阿拉伯数字再比较，更接近真实识别水平。",
        "",
        "| 模型 | 原始 CER | 规范化 CER | 替换 | 漏字 | 多字 | 识别耗时 | 速度倍率 |",
        "|---|---|---|---|---|---|---|---|",
    ]

    results = []
    for name in args.models:
        model_dir = PROJECT / "models" / name
        if not model_dir.exists():
            print(f"[跳过] 缺少模型: {model_dir}")
            continue

        model = WhisperModel(str(model_dir), device="cpu", compute_type="int8")
        t0 = time.time()
        segments, info = model.transcribe(
            str(audio_path),
            language="zh",
            beam_size=5,
            vad_filter=True,
            initial_prompt=args.prompt,
        )
        text = "".join(s.text for s in segments).strip()
        elapsed = time.time() - t0

        hyp_raw = normalize(text)
        dist_raw, _ = align(reference, hyp_raw)
        cer_raw = dist_raw / max(len(reference), 1)

        # 规范化后再比一次：把中文数字统一成阿拉伯数字，剔除纯格式差异
        ref_norm = normalize_numbers(reference)
        hyp_norm = normalize_numbers(hyp_raw)
        distance, ops = align(ref_norm, hyp_norm)
        subs = sum(1 for t, _, _ in ops if t == "替换")
        dels = sum(1 for t, _, _ in ops if t == "漏字")
        ins = sum(1 for t, _, _ in ops if t == "多字")
        cer = distance / max(len(ref_norm), 1)

        print("=" * 72)
        print(f"模型: {name}")
        print(f"识别结果: {text}")
        print(
            f"字错率: 原始 {cer_raw:.1%}  →  规范化后 {cer:.1%}  "
            f"(替换 {subs} / 漏字 {dels} / 多字 {ins}，共 {len(ref_norm)} 字)"
        )
        print(
            f"识别耗时 {elapsed:.1f}s  "
            f"音频时长 {info.duration:.1f}s  "
            f"速度倍率 {info.duration / max(elapsed, 1e-6):.1f}x"
        )

        errors = [op for op in ops if op[0] != "ok"]
        if errors:
            print(f"\n错在哪里（只列前 25 处）:")
            for tag, r, h in errors[:25]:
                if tag == "替换":
                    print(f"  [替换] 应为「{r}」→ 识别成「{h}」")
                elif tag == "漏字":
                    print(f"  [漏字] 丢掉「{r}」")
                else:
                    print(f"  [多字] 多出「{h}」")
        else:
            print("\n完全正确，一个字都没错。")
        print()

        results.append((name, cer_raw, cer, subs, dels, ins, elapsed, info.duration, text))
        report.append(
            f"| {name} | {cer_raw:.1%} | {cer:.1%} | {subs} | {dels} | {ins} | "
            f"{elapsed:.1f}s | {info.duration / max(elapsed, 1e-6):.1f}x |"
        )

    if len(results) > 1:
        best = min(results, key=lambda r: r[2])
        print("=" * 72)
        print(f"结论: 规范化后字错率最低的是 {best[0]}（CER {best[2]:.1%}）")
        report += ["", f"**结论**: 规范化后字错率最低的是 `{best[0]}`（CER {best[2]:.1%}）"]

    report += ["", "## 识别原文", ""]
    for name, _, _, _, _, _, _, _, text in results:
        report += [f"**{name}**:", "", f"> {text}", ""]

    text = "\n".join(report)

    # 固定文件名：方便随时查看"最新一次"的结果（会被覆盖）
    latest = PROJECT / "eval_report.md"
    latest.write_text(text, encoding="utf-8")

    # 带时间戳归档：保留每一次实验的历史，方便对比
    reports_dir = PROJECT / "reports"
    reports_dir.mkdir(exist_ok=True)
    archived = reports_dir / (
        f"{time.strftime('%Y%m%d-%H%M%S')}_{audio_path.stem}{prompt_tag}.md"
    )
    archived.write_text(text, encoding="utf-8")

    print(f"报告已写入 {latest.name}（最新）和 {archived.relative_to(PROJECT)}（归档）")


if __name__ == "__main__":
    main()
