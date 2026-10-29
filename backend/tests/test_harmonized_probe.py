"""Tests for scripts/harmonized_feature_probe.py (acquisition-chain harmonization)."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import harmonized_feature_probe as hfp  # noqa: E402


def test_window_ends_are_evenly_spread_bounded_and_valid() -> None:
    ends = hfp.select_window_ends(n_samples=256 * 60, min_len=1024, step=128, cap=12)

    assert len(ends) == 12
    assert ends[0] >= 1024 and ends[-1] <= 256 * 60
    assert all((e - 1024) % 128 == 0 for e in ends)          # on the normal hop grid
    assert np.all(np.diff(ends) > 0)


def test_window_ends_short_recording_returns_all_available() -> None:
    ends = hfp.select_window_ends(n_samples=1024 + 3 * 128, min_len=1024, step=128, cap=12)

    assert ends == [1024, 1152, 1280, 1408]


def test_variant_config_sets_band_and_keeps_everything_else() -> None:
    base = hfp.variant_config("baseline")
    harm = hfp.variant_config("harm_2_30")

    assert (base.bandpass_low, base.bandpass_high) == (1.0, 35.0)
    assert (harm.bandpass_low, harm.bandpass_high) == (2.0, 30.0)
    assert base.bandpass_order == 4 and harm.bandpass_order == 8
    assert harm.sqi_threshold == base.sqi_threshold           # identical gate -> same windows
    assert harm.channels == base.channels


def _multichannel(seed: int = 0, n_ch: int = 18, n: int = 256 * 60) -> np.ndarray:
    """Independent channels with distinct spectral shapes (filtered white noise)."""
    from scipy.signal import butter, sosfilt
    rng = np.random.default_rng(seed)
    out = np.empty((n_ch, n))
    for c in range(n_ch):
        sos = butter(2, [2 + c * 0.5, 20 + c], btype="bandpass", fs=256, output="sos")
        out[c] = sosfilt(sos, rng.standard_normal(n))
    return out


def test_common_whitening_cancels_a_transfer_function_shared_by_all_channels() -> None:
    """The 'device' (same filter on every channel) must not change the whitened SPECTRUM.

    Whitening corrects |H(f)| only; a causal device filter's phase shift remains, so
    the guarantee is spectral, not sample-by-sample.
    """
    from scipy.signal import butter, sosfilt, welch
    s = _multichannel()
    device = butter(2, 10, btype="lowpass", fs=256, output="sos")   # strong tilt across the band
    y = sosfilt(device, s, axis=1)

    def log_psd(x: np.ndarray) -> np.ndarray:
        f, p = welch(x, fs=256, nperseg=512, axis=1)
        return 10 * np.log10(p[:, (f >= 2) & (f <= 28)])

    ws = hfp.whiten_common_spectrum(s, fs=256.0, band=(1.0, 30.0))
    wy = hfp.whiten_common_spectrum(y, fs=256.0, band=(1.0, 30.0))

    whitened_gap_db = np.mean(np.abs(log_psd(ws) - log_psd(wy)))
    raw_gap_db = np.mean(np.abs(log_psd(s) - log_psd(y)))
    assert raw_gap_db > 3.0                                       # the device really changes spectra
    assert whitened_gap_db < 1.0


def test_common_whitening_keeps_a_focal_channel_difference() -> None:
    """A delta excess on one channel (focal slowing) must survive common whitening
    but be erased by per-channel whitening."""
    from scipy.signal import welch
    s = _multichannel(seed=1)
    t = np.arange(s.shape[1]) / 256.0
    s[3] += 3.0 * np.std(s[3]) * np.sin(2 * np.pi * 3.0 * t)       # focal 3 Hz excess on ch 3

    def delta_share(x: np.ndarray, c: int) -> float:
        f, p = welch(x[c], fs=256, nperseg=512)
        return float(p[(f >= 2) & (f <= 4)].sum() / p[(f >= 1) & (f <= 30)].sum())

    common = hfp.whiten_common_spectrum(s, fs=256.0, band=(1.0, 30.0))
    per_ch = hfp.whiten_common_spectrum(s, fs=256.0, band=(1.0, 30.0), per_channel=True)

    others = [c for c in range(s.shape[0]) if c != 3]
    focal_vs_rest_common = delta_share(common, 3) / np.mean([delta_share(common, c) for c in others])
    focal_vs_rest_perch = delta_share(per_ch, 3) / np.mean([delta_share(per_ch, c) for c in others])
    assert focal_vs_rest_common > 3.0
    assert focal_vs_rest_perch < 1.5


def test_harmonized_filter_removes_out_of_band_power() -> None:
    """A 45 Hz tone (where the sources differ most) must be suppressed by harm_2_30."""
    from eeg_stroke_pipeline import preprocess_eeg

    fs, t = 256.0, np.arange(256 * 20) / 256.0
    # Distinct per-channel gains, otherwise common-average referencing cancels everything.
    gains = np.linspace(0.5, 1.5, 18)[:, None]
    x = gains * (np.sin(2 * np.pi * 45 * t) + np.sin(2 * np.pi * 10 * t))

    out_base = preprocess_eeg(x, fs, hfp.variant_config("baseline"))
    out_harm = preprocess_eeg(x, fs, hfp.variant_config("harm_2_30"))

    def p45(y: np.ndarray) -> float:
        spec = np.abs(np.fft.rfft(y[0, 1024:])) ** 2
        f = np.fft.rfftfreq(y.shape[1] - 1024, 1 / fs)
        return float(spec[np.argmin(np.abs(f - 45))])

    assert p45(out_harm) < 0.1 * p45(out_base)
