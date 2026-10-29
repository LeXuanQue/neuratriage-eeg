# Brain-Life Focus+ — device bring-up guide

Goal: connect the real headband and stream EEG into NeuraTriage **without
guessing the wire protocol**. The public datasheet
(`2026-02-12 - Brain-Life Focus+ technical specifications.pdf`) gives hardware
facts but **not** the BLE GATT protocol. So we discover it from the device, then
fill the decoder with measured values.

## What the datasheet tells us (confirmed)

| Item | Value |
|------|-------|
| Transport | Bluetooth 6.0 **LE**, range ~10 m, OTA firmware, USB-C charge only |
| EEG | **2 differential channels** from electrodes F3, F4, T7, T8 (10–20): F3-T7 (left), F4-T8 (right) |
| EEG rate | 256 Hz (configurable), band 0.5–100 Hz, noise <5 µV p-p |
| fNIRS | 100 Hz (HbO₂/HHb, 740 & 850 nm) |
| PPG | 100–200 Hz (HR 30–220 BPM, HRV) |
| Battery | 400 mAh, RGB LED status; auto-resume sync after disconnect |
| Intended use | **Not a medical diagnostic device** (focus/wellness/research) |

## What it does NOT tell us (must be discovered)

- GATT service / characteristic **UUIDs** for EEG, fNIRS, PPG, battery
- EEG **frame layout**: header/counter, samples-per-frame, channel interleaving
- Sample **encoding**: int16 / int24 / float32, little/big-endian
- **µV scaling** (raw LSB → microvolt)
- Whether a **start command** must be written before streaming

## Step 1 — Probe the device

Headband on, Bluetooth on, not connected in the vendor app, then:

```bat
.venv\Scripts\python.exe -m pip install bleak
.venv\Scripts\python.exe scripts\ble_probe.py --seconds 10
```

It scans, lists devices, connects to the one whose name contains `Brain`
(override with `--address AA:BB:...`), enumerates all GATT
services/characteristics, subscribes to every notify characteristic for 10 s,
and writes `out/ble_probe_capture.txt` with, per characteristic: frame count,
**rate (Hz)**, **byte-length histogram**, and the first frames as hex.

## Step 2 — Identify the EEG characteristic

From the capture:

- **EEG** ≈ 256 Hz, one fixed frame size. Infer samples/frame:
  `payload_bytes / sample_size / 2 channels`. e.g. a steady 20-byte payload at
  256 Hz with 2 ch int16 → `20/2/2 = 5` samples/frame × 256 Hz ≈ matches.
- **fNIRS/PPG** ≈ 100–200 Hz.
- **Battery** usually standard `0x2A19` (the probe reads it directly).

Infer **dtype/endianness** from the byte math + sanity of values (EEG noise is
<5 µV p-p; decoded amplitudes should look like tens of µV, not millions of
counts). If unsure, capture eyes-open vs eyes-closed and check the alpha (8–12
Hz) rise on the occipital-ish channels.

## Step 3 — Fill the decoder

Edit `backend/app/services/device_source.py` → `BRAIN_LIFE_FOCUS_PLUS`:

```python
BRAIN_LIFE_FOCUS_PLUS = DeviceProtocol(
    name="Brain-Life Focus+",
    eeg_char_uuid="<EEG characteristic UUID from probe>",
    battery_char_uuid="00002a19-0000-1000-8000-00805f9b34fb",
    channel_labels=[...],          # see "differential channels" note below
    fs=256.0,
    decoder=EEGFrameDecoder(
        dtype="int16",             # confirm
        endian="little",           # confirm
        n_channels=2,
        header_bytes=0,            # set if frames start with a counter/flags
        scale_uv=<LSB->µV factor>, # confirm
    ),
    start_command=None,            # set bytes + start_command_uuid if needed
    configured=True,               # flip ONLY after the above is verified
)
```

`BleDeviceSource.run()` refuses to stream while `configured=False`, so
placeholders can never silently feed garbage into the detector.

## Step 4 — Validate before trusting

- Re-run a short capture through the decoder; confirm shape `(2, N)` and µV-scale
  amplitudes.
- `pytest backend/tests/test_device_decode.py` (decode math).
- Eyes-closed alpha sanity check as above.

## ⚠️ Differential channels — a real modelling caveat

The pipeline/model was trained on a **monopolar** 18-channel montage. The Focus+
gives **2 differential (bipolar) channels**: F3-T7 (left), F4-T8 (right).
`channel_labels=["F3-T7","F4-T8"]` names them as bipolar derivations, which
intentionally do **not** alias onto monopolar T3/T4 in `channel_mapper.py` — a
bipolar signal is not equivalent to either of its monopolar electrodes under the
training montage's CAR reference, so treating it as such would be scientifically
wrong. `map_to_pipeline` therefore leaves all 18 target rows NaN, which
`fill_nan_channels` zero-fills; the live path stays **exploratory**, not
validated evidence — this repo's Hybrid demo design classifies from the
validated offline replay path, using the live device only to drive real SQI /
No-Decision behavior. A same-rig probe confirms the 2-channel montage itself
carries real pathology signal when features are computed natively on the
bipolar pair (AUC ~0.80, see `scripts/run_headband_eval.py`); wiring that
dedicated bipolar feature path into a production classifier is future work, not
done here. Confirm the exact pairing with the vendor before any quantitative
claim. Validated evidence remains the offline 50-ischemic + 50-healthy dataset
(see `docs/uist_evidence.md`).

## Step 5 — Wire into the app (after the decoder is confirmed)

`BleDeviceSource(on_chunk=...)` is designed to feed the **same path as replay**:
each decoded chunk + `channel_labels` goes through
`channel_mapper.map_to_pipeline(...)` → the session's `RealTimeStrokeDetector`,
and events are emitted over the existing `/ws/stream/{session_id}` socket. This
backend-side wiring is the next step once Step 3–4 pass on real hardware.
