#!/usr/bin/env python3
"""4-layer system architecture figure for the UIST paper (deterministic matplotlib).

A fallback to the Gemini prompt: renders the pipeline + interaction band directly,
consistent with the other figures' Ocean Dusk palette. Content from sec 4.2-4.3.

Run: .venv/Scripts/python.exe figures/gen_architecture.py
Output: figures/fig_architecture.{pdf,png}
"""
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

FIG = Path(__file__).resolve().parent
FIG.mkdir(exist_ok=True)

plt.rcParams.update({
    "font.family": "serif", "font.serif": ["Times New Roman", "DejaVu Serif"],
    "savefig.dpi": 600, "savefig.bbox": "tight",
})

DEEP, TEAL, GOLD, ORANGE, OUR = "#264653", "#2A9D8F", "#E9C46A", "#F4A261", "#E76F51"
INK = "#22303A"
BODY_BG = "#FFFFFF"
WASH = "#F5F7F7"

STAGES = [
    (DEEP, "1 · Data Acquisition & Preprocessing",
     ["18-channel EEG @ 256 Hz", "Causal band-pass 1–35 Hz",
      "Signal Quality Index (SQI):", "line noise · clipping · electrode loss"]),
    (TEAL, "2 · Hybrid Feature Extraction",
     ["1 s window → Entropy (ApEn, FuEn)", "4 s buffer → MFDFA spectrum",
      "→ 125-dim vector", "(+ Fuzzy Asymmetric Index, asymmetry)"]),
    (GOLD, "3 · Classification",
     ["LightGBM", "tuned by TPE (Optuna)", "→ P(ischemic) vs P(non-stroke)"]),
    (ORANGE, "4 · Online Inference Engine",
     ["0.5 s hop · ring buffer", "causal filters", "real-time streaming"]),
]

INTERACTION = [
    "Risk-score stream",
    "SQI gating\n→ No-Decision",
    "EMA smoothing +\nhysteresis (θhigh=0.80)",
    "Cooldown\n(no redundant alerts)",
    "Paramedic UI:\nalert + “why this alert”",
]


def rbox(ax, x, y, w, h, fc, ec="none", lw=0, rad=0.025, z=2):
    ax.add_patch(FancyBboxPatch((x, y), w, h, mutation_aspect=1,
                 boxstyle=f"round,pad=0,rounding_size={rad}",
                 fc=fc, ec=ec, lw=lw, zorder=z))


def arrow(ax, x0, y0, x1, y1, color="#5B6B73"):
    ax.add_patch(FancyArrowPatch((x0, y0), (x1, y1), arrowstyle="-|>",
                 mutation_scale=14, lw=1.6, color=color, zorder=5,
                 shrinkA=0, shrinkB=0))


def main():
    fig, ax = plt.subplots(figsize=(11.2, 5.2))
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.axis("off")

    n = len(STAGES)
    gap = 2.0
    w = (100 - 2 * 2 - (n - 1) * gap) / n
    x0 = 2.0
    top, bot = 92, 44
    h = top - bot
    centers = []
    for i, (color, title, items) in enumerate(STAGES):
        x = x0 + i * (w + gap)
        centers.append(x + w / 2)
        rbox(ax, x, bot, w, h, WASH, z=1)                 # section wash
        rbox(ax, x, top - 7, w, 7, color, z=3)            # header
        ax.text(x + w / 2, top - 3.5, title, ha="center", va="center",
                fontsize=8.6, fontweight="bold", color="white", zorder=4)
        ax.text(x + w / 2, (bot + top - 7) / 2 + 1.5, "\n".join(items),
                ha="center", va="center", fontsize=8.0, color=INK,
                zorder=4, linespacing=1.9)

    # horizontal flow arrows
    midy = (bot + top - 7) / 2
    for i in range(n - 1):
        xa = x0 + i * (w + gap) + w
        arrow(ax, xa - 0.2, midy, xa + gap + 0.2, midy)

    # interaction band
    bx, bw, by, bh = 2.0, 96.0, 6, 30
    rbox(ax, bx, by, bw, bh, "#FCEEE9", z=1)
    rbox(ax, bx, by + bh - 6, bw, 6, OUR, z=3)
    ax.text(bx + bw / 2, by + bh - 3, "Interaction & Alerting  (alarm-fatigue-aware)",
            ha="center", va="center", fontsize=8.8, fontweight="bold",
            color="white", zorder=4)

    m = len(INTERACTION)
    igap = 1.6
    iw = (bw - 4 - (m - 1) * igap) / m
    iy, ih = by + 3, bh - 12
    icenters = []
    for j, label in enumerate(INTERACTION):
        ix = bx + 2 + j * (iw + igap)
        icenters.append(ix + iw / 2)
        fc = "#FFFFFF" if j < m - 1 else "#FDEAE3"
        rbox(ax, ix, iy, iw, ih, fc, ec="#EAD7CF", lw=0.8, z=3)
        ax.text(ix + iw / 2, iy + ih / 2, label, ha="center", va="center",
                fontsize=7.8, color=INK, zorder=4, linespacing=1.35)
        if j < m - 1:
            arrow(ax, ix + iw, iy + ih / 2, ix + iw + igap, iy + ih / 2,
                  color="#C98E78")

    # down arrow: stage 4 -> interaction band
    arrow(ax, centers[-1], bot - 0.5, centers[-1], by + bh + 0.5, color=OUR)
    ax.text(centers[-1] + 1.2, (bot + by + bh) / 2, "probabilities + SQI",
            ha="left", va="center", fontsize=7.4, color=OUR, style="italic")

    for ext in ("pdf", "png"):
        for cand in (f"fig_architecture.{ext}", f"fig_architecture_new.{ext}"):
            try:
                fig.savefig(FIG / cand, dpi=600)
                print(f"  -> {cand}")
                break
            except PermissionError:
                continue
    plt.close(fig)


if __name__ == "__main__":
    main()
