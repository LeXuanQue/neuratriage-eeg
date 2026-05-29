"""
Convert Figshare-21679035 EDF files -> pipeline-compatible .npz + manifest.csv

Usage:
    python convert_edf_to_npz.py

Output:
    dataset_real/sub-XX.npz        -- EEG arrays for pipeline
    dataset_real/manifest_ischemic.csv  -- manifest with ischemic labels
"""
import warnings
import numpy as np
import pandas as pd
from pathlib import Path

warnings.filterwarnings("ignore")
import mne

EDF_ROOT  = Path(r"C:\Users\Admin\eeg-stroke-app\21679035\edffile")
PARTS_TSV = Path(r"C:\Users\Admin\eeg-stroke-app\21679035\participants.tsv")
OUT_DIR   = Path(r"C:\Users\Admin\eeg-stroke-app\dataset_real")
TARGET_FS = 256.0

PIPELINE_CHANNELS = [
    "C3", "C4", "CZ", "F3", "F4", "F7", "F8", "FZ",
    "FP1", "FP2", "O1", "O2", "P3", "P4", "T3", "T4", "T5", "T6",
]

RENAME = {"Fz": "FZ", "Cz": "CZ", "Pz": "PZ"}
DROP   = {"HEOL", "HEOR", "EOG", ""}


def load_edf(path: Path):
    raw = mne.io.read_raw_edf(str(path), preload=True, verbose=False)
    keep = [ch for ch in raw.ch_names if ch.strip().upper() not in DROP and ch.strip() != ""]
    raw.pick_channels(keep)
    raw.rename_channels({ch: RENAME.get(ch, ch) for ch in raw.ch_names if ch in RENAME})
    raw.resample(TARGET_FS, npad="auto")
    return raw.get_data(), raw.ch_names, TARGET_FS


def reorder(data: np.ndarray, src_channels: list) -> np.ndarray:
    idx = {ch: i for i, ch in enumerate(src_channels)}
    rows = []
    for ch in PIPELINE_CHANNELS:
        if ch in idx:
            rows.append(data[idx[ch]])
        else:
            print(f"  WARNING: {ch} missing — inserting NaN")
            rows.append(np.full(data.shape[1], np.nan))
    return np.vstack(rows)


def main():
    OUT_DIR.mkdir(exist_ok=True)
    parts = pd.read_csv(PARTS_TSV, sep="\t")
    parts.columns = [c.strip() for c in parts.columns]

    rows, ok, fail = [], 0, 0
    for _, p in parts.iterrows():
        pid = str(p["Participant_ID"]).strip()
        edf = EDF_ROOT / pid / "eeg" / f"{pid}_task-motor-imagery_eeg.edf"
        if not edf.exists():
            print(f"[SKIP] {pid}: not found")
            fail += 1
            continue

        print(f"[{pid}]", end=" ")
        try:
            data, chs, fs = load_edf(edf)
            ordered = reorder(data, chs)
            npz = OUT_DIR / f"{pid}.npz"
            np.savez_compressed(npz,
                data=ordered.astype(np.float32),
                channels=np.array(PIPELINE_CHANNELS),
                fs=np.float32(fs),
            )
            print(f"shape={ordered.shape}  OK")
            rows.append({"patient_id": pid, "label": "ischemic", "path": str(npz), "fs": TARGET_FS})
            ok += 1
        except Exception as e:
            print(f"ERROR: {e}")
            fail += 1

    pd.DataFrame(rows).to_csv(OUT_DIR / "manifest_ischemic.csv", index=False)
    print(f"\nConverted {ok}/50  |  failed {fail}")
    print(f"Manifest -> {OUT_DIR / 'manifest_ischemic.csv'}")


if __name__ == "__main__":
    main()
