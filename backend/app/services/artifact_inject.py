"""Synthetic artifact injection — a DEMO-ONLY control.

When the presenter toggles "inject artifact", each streamed EEG chunk is corrupted
so its Signal-Quality-Index drops below the detector gate and the UI enters the
No-Decision state on demand. This lets the booth/video show the quality-gating /
No-Decision interaction — the core contribution — without waiting for a naturally
low-SQI segment.

It is deliberately NOT part of the ML/decision path: it only degrades the signal
the way a real transit/motion artifact would (broadband high-frequency noise,
amplitude spikes/saturation, and electrode-detachment flatlines), so the SQI
response is faithful rather than a fake "set SQI = 0". The 50 Hz line component is
mostly removed by the SQI preprocessor's notch, so the reliable levers are
``sqi_hf_ratio``, ``sqi_clip`` and ``sqi_flatline`` (see
``eeg_stroke_pipeline.compute_sqi``).
"""
from __future__ import annotations

import numpy as np

_LINE_HZ = 50.0


def apply_synthetic_artifact(chunk, fs, intensity: float = 1.0, seed=None):
    """Return a corrupted copy of ``chunk`` (n_channels, n_samples) that tanks SQI.

    ``intensity`` (>= 0) scales the corruption; ``0`` (or a non-2-D / empty input)
    is a no-op passthrough. ``seed`` makes it deterministic for tests.
    """
    x = np.asarray(chunk, dtype=float)
    if x.ndim != 2 or x.size == 0 or intensity <= 0:
        return x.copy()
    x = x.copy()
    n_ch, n = x.shape
    fs = float(fs) or 256.0
    rng = np.random.default_rng(seed)
    t = np.arange(n) / fs

    scale = float(np.nanstd(x))
    if not np.isfinite(scale) or scale <= 0:
        scale = 1.0
    k = float(intensity)

    # Broadband high-frequency noise -> sqi_hf_ratio (survives the 50 Hz notch).
    x = x + (6.0 * scale * k) * rng.standard_normal(size=x.shape)
    # 50 Hz mains hum -> sqi_line_ratio (mostly notched, cheap to add).
    x = x + (5.0 * scale * k) * np.sin(2.0 * np.pi * _LINE_HZ * t)[None, :]
    # Dense amplitude spikes -> sqi_clip (saturation / clipping).
    n_spikes = max(1, int(0.10 * n))
    for ch in range(n_ch):
        idx = rng.choice(n, size=min(n_spikes, n), replace=False)
        x[ch, idx] += rng.choice([-1.0, 1.0], size=idx.size) * (30.0 * scale * k)
    # Electrode detachment: flatline a fraction of channels -> sqi_flatline.
    n_flat = int(np.ceil(0.4 * n_ch)) if k >= 1.0 else 0
    for ch in range(min(n_flat, n_ch)):
        x[ch, :] = 0.0
    return x


__all__ = ["apply_synthetic_artifact"]
