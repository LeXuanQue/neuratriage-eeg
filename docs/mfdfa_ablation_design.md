# MFDFA Ablation Design

Goal: test whether MFDFA adds measurable value beyond ApFu entropy features.

## Why Redesign

The previous `scripts/run_cv_ablation.py` labels one condition as `ApFu-only`, but that
condition actually uses `ApFu + SQI`. This can hide the independent effect of
MFDFA because SQI may already explain most of the separability.

The redesigned experiment uses `scripts/run_mfdfa_ablation.py` and separates feature
families:

```text
ApFu
MFDFA
ApFu + MFDFA
ApFu + SQI
ApFu + MFDFA + SQI
```

Optional condition:

```text
SQI
```

## Rule For Claiming Improvement

MFDFA is considered useful only if one or both paired comparisons improves
consistently across patient-wise folds:

```text
ApFu + MFDFA       > ApFu
ApFu + MFDFA + SQI > ApFu + SQI
```

The script reports fold-wise paired deltas and a paired t-test p-value. With
only five folds, the p-value is supportive evidence, not final proof.

## Commands

Fast sanity check:

```bat
.venv\Scripts\python.exe scripts/run_mfdfa_ablation.py --fast --folds 3 --n-trials 0
```

Report run on the current binary table:

```bat
.venv\Scripts\python.exe scripts/run_mfdfa_ablation.py --folds 5 --n-trials 30
```

Run on a new dataset feature table:

```bat
.venv\Scripts\python.exe scripts/run_mfdfa_ablation.py --feature-table path\to\feature_table.csv --folds 5 --n-trials 30
```

Run only selected labels:

```bat
.venv\Scripts\python.exe scripts/run_mfdfa_ablation.py --feature-table path\to\feature_table.csv --classes non-stroke,ischemic,hemorrhagic --folds 5 --n-trials 30
```

## Outputs

```text
results/mfdfa_ablation_results.json
results/mfdfa_ablation_summary.txt
```

## Current Local Result

Fast 5-fold patient-wise run on `dataset_ischemic/feature_table_combined.csv`
without Optuna:

```text
Condition           Feat  MacroF1     std     ptF1      AUC      ECE
ApFu                  60   0.7924  0.0590   0.9592   0.8935   0.0383
MFDFA                 60   0.7177  0.0481   0.8993   0.8198   0.0420
ApFu+MFDFA           120   0.8225  0.0478   0.9696   0.9172   0.0235
ApFu+SQI              65   0.9911  0.0027   1.0000   0.9997   0.0029
ApFu+MFDFA+SQI       125   0.9913  0.0032   1.0000   0.9997   0.0031
```

Paired fold delta:

```text
ApFu+MFDFA - ApFu       = +0.030048 MacroF1, p=0.02073
ApFu+MFDFA+SQI - ApFu+SQI = +0.000171 MacroF1, p=0.7268
```

Interpretation: MFDFA improves over ApFu when SQI is not included. After SQI is
included, the binary task is near saturated and MFDFA adds no meaningful gain.

## Dataset Requirement

For a strong claim against Tong et al. 2025, use a patient-wise three-class
dataset:

```text
non-stroke / ischemic / hemorrhagic
```

The current local result is binary ischemic-vs-non-stroke, so it can test the
feature contribution but cannot fully prove superiority over Tong's three-class
setting.
