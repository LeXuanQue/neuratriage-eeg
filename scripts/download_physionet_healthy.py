"""
Download PhysioNet EEG Motor Movement/Imagery dataset (healthy subjects) and
convert to pipeline-compatible .npz files.

Dataset: https://physionet.org/content/eegmmidb/1.0.0/
  109 healthy subjects, 64 channels, 160 Hz
  Run 1 = baseline eyes-open  (60 s)
  Run 2 = baseline eyes-closed (60 s)
  Concatenate runs 1+2 -> ~120 s resting-state per subject.

Output:
  dataset_healthy/sub-S001.npz  ...  sub-S109.npz
  dataset_healthy/manifest_healthy.csv  (label = non-stroke)

Usage:
  .venv/Scripts/python.exe scripts/download_physionet_healthy.py
  .venv/Scripts/python.exe scripts/download_physionet_healthy.py --subjects 20
"""
import argparse
import time
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "dataset_healthy"
MNE_DATA_DIR = ROOT / "mne_data"   # pre-set so MNE never prompts interactively
TARGET_FS = 256.0
RUNS = [1, 2]  # resting baseline: eyes-open + eyes-closed

PIPELINE_CHANNELS = [
    "C3", "C4", "CZ", "F3", "F4", "F7", "F8", "FZ",
    "FP1", "FP2", "O1", "O2", "P3", "P4", "T3", "T4", "T5", "T6",
]

# BCI2000 (PhysioNet) -> 10-20 standard names used by the pipeline
RENAME = {
    "Cz": "CZ", "Fz": "FZ", "Pz": "PZ",
    "Fp1": "FP1", "Fp2": "FP2", "Fpz": "FPZ",
    "T7": "T3", "T8": "T4",   # CHANNEL_ALIASES in pipeline
    "P7": "T5", "P8": "T6",   # CHANNEL_ALIASES in pipeline
}


def convert_subject(subject_id: int) -> dict | None:
    import os
    import mne
    import numpy as np

    # Set env var before MNE reads config — avoids interactive "set path?" prompt
    MNE_DATA_DIR.mkdir(parents=True, exist_ok=True)
    os.environ["MNE_DATA"] = str(MNE_DATA_DIR)

    subj_str = f"S{subject_id:03d}"
    out_npz = OUT_DIR / f"sub-{subj_str}.npz"

    try:
        fnames = mne.datasets.eegbci.load_data(
            subjects=subject_id, runs=RUNS,
            path=str(MNE_DATA_DIR),
            update_path=False,  # never prompt to save path to MNE config
            verbose=False,
        )
        raws = [mne.io.read_raw_edf(f, preload=True, verbose=False) for f in fnames]
        raw = mne.concatenate_raws(raws, verbose=False)

        # PhysioNet eegmmidb stores channel names with trailing dots and
        # padding (e.g. "Fp1.", "Cz..", "Fc5."). Strip those so RENAME and
        # the idx_map lookup actually match — without this every channel
        # silently becomes NaN downstream.
        raw.rename_channels({ch: ch.strip().strip(".") for ch in raw.ch_names})

        raw.rename_channels({ch: RENAME[ch] for ch in raw.ch_names if ch in RENAME})
        raw.resample(TARGET_FS, npad="auto", verbose=False)

        data_all = raw.get_data()
        idx_map = {ch.upper(): i for i, ch in enumerate(raw.ch_names)}

        ordered_rows = []
        for ch in PIPELINE_CHANNELS:
            if ch in idx_map:
                ordered_rows.append(data_all[idx_map[ch]])
            else:
                ordered_rows.append(np.full(data_all.shape[1], np.nan))

        ordered = np.vstack(ordered_rows).astype(np.float32)
        np.savez_compressed(
            out_npz,
            data=ordered,
            channels=np.array(PIPELINE_CHANNELS),
            fs=np.float32(TARGET_FS),
        )
        return {
            "patient_id": f"ns-{subj_str}",
            "label": "non-stroke",
            "path": str(out_npz),
            "fs": TARGET_FS,
        }

    except Exception as exc:
        print(f"    ERROR: {exc}")
        return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--subjects", type=int, default=109,
                        help="How many subjects to download (1-109). Default: all 109.")
    args = parser.parse_args()

    n = min(max(1, args.subjects), 109)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    print(f"Downloading PhysioNet EEGMMIDB: {n} healthy subjects")
    print(f"Runs: {RUNS}  (eyes-open + eyes-closed resting baseline)")
    print(f"Output dir: {OUT_DIR}\n")

    manifest_rows = []
    ok = fail = 0
    t_start = time.time()

    for i, subj_id in enumerate(range(1, n + 1), start=1):
        subj_str = f"S{subj_id:03d}"
        print(f"  [{i:3d}/{n}] {subj_str}", end="", flush=True)
        row = convert_subject(subj_id)
        if row:
            manifest_rows.append(row)
            ok += 1
            elapsed = time.time() - t_start
            eta_min = (elapsed / i) * (n - i) / 60
            print(f"  OK  [ETA {eta_min:.1f} min]")
        else:
            fail += 1
            print()

    import pandas as pd
    manifest_path = OUT_DIR / "manifest_healthy.csv"
    pd.DataFrame(manifest_rows).to_csv(manifest_path, index=False)

    total_min = (time.time() - t_start) / 60
    print(f"\nDone: {ok} OK  |  {fail} failed  |  {total_min:.1f} min total")
    print(f"Manifest -> {manifest_path}")
    print()
    print("Next: build healthy feature table:")
    print(f"  .venv/Scripts/python.exe build_feature_table.py"
          f" --manifest {manifest_path}"
          f" --out {OUT_DIR / 'feature_table_healthy.csv'}")


if __name__ == "__main__":
    main()
