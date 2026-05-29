"""
Convert BioSemi BDF EEG/EIT recordings to pipeline-compatible NPZ files.

This is meant for datasets like data/Patient_01 where the BDF uses BioSemi
channel labels A1..A32 and a *_channels.tsv file maps them to 10-20 names.

The converter is conservative:
- it does not assign clinical labels by itself;
- it excludes the Status/stim channel;
- it renames channels using the TSV;
- it crops a selected time range;
- it downsamples from 16384 Hz to 256 Hz;
- it reorders to the pipeline's 18 default channels and inserts NaN for missing
  channels so the existing pipeline preprocessing can handle them.

Example:
  .venv\\Scripts\\python.exe convert_bdf_eit_to_npz.py \\
    --input data\\Patient_01\\P1_TD1.bdf \\
    --channels-tsv data\\Patient_01\\Patient_01_channels.tsv \\
    --output data\\converted\\Patient_01_TD1_20s.npz \\
    --start 20 --duration 20 --label unlabeled
"""
from __future__ import annotations

import argparse
import json
import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")

import mne
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from eeg_stroke_pipeline import (  # noqa: E402
    DEFAULT_CHANNELS,
    reorder_to_target_channels,
)


TARGET_FS = 256.0
ALIASES = {
    "Fz": "FZ",
    "Cz": "CZ",
    "Pz": "PZ",
    "Fp1": "FP1",
    "Fp2": "FP2",
    "T7": "T3",
    "T8": "T4",
    "P7": "T5",
    "P8": "T6",
    "I1/O9": "O1",
    "I2/O10": "O2",
}


def read_channel_map(channels_tsv: Path, n_eeg_channels: int) -> dict[str, str]:
    table = pd.read_csv(channels_tsv, sep="\t")
    if "particap" not in table.columns:
        raise ValueError(f"{channels_tsv} must contain a 'particap' column.")
    names = [str(x).strip() for x in table["particap"].tolist()[:n_eeg_channels]]
    if len(names) < n_eeg_channels:
        raise ValueError(
            f"{channels_tsv} has {len(names)} mapped channels, "
            f"but BDF has {n_eeg_channels} EEG channels."
        )
    return {f"A{i + 1}": ALIASES.get(name, name.upper()) for i, name in enumerate(names)}


def robust_scale_to_volts(data: np.ndarray) -> tuple[np.ndarray, str]:
    """MNE returns volts for normal BDF. Some EIT BDF files can still contain
    huge values after conversion; leave them as-is but report a warning string.
    """
    peak_uv = float(np.nanpercentile(np.abs(data), 99.5) * 1e6)
    if peak_uv > 5000:
        return data, (
            f"high_amplitude_warning: p99.5={peak_uv:.1f} uV. "
            "This EIT recording likely contains injection artifact."
        )
    return data, ""


def convert(
    input_path: Path,
    channels_tsv: Path,
    output_path: Path,
    start: float,
    duration: float | None,
    target_fs: float,
) -> dict:
    raw = mne.io.read_raw_bdf(str(input_path), preload=False, verbose="ERROR")
    eeg_chs = [ch for ch in raw.ch_names if ch.lower() != "status"]
    mapping = read_channel_map(channels_tsv, len(eeg_chs))
    raw.rename_channels({ch: mapping[ch] for ch in eeg_chs if ch in mapping})
    raw.pick([ch for ch in raw.ch_names if ch.lower() != "status"])

    tmin = max(0.0, float(start))
    tmax = None
    if duration is not None:
        tmax = min(raw.times[-1], tmin + float(duration))
    raw.crop(tmin=tmin, tmax=tmax, include_tmax=False)

    raw.load_data(verbose="ERROR")
    raw.notch_filter(freqs=[50.0], verbose="ERROR")
    raw.filter(l_freq=0.5, h_freq=45.0, verbose="ERROR")
    raw.resample(target_fs, npad="auto", verbose="ERROR")

    data = raw.get_data()
    data, warning = robust_scale_to_volts(data)
    ordered = reorder_to_target_channels(data, raw.ch_names, DEFAULT_CHANNELS)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        output_path,
        data=ordered.astype(np.float32),
        channels=np.asarray(DEFAULT_CHANNELS),
        fs=np.float32(target_fs),
        source=str(input_path),
        source_channels=np.asarray(raw.ch_names),
        start_sec=np.float32(tmin),
        duration_sec=np.float32(ordered.shape[1] / target_fs),
    )

    return {
        "output": str(output_path),
        "source": str(input_path),
        "shape": [int(ordered.shape[0]), int(ordered.shape[1])],
        "fs": float(target_fs),
        "duration_sec": float(ordered.shape[1] / target_fs),
        "channels": list(DEFAULT_CHANNELS),
        "source_channels": list(raw.ch_names),
        "warning": warning,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="Input .bdf file.")
    parser.add_argument("--channels-tsv", required=True, help="Patient channels TSV.")
    parser.add_argument("--output", required=True, help="Output .npz path.")
    parser.add_argument("--start", type=float, default=20.0)
    parser.add_argument("--duration", type=float, default=20.0)
    parser.add_argument("--target-fs", type=float, default=TARGET_FS)
    parser.add_argument(
        "--label",
        default="unlabeled",
        help="Optional manifest label. Use only if clinically verified.",
    )
    parser.add_argument(
        "--manifest",
        default="",
        help="Optional manifest CSV to append/create.",
    )
    parser.add_argument(
        "--patient-id",
        default="",
        help="Optional patient_id for manifest. Defaults to output stem.",
    )
    args = parser.parse_args()

    info = convert(
        input_path=Path(args.input),
        channels_tsv=Path(args.channels_tsv),
        output_path=Path(args.output),
        start=args.start,
        duration=args.duration,
        target_fs=args.target_fs,
    )

    if args.manifest:
        manifest = Path(args.manifest)
        row = {
            "patient_id": args.patient_id or Path(args.output).stem,
            "label": args.label,
            "path": str(Path(args.output).resolve()),
            "fs": args.target_fs,
        }
        if manifest.exists():
            df = pd.read_csv(manifest)
            df = pd.concat([df, pd.DataFrame([row])], ignore_index=True)
        else:
            manifest.parent.mkdir(parents=True, exist_ok=True)
            df = pd.DataFrame([row])
        df.to_csv(manifest, index=False)
        info["manifest"] = str(manifest)
        info["manifest_row"] = row

    print(json.dumps(info, indent=2))


if __name__ == "__main__":
    main()
