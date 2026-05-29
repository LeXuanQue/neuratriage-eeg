# NeuraTriage EEG

Research prototype for EEG-based stroke triage. The active app is a FastAPI
backend that serves the static React/Babel frontend and exposes REST/WebSocket
APIs for login, live stream/replay, upload, inference, patients, devices,
alerts, dashboard, and PDF reports.

This is a research prototype, not a medical device.

## Current Evidence Boundary

The UIST demo target is triage-support interaction, not diagnosis. Current
validated evidence is binary ischemic-vs-non-stroke using 50 ischemic EEG records
and 50 healthy resting-baseline records. Four UCLH hemorrhagic patients
(`P3`, `P5`, `P6A`, `P11`) have been converted as exploratory evidence, but
validated 3-class performance still needs at least one more HS patient for the
planned 5-fold patient-level CV protocol.

See `docs/uist_evidence.md` for the safe claim language, metrics, and
limitations.

## Active Runtime

- `backend/app/` - active FastAPI backend (serves everything on port 8501).
- `backend/frontend/app.html` - active command-center UI.
- `backend/frontend/index.html` - redirect entrypoint to `app.html`.
- `backend/frontend/app/` and `backend/frontend/shared/` - active screens/helpers.
- `backend/eeg_stroke_pipeline.py` - EEG feature extraction, inference,
  training, and realtime detector logic.
- `backend/models/model.joblib` - small demo model expected by the prototype.

Legacy files are still kept for reference:

- `legacy/api/index.py` - old Flask API, no longer the default runtime.
- `legacy/app.py` - old local research workbench.
- `backend/frontend/components/`, `backend/frontend/screens/`, `backend/frontend/lib/` - old UI slices.

## Project Layout

```text
eeg-stroke-app/
  backend/
    app/                  FastAPI app, routers, services, SQLAlchemy models
    frontend/             static UI (served by FastAPI on the same port)
      app.html            active command-center entrypoint
      app/                React screens, shell, visualizations
      shared/             API client, WebSocket, live-data helpers
      landing.html        public landing page
    models/               demo model artifacts
    tests/                FastAPI backend tests
    eeg_stroke_pipeline.py
    run_app.bat           local FastAPI launcher
  tests/                  top-level API contract tests
  Dockerfile
  docker-compose.yml
  requirements.txt
```

Local datasets, SQLite databases, uploads, reports, logs, and generated result
folders are ignored by Git and Docker.

## Run Locally

From the repo root:

```bat
.venv\Scripts\python.exe -m pip install -r requirements.txt
backend\run_app.bat
```

Open:

```text
http://127.0.0.1:8501/
```

Direct backend command:

```bat
cd backend
..\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8501
```

Demo login:

```text
doctor@neuratriage.com / demo1234
admin@neuratriage.com  / demo1234
```

## Test

```bat
.venv\Scripts\python.exe -m pytest -q
```

## Docker

```bat
docker compose up --build
```

Then open:

```text
http://127.0.0.1:8501/
```

## Deploy Direction

The full prototype should be deployed as a Docker/FastAPI app on Render,
Railway, Fly.io, a VPS, or similar. `vercel.json` is kept only for a static
frontend preview and does not deploy the FastAPI/ML backend.

See [`docs/deploy.md`](docs/deploy.md) for the step-by-step deploy guide
(secrets, single-worker requirement, persistent volume, datasets, SendGrid).

## Core Flow

```text
Login
  -> Dashboard
  -> Live EEG WebSocket or replay NPZ
  -> Alert creation / ack / dismiss
  -> Upload NPZ
  -> Offline inference
  -> Patient and device records
  -> Weekly PDF report generation
```

Uploads accept inference-ready `.npz` or `.npy` files. Raw `.edf`, `.bdf`, and
`.fif` files must be converted first with the converter scripts before demo
inference.
