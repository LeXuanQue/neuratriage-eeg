"""Live EEG device source — Brain-Life Focus+ over Bluetooth LE.

Architecture (discovery-first, see docs/device_bring_up.md):

* ``EEGFrameDecoder`` is a PURE, unit-tested function from raw BLE bytes to a
  ``(n_channels, n_samples)`` microvolt array. Every device-specific unknown
  (dtype, endianness, header size, interleaving, µV scale) is an explicit field
  so it can be filled from ``scripts/ble_probe.py`` output and verified by tests.
* ``DeviceProtocol`` bundles the decoder with the GATT characteristic UUIDs and
  the channel labels. ``BRAIN_LIFE_FOCUS_PLUS`` holds PROVISIONAL values — they
  are placeholders until confirmed against the real device, hence
  ``configured=False`` (callers should refuse to stream until it is True).
* ``BleDeviceSource`` runs the bleak client with reconnect/backoff (the device
  spec advertises auto-resume after disconnection) and pushes decoded chunks to
  an ``on_chunk`` callback. bleak is imported lazily so the app, tests, and CI
  do not require it unless a live device is actually used.

The Focus+ EEG is **2 monopolar channels, AF3 and AF4** (frontal-polar), streamed
as ASCII line frames tagged by header byte (0x24=AF3, 0x26=AF4; recovered from the
vendor app — see ``BrainLifeAsciiDecoder``). AF3/AF4 are not in the 18-ch training
montage, so ``channel_mapper.map_to_pipeline`` leaves the target channels NaN
(honest "no equivalent data") and classification stays on the validated 18-ch
replay path; the live 2-ch device only drives SQI / No-Decision (the Hybrid demo).
This live path is exploratory; validated evidence remains the offline
50-ischemic + 50-healthy dataset. See docs/device_bring_up.md.
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Awaitable, Callable, List, Optional

import numpy as np

logger = logging.getLogger("neuratriage.device")

# Callback receives (data[n_channels, n_samples] in µV, channel_labels).
OnChunk = Callable[[np.ndarray, List[str]], None]

_DTYPE_SIZE = {"int16": 2, "int24": 3, "float32": 4}


@dataclass(frozen=True)
class EEGFrameDecoder:
    """Decode one BLE notification payload into a (n_channels, n_samples) µV array.

    All fields are device-specific and PROVISIONAL until verified with
    scripts/ble_probe.py. Defaults assume the most common layout (int16, little
    endian, interleaved samples) but MUST be confirmed.
    """

    dtype: str = "int16"          # "int16" | "int24" | "float32"
    endian: str = "little"        # "little" | "big"
    n_channels: int = 2           # Focus+ EEG = 2 differential channels
    header_bytes: int = 0         # leading bytes to skip (counter/flags), if any
    trailer_bytes: int = 0        # trailing bytes to skip (CRC), if any
    interleaved: bool = True      # True: ch0,ch1,ch0,ch1...  False: ch0...,ch1...
    scale_uv: float = 1.0         # multiply raw sample -> microvolt

    def sample_size(self) -> int:
        try:
            return _DTYPE_SIZE[self.dtype]
        except KeyError:
            raise ValueError(f"Unsupported dtype {self.dtype!r}") from None

    def _payload(self, raw: bytes) -> bytes:
        end = len(raw) - self.trailer_bytes
        if self.header_bytes < 0 or end < self.header_bytes:
            raise ValueError(
                f"Frame too short ({len(raw)}B) for header={self.header_bytes} "
                f"trailer={self.trailer_bytes}"
            )
        return raw[self.header_bytes : end]

    def _raw_samples(self, payload: bytes) -> np.ndarray:
        e = "<" if self.endian == "little" else ">"
        if self.dtype == "int16":
            return np.frombuffer(payload, dtype=np.dtype(e + "i2")).astype(np.float64)
        if self.dtype == "float32":
            return np.frombuffer(payload, dtype=np.dtype(e + "f4")).astype(np.float64)
        if self.dtype == "int24":
            b = np.frombuffer(payload, dtype=np.uint8).reshape(-1, 3).astype(np.int32)
            if self.endian == "little":
                val = b[:, 0] | (b[:, 1] << 8) | (b[:, 2] << 16)
            else:
                val = b[:, 2] | (b[:, 1] << 8) | (b[:, 0] << 16)
            # sign-extend 24-bit -> 32-bit
            val = (val ^ 0x800000) - 0x800000
            return val.astype(np.float64)
        raise ValueError(f"Unsupported dtype {self.dtype!r}")

    def decode(self, raw: bytes) -> np.ndarray:
        """Return (n_channels, n_samples) in µV. Raises ValueError on bad framing."""
        payload = self._payload(raw)
        if self.dtype == "int24" and len(payload) % 3 != 0:
            raise ValueError(f"int24 payload {len(payload)}B not a multiple of 3")
        samples = self._raw_samples(payload)
        if samples.size % self.n_channels != 0:
            raise ValueError(
                f"{samples.size} samples not divisible by n_channels={self.n_channels} "
                f"(payload {len(payload)}B, dtype {self.dtype})"
            )
        n = samples.size // self.n_channels
        if self.interleaved:
            data = samples.reshape(n, self.n_channels).T
        else:
            data = samples.reshape(self.n_channels, n)
        return np.ascontiguousarray(data) * self.scale_uv


@dataclass(frozen=True)
class BrainLifeAsciiDecoder:
    """Decode Brain-Life Focus+ ASCII-line frames into per-channel µV samples.

    Recovered from the vendor app (``brain-life-desktop``: ``BLE.bluetooth_manager``
    + ``common.signals``/``common.data_processors``). After the start command
    ``b"9999"`` is written to NUS RX, the device notifies on NUS TX with frames of
    10-byte lines: ``<1-byte header><8 ASCII digits><0x0A>``. The header byte tags
    the source channel — ``0x24``=AF3 and ``0x26``=AF4 are the two EEG channels;
    ``0x25``/``0x27``/``0x28`` are PPG/fNIRS and ignored here. AF3 and AF4 arrive in
    separate notifications, so ``BleDeviceSource`` accumulates per channel and
    emits an aligned 2-row chunk.

    ``scale_uv``/``offset`` are a passthrough by default (raw ADC counts); the SQI
    path detrends the DC offset, so quality gating works without exact calibration.
    """

    eeg_headers: tuple = ((0x24, "AF3"), (0x26, "AF4"))
    scale_uv: float = 1.0
    offset: float = 0.0

    @property
    def channel_labels(self) -> List[str]:
        return [label for _, label in self.eeg_headers]

    def parse(self, raw: bytes) -> dict:
        """Return ``{header_byte: [µV, ...]}`` for the EEG headers in this frame."""
        wanted = {h for h, _ in self.eeg_headers}
        out: dict = {}
        for line in raw.split(b"\n"):
            if len(line) < 2:
                continue
            header = line[0]
            if header not in wanted:
                continue
            digits = line[1:]
            if not digits.isdigit():
                continue
            value = (float(int(digits.decode("ascii"))) - self.offset) * self.scale_uv
            out.setdefault(header, []).append(value)
        return out


@dataclass(frozen=True)
class DeviceProtocol:
    name: str
    eeg_char_uuid: str            # GATT characteristic that notifies EEG frames
    channel_labels: List[str]     # canonical electrode labels for the rows decode() returns
    fs: float
    decoder: EEGFrameDecoder
    eeg_mode: str = "differential"
    battery_char_uuid: Optional[str] = None
    # Some devices need a command written before they start streaming.
    start_command: Optional[bytes] = None
    start_command_uuid: Optional[str] = None
    stop_command: Optional[bytes] = None
    # When set, frames are ASCII line-tagged (Focus+) rather than binary; the
    # source accumulates per-channel and emits aligned chunks via this decoder.
    ascii_decoder: Optional[BrainLifeAsciiDecoder] = None
    # Advertised-name substring used to find the device when no explicit BLE
    # address is given (the Focus+ advertises "BL <id> focus+", not its DB name).
    name_hint: Optional[str] = None
    configured: bool = False      # flip True only after the real protocol is confirmed


# ── CONFIRMED profile — recovered from the vendor app brain-life-desktop ──────
# UUIDs, start/stop commands, and the ASCII frame format were reverse-engineered
# from the official PyInstaller+bleak desktop app (BLE.bluetooth_manager) and
# verified live: writing b"9999" to NUS RX starts a real EEG stream on NUS TX.
# Nordic UART Service: 6e400001; RX(write)=6e400002; TX(notify)=6e400003.
# EEG electrodes are AF3 & AF4 (frontal-polar), 2 monopolar channels.
NUS_RX_UUID = "6e400002-b5a3-f393-e0a9-e50e24dcca9e"
NUS_TX_UUID = "6e400003-b5a3-f393-e0a9-e50e24dcca9e"

BRAIN_LIFE_FOCUS_PLUS = DeviceProtocol(
    name="Brain-Life Focus+",
    eeg_char_uuid=NUS_TX_UUID,
    battery_char_uuid="00002a19-0000-1000-8000-00805f9b34fb",
    channel_labels=["AF3", "AF4"],  # 2 EEG electrodes (headers 0x24, 0x26)
    fs=256.0,
    eeg_mode="monopolar",
    # Binary decoder kept only for API compatibility; the ASCII decoder is active.
    decoder=EEGFrameDecoder(dtype="int16", endian="little", n_channels=2),
    ascii_decoder=BrainLifeAsciiDecoder(),
    start_command=b"9999",
    start_command_uuid=NUS_RX_UUID,
    stop_command=b"2200220D",
    name_hint="focus",  # advertises as "BL <id> focus+"
    configured=True,
)


class BleDeviceSource:
    """Connect to a BLE EEG device, decode frames, and push chunks to a callback.

    Reconnects with capped backoff (the Focus+ advertises auto-resume after a
    drop). All BLE/decode errors are logged and never crash the caller.
    """

    def __init__(
        self,
        protocol: DeviceProtocol,
        on_chunk: OnChunk,
        address_or_name: str,
        on_battery: Optional[Callable[[int], None]] = None,
        max_backoff_sec: float = 8.0,
        on_status: Optional[Callable[[dict], Awaitable[None]]] = None,
    ) -> None:
        self._proto = protocol
        self._on_chunk = on_chunk
        self._target = address_or_name
        self._on_battery = on_battery
        # Optional async sink for link-state updates. Without it a switched-off
        # headset is indistinguishable from a broken app: the loop below just
        # retries forever and the caller is told nothing.
        self._on_status = on_status
        self._max_backoff = max_backoff_sec
        # Per-channel accumulator for the ASCII (Focus+) path: AF3/AF4 arrive in
        # separate notifications, so buffer each header and emit aligned chunks.
        self._ascii = protocol.ascii_decoder
        self._acc: dict = (
            {h: [] for h, _ in self._ascii.eeg_headers} if self._ascii else {}
        )
        self._emit_samples = 32

    async def _emit_status(self, state: str, message: str = "", **extra: object) -> None:
        """Report a link-state change. Never raises — status is not the payload."""
        if self._on_status is None:
            return
        payload = {"state": state, "message": message}
        payload.update(extra)
        try:
            await self._on_status(payload)
        except Exception:  # noqa: BLE001
            logger.exception("device status callback raised")

    def _frame_cb(self, _sender, data: bytearray) -> None:
        if self._ascii is not None:
            self._handle_ascii(bytes(data))
            return
        try:
            chunk = self._proto.decoder.decode(bytes(data))
        except Exception as exc:  # noqa: BLE001
            logger.warning("EEG frame decode failed (%dB): %s", len(data), exc)
            return
        try:
            self._on_chunk(chunk, list(self._proto.channel_labels))
        except Exception:  # noqa: BLE001
            logger.exception("on_chunk callback raised")

    def _handle_ascii(self, raw: bytes) -> None:
        """Accumulate ASCII per-channel samples and emit an aligned 2-row chunk."""
        try:
            parsed = self._ascii.parse(raw)
        except Exception as exc:  # noqa: BLE001
            logger.warning("ASCII frame parse failed (%dB): %s", len(raw), exc)
            return
        for header, samples in parsed.items():
            if header in self._acc:
                self._acc[header].extend(samples)
        ready = min((len(buf) for buf in self._acc.values()), default=0)
        if ready < self._emit_samples:
            return
        rows = []
        for header, _label in self._ascii.eeg_headers:
            buf = self._acc[header]
            rows.append(np.asarray(buf[:ready], dtype=float))
            self._acc[header] = buf[ready:]
        chunk = np.vstack(rows)
        try:
            self._on_chunk(chunk, list(self._ascii.channel_labels))
        except Exception:  # noqa: BLE001
            logger.exception("on_chunk callback raised")

    async def run(self, stop: asyncio.Event) -> None:
        if not self._proto.configured:
            await self._emit_status(
                "blocked",
                f"{self._proto.name} protocol is not configured",
            )
            raise RuntimeError(
                f"{self._proto.name} protocol is not configured "
                "(run scripts/ble_probe.py and fill device_source.py before streaming)."
            )
        try:
            from bleak import BleakClient, BleakScanner
        except ImportError as exc:
            await self._emit_status("blocked", "bleak not installed on the server")
            raise RuntimeError(
                "bleak not installed — `pip install bleak` to use a live device."
            ) from exc

        backoff = 1.0
        while not stop.is_set():
            try:
                await self._emit_status(
                    "searching", f"looking for {self._proto.name}", target=self._target
                )
                target = self._target
                # Treat the target as a BLE address only if it looks like a MAC
                # (contains ':'); otherwise resolve it as an advertised-name
                # substring (the Focus+ advertises "BL <id> focus+").
                if ":" not in target:
                    needle = target.lower()
                    dev = await BleakScanner.find_device_by_filter(
                        lambda d, _ad: (d.name or "").lower().find(needle) >= 0,
                        timeout=8.0,
                    )
                    if dev is None:
                        raise RuntimeError(f"device matching {target!r} not found")
                    target = dev

                async with BleakClient(target) as client:
                    logger.info("Device connected: %s", self._proto.name)
                    backoff = 1.0
                    await self._emit_status(
                        "connected",
                        f"{self._proto.name} connected",
                        channels=list(self._proto.channel_labels),
                        fs=self._proto.fs,
                    )
                    if self._proto.start_command and self._proto.start_command_uuid:
                        await client.write_gatt_char(
                            self._proto.start_command_uuid, self._proto.start_command
                        )
                    if self._on_battery and self._proto.battery_char_uuid:
                        try:
                            val = await client.read_gatt_char(self._proto.battery_char_uuid)
                            self._on_battery(int(val[0]))
                        except Exception:  # noqa: BLE001
                            pass
                    await client.start_notify(self._proto.eeg_char_uuid, self._frame_cb)
                    while not stop.is_set() and client.is_connected:
                        await asyncio.sleep(0.2)
                    if self._proto.stop_command and self._proto.start_command_uuid:
                        try:
                            await client.write_gatt_char(
                                self._proto.start_command_uuid, self._proto.stop_command
                            )
                        except Exception:  # noqa: BLE001
                            pass
                    try:
                        await client.stop_notify(self._proto.eeg_char_uuid)
                    except Exception:  # noqa: BLE001
                        pass
            except Exception as exc:  # noqa: BLE001
                if stop.is_set():
                    break
                logger.warning("Device link error (%s); reconnecting in %.1fs", exc, backoff)
                await self._emit_status(
                    "error", str(exc), retry_in_sec=float(backoff)
                )
                try:
                    await asyncio.wait_for(stop.wait(), timeout=backoff)
                except asyncio.TimeoutError:
                    pass
                backoff = min(self._max_backoff, backoff * 2)
        await self._emit_status("stopped", f"{self._proto.name} stream stopped")
        logger.info("Device source stopped: %s", self._proto.name)


__all__ = [
    "EEGFrameDecoder",
    "DeviceProtocol",
    "BleDeviceSource",
    "BRAIN_LIFE_FOCUS_PLUS",
    "OnChunk",
]
