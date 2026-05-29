# Legacy (reference only — not the active runtime)

These are superseded implementations kept for historical reference. The active
app is the FastAPI backend at `backend/app/` + static frontend at
`backend/frontend/` (see the top-level `README.md`).

- `api/index.py` — old Flask JSON API. Replaced by `backend/app/` (FastAPI).
- `app.py` — old local research workbench (formerly `backend/app.py`).
- `run_workbench.bat` — launcher for `app.py`.

> The workbench imports `eeg_stroke_pipeline`, which lives in `backend/`. To run
> it from here you must put `backend/` on the path, e.g.:
> `set PYTHONPATH=%CD%\backend & .venv\Scripts\python.exe legacy\app.py`

Nothing in the active runtime imports this folder.
