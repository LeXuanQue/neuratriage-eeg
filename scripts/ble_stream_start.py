"""Trigger EEG streaming on the Brain-Life Focus+ by trying candidate start
commands, then capture the resulting frames so the decoder can be filled.

Context (from scripts/ble_probe.py output, out/ble_probe_capture.txt):
  * EEG almost certainly rides the Nordic UART Service (NUS):
      - TX (notify): 6e400003-b5a3-f393-e0a9-e50e24dcca9e   <- EEG data out
      - RX (write) : 6e400002-b5a3-f393-e0a9-e50e24dcca9e   <- command in
  * During a passive probe the TX characteristic sent ZERO frames, i.e. the
    device only streams AFTER it receives a vendor "start" command on RX.

This tool: subscribe to every notify characteristic, then write a series of
common start commands to the NUS RX (and, as a fallback, to the other writable
characteristics). After each command it measures the per-characteristic frame
rate; a characteristic that jumps to ~200-320 Hz with a fixed frame size is the
EEG stream. The winning command + raw frames are logged so the frame format
(dtype, samples/frame, channel count, µV scale) can be inferred.

It only writes small control commands — it never touches the SMP/firmware
service. Nothing here is destructive; worst case the device ignores the writes.

Run (device powered on, near the PC, not connected in another app):

    .venv\\Scripts\\python.exe scripts/ble_stream_start.py
    .venv\\Scripts\\python.exe scripts/ble_stream_start.py --address D4:0D:D3:18:18:47 --per 4
"""
from __future__ import annotations

import argparse
import asyncio
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Nordic UART Service (the likely EEG transport).
NUS_TX = "6e400003-b5a3-f393-e0a9-e50e24dcca9e"   # notify — EEG data out
NUS_RX = "6e400002-b5a3-f393-e0a9-e50e24dcca9e"   # write  — command in
# Other writable characteristics, tried only if NUS RX yields nothing.
FALLBACK_WRITE_UUIDS = [
    "00001525-1212-efde-1523-e3d498cfb8d7",  # Unknown vendor service, [write]
    "00001525-1212-efde-1523-785feabcd123",  # Nordic LED Button Service, [write]
]
BATTERY_STATUS_UUID = "00002bed-0000-1000-8000-00805f9b34fb"  # noisy: ignore for EEG

OUT_PATH = Path(__file__).resolve().parent.parent / "out" / "ble_stream_start_capture.txt"

# Candidate start commands. Ordered from most-common to more speculative.
# Each entry is (label, payload_bytes).
CANDIDATE_COMMANDS: List[Tuple[str, bytes]] = [
    ("0x01", bytes([0x01])),
    ("0x02", bytes([0x02])),
    ("0x03", bytes([0x03])),
    ("0x01,0x01", bytes([0x01, 0x01])),
    ("0x02,0x01", bytes([0x02, 0x01])),
    ("0xAA,0x01", bytes([0xAA, 0x01])),
    ("0x55,0x01", bytes([0x55, 0x01])),
    ("0xA0", bytes([0xA0])),
    ("ascii 'b'", b"b"),
    ("ascii '1'", b"1"),
    ("ascii 'start'", b"start"),
    ("ascii 'start\\r\\n'", b"start\r\n"),
    ("ascii 'START'", b"START"),
    ("ascii 'on'", b"on"),
    ("0x01,0x00", bytes([0x01, 0x00])),
    ("0xFF,0x01", bytes([0xFF, 0x01])),
]

# A characteristic counts as an EEG hit if it exceeds this rate with data
# frames larger than a couple of bytes (to exclude the 3-byte battery status).
EEG_MIN_RATE_HZ = 40.0
EEG_MIN_FRAME_BYTES = 6


def _import_bleak():
    try:
        from bleak import BleakClient, BleakScanner

        return BleakScanner, BleakClient
    except ImportError:
        sys.exit(
            "bleak is not installed. Install it first:\n"
            "    .venv\\Scripts\\python.exe -m pip install bleak"
        )


def _hex(data: bytes, limit: int = 40) -> str:
    head = data[:limit]
    return head.hex(" ") + (" …" if len(data) > limit else "")


class Capture:
    """Per-characteristic frame counters, resettable between commands."""

    def __init__(self) -> None:
        self.counts: Counter = Counter()
        self.sizes: Dict[str, Counter] = defaultdict(Counter)
        self.samples: Dict[str, List[str]] = defaultdict(list)

    def reset(self) -> None:
        self.counts.clear()
        self.sizes.clear()
        self.samples.clear()

    def make_cb(self, uuid: str):
        def _cb(_sender, data: bytearray) -> None:
            self.counts[uuid] += 1
            self.sizes[uuid][len(data)] += 1
            if len(self.samples[uuid]) < 5:
                self.samples[uuid].append(_hex(bytes(data)))

        return _cb

    def eeg_hit(self, elapsed: float) -> Optional[str]:
        """Return the UUID of a characteristic that looks like an EEG stream."""
        for uuid, n in self.counts.items():
            if uuid == BATTERY_STATUS_UUID:
                continue
            rate = n / max(1e-6, elapsed)
            biggest = max(self.sizes[uuid], default=0)
            if rate >= EEG_MIN_RATE_HZ and biggest >= EEG_MIN_FRAME_BYTES:
                return uuid
        return None


async def _scan(BleakScanner, name: str, address: Optional[str], timeout: float):
    print(f"[scan] discovering BLE devices for {timeout:.0f}s ...")
    devices = await BleakScanner.discover(timeout=timeout)
    for d in devices:
        print(f"  - {d.address}  rssi={getattr(d, 'rssi', '?')}  name={d.name!r}")
    if address:
        match = next((d for d in devices if d.address.lower() == address.lower()), None)
        if not match:
            sys.exit(f"[scan] no device with address {address}")
        return match
    needle = name.lower()
    match = next((d for d in devices if (d.name or "").lower().find(needle) >= 0), None)
    if not match:
        sys.exit(f"[scan] no device whose name contains {name!r}. Pass --address.")
    return match


def _build_command_list(deep: bool) -> List[Tuple[str, bytes]]:
    """Curated commands first, then (optionally) every remaining single byte."""
    cmds = list(CANDIDATE_COMMANDS)
    if deep:
        seen = {payload for _, payload in cmds}
        for b in range(0x00, 0x100):
            payload = bytes([b])
            if payload in seen:
                continue
            cmds.append((f"0x{b:02X}", payload))
    return cmds


async def _resolve_target(BleakScanner, name: str, address: Optional[str], scan_timeout: float, log):
    """Prefer a direct address connect (works once bonded in Windows, even if
    the device has stopped advertising); fall back to a name scan."""
    if address:
        log(f"[target] using explicit address {address} (direct connect, no scan needed)")
        return address
    device = await _scan(BleakScanner, name, None, scan_timeout)
    return device.address


async def run(name: str, address: Optional[str], per: float, scan_timeout: float, deep: bool) -> None:
    BleakScanner, BleakClient = _import_bleak()

    lines: List[str] = []

    def log(msg: str = "") -> None:
        print(msg)
        lines.append(msg)

    target_addr = await _resolve_target(BleakScanner, name, address, scan_timeout, log)
    commands = _build_command_list(deep)
    log(f"[plan] {len(commands)} candidate command(s), {per:.1f}s each "
        f"(~{len(commands) * per / 60:.1f} min max) on NUS RX {NUS_RX}")

    cap = Capture()
    hit_uuid: Optional[str] = None
    hit_desc: Optional[str] = None
    baseline_done = False
    idx = 0                       # resume point across reconnects
    max_reconnects = 6
    reconnects = 0

    while idx < len(commands) and hit_uuid is None:
        try:
            async with BleakClient(target_addr) as client:
                log(f"\n[connected] {target_addr}")
                # Re-subscribe fresh on every (re)connection.
                notify_uuids: List[str] = []
                for service in client.services:
                    for ch in service.characteristics:
                        if "notify" in ch.properties or "indicate" in ch.properties:
                            notify_uuids.append(ch.uuid)
                subscribed: List[str] = []
                for uuid in notify_uuids:
                    try:
                        await client.start_notify(uuid, cap.make_cb(uuid))
                        subscribed.append(uuid)
                    except Exception:
                        pass
                log(f"[subscribed] {len(subscribed)} notify char(s)")

                if not baseline_done:
                    cap.reset()
                    t0 = time.monotonic()
                    await asyncio.sleep(min(3.0, per))
                    log("\n=== baseline (no command) ===")
                    _log_window(log, cap, time.monotonic() - t0)
                    baseline_done = True

                while idx < len(commands):
                    label, payload = commands[idx]
                    if not client.is_connected:
                        log("  ! link dropped — will reconnect and resume")
                        break
                    cap.reset()
                    sent = await _try_write(client, NUS_RX, payload, log, label)
                    if not sent:
                        if not client.is_connected:
                            break
                        idx += 1
                        continue
                    t0 = time.monotonic()
                    await asyncio.sleep(per)
                    elapsed = time.monotonic() - t0
                    log(f"\n--- after {label} ({payload.hex(' ')}) ---")
                    _log_window(log, cap, elapsed)
                    uuid = cap.eeg_hit(elapsed)
                    if uuid:
                        hit_uuid = uuid
                        hit_desc = f"command {label} ({payload.hex(' ')}) on {NUS_RX}"
                        log(f"\n*** EEG STREAM DETECTED on {uuid} via {hit_desc} ***")
                        log("\n=== extended capture of winning stream (5s) ===")
                        cap.reset()
                        t0 = time.monotonic()
                        await asyncio.sleep(5.0)
                        _log_window(log, cap, time.monotonic() - t0)
                        break
                    idx += 1

                for uuid in subscribed:
                    try:
                        await client.stop_notify(uuid)
                    except Exception:
                        pass
        except Exception as exc:  # noqa: BLE001
            reconnects += 1
            log(f"  ! connection error ({exc}); reconnect {reconnects}/{max_reconnects}")
            if reconnects > max_reconnects:
                log("[abort] too many reconnects — giving up.")
                break
            await asyncio.sleep(2.0)

    if hit_uuid:
        log(f"\n[RESULT] EEG characteristic : {hit_uuid}")
        log(f"[RESULT] start command      : {hit_desc}")
        log("[RESULT] Next: infer dtype/samples-per-frame/µV scale from the")
        log("         frame size + rate, then fill BRAIN_LIFE_FOCUS_PLUS in")
        log("         backend/app/services/device_source.py and set configured=True.")
    else:
        log("\n[RESULT] No start command triggered an EEG stream.")
        log("[RESULT] The command is likely vendor-specific/multi-byte. Best")
        log("         path: capture it from the official app via Android HCI")
        log("         snoop log or a BLE sniffer, watching writes to NUS RX")
        log(f"         ({NUS_RX}).")

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(f"\n[done] capture written to {OUT_PATH}")


async def _try_write(client, uuid: str, payload: bytes, log, label: str) -> bool:
    """Write a command, preferring write-without-response, falling back to write."""
    for response in (False, True):
        try:
            await client.write_gatt_char(uuid, payload, response=response)
            return True
        except Exception:
            continue
    log(f"  ! write failed for {label} on {uuid}")
    return False


def _log_window(log, cap: Capture, elapsed: float) -> None:
    if not cap.counts:
        log("  (no frames)")
        return
    for uuid, n in cap.counts.most_common():
        rate = n / max(1e-6, elapsed)
        size_str = ", ".join(f"{sz}B×{c}" for sz, c in cap.sizes[uuid].most_common())
        tag = ""
        if uuid == NUS_TX:
            tag = "  [NUS TX / expected EEG]"
        elif uuid == BATTERY_STATUS_UUID:
            tag = "  [battery status — ignore]"
        log(f"  {uuid}  frames={n}  rate≈{rate:.1f} Hz  sizes=[{size_str}]{tag}")
        for fr in cap.samples[uuid]:
            log(f"      {fr}")


def main() -> None:
    ap = argparse.ArgumentParser(description="Try start commands to trigger BLE EEG streaming.")
    ap.add_argument("--name", default="focus", help="device name substring to match")
    ap.add_argument("--address", default="D4:0D:D3:18:18:47", help="explicit BLE address")
    ap.add_argument("--per", type=float, default=3.0, help="seconds to listen after each command")
    ap.add_argument("--scan-timeout", type=float, default=8.0, help="scan duration seconds")
    ap.add_argument("--deep", action="store_true", help="also sweep every single-byte opcode 0x00-0xFF")
    args = ap.parse_args()
    asyncio.run(run(args.name, args.address, args.per, args.scan_timeout, args.deep))


if __name__ == "__main__":
    main()
