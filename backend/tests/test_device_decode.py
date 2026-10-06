"""Unit tests for the BLE EEG frame decoder.

These verify the decode *math* (dtype, endianness, interleaving, scaling, framing
guards) using synthetic frames. The device-specific constants in
BRAIN_LIFE_FOCUS_PLUS are intentionally NOT asserted here — they are filled and
verified against the real device via scripts/ble_probe.py.
"""
from __future__ import annotations

import numpy as np
import pytest

from app.services.device_source import (
    BRAIN_LIFE_FOCUS_PLUS,
    BrainLifeAsciiDecoder,
    EEGFrameDecoder,
)


def _pack_int24_le(vals: list[int]) -> bytes:
    out = bytearray()
    for v in vals:
        u = v & 0xFFFFFF
        out += bytes([u & 0xFF, (u >> 8) & 0xFF, (u >> 16) & 0xFF])
    return bytes(out)


def test_int16_le_interleaved_roundtrip() -> None:
    ch0 = np.array([1, 2, 3], dtype="<i2")
    ch1 = np.array([-1, -2, -3], dtype="<i2")
    inter = np.empty(6, dtype="<i2")
    inter[0::2] = ch0
    inter[1::2] = ch1
    dec = EEGFrameDecoder(dtype="int16", endian="little", n_channels=2, scale_uv=0.5)

    out = dec.decode(inter.tobytes())

    assert out.shape == (2, 3)
    np.testing.assert_allclose(out[0], ch0 * 0.5)
    np.testing.assert_allclose(out[1], ch1 * 0.5)


def test_header_and_trailer_are_skipped() -> None:
    payload = np.array([10, 20, 30, 40], dtype="<i2").tobytes()
    raw = b"\xAB\xCD" + payload + b"\x99"  # 2-byte header, 1-byte trailer
    dec = EEGFrameDecoder(dtype="int16", n_channels=2, header_bytes=2, trailer_bytes=1)

    out = dec.decode(raw)

    assert out.shape == (2, 2)
    np.testing.assert_allclose(out[0], [10, 30])
    np.testing.assert_allclose(out[1], [20, 40])


def test_int24_le_signed_roundtrip() -> None:
    vals = [-1, 100, -32768, 8388607]  # includes max positive 24-bit
    dec = EEGFrameDecoder(dtype="int24", endian="little", n_channels=2)

    out = dec.decode(_pack_int24_le(vals))

    assert out.shape == (2, 2)
    np.testing.assert_allclose(out[0], [-1, -32768])
    np.testing.assert_allclose(out[1], [100, 8388607])


def test_float32_non_interleaved() -> None:
    ch0 = np.array([0.1, 0.2, 0.3], dtype="<f4")
    ch1 = np.array([0.4, 0.5, 0.6], dtype="<f4")
    raw = np.concatenate([ch0, ch1]).astype("<f4").tobytes()
    dec = EEGFrameDecoder(dtype="float32", n_channels=2, interleaved=False)

    out = dec.decode(raw)

    assert out.shape == (2, 3)
    np.testing.assert_allclose(out[0], ch0, rtol=1e-6)
    np.testing.assert_allclose(out[1], ch1, rtol=1e-6)


def test_sample_count_not_divisible_by_channels_raises() -> None:
    raw = np.array([1, 2, 3], dtype="<i2").tobytes()  # 3 samples, 2 channels
    dec = EEGFrameDecoder(dtype="int16", n_channels=2)
    with pytest.raises(ValueError, match="not divisible by n_channels"):
        dec.decode(raw)


def test_int24_payload_not_multiple_of_three_raises() -> None:
    dec = EEGFrameDecoder(dtype="int24", n_channels=2)
    with pytest.raises(ValueError, match="multiple of 3"):
        dec.decode(b"\x00\x01\x02\x03")  # 4 bytes


def test_focus_plus_profile_is_configured_from_vendor_app() -> None:
    # Protocol recovered + live-verified from the vendor app (brain-life-desktop):
    # b"9999" to NUS RX starts a real EEG stream on NUS TX.
    p = BRAIN_LIFE_FOCUS_PLUS
    assert p.configured is True
    assert p.eeg_char_uuid == "6e400003-b5a3-f393-e0a9-e50e24dcca9e"       # NUS TX
    assert p.start_command == b"9999"
    assert p.start_command_uuid == "6e400002-b5a3-f393-e0a9-e50e24dcca9e"  # NUS RX
    assert p.stop_command == b"2200220D"
    assert p.channel_labels == ["AF3", "AF4"]
    assert p.ascii_decoder is not None


def test_ascii_decoder_parses_header_tagged_lines() -> None:
    # One notification carrying interleaved AF3 (0x24) and AF4 (0x26) samples,
    # plus a PPG line (0x25) that must be ignored.
    dec = BrainLifeAsciiDecoder()
    raw = (
        b"\x2408353704\n"   # AF3
        b"\x2608372232\n"   # AF4
        b"\x2500032151\n"   # PPG — ignored
        b"\x2408353705\n"   # AF3
        b"\x2608372233\n"   # AF4
    )
    parsed = dec.parse(raw)
    assert parsed[0x24] == [8353704.0, 8353705.0]
    assert parsed[0x26] == [8372232.0, 8372233.0]
    assert 0x25 not in parsed
    assert dec.channel_labels == ["AF3", "AF4"]
