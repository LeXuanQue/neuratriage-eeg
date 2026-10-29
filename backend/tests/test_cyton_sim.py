"""Tests for the OpenBCI Cyton simulator (ADS1299 physics + 33-byte wire format).

The wire format is decoded with the existing ``EEGFrameDecoder`` (``CYTON_DECODER``),
so these tests also prove the real-device decode path works on simulated bytes.
"""
from __future__ import annotations

import numpy as np
import pytest

from app.services.channel_mapper import DEVICE_PRESETS
from app.services.cyton_sim import (
    CYTON_DECODER,
    CYTON_FS,
    CYTON_SCALE_UV,
    FULL_SCALE_UV,
    PACKET_SIZE,
    CytonSimConfig,
    count_dropped,
    encode_packet,
    encode_stream,
    render_cyton_signal,
    split_packets,
)
from eeg_stroke_pipeline import DEFAULT_CHANNELS, canonicalize_channel_name

pytestmark = pytest.mark.unit


def _blank(fs: int, seconds: int) -> np.ndarray:
    return np.zeros((len(DEFAULT_CHANNELS), fs * seconds))


# ── wire format ──────────────────────────────────────────────────────────────


def test_scale_matches_ads1299_at_gain_24() -> None:
    assert CYTON_FS == 250
    assert CYTON_SCALE_UV == pytest.approx(0.02235, rel=1e-3)
    assert FULL_SCALE_UV == pytest.approx(187_500.0)


def test_packet_layout_is_33_bytes_with_header_counter_footer() -> None:
    pkt = encode_packet(7, np.zeros(8))

    assert len(pkt) == PACKET_SIZE == 33
    assert pkt[0] == 0xA0
    assert pkt[1] == 7
    assert pkt[-1] == 0xC0


def test_packet_roundtrip_within_one_lsb() -> None:
    vals = np.array([0.0, 1.0, -1.0, 50.3, -120.7, 1000.0, -5000.0, 12345.6])

    out = CYTON_DECODER.decode(encode_packet(0, vals))

    assert out.shape == (8, 1)
    np.testing.assert_allclose(out[:, 0], vals, atol=CYTON_SCALE_UV)


def test_packet_clips_at_adc_full_scale() -> None:
    out = CYTON_DECODER.decode(encode_packet(0, np.full(8, 1e6)))

    assert np.all(out <= FULL_SCALE_UV)
    assert np.all(out > 0.999 * FULL_SCALE_UV)


def test_stream_counter_wraps_at_256() -> None:
    pkts, rest, skipped = split_packets(encode_stream(np.zeros((8, 300))))

    assert len(pkts) == 300 and rest == b"" and skipped == 0
    assert [p[1] for p in pkts[254:258]] == [254, 255, 0, 1]


def test_split_resyncs_after_garbage_and_keeps_partial_tail() -> None:
    stream = encode_stream(np.zeros((8, 3)))

    pkts, rest, skipped = split_packets(b"\x01\x02\xa0junk" + stream + stream[:10])

    assert len(pkts) == 3
    assert rest == stream[:10]
    assert skipped > 0


def test_count_dropped_detects_gaps_across_wrap() -> None:
    assert count_dropped([253, 254, 255, 0, 1]) == 0
    assert count_dropped([10, 11, 14]) == 2
    assert count_dropped([255, 2]) == 2


# ── device physics ───────────────────────────────────────────────────────────


def test_render_selects_montage_in_order_and_resamples_to_250() -> None:
    fs_in = 256
    data = np.vstack([np.full(fs_in * 4, float(i)) for i in range(len(DEFAULT_CHANNELS))])
    cfg = CytonSimConfig(montage=("C4", "F3"), noise_uv_rms=0.0)

    out, labels = render_cyton_signal(data, fs_in, list(DEFAULT_CHANNELS), cfg)

    assert labels == ["C4", "F3"]
    assert out.shape == (2, 1000)
    np.testing.assert_allclose(out[0, 50:-50], DEFAULT_CHANNELS.index("C4"), atol=CYTON_SCALE_UV)
    np.testing.assert_allclose(out[1, 50:-50], DEFAULT_CHANNELS.index("F3"), atol=CYTON_SCALE_UV)


def test_render_accepts_10_10_aliases() -> None:
    cfg = CytonSimConfig(montage=("T7", "T8"), noise_uv_rms=0.0)

    _, labels = render_cyton_signal(_blank(256, 2), 256, list(DEFAULT_CHANNELS), cfg)

    assert labels == ["T7", "T8"]


def test_render_missing_channel_raises() -> None:
    cfg = CytonSimConfig(montage=("PZ",))

    with pytest.raises(ValueError, match="PZ"):
        render_cyton_signal(_blank(256, 2), 256, list(DEFAULT_CHANNELS), cfg)


def test_render_output_is_quantized_to_adc_lsb() -> None:
    cfg = CytonSimConfig(montage=("F3", "F4"), noise_uv_rms=3.0, seed=1)

    out, _ = render_cyton_signal(_blank(256, 2), 256, list(DEFAULT_CHANNELS), cfg)

    codes = out / CYTON_SCALE_UV
    np.testing.assert_allclose(codes, np.round(codes), atol=1e-6)


def test_noise_is_seeded_and_has_requested_rms() -> None:
    cfg = CytonSimConfig(montage=("F3", "F4"), noise_uv_rms=2.0, seed=42)

    a, _ = render_cyton_signal(_blank(256, 8), 256, list(DEFAULT_CHANNELS), cfg)
    b, _ = render_cyton_signal(_blank(256, 8), 256, list(DEFAULT_CHANNELS), cfg)

    np.testing.assert_array_equal(a, b)
    assert a.std() == pytest.approx(2.0, rel=0.1)


def test_mains_interference_adds_50hz_peak() -> None:
    cfg = CytonSimConfig(montage=("C3",), noise_uv_rms=0.0, mains_uv=10.0, mains_hz=50.0)

    out, _ = render_cyton_signal(_blank(256, 8), 256, list(DEFAULT_CHANNELS), cfg)

    spec = np.abs(np.fft.rfft(out[0])) * 2 / out.shape[1]
    freqs = np.fft.rfftfreq(out.shape[1], 1 / CYTON_FS)
    assert freqs[np.argmax(spec)] == pytest.approx(50.0, abs=0.2)
    assert spec.max() == pytest.approx(10.0, rel=0.05)


def test_railed_channel_is_pinned_at_full_scale() -> None:
    cfg = CytonSimConfig(montage=("F3", "F4"), noise_uv_rms=1.0, railed_channels=("F3",))

    out, _ = render_cyton_signal(_blank(256, 2), 256, list(DEFAULT_CHANNELS), cfg)

    assert np.all(np.abs(out[0]) > 0.999 * FULL_SCALE_UV)
    assert np.all(np.abs(out[1]) < 100.0)


def test_rendered_signal_survives_the_wire_roundtrip() -> None:
    cfg = CytonSimConfig(montage=tuple(DEFAULT_CHANNELS[:8]), noise_uv_rms=5.0, seed=3)
    sig, _ = render_cyton_signal(_blank(256, 2), 256, list(DEFAULT_CHANNELS), cfg)

    pkts, _, _ = split_packets(encode_stream(sig))
    back = np.hstack([CYTON_DECODER.decode(p) for p in pkts])

    np.testing.assert_allclose(back, sig, atol=CYTON_SCALE_UV)


# ── the montage chosen for stroke screening ─────────────────────────────────


def test_cyton_preset_montage_fits_board_and_model() -> None:
    preset = DEVICE_PRESETS["openbci_cyton"]
    chans = [canonicalize_channel_name(c) for c in preset["channels"]]

    assert preset["fs"] == CYTON_FS
    assert len(chans) == 8, "Cyton has exactly 8 input channels"
    assert len(set(chans)) == 8, "montage has duplicate electrodes"
    missing = [c for c in chans if c not in DEFAULT_CHANNELS]
    assert not missing, f"not in the model's training montage: {missing}"
