# Tiến trình nghiên cứu — NeuraTriage EEG Stroke

## Mục tiêu
**UIST 2026 Poster** — deadline 10/7/2026
**Kế hoạch:** Hoàn thành trong 1 tháng (bắt đầu 6/5/2026)

---

## Kế hoạch 1 tháng

### Tuần 1 — Data + Experiments (6–12/5)
- [x] Ngày 1 tối: Chạy feature table 50 bệnh nhân qua đêm → `build_feature_table.py`
- [ ] Ngày 2: Download PhysioNet healthy EEG (109 subjects) → `download_physionet_healthy.py`
- [ ] Ngày 2–3: Convert healthy EEG → npz + combine → `combine_manifests.py`
- [ ] Ngày 4–5: CV + ablation ApFu vs ApFu+MFDFA → `run_cv_ablation.py`
- [ ] Ngày 6–7: Kiểm tra kết quả → `results/cv_summary.txt`

### Tuần 2 — Interviews + Abstract Draft (13–19/5)
- [ ] Liên hệ 5 bác sĩ/y tá, đặt lịch phỏng vấn
- [ ] Conduct 3–5 expert interviews (20 phút/người, demo app)
- [ ] Viết draft 2-page abstract

### Tuần 3 — Polish Abstract + Poster (20–26/5)
- [ ] Revise abstract dựa trên feedback interviews
- [ ] Design poster A0
- [ ] Review toàn bộ, chỉnh số liệu

### Tuần 4 — Video + Submit (27/5–2/6)
- [ ] Quay + edit video demo 5 phút
- [ ] Final review abstract + poster
- [ ] Nộp trên PCS 2.0 (buffer 12 ngày trước deadline 10/7)

### Quy tắc
- Không thêm feature mới vào app
- Chạy experiments ban đêm, ban ngày viết và interview
- Abstract viết trước, poster làm sau

---

## Đã hoàn thành
- [x] Pipeline: ApEn + FuEn + MFDFA + LightGBM + Optuna/TPE
- [x] Frontend app: login, live monitor, alert system
- [x] Dataset Figshare 21679035 — 50 bệnh nhân ischemic stroke
- [x] Extract + convert 50 EDF → npz (18 channels, 256 Hz, 320s/patient)
  - Script: `convert_edf_to_npz.py`
  - Output: `dataset_real/sub-01.npz` ... `sub-50.npz`
  - Manifest: `dataset_real/manifest_ischemic.csv`

---

## Bước tiếp theo (bắt đầu ngày mai)

### Bước 1 — Build feature table (chạy qua đêm nếu được, ~20-40 phút)
```powershell
& "C:\Users\Admin\eeg-stroke-app\.venv\Scripts\python.exe" -c @"
import sys, warnings
warnings.filterwarnings('ignore')
sys.path.insert(0, r'C:\Users\Admin\eeg-stroke-app\backend')
from eeg_stroke_pipeline import load_records_from_manifest, build_feature_table, PipelineConfig

cfg = PipelineConfig()
records = load_records_from_manifest(r'C:\Users\Admin\eeg-stroke-app\dataset_real\manifest_ischemic.csv', cfg)
print(f'Loaded: {len(records)} records')
ft = build_feature_table(records, cfg)
ft.to_csv(r'C:\Users\Admin\eeg-stroke-app\dataset_real\feature_table.csv', index=False)
print(f'Done: {ft.shape[0]} windows saved.')
"@
```

### Bước 2 — Ablation experiment: ApFu-only vs ApFu+MFDFA
### Bước 3 — Cross-validation (macro F1, AUC, ECE)
### Bước 4 — Viết 2-page UIST abstract
### Bước 5 — Design poster A0
### Bước 6 — Quay video demo app (5 phút)

---

## Ghi chú kỹ thuật
- Feature table build chậm vì ApEn/FuEn O(n²) — nên để chạy background
- Sau khi có `feature_table.csv`, CV và ablation chạy nhanh (~5-10 phút)
- Dataset thực chỉ có ischemic — binary classification hoặc severity-based

## Cấu trúc dataset
- `dataset_real/` — 50 bệnh nhân ischemic thật (Figshare 21679035)
- `dataset_npz/` — 12 bệnh nhân synthetic (smoke test)
- `21679035/`    — raw dataset gốc (EDF + metadata)
- `dataset_healthy/` — 50 PhysioNet eegmmidb resting baseline (S001-S050, dot-strip bug đã fix 2026-05-07)

---

## Handoff cho session Claude tiếp theo (2026-05-07 cuối ngày)

### Backend FastAPI (`backend/app/`) — Phase 1+2+3 done
- 35 REST routes + 1 WebSocket. Auto-load model từ `models_store/`/`out/`/`dataset_npz/`.
- 5 SQLite tables: `patients`, `emergency_contacts`, `devices`, `eeg_sessions`, `alerts`.
- DB tại `data/neuratriage.db`. Init tự động trên lifespan.
- Auth: JWT HS256, 2 user demo: `admin@neuratriage.com` / `doctor@neuratriage.com` (Xuan Que, clinician), password `demo1234`.
- WS streaming có replay mode: init message thêm `replay_npz: "sub-01.npz"` → server tự đọc + pump từ `dataset_real/sub-XX.npz`.
- 26/26 pytest passing (`tests/test_channel_mapper.py`, `test_devices.py`, `test_envelope.py`, `test_ws_stream.py`, `test_phase3_crud.py`).

### Frontend (`frontend/app.html` + `frontend/app/*.jsx`) — wired ~70%
- `shared/api.js` auto-login + JWT + `useApi` hook.
- `shared/ws-stream.js` real-time WS với replay support.
- 4 clinical screens nối DB thật: Dashboard, Alerts (+ack/dismiss), Device (+pair/unpair), Patient (selector).
- Setup screen upload + infer thật. Modal tạo patient mới. Click bed → Patient navigation qua CustomEvent `nt:nav`.
- Tweaks panel có toggle Polling/WS + dropdown Replay từ dataset.

### Còn lại theo độ ưu tiên
1. **Research evidence (UIST)**: chuỗi `dataset_healthy/feature_table_healthy.csv` → `feature_table_combined.csv` → `results/cv_summary.txt` + ablation. Script đã có (`build_feature_table.py`, `combine_manifests.py`, `run_cv_ablation.py`). Lần chạy hôm 2026-05-07 bị kill 48/50 do taskkill nhầm. Re-run được trong ~30 phút build + 1-3h CV.
2. **Insights screen**: hiện hardcode `Acc=94.2% F1=0.917 κ=0.882` ở `frontend/app/screens-tools.jsx:104`. Sau khi có CV results, replace bằng read từ `results/cv_summary.txt` qua endpoint mới hoặc serve file static.
3. **Backend Phase 4**: PDF weekly reports (WeasyPrint hoặc HTML+browser print) + SendGrid + APScheduler weekly cron. Master Prompt §7.
4. **Backend Phase 5**: Dockerfile + docker-compose.
5. **Login UI** thay auto-login demo cho production.

### Demo URL (random Cloudflare quick tunnel — đổi mỗi lần restart)
Hôm 2026-05-07 cuối ngày: `https://fred-warrant-richards-immunology.trycloudflare.com/app.html`

Restart tunnel:
```powershell
C:\Users\Admin\eeg-stroke-app\tools\cloudflared.exe tunnel --url http://127.0.0.1:8501
```

Restart backend:
```powershell
cd C:\Users\Admin\eeg-stroke-app\backend
..\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8501
```

### Bug fix gần nhất
- `download_physionet_healthy.py:67-72` — strip dots khỏi PhysioNet channel names (`Fp1.`, `Cz..`) trước RENAME. Lần convert đầu tạo toàn NaN; đã re-convert thành công 50/50 healthy npz với std ~60µV.

---

## UIST demo implementation update (2026-05-10)

- Active claim boundary: research prototype for EEG triage support, not
  diagnosis and not CT/MRI replacement.
- Current evidence: binary ischemic-vs-non-stroke. HS UI states remain
  demo/simulation until a real hemorrhagic cohort is validated.
- Backend upload now accepts inference-ready `.npz`/`.npy` only. Raw
  `.edf`/`.bdf`/`.fif` receives a converter-script error.
- Live Monitor recommendation copy is demo-safe and includes a "Why this alert?"
  panel with risk pattern, confidence, SQI, state, and top signals.
- Report generation uses backend patient contacts with `notify_weekly_report`;
  browser-local recipients are labeled as alert-demo settings only.
- Evidence handoff: `docs/uist_evidence.md`.

## Hemorrhagic dataset update (2026-05-10)

- New local sources detected: `Patient_03`, `Patient_05`, `Patient_06a`,
  `Patient_11`. `Patient_06b` is labeled None in the UCLH table and was not
  added as HS.
- UCLH labels mapped to pipeline class `hemorrhagic` / `2`:
  `P3 = Big ICH`, `P5 = Small ICH`, `P6A = Big ICH`, `P11 = Big ICH`.
- Converted pre-injection TD segments:
  `p3_td1_preinject_10s.npz`, `p5_td1_preinject_20s.npz`,
  `p6a_td1_preinject_20s.npz`, `p11_td1_preinject_8s.npz`.
- Extracted feature table:
  `dataset_hemorrhagic/feature_table_hemorrhagic.csv` with 88 retained windows
  from 4 HS patients.
- Built exploratory 3-class combined table:
  `dataset_real/feature_table_combined_3class_exploratory.csv`.
- 4-fold exploratory ablation with 10 Optuna trials:
  ApFu Macro-F1 `0.6467`, ApFu+MFDFA Macro-F1 `0.7546`, delta `+0.107811`,
  p=`0.06354`. Best condition is ApFu+MFDFA+SQI Macro-F1 `0.8661`.
- Research status: missing HS class is now confirmed and integrated
  exploratorily, but planned 5-fold validated 3-class CV still requires at
  least one more HS patient.

## App replay update (2026-05-10)

- Setup screen `Replay session` is now wired to `/api/replay/cases`.
- Replay list includes NS, IS, and HS exploratory cases with class filters.
- HS replay cases from `dataset_hemorrhagic/` can run `/api/infer` directly by
  `case_id`.
- Smoke checked `p11_td1_preinject_8s.npz`: backend inference returned
  `pred_class=hemorrhagic`, 9 windows, SQI mean about `0.642`.

## Evidence QC update (2026-05-10)

- Added `build_hemorrhagic_qc.py`.
- Generated `dataset_hemorrhagic/qc_summary.csv` and `.json`.
- `/api/research/metrics` now exposes HS QC summary.
- Insights screen now shows evidence badges and a Hemorrhagic QC panel.

## App stability pass (2026-05-11)

- Fixed JS crash: `useRef` was used in `App()` component (`frontend/app.html:199`) but not
  destructured from React. Added `useRef` to the destructuring on line 46.
- Verified 44/44 tests pass (`pytest -q` from repo root: 41 backend + 3 top-level).
- Verified all key endpoints: health, login, dashboard, research/metrics, reports/generate,
  replay/cases, alerts, patients.
- PDF report generation confirmed working (reportlab 4.5.0, 2717+ bytes output).
- Insights screen reads real data from `results/mfdfa_ablation_results.json` (5 conditions,
  binary task, N=100 patients). No hardcoded metrics.
- No other functional changes — app is demo-ready at `http://127.0.0.1:8501/`.

## App polish + backend/algorithm review + production hardening (2026-05-29)

Three blocks of work; **45/45 tests pass** throughout.

### Track A — demo polish (frontend)
- Fixed 11 corrupted Vietnamese UI strings (mojibake `?` + stripped diacritics) in
  `app.html`, `screen-live.jsx`, `screens-clinical.jsx`, `screens-tools.jsx`.
- Added **Emergency Contacts UI** in the Patient screen (add/delete + `notify_weekly_report`/
  `notify_on_alert` toggles → `/api/patients/{id}/contacts`). The weekly-email pipeline is now
  reachable end-to-end (previously no UI to set recipients).
- "Page MD" relabelled as a simulated escalation (no real paging backend) + tooltip.
- Removed dead duplicate `_week_label`/`_build_pdf` in `report_service.py`.

### Backend + algorithm review (fixes)
- **Bug (demo-breaking):** datasets renamed `dataset_real` → `dataset_ischemic` but
  `replay_cases.py` / `inference.py` still pointed at the old name → ischemic replay & case
  inference silently empty. Fixed (verified: `sub-01.npz` resolves, 12 IS cases listed).
- **SQI train/inference skew:** realtime detector computed SQI on the band-passed+CAR signal
  while training uses notch-only. Added a parallel notch-only path (`OnlineEEGPreprocessor.sos_sqi`
  + `RealTimeStrokeDetector.sqi_buffer`) so online SQI matches training. Verified: mean|Δ|
  per window dropped 0.056 → 0.0037. No retraining needed (model/features unchanged).
- Hardening: `numpy>=2.0` pin (np.trapezoid), `/api/upload` 200 MB cap, lock-safe
  `ModelManager.reset()` for reload, `PipelineConfig` extra-key fallback in `/api/infer`.
- Verified clean (not bugs): ApEn/FuEn/MFDFA math, causal-filter train↔online parity,
  alert state machine, ECE binning, auth/JWT, path-traversal guards.

### Track C — production hardening + deploy
- Security-headers middleware in `main.py` (base headers always; **HSTS + CSP** when
  `APP_ENV=production`).
- Production guard: app refuses to boot in production with the default/weak `JWT_SECRET`
  (`config.DEV_JWT_SECRET`, `Settings.is_production` / `jwt_secret_is_insecure`).
- `Dockerfile`: HEALTHCHECK + pinned `--workers 1` (in-process singletons + in-RAM WS state).
- `docker-compose.yml`: volume mounts fixed to `dataset_ischemic`/hemorrhagic/npz.
- `.dockerignore`: keep `results/` (Insights needs it); exclude large datasets (mount instead).
- New `docs/deploy.md` (Render/Railway/Fly/VPS, secrets, volume, datasets, SendGrid).
- Smoke-tested in production mode (uvicorn, single worker): health+headers, login,
  replay/cases (12 IS), research/metrics (5 conditions), dashboard, static `app.html` — all OK.
  (Docker engine not installed on this machine, so the container layer itself is untested.)

### Repo state / next
- The entire FastAPI rewrite (`backend/app/`, `backend/frontend/`, tests, migrations) is still
  **uncommitted** — last commit is the old Flask + top-level-`frontend/` era.
- 96 stray `*.log` artifacts (gitignored tunnel/server logs) deleted.
- Repo reorganised: 9 loose research/convert scripts moved to `scripts/`; legacy
  `api/` (Flask) + `backend/app.py` + `backend/run_workbench.bat` moved to `legacy/`
  (with `legacy/README.md`). Doc command paths updated. Run scripts from repo root,
  e.g. `.venv\Scripts\python.exe scripts\run_mfdfa_ablation.py …`.
- All of the above committed on branch `feat/fastapi-rewrite` (first commit of the
  FastAPI rewrite — previous history was the Flask era).
