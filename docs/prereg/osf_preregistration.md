# OSF Preregistration: Study 1 and Study 2

_Draft 2026-11-17, from `docs/user_study_protocol.md` (sections 1–2). Follows the "OSF Preregistration" template. Submit after ethics approval and **before the first session**, including pilots if pilot data are used to revise assumptions. Fields in [brackets] are filled at submission. Keep author names out of the public version until review ends (embargo or anonymised link)._

---

## 1. Study information

**Title.** Actionable abstention for non-expert EEG: per-channel guidance during acquisition (Study 1) and the wording of "No-Decision" (Study 2).

**Authors.** [names, affiliations]

**Description.** A triage interface scores every channel of a 2-electrode EEG headband in real time and, in its guided condition, names the channel to fix, the reason and one action. A patient-level conformal rule lets the system withhold a decision ("No-Decision") with a false-alert bound. Study 1 tests whether the per-channel guidance helps novices acquire usable EEG faster than a per-channel quality indicator alone. Study 2 tests whether wording No-Decision as an action ("not normal, continue the stroke pathway") reduces missed strokes compared with a plain wording.

**Hypotheses.**

| | Hypothesis | Direction |
|---|---|---|
| H1 (primary, Study 1) | Time to usable signal (TTU) is shorter with guidance (G) than with the indicator only (B) | G < B |
| H2 | More runs reach usable signal within 8 min in G | G > B |
| H3 | Operators identify the planted fault's cause correctly more often in G | G > B |
| H4 | Workload (NASA-TLX) is lower and usability (SUS) higher in G | TLX G < B; SUS G > B |
| H5 (primary, Study 2) | On stroke vignettes where the system returns No-Decision, stroke-pathway activation is higher with the actionable wording (F-A) than the plain wording (F-P) | F-A > F-P |
| H6 | In F-P, activation on stroke vignettes is lower with No-Decision than with no AI output | ND < no-AI |
| H7 | In F-A, activation with No-Decision is not lower than with no AI output, by more than 10 percentage points (non-inferiority) | ND ≥ no-AI − 10 pp |

## 2. Design plan

**Study type.** Experiment (randomised).

**Blinding.**
- Study 1: participants are not told which interface is new. The TTU rater sees shuffled 10 s epochs without participant, condition or run. The experimenter cannot be blind to condition.
- Study 2: participants are not told that the No-Decision wording differs between groups (debrief at the end). Group is assigned by the survey platform.

**Study design.**
- Study 1: within-subjects, 2 conditions (B, G). Each operator does one run per condition on a different healthy wearer, each run starting with 3 planted faults (dry electrode, loose band, jaw clench on cue, active charger near the device). Order (BG/GB) × wearer pairing × fault set are counterbalanced with a Latin square over 16 operators.
- Study 2: mixed. Wording (F-P vs. F-A) between subjects. System output within subjects: each participant sees 24 vignettes, 12 stroke and 12 mimic, with outputs no-AI 6 (3 stroke / 3 mimic), alert 4 (3 correct / 1 wrong), reassure 4 (3 correct / 1 wrong) and No-Decision 10 (5 stroke / 5 mimic). Vignette-to-output mapping rotates over 4 lists.

**Randomisation.** Study 1: Latin-square assignment fixed before recruitment, operators take the next free slot. Study 2: platform randomises wording 1:1 (balanced by role if supported) and list 1:1:1:1; vignette order random per participant.

## 3. Sampling plan

**Existing data.** No data have been collected for these studies at the time of registration. [If pilots ran first: "Pilot data from N operators were used only to check procedures and the effect-size assumption; they are not included."]

**Data collection.**
- Study 1: in-person at [lab], adults ≥ 18 who have never placed EEG electrodes; preferably 2–6 paramedics or emergency nurses. 4 healthy wearers. Raw EEG and timestamped app events are logged per run (`data/study_logs/`, ISO 8601 timestamps from server-side chunk arrival).
- Study 2: online, emergency/neurology physicians, emergency nurses and final-year medical students, recruited through [clinical advisor's network].

**Sample size.**
- Study 1: 16 operators (32 runs).
- Study 2: minimum 40 (20 per wording), target 60; stop at 60 or at [date], whichever comes first.

**Rationale.**
- Study 1: paired test, d = 0.8, α = 0.05, power 0.80 needs about 15; 16 fills both orders. d = 0.8 is an assumption checked in the pilot.
- Study 2: 5 stroke-with-No-Decision vignettes per person gives about 200–300 decisions; N = 40 detects only large differences (about 20 pp). H5 is therefore reported with its effect size and CI, not only a p-value.

**Stopping rule.** Fixed N; no interim analysis of outcomes.

## 4. Variables

**Manipulated.** Study 1: interface condition (B, G). Study 2: wording (F-P, F-A); system output (no-AI, alert, reassure, No-Decision); vignette truth (stroke, mimic).

**Measured.**

| Variable | Definition |
|---|---|
| TTU (Study 1, primary) | Earliest time from run start at which 60 consecutive seconds are rated usable by the independent rater (10 s epochs, usable / not usable). Runs that never reach it are set to 8 min. |
| Success | TTU ≤ 8 min (yes/no) |
| Usable share | Share of usable epochs in the last 60 s of the run |
| Fault identification | Whether the operator verbally names the cause of each planted fault; coded from transcripts by two coders blind to condition where possible |
| Fix actions | Count of operator fix events from the app log |
| NASA-TLX, SUS, trust | Questionnaires after each run (trust: Jian et al. 2000) |
| TTU by SQI v1 / v2 | Secondary, reported as biased toward G |
| Activation (Study 2, primary) | Answer to "activate the stroke pathway and transfer to a stroke centre?" (yes/no) |
| Confidence, influence | 1–7 Likert per vignette |
| Meaning of No-Decision | Free text, coded qualitatively |

**Indices.** Rater agreement: Cohen's κ on 20% of runs rated by a second rater. NASA-TLX raw (unweighted) mean; SUS standard 0–100 score.

## 5. Analysis plan

**Statistical models.**
- H1: Wilcoxon signed-rank on paired TTU. Sensitivity: Cox model with operator frailty, runs reaching 8 min censored.
- H2: McNemar.
- H3: logistic GLMM, correct ~ condition + (1 | operator) + (1 | fault type).
- H4: Wilcoxon signed-rank for TLX and SUS.
- H5: logistic GLMM on stroke vignettes with No-Decision, activation ~ wording + (1 | participant) + (1 | vignette); report odds ratio with 95% CI.
- H6, H7: logistic GLMM on stroke vignettes with output ∈ {no-AI, No-Decision}, activation ~ output × wording + random intercepts; H7 compares the model-estimated difference in percentage points with the −10 pp margin (one-sided 95% CI).
- Effect sizes with 95% CIs (bootstrap over operators / participants). Order effect (B first vs. G first) checked for H1.

**Inference criteria.** Two-sided α = 0.05 for H1–H6 (one-sided for H7 non-inferiority). Primary hypotheses H1 and H5 are tested without correction; H2–H4 and H6–H7 are reported as secondary without multiplicity correction and interpreted with their CIs.

**Data exclusion.**
- Study 1: a run is repeated with the spare fault set if the device or recording fails technically (BLE disconnection longer than 30 s, or the app shows "NOT RECORDING"); the failed run is reported but not analysed. An operator who withdraws is replaced in the same Latin-square slot.
- Study 2: participants failing **both** attention checks are excluded; a sensitivity analysis also excludes those failing either. Participants who ask for deletion after the debrief are removed and counted. Completion time under [5] minutes is excluded.

**Missing data.** Study 1 questionnaires: item-level missing values handled by the instrument's scoring rule; otherwise complete-case. Study 2: partial responses [are / are not] used, as stated in the consent page.

**Exploratory analyses (labelled as such).** Results by role and experience (Study 2); TTU by SQI v1/v2 criteria; activation on mimic vignettes with No-Decision (cost of over-triage); qualitative themes from interviews and free text.

## 6. Other

Analysis code and the frozen SQI v2 configuration (drift ramp fitted on TUAR, commit [hash]) are in the project repository; the decision threshold of the guidance and the No-Decision rule do not change during the studies.
