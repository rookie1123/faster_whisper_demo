"""从 reports/ 里的评测报告自动提取数据并画图。

用法:
    python tools/plot_results.py

产出（保存到 reports/figures/）:
    1_vocab_effect.png        五个说话人 × 三种词表
    2_model_compare.png       五个说话人 × 两个模型
    3_quantization.png        两个模型 × 三个数值档位

为什么要自动解析而不是把数字写死在脚本里：
    实验一旦重跑，数字会变（比如换了机器、加了样本）。写死的话图和数据会脱节，
    而且没人会记得回来改。
"""

import re
from collections import defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

PROJECT = Path(__file__).resolve().parent.parent
REPORTS = PROJECT / "reports"
OUT_DIR = REPORTS / "figures"

# 中文字体，Windows 自带
plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei"]
plt.rcParams["axes.unicode_minus"] = False

SPEAKERS = [
    "speaker_fujian",
    "speaker_daiyipeng",
    "speaker_huangsiyang",
    "speaker_gaojinglin",
    "speaker_wenglekang",
]

# 文件名里时间戳之后的部分 -> 条件名
CONDITION_PATTERNS = [
    ("_noprompt_int8_float32", "int8_float32"),
    ("_noprompt_float32", "float32"),
    ("_prompt-ml", "ml 词表"),
    ("_prompt-tech", "tech 词表"),
    ("_noprompt", "不加词表"),
]

MODEL_RE = re.compile(
    r"^\|\s*(faster-whisper-(tiny|small|medium))\s*\|[^|]*\|\s*([\d.]+)%", re.M
)


def parse_report(path: Path) -> dict:
    """返回 {模型: 规范化字错率}，读不到就返回空字典。"""
    text = path.read_text(encoding="utf-8", errors="ignore")
    return {
        short: float(value)
        for _, short, value in MODEL_RE.findall(text)
    }


def classify(name: str):
    """从文件名判断它属于哪个说话人、哪个条件。"""
    stem = re.sub(r"^\d{8}-\d{4,6}_", "", name)
    if not stem.endswith(".md"):
        return None, None
    stem = stem[:-3]
    for speaker in SPEAKERS:
        if stem.startswith(speaker):
            tail = stem[len(speaker):]
            for pattern, label in CONDITION_PATTERNS:
                if tail == pattern:
                    return speaker, label
    return None, None


def collect():
    """扫描 reports/，返回 {(说话人, 条件): {模型: CER}}。

    同一「说话人 × 条件」可能有多份报告，来自不同的人和不同的机器。
    跨机器的数值有细微差异（CPU 指令集不同导致 int8 算子的浮点累加顺序不同），
    混在一张图里会出现"同一条件两个数"的自相矛盾。

    所以这里优先取**同一批次**的报告：模型数最多的那份（同一批实验会一次跑完
    tiny 和 small，而零散补跑的报告通常只含一个模型）。模型数相同时取时间戳最新的。
    """
    candidates = defaultdict(list)
    for path in REPORTS.glob("*.md"):
        key = classify(path.name)
        if key[0] is None:
            continue
        values = parse_report(path)
        if values:
            candidates[key].append((path.name, values))

    data = {}
    for key, items in candidates.items():
        items.sort(key=lambda pair: (len(pair[1]), pair[0]))
        data[key] = items[-1][1]
    return data


def grouped_bar(ax, groups, series, colors, ylabel):
    """画分组柱状图。series 是 [(标签, {组: 值}), ...]。"""
    n_series = len(series)
    width = 0.8 / n_series
    xs = range(len(groups))

    for i, (label, values) in enumerate(series):
        offset = (i - (n_series - 1) / 2) * width
        heights = [values.get(g, 0) for g in groups]
        bars = ax.bar(
            [x + offset for x in xs], heights, width * 0.92,
            label=label, color=colors[i], zorder=3,
        )
        ax.bar_label(bars, fmt="%.1f", fontsize=9, padding=2)

    ax.set_xticks(list(xs))
    ax.set_xticklabels([g.replace("speaker_", "") for g in groups], fontsize=11)
    ax.set_ylabel(ylabel, fontsize=11)
    ax.grid(axis="y", alpha=0.3, zorder=0)
    ax.legend(fontsize=10, frameon=False)
    ax.spines[["top", "right"]].set_visible(False)


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    data = collect()

    if not data:
        print("reports/ 里没有解析到数据")
        return

    # ---------- 图 1：词表效果 ----------
    conditions = ["不加词表", "tech 词表", "ml 词表"]
    series = []
    for cond in conditions:
        values = {
            speaker: data[(speaker, cond)]["small"]
            for speaker in SPEAKERS
            if (speaker, cond) in data and "small" in data[(speaker, cond)]
        }
        if values:
            series.append((cond, values))

    if series:
        fig, ax = plt.subplots(figsize=(10, 5.6), dpi=160)
        grouped_bar(
            ax, SPEAKERS, series,
            ["#94A3B8", "#93C5FD", "#1D4ED8"],
            "规范化字错率（%，越低越好）",
        )
        ax.set_title("三种词表在五个说话人上的效果（small 模型）",
                     fontsize=14, pad=14, loc="left")
        fig.tight_layout()
        fig.savefig(OUT_DIR / "1_vocab_effect.png")
        plt.close(fig)
        print("已生成 1_vocab_effect.png")

    # ---------- 图 2：模型对比 ----------
    series = []
    for model, label, color in [
        ("tiny", "tiny（39M）", "#F59E0B"),
        ("small", "small（244M）", "#1D4ED8"),
    ]:
        values = {
            speaker: data[(speaker, "不加词表")][model]
            for speaker in SPEAKERS
            if (speaker, "不加词表") in data and model in data[(speaker, "不加词表")]
        }
        if values:
            series.append((label, values))

    if len(series) == 2:
        fig, ax = plt.subplots(figsize=(10, 5.6), dpi=160)
        grouped_bar(
            ax, SPEAKERS, series,
            ["#F59E0B", "#1D4ED8"],
            "规范化字错率（%，越低越好）",
        )
        ax.set_title("同一段文字、不同说话人：tiny 的波动远大于 small",
                     fontsize=14, pad=14, loc="left")
        fig.tight_layout()
        fig.savefig(OUT_DIR / "2_model_compare.png")
        plt.close(fig)
        print("已生成 2_model_compare.png")

    # ---------- 图 3：模型规模 vs 数值档位 ----------
    quant = defaultdict(dict)
    for path in REPORTS.glob("*.md"):
        stem = re.sub(r"^\d{8}-\d{4,6}_", "", path.name)
        if not stem.startswith("speaker_fujian"):
            continue
        match = re.search(r"_(int8_float32|float32)\.md$", stem)
        level = match.group(1) if match else "int8"
        for model, value in parse_report(path).items():
            quant[model][level] = value

    levels = ["int8", "int8_float32", "float32"]
    models = [m for m in ["tiny", "small"] if m in quant]
    if models and any(quant[m] for m in models):
        fig, ax = plt.subplots(figsize=(8.4, 5.6), dpi=160)
        series = []
        for model, label, color in [
            ("tiny", "tiny", "#F59E0B"),
            ("small", "small", "#1D4ED8"),
        ]:
            if model in quant:
                series.append((label, quant[model]))
        grouped_bar(
            ax, models, series,
            ["#F59E0B", "#1D4ED8"],
            "规范化字错率（%，越低越好）",
        )
        ax.set_xticklabels(models, fontsize=12)
        ax.set_title("模型规模与数值档位的取舍（speaker_fujian）",
                     fontsize=14, pad=14, loc="left")
        fig.tight_layout()
        fig.savefig(OUT_DIR / "3_quantization.png")
        plt.close(fig)
        print("已生成 3_quantization.png")

    print(f"\n图片目录: {OUT_DIR}")


if __name__ == "__main__":
    main()
