#!/usr/bin/env python3
"""Alert-state timeline figure for the UIST paper (Interaction Design, sec 4.3-4.4).

This is an ILLUSTRATIVE scenario run through the system's REAL online detector logic
and REAL configured thresholds (from backend/eeg_stroke_pipeline.py, RealTimeConfig):
    sqi_threshold = 0.55   (below -> No-Decision)
    ema_beta      = 0.35   (probability smoothing)
    theta_high    = 0.80   (hysteresis: raise alert)
    theta_low     = 0.60   (hysteresis: clear alert)
    cooldown_sec  = 15.0

The replay cases never drop SQI below the 0.55 gate and pin IS-probability at ~1.0,
so a real trace cannot exercise No-Decision / hysteresis. We therefore construct a
representative pre-hospital scenario (transit artifact + rising risk) and let the
actual detector state machine decide alert / no-decision states.

Run: .venv/Scripts/python.exe figures/gen_alert_timeline.py
Output: figures/fig_alert_timeline.{pdf,png}
"""
from pathlib import Path

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Patch

FIG = Path(__file__).resolve().parent
FIG.mkdir(exist_ok=True)

# --- real detector constants (eeg_stroke_pipeline.py: RealTimeConfig) ---
SQI_GATE = 0.55
EMA_BETA = 0.35
THETA_HIGH = 0.80
THETA_LOW = 0.60
COOLDOWN_SEC = 15.0
HOP_SEC = 0.5  # online hop size

plt.rcParams.update({
    "font.family": "serif", "font.serif": ["Times New Roman", "DejaVu Serif"],
    "font.size": 10, "axes.titlesize": 11, "axes.titleweight": "bold",
    "axes.labelsize": 9.5, "legend.fontsize": 8, "legend.frameon": False,
    "figure.dpi": 600, "savefig.dpi": 600, "savefig.bbox": "tight",
    "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "grid.alpha": 0.15,
})
DEEP, TEAL, GOLD, OUR, GRAY = "#264653", "#2A9D8F", "#E9C46A", "#E76F51", "#9AA7AE"


def scenario():
    """Constructed IS-risk and SQI streams for a pre-hospital triage window."""
    t = np.arange(0.0, 40.0, HOP_SEC)
    rng = np.random.default_rng(7)

    # raw ischemic-class probability (the "risk")
    risk = np.full_like(t, 0.12)
    risk += np.where((t >= 8) & (t < 10), 0.8, 0.0)          # spurious spike (artifact)
    ramp = np.clip((t - 10.5) / 3.0, 0, 1)                    # genuine rise
    risk = np.where(t >= 10.5, 0.15 + 0.78 * ramp, risk)
    fall = np.clip((t - 28.0) / 3.5, 0, 1)
    risk = np.where(t >= 28.0, np.maximum(0.12, 0.93 - 0.85 * fall), risk)
    risk = np.clip(risk + rng.normal(0, 0.03, t.size), 0, 1)

    # SQI: good, with a transit-artifact dropout at 8-10 s (electrode movement)
    sqi = np.full_like(t, 0.9) + rng.normal(0, 0.02, t.size)
    sqi = np.where((t >= 8) & (t < 10), 0.30, sqi)            # dropout < gate
    sqi = np.clip(sqi, 0, 1)
    return t, risk, sqi


def run_detector(t, risk, sqi):
    """Replicate RealTimeStrokeDetector: SQI gate -> EMA -> hysteresis -> cooldown."""
    smooth = None
    alert = False
    last_alert_t = -1e9
    status = []       # "no-decision" | "monitor" | "alert"
    smoothed = []
    for ti, p, s in zip(t, risk, sqi):
        if s < SQI_GATE:
            status.append("no-decision")
            smoothed.append(smooth if smooth is not None else p)
            continue
        smooth = p if smooth is None else EMA_BETA * p + (1 - EMA_BETA) * smooth
        smoothed.append(smooth)
        if not alert:
            if smooth >= THETA_HIGH and (ti - last_alert_t) >= COOLDOWN_SEC:
                alert = True
                last_alert_t = ti
        else:
            if smooth < THETA_LOW:
                alert = False
        status.append("alert" if alert else "monitor")
    return np.array(status), np.array(smoothed)


def _spans(t, mask):
    """Yield (t_start, t_end) contiguous spans where mask is True."""
    if not mask.any():
        return
    idx = np.where(mask)[0]
    start = idx[0]
    for a, b in zip(idx[:-1], idx[1:]):
        if b != a + 1:
            yield t[start], t[a] + HOP_SEC
            start = b
    yield t[start], t[idx[-1]] + HOP_SEC


def main():
    t, risk, sqi = scenario()
    status, smooth = run_detector(t, risk, sqi)

    fig, (ax, axs) = plt.subplots(
        2, 1, figsize=(7.4, 3.9), sharex=True,
        gridspec_kw={"height_ratios": [2.5, 1], "hspace": 0.14})

    # shaded state bands
    for a, b in _spans(t, status == "no-decision"):
        ax.axvspan(a, b, color=GRAY, alpha=0.30, lw=0)
    for a, b in _spans(t, status == "alert"):
        ax.axvspan(a, b, color=OUR, alpha=0.13, lw=0)

    # probability traces
    ax.plot(t, risk, color=GRAY, lw=1.0, alpha=0.8, label="Raw P(ischemic)")
    ax.plot(t, smooth, color=DEEP, lw=2.0, label=f"EMA-smoothed (β={EMA_BETA})")
    ax.axhline(THETA_HIGH, color=OUR, ls="--", lw=1.0)
    ax.axhline(THETA_LOW, color=TEAL, ls="--", lw=1.0)
    ax.text(39.6, THETA_HIGH + 0.015, r"$\theta_{high}=0.80$", ha="right",
            fontsize=7.5, color=OUR)
    ax.text(39.6, THETA_LOW - 0.075, r"$\theta_{low}=0.60$", ha="right",
            fontsize=7.5, color=TEAL)
    ax.set_ylim(0, 1.05)
    ax.set_ylabel("P(ischemic)")
    ax.set_title("Alert-state timeline with SQI gating and hysteresis")

    # annotations
    ax.annotate("transit artifact\n→ No-Decision\n(false alert suppressed)",
                xy=(9, 0.5), xytext=(2.0, 0.62), fontsize=7.2, color="#555",
                ha="left", arrowprops=dict(arrowstyle="->", color="#888", lw=0.9))
    ax.annotate("alert raised\n(EMA ≥ θhigh)", xy=(13.5, THETA_HIGH),
                xytext=(15.0, 0.40), fontsize=7.2, color=OUR, ha="left",
                arrowprops=dict(arrowstyle="->", color=OUR, lw=0.9))
    ax.annotate("alert cleared\n(EMA < θlow)", xy=(31.0, THETA_LOW),
                xytext=(23.5, 0.30), fontsize=7.2, color=TEAL, ha="left",
                arrowprops=dict(arrowstyle="->", color=TEAL, lw=0.9))

    legend_items = [
        plt.Line2D([], [], color=GRAY, lw=1.0, label="Raw P(ischemic)"),
        plt.Line2D([], [], color=DEEP, lw=2.0, label="EMA-smoothed"),
        Patch(facecolor=OUR, alpha=0.13, label="Alert: ischemic"),
        Patch(facecolor=GRAY, alpha=0.30, label="No-Decision (low SQI)"),
    ]
    fig.legend(handles=legend_items, loc="lower center",
               bbox_to_anchor=(0.5, -0.075), ncol=4, columnspacing=1.6,
               handlelength=1.6, frameon=False)

    # SQI panel
    axs.plot(t, sqi, color=TEAL, lw=1.6)
    axs.axhline(SQI_GATE, color=GRAY, ls="--", lw=1.0)
    axs.text(39.6, SQI_GATE + 0.03, "SQI gate = 0.55", ha="right",
             fontsize=7.5, color="#666")
    for a, b in _spans(t, status == "no-decision"):
        axs.axvspan(a, b, color=GRAY, alpha=0.30, lw=0)
    axs.set_ylim(0, 1.05)
    axs.set_ylabel("SQI")
    axs.set_xlabel("Time (s)")

    fig.text(0.5, -0.145, "Illustrative pre-hospital scenario run through the system's "
             "real online detector and configured thresholds.",
             ha="center", fontsize=7.2, style="italic", color="#777")

    for ext in ("pdf", "png"):
        for cand in (f"fig_alert_timeline.{ext}", f"fig_alert_timeline_new.{ext}"):
            try:
                fig.savefig(FIG / cand, dpi=600)
                print(f"  -> {cand}")
                break
            except PermissionError:
                continue
    plt.close(fig)


if __name__ == "__main__":
    main()
