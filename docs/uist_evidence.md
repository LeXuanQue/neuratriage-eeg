# UIST Demo Evidence

Status date: 2026-05-10

NeuraTriage EEG is positioned as an EEG triage-support research prototype. It is
not a medical device, not a diagnosis system, and not a replacement for CT/MRI or
clinical assessment.

## Current Validated Task

- Task: binary ischemic-vs-non-stroke research classification.
- Ischemic cohort: `dataset_ischemic/`, 50 patients.
- Non-stroke cohort: `dataset_healthy/`, 50 PhysioNet resting-baseline subjects.
- Combined feature table: `dataset_ischemic/feature_table_combined.csv`.
- Main result files:
  - `results/mfdfa_ablation_results.json`
  - `results/mfdfa_ablation_summary.txt`
  - `results/cv_summary.txt`

## Exploratory Hemorrhagic Addition

- Source: UCLH Stroke EIT Dataset.
- Integrated tags: `P3` Big ICH, `P5` Small ICH, `P6A` Big ICH, `P11` Big ICH.
- Pipeline label: `hemorrhagic`, class `2`.
- Feature table: `dataset_hemorrhagic/feature_table_hemorrhagic.csv`.
- Retained windows: 88 from 4 patients.
- Exploratory 3-class table:
  `dataset_ischemic/feature_table_combined_3class_exploratory.csv`.

This confirms the missing class is present in the newly added dataset. Four HS
patients are enough for a 4-fold exploratory check, but still short of the
planned 5-fold patient-level CV target.

Exploratory 4-fold result on NS/IS/HS with 10 Optuna trials per condition/fold:

| Condition | Macro-F1 | Patient Macro-F1 |
| --- | ---: | ---: |
| ApFu | 0.6467 | 0.7070 |
| ApFu + MFDFA | 0.7546 | 0.8730 |
| ApFu + SQI | 0.8371 | 0.8278 |
| ApFu + MFDFA + SQI | 0.8661 | 0.8860 |

MFDFA delta without SQI: +0.107811 Macro-F1, p=0.06354. With SQI:
+0.029037, p=0.192. Present this as an exploratory positive trend, not as a
statistically validated 3-class claim.

## Ablation Summary

| Condition | Macro-F1 |
| --- | ---: |
| ApFu | 0.7924 |
| ApFu + MFDFA | 0.8225 |
| ApFu + SQI | 0.9911 |
| ApFu + MFDFA + SQI | 0.9913 |

Paired comparison:

- MFDFA gain without SQI: mean delta +0.030048, p=0.02073.
- MFDFA gain with SQI: mean delta +0.000171, p=0.7268.

Interpretation for demo: MFDFA adds measurable signal in the ApFu-only setting,
while SQI dominates the current binary split. This should be presented as
research evidence, not a clinical performance claim.

## Demo-Safe Claims

Use:

- "EEG risk pattern detected"
- "triage support"
- "research prototype"
- "binary ischemic-vs-non-stroke evidence"
- "confirm through standard stroke workflow and imaging when indicated"

Avoid:

- "stroke detected"
- "diagnosis"
- "no CT needed"
- "replaces CT/MRI"
- "validated hemorrhagic detection"
- "validated 3-class NS/IS/HS performance"

## Known Limitations

- The current validated result is still binary. A real hemorrhagic source has
  been integrated for 4 patients, but the HS sample is exploratory until at
  least one more UCLH hemorrhagic patient is converted for planned 5-fold CV.
- Healthy resting EEG is not a perfect clinical non-stroke control.
- Metrics are internal research results and should be treated as replayable
  evidence for the prototype, not deployment-grade clinical validation.
- Further work needs a real HS cohort, external validation, prospective workflow
  testing, and clinician-facing usability evidence.

## UIST Demo Focus

The demo should emphasize the interaction loop:

1. Stream/replay EEG data.
2. Show risk probabilities and SQI.
3. Explain "why this alert" with top signals and confidence.
4. Route review through clinician actions, patient records, alerts, and PDF
   reports.
5. Keep the limitation visible: research prototype, no diagnostic claim.
