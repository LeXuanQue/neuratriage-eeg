# UIST Demo Handoff - 2026-05-09

## Current Goal

Prepare NeuraTriage EEG for UIST 2026 Demo submission by 2026-07-10 AoE.

Positioning:

- Research/demo system for uncertainty-aware EEG triage support.
- Do not claim clinical diagnosis or replacement for CT/MRI.
- Demo should use anonymized replay cases, not live patient data.

## Implemented Today

- Added research metrics endpoint:
  - `GET /api/research/metrics`
  - Reads `results/mfdfa_ablation_results.json`.
  - Returns ablation conditions, paired comparisons, dataset metadata, and limitations.
- Added replay case endpoint:
  - `GET /api/replay/cases`
  - Returns allow-listed `.npz` replay case IDs from dataset folders.
- Hardened inference:
  - `/api/infer` now accepts `upload_id` or `case_id`.
  - Raw `eeg_path` is only a development compatibility path and must stay inside allow-listed project data folders.
  - Upload endpoint now returns `upload_id`.
- Hardened WebSocket:
  - `/ws/stream/{session_id}` now requires JWT via query `?token=...` or `Authorization: Bearer ...`.
  - Replay resolution now uses the shared allow-listed case resolver.
- Frontend changes:
  - Removed demo auto-login from `frontend/shared/api.js`.
  - WebSocket client attaches JWT token.
  - Replay dropdown loads case list from `/api/replay/cases`.
  - Topbar shows `REPLAY`, `LIVE WS`, or `SIM`.
  - Setup/analyze sends `upload_id` to `/api/infer`.
  - Insights reads `/api/research/metrics`.
  - Dashboard no longer shows hardcoded `94.2% / F1=0.917 / kappa`.
- Tests:
  - Added `backend/tests/test_research_demo.py`.
  - Updated WebSocket tests for token auth.
  - Full test suite passed: `31 passed in 8.65s`.

## Server Status

Local server was started and verified:

```text
http://127.0.0.1:8501/
```

Health response was OK:

```json
{"success":true,"data":{"status":"ok","app":"NeuraTriage EEG","version":"0.2.0"}}
```

Demo login:

```text
doctor@neuratriage.com / demo1234
admin@neuratriage.com  / demo1234
```

## Next Priority

Do these in order:

1. Run demo flow end-to-end in browser:
   - login
   - Live Monitor
   - replay case from Tweaks
   - WebSocket shows `REPLAY`
   - risk/probability timeline updates
   - Insights shows real metrics
   - Upload and Analyze works with `upload_id`
2. Implement `Why this alert?` panel:
   - alert class
   - confidence
   - SQI
   - timestamp
   - top contributing features
   - affected channels
   - wording: "risk pattern detected", not "stroke detected"
3. Implement clearer alert timeline:
   - signal quality OK
   - risk rises
   - alert-enter
   - clinician ack/dismiss
   - report/review
4. Add expert walkthrough materials:
   - script
   - consent/no-PHI note
   - interview questions
   - feedback synthesis table
5. Draft UIST demo abstract:
   - problem
   - system
   - interaction workflow
   - implementation
   - evidence
   - limitations
   - demo setup

## Suggested Tomorrow Command

Start by running tests:

```powershell
cd C:\Users\Admin\eeg-stroke-app
.\.venv\Scripts\python.exe -m pytest -q
```

Then run the app:

```powershell
backend\run_app.bat
```

Open:

```text
http://127.0.0.1:8501/
```

