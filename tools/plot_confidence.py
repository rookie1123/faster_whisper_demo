"""画置信度标记实验的两张图。

数据来自 docs/confidence-flagging.md（翁乐康的实验），脚本直接解析那份文档里的表格，
所以文档一更新，重跑本脚本图就跟着更新。

用法:
    python tools/plot_confidence.py

产出（reports/figures/）:
    6_confidence_sweep.png   阈值扫描：准确率、召回率、F1 随阈值的变化
    7_word_confidence.png    对词与错词的置信度分布对比
"""

import re
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

PROJECT = Path(__file__).resolve().parent.parent
DOC = PROJECT / "docs" / "confidence-flagging.md"
OUT_DIR = PROJECT / "reports" / "figures"

plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei"]
plt.rcParams["axes.unicode_minus"] = False

INK = "#0F172A"
MUTED = "#64748B"
GRID = "#E2E8F0"
BLUE = "#1D4ED8"
AMBER = "#F59E0B"
RED = "#DC2626"
GREEN = "#059669"


def clean(text: str) -> str:
    return text.replace("*", "").strip()


def parse_sweep(text: str):
    """解析阈值扫描表，返回 [(阈值, 准确率, 召回率, F1)]。"""
    rows = []
    # 表格里用于强调的粗体标记（**0.70**）会干扰解析，先去掉
    text = text.replace("**", "")
    pattern = re.compile(
        r"^\|\s*([\d.]+)\s*\|[^|]*\|[^|]*\|[^|]*\|[^|]*\|\s*([\d.]+)\s*\|\s*([\d.]+)\s*\|\s*([\d.]+)\s*\|",
        re.M,
    )
    for threshold, precision, recall, f1 in pattern.findall(text):
        rows.append((float(threshold), float(precision), float(recall), float(f1)))
    return sorted(rows)


def parse_quantiles(text: str):
    """解析对/错词的置信度分位数表，返回 {标签: (最低, p25, 中位, 最高)}。"""
    result = {}
    pattern = re.compile(
        r"^\|\s*(对的词|错的词)[^|]*\|\s*([\d.]+)\s*\|\s*([\d.]+)\s*\|\s*\*{0,2}([\d.]+)\*{0,2}\s*\|\s*([\d.]+)\s*\|",
        re.M,
    )
    for label, low, p25, median, high in pattern.findall(text):
        result[label] = (float(low), float(p25), float(median), float(high))
    return result


def style(ax):
    ax.grid(axis="y", color=GRID, linewidth=0.8, zorder=0)
    ax.set_axisbelow(True)
    ax.spines[["top", "right"]].set_visible(False)
    ax.spines[["left", "bottom"]].set_color(GRID)
    ax.tick_params(colors=MUTED, labelsize=10)


def fig_sweep(rows):
    """折线图：三条指标曲线，标出 F1 最高点。"""
    fig, ax = plt.subplots(figsize=(9.6, 5.6), dpi=160)
    xs = [r[0] for r in rows]

    ax.plot(xs, [r[1] for r in rows], marker="o", markersize=6, linewidth=2,
            color=BLUE, label="准确率（标出来的句子里真有错的占比）", zorder=3)
    ax.plot(xs, [r[2] for r in rows], marker="s", markersize=6, linewidth=2,
            color=AMBER, label="召回率（真错的句子里被标出来的占比）", zorder=3)
    ax.plot(xs, [r[3] for r in rows], marker="D", markersize=6, linewidth=2.6,
            color=RED, label="F1（两者的综合）", zorder=4)

    best = max(rows, key=lambda r: r[3])
    ax.axvline(best[0], color=RED, linestyle="--", linewidth=1.2, alpha=0.5, zorder=2)
    ax.annotate(
        f"F1 最高：阈值 {best[0]:.2f}，F1 {best[3]:.3f}\n"
        f"准确率 {best[1]:.2f}　召回率 {best[2]:.2f}",
        xy=(best[0], best[3]), xytext=(best[0] + 0.04, best[3] - 0.22),
        fontsize=11, color=RED,
        arrowprops=dict(arrowstyle="-", color=RED, linewidth=1),
    )

    ax.set_xlabel("置信度阈值（句内最低词置信度低于它，就把这句标出来）",
                  fontsize=11, color=MUTED)
    ax.set_ylabel("比例", fontsize=11, color=MUTED)
    ax.set_ylim(0.3, 1.05)
    ax.set_xlim(0.46, 1.02)
    ax.set_title("阈值越高，标出的句子越多，但白看的也越多", fontsize=14,
                 color=INK, pad=16, loc="left")
    style(ax)
    ax.legend(fontsize=10, frameon=False, loc="lower left")
    fig.text(0.01, 0.005, "数据来源：docs/confidence-flagging.md 第 3.3 节（5 段真人录音，38 句，512 词）",
             fontsize=9, color=MUTED, ha="left")
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    fig.savefig(OUT_DIR / "6_confidence_sweep.png")
    plt.close(fig)


def fig_distribution(quantiles):
    """区间图：对词与错词的置信度分布，两组叠在一起看重叠。"""
    if "对的词" not in quantiles or "错的词" not in quantiles:
        return
    good = quantiles["对的词"]
    bad = quantiles["错的词"]

    fig, ax = plt.subplots(figsize=(9.6, 4.4), dpi=160)
    for row, (label, values, color, count) in enumerate([
        ("错的词", bad, RED, "39 个"),
        ("对的词", good, GREEN, "473 个"),
    ]):
        low, p25, median, high = values
        ax.plot([low, high], [row, row], color=color, linewidth=3,
                alpha=0.35, solid_capstyle="round", zorder=2)
        ax.scatter([p25, median], [row, row], s=[90, 190], color=color,
                   edgecolor="white", linewidth=1.5, zorder=4)
        ax.annotate(f"p25 {p25:.2f}", (p25, row), textcoords="offset points",
                    xytext=(0, 16), ha="center", fontsize=10, color=color)
        ax.annotate(f"中位 {median:.2f}", (median, row), textcoords="offset points",
                    xytext=(0, -24), ha="center", fontsize=10,
                    color=color, fontweight="bold")
        ax.text(0.02, row + 0.12, f"{label}（{count}）", fontsize=11, color=color)

    ax.axvline(0.70, color=BLUE, linestyle="--", linewidth=1.4, zorder=1)
    ax.text(0.705, 1.42, "推荐阈值 0.70", fontsize=11, color=BLUE)

    ax.set_yticks([])
    ax.set_ylim(-0.6, 1.6)
    ax.set_xlim(0, 1.05)
    ax.set_xlabel("逐词置信度", fontsize=11, color=MUTED)
    ax.set_title("两个分位数区间大面积重叠，所以不能逐词判定",
                 fontsize=14, color=INK, pad=16, loc="left")
    style(ax)
    ax.grid(axis="y", visible=False)
    fig.text(0.01, 0.005, "数据来源：docs/confidence-flagging.md 第 3.2 节；"
                          "圆点标出 p25 与中位数，横线是完整取值范围",
             fontsize=9, color=MUTED, ha="left")
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    fig.savefig(OUT_DIR / "7_word_confidence.png")
    plt.close(fig)


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    text = DOC.read_text(encoding="utf-8", errors="ignore")

    rows = parse_sweep(text)
    if rows:
        fig_sweep(rows)
        print(f"6_confidence_sweep.png   阈值扫描（{len(rows)} 个阈值点）")
    else:
        print("没解析到阈值扫描表")

    quantiles = parse_quantiles(text)
    if quantiles:
        fig_distribution(quantiles)
        print("7_word_confidence.png    逐词置信度分布")
    else:
        print("没解析到分位数表")

    print(f"\n图片目录: {OUT_DIR}")


if __name__ == "__main__":
    main()
