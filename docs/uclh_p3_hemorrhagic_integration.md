# UCLH Hemorrhagic Integration Note

Status date: 2026-05-10

## Finding

The newly added local UCLH datasets contain the missing hemorrhagic stroke
class.

Evidence:

- Local BDF/log naming uses patient tags `P3`, `P5`, `P6A`, and `P11`.
- The UCLH Stroke EIT Dataset paper identifies these as ICH groups.
- In that dataset, `ICH` is defined as haemorrhage/hemorrhagic stroke.

This means the local class mapping is:

| Local source | Research label | Pipeline label | Pipeline class |
| --- | --- | --- | ---: |
| `Patient_03`, `P3_TD1.bdf` | Big ICH | hemorrhagic | 2 |
| `Patient_05`, `P5_TD1.bdf` | Small ICH | hemorrhagic | 2 |
| `Patient_06a`, `P6a_TD1.bdf` | Big ICH | hemorrhagic | 2 |
| `Patient_11`, `P11_TD1.bdf` | Big ICH | hemorrhagic | 2 |

## Generated Artifacts

```text
dataset_hemorrhagic/
  manifest_hemorrhagic.csv
  p3_td1_preinject_10s.npz
  p5_td1_preinject_20s.npz
  p6a_td1_preinject_20s.npz
  p11_td1_preinject_8s.npz
  feature_table_hemorrhagic.csv
```

Conversion command:

```powershell
.\.venv\Scripts\python.exe scripts/convert_bdf_eit_to_npz.py `
  --input "data\Patient_03 (1)\Patient_03\P3_TD1.bdf" `
  --channels-tsv "data\Patient_03 (1)\Patient_03\Patient_03_channels.tsv" `
  --output "dataset_hemorrhagic\p3_td1_preinject_10s.npz" `
  --start 0 --duration 10 `
  --label hemorrhagic `
  --patient-id uclh_p3_big_ich `
  --manifest "dataset_hemorrhagic\manifest_hemorrhagic.csv"
```

Feature extraction command:

```powershell
.\.venv\Scripts\python.exe scripts/build_feature_table.py `
  --manifest dataset_hemorrhagic\manifest_hemorrhagic.csv `
  --out dataset_hemorrhagic\feature_table_hemorrhagic.csv `
  --workers 1
```

Feature extraction result:

- Patients: 4
- Windows retained: 88
- Label: class `2`
- Exploratory 3-class combined table:
  `dataset_ischemic/feature_table_combined_3class_exploratory.csv`

## Research Interpretation

This is enough to update the project status from "no hemorrhagic data available"
to "hemorrhagic source confirmed and 4 exploratory patients integrated."

It is still not enough to claim final validated 3-class performance under the
planned 5-fold patient-level CV protocol. It is enough for a 4-fold exploratory
check.

Exploratory 4-fold result with 10 Optuna trials per condition/fold:

- `ApFu`: Macro-F1 `0.6467`, patient Macro-F1 `0.7070`.
- `ApFu+MFDFA`: Macro-F1 `0.7546`, patient Macro-F1 `0.8730`.
- `ApFu+SQI`: Macro-F1 `0.8371`, patient Macro-F1 `0.8278`.
- `ApFu+MFDFA+SQI`: Macro-F1 `0.8661`, patient Macro-F1 `0.8860`.
- MFDFA mean delta without SQI: `+0.107811`, p=`0.06354`, positive trend.
- MFDFA mean delta with SQI: `+0.029037`, p=`0.192`, positive trend.
- SQI remains a strong contributor and should be discussed separately from the
  MFDFA contribution.

Recommended next hemorrhagic UCLH patients from the same dataset family:

- `P17` Small ICH.
- `P20` Small ICH.
- `P23` Big ICH.
- `P24` Big ICH.

Once at least 5 HS patients are converted, rerun:

```powershell
.\.venv\Scripts\python.exe scripts/run_mfdfa_ablation.py `
  --feature-table <combined_3class_feature_table.csv> `
  --classes non-stroke,ischemic,hemorrhagic `
  --folds 5 `
  --n-trials 20 `
  --output-prefix mfdfa_ablation_3class
```

## Citation Pointers

- Goren et al., "Multi-frequency electrical impedance tomography and
  neuroimaging data in stroke patients", Scientific Data 5, 180112 (2018).
- UCLH Stroke EIT Dataset repository: `EIT-team/Stroke_EIT_Dataset`.
- Zenodo UCLH Stroke EIT Dataset Patients Part 1 contains `Patient_03.zip`.
