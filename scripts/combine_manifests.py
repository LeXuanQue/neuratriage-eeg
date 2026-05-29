"""
Merge feature tables into one combined CSV.

Usage:
  .venv/Scripts/python.exe combine_manifests.py
  .venv/Scripts/python.exe combine_manifests.py --include-hemorrhagic

Inputs:
  dataset_real/feature_table_ischemic.csv    (label = 1 / ischemic)
  dataset_healthy/feature_table_healthy.csv  (label = 0 / non-stroke)
  dataset_hemorrhagic/feature_table_hemorrhagic.csv (label = 2 / hemorrhagic)

Output:
  dataset_real/feature_table_combined.csv
  dataset_real/feature_table_combined_3class_exploratory.csv with --include-hemorrhagic
"""
import argparse
import sys
from pathlib import Path

ROOT        = Path(__file__).resolve().parent
ISCHEMIC_CSV = ROOT / "dataset_real"    / "feature_table_ischemic.csv"
HEALTHY_CSV  = ROOT / "dataset_healthy" / "feature_table_healthy.csv"
HEMORRHAGIC_CSV = ROOT / "dataset_hemorrhagic" / "feature_table_hemorrhagic.csv"
BINARY_OUT_CSV = ROOT / "dataset_real" / "feature_table_combined.csv"
THREE_CLASS_OUT_CSV = (
    ROOT / "dataset_real" / "feature_table_combined_3class_exploratory.csv"
)


def _describe(name: str, frame) -> None:
    print(
        f"{name:12s}: {len(frame):6d} windows  "
        f"({frame['patient_id'].nunique()} patients)"
    )


def _ensure_same_columns(frames: list) -> None:
    first = list(frames[0].columns)
    for frame in frames[1:]:
        if list(frame.columns) != first:
            missing = sorted(set(first) - set(frame.columns))
            extra = sorted(set(frame.columns) - set(first))
            raise ValueError(
                "Feature tables have incompatible columns. "
                f"Missing={missing[:8]} Extra={extra[:8]}"
            )


def main():
    import pandas as pd

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--include-hemorrhagic",
        action="store_true",
        help="Include dataset_hemorrhagic as exploratory class 2.",
    )
    parser.add_argument(
        "--out",
        default="",
        help="Optional output CSV. Defaults depend on --include-hemorrhagic.",
    )
    args = parser.parse_args()

    required = [ISCHEMIC_CSV, HEALTHY_CSV]
    if args.include_hemorrhagic:
        required.append(HEMORRHAGIC_CSV)

    for p in required:
        if not p.exists():
            print(f"ERROR: missing {p}")
            print("Run build_feature_table.py for the missing dataset first.")
            sys.exit(1)

    ischemic = pd.read_csv(ISCHEMIC_CSV)
    healthy  = pd.read_csv(HEALTHY_CSV)
    frames = [ischemic, healthy]
    names = ["Ischemic", "Non-stroke"]
    if args.include_hemorrhagic:
        hemorrhagic = pd.read_csv(HEMORRHAGIC_CSV)
        frames.append(hemorrhagic)
        names.append("Hemorrhagic")

    _ensure_same_columns(frames)

    for name, frame in zip(names, frames):
        _describe(name, frame)

    combined = pd.concat(frames, ignore_index=True)
    out_csv = Path(args.out) if args.out else (
        THREE_CLASS_OUT_CSV if args.include_hemorrhagic else BINARY_OUT_CSV
    )
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    combined.to_csv(out_csv, index=False)

    print(f"\nCombined  : {len(combined):6d} windows  "
          f"({combined['patient_id'].nunique()} patients)")
    print(f"Label dist:\n{combined['label'].value_counts().to_string()}")
    print(f"\nSaved -> {out_csv}")
    if args.include_hemorrhagic:
        print("\nExploratory only: current HS patient count is too small for")
        print("validated 3-class patient-level CV.")
    else:
        print("\nNext: run cross-validation + ablation:")
        print("  .venv/Scripts/python.exe run_cv_ablation.py")


if __name__ == "__main__":
    main()
