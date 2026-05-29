# NeuraTriage EEG Frontend

The active frontend is a static React 18 + Babel app loaded directly in the
browser. There is no build step yet.

## Active Files

```text
frontend/
  index.html              redirect entrypoint to app.html
  app.html                active command-center UI
  landing.html            public landing page
  app/
    shell.jsx             sidebar, topbar, command palette
    screen-live.jsx       live monitoring screen
    screens-clinical.jsx  dashboard, patients, alerts, devices
    screens-tools.jsx     setup, insights, reports, settings
    visualizations.jsx    UI visualizations
    icons.jsx             icon set
  shared/
    api.js                REST helper
    live-data.js          polling/demo live-data adapter
    ws-stream.js          WebSocket stream/replay adapter
    i18n.js               VI/EN strings
```

Legacy folders are still present for reference and should not be treated as the
active app surface:

```text
frontend/components/
frontend/screens/
frontend/lib/
frontend/styles/
```

## Run With Backend

Use the FastAPI server from the repo root:

```bat
backend\run_app.bat
```

Open:

```text
http://127.0.0.1:8501/
```

FastAPI serves `frontend/` as static files, and `index.html` redirects to
`app.html`.

## Static Preview Only

For UI-only preview without the backend:

```bat
cd frontend
python -m http.server 8000
```

Open:

```text
http://127.0.0.1:8000/
```

Some screens require the FastAPI backend. Live data can fall back to browser
demo mode, but login, CRUD, upload, inference, and reports need the backend.

## Demo Wording Boundary

The active frontend should describe results as EEG risk-pattern triage support.
Do not present the app as a diagnosis system or CT/MRI replacement. Current
validated evidence is binary NS/IS. Four UCLH ICH patients are integrated as
exploratory HS evidence, but HS is not yet validated for the planned 5-fold
3-class CV.

## Known P1 Items

- `shared/api.js` requires an explicit login token; demo auto-login has been removed.
- Upload/inference is hardened to converted `.npz`/`.npy` inputs; raw EEG files
  need converter scripts before upload.
- Public claims should be checked against `docs/uist_evidence.md` and the
  `/api/research/metrics` endpoint before presentation.
