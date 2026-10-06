"""Brute-force the START command for the Brain-Life Focus+ (Nordic-UART EEG).

ble_probe.py proved the device connects fine but streams NOTHING on its own:
the EEG characteristic (Nordic UART TX 6e400003) stays silent until the host
writes a "start streaming" command to a control characteristic. The datasheet
does not document that command, so this tool discovers it empirically:

  1. Connect and subscribe to every notify characteristic (so we can see any
     stream that appears), ignoring the two battery characteristics.
  2. For each writable control characteristic (Nordic UART RX + the vendor
     "Unknown" 0x1525 char) try a list of common start payloads, one at a time.
  3. After each write, watch the notify channels for ~a few seconds. If a
     non-battery characteristic suddenly bursts frames (rate well above 0), that
     (write_uuid, payload) pair is the start command — reported and saved.

Only two SAFE control characteristics are written to. The SMP characteristic
(firmware/DFU management) and standard GATT internals are never touched.

Run (device on, not paired elsewhere):

    .venv\\Scripts\\python.exe scripts/ble_start_scan.py --address D4:0D:D3:18:18:47
    .venv\\Scripts\\python.exe scripts/ble_start_scan.py --address D4:... --all --dwell 3
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from collections import Counter
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Nordic UART Service — the standard custom-data pipe on nRF devices.
NUS_RX = "6e400002-b5a3-f393-e0a9-e50e24dcca9e"  # host -> device (commands)
NUS_TX = "6e400003-b5a3-f393-e0a9-e50e24dcca9e"  # device -> host (data)
# Vendor "Unknown" control characteristic seen in the GATT dump (also writable).
VENDOR_CTRL = "00001525-1212-efde-1523-e3d498cfb8d7"

# Characteristics that produce data we must NOT count as an EEG stream.
BATTERY_UUIDS = {
    "00002a19-0000-1000-8000-00805f9b34fb",  # Battery Level
    "00002bed-0000-1000-8000-00805f9b34fb",  # Battery Level Status
}
# Never write to these (firmware mgmt / GATT internals) even though writable.
WRITE_BLOCKLIST = {
    "da2e7828-fbce-4e01-ae9e-261174997c48",  # SMP (DFU) — dangerous
    "00002b29-0000-1000-8000-00805f9b34fb",  # Client Supported Features (GATT)
    "00001525-1212-efde-1523-785feabcd123",  # LED — just toggles an LED
}

OUT_PATH = Path(__file__).resolve().parent.parent / "out" / "ble_start_scan.txt"


def _candidates() -> List[Tuple[str, bytes]]:
    """(human label, payload) start commands to try, cheapest/likeliest first."""
    text = [
        "start", "START", "start\r\n", "start\n", "stream", "run", "go",
        "b", "s", "on", "1", "AT+START\r\n",
    ]
    binary = [
        b"\x01", b"\x02", b"\x01\x01", b"\x01\x00", b"\x00\x01",
        b"\xaa", b"\x55", b"\xaa\x55", b"\xff", b"\x02\x01\x00",
    ]
    out: List[Tuple[str, bytes]] = [(f"text:{t!r}", t.encode()) for t in text]
    out += [(f"bytes:{p.hex()}", p) for p in binary]
    return out


def _import_bleak():
    try:
        from bleak import BleakClient, BleakScanner

        return BleakScanner, BleakClient
    except ImportError:
        sys.exit(
            "bleak is not installed:\n"
            "    .venv\\Scripts\\python.exe -m pip install bleak"
        )


async def _resolve(BleakScanner, address: Optional[str], name: str, timeout: float):
    if address and ":" in address:
        return address  # BleakClient accepts a raw address string on Windows.
    print(f"[scan] discovering for {timeout:.0f}s ...")
    devices = await BleakScanner.discover(timeout=timeout)
    for d in devices:
        print(f"  - {d.address}  name={d.name!r}")
    needle = name.lower()
    match = next((d for d in devices if (d.name or "").lower().find(needle) >= 0), None)
    if not match:
        sys.exit(f"[scan] no device matching name {name!r}; pass --address.")
    return match


async def scan(address: Optional[str], name: str, dwell: float,
               scan_timeout: float, try_all: bool, extra: Optional[str]) -> None:
    BleakScanner, BleakClient = _import_bleak()
    target = await _resolve(BleakScanner, address, name, scan_timeout)

    counts: Counter = Counter()

    def cb(sender, _data: bytearray) -> None:
        counts[str(getattr(sender, "uuid", sender))] += 1

    lines: List[str] = []

    def log(msg: str = "") -> None:
        print(msg)
        lines.append(msg)

    hits: List[str] = []
    async with BleakClient(target) as client:
        log(f"[connected] {client.address}")

        # Subscribe to every notify characteristic so any new stream is visible.
        subscribed: List[str] = []
        for service in client.services:
            for ch in service.characteristics:
                if "notify" in ch.properties or "indicate" in ch.properties:
                    if ch.uuid in WRITE_BLOCKLIST:
                        continue
                    try:
                        await client.start_notify(ch.uuid, cb)
                        subscribed.append(ch.uuid)
                    except Exception as exc:  # noqa: BLE001
                        log(f"  ! subscribe {ch.uuid} failed: {exc}")
        log(f"[subscribed] {len(subscribed)} notify char(s)")

        # Writable control characteristics to sweep (safe ones only).
        writables: List[str] = []
        for service in client.services:
            for ch in service.characteristics:
                writable = "write" in ch.properties or "write-without-response" in ch.properties
                if writable and ch.uuid not in WRITE_BLOCKLIST:
                    writables.append(ch.uuid)
        # Prefer Nordic UART RX and the vendor control char, in that order.
        order = {NUS_RX: 0, VENDOR_CTRL: 1}
        writables.sort(key=lambda u: order.get(u, 9))
        log(f"[write targets] {writables}")

        cmds = list(_candidates())
        if extra:
            cmds.insert(0, (f"custom:{extra!r}", extra.encode()))

        def data_rate_excluding_battery(snapshot: Counter) -> Dict[str, float]:
            return {
                u: c / dwell
                for u, c in snapshot.items()
                if u not in BATTERY_UUIDS and c > 0
            }

        log(f"\n=== sweeping {len(cmds)} commands x {len(writables)} targets, "
            f"dwell={dwell:.1f}s ===")
        for w_uuid in writables:
            for label, payload in cmds:
                before = Counter(counts)
                ok = await _try_write(client, w_uuid, payload)
                if not ok:
                    continue
                await asyncio.sleep(dwell)
                delta = counts - before
                streams = data_rate_excluding_battery(delta)
                if streams:
                    best = ", ".join(f"{u}≈{r:.1f}Hz" for u, r in streams.items())
                    log(f"  ✔ HIT  write {w_uuid}  <= {label}  -> {best}")
                    hits.append(f"write {w_uuid}  payload {label}  streams: {best}")
                    if not try_all:
                        break
                else:
                    log(f"    .  {w_uuid} <= {label}: no stream")
            if hits and not try_all:
                break

        for u in subscribed:
            try:
                await client.stop_notify(u)
            except Exception:  # noqa: BLE001
                pass

    log("\n=== result ===")
    if hits:
        for h in hits:
            log(f"  START FOUND -> {h}")
        log("\nNext: put this payload in device_source.py:")
        log("  start_command_uuid = <write uuid above>")
        log("  start_command      = <payload bytes>")
    else:
        log("  No start command found. Try: --all (sweep every combo),")
        log("  a longer --dwell, or --extra '<your guess>'. The command may also")
        log("  be multi-step (handshake) — capturing the vendor app is then needed.")

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(f"\n[done] written to {OUT_PATH}")


async def _try_write(client, uuid: str, payload: bytes) -> bool:
    """Write payload, preferring write-without-response, falling back to response."""
    for response in (False, True):
        try:
            await client.write_gatt_char(uuid, payload, response=response)
            return True
        except Exception:  # noqa: BLE001
            continue
    return False


def main() -> None:
    ap = argparse.ArgumentParser(description="Brute-force the EEG start command.")
    ap.add_argument("--address", default=None, help="BLE address (e.g. D4:0D:D3:18:18:47)")
    ap.add_argument("--name", default="focus", help="name substring if no --address")
    ap.add_argument("--dwell", type=float, default=2.5, help="seconds to watch after each write")
    ap.add_argument("--scan-timeout", type=float, default=8.0)
    ap.add_argument("--all", action="store_true", help="try every combo (don't stop at first hit)")
    ap.add_argument("--extra", default=None, help="one custom command string to try first")
    args = ap.parse_args()
    asyncio.run(scan(args.address, args.name, args.dwell, args.scan_timeout, args.all, args.extra))


if __name__ == "__main__":
    main()
