"""BLE bring-up / discovery tool for the Brain-Life Focus+ (and any BLE device).

The public datasheet does NOT document the GATT protocol (service/characteristic
UUIDs, packet layout, sample encoding, µV scaling). This script discovers those
*from the real device* so the decoder can be filled with measured facts instead
of guesses:

  1. Scan for the headband (by name substring or explicit address).
  2. Enumerate every GATT service + characteristic (UUID + properties).
  3. Subscribe to every notify/indicate characteristic and capture raw frames.
  4. Report, per characteristic: frame count, byte-length histogram, observed
     rate (Hz), and the first few frames as hex — enough to identify which
     characteristic is EEG (≈256 Hz, fixed frame size) vs fNIRS/PPG (≈100 Hz)
     vs battery, and to infer dtype/endianness/samples-per-frame.
  5. Read the standard Battery Level characteristic (0x2A19) if present.

Run (device powered on, Bluetooth on, not paired in another app):

    .venv\\Scripts\\python.exe scripts/ble_probe.py --seconds 10
    .venv\\Scripts\\python.exe scripts/ble_probe.py --address AA:BB:CC:DD:EE:FF

Nothing here is device-specific or destructive — it only listens.
"""
from __future__ import annotations

import argparse
import asyncio
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, List, Optional

# Standard 16-bit Battery Level characteristic (Battery Service 0x180F).
BATTERY_LEVEL_UUID = "00002a19-0000-1000-8000-00805f9b34fb"

OUT_PATH = Path(__file__).resolve().parent.parent / "out" / "ble_probe_capture.txt"


def _import_bleak():
    try:
        import bleak  # noqa: F401
        from bleak import BleakClient, BleakScanner

        return BleakScanner, BleakClient
    except ImportError:
        sys.exit(
            "bleak is not installed. Install it first:\n"
            "    .venv\\Scripts\\python.exe -m pip install bleak\n"
            "(bleak is the cross-platform Python BLE client; Windows uses WinRT.)"
        )


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
        sys.exit(
            f"[scan] no device whose name contains {name!r}. "
            f"Pass --address with one of the addresses listed above."
        )
    return match


def _hex(data: bytes, limit: int = 40) -> str:
    head = data[:limit]
    s = head.hex(" ")
    return s + (" …" if len(data) > limit else "")


async def probe(name: str, address: Optional[str], seconds: float, scan_timeout: float) -> None:
    BleakScanner, BleakClient = _import_bleak()
    device = await _scan(BleakScanner, name, address, scan_timeout)
    print(f"\n[connect] {device.address} ({device.name!r}) ...")

    # Per-characteristic capture buffers.
    counts: Counter = Counter()
    sizes: Dict[str, Counter] = defaultdict(Counter)
    first_frames: Dict[str, List[str]] = defaultdict(list)

    def make_cb(uuid: str):
        def _cb(_sender, data: bytearray) -> None:
            counts[uuid] += 1
            sizes[uuid][len(data)] += 1
            if len(first_frames[uuid]) < 5:
                first_frames[uuid].append(_hex(bytes(data)))

        return _cb

    lines: List[str] = []

    def log(msg: str = "") -> None:
        print(msg)
        lines.append(msg)

    async with BleakClient(device) as client:
        log(f"[connected] {device.address} ({device.name!r})")
        log("\n=== GATT services / characteristics ===")
        notify_uuids: List[str] = []
        for service in client.services:
            log(f"service {service.uuid}  ({service.description})")
            for ch in service.characteristics:
                props = ",".join(ch.properties)
                log(f"  char {ch.uuid}  [{props}]  ({ch.description})")
                if "notify" in ch.properties or "indicate" in ch.properties:
                    notify_uuids.append(ch.uuid)

        # Battery level (best-effort).
        try:
            val = await client.read_gatt_char(BATTERY_LEVEL_UUID)
            log(f"\n[battery] 0x2A19 = {int(val[0])}%")
        except Exception:
            log("\n[battery] standard 0x2A19 not readable (device may use a custom field)")

        log(f"\n=== subscribing to {len(notify_uuids)} notify/indicate char(s) for {seconds:.0f}s ===")
        started: List[str] = []
        for uuid in notify_uuids:
            try:
                await client.start_notify(uuid, make_cb(uuid))
                started.append(uuid)
            except Exception as exc:  # noqa: BLE001
                log(f"  ! could not subscribe {uuid}: {exc}")

        t0 = time.monotonic()
        await asyncio.sleep(seconds)
        elapsed = max(1e-6, time.monotonic() - t0)

        for uuid in started:
            try:
                await client.stop_notify(uuid)
            except Exception:
                pass

        log("\n=== capture summary ===")
        if not counts:
            log("No frames received. Device may need a start command before streaming,")
            log("or the data characteristic uses 'read' instead of 'notify'.")
        for uuid in started:
            n = counts[uuid]
            rate = n / elapsed
            size_str = ", ".join(f"{sz}B×{c}" for sz, c in sizes[uuid].most_common())
            log(f"\nchar {uuid}")
            log(f"  frames={n}  rate≈{rate:.1f} Hz  sizes=[{size_str}]")
            for fr in first_frames[uuid]:
                log(f"    {fr}")
            # Heuristic hint.
            if 200 <= rate <= 320:
                log("  → candidate EEG stream (≈256 Hz)")
            elif 80 <= rate <= 220:
                log("  → candidate fNIRS/PPG stream (≈100–200 Hz)")

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(f"\n[done] capture written to {OUT_PATH}")
    print("Next: use the byte sizes + rates to fill BRAIN_LIFE_FOCUS_PLUS in")
    print("backend/app/services/device_source.py (see docs/device_bring_up.md).")


def main() -> None:
    ap = argparse.ArgumentParser(description="BLE discovery/bring-up probe.")
    ap.add_argument("--name", default="Brain", help="device name substring to match")
    ap.add_argument("--address", default=None, help="explicit BLE address (overrides --name)")
    ap.add_argument("--seconds", type=float, default=10.0, help="capture window seconds")
    ap.add_argument("--scan-timeout", type=float, default=8.0, help="scan duration seconds")
    args = ap.parse_args()
    asyncio.run(probe(args.name, args.address, args.seconds, args.scan_timeout))


if __name__ == "__main__":
    main()
