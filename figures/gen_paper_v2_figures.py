#!/usr/bin/env python3
"""Data figures for paper v2 (2026-10-06). Every number is read from results/, none typed in.

  fig5_ablation_v2.png   results/mfdfa_ablation_results.json            (unit-corrected features)
  fig6_confound_v2.png   results/source_confound_report_crosscohort.json
  fig7_cascade.png       results/leave_source_out*.json                 (unseen-source controls)

Palette: dataviz reference categorical slots 1-3 (#2a78d6, #eb6834, #1baf7a), validated with
validate_palette.js (all checks pass; slot 3 below 3:1 contrast -> every mark is direct-labelled
and models also differ by marker shape).

Run: .venv/Scripts/python.exe figures/gen_paper_v2_figures.py
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
RES, FIG = ROOT / "results", ROOT / "figures"
BLUE, ORANGE, AQUA = "#2a78d6", "#eb6834", "#1baf7a"
INK, MUTED, GRID = "#222222", "#666666", "#e6e6e6"

plt.rcParams.update({
    "font.family": "serif", "font.serif": ["Times New Roman", "DejaVu Serif"], "font.size": 8.5,
    "axes.titlesize": 9, "axes.titleweight": "bold", "axes.labelsize": 8.5, "axes.edgecolor": MUTED,
    "axes.spines.top": False, "axes.spines.right": False, "axes.grid": True, "axes.axisbelow": True,
    "grid.color": GRID, "grid.linewidth": 0.6, "xtick.color": MUTED, "ytick.color": MUTED,
    "legend.frameon": False, "legend.fontsize": 8, "savefig.dpi": 600, "savefig.bbox": "tight",
})


def _load(name: str) -> dict:
    return json.loads((RES / name).read_text(encoding="utf-8"))


def _label(ax, x, y, text, dy=0.012):
    ax.text(x, y + dy, text, ha="center", va="bottom", fontsize=7.5, color=INK)


def fig_ablation() -> None:
    r = _load("mfdfa_ablation_results.json")["results"]
    keys = ["apfu", "apfu_mfdfa", "apfu_sqi", "apfu_mfdfa_sqi"]
    names = ["Entropy", "Entropy\n+MFDFA", "Entropy\n+SQI feat.", "Entropy\n+MFDFA\n+SQI feat."]
    vals = [r[k]["macro_f1"] for k in keys]
    errs = [r[k]["std_macro_f1"] for k in keys]
    fig, ax = plt.subplots(figsize=(3.3, 2.35))
    x = np.arange(len(keys))
    for i in x:
        shortcut = "sqi" in keys[i]
        ax.bar(i, vals[i], 0.6, color="white" if shortcut else BLUE, edgecolor=BLUE, linewidth=1.0,
               hatch="////" if shortcut else None, zorder=3)
        ax.errorbar(i, vals[i], yerr=errs[i], color=INK, linewidth=0.8, capsize=2, zorder=4)
        _label(ax, i, vals[i] + errs[i], f"{vals[i]:.3f}")
    ax.set_xticks(x, names)
    ax.set_ylabel("Macro-F1 (patient-level 5-fold CV)")
    ax.set_ylim(0.5, 1.08)
    ax.set_title("Component ablation, binary IS vs NS", pad=16)
    ax.text(0.5, 1.02, "hatched = acquisition shortcut (SQI features encode the source)", transform=ax.transAxes,
            ha="center", va="bottom", fontsize=7, color=MUTED, style="italic")
    fig.savefig(FIG / "fig5_ablation_v2.png")
    plt.close(fig)


def fig_confound() -> None:
    p = _load("source_confound_report_crosscohort.json")["probe"]
    groups = [("ENTROPY-only", "Entropy only\n(60, pathology)"), ("SQI-only", "SQI only\n(5, signal quality)"),
              ("FULL (Ent+MFDFA+SQI)", "Full\n(125)")]
    fig, ax = plt.subplots(figsize=(3.3, 2.35))
    x, w = np.arange(len(groups)), 0.34
    for off, metric, color, name in ((-w / 2, "macro_f1", BLUE, "Macro-F1"), (w / 2, "auc", ORANGE, "AUC")):
        vals = [p[k][metric] for k, _ in groups]
        ax.bar(x + off, vals, w, color=color, label=name, zorder=3, edgecolor="white", linewidth=1.0)
        for xi, v in zip(x + off, vals):
            _label(ax, xi, v, f"{v:.3f}", dy=0.008)
    ax.set_xticks(x, [g[1] for g in groups])
    ax.set_ylabel("Score (patient-level 5-fold CV)")
    ax.set_ylim(0.5, 1.1)
    ax.legend(loc="upper left", ncol=2, bbox_to_anchor=(0, 1.02))
    ax.set_title("Cross-cohort separability by feature group", pad=12)
    fig.savefig(FIG / "fig6_confound_v2.png")
    plt.close(fig)


def _swaps(name: str, model: str, test_has: str | None = None) -> list[float]:
    rows = _load(name)["source_swap"]
    return [r["patient_auc"] for r in rows if r["model"] == model and (test_has is None or test_has in r["test"])]


def cascade_data() -> dict[str, dict[str, list[float]]]:
    """Patient AUC per model and evaluation condition (lists = one value per source swap)."""
    main = _load("leave_source_out.json")
    return {
        "Entropy+MFDFA (LightGBM)": {
            "In-source CV": [main["in_source_cv"]["feat_lgbm"]["patient_auc"]],
            "Unseen devices": _swaps("leave_source_out.json", "feat_lgbm"),
            "+ age-matched": _swaps("leave_source_out_age.json", "feat_lgbm"),
            "+ eye-matched": _swaps("leave_source_out_eyes_fast.json", "feat_lgbm", "physionet_eo"),
        },
        "EEGNet": {
            "In-source CV": [main["in_source_cv"]["eegnet"]["patient_auc"]],
            "Unseen devices": _swaps("leave_source_out.json", "eegnet"),
            "+ age-matched": _swaps("leave_source_out_age_eegnet.json", "eegnet"),
            "+ eye-matched": _swaps("leave_source_out_eyes_eegnet.json", "eegnet", "physionet_eo"),
        },
        "Riemannian (deployed)": {
            "In-source CV": [_load("leave_source_out_main_riemann_app.json")["in_source_cv"]["riemann_app"]["patient_auc"]],
            "Unseen devices": _swaps("leave_source_out_main_riemann_app.json", "riemann_app"),
            "+ age-matched": _swaps("leave_source_out_age_riemann_app.json", "riemann_app"),
            "+ eye-matched": _swaps("leave_source_out_eyes_riemann_app.json", "riemann_app", "physionet_eo"),
        },
    }


def fig_cascade() -> dict:
    data = cascade_data()
    conds = list(next(iter(data.values())))
    fig, ax = plt.subplots(figsize=(3.4, 2.6))
    x = np.arange(len(conds))
    styles = {"Entropy+MFDFA (LightGBM)": (BLUE, "o", -0.08), "EEGNet": (ORANGE, "s", 0.0),
              "Riemannian (deployed)": (AQUA, "^", 0.08)}
    ax.axhline(0.5, color=MUTED, linewidth=0.8, linestyle="--", zorder=1)
    ax.text(len(conds) - 0.55, 0.51, "chance", fontsize=7, color=MUTED, ha="right")
    for model, by_cond in data.items():
        color, marker, dx = styles[model]
        means = [float(np.mean(by_cond[c])) for c in conds]
        lo = [min(by_cond[c]) for c in conds]
        hi = [max(by_cond[c]) for c in conds]
        ax.vlines(x + dx, lo, hi, color=color, linewidth=1.2, alpha=0.55, zorder=2)
        ax.plot(x + dx, means, color=color, marker=marker, markersize=5, linewidth=2, label=model, zorder=3,
                markeredgecolor="white", markeredgewidth=0.8)
        ax.text(x[-1] + dx + 0.12, means[-1], f"{means[-1]:.2f}", fontsize=7.5, color=INK, va="center")
    ax.set_xticks(x, ["In-source\nCV", "Unseen\ndevices", "+ age\nmatched", "+ eye state\nmatched"])
    ax.set_ylim(0.45, 1.03)
    ax.set_ylabel("Patient-level AUC")
    ax.legend(loc="lower left", fontsize=7)
    ax.set_title("Each control removes one shortcut")
    fig.savefig(FIG / "fig7_cascade.png")
    plt.close(fig)
    return {m: {c: round(float(np.mean(v)), 3) for c, v in d.items()} for m, d in data.items()}


if __name__ == "__main__":
    fig_ablation()
    fig_confound()
    print(json.dumps(fig_cascade(), indent=1))
