#!/usr/bin/env python3
"""Generate the two data-driven figures for the EEG stroke triage UIST paper.

Outputs (figures/):
  fig_confound.{pdf,png}  -- source-confound diagnostic (the key honesty figure)
  fig_ablation.{pdf,png}  -- feature/SQI ablation, binary vs exploratory 3-class

Run: .venv/Scripts/python.exe figures/gen_data_figures.py

Data sources:
  - results/source_confound_report.json        (confound probe, generated)
  - docs/uist_evidence.md "Ablation Summary"    (binary macro-F1)
  - results/mfdfa_ablation_3class_4hs_summary.txt (3-class exploratory macro-F1)
"""
import json
from pathlib import Path

import numpy as np
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parent.parent
FIG = ROOT / "figures"
FIG.mkdir(exist_ok=True)

plt.rcParams.update({
    "font.family": "serif", "font.serif": ["Times New Roman", "DejaVu Serif"],
    "font.size": 10, "axes.titlesize": 11, "axes.titleweight": "bold",
    "axes.labelsize": 10, "legend.fontsize": 8.5, "legend.frameon": False,
    "figure.dpi": 600, "savefig.dpi": 600, "savefig.bbox": "tight",
    "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "grid.alpha": 0.15, "lines.linewidth": 1.8,
})

OUR = "#E76F51"        # coral highlight
TEAL = "#2A9D8F"
DEEP = "#264653"
GOLD = "#E9C46A"
GRAY = "#B0BEC5"


def _save(fig, name: str) -> None:
    for ext in ("pdf", "png"):
        for cand in (f"{name}.{ext}", f"{name}_new.{ext}"):
            try:
                fig.savefig(FIG / cand, dpi=600)
                print(f"  -> {cand}")
                break
            except PermissionError:
                continue
        else:
            print(f"  -> SKIPPED {name}.{ext} (all targets locked)")


def fig_confound() -> None:
    """Entropy-only vs SQI-only vs Full: macro-F1 and AUC.

    Story: 5 signal-quality (SQI) features alone -- which encode recording
    condition, not pathology -- nearly separate the classes (AUC 0.998),
    evidencing an acquisition-rig shortcut.
    """
    # CROSS-COHORT confound probe (50 IS vs 50 NS, patient-level 5-fold).
    # NB: results/source_confound_report.json was later overwritten with the
    # SAME-RIG (TUH Slowing) probe, so it can no longer be read here -- the
    # same-rig story is shown separately (poster Table B / abstract text). These
    # cross-cohort values are the audited, documented figures from
    # docs/paper_binary_revision.md (SQI-only AUC 0.998 / macro-F1 0.976,
    # entropy AUC 0.906) and the binary ablation (full 0.991 / AUC 1.000).
    labels = ["Entropy only\n(60 feat,\npathology)",
              "SQI only\n(5 feat,\nsignal quality)",
              "Full\n(125 feat)"]
    f1 = [0.792, 0.976, 0.991]
    auc = [0.906, 0.998, 1.000]

    x = np.arange(len(labels))
    w = 0.36
    fig, ax = plt.subplots(figsize=(5.6, 3.4))

    # highlight the "SQI only" shortcut group with a soft background band (no arrow)
    ax.axvspan(x[1] - 0.5, x[1] + 0.5, color=OUR, alpha=0.08, zorder=0)
    ax.text(x[1], 1.045, "signal quality only\n(no pathology)",
            ha="center", va="bottom", fontsize=7.5, color=OUR, style="italic")

    # consistent colors per metric (intuitive grouped bars)
    b1 = ax.bar(x - w / 2, f1, w, label="Macro-F1", color=DEEP,
                edgecolor="white", linewidth=0.6, zorder=3)
    b2 = ax.bar(x + w / 2, auc, w, label="AUC", color=GOLD,
                edgecolor="white", linewidth=0.6, zorder=3)
    for bars in (b1, b2):
        for bar in bars:
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.008,
                    f"{bar.get_height():.3f}", ha="center", va="bottom",
                    fontsize=7.5, color="#333")
    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=8.5)
    ax.set_ylabel("Score (patient-level 5-fold CV)")
    ax.set_ylim(0.5, 1.14)
    ax.set_yticks([0.5, 0.6, 0.7, 0.8, 0.9, 1.0])
    ax.set_title("Cross-cohort separability by feature group", pad=22)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.34), ncol=2,
              handlelength=1.4, columnspacing=2.5)
    _save(fig, "fig_confound")
    plt.close(fig)


def fig_ablation() -> None:
    """Component ablation, binary IS-vs-NS only (validated task)."""
    conds = ["ApFu", "ApFu+MFDFA", "ApFu+MFDFA+SQI"]
    binary = [0.7924, 0.8225, 0.9913]   # docs/uist_evidence.md

    x = np.arange(len(conds))
    fig, ax = plt.subplots(figsize=(4.6, 3.1))
    colors = [DEEP, DEEP, OUR]          # highlight the full model
    bars = ax.bar(x, binary, 0.56, color=colors,
                  edgecolor="white", linewidth=0.6)
    for bar in bars:
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.012,
                f"{bar.get_height():.3f}", ha="center", va="bottom",
                fontsize=8, color="#333")
    ax.set_xticks(x)
    ax.set_xticklabels(conds, fontsize=9)
    ax.set_ylabel("Macro-F1 (patient-level CV)")
    ax.set_ylim(0.5, 1.06)
    ax.set_title("Component ablation (binary IS vs NS)")
    _save(fig, "fig_ablation")
    plt.close(fig)


if __name__ == "__main__":
    print("Generating data figures...")
    fig_confound()
    fig_ablation()
    print("Done.")
