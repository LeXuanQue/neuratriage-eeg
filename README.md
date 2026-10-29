# NeuraTriage EEG

A real-time EEG system for pre-hospital stroke triage that **withholds a decision when signal
quality is too low**, and that measures how much of its own accuracy comes from the recording
setup rather than from pathology.

> **Research prototype, not a medical device.** It reports internal metrics and has not been
> clinically validated.

The work targets the sensing and interaction layer rather than a new classifier: continuous
signal-quality gating, an explicit *No-Decision* state instead of a forced guess, hysteresis and
cooldown against alarm flicker, and a glass-box panel that shows why an alert fired.

## What the evidence supports

The task is binary ischemic stroke vs. non-stroke (50 + 50 records, patient-level cross-validation).

- **The headline score is confounded.** Entropy/MFDFA features reach macro-F1 0.79 / AUC 0.91
  across cohorts, and five signal-quality (SQI) features that carry no pathology information
  already reach AUC 0.998. The two classes come from different recording setups, so most of the
  cross-cohort accuracy reflects acquisition, not diagnosis.
- **On a single rig the shortcut weakens.** On the TUH Slowing Corpus (N=29, one clinical rig)
  entropy features reach AUC 0.823 against 0.771 for SQI-only. This is a slowing proxy, not
  ischemic stroke, and is directional evidence only.
- **Stricter controls lower the number further** (held-out source, age matching, eye-state
  matching; see `scripts/leave_source_out.py`), and fixed-threshold alerting still raises many
  false alerts on healthy controls (`scripts/clinical_utility.py`). The current model is not
  suitable for continuous monitoring.
- **The live headband (Brain-Life Focus+, 2 channels AF3/AF4) drives quality gating and
  No-Decision only.** Classification uses the 18-channel replay path.
- **Not done yet:** a stroke cohort recorded on the same device as its controls, and a user study
  of the No-Decision interaction.

Details, safe claim language and limitations: [`docs/uist_evidence.md`](docs/uist_evidence.md).
The generated `results/` folder is not versioned, so the scripts above need the local datasets.

## Quick start

```bat
.venv\Scripts\python.exe -m pip install -r requirements.txt
backend\run_app.bat
```

Open <http://127.0.0.1:8501/>. Direct command:

```bat
cd backend
..\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8501
```

Demo login (local demo only; replace before any public deployment):

```text
doctor@neuratriage.com / demo1234
admin@neuratriage.com  / demo1234
```

The demo needs no hardware: it replays de-identified recordings and can inject artifacts so you
can watch the SQI gate switch the interface into No-Decision.

### Docker

```bat
docker compose up --build
```

Replay datasets are mounted read-only from `./dataset_*` (see `docker-compose.yml`). Deployment,
secrets, the single-worker requirement and SendGrid are covered in
[`docs/deploy.md`](docs/deploy.md).

### Tests

```bat
.venv\Scripts\python.exe -m pytest -q
```

## How it works

```text
EEG (18 ch, 256 Hz)
  -> causal band-pass 1-35 Hz
  -> signal-quality index per window  --(low)--> No-Decision
  -> entropy + MFDFA features (1 s / 4 s dual window, 125-dim)
  -> calibrated LightGBM (or Riemann model)
  -> EMA smoothing, hysteresis 0.80 / 0.60, cooldown
  -> alert + glass-box explanation
```

A live headband or replay feeds the same pipeline over WebSocket. Alerts can be acknowledged or
dismissed, and weekly PDF reports can be generated.

## Repository layout

```text
backend/
  app/               FastAPI app: routers/, services/, ws/, models/
  frontend/          static React/Babel UI served by FastAPI (app.html is the entrypoint)
  models/            demo model artifacts (model.joblib)
  tests/             backend tests
  eeg_stroke_pipeline.py   feature extraction, inference, training, realtime detector
scripts/             research and data-conversion scripts (see below)
tests/               API contract and source-confound tests
docs/                evidence, plans, literature reviews, deploy and device guides
figures/             figures used in the paper and poster
legacy/              old Flask API and research workbench, kept for reference only
```

Local datasets, SQLite databases, uploads, reports, logs and `results/` are ignored by Git and
Docker. Uploads accept inference-ready `.npz` or `.npy`; convert raw `.edf`, `.bdf` and `.fif`
first with the converter scripts.

## Research scripts

| Script | Purpose |
|---|---|
| `diagnose_source_confound.py` | probe whether source or SQI separates the classes |
| `leave_source_out.py` | held-out-source evaluation with age and eye-state matching |
| `run_mfdfa_ablation.py` | feature-family ablation (entropy, MFDFA, SQI) |
| `clinical_utility.py`, `device_recalibration.py` | false alerts per hour and per-device thresholds |
| `tusl_to_npz.py`, `tuab_to_npz.py` | build same-rig datasets from the TUH corpora |
| `nedc_report_query.py` | keyword filter for TUH reports, run by NEDC on their side (stdlib only) |
| `convert_*.py`, `build_feature_table.py` | dataset conversion and feature tables |

TUH data is distributed under the corpus data-use agreement and is not redistributed here.

## Live headband

Streaming from the Brain-Life Focus+ needs Bluetooth LE (`bleak`, imported lazily; the app and
tests run without it). See [`docs/device_bring_up.md`](docs/device_bring_up.md).

## Documentation

| Topic | File |
|---|---|
| Claims, metrics, limitations | [`docs/uist_evidence.md`](docs/uist_evidence.md) |
| Technical report | [`docs/technical_report.md`](docs/technical_report.md) |
| Same-rig (TUH) runbook | [`docs/tuh_samerig.md`](docs/tuh_samerig.md) |
| Plan toward the full paper | [`docs/full_paper_plan.md`](docs/full_paper_plan.md) |
| Literature reviews | [`docs/lit_review.md`](docs/lit_review.md), [`docs/lit_review_eeg_fm.md`](docs/lit_review_eeg_fm.md) |
| Deployment | [`docs/deploy.md`](docs/deploy.md) |
