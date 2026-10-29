# Paper revision — pivot 3-class → binary (IS vs NS)

Status: 2026-06-22. Áp dụng cho `EEGStroke_newjournal.docx`.
Nguyên tắc: trung thực về dữ liệu, đóng khung theo UIST (đóng góp hệ thống/tương tác,
không chỉ accuracy). KHÔNG bịa số liệu user-study.

Số liệu thật dùng trong bài (từ `results/` + `docs/uist_evidence.md`):
- Cohort: 50 ischemic (sub-01..50, ~31.6k windows) + 50 non-stroke PhysioNet
  resting (ns-S001..050, ~11.8k windows). Patient-level 5-fold CV, 30 Optuna trials.
- Binary IS-vs-NS: ApEn/FuEn alone macro-F1 0.792; + SQI gating 0.991;
  MFDFA gain (no SQI) +0.030 macro-F1, p=0.021; với SQI +0.0002 (n.s.).
  AUC tiến tới 1.000 — XEM cảnh báo confound ở Limitations.
- HS exploratory: 4 UCLH-EIT patients, 88 windows, 3-class macro-F1 0.866 (p≈0.06–0.19,
  chưa significant) → chỉ trình bày như exploratory / future, KHÔNG phải validated claim.

---

## [REDLINE 1] Abstract — thay đoạn hiện tại

> Stroke is a leading cause of global disability and mortality, where the window
> for effective intervention depends on rapid, accurate triage. Existing EEG analysis
> often relies on linear features or single-metric non-linear approaches that fail to
> capture the multi-scale dynamics and local informational uncertainty of pathological
> brain signals. We present an end-to-end real-time EEG triage-support system whose
> primary contribution is the *interaction and sensing-layer design* for the
> pre-hospital setting, built on a hybrid feature space that fuses Approximate and
> Fuzzy Entropy with Multifractal Detrended Fluctuation Analysis (MFDFA). To avoid the
> identity leakage that inflates much of the prior literature, we evaluate under strict
> patient-level cross-validation on a cohort of **50 ischemic-stroke and 50 non-stroke
> subjects**, framed as a **binary ischemic-vs-non-stroke** detection task. Entropy
> features alone reach a macro-F1 of 0.79; adding continuous Signal-Quality-Index (SQI)
> gating — the core of our alarm-fatigue-aware interaction design — raises macro-F1 to
> 0.99, with MFDFA contributing a measurable gain (+0.03 macro-F1, p<.05) in the
> ungated setting. We further report an *exploratory* three-class extension on 4
> hemorrhagic patients, which we present as a direction rather than a validated result.
> These findings indicate that pairing multi-scale non-linear features with a
> quality-gated, human-centered alerting loop yields a portable, low-cost triage-support
> prototype — not a diagnostic device — for resource-limited pre-hospital settings.

Lý do: bỏ "3 participants" (sai), bỏ `[X]/[Y]` placeholder, đổi headline sang binary,
đóng khung đóng góp theo UIST (interaction/sensing layer), số liệu trung thực, có caveat.

---

## [REDLINE 2] Introduction — Barrier #1 (đoạn "Deploying EEG ... three actionable states")

Đổi câu khẳng định 3-state là yêu cầu cốt lõi thành:

> First, regarding clinical utility, robust pre-hospital triage must at minimum reliably
> separate stroke from non-stroke under realistic, artifact-heavy conditions; finer
> ischemic-vs-hemorrhagic separation is clinically desirable but remains data-limited,
> as public hemorrhagic-EEG cohorts are scarce (van Stigt et al., 2023).

## [REDLINE 3] Introduction — Contribution #1 "Patient-Level Optimization..."

Giữ contribution về subject-level splitting và SQI/interaction. SỬA contribution
"Actionable Clinical Scope" (nếu xuất hiện như đóng góp 3-class) thành:

> **Leakage-Resistant Binary Detection.** We validate ischemic-vs-non-stroke detection
> under strict patient-level cross-validation, explicitly guarding against the
> window-level identity leakage that inflates prior reports (Brookshire et al., 2024),
> and we openly characterize a residual cross-cohort acquisition confound as a limitation
> rather than masking it. A three-class (NS/IS/HS) extension is reported as exploratory.

## [REDLINE 4] Related Work 3.4 — bullet "Actionable Clinical Scope"

> **Honest Clinical Scope.** Rather than over-claiming three-class performance on a
> hemorrhagic sample too small for patient-level CV, we validate the binary task and
> treat NS/IS/HS as an explicitly exploratory extension — a contrast to reports that
> present small-cohort multi-class accuracy as deployment-ready.

Đồng thời dọn các placeholder: `???` (cuối 3.1), `[Willam et al.]`→`[William et al., 2019]`,
`[Poweres]`→`[Powers et al., 2019]`, `[Simmon Finnigan]`→`[Finnigan et al., 2016]`.

---

## [FILL] V. Preliminaries, Concepts and Methodology

### 5.1 Study design
Retrospective, between-subjects technical evaluation on de-identified EEG, plus a
*planned* prospective usability study (protocol below; data to be collected).

**Participants (data cohort).** 50 ischemic-stroke recordings (`dataset_ischemic/`)
and 50 non-stroke resting-baseline recordings from PhysioNet (`dataset_healthy/`),
split at the patient level (no subject appears in both train and test).

**Apparatus.** 18-channel EEG resampled to 256 Hz; causal 1–35 Hz filtering; dual-window
feature extraction (1 s entropy window, 4 s MFDFA buffer); 125-dim feature vector;
LightGBM classifier tuned with the Tree-structured Parzen Estimator; SQI gating for
window admission; the prototype UI (risk stream, SQI state, "why this alert" panel).

**Procedure (technical eval).** Patient-level 5-fold CV; 30 Optuna trials per
condition/fold; ablation across {ApFu, ApFu+MFDFA, ApFu+SQI, ApFu+MFDFA+SQI};
metrics: macro-F1, patient-level F1, AUC, ECE; paired per-fold tests for component gains.

### 5.2 Tasks (planned usability study — DATA TO BE COLLECTED)
Paramedics/clinicians (target N≈8–12) perform timed triage-routing decisions on replayed
EEG streams: (T1) accept/route under a clear alert, (T2) behavior during a low-SQI
No-Decision state, (T3) response under injected transit artifacts. **[Run before camera-ready.]**

### 5.3 Data collection
Quantitative: decision time, routing accuracy vs ground truth, false-alarm
acknowledgement rate, number of alerts dismissed (alarm-fatigue proxy). Qualitative:
post-task NASA-TLX, semi-structured interview on trust and the No-Decision state.
**[Instruments defined; responses not yet collected — placeholder, not fabricated.]**

### 5.4 Results
**Technical (real).**

| Condition | macro-F1 | patient-F1 | note |
| --- | ---: | ---: | --- |
| ApFu | 0.792 | — | entropy only |
| ApFu + MFDFA | 0.822 | — | MFDFA gain +0.030, p=0.021 |
| ApFu + SQI | 0.991 | 1.000 | quality gating dominates |
| ApFu + MFDFA + SQI | 0.991 | 1.000 | MFDFA gain n.s. once gated |

Exploratory NS/IS/HS (4 HS patients): macro-F1 0.866, gains not yet significant
(p≈0.06–0.19) — exploratory only.

**Usability (planned).** [To be reported after the study in 5.2–5.3 is run.]

---

## [FILL] VI. Discussion & Limitations

**Discussion.** The dominant driver of binary performance is SQI gating, not raw feature
power — which reframes the result as evidence for *interaction/sensing-layer design*
rather than a new classifier, aligning the contribution with UIST's emphasis on systems
and human-centered alerting. MFDFA adds genuine but modest signal where quality gating is
absent, suggesting value in lower-quality field conditions.

**Limitations.**
1. **Cross-cohort acquisition confound (primary).** IS and NS come from different sources
   (clinical vs PhysioNet), different devices/montages, and in our data the recording
   source is 100% correlated with the label. A diagnostic probe
   (`scripts/diagnose_source_confound.py`, report `results/source_confound_report.json`)
   shows that **5 signal-quality (SQI) features alone — which encode recording condition,
   not brain pathology — separate the classes at AUC 0.998 (macro-F1 0.976)**, versus
   AUC 0.906 for the 60 entropy (pathology) features. Patient-level splitting removes
   identity leakage *within* a cohort but cannot remove this *between*-cohort confound, so
   the near-perfect headline AUC is largely an acquisition-rig shortcut rather than pure
   pathology. Same-rig controls (a single-hospital corpus such as TUH, where stroke and
   neuro-normal recordings share one acquisition setup) are required to settle this; the
   diagnostic script doubles as the same-rig / leave-one-source-out evaluation harness for
   that cohort.
2. **No completed user study.** Section 5.2–5.3 is a protocol; UIST-grade usability
   evidence is not yet collected.
3. **Hemorrhagic class underpowered.** 4 patients / 88 windows, exploratory only.
4. **Healthy resting EEG is an imperfect non-stroke control** for true emergency cases.
5. Internal research metrics, not deployment-grade clinical validation.

---

## [FILL] VII. Conclusion & Future Work

We presented a quality-gated, alarm-fatigue-aware EEG triage-support prototype whose
validated contribution is binary ischemic-vs-non-stroke detection under leakage-resistant,
patient-level evaluation, coupled with an interaction design that suppresses spurious
alerts via SQI gating, EMA smoothing, and hysteresis.

**Generalizability (HCI).** The SQI-gated "No-Decision" pattern and hysteresis-based
alert suppression generalize to any high-stakes, low-SNR monitoring interface where false
alarms erode operator trust.

**Future directions.** (1) Resolve the acquisition confound with same-rig IS/NS controls
(e.g., TUH-style single-hospital corpus). (2) Acquire a larger human hemorrhagic cohort to
make NS/IS/HS a validated rather than exploratory claim. (3) Run the prospective usability
study in 5.2–5.3. (4) Move from retrospective replay toward continuous in-ambulance
monitoring with prospective, workflow-embedded evaluation.
