"""Generate a clean, sharp, labelled schematic of the NeuraTriage operator
interface (glass-box panel) for the 2-page abstract. Vector-quality matplotlib
render, not a screenshot, so it stays crisp at print size."""
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, Rectangle
import pathlib

OUT = pathlib.Path(__file__).resolve().parent
INK = "#1f2a33"; MUT = "#6b7580"; TEAL = "#1C6E7E"; CRIM = "#C0553A"; AMB = "#C0892F"
HAIR = "#d7d2c8"; PANEL = "#ffffff"; BG = "#f4f2ec"

plt.rcParams.update({
    "font.family": "DejaVu Sans", "font.size": 9, "axes.edgecolor": HAIR,
    "axes.linewidth": 0.9, "text.color": INK, "axes.labelcolor": INK,
    "xtick.color": MUT, "ytick.color": MUT,
})

THI, TLO, GATE = 0.80, 0.60, 0.55
fig = plt.figure(figsize=(9.2, 4.7), dpi=440)
fig.patch.set_facecolor(BG)
gs = fig.add_gridspec(2, 2, width_ratios=[2.15, 1.0], height_ratios=[2.5, 1.0],
                      hspace=0.32, wspace=0.20,
                      left=0.065, right=0.975, top=0.86, bottom=0.11)

# ---- synthetic session (EMA-smoothed, as the system displays it) ----
t = np.linspace(0, 40, 600)
rng = np.random.default_rng(7)

def ema(x, a=0.06):
    y = np.empty_like(x); y[0] = x[0]
    for i in range(1, len(x)):
        y[i] = a * x[i] + (1 - a) * y[i - 1]
    return y

base = 0.27 + 0.62 / (1 + np.exp(-(t - 14) / 1.7)) - 0.62 / (1 + np.exp(-(t - 29) / 1.7))
p_disp = np.clip(ema(base + 0.03 * rng.standard_normal(t.size), 0.05), 0.03, 0.97)
sqi = ema(0.85 + 0.02 * rng.standard_normal(t.size), 0.12)
nod = (t >= 7.0) & (t <= 10.2)                      # low-SQI No-Decision window
sqi = np.where(nod, 0.30, sqi)
sqi = ema(sqi, 0.35)

# ===== main monitor: P(ischemic) =====
ax = fig.add_subplot(gs[0, 0]); ax.set_facecolor(PANEL)
ax.axhspan(THI, 1.0, color=CRIM, alpha=0.06)
ax.axhline(THI, color=CRIM, lw=1.2, ls="--"); ax.axhline(TLO, color=AMB, lw=1.2, ls="--")
ax.axvspan(7.2, 10.2, color=MUT, alpha=0.16)
alert = p_disp >= THI
ax.plot(t, p_disp, color=INK, lw=1.8)
ax.fill_between(t, THI, p_disp, where=alert, color=CRIM, alpha=0.22)
ax.text(39.4, THI + 0.015, r"$\theta_{high}=0.80$", ha="right", va="bottom", color=CRIM, fontsize=8)
ax.text(39.4, TLO - 0.075, r"$\theta_{low}=0.60$", ha="right", va="top", color=AMB, fontsize=8)
ax.text(8.7, 0.12, "No-Decision\n(low SQI)", ha="center", va="bottom", color=MUT, fontsize=7.5)
ax.annotate("stable ALERT\n(hysteresis + cooldown)", xy=(22, 0.9), xytext=(24.5, 0.66),
            fontsize=7.5, color=CRIM, ha="left",
            arrowprops=dict(arrowstyle="->", color=CRIM, lw=1))
ax.set_ylim(0, 1); ax.set_xlim(0, 40); ax.set_ylabel("P(ischemic)")
ax.set_xticklabels([]); ax.set_yticks([0, 0.5, 1.0])
ax.set_title("Live risk stream", loc="left", fontsize=9.5, fontweight="bold", color=INK, pad=4)

# ===== SQI strip =====
axq = fig.add_subplot(gs[1, 0]); axq.set_facecolor(PANEL)
axq.axhline(GATE, color=TEAL, lw=1.1, ls=":")
axq.plot(t, sqi, color=TEAL, lw=1.5)
axq.axvspan(7.2, 10.2, color=MUT, alpha=0.16)
axq.text(39.4, GATE + 0.03, "SQI gate = 0.55", ha="right", va="bottom", color=TEAL, fontsize=7.5)
axq.set_ylim(0, 1); axq.set_xlim(0, 40); axq.set_ylabel("SQI"); axq.set_xlabel("time (s)")
axq.set_yticks([0, 0.5, 1.0])

# ===== right: glass-box "why this alert" =====
axg = fig.add_subplot(gs[:, 1]); axg.set_facecolor(PANEL)
axg.set_xlim(0, 1); axg.set_ylim(0, 1); axg.set_xticks([]); axg.set_yticks([])
axg.set_title("Glass-box: why this alert", loc="left", fontsize=9.5, fontweight="bold", color=INK, pad=4)
def chip(x, y, w, h, label, val, c):
    axg.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.006,rounding_size=0.03",
                                 fc="#eef4f4", ec=HAIR, lw=0.8))
    axg.text(x + 0.03, y + h/2, label, va="center", ha="left", fontsize=7.2, color=MUT)
    axg.text(x + w - 0.03, y + h/2, val, va="center", ha="right", fontsize=8.2, color=c, fontweight="bold")
chip(0.05, 0.86, 0.90, 0.085, "State", "ALERT · ischemic", CRIM)
chip(0.05, 0.76, 0.90, 0.085, "Source", "live headband", TEAL)
chip(0.05, 0.66, 0.90, 0.085, "SQI", "0.84  (usable)", TEAL)
axg.text(0.05, 0.60, "Top contributing features (SHAP)", fontsize=7.6, color=MUT, va="center")
feats = ["Fuzzy asym. index", "MFDFA width", "ApEn (right)", "Hemispheric asym."]
vals = [0.31, 0.24, 0.18, 0.11]
y0 = 0.485; bh = 0.055; step = 0.118
for i, (f, v) in enumerate(zip(feats, vals)):
    yy = y0 - i * step
    axg.text(0.05, yy + bh + 0.012, f, fontsize=6.9, color=INK, va="bottom")
    axg.add_patch(Rectangle((0.05, yy), 0.60 * v / max(vals), bh, fc=TEAL, ec="none", alpha=0.85))
    axg.text(0.95, yy + bh/2, f"{v:.2f}", fontsize=7.0, color=MUT, va="center", ha="right")

fig.suptitle("NeuraTriage operator interface", x=0.065, ha="left", fontsize=12,
             fontweight="bold", color=INK, y=0.965)
fig.text(0.065, 0.915, "Continuous risk stream with hysteresis, SQI gate and No-Decision band, "
         "an alert-state readout, and an inspectable feature panel.", ha="left", fontsize=8, color=MUT)

for ext in ("png", "pdf"):
    fig.savefig(OUT / f"fig_interface.{ext}", dpi=440, facecolor=BG, bbox_inches="tight")
    print("  ->", f"fig_interface.{ext}")
print("Done.")
