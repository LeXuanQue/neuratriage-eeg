# NeuraTriage EEG — Master Backend Prompt

> **Mục đích:** Prompt này dùng để hướng dẫn AI (hoặc developer) xây dựng toàn bộ backend cho hệ thống NeuraTriage EEG Stroke Early Warning, tích hợp với frontend đã có tại https://neuratriage-eeg.vercel.app/ và pipeline EEG đã có trong file `eeg_stroke_pipeline.py`.

---

## 0. Ngữ cảnh tổng quan

Bạn đang build backend cho ứng dụng y tế **NeuraTriage EEG** — hệ thống phát hiện sớm đột quỵ bằng EEG thời gian thực. Backend phải:

1. Wrap toàn bộ logic từ `eeg_stroke_pipeline.py` thành REST API
2. Hỗ trợ thiết bị EEG thực (Brain-Life Focus+ và các thiết bị khác) với số kênh linh hoạt
3. Quản lý hồ sơ bệnh nhân, bác sĩ, người thân
4. Gửi báo cáo tuần tự động qua email (SendGrid)
5. Phục vụ frontend React đã có

**Stack khuyến nghị:** Python + FastAPI (phù hợp nhất vì pipeline là Python, async tốt cho WebSocket streaming)

---

## 1. Cấu trúc thư mục project

```
neuratriage-backend/
├── app/
│   ├── main.py                    # FastAPI app entry point
│   ├── config.py                  # Settings (env vars, constants)
│   ├── database.py                # DB connection (SQLite dev / PostgreSQL prod)
│   ├── models/                    # SQLAlchemy ORM models
│   │   ├── patient.py
│   │   ├── doctor.py
│   │   ├── device.py
│   │   ├── session.py
│   │   └── alert.py
│   ├── schemas/                   # Pydantic schemas (request/response)
│   │   ├── patient.py
│   │   ├── device.py
│   │   ├── inference.py
│   │   └── report.py
│   ├── routers/
│   │   ├── patients.py
│   │   ├── devices.py
│   │   ├── inference.py
│   │   ├── sessions.py
│   │   └── reports.py
│   ├── services/
│   │   ├── eeg_service.py         # Wrapper quanh eeg_stroke_pipeline.py
│   │   ├── device_service.py      # BLE/Bluetooth device management
│   │   ├── report_service.py      # Tạo báo cáo PDF + gửi SendGrid
│   │   └── scheduler.py           # APScheduler: job gửi báo cáo tuần
│   ├── ws/
│   │   └── stream_handler.py      # WebSocket handler cho streaming EEG
│   └── utils/
│       ├── npz_loader.py
│       └── channel_mapper.py
├── eeg_stroke_pipeline.py         # File pipeline gốc — KHÔNG SỬA
├── models_store/                  # Thư mục chứa file .joblib đã train
├── data/uploads/                  # Upload .npz dataset tạm thời
├── tests/
├── requirements.txt
├── .env.example
└── Dockerfile
```

**QUAN TRỌNG:** Không được sửa file `eeg_stroke_pipeline.py`. Chỉ import và wrap nó.

---

## 2. Dependencies (requirements.txt)

```
fastapi>=0.111.0
uvicorn[standard]>=0.29.0
websockets>=12.0
sqlalchemy>=2.0.0
alembic>=1.13.0
pydantic>=2.0.0
pydantic-settings>=2.0.0
python-multipart>=0.0.9
aiofiles>=23.0.0
apscheduler>=3.10.0
sendgrid>=6.11.0
jinja2>=3.1.0
weasyprint>=61.0          # Tạo PDF báo cáo
numpy>=1.24.0
scipy>=1.11.0
pandas>=2.0.0
scikit-learn>=1.3.0
lightgbm>=4.0.0
joblib>=1.3.0
optuna>=3.0.0
PyEMD>=1.4.0
python-dotenv>=1.0.0
pytest>=8.0.0
httpx>=0.27.0             # Test async
```

---

## 3. Core EEG Service — `app/services/eeg_service.py`

Đây là file quan trọng nhất. Wrap toàn bộ pipeline.

```python
"""
eeg_service.py
Wrapper quanh eeg_stroke_pipeline.py để dùng trong FastAPI.
KHÔNG import trực tiếp pipeline vào router — luôn đi qua service này.
"""
import numpy as np
from pathlib import Path
from typing import List, Optional, Dict, Any
import threading

# Import từ pipeline gốc
from eeg_stroke_pipeline import (
    TrainedStrokeModel,
    RealTimeStrokeDetector,
    PipelineConfig,
    EEGRecord,
    run_offline_inference,
    load_array_file,
    reorder_to_target_channels,
    canonicalize_channel_name,
    DEFAULT_CHANNELS,
    CHANNEL_ALIASES,
    CLASS_NAMES,
)
```

### 3.1 Model Manager (singleton, thread-safe)

```python
class ModelManager:
    """
    Singleton quản lý TrainedStrokeModel đã load.
    Thread-safe với lock vì FastAPI có thể có nhiều request đồng thời.
    """
    _instance = None
    _lock = threading.Lock()

    def __init__(self):
        self._model: Optional[TrainedStrokeModel] = None
        self._model_path: Optional[str] = None

    @classmethod
    def get(cls) -> "ModelManager":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def load_model(self, path: str) -> None:
        """Load model từ .joblib file. Gọi lúc startup hoặc qua API."""
        with self._lock:
            self._model = TrainedStrokeModel.load(path)
            self._model_path = path

    def get_model(self) -> TrainedStrokeModel:
        if self._model is None:
            raise RuntimeError("Model chưa được load. Gọi POST /inference/load-model trước.")
        return self._model

    @property
    def is_loaded(self) -> bool:
        return self._model is not None
```

### 3.2 Channel Mapping — linh hoạt theo thiết bị

```python
class ChannelMapper:
    """
    Map các kênh từ thiết bị thực (có thể thiếu kênh) sang 18 kênh chuẩn
    của pipeline. Kênh thiếu sẽ được fill bằng NaN → pipeline dùng
    fill_nan_channels() xử lý tự động.

    Ví dụ Brain-Life Focus+:
        Device channels: ["AF3", "AF4", "T7", "T8"]
        → Map: AF3→FP1 region, AF4→FP2 region, T7→T3 (alias), T8→T4 (alias)
        → 14 kênh còn lại: NaN → imputed bởi pipeline
    """

    DEVICE_PRESETS = {
        "brain_life_focus_plus": {
            "channels": ["AF3", "AF4", "T7", "T8"],
            "fs": 256,
            "description": "Brain-Life Focus+ (4 kênh EEG, PPG, fNIRS)"
        },
        "full_18ch": {
            "channels": DEFAULT_CHANNELS,
            "fs": 256,
            "description": "Full 18-channel EEG cap"
        },
        "custom": {
            "channels": [],  # Được set lúc runtime
            "fs": 256,
            "description": "Thiết bị tùy chỉnh"
        }
    }

    @staticmethod
    def map_to_pipeline(
        data: np.ndarray,              # shape: (n_device_channels, n_samples)
        device_channels: List[str],    # tên kênh thực của thiết bị
        fs: float,
        target_channels: List[str] = DEFAULT_CHANNELS,
    ) -> tuple[np.ndarray, List[str]]:
        """
        Trả về (data_18ch, target_channels).
        Kênh thiếu → NaN row.
        Alias được chuẩn hóa (T7→T3, T8→T4, P7→T5, P8→T6).
        """
        # Normalize alias
        normalized_input = [canonicalize_channel_name(ch) for ch in device_channels]
        target_normalized = [canonicalize_channel_name(ch) for ch in target_channels]

        idx_map = {name: i for i, name in enumerate(normalized_input)}
        output_rows = []
        for tch in target_normalized:
            if tch in idx_map:
                output_rows.append(data[idx_map[tch]])
            else:
                output_rows.append(np.full(data.shape[1], np.nan))

        return np.vstack(output_rows), target_channels
```

### 3.3 Session Manager (real-time streaming)

```python
class SessionManager:
    """
    Mỗi patient session có 1 RealTimeStrokeDetector riêng.
    Key: session_id (UUID string)
    """
    def __init__(self):
        self._sessions: Dict[str, RealTimeStrokeDetector] = {}
        self._lock = threading.Lock()

    def create_session(
        self,
        session_id: str,
        device_channels: List[str],
        fs: float = 256.0,
        config_overrides: Optional[Dict] = None,
    ) -> RealTimeStrokeDetector:
        """
        Tạo detector mới cho session.
        device_channels: kênh thực của thiết bị (có thể ít hơn 18)
        Pipeline sẽ impute kênh thiếu tự động.
        """
        model = ModelManager.get().get_model()
        cfg_dict = model.config.copy()

        # Override channels theo thiết bị
        cfg_dict["channels"] = DEFAULT_CHANNELS  # Pipeline luôn dùng 18 kênh chuẩn
        cfg_dict["fs"] = fs
        cfg_dict["impute_missing_channels"] = True  # BẮT BUỘC bật khi thiết bị ít kênh

        if config_overrides:
            cfg_dict.update(config_overrides)

        config = PipelineConfig(**cfg_dict)
        detector = RealTimeStrokeDetector(model, config=config, preprocess_online=True)

        with self._lock:
            self._sessions[session_id] = detector
        return detector

    def get_session(self, session_id: str) -> Optional[RealTimeStrokeDetector]:
        return self._sessions.get(session_id)

    def close_session(self, session_id: str) -> None:
        with self._lock:
            self._sessions.pop(session_id, None)

    def list_active_sessions(self) -> List[str]:
        return list(self._sessions.keys())
```

---

## 4. WebSocket Streaming — `app/ws/stream_handler.py`

```python
"""
WebSocket endpoint cho real-time EEG streaming.

Protocol (JSON):
  Client → Server:
    { "type": "init", "session_id": "...", "device_type": "brain_life_focus_plus",
      "device_channels": ["AF3","AF4","T7","T8"], "fs": 256 }
    { "type": "data", "chunk": [[...], [...], [...], [...]] }  # (n_channels, n_samples)
    { "type": "close" }

  Server → Client:
    { "type": "ready", "session_id": "...", "mapped_channels": [...] }
    { "type": "event", "timestamp_sec": 1.5, "status": "monitor"|"alert-enter"|"alert-hold"|"alert-exit"|"no-decision",
      "predicted_class": "non-stroke"|"ischemic"|"hemorrhagic"|null,
      "probabilities_smooth": [0.9, 0.05, 0.05],
      "sqi_total": 0.82,
      "alert_class": null }
    { "type": "error", "message": "..." }
"""

IMPORTANT — Lưu ý implementation:

1. Chunk data từ client phải là numpy array shape (n_device_channels, n_samples)
   → Dùng ChannelMapper.map_to_pipeline() trước khi đưa vào detector.update()

2. detector.update(chunk) trả về List[Dict] — mỗi dict là 1 event.
   Gửi từng event về client ngay lập tức (không batch).

3. Khi status == "alert-enter" hoặc "alert-switch":
   → Ghi alert vào DB
   → Trigger notification (có thể dùng background task)

4. Mỗi WebSocket connection = 1 session. Khi disconnect → close_session()

5. Xử lý lỗi: nếu model chưa load → gửi { "type": "error", "message": "Model not loaded" }
   trước khi accept connection để client không bị treo.
```

---

## 5. Database Models — SQLAlchemy

### 5.1 Patient Profile

```python
# models/patient.py
"""
Bảng patients:
  - id (UUID)
  - full_name, date_of_birth, gender
  - medical_record_number (MRN)
  - diagnosis_history (JSON)
  - doctor_id (FK → doctors)
  - emergency_contacts: List[EmergencyContact] (JSON hoặc bảng riêng)
  - created_at, updated_at

Bảng emergency_contacts:
  - id, patient_id (FK)
  - name, relationship, phone, email
  - notify_on_alert (bool) — có nhận email khi có alert không
  - notify_weekly_report (bool) — có nhận báo cáo tuần không
"""
```

### 5.2 Device Registry

```python
# models/device.py
"""
Bảng devices:
  - id (UUID)
  - device_type: str  # "brain_life_focus_plus" | "custom" | etc.
  - device_name: str
  - mac_address: str (nullable — cho BLE)
  - channels: JSON List[str]  # Kênh thực của thiết bị này
  - fs: float
  - is_active: bool
  - patient_id (FK, nullable) — thiết bị đang gắn với bệnh nhân nào
  - last_connected_at

QUAN TRỌNG: channels field quyết định ChannelMapper sẽ map như thế nào.
Khi tạo device mới với device_type="custom", frontend cho phép
người dùng tick chọn kênh nào có trong thiết bị.
"""
```

### 5.3 Session & Alerts

```python
# models/session.py
"""
Bảng eeg_sessions:
  - id (UUID) = session_id dùng cho WebSocket
  - patient_id (FK)
  - device_id (FK)
  - started_at, ended_at
  - duration_sec
  - total_windows, valid_windows, sqi_mean
  - alert_count
  - raw_data_path (nullable — đường dẫn file .npz nếu có lưu)

Bảng alerts:
  - id, session_id (FK), patient_id (FK)
  - timestamp_sec (từ detector)
  - alert_class: "ischemic" | "hemorrhagic"
  - status: "alert-enter" | "alert-switch" | "alert-exit"
  - probabilities_smooth: JSON [p0, p1, p2]
  - sqi_total: float
  - acknowledged: bool
  - acknowledged_by (doctor_id FK, nullable)
  - acknowledged_at
"""
```

---

## 6. API Endpoints

### 6.1 Model Management
```
POST /inference/load-model
  Body: { "model_path": "models_store/model.joblib" }
  Response: { "status": "loaded", "feature_count": 101, "channels": [...] }

GET /inference/status
  Response: { "loaded": true, "model_path": "...", "active_sessions": 3 }

POST /inference/upload-dataset
  Body: multipart/form-data — file .npz + manifest CSV
  Action: Lưu vào data/uploads/, không train ngay

POST /inference/offline
  Body: { "patient_id": "...", "npz_path": "..." }
  Response: DataFrame as JSON (t_end_sec, sqi_total, pred_class, probabilities)
```

### 6.2 Device Management
```
GET  /devices
POST /devices           — Đăng ký thiết bị mới (bao gồm channels list)
GET  /devices/{id}
PUT  /devices/{id}      — Cập nhật channels nếu firmware update
DELETE /devices/{id}

GET  /devices/presets   — Trả về DEVICE_PRESETS từ ChannelMapper
  Response: {
    "brain_life_focus_plus": { "channels": ["AF3","AF4","T7","T8"], "fs": 256, ... },
    ...
  }
```

### 6.3 Patient & Profile
```
GET  /patients
POST /patients
GET  /patients/{id}
PUT  /patients/{id}
DELETE /patients/{id}

GET  /patients/{id}/contacts
POST /patients/{id}/contacts
DELETE /patients/{id}/contacts/{contact_id}

GET  /patients/{id}/sessions     — Lịch sử session
GET  /patients/{id}/alerts       — Tất cả alerts
GET  /patients/{id}/weekly-report?week=2025-W20  — Xem report tuần cụ thể
```

### 6.4 Sessions
```
POST /sessions/start
  Body: { "patient_id": "...", "device_id": "..." }
  Response: { "session_id": "uuid", "ws_url": "ws://host/ws/stream/uuid" }

POST /sessions/{id}/end
GET  /sessions/{id}
GET  /sessions/{id}/alerts
```

### 6.5 WebSocket
```
WS /ws/stream/{session_id}
  Protocol mô tả ở mục 4 trên.
```

### 6.6 Reports
```
POST /reports/generate
  Body: { "patient_id": "...", "week_start": "2025-05-05" }
  Action: Generate PDF + gửi email ngay (on-demand)

GET  /reports/{patient_id}        — Danh sách báo cáo đã gửi
GET  /reports/{report_id}/pdf     — Download file PDF
```

---

## 7. Report Service — `app/services/report_service.py`

### 7.1 Nội dung báo cáo tuần (Weekly Report)

```python
"""
Báo cáo tuần bao gồm:

1. TỔNG QUAN TUẦN
   - Số session, tổng thời gian monitoring
   - Số alerts (phân loại: ischemic / hemorrhagic)
   - SQI trung bình (chất lượng tín hiệu)

2. BIỂU ĐỒ XU HƯỚNG
   - p_ischemic_smooth và p_hemorrhagic_smooth theo ngày
   - SQI theo ngày
   (Dùng matplotlib để render chart → embed vào PDF)

3. CHI TIẾT ALERTS
   - Danh sách từng alert: thời gian, loại, xác suất, độ dài episode
   - Bác sĩ đã acknowledge chưa

4. THÔNG TIN THIẾT BỊ
   - Thiết bị đã dùng, kênh nào active

5. KHUYẾN NGHỊ
   - Template cố định; nếu alert_count > 0 → thêm cảnh báo cần khám

Format output:
   - HTML template (Jinja2) → WeasyPrint → PDF
   - Gửi qua SendGrid: đính kèm PDF + body HTML tóm tắt
"""
```

### 7.2 SendGrid Integration

```python
"""
Sử dụng sendgrid-python SDK.
Config cần trong .env:
  SENDGRID_API_KEY=...
  SENDGRID_FROM_EMAIL=noreply@neuratriage.ai
  SENDGRID_FROM_NAME=NeuraTriage EEG System

Recipients:
  1. Doctor email (từ doctors table)
  2. Emergency contacts có notify_weekly_report=True

Email subject: f"[NeuraTriage] Báo cáo EEG tuần {week_label} — {patient_name}"

Lưu ý: Gửi bất đồng bộ (background task hoặc APScheduler job).
Nếu gửi thất bại → log lỗi, retry 1 lần sau 1 giờ.
"""
```

### 7.3 Scheduler

```python
"""
Dùng APScheduler (AsyncIOScheduler) khởi động cùng FastAPI.

Job: send_weekly_reports
  - Cron: Mỗi Thứ Hai lúc 07:00 (múi giờ Asia/Ho_Chi_Minh)
  - Logic:
      1. Lấy danh sách tất cả patients active
      2. Với mỗi patient: tổng hợp dữ liệu 7 ngày qua
      3. Generate PDF
      4. Gửi email đến doctor + emergency contacts

Khởi động scheduler trong FastAPI lifespan event:
  @asynccontextmanager
  async def lifespan(app: FastAPI):
      scheduler.start()
      yield
      scheduler.shutdown()
"""
```

---

## 8. Environment Variables (.env.example)

```env
# App
APP_ENV=development
SECRET_KEY=change_me_in_production
ALLOWED_ORIGINS=http://localhost:3000,https://neuratriage-eeg.vercel.app

# Database
DATABASE_URL=sqlite+aiosqlite:///./neuratriage.db
# Production: postgresql+asyncpg://user:password@host/dbname

# Model
DEFAULT_MODEL_PATH=models_store/model.joblib
AUTO_LOAD_MODEL_ON_STARTUP=true

# SendGrid
SENDGRID_API_KEY=
SENDGRID_FROM_EMAIL=noreply@neuratriage.ai
SENDGRID_FROM_NAME=NeuraTriage EEG

# Report Scheduler
WEEKLY_REPORT_CRON=mon
WEEKLY_REPORT_HOUR=7
WEEKLY_REPORT_TIMEZONE=Asia/Ho_Chi_Minh
```

---

## 9. Xử lý thiết bị không đủ kênh — Luồng dữ liệu đầy đủ

```
Thiết bị thực (Brain-Life Focus+: 4 kênh)
    AF3, AF4, T7, T8
        │
        ▼
ChannelMapper.map_to_pipeline()
    Alias: T7→T3, T8→T4
    Output: 18-channel array, 14 kênh = NaN
        │
        ▼
RealTimeStrokeDetector.update(chunk)
    → OnlineEEGPreprocessor.transform()
        → fill_nan_channels()     ← impute NaN bằng median/interpolation
        → clip_channel_outliers()
        → bandpass + notch filter
        → Common Average Reference
    → build_feature_row_from_windows()
        → ApEn + FuEn trên 18 kênh (NaN đã được impute)
        → MFDFA trên regions
        → SQI gate
    → predict_proba_from_features()
    → EMA + hysteresis + cooldown
        │
        ▼
Event { status, predicted_class, probabilities_smooth, sqi_total }
        │
        ▼
WebSocket → Frontend
```

**QUAN TRỌNG:** `impute_missing_channels=True` phải luôn bật khi dùng thiết bị ít kênh. `PipelineConfig` đã có flag này ở default=True — đừng override thành False.

---

## 10. Error Handling quan trọng

```python
"""
Các lỗi thường gặp và cách xử lý:

1. Model chưa load khi gọi WebSocket:
   → Kiểm tra ModelManager.is_loaded TRƯỚC khi accept WS connection
   → Trả về HTTP 503 (không phải WS error) nếu model chưa ready

2. Chunk có shape sai (n_device_channels != len(device_channels)):
   → Bắt ValueError trong ChannelMapper
   → Gửi WS event { "type": "error", "message": "Channel count mismatch" }
   → KHÔNG close session — chờ client gửi chunk hợp lệ

3. SQI quá thấp liên tục (> 30 giây):
   → Vẫn là behavior bình thường (điện cực tiếp xúc kém)
   → Gửi event status="no-decision", KHÔNG raise exception
   → Frontend hiển thị cảnh báo "Tín hiệu kém — kiểm tra điện cực"

4. TrainedStrokeModel.load() thất bại (file corrupt):
   → Log rõ ràng, raise HTTP 500 với message cụ thể
   → Không để app crash

5. SendGrid rate limit / network error:
   → Bắt exception, log, retry sau 1 giờ
   → Ghi trạng thái gửi (pending/sent/failed) vào DB
"""
```

---

## 11. Testing checklist

```python
"""
tests/test_eeg_service.py:
  ✓ ChannelMapper với 4 kênh Brain-Life Focus+ → output shape (18, N)
  ✓ ChannelMapper với T7/T8 alias → map đúng sang T3/T4
  ✓ SessionManager tạo/lấy/đóng session
  ✓ ModelManager singleton thread-safe

tests/test_inference.py:
  ✓ Upload .npz → offline inference → response có đủ columns
  ✓ WebSocket stream → nhận ít nhất 1 event sau khi push đủ samples

tests/test_reports.py:
  ✓ generate_weekly_report() với mock data → PDF không rỗng
  ✓ SendGrid mock → email được gọi với đúng recipients

tests/test_api.py:
  ✓ CRUD patients, devices, contacts
  ✓ /devices/presets trả về brain_life_focus_plus
"""
```

---

## 12. Lưu ý tích hợp với Frontend hiện có

```
Frontend tại: https://neuratriage-eeg.vercel.app/

Các màn hình cần API:

1. Dashboard / Real-time Monitor
   → WebSocket: WS /ws/stream/{session_id}
   → Lấy: predicted_class, probabilities_smooth, sqi_total, status

2. Patient Profile
   → GET/POST/PUT /patients/{id}
   → GET /patients/{id}/contacts
   → Hiển thị: thông tin bác sĩ cá nhân, danh sách người thân,
               cấu hình notify (alert + weekly report)

3. Device Connection
   → GET /devices/presets — để hiện dropdown chọn loại thiết bị
   → POST /devices — đăng ký thiết bị, chọn channels
   → POST /sessions/start — lấy session_id + ws_url

4. History / Alerts
   → GET /patients/{id}/sessions
   → GET /patients/{id}/alerts

5. Weekly Report
   → GET /patients/{id}/weekly-report?week=...
   → POST /reports/generate (on-demand)

CORS: Bật ALLOWED_ORIGINS cho https://neuratriage-eeg.vercel.app
```

---

## 13. Checklist triển khai (theo thứ tự)

```
□ 1. Setup FastAPI app + DB + Alembic migrations
□ 2. Implement ModelManager + load endpoint
□ 3. Implement ChannelMapper (unit test ngay)
□ 4. Implement SessionManager
□ 5. WebSocket handler + test với fake EEG data
□ 6. CRUD: Patient, Doctor, Device, EmergencyContact
□ 7. Offline inference endpoint (.npz upload)
□ 8. Alert persistence (ghi DB khi status=alert-enter)
□ 9. Report service (PDF generation)
□ 10. SendGrid integration + test với email thật
□ 11. APScheduler weekly job
□ 12. CORS + env config cho production
□ 13. Docker + deploy
```

---

*Generated for NeuraTriage EEG backend — based on eeg_stroke_pipeline.py (ApFu-MFDFA-TPELGBM-RT) and Brain-Life Focus+ Technical Specifications.*
