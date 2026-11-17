"""SQI v2: per-channel, spectrally-aware signal quality with actionable reason codes.

v1 (``eeg_stroke_pipeline.compute_sqi``) scores a whole 1 s window from flatline, clipping,
line and high-frequency ratios. It missed slow drift and poor electrode contact on the real
headband (docs/full_paper_plan.md, R1). v2 works on a longer raw window (default 4 s) and
scores every channel separately, so the interface can say *which* electrode to fix and *how*.

Design rules:

* Every measure is a ratio, a shape statistic or a log-log slope, so the result does not
  depend on whether the recording is stored in V, uV or ADC counts.
* Stroke-like slowing (more 1-4 Hz delta, a steeper 1/f slope) and missing alpha are
  pathology, not artifact, and are never penalised. Drift is the sub-0.5 Hz power *in excess
  of what the channel's own 1/f fit predicts*: a raw sub-0.5 Hz share would grow with the
  exponent and gate slowed EEG as bad contact.
* v1 stays untouched: the deployed model was trained on v1 features.
"""
from __future__ import annotations

from dataclasses import dataclass, fields
from types import MappingProxyType
from typing import Mapping, Optional, Protocol, Sequence, Tuple

import numpy as np
from scipy import signal
from scipy.stats import kurtosis

# Reason codes, in the order the operator should fix them when several apply.
REASON_ADVICE: Mapping[str, str] = MappingProxyType(
    {
        "missing": "Samples are missing: check the wireless link and keep the device close to the receiver.",
        "flat": "No signal: check that the electrode touches the skin and the lead is connected.",
        "clipping": "Amplifier saturates: re-seat the electrode and wait for the signal to settle.",
        "drift": "Slow baseline drift: press the electrode firmly or re-wet it for better contact.",
        "line_noise": "Mains interference: move away from power cables and chargers, check the reference.",
        "muscle": "Muscle noise: ask the patient to relax the jaw and forehead.",
        "transient": "Sudden spikes: keep the cable still and ask the patient to avoid blinking or moving.",
        # Advisory only (weight 0): never lowers the score, see SqiV2Config.eye_delta_min.
        "eye": "Eye movements or blinks: ask the patient to close the eyes gently and keep them still.",
    }
)

# Channel score below which the interface asks the operator to act on that channel.
CHANNEL_OK = 0.7

# A reason is reported once its 0-1 severity ramp passes this point.
REASON_SEVERITY = 0.5

Ramp = Tuple[float, float, float]  # (value where penalty starts, value where it saturates, weight)

_FEATURE_KEYS = (
    "missing_fraction", "clip_fraction", "drift_excess", "line_ratio", "line_prominence",
    "hf_ratio", "aperiodic_exponent", "kurtosis", "delta_ratio", "alpha_peak",
)


@dataclass(frozen=True)
class SqiV2Config:
    line_freq: float = 50.0
    min_window_sec: float = 2.0
    min_fs: float = 100.0
    drift_cutoff_hz: float = 0.5
    broad_band: Tuple[float, float] = (1.0, 35.0)
    delta_band: Tuple[float, float] = (1.0, 4.0)
    hf_band: Tuple[float, float] = (35.0, 70.0)
    alpha_band: Tuple[float, float] = (8.0, 12.0)
    fit_range: Tuple[float, float] = (2.0, 40.0)
    fit_exclude: Tuple[Tuple[float, float], ...] = ((7.0, 14.0),)
    line_halfwidth_hz: float = 1.0
    flat_rel: float = 1e-2  # a channel 40 dB below the median channel counts as flat
    min_line_prominence: float = 4.0
    missing_ramp: Ramp = (0.0, 0.1, 0.8)
    clip_ramp: Ramp = (0.005, 0.05, 0.6)
    # log10(observed sub-0.5 Hz power / power the 1/f fit predicts there). Synthetic check:
    # 1/f^2-3 noise down to DC stays <= 0.3 (p95), slowed EEG ~ -2, real drift >= 0.4.
    drift_ramp: Ramp = (0.4, 1.2, 0.6)
    line_ramp: Ramp = (0.1, 0.5, 0.5)
    hf_ramp: Ramp = (0.3, 1.0, 0.5)
    low_exponent_ramp: Ramp = (0.6, 0.1, 0.5)  # decreasing: a flat (white) spectrum is noise
    kurtosis_ramp: Ramp = (5.0, 20.0, 0.5)
    # Eye movement / blink: high 1-4 Hz share with no alpha above the 1/f fit. Fixed on the TUAR
    # calibration half only (clean-channel 91st and 25th percentiles; docs/paper_outline.md s.7).
    # Stroke slowing looks the same per channel, so this reason has weight 0 (DG2).
    eye_delta_min: float = 0.857
    eye_alpha_max: float = -0.104


@dataclass(frozen=True)
class ChannelQuality:
    name: str
    score: float
    reasons: Tuple[str, ...]  # most severe first
    features: Mapping[str, float]


@dataclass(frozen=True)
class WindowQuality:
    score: float
    channels: Tuple[ChannelQuality, ...]
    worst_channel: int


@dataclass(frozen=True)
class Guidance:
    channel: str
    reason: str
    advice: str


# --------------------------------------------------------------------------- helpers
def _ramp(value: float, start: float, end: float) -> float:
    """0 at ``start``, 1 at ``end`` (works for increasing or decreasing ramps)."""
    if not np.isfinite(value):
        return 0.0
    return float(np.clip((value - start) / (end - start), 0.0, 1.0))


def _band_power(freqs: np.ndarray, psd: np.ndarray, band: Tuple[float, float]) -> float:
    mask = (freqs >= band[0]) & (freqs <= band[1])
    if mask.sum() < 2:
        return 0.0
    return float(np.trapezoid(psd[mask], freqs[mask]))


def _safe_ratio(num: float, den: float) -> float:
    return num / den if den > 0 else 0.0


def _line_band(cfg: SqiV2Config, scale: float = 1.0) -> Tuple[float, float]:
    hw = scale * cfg.line_halfwidth_hz
    return cfg.line_freq - hw, cfg.line_freq + hw


def _validate(window: np.ndarray, fs: float, names: Optional[Sequence[str]], cfg: SqiV2Config) -> None:
    if window.ndim != 2:
        raise ValueError(f"Expected a 2D (channels, samples) window, got shape {window.shape}.")
    if fs < cfg.min_fs:
        raise ValueError(f"sampling rate {fs} Hz is below the {cfg.min_fs} Hz needed for the spectral fit.")
    if window.shape[1] < cfg.min_window_sec * fs:
        raise ValueError(f"Window too short: {window.shape[1] / fs:.2f} s < {cfg.min_window_sec} s.")
    if names is not None and len(names) != window.shape[0]:
        raise ValueError(f"Got {len(names)} channel names for {window.shape[0]} channels.")


# --------------------------------------------------------------------------- features
def _drift_measures(x: np.ndarray, fs: float, slope: float, intercept: float, cfg: SqiV2Config) -> Tuple[float, float]:
    """(sub-cutoff variance share, log10 excess of that power over the 1/f extrapolation)."""
    total = float(np.var(x))
    if total <= 0:
        return 0.0, float("nan")
    sos = signal.butter(2, cfg.drift_cutoff_hz, btype="lowpass", fs=fs, output="sos")
    slow = float(np.var(signal.sosfiltfilt(sos, x)))
    if not np.isfinite(slope) or slow <= 0:
        return slow / total, float("nan")
    f_lo = fs / x.size  # lowest frequency the window resolves
    f = np.linspace(f_lo, cfg.drift_cutoff_hz, 200)
    predicted = float(np.trapezoid(10.0**intercept * f**slope, f))
    excess = np.log10(slow / predicted) if predicted > 0 else float("nan")
    return slow / total, float(excess)


def _aperiodic_fit(freqs: np.ndarray, psd: np.ndarray, fs: float, cfg: SqiV2Config) -> Tuple[float, float, float, float]:
    """(exponent, r2, slope, intercept) of log10 PSD vs log10 f with peaks excluded."""
    hi = min(cfg.fit_range[1], fs / 2 - 1.0)
    mask = (freqs >= cfg.fit_range[0]) & (freqs <= hi) & (psd > 0)
    for lo_ex, hi_ex in tuple(cfg.fit_exclude) + (_line_band(cfg, 2.0),):
        mask &= ~((freqs >= lo_ex) & (freqs <= hi_ex))
    if mask.sum() < 5:
        nan = float("nan")
        return nan, nan, nan, nan
    lf, lp = np.log10(freqs[mask]), np.log10(psd[mask])
    slope, intercept = np.polyfit(lf, lp, 1)
    resid = lp - (slope * lf + intercept)
    ss_tot = float(np.sum((lp - lp.mean()) ** 2))
    r2 = 1.0 - float(np.sum(resid**2)) / ss_tot if ss_tot > 0 else 0.0
    return float(-slope), r2, float(slope), float(intercept)


def _alpha_peak(freqs: np.ndarray, psd: np.ndarray, slope: float, intercept: float, cfg: SqiV2Config) -> float:
    """Mean log10 excess over the aperiodic fit inside the alpha band (about 0 when absent)."""
    mask = (freqs >= cfg.alpha_band[0]) & (freqs <= cfg.alpha_band[1]) & (psd > 0)
    if not mask.any() or not np.isfinite(slope):
        return float("nan")
    fitted = slope * np.log10(freqs[mask]) + intercept
    return float(np.mean(np.log10(psd[mask]) - fitted))


def _line_measures(freqs: np.ndarray, psd: np.ndarray, broad: float, cfg: SqiV2Config) -> Tuple[float, float]:
    """(share of broadband power in the mains band, peak height over the flanking density)."""
    f0, hw = cfg.line_freq, cfg.line_halfwidth_hz
    if f0 + 6 * hw >= freqs[-1]:
        return 0.0, 0.0
    in_band = (freqs >= f0 - hw) & (freqs <= f0 + hw)
    flanks = ((freqs >= f0 - 6 * hw) & (freqs < f0 - 3 * hw)) | ((freqs > f0 + 3 * hw) & (freqs <= f0 + 6 * hw))
    share = _safe_ratio(_band_power(freqs, psd, _line_band(cfg)), broad)
    flank_density = float(np.median(psd[flanks])) if flanks.any() else 0.0
    prominence = _safe_ratio(float(np.max(psd[in_band])), flank_density) if in_band.any() else 0.0
    return share, prominence


def _clip_fraction(x: np.ndarray) -> float:
    """Share of samples sitting on the window's own min or max (amplifier rail)."""
    top, bottom = float(np.max(x)), float(np.min(x))
    span = top - bottom
    if span <= 0:
        return 0.0
    tol = 1e-6 * span
    return float(np.mean((x >= top - tol) | (x <= bottom + tol)))


def _hf_power(freqs: np.ndarray, psd: np.ndarray, fs: float, cfg: SqiV2Config) -> float:
    """High-frequency power with the mains band removed (mains is scored on its own)."""
    hi = min(cfg.hf_band[1], fs / 2 - 1.0)
    power = _band_power(freqs, psd, (cfg.hf_band[0], hi))
    if cfg.hf_band[0] < cfg.line_freq < hi:
        power -= _band_power(freqs, psd, _line_band(cfg, 2.0))
    return max(power, 0.0)


def channel_features(x: np.ndarray, fs: float, config: Optional[SqiV2Config] = None) -> dict:
    """Unit-free quality features of one raw channel (also used by the TUAR evaluation)."""
    cfg = config or SqiV2Config()
    x = np.asarray(x, dtype=float)
    x = x - np.mean(x)
    nperseg = int(round(fs))  # 1 Hz bins, ~7 segments in 4 s: steadier than 0.5 Hz bins
    freqs, psd = signal.welch(x, fs=fs, nperseg=nperseg, noverlap=nperseg // 2)
    broad = _band_power(freqs, psd, cfg.broad_band)
    exponent, r2, slope, intercept = _aperiodic_fit(freqs, psd, fs, cfg)
    line_share, line_prominence = _line_measures(freqs, psd, broad, cfg)
    drift_ratio, drift_excess = _drift_measures(x, fs, slope, intercept, cfg)
    return {
        "drift_ratio": drift_ratio,
        "drift_excess": drift_excess,
        "delta_ratio": _safe_ratio(_band_power(freqs, psd, cfg.delta_band), broad),
        "hf_ratio": _safe_ratio(_hf_power(freqs, psd, fs, cfg), broad),
        "line_ratio": line_share,
        "line_prominence": line_prominence,
        "aperiodic_exponent": exponent,
        "aperiodic_r2": r2,
        "alpha_peak": _alpha_peak(freqs, psd, slope, intercept, cfg),
        "kurtosis": float(kurtosis(x, fisher=True, bias=True)),
        "clip_fraction": _clip_fraction(x),
    }


# --------------------------------------------------------------------------- scoring
def config_from_dict(values: Mapping[str, object]) -> SqiV2Config:
    """Build a config from JSON-style values (lists -> tuples); unknown keys are ignored."""
    known = {f.name for f in fields(SqiV2Config)}
    kwargs = {}
    for key, value in values.items():
        if key not in known:
            continue
        if isinstance(value, list):
            value = tuple(tuple(v) if isinstance(v, list) else v for v in value)
        kwargs[key] = value
    return SqiV2Config(**kwargs)


def _severities(features: Mapping[str, float], cfg: SqiV2Config) -> dict:
    """(0-1 severity, weight) per reason; penalty = severity * weight."""
    f = {k: features.get(k, float("nan")) for k in _FEATURE_KEYS}
    has_line_peak = f["line_prominence"] >= cfg.min_line_prominence
    # Muscle has two signatures (excess 35-70 Hz power, or a whitened spectrum); the
    # stronger weighted one counts, re-expressed as a 0-1 severity of the larger weight.
    muscle = max(
        cfg.hf_ramp[2] * _ramp(f["hf_ratio"], *cfg.hf_ramp[:2]),
        cfg.low_exponent_ramp[2] * _ramp(f["aperiodic_exponent"], *cfg.low_exponent_ramp[:2]),
    )
    muscle_weight = max(cfg.hf_ramp[2], cfg.low_exponent_ramp[2])
    return {
        "missing": (_ramp(f["missing_fraction"], *cfg.missing_ramp[:2]), cfg.missing_ramp[2]),
        "clipping": (_ramp(f["clip_fraction"], *cfg.clip_ramp[:2]), cfg.clip_ramp[2]),
        "drift": (_ramp(f["drift_excess"], *cfg.drift_ramp[:2]), cfg.drift_ramp[2]),
        "line_noise": (_ramp(f["line_ratio"], *cfg.line_ramp[:2]) if has_line_peak else 0.0, cfg.line_ramp[2]),
        "muscle": (muscle / muscle_weight, muscle_weight),
        "transient": (_ramp(f["kurtosis"], *cfg.kurtosis_ramp[:2]), cfg.kurtosis_ramp[2]),
        "eye": (float(f["delta_ratio"] >= cfg.eye_delta_min and f["alpha_peak"] <= cfg.eye_alpha_max), 0.0),
    }


def _fill_gaps(x: np.ndarray) -> Tuple[np.ndarray, float]:
    """Linearly interpolate non-finite samples; return (filled, missing fraction)."""
    bad = ~np.isfinite(x)
    frac = float(bad.mean())
    if frac == 0.0 or frac == 1.0:
        return (x if frac == 0.0 else np.zeros_like(x)), frac
    idx = np.arange(x.size)
    filled = x.copy()
    filled[bad] = np.interp(idx[bad], idx[~bad], x[~bad])
    return filled, frac


class ChannelScorer(Protocol):
    """Anything that turns SQI v2 features into a 0-1 channel score (``sqi_learned.LearnedScorer``)."""

    def channel_score(self, features: Mapping[str, float]) -> float: ...


def _strongest_reason(features: Mapping[str, float], cfg: SqiV2Config) -> Tuple[str, ...]:
    """The rule with the largest weighted penalty, if any rule penalises the channel at all."""
    sev = _severities(features, cfg)
    weighted = {r: s * w for r, (s, w) in sev.items() if np.isfinite(s * w) and s * w > 0}
    return (max(weighted, key=weighted.get),) if weighted else ()


def _score_channel(
    name: str, x: np.ndarray, missing: float, is_flat: bool, fs: float, cfg: SqiV2Config,
    scorer: Optional[ChannelScorer] = None,
) -> ChannelQuality:
    if missing >= 1.0:
        return ChannelQuality(name=name, score=0.0, reasons=("missing",), features=MappingProxyType({"missing_fraction": 1.0}))
    if is_flat:
        return ChannelQuality(name=name, score=0.0, reasons=("flat",), features=MappingProxyType({"missing_fraction": missing}))
    feats = {**channel_features(x, fs, cfg), "missing_fraction": missing}
    score, reasons = score_features(feats, cfg)
    if scorer is not None:
        score = float(scorer.channel_score(feats))
        if score < CHANNEL_OK and not reasons:
            reasons = _strongest_reason(feats, cfg)  # a channel marked bad must say what to fix
    return ChannelQuality(name=name, score=score, reasons=reasons, features=MappingProxyType(feats))


def score_features(features: Mapping[str, float], config: SqiV2Config) -> Tuple[float, Tuple[str, ...]]:
    """Channel score and reasons from precomputed features (lets a cached run be re-scored
    with a calibrated config). Flat / all-missing channels are handled by the caller."""
    sev = _severities(features, config)
    weighted = {reason: s * w for reason, (s, w) in sev.items()}
    score = float(np.clip(1.0 - sum(weighted.values()), 0.0, 1.0))
    flagged = sorted((r for r, (s, _) in sev.items() if s >= REASON_SEVERITY), key=lambda r: -weighted[r])
    return score, tuple(flagged)


def assess_window(
    window: np.ndarray,
    fs: float,
    channel_names: Optional[Sequence[str]] = None,
    config: Optional[SqiV2Config] = None,
    scorer: Optional[ChannelScorer] = None,
) -> WindowQuality:
    """Score each channel of a raw ``(channels, samples)`` window and the window as a whole.

    With ``scorer`` the channel score comes from it (the TUAR-fitted model); reasons always
    come from the rules."""
    cfg = config or SqiV2Config()
    x = np.asarray(window, dtype=float)
    _validate(x, fs, channel_names, cfg)
    names = list(channel_names) if channel_names is not None else [f"ch{i}" for i in range(x.shape[0])]
    filled = [_fill_gaps(row) for row in x]
    x = np.stack([f for f, _ in filled])
    missing = [m for _, m in filled]

    stds = np.std(x, axis=1)
    present = np.array([m < 1.0 for m in missing])
    ref = float(np.median(stds[present])) if present.any() else 0.0
    flat = (stds <= cfg.flat_rel * ref) if ref > 0 else np.ones(stds.shape, dtype=bool)
    flat = flat | (stds == 0)

    channels = tuple(
        _score_channel(names[i], x[i], missing[i], bool(flat[i]), fs, cfg, scorer) for i in range(x.shape[0])
    )
    scores = np.array([c.score for c in channels])
    return WindowQuality(score=float(scores.mean()), channels=channels, worst_channel=int(np.argmin(scores)))


def guidance(quality: WindowQuality) -> Optional[Guidance]:
    """The single most useful fix for the operator, or None when no channel needs action."""
    worst = quality.channels[quality.worst_channel]
    if not worst.reasons or worst.score >= CHANNEL_OK:
        return None
    reason = worst.reasons[0]
    return Guidance(channel=worst.name, reason=reason, advice=REASON_ADVICE[reason])
