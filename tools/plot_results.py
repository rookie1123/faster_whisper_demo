"""从 reports/ 里的评测报告自动提取数据并画图。

用法:
    python tools/plot_results.py

产出（保存到 reports/figures/）:
    1_model_stability.png   五个说话人下，两个模型的字错率分布     点图 + 极差
    2_vocab_slope.png       三种词表的效果变化                    斜率图
    3_vocab_heatmap.png     说话人 × 词表 的字错率矩阵             热力图
    4_error_composition.png 错误类型构成                          堆叠柱状图
    5_accuracy_speed.png    精度与速度的权衡                      散点图

数据不写死在脚本里，而是解析 reports/ 下的报告，实验重跑后图会自动更新。
"""

import re
from collections import defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch

PROJECT = Path(__file__).resolve().parent.parent
REPORTS = PROJECT / "reports"
OUT_DIR = REPORTS / "figures"

plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei"]
plt.rcParams["axes.unicode_minus"] = False

INK = "#0F172A"
MUTED = "#64748B"
GRID = "#E2E8F0"
BLUE = "#1D4ED8"
LIGHT_BLUE = "#93C5FD"
AMBER = "#F59E0B"
RED = "#DC2626"

SPEAKERS = [
    "speaker_fujian",
    "speaker_daiyipeng",
    "speaker_huangsiyang",
    "speaker_gaojinglin",
    "speaker_wenglekang",
]

CONDITION_PATTERNS = [
    ("_noprompt_int8_float32", "int8_float32"),
    ("_noprompt_float32", "float32"),
    ("_prompt-ml", "ml 词表"),
    ("_prompt-tech", "tech 词表"),
    ("_noprompt", "不加词表"),
]

# 每行报告表格：模型名 | 原始 | 规范化 | 替换 | 漏字 | 多字 | 耗时 | 倍率
ROW_RE = re.compile(
    r"^\|\s*(faster-whisper-(tiny|small|medium))\s*\|"
    r"\s*([\d.]+)%\s*\|\s*([\d.]+)%\s*\|"
    r"\s*(\d+)\s*\|\s*(\d+)\s*\|\s*(\d+)\s*\|"
    r"\s*([\d.]+)s\s*\|\s*([\d.]+)x",
    re.M,
)


def parse_report(path: Path) -> dict:
    """返回 {模型: {cer, sub, dele, ins, sec, speed}}。"""
    text = path.read_text(encoding="utf-8", errors="ignore")
    return {
        short: {
            "cer": float(cer),
            "sub": int(sub),
            "dele": int(dele),
            "ins": int(ins),
            "sec": float(sec),
            "speed": float(speed),
        }
        for _, short, _, cer, sub, dele, ins, sec, speed in ROW_RE.findall(text)
    }


def classify(name: str):
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
    """{(说话人, 条件): {模型: 指标}}。

    同一组合可能有多份报告，来自不同的人和不同的机器。跨机器数值有细微差异
    （CPU 指令集不同导致 int8 算子的浮点累加顺序不同），混在一张图里会出现
    「同一条件两个数」。所以优先取同一批次的完整报告：模型数最多的那份。
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


def style(ax):
    ax.grid(axis="y", color=GRID, linewidth=0.8, zorder=0)
    ax.set_axisbelow(True)
    ax.spines[["top", "right"]].set_visible(False)
    ax.spines[["left", "bottom"]].set_color(GRID)
    ax.tick_params(colors=MUTED, labelsize=10)


def title(ax, main):
    ax.set_title(main, fontsize=14, color=INK, pad=16, loc="left")


def short(speaker):
    return speaker.replace("speaker_", "")


# --------------------------------------------------------------- 图 1
def fig_stability(data):
    """点图：横轴字错率，纵轴两个模型，每个说话人一个点。"""
    fig, ax = plt.subplots(figsize=(10, 4.6), dpi=160)
    models = [("small", "small（244M）", BLUE), ("tiny", "tiny（39M）", AMBER)]
    markers = ["o", "s", "^", "D", "v"]

    for row, (model, label, color) in enumerate(models):
        values = [
            (speaker, data[(speaker, "不加词表")][model]["cer"])
            for speaker in SPEAKERS
            if (speaker, "不加词表") in data and model in data[(speaker, "不加词表")]
        ]
        if not values:
            continue
        xs = [v for _, v in values]
        ax.plot(
            [min(xs), max(xs)], [row, row],
            color=color, linewidth=2, alpha=0.35, zorder=2,
        )
        for i, (speaker, value) in enumerate(values):
            ax.scatter(
                value, row, s=110, color=color,
                marker=markers[i % len(markers)],
                edgecolor="white", linewidth=1.2, zorder=3,
                label=short(speaker) if row == 0 else None,
            )
        ax.text(
            max(xs) + 2, row,
            f"极差 {max(xs) - min(xs):.1f}",
            va="center", fontsize=11, color=color, fontweight="bold",
        )

    ax.set_yticks([0, 1])
    ax.set_yticklabels([m[1] for m in models], fontsize=12, color=INK)
    ax.set_ylim(-0.6, 1.6)
    ax.set_xlabel("规范化字错率（%，越低越好）", fontsize=11, color=MUTED)
    title(ax, "同一段文字、五个说话人：tiny 的波动远大于 small")
    style(ax)
    ax.grid(axis="y", visible=False)
    ax.legend(title="说话人", fontsize=9, title_fontsize=9,
              frameon=False, ncol=5, loc="lower center",
              bbox_to_anchor=(0.5, -0.42))
    fig.tight_layout()
    fig.savefig(OUT_DIR / "1_model_stability.png")
    plt.close(fig)


# --------------------------------------------------------------- 图 2
def fig_slope(data):
    """斜率图：每个说话人一条线，三种词表从左到右。"""
    conditions = ["不加词表", "tech 词表", "ml 词表"]
    fig, ax = plt.subplots(figsize=(8.6, 5.6), dpi=160)
    colors = ["#1D4ED8", "#0E7490", "#B45309", "#7C3AED", "#BE123C"]
    xs = range(len(conditions))

    for i, speaker in enumerate(SPEAKERS):
        ys = []
        for cond in conditions:
            entry = data.get((speaker, cond), {}).get("small")
            ys.append(entry["cer"] if entry else None)
        if any(y is None for y in ys):
            continue
        ax.plot(xs, ys, marker="o", markersize=7, linewidth=2.2,
                color=colors[i % len(colors)], label=short(speaker), zorder=3)
        ax.annotate(f"{ys[-1]:.1f}", (xs[-1], ys[-1]),
                    textcoords="offset points", xytext=(8, -3),
                    fontsize=10, color=colors[i % len(colors)])

    ax.set_xticks(list(xs))
    ax.set_xticklabels(conditions, fontsize=12, color=INK)
    ax.set_ylabel("规范化字错率（%，越低越好）", fontsize=11, color=MUTED)
    ax.set_ylim(0, max(12, ax.get_ylim()[1]))
    title(ax, "领域词表让五个说话人全部下降，通用词表则不稳定")
    style(ax)
    ax.legend(fontsize=10, frameon=False, ncol=5, loc="lower center",
              bbox_to_anchor=(0.5, -0.24))
    fig.tight_layout()
    fig.savefig(OUT_DIR / "2_vocab_slope.png")
    plt.close(fig)


# --------------------------------------------------------------- 图 3
def fig_heatmap(data):
    """热力图：行是说话人，列是词表，颜色是字错率。"""
    conditions = ["不加词表", "tech 词表", "ml 词表"]
    rows = []
    for speaker in SPEAKERS:
        row = []
        for cond in conditions:
            entry = data.get((speaker, cond), {}).get("small")
            row.append(entry["cer"] if entry else float("nan"))
        rows.append(row)

    fig, ax = plt.subplots(figsize=(7.2, 5.2), dpi=160)
    image = ax.imshow(rows, cmap="Blues", aspect="auto", vmin=0, vmax=12)
    ax.set_xticks(range(len(conditions)))
    ax.set_xticklabels(conditions, fontsize=11, color=INK)
    ax.set_yticks(range(len(SPEAKERS)))
    ax.set_yticklabels([short(s) for s in SPEAKERS], fontsize=11, color=INK)
    for i, row in enumerate(rows):
        for j, value in enumerate(row):
            if value != value:
                continue
            ax.text(j, i, f"{value:.1f}", ha="center", va="center",
                    fontsize=12, color="white" if value > 6 else INK)
    ax.set_xticks([x - 0.5 for x in range(1, len(conditions))], minor=True)
    ax.set_yticks([y - 0.5 for y in range(1, len(SPEAKERS))], minor=True)
    ax.grid(which="minor", color="white", linewidth=2)
    ax.tick_params(which="minor", length=0)
    title(ax, "说话人与词表的字错率矩阵（small 模型，%）")
    fig.colorbar(image, ax=ax, shrink=0.75, label="规范化字错率")
    fig.tight_layout()
    fig.savefig(OUT_DIR / "3_vocab_heatmap.png")
    plt.close(fig)


# --------------------------------------------------------------- 图 4
def fig_error_composition(data):
    """堆叠柱状图：替换、漏字、多字三类错误的构成。"""
    fig, ax = plt.subplots(figsize=(9, 5.2), dpi=160)
    groups = [("不加词表", "不加词表"), ("ml 词表", "加 ml 词表")]
    models = [("tiny", "tiny"), ("small", "small")]
    labels = ["替换", "漏字", "多字"]
    colors = [BLUE, AMBER, RED]

    xs = []
    tick_labels = []
    totals = {k: [0, 0, 0] for k in range(len(groups) * len(models))}
    for gi, (cond, cond_label) in enumerate(groups):
        for mi, (model, _) in enumerate(models):
            idx = gi * len(models) + mi
            xs.append(idx)
            tick_labels.append(f"{model}\n{cond_label}")
            for speaker in SPEAKERS:
                entry = data.get((speaker, cond), {}).get(model)
                if not entry:
                    continue
                totals[idx][0] += entry["sub"]
                totals[idx][1] += entry["dele"]
                totals[idx][2] += entry["ins"]

    bottom = [0] * len(xs)
    for k in range(3):
        heights = [totals[i][k] for i in xs]
        ax.bar(xs, heights, bottom=bottom, width=0.55,
               color=colors[k], label=labels[k], zorder=3)
        bottom = [b + h for b, h in zip(bottom, heights)]

    for i, total in zip(xs, bottom):
        ax.text(i, total + 3, str(total), ha="center",
                fontsize=11, color=INK, fontweight="bold")

    ax.set_xticks(xs)
    ax.set_xticklabels(tick_labels, fontsize=11, color=INK)
    ax.set_ylabel("错误字数合计（五个说话人）", fontsize=11, color=MUTED)
    title(ax, "错误构成：加词表后错误总数减少一半以上")
    style(ax)
    ax.legend(fontsize=10, frameon=False)
    fig.tight_layout()
    fig.savefig(OUT_DIR / "4_error_composition.png")
    plt.close(fig)


# --------------------------------------------------------------- 图 5
def fig_accuracy_speed(data):
    """散点图：横轴速度倍率，纵轴字错率，理想区在右下。"""
    points = []
    for speaker in SPEAKERS:
        entry = data.get((speaker, "不加词表"))
        if not entry:
            continue
        for model in ("tiny", "small"):
            if model in entry:
                points.append((model, entry[model]))
                break

    quant = defaultdict(dict)
    for path in REPORTS.glob("*.md"):
        stem = re.sub(r"^\d{8}-\d{4,6}_", "", path.name)
        if not stem.startswith("speaker_fujian"):
            continue
        match = re.search(r"_(int8_float32|float32)\.md$", stem)
        level = match.group(1) if match else "int8"
        for model, values in parse_report(path).items():
            quant[model][level] = values

    fig, ax = plt.subplots(figsize=(9, 5.6), dpi=160)

    for i, (model, values) in enumerate(quant.items()):
        for level, v in values.items():
            ax.scatter(v["speed"], v["cer"], s=150,
                       color=BLUE if model == "small" else AMBER,
                       marker="o" if model == "small" else "s",
                       edgecolor="white", linewidth=1.4, zorder=3)
            ax.annotate(f"{model} · {level}", (v["speed"], v["cer"]),
                        textcoords="offset points", xytext=(10, 6),
                        fontsize=9, color=MUTED)

    ax.axhspan(0, 10, color=BLUE, alpha=0.05, zorder=0)
    ax.text(ax.get_xlim()[1], 9.4, "可用区间（字错率低于 10%）",
            ha="right", fontsize=10, color=BLUE)
    ax.set_xlabel("速度倍率（越大越快）", fontsize=11, color=MUTED)
    ax.set_ylabel("规范化字错率（%，越低越好）", fontsize=11, color=MUTED)
    title(ax, "精度与速度的权衡：换模型比换档位有效得多")
    style(ax)
    ax.grid(axis="x", color=GRID, linewidth=0.8)
    fig.tight_layout()
    fig.savefig(OUT_DIR / "5_accuracy_speed.png")
    plt.close(fig)


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for old in OUT_DIR.glob("*.png"):
        old.unlink()

    data = collect()
    if not data:
        print("reports/ 里没有解析到数据")
        return

    fig_stability(data)
    print("1_model_stability.png   点图：模型稳定性")
    fig_slope(data)
    print("2_vocab_slope.png       斜率图：词表效果")
    fig_heatmap(data)
    print("3_vocab_heatmap.png     热力图：词表矩阵")
    fig_error_composition(data)
    print("4_error_composition.png 堆叠柱状图：错误构成")
    fig_accuracy_speed(data)
    print("5_accuracy_speed.png    散点图：精度与速度")
    print(f"\n图片目录: {OUT_DIR}")


if __name__ == "__main__":
    main()
