# Hemorrhagic EEG/EIT Extract

Source folders:

```text
data/Patient_03 (1)/Patient_03/
data/Patient_05/Patient_05/
data/Patient_06a/
data/Patient_11/
```

Clinical label:

- Dataset: UCLH Stroke EIT Dataset.
- Local patient tags integrated:
  - `P3` / `Patient_03`: Big ICH.
  - `P5` / `Patient_05`: Small ICH.
  - `P6A` / `Patient_06a`: Big ICH.
  - `P11` / `Patient_11`: Big ICH.
- Pipeline label: `hemorrhagic` / class `2`.

Generated files:

- `p3_td1_preinject_10s.npz` - 10 seconds extracted from `P3_TD1.bdf`, before
  the EIT injection sequence starts in the log at about 10.72 s.
- `p5_td1_preinject_20s.npz` - 20 seconds extracted before injection at about
  25.33 s.
- `p6a_td1_preinject_20s.npz` - 20 seconds extracted before injection at about
  28.19 s.
- `p11_td1_preinject_8s.npz` - 8 seconds extracted before injection at about
  9.05 s.
- `manifest_hemorrhagic.csv` - manifest row for feature extraction.
- `feature_table_hemorrhagic.csv` - 88 retained feature windows after SQI
  filtering.
- `qc_summary.csv` / `qc_summary.json` - per-patient QC summary used by the app
  Insights screen.

Quality notes:

- Converter warnings: high amplitude remains in these BDF extracts, so this
  should be treated as exploratory until the raw EEG quality is reviewed.
- The channel aliases `I1/O9 -> O1` and `I2/O10 -> O2` are mapped in
  `scripts/convert_bdf_eit_to_npz.py` for this dataset family.
- These 4 patients confirm the missing hemorrhagic class is present, but this
  is still below the 5-patient target for 5-fold patient-level CV.
