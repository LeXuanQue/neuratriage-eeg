"""Figures for the UIST 2027 paper from the result files (docs/paper_outline.md, section 2).

  fig_confound_cascade   E2   patient AUC per control level, LightGBM features vs Riemann
  fig_far_vs_alpha       E10  realised FAR vs target alpha: conformal, heuristic, window-level
  fig_calibration_size   E12  FAR (mean, p90) vs calibration patients per class
  fig_decision_time      E13  AUC / sensitivity / No-Decision vs recording length

Style follows the dataviz method: one y-axis per chart, thin marks, recessive grid, a legend
for >= 2 series plus a distinct marker per series (the third colour is below 3:1 contrast,
so identity never relies on colour alone). Palette = first three reference categorical
slots, validated all-pairs for the light surface.

Usage::

    .venv/Scripts/python.exe scripts/paper_figures.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "results"
OUT = ROOT / "figures" / "uist2027"

BLUE, ORANGE, AQUA = "#2a78d6", "#eb6834", "#1baf7a"
INK, INK_2, GRID = "#0b0b0b", "#52514e", "#e4e3df"
WIDTH = 3.4  # in, one ACM column


# --------------------------------------------------------------------------- data helpers
def cascade_points(lso: dict, model: str, test_must_include: Optional[str] = None) -> List[Tuple[float, float, float]]:
    """(AUC, CI low, CI high) for every source swap of ``model``."""
    out = []
    for r in lso["source_swap"]:
        if r["model"] != model:
            continue
        if test_must_include and test_must_include not in r["test"]:
            continue
        lo, hi = r["patient_auc_ci95"]
        out.append((r["patient_auc"], lo, hi))
    return out


def far_curve(report: dict, split: str, method: str) -> Tuple[List[float], List[float], List[float], List[float]]:
    """alphas, mean FAR, p05, p95 for ``method`` (a method dict with 'far', or the window-level key)."""
    alphas = sorted(report["splits"][split]["alphas"], key=float)
    mean, lo, hi = [], [], []
    for a in alphas:
        entry = report["splits"][split]["alphas"][a][method]
        far = entry["far"] if "far" in entry else entry
        mean.append(far["mean"])
        lo.append(far["p05"])
        hi.append(far["p95"])
    return [float(a) for a in alphas], mean, lo, hi


# --------------------------------------------------------------------------- style
def _style():
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.rcParams.update({
        "font.size": 8, "axes.labelsize": 8, "axes.titlesize": 8, "legend.fontsize": 7,
        "xtick.labelsize": 7, "ytick.labelsize": 7, "axes.edgecolor": INK_2, "axes.labelcolor": INK,
        "xtick.color": INK_2, "ytick.color": INK_2, "text.color": INK, "axes.grid": True,
        "grid.color": GRID, "grid.linewidth": 0.6, "axes.axisbelow": True,
        "axes.spines.top": False, "axes.spines.right": False, "lines.linewidth": 1.5,
        "lines.markersize": 5, "legend.frameon": False, "pdf.fonttype": 42, "savefig.dpi": 300,
    })
    return plt


def _save(fig, name: str) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for ext in ("pdf", "png"):
        fig.savefig(OUT / f"{name}.{ext}", bbox_inches="tight")


def _load(name: str) -> dict:
    return json.loads((RESULTS / name).read_text(encoding="utf-8"))


# --------------------------------------------------------------------------- figures
def fig_confound_cascade(plt) -> None:
    levels = [
        ("Same\nsource", "lso_ci_main.json", None, True),
        ("Source\nswap", "lso_ci_main.json", None, False),
        ("Age\nmatched", "lso_ci_age.json", None, False),
        ("Eye-state\nmatched", "lso_ci_eyes.json", "physionet_eo", False),
    ]
    fig, ax = plt.subplots(figsize=(WIDTH, 2.3))
    for model, color, marker, dx, label in (
        ("feat_lgbm", ORANGE, "s", -0.12, "Entropy/MFDFA features"),
        ("riemann_app", BLUE, "o", 0.12, "Riemannian"),
    ):
        for i, (_, fname, must, in_source) in enumerate(levels):
            lso = _load(fname)
            if in_source:
                ax.plot(i + dx, lso["in_source_cv"][model]["patient_auc"], marker, color=color, ms=5)
                continue
            for j, (auc, lo, hi) in enumerate(cascade_points(lso, model, must)):
                x = i + dx + (j - 1.5) * 0.04
                ax.plot([x, x], [lo, hi], color=color, lw=1.0, alpha=0.8)
                ax.plot(x, auc, marker, color=color, ms=4)
        ax.plot([], [], marker, color=color, label=label)
    ax.axhline(0.5, color=INK_2, lw=0.8, ls="--")
    ax.text(3.45, 0.505, "chance", color=INK_2, fontsize=6.5, ha="right", va="bottom")
    ax.set_xticks(range(len(levels)), [lv[0] for lv in levels])
    ax.set_ylabel("Patient-level AUC (95% CI)")
    ax.set_ylim(0.4, 1.02)
    ax.legend(loc="lower center", bbox_to_anchor=(0.5, 1.0), ncols=2)
    _save(fig, "fig_confound_cascade")
    plt.close(fig)


def fig_far_vs_alpha(plt) -> None:
    report = _load("conformal_no_decision.json")
    fig, axes = plt.subplots(1, 2, figsize=(WIDTH * 2, 2.3), sharey=True)
    methods = (
        ("conformal", BLUE, "o", "Patient-level conformal (ours)"),
        ("heuristic_0.8_0.2", ORANGE, "s", "Fixed thresholds 0.8 / 0.2"),
        ("window_level_any_alert_far", AQUA, "^", "Window-level conformal, any alert"),
    )
    for ax, split in zip(axes, ("S1", "S2")):
        for k, (method, color, marker, label) in enumerate(methods):
            a, mean, lo, hi = far_curve(report, split, method)
            x = [v * (1 + 0.06 * (k - 1)) for v in a]  # small dodge so the 5-95% bars stay apart
            ax.errorbar(x, mean, yerr=[[m - l for m, l in zip(mean, lo)], [h - m for m, h in zip(mean, hi)]],
                         fmt=marker + "-", color=color, ecolor=color, elinewidth=0.9, capsize=0, label=label)
        ax.plot([0, 0.25], [0, 0.25], color=INK_2, lw=0.8, ls="--", label="Target: FAR = α")
        n = report["splits"][split]
        ax.set_title(f"{split}: {n['n_stroke']} stroke / {n['n_control']} control (held-out sources)", color=INK)
        ax.set_xlabel("Target α")
        ax.set_xticks([0.05, 0.1, 0.2])
        ax.set_xlim(0.03, 0.22)
    axes[0].set_ylabel("Realised false-alert rate\n(mean, 5–95% over calibrations)")
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", bbox_to_anchor=(0.5, -0.06), ncols=4)
    _save(fig, "fig_far_vs_alpha")
    plt.close(fig)


def fig_calibration_size(plt) -> None:
    report = _load("conformal_calibration_size.json")
    alpha = "0.1"
    n_min = report["min_calibration_size"][alpha]
    # S1 and S2 give near-identical curves (conformal FAR depends only on ranks), so plot S2.
    curve = report["splits"]["S2"][alpha]
    ns = sorted(curve, key=int)
    x = [int(n) for n in ns]
    fig, ax = plt.subplots(figsize=(WIDTH, 2.3))
    ax.axvspan(0, n_min - 0.5, color=GRID, alpha=0.6, lw=0)
    ax.text((3 + n_min - 0.5) / 2, 0.15, f"< {n_min} per class:\nnever alerts", color=INK_2, fontsize=6.5, ha="center")
    ax.plot(x, [curve[n]["far_p90"] for n in ns], marker="o", color=BLUE, ls=":", mfc="white",
            label="90th percentile over calibrations")
    ax.plot(x, [curve[n]["far_mean"] for n in ns], marker="o", color=BLUE, label="Mean (the guarantee)")
    ax.axhline(float(alpha), color=INK_2, lw=0.8, ls="--")
    ax.text(20.6, float(alpha) + 0.004, "α = 0.1", color=INK_2, fontsize=6.5, ha="right", va="bottom")
    ax.set_xlabel("Calibration patients per class (S2)")
    ax.set_ylabel("Realised false-alert rate")
    ax.set_xlim(3, 21)
    ax.set_ylim(0, 0.25)
    ax.legend(loc="lower right")
    _save(fig, "fig_calibration_size")
    plt.close(fig)


def fig_decision_time(plt) -> None:
    report = _load("decision_time.json")
    hs = sorted(report["horizons"], key=float)
    t = [float(h) for h in hs]
    fig, ax = plt.subplots(figsize=(WIDTH, 2.3))
    series = (
        ([report["horizons"][h]["auc"] for h in hs], BLUE, "o", "Patient AUC"),
        ([report["horizons"][h]["alpha_0.2"]["sensitivity"] for h in hs], ORANGE, "s", "Sensitivity (α = 0.2)"),
        ([report["horizons"][h]["alpha_0.2"]["no_decision_stroke"] for h in hs], AQUA, "^", "Stroke in No-Decision (α = 0.2)"),
    )
    for y, color, marker, label in series:
        ax.plot(t, y, marker=marker, color=color, label=label)
    ax.set_xscale("log")
    ax.set_xticks(t, [f"{v:g}" for v in t])
    ax.minorticks_off()
    ax.set_xlabel("Seconds recorded before deciding")
    ax.set_ylabel("Proportion")
    ax.set_ylim(0, 1)
    ax.legend(loc="center right", bbox_to_anchor=(1.0, 0.40))
    _save(fig, "fig_decision_time")
    plt.close(fig)


def main(names: Sequence[str] = ()) -> None:
    plt = _style()
    figures = {
        "fig_confound_cascade": fig_confound_cascade,
        "fig_far_vs_alpha": fig_far_vs_alpha,
        "fig_calibration_size": fig_calibration_size,
        "fig_decision_time": fig_decision_time,
    }
    for name, fn in figures.items():
        if not names or name in names:
            fn(plt)
            print(f"wrote {OUT / name}.pdf/.png")


if __name__ == "__main__":
    main(sys.argv[1:])
