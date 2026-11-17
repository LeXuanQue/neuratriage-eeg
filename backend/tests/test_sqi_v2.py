"""SQI v2: per-channel, spectrally-aware signal quality with actionable reason codes.

All signals are synthetic so the tests are deterministic and need no dataset.
"""
from __future__ import annotations

import dataclasses

import numpy as np
import pytest
from scipy import signal as sps

import sqi_v2 as S

FS = 256.0
SEC = 4.0
N = int(FS * SEC)
UV = 1e-6  # synthetic signals are built in volts, like the stored datasets


def _colored_noise(rng: np.random.Generator, n: int, exponent: float, knee_hz: float = 1.0) -> np.ndarray:
    """Noise with PSD ~ 1/f^exponent above knee_hz and flat below it.

    The flat part mimics an amplifier high-pass: real EEG does not keep rising below ~0.5 Hz.
    """
    freqs = np.fft.rfftfreq(n, d=1.0 / FS)
    amp = np.maximum(freqs, knee_hz) ** (-exponent / 2.0)
    amp[0] = 0.0
    phases = rng.uniform(0.0, 2.0 * np.pi, size=freqs.size)
    x = np.fft.irfft(amp * np.exp(1j * phases), n=n)
    return x / np.std(x)


def _clean_channel(rng: np.random.Generator, exponent: float = 1.5, alpha: bool = True) -> np.ndarray:
    t = np.arange(N) / FS
    x = 20.0 * _colored_noise(rng, N, exponent)
    if alpha:
        x = x + 12.0 * np.sin(2 * np.pi * 10.0 * t + rng.uniform(0, 2 * np.pi))
    return x * UV


def _clean(n_ch: int = 4, seed: int = 0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return np.stack([_clean_channel(rng) for _ in range(n_ch)])


def _bandpassed_noise(rng: np.random.Generator, band: tuple[float, float]) -> np.ndarray:
    sos = sps.butter(4, list(band), btype="bandpass", fs=FS, output="sos")
    x = sps.sosfiltfilt(sos, rng.standard_normal(N))
    return x / np.std(x)


# --------------------------------------------------------------------- input checks
@pytest.mark.unit
def test_rejects_non_2d_input() -> None:
    with pytest.raises(ValueError, match="2D"):
        S.assess_window(np.zeros(N), FS)


@pytest.mark.unit
def test_rejects_window_shorter_than_minimum() -> None:
    with pytest.raises(ValueError, match="too short"):
        S.assess_window(np.zeros((2, int(FS * 1.0))), FS)


@pytest.mark.unit
def test_rejects_sampling_rate_too_low_for_spectral_fit() -> None:
    with pytest.raises(ValueError, match="sampling rate"):
        S.assess_window(np.zeros((2, 4 * 64)), 64.0)


@pytest.mark.unit
def test_channel_names_must_match_channel_count() -> None:
    with pytest.raises(ValueError, match="channel names"):
        S.assess_window(_clean(2), FS, channel_names=["AF3"])


# --------------------------------------------------------------------- output shape
@pytest.mark.unit
def test_result_is_immutable_and_named() -> None:
    q = S.assess_window(_clean(2), FS, channel_names=["AF3", "AF4"])
    assert [c.name for c in q.channels] == ["AF3", "AF4"]
    with pytest.raises(dataclasses.FrozenInstanceError):
        q.score = 0.0  # type: ignore[misc]
    with pytest.raises(dataclasses.FrozenInstanceError):
        q.channels[0].score = 0.0  # type: ignore[misc]


@pytest.mark.unit
def test_default_channel_names_are_indices() -> None:
    q = S.assess_window(_clean(3), FS)
    assert [c.name for c in q.channels] == ["ch0", "ch1", "ch2"]


# --------------------------------------------------------------------- clean signal
@pytest.mark.unit
def test_clean_eeg_scores_high_with_no_reasons() -> None:
    q = S.assess_window(_clean(4), FS)
    assert q.score >= 0.9
    for ch in q.channels:
        assert ch.reasons == ()
        assert ch.score >= 0.9


@pytest.mark.unit
@pytest.mark.parametrize("exponent", [1.0, 1.5, 2.0])
def test_aperiodic_exponent_recovers_ground_truth(exponent: float) -> None:
    rng = np.random.default_rng(1)
    x = np.stack([_clean_channel(rng, exponent=exponent, alpha=False) for _ in range(2)])
    q = S.assess_window(x, FS)
    for ch in q.channels:
        assert ch.features["aperiodic_exponent"] == pytest.approx(exponent, abs=0.3)
        assert ch.features["aperiodic_r2"] > 0.8


@pytest.mark.unit
def test_alpha_peak_is_reported_but_absence_is_not_penalised() -> None:
    rng = np.random.default_rng(2)
    with_alpha = np.stack([_clean_channel(rng, alpha=True) for _ in range(2)])
    no_alpha = np.stack([_clean_channel(rng, alpha=False) for _ in range(2)])
    qa = S.assess_window(with_alpha, FS)
    qn = S.assess_window(no_alpha, FS)
    assert all(c.features["alpha_peak"] > 0.1 for c in qa.channels)
    assert all(c.features["alpha_peak"] < 0.1 for c in qn.channels)
    assert qn.score >= 0.9


@pytest.mark.unit
def test_scores_do_not_depend_on_storage_unit() -> None:
    x = _clean(3, seed=3)
    x[1] = x[1] + 300 * UV * np.sin(2 * np.pi * 0.2 * np.arange(N) / FS)  # one bad channel
    in_v = S.assess_window(x, FS)
    in_uv = S.assess_window(x / UV, FS)
    assert in_uv.score == pytest.approx(in_v.score, abs=1e-9)
    for a, b in zip(in_v.channels, in_uv.channels):
        assert a.reasons == b.reasons
        for key, value in a.features.items():
            assert b.features[key] == pytest.approx(value, rel=1e-6, abs=1e-9), key


# --------------------------------------------------------------------- artifacts
def _assert_flagged(q: S.WindowQuality, bad: int, reason: str) -> None:
    assert reason in q.channels[bad].reasons, q.channels[bad]
    assert q.worst_channel == bad
    assert q.channels[bad].score < S.CHANNEL_OK
    for i, ch in enumerate(q.channels):
        if i != bad:
            assert ch.score >= 0.9, (i, ch)


@pytest.mark.unit
def test_slow_drift_is_flagged_on_the_drifting_channel() -> None:
    x = _clean(4, seed=4)
    t = np.arange(N) / FS
    x[2] = x[2] + 200 * UV * np.sin(2 * np.pi * 0.15 * t) + 150 * UV * t / SEC
    _assert_flagged(S.assess_window(x, FS), 2, "drift")


@pytest.mark.unit
def test_flat_channel_is_flagged() -> None:
    x = _clean(4, seed=5)
    x[0] = 1e-4 * x[0]
    _assert_flagged(S.assess_window(x, FS), 0, "flat")


@pytest.mark.unit
def test_two_channel_headband_flat_channel_is_flagged() -> None:
    x = _clean(2, seed=6)
    x[1] = 0.0
    q = S.assess_window(x, FS)
    assert "flat" in q.channels[1].reasons
    assert q.worst_channel == 1


@pytest.mark.unit
def test_line_noise_is_flagged() -> None:
    x = _clean(4, seed=7)
    x[3] = x[3] + 60 * UV * np.sin(2 * np.pi * 50.0 * np.arange(N) / FS)
    _assert_flagged(S.assess_window(x, FS), 3, "line_noise")


@pytest.mark.unit
def test_line_noise_at_60hz_is_flagged_when_configured() -> None:
    x = _clean(2, seed=8)
    x[0] = x[0] + 60 * UV * np.sin(2 * np.pi * 60.0 * np.arange(N) / FS)
    q = S.assess_window(x, FS, config=S.SqiV2Config(line_freq=60.0))
    assert "line_noise" in q.channels[0].reasons


@pytest.mark.unit
def test_muscle_artifact_is_flagged() -> None:
    rng = np.random.default_rng(9)
    x = _clean(4, seed=9)
    x[1] = x[1] + 60 * UV * _bandpassed_noise(rng, (40.0, 100.0))
    _assert_flagged(S.assess_window(x, FS), 1, "muscle")


@pytest.mark.unit
def test_clipping_is_flagged() -> None:
    x = _clean(4, seed=10)
    lim = 0.5 * np.max(np.abs(x[2]))
    x[2] = np.clip(x[2], -lim, lim)
    _assert_flagged(S.assess_window(x, FS), 2, "clipping")


@pytest.mark.unit
def test_electrode_pop_transient_is_flagged() -> None:
    x = _clean(4, seed=11)
    t = np.arange(N) / FS
    x[0] = x[0] + 400 * UV * np.exp(-((t - 2.0) ** 2) / (2 * 0.03**2))
    _assert_flagged(S.assess_window(x, FS), 0, "transient")


@pytest.mark.unit
def test_window_score_drops_with_more_bad_channels() -> None:
    t = np.arange(N) / FS
    drift = 200 * UV * np.sin(2 * np.pi * 0.15 * t)
    one = _clean(4, seed=12)
    one[0] += drift
    three = _clean(4, seed=12)
    three[:3] += drift
    assert S.assess_window(three, FS).score < S.assess_window(one, FS).score


# --------------------------------------------------------------------- stroke safety
@pytest.mark.unit
def test_stroke_like_slowing_is_not_gated_like_drift() -> None:
    """Polymorphic delta (1-4 Hz) and a steeper 1/f slope are pathology, not bad contact.

    docs/lit_review.md (R1) requires that SQI v2 does not gate ischemic stroke more than
    controls; this is the synthetic version of that check.
    """
    rng = np.random.default_rng(13)
    chans = [
        _clean_channel(rng, exponent=2.2, alpha=False) + 40 * UV * _bandpassed_noise(rng, (1.0, 4.0))
        for _ in range(4)
    ]
    q = S.assess_window(np.stack(chans), FS)
    assert q.score >= 0.9
    for ch in q.channels:
        assert "drift" not in ch.reasons
        assert ch.features["delta_ratio"] > 0.5


@pytest.mark.unit
@pytest.mark.parametrize("exponent", [2.0, 3.0])
def test_steep_aperiodic_spectrum_down_to_dc_is_not_drift(exponent: float) -> None:
    """Review finding: a raw sub-0.5 Hz variance share grows with the 1/f exponent.

    Drift must be judged against what the channel's own 1/f slope predicts, otherwise a
    steep (slowed) spectrum without a hardware high-pass is gated as bad contact.
    """
    rng = np.random.default_rng(15)
    x = np.stack([20 * UV * _colored_noise(rng, N, exponent, knee_hz=0.01) for _ in range(4)])
    q = S.assess_window(x, FS)
    for ch in q.channels:
        assert "drift" not in ch.reasons, ch
    assert q.score >= 0.85


@pytest.mark.unit
def test_missing_samples_are_reported_as_missing_not_muscle() -> None:
    x = _clean(4, seed=16)
    x[2, 300:700] = np.nan
    q = S.assess_window(x, FS)
    bad = q.channels[2]
    assert bad.reasons[0] == "missing"
    assert "muscle" not in bad.reasons
    assert q.worst_channel == 2
    assert bad.features["missing_fraction"] == pytest.approx(400 / N)


@pytest.mark.unit
def test_all_nan_channel_is_missing() -> None:
    x = _clean(2, seed=17)
    x[0] = np.nan
    q = S.assess_window(x, FS)
    assert q.channels[0].reasons[0] == "missing"
    assert q.channels[0].score == 0.0


# --------------------------------------------------------------------- calibration
@pytest.mark.unit
def test_score_features_matches_assess_window() -> None:
    x = _clean(3, seed=18)
    x[1] = x[1] + 200 * UV * np.sin(2 * np.pi * 0.15 * np.arange(N) / FS)
    q = S.assess_window(x, FS)
    for ch in q.channels:
        score, reasons = S.score_features(ch.features, S.SqiV2Config())
        assert score == pytest.approx(ch.score)
        assert reasons == ch.reasons


@pytest.mark.unit
def test_config_from_dict_restores_tuples_and_ignores_metadata() -> None:
    cfg = S.config_from_dict({"drift_ramp": [0.9, 1.7, 0.6], "line_freq": 60.0, "note": "calibrated on TUAR"})
    assert cfg.drift_ramp == (0.9, 1.7, 0.6)
    assert cfg.line_freq == 60.0
    assert cfg.clip_ramp == S.SqiV2Config().clip_ramp


@pytest.mark.unit
def test_raising_the_drift_start_stops_flagging_mild_drift() -> None:
    x = _clean(2, seed=19)
    x[0] = x[0] + 60 * UV * np.sin(2 * np.pi * 0.2 * np.arange(N) / FS)
    default = S.assess_window(x, FS)
    strict = S.assess_window(x, FS, config=S.config_from_dict({"drift_ramp": [3.0, 4.0, 0.6]}))
    assert "drift" in default.channels[0].reasons
    assert "drift" not in strict.channels[0].reasons


# --------------------------------------------------------------------- guidance
@pytest.mark.unit
@pytest.mark.parametrize("reason", sorted(S.REASON_ADVICE))
def test_every_reason_has_operator_advice(reason: str) -> None:
    advice = S.REASON_ADVICE[reason]
    assert isinstance(advice, str) and len(advice) > 10


@pytest.mark.unit
def test_guidance_names_the_worst_channel_and_its_fix() -> None:
    x = _clean(2, seed=14)
    x[1] = 0.0
    q = S.assess_window(x, FS, channel_names=["AF3", "AF4"])
    tip = S.guidance(q)
    assert tip is not None
    assert tip.channel == "AF4"
    assert tip.reason == "flat"
    assert tip.advice == S.REASON_ADVICE["flat"]


@pytest.mark.unit
def test_guidance_is_none_for_clean_signal() -> None:
    assert S.guidance(S.assess_window(_clean(2), FS)) is None


# --------------------------------------------------------------------- eye movement (advisory)
_QUIET = {"missing_fraction": 0.0, "clip_fraction": 0.0, "drift_excess": 0.0, "line_ratio": 0.0,
          "line_prominence": 1.0, "hf_ratio": 0.01, "aperiodic_exponent": 1.5, "kurtosis": 0.0}


@pytest.mark.unit
def test_eye_reason_is_off_by_default() -> None:
    """It failed its pre-registered E7 criterion on the TUAR test half (docs/paper_outline.md s.7)."""
    _, reasons = S.score_features({**_QUIET, "delta_ratio": 0.95, "alpha_peak": -0.3}, S.SqiV2Config())
    assert "eye" not in reasons


@pytest.mark.unit
def test_eye_reason_fires_on_high_delta_without_alpha() -> None:
    cfg = S.SqiV2Config(eye_reason=True)
    _, reasons = S.score_features({**_QUIET, "delta_ratio": 0.95, "alpha_peak": -0.3}, cfg)
    assert reasons == ("eye",)


@pytest.mark.unit
@pytest.mark.parametrize("delta, alpha", [(0.95, 0.4), (0.6, -0.3), (float("nan"), -0.3)])
def test_eye_reason_needs_both_high_delta_and_no_alpha(delta: float, alpha: float) -> None:
    _, reasons = S.score_features({**_QUIET, "delta_ratio": delta, "alpha_peak": alpha}, S.SqiV2Config(eye_reason=True))
    assert "eye" not in reasons


@pytest.mark.unit
def test_eye_reason_never_changes_the_score() -> None:
    """Weight 0 by design (DG2): high delta without alpha is also what stroke slowing looks like."""
    feats = {**_QUIET, "delta_ratio": 0.95, "alpha_peak": -0.3, "drift_excess": 2.6}
    on = S.score_features(feats, S.SqiV2Config(eye_reason=True))
    off = S.score_features(feats, S.SqiV2Config())
    assert on[0] == off[0]
    assert on[1][-1] == "eye" and on[1][:-1] == off[1]  # listed after every reason that costs score
