"""Phase-2 wiring: stream a live EEG device through the SAME path as replay.

A live BLE device must reach the UI through exactly the path replay uses:
raw chunk -> ``map_to_pipeline`` -> ``detector.update`` -> publish events. This
module is the decoupled plumbing for that, designed to be testable without any
hardware or ``bleak``:

* ``process_chunk`` is the pure step (map + one detector update).
* ``run_device_session`` is the orchestration: a chunk *source*
  (``BleDeviceSource`` in production, a fake in tests) pushes ``(chunk, labels)``
  which are queued and handed to an async ``on_data`` handler supplied by the WS
  layer. A bounded queue drops the oldest chunk under backpressure so a slow
  detector never blocks the BLE notification callback.
* ``device_readiness`` reports whether a protocol can stream right now, for the
  device status endpoint / UI.

The actual live hookup stays guarded by ``protocol.configured`` (see
``device_source.py``): until ``scripts/ble_probe.py`` confirms the real UUIDs and
flips it True, streaming refuses rather than feeding garbage to the detector.
"""
from __future__ import annotations

import asyncio
import contextlib
import logging
from typing import Any, Awaitable, Callable, Dict, List, Optional

import numpy as np

from eeg_stroke_pipeline import compute_sqi, preprocess_eeg_for_sqi
from .channel_mapper import map_to_pipeline
from .device_source import DeviceProtocol

logger = logging.getLogger("neuratriage.device")

OnChunk = Callable[[np.ndarray, List[str]], None]
OnData = Callable[[np.ndarray, List[str]], Awaitable[None]]


class DeviceSqiMonitor:
    """Score signal quality on the REAL device channels (not the 18-ch map).

    The Focus+'s 2 differential channels do not alias onto the monopolar pipeline
    montage, so ``map_to_pipeline`` NaN-fills them and the detector would compute
    SQI on zeros — pinning the live device at No-Decision regardless of actual
    electrode contact. Signal *quality*, however, is well-defined directly on the
    raw device channels, so this monitor scores it there. That lets the live
    headband genuinely drive the SQI gate / No-Decision state (the Hybrid demo),
    while classification stays on the validated 18-ch replay path — this monitor
    deliberately never emits a class from the 2-channel device.
    """

    def __init__(self, n_channels: int, fs: float, config: Any) -> None:
        self._fs = float(fs)
        self._config = config
        self._win = max(1, int(round(config.entropy_window_sec * self._fs)))
        self._buf = np.zeros((n_channels, 0), dtype=float)

    def push(self, chunk: np.ndarray) -> Optional[Dict[str, float]]:
        """Buffer a raw device chunk; return the SQI dict once a full window exists."""
        arr = np.asarray(chunk, dtype=float)
        if arr.ndim != 2 or arr.size == 0:
            return None
        self._buf = np.concatenate([self._buf, arr], axis=1)
        if self._buf.shape[1] > self._win:
            self._buf = self._buf[:, -self._win:]
        if self._buf.shape[1] < self._win:
            return None
        prepped = preprocess_eeg_for_sqi(self._buf, self._fs, self._config)
        return compute_sqi(prepped, self._config.fs, self._config)


def device_sqi_event(sqi: Dict[str, float], timestamp_sec: float, gate: float) -> Dict[str, Any]:
    """Build a quality-only event from a device SQI dict.

    Below the gate the status is ``no-decision``; above it the device shows
    ``monitor`` (usable signal) but never a predicted class — the 2-channel
    device montage is not the validated classification path.
    """
    total = float(sqi["sqi_total"])
    return {
        "timestamp_sec": timestamp_sec,
        "sqi_total": total,
        "sqi_flatline": sqi.get("sqi_flatline"),
        "sqi_clip": sqi.get("sqi_clip"),
        "sqi_line_ratio": sqi.get("sqi_line_ratio"),
        "sqi_hf_ratio": sqi.get("sqi_hf_ratio"),
        "status": "no-decision" if total < gate else "monitor",
        "predicted_class": None,
        "probabilities_raw": None,
        "probabilities_smooth": None,
        "alert_class": None,
    }


def process_chunk(detector, chunk: np.ndarray, labels: List[str]) -> List[Dict[str, Any]]:
    """Map a raw device chunk onto the pipeline montage and run one detector step.

    Returns the detector's event list (possibly empty). Raises ValueError only on
    a channel-count mismatch (a programming error, surfaced to the caller).
    """
    mapped, _ = map_to_pipeline(np.asarray(chunk, dtype=float), list(labels), fs=detector.fs)
    return list(detector.update(mapped))


def device_readiness(protocol: DeviceProtocol) -> Dict[str, Any]:
    """Whether ``protocol`` can stream right now (configured + bleak importable)."""
    try:
        import bleak  # noqa: F401
        bleak_ok = True
    except Exception:
        bleak_ok = False
    if not protocol.configured:
        reason: Optional[str] = "protocol not configured (run scripts/ble_probe.py)"
    elif not bleak_ok:
        reason = "bleak not installed (pip install bleak)"
    else:
        reason = None
    return {
        "name": protocol.name,
        "configured": bool(protocol.configured),
        "bleak_available": bleak_ok,
        "ready": bool(protocol.configured) and bleak_ok,
        "channels": list(protocol.channel_labels),
        "fs": protocol.fs,
        "eeg_mode": protocol.eeg_mode,
        "blocking_reason": reason,
    }


async def run_device_session(
    source_factory: Callable[[OnChunk], Any],
    on_data: OnData,
    *,
    stop: Optional[asyncio.Event] = None,
    queue_size: int = 64,
) -> None:
    """Plumb a chunk source into ``on_data`` until ``stop`` is set or the source ends.

    ``source_factory(on_chunk)`` returns an object exposing ``async run(stop)`` and
    calling ``on_chunk(chunk, labels)`` per BLE notification. Source and handler
    errors are logged, never raised into the caller, so the WS loop stays alive.
    """
    stop = stop or asyncio.Event()
    queue: asyncio.Queue = asyncio.Queue(maxsize=queue_size)

    def on_chunk(chunk: np.ndarray, labels: List[str]) -> None:
        item = (chunk, list(labels))
        try:
            queue.put_nowait(item)
        except asyncio.QueueFull:
            with contextlib.suppress(asyncio.QueueEmpty):
                queue.get_nowait()  # drop oldest, keep the freshest signal
            with contextlib.suppress(asyncio.QueueFull):
                queue.put_nowait(item)

    source = source_factory(on_chunk)

    async def _produce() -> None:
        try:
            await source.run(stop)
        except Exception:
            logger.exception("device source.run failed")
        finally:
            stop.set()

    producer = asyncio.create_task(_produce())
    try:
        while True:
            if stop.is_set() and queue.empty():
                break
            try:
                chunk, labels = await asyncio.wait_for(queue.get(), timeout=0.25)
            except asyncio.TimeoutError:
                if producer.done() and queue.empty():
                    break
                continue
            try:
                await on_data(chunk, labels)
            except Exception:
                logger.exception("device on_data handler failed")
    finally:
        stop.set()
        if not producer.done():
            producer.cancel()
        with contextlib.suppress(asyncio.CancelledError, Exception):
            await producer


__all__ = ["process_chunk", "device_readiness", "run_device_session", "OnChunk", "OnData"]
