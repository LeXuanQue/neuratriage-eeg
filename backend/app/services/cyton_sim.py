"""OpenBCI Cyton simulator — ADS1299 signal physics + the 33-byte serial wire format.

Lets the stroke-screening montage and the live path be exercised before the board
exists. Two layers, both pure and unit-tested (backend/tests/test_cyton_sim.py):

* ``render_cyton_signal`` turns a recorded EEG (any fs, 18-ch npz layout) into what
  the Cyton would deliver: the chosen 8-electrode montage, resampled to 250 Hz, plus
  electrode noise, mains interference, drift, railed (lead-off) inputs, and the
  ADS1299's 24-bit quantization and ±187.5 mV range at gain 24.
* ``encode_stream`` / ``split_packets`` produce and frame the Cyton byte stream
  (``0xA0 | counter | 8×int24 BE | 6 aux | 0xC0``). One packet is decoded by the
  existing ``EEGFrameDecoder`` (``CYTON_DECODER``) — the same decoder class the BLE
  path uses, so no second decoder exists to drift out of sync.

Limitation: the physical reference cannot be re-simulated. Source recordings keep
their own reference (TUH average/linked-ear, hospital montages), whereas a real
Cyton measures every input against SRB2 (usually an earlobe). Treat results as an
upper bound until checked on the real board.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import gcd
from typing import List, Sequence, Tuple

import numpy as np
from scipy.signal import resample_poly

from app.services.channel_mapper import DEVICE_PRESETS
from app.services.device_source import EEGFrameDecoder
from eeg_stroke_pipeline import canonicalize_channel_name

CYTON_FS = 250
CYTON_CHANNELS = 8
ADS1299_GAIN = 24
ADS1299_VREF = 4.5
_MAX_CODE = 2**23 - 1
_MIN_CODE = -(2**23)
CYTON_SCALE_UV = ADS1299_VREF / ADS1299_GAIN / _MAX_CODE * 1e6
FULL_SCALE_UV = _MAX_CODE * CYTON_SCALE_UV

PACKET_SIZE = 33
START_BYTE = 0xA0
STOP_BYTE = 0xC0  # 0xC0 = standard accelerometer aux; the board may send 0xC0–0xCF
_AUX_BYTES = 6

CYTON_DECODER = EEGFrameDecoder(
    dtype="int24",
    endian="big",
    n_channels=CYTON_CHANNELS,
    header_bytes=2,
    trailer_bytes=_AUX_BYTES + 1,
    scale_uv=CYTON_SCALE_UV,
)

_PRESET_MONTAGE = tuple(DEVICE_PRESETS["openbci_cyton"]["channels"])


@dataclass(frozen=True)
class CytonSimConfig:
    """Electrode + environment conditions for one simulated recording (µV units)."""

    montage: Tuple[str, ...] = _PRESET_MONTAGE
    noise_uv_rms: float = 2.0       # dry-electrode + amplifier noise floor
    mains_uv: float = 0.0           # mains pickup amplitude
    mains_hz: float = 50.0          # Vietnam / EU grid
    drift_uv_per_s: float = 0.0     # slow electrode drift (the Focus+ failure mode)
    railed_channels: Tuple[str, ...] = ()  # inputs with lead-off -> pinned at full scale
    seed: int = 0

    def __post_init__(self) -> None:
        if not 0 < len(self.montage) <= CYTON_CHANNELS:
            raise ValueError(f"Cyton montage needs 1–{CYTON_CHANNELS} electrodes, got {len(self.montage)}")
        if self.noise_uv_rms < 0 or self.mains_uv < 0:
            raise ValueError("noise_uv_rms and mains_uv must be >= 0")


def _quantize(uv: np.ndarray) -> np.ndarray:
    codes = np.clip(np.round(uv / CYTON_SCALE_UV), _MIN_CODE, _MAX_CODE)
    return codes * CYTON_SCALE_UV


def _select(data: np.ndarray, labels: Sequence[str], montage: Sequence[str]) -> np.ndarray:
    index = {canonicalize_channel_name(name): i for i, name in enumerate(labels)}
    rows = []
    for name in montage:
        canon = canonicalize_channel_name(name)
        if canon not in index:
            raise ValueError(f"Montage electrode {name} not in recording channels {list(labels)}")
        rows.append(index[canon])
    return np.asarray(data, dtype=float)[rows]


def render_cyton_signal(
    data: np.ndarray,
    fs_in: float,
    labels: Sequence[str],
    config: CytonSimConfig | None = None,
) -> Tuple[np.ndarray, List[str]]:
    """Return ``(signal_uv[len(montage), n_250hz], montage_labels)`` as the Cyton would read it."""
    config = config or CytonSimConfig()
    sig = _select(data, labels, config.montage)
    fs_int = int(round(fs_in))
    if fs_int != CYTON_FS:
        g = gcd(fs_int, CYTON_FS)
        sig = resample_poly(sig, CYTON_FS // g, fs_int // g, axis=1)

    t = np.arange(sig.shape[1]) / CYTON_FS
    rng = np.random.default_rng(config.seed)
    sig = sig + rng.normal(0.0, config.noise_uv_rms, sig.shape)
    sig = sig + config.mains_uv * np.sin(2 * np.pi * config.mains_hz * t)
    sig = sig + config.drift_uv_per_s * t

    railed = {canonicalize_channel_name(c) for c in config.railed_channels}
    for row, name in enumerate(config.montage):
        if canonicalize_channel_name(name) in railed:
            sig[row] = FULL_SCALE_UV
    return _quantize(sig), list(config.montage)


def encode_packet(counter: int, sample_uv: np.ndarray) -> bytes:
    """One 33-byte Cyton packet for a single sample across 8 channels."""
    vals = np.asarray(sample_uv, dtype=float)
    if vals.shape != (CYTON_CHANNELS,):
        raise ValueError(f"Expected {CYTON_CHANNELS} channel values, got shape {vals.shape}")
    codes = np.clip(np.round(vals / CYTON_SCALE_UV), _MIN_CODE, _MAX_CODE).astype(np.int64)
    out = bytearray([START_BYTE, counter & 0xFF])
    for code in codes:
        u = int(code) & 0xFFFFFF
        out += bytes([(u >> 16) & 0xFF, (u >> 8) & 0xFF, u & 0xFF])
    out += bytes(_AUX_BYTES)
    out.append(STOP_BYTE)
    return bytes(out)


def encode_stream(signal_uv: np.ndarray, start_counter: int = 0) -> bytes:
    """Serial byte stream for ``signal_uv[n_ch<=8, n]``; unused inputs read 0."""
    sig = np.asarray(signal_uv, dtype=float)
    if sig.ndim != 2 or sig.shape[0] > CYTON_CHANNELS:
        raise ValueError(f"Expected (<= {CYTON_CHANNELS}, n) array, got shape {sig.shape}")
    padded = np.zeros((CYTON_CHANNELS, sig.shape[1]))
    padded[: sig.shape[0]] = sig
    return b"".join(encode_packet(start_counter + i, padded[:, i]) for i in range(sig.shape[1]))


def split_packets(stream: bytes) -> Tuple[List[bytes], bytes, int]:
    """Frame a byte stream into packets, resyncing on bad framing.

    Returns ``(packets, unconsumed_tail, skipped_bytes)``; feed the tail back in
    front of the next read so a packet split across reads is not lost.
    """
    packets: List[bytes] = []
    skipped = 0
    i = 0
    while True:
        j = stream.find(bytes([START_BYTE]), i)
        if j < 0:
            skipped += len(stream) - i
            return packets, b"", skipped
        if len(stream) - j < PACKET_SIZE:
            skipped += j - i
            return packets, stream[j:], skipped
        if 0xC0 <= stream[j + PACKET_SIZE - 1] <= 0xCF:
            skipped += j - i
            packets.append(stream[j : j + PACKET_SIZE])
            i = j + PACKET_SIZE
        else:
            skipped += j + 1 - i
            i = j + 1


def count_dropped(counters: Sequence[int]) -> int:
    """Packets lost between consecutive sample counters (8-bit, wraps at 256)."""
    return sum((b - a - 1) % 256 for a, b in zip(counters, counters[1:]))


__all__ = [
    "CYTON_DECODER",
    "CYTON_FS",
    "CYTON_SCALE_UV",
    "FULL_SCALE_UV",
    "PACKET_SIZE",
    "CytonSimConfig",
    "count_dropped",
    "encode_packet",
    "encode_stream",
    "render_cyton_signal",
    "split_packets",
]
