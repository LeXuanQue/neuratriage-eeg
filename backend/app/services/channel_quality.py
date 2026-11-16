"""Rolling per-channel signal quality (SQI v2) for the live interface.

Feeds condition G of Study 1 (docs/user_study_protocol.md): every ``every_sec`` it scores
the last ``window_sec`` of the RAW device channels and emits one WebSocket message with a
score and reason codes per channel plus a single operator tip.

Scored on the device channels, not the 18-channel pipeline map, for the same reason as
``DeviceSqiMonitor``: a 2-channel headband maps onto mostly empty montage slots.

The drift threshold comes from the frozen TUAR calibration when it exists
(``results/sqi_v2_calibration.json`` or ``NEURATRIAGE_SQI_CALIBRATION``), otherwise from
the synthetic defaults in ``sqi_v2``.
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

import numpy as np
import sqi_v2

logger = logging.getLogger("neuratriage.quality")

DEFAULT_CALIBRATION = Path(__file__).resolve().parents[3] / "results" / "sqi_v2_calibration.json"
DEFAULT_LINE_FREQ = 50.0  # mains frequency where the device is used (Vietnam: 50 Hz)


def load_sqi_config(line_freq: float = DEFAULT_LINE_FREQ, calibration_path: Optional[Path] = None) -> sqi_v2.SqiV2Config:
    """SQI v2 config with the frozen drift ramp when a calibration file is available."""
    path = calibration_path or Path(os.environ.get("NEURATRIAGE_SQI_CALIBRATION", DEFAULT_CALIBRATION))
    values: Dict[str, Any] = {"line_freq": float(line_freq)}
    try:
        values["drift_ramp"] = json.loads(Path(path).read_text(encoding="utf-8"))["drift_ramp"]
    except FileNotFoundError:
        pass
    except (OSError, ValueError, KeyError) as exc:
        logger.warning("Ignoring unreadable SQI calibration %s: %s", path, exc)
    return sqi_v2.config_from_dict(values)


def _finite(value: float) -> float:
    return round(float(value), 3) if np.isfinite(value) else 0.0


class ChannelQualityTracker:
    """Buffer raw device chunks and emit a ``channel_quality`` message at a fixed cadence."""

    def __init__(
        self,
        channel_names: Sequence[str],
        fs: float,
        window_sec: float = 4.0,
        every_sec: float = 1.0,
        config: Optional[sqi_v2.SqiV2Config] = None,
    ) -> None:
        self._names: List[str] = [str(n) for n in channel_names]
        self._fs = float(fs)
        self._config = config or load_sqi_config()
        self._win = int(round(window_sec * self._fs))
        self._every = max(1, int(round(every_sec * self._fs)))
        self._buf = np.zeros((len(self._names), 0), dtype=float)
        self._total = 0  # samples received since start
        self._last_emit: Optional[int] = None
        self.available = self._fs >= self._config.min_fs and window_sec >= self._config.min_window_sec

    @property
    def buffered_samples(self) -> int:
        return int(self._buf.shape[1])

    def push(self, chunk: np.ndarray) -> Optional[Dict[str, Any]]:
        """Add a ``(channels, samples)`` chunk; return a message when one is due."""
        arr = np.asarray(chunk, dtype=float)
        if arr.ndim != 2 or arr.shape[0] != len(self._names):
            raise ValueError(f"Expected {len(self._names)} channels, got shape {arr.shape}")
        if not self.available or arr.shape[1] == 0:
            return None
        self._buf = np.concatenate([self._buf, arr], axis=1)[:, -self._win :]
        self._total += arr.shape[1]
        if self._buf.shape[1] < self._win:
            return None
        if self._last_emit is not None and self._total - self._last_emit < self._every:
            return None
        self._last_emit = self._total
        return self._message()

    def _message(self) -> Dict[str, Any]:
        quality = sqi_v2.assess_window(self._buf, self._fs, channel_names=self._names, config=self._config)
        tip = sqi_v2.guidance(quality)
        return {
            "type": "channel_quality",
            "timestamp_sec": round(self._total / self._fs, 3),
            "score": _finite(quality.score),
            "worst_channel": quality.channels[quality.worst_channel].name,
            "channels": [
                {"name": c.name, "score": _finite(c.score), "reasons": list(c.reasons)} for c in quality.channels
            ],
            "guidance": None if tip is None else {"channel": tip.channel, "reason": tip.reason, "advice": tip.advice},
        }
