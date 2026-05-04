# NeuraTriage EEG — Stroke Early Warning

Hệ thống cảnh báo sớm đột quỵ dựa trên tín hiệu EEG. Repo gồm hai phần độc lập:

- **`frontend/`** — Giao diện React (mockup + login screen, deploy lên Vercel).
- **`backend/`** — Pipeline Python (LightGBM + MFDFA + ApEn/FuEn) + Flask app.
- **`docs/`** — Research notes.

## Cấu trúc

```
eeg-stroke-app/
├── frontend/         ← React 18 + Babel standalone (xem frontend/README.md)
├── backend/          ← Python research pipeline + Flask app
├── docs/             ← research_guide.md
├── README.md
└── vercel.json       ← Vercel config (deploys frontend/ as static site)
```

---

## Frontend

Xem chi tiết ở [`frontend/README.md`](frontend/README.md).

Mở local:

```bash
cd frontend
python -m http.server 8000
# → http://localhost:8000/
```

Production: auto-deploy lên Vercel khi push vào `main`.

---

## Backend

Pipeline nghiên cứu Python (`backend/eeg_stroke_pipeline.py`) + Flask app
(`backend/app.py`).

### Pipeline

```text
raw EEG
→ channel ordering + preprocessing
→ 1-second ApEn/FuEn entropy features
→ 4-second MFDFA features
→ SQI quality features
→ LightGBM classifier
→ Optuna/TPE hyperparameter search
→ probability calibration
→ offline inference or realtime alert logic
```

### Data format

Manifest CSV:

```csv
patient_id,label,path,fs
sub-01,non-stroke,C:\path\to\sub-01.npz,256
sub-02,ischemic,C:\path\to\sub-02.npz,256
sub-03,hemorrhagic,C:\path\to\sub-03.npz,256
```

Labels: `non-stroke`, `ischemic`, `hemorrhagic` (or numeric `0`, `1`, `2`).

`.npz` file keys:

- `data` — float array `(n_channels, n_samples)`
- `channels` — channel names
- `fs` — sampling rate (optional if manifest có `fs`)

`.npy` file — float array `(n_channels, n_samples)` theo thứ tự kênh mặc định
trong pipeline.

### Chạy backend

Có sẵn `.venv` tươi; batch file dùng local `.venv` khi sẵn sàng, fallback
sang `C:\Users\Admin\EEG\.venv` nếu local chưa cài đủ deps.

```bat
cd backend
run_app.bat
```

Mở: <http://127.0.0.1:8501>

Trực tiếp:

```bat
C:\Users\Admin\EEG\.venv\Scripts\python.exe backend\app.py --host 127.0.0.1 --port 8501
```

Cài deps vào `.venv` riêng cho project:

```bat
.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
```

### Smoke-test defaults

- Model: `C:\Users\Admin\EEG\testdata\pipeline_smoke_npz\model_smoke.joblib`
- Manifest: `C:\Users\Admin\EEG\testdata\pipeline_smoke_npz\manifest.csv`
- EEG file: `C:\Users\Admin\EEG\testdata\pipeline_smoke_npz\sub-01.npz`

Thay bằng output thí nghiệm thực khi chạy nghiên cứu.

---

## Trạng thái

- Frontend là **mockup** với mock auth (lưu `localStorage`). Chưa nối API
  backend thật — login chỉ lưu role/layout, click "Sign in" cho qua.
- Backend chạy độc lập trên localhost, chưa expose lên internet.
- Tích hợp frontend ↔ backend là bước tiếp theo (thay `handleLogin` +
  fetch các endpoint từ Flask).
