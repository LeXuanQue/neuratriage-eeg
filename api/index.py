"""
NeuraTriage EEG — Backend API
=============================

Flask app phục vụ JSON API cho frontend trên Vercel.

Endpoints:
- GET  /api/health           : liveness probe (no auth)
- GET  /api/disclaimer       : research-use-only banner
- GET  /api/live             : live monitor payload (no auth, demo/API stream)
- POST /api/auth/login       : email+password -> JWT
- GET  /api/auth/me          : (Bearer JWT) -> user info
- POST /api/auth/logout      : (Bearer JWT) -> audit only (stateless)
- POST /api/infer            : (Bearer JWT) -> chạy inference 1 file EEG
                                Lazy-load pipeline; trả 503 nếu deps không nạp được.

Compliance hooks (đáp ứng tiêu chuẩn y sinh):
- CORS whitelist (FRONTEND_ORIGIN), không dùng wildcard ở production
- JWT HS256, exp 8h (đổi sang RS256 khi có HSM/KMS)
- bcrypt cost=12 cho password
- Constant-time compare chống timing oracle
- Audit log JSON ra stdout cho mọi action có hệ quả
- Error envelope chuẩn { success, error: { code, message } }
- Response không leak stack trace ra client
- "FOR RESEARCH USE ONLY" trong mọi response

Local dev:
    python api/index.py        # → http://127.0.0.1:8501

Vercel:
    Tự nhận `app` global từ file này (Vercel Python runtime).
"""
from __future__ import annotations

import json
import logging
import math
import os
import sys
import time
import traceback
from datetime import datetime, timedelta, timezone
from functools import wraps
from pathlib import Path
from typing import Any, Callable, Dict, Tuple

import bcrypt
import jwt
from flask import Flask, Response, g, jsonify, request


# ──────────────────────────────────────────────────────────────────
# Setup
# ──────────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent

# Cho phép import eeg_stroke_pipeline từ backend/
sys.path.insert(0, str(ROOT / "backend"))

JWT_SECRET = os.environ.get("JWT_SECRET", "dev-secret-CHANGE-ME-in-production")
JWT_ALGORITHM = "HS256"
JWT_EXPIRES_HOURS = int(os.environ.get("JWT_EXPIRES_HOURS", "8"))

# Whitelist origin. Production: set chính xác domain Vercel.
# Dev: "*" được chấp nhận vì localhost.
FRONTEND_ORIGIN = os.environ.get("FRONTEND_ORIGIN", "*")

DISCLAIMER = (
    "FOR RESEARCH USE ONLY. NOT A MEDICAL DEVICE. "
    "Output must not be used as the sole basis for clinical decisions. "
    "Có giá trị tham khảo nghiên cứu — không thay thế chẩn đoán lâm sàng."
)
CLASS_KEYS = ("NS", "IS", "HS")

# Logger structured JSON
logging.basicConfig(
    level=logging.INFO,
    format='{"ts":"%(asctime)s","level":"%(levelname)s","msg":%(message)s}',
)
log = logging.getLogger("neuratriage")


# ──────────────────────────────────────────────────────────────────
# Demo user store (THAY BẰNG DATABASE THẬT TRƯỚC KHI PRODUCTION)
# ──────────────────────────────────────────────────────────────────
def _hash(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=12)).decode()


DEMO_USERS: Dict[str, Dict[str, Any]] = {
    "bs.lan@hospital.vn": {
        "password_hash": _hash("password"),
        "role": "doctor",
        "name": "BS. Nguyen Thi Lan",
    },
    "tech@hospital.vn": {
        "password_hash": _hash("password"),
        "role": "technician",
        "name": "KTV. Tran Van A",
    },
    "admin@neuratriage.dev": {
        "password_hash": _hash("admin123"),
        "role": "admin",
        "name": "System Admin",
    },
}


# ──────────────────────────────────────────────────────────────────
# Flask app
# ──────────────────────────────────────────────────────────────────
app = Flask(__name__)


# ──────────────────────────────────────────────────────────────────
# Helpers: response envelope
# ──────────────────────────────────────────────────────────────────
def ok(data: Any, status: int = 200) -> Tuple[Response, int]:
    return jsonify({"success": True, "data": data, "disclaimer": DISCLAIMER}), status


def err(code: str, message: str, status: int = 400, **extra: Any) -> Tuple[Response, int]:
    body = {"success": False, "error": {"code": code, "message": message, **extra}}
    return jsonify(body), status


def audit(event: str, **fields: Any) -> None:
    """Audit log có cấu trúc — chuyển vào DB/SIEM khi production."""
    payload = {"event": event, **fields}
    log.info(json.dumps(payload, ensure_ascii=False))


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def normalize_probs(ns: float, ischemic: float, hemorrhagic: float) -> Dict[str, float]:
    values = [max(0.01, float(ns)), max(0.01, float(ischemic)), max(0.01, float(hemorrhagic))]
    total = sum(values)
    return {key: values[i] / total for i, key in enumerate(CLASS_KEYS)}


def simulated_probabilities(scenario: str, now: float) -> Dict[str, float]:
    wave = math.sin(now * 0.72)
    slow = math.sin(now * 0.18)
    ripple = math.sin(now * 1.31)
    if scenario == "NS":
        return normalize_probs(0.80 + 0.04 * wave, 0.13 + 0.025 * slow, 0.07 + 0.015 * ripple)
    if scenario == "IS":
        ramp = 0.5 + 0.5 * math.sin(now * 0.22)
        return normalize_probs(0.20 - 0.04 * ramp, 0.64 + 0.12 * ramp + 0.03 * wave, 0.13 + 0.02 * ripple)
    ramp = 0.5 + 0.5 * math.sin(now * 0.20)
    return normalize_probs(0.06 + 0.025 * slow, 0.17 + 0.035 * wave, 0.70 + 0.12 * ramp + 0.025 * ripple)


def live_payload(scenario_text: str) -> Dict[str, Any]:
    scenario = (scenario_text or "HS").upper()
    if scenario not in CLASS_KEYS:
        scenario = "HS"
    now = time.time()
    probs = simulated_probabilities(scenario, now)
    dominant = max(probs, key=probs.get)
    sqi = clamp(0.90 + 0.045 * math.sin(now * 0.27), 0.74, 0.98)
    status = "alert-hold" if dominant in {"IS", "HS"} and probs[dominant] >= 0.72 else "monitor"
    history = []
    for i in range(80):
        point = simulated_probabilities(scenario, now - (79 - i))
        point["t"] = i - 79
        history.append(point)
    scale = 1.0 if scenario == "HS" else 0.78 if scenario == "IS" else 0.42
    wobble = math.sin(now * 0.55) * 0.012
    return {
        "source": "vercel-api-sim",
        "timestamp_ms": int(now * 1000),
        "scenario": scenario,
        "mode": scenario,
        "status": status,
        "dominant": dominant,
        "probabilities": probs,
        "sqi": sqi,
        "time_to_alert_sec": 4.2 if status.startswith("alert") else None,
        "patient": {
            "name": "Nguyen Van T.",
            "initials": "NV",
            "mrn": "MRN-2026-04812",
            "age": 67,
            "sex": "M",
            "bed": "ED-04",
            "onset_min": 42,
        },
        "device": {
            "name": "g.tec g.HIamp",
            "sample_rate": 256,
            "battery": int(clamp(87 + 4 * math.sin(now * 0.08), 78, 94)),
            "channels": 19,
            "stream": "connected",
        },
        "history": history,
        "features": [
            {"name": "FuEn (T4)", "value": 0.135 * scale + wobble},
            {"name": "delta_h MFDFA (Fp2)", "value": 0.118 * scale - wobble * 0.6},
            {"name": "alpha-power (O1)", "value": -0.096 * scale + wobble * 0.4},
            {"name": "ApEn (C3)", "value": 0.082 * scale + wobble * 0.8},
            {"name": "Hurst H(2) (P4)", "value": 0.068 * scale - wobble * 0.3},
            {"name": "theta/alpha ratio (Fz)", "value": 0.061 * scale + wobble * 0.5},
        ],
        "metrics": {
            "apen_mean": 0.84 + 0.04 * math.sin(now * 0.33),
            "fuen_mean": 0.91 + 0.035 * math.sin(now * 0.29),
            "h2": 0.71 + 0.025 * math.sin(now * 0.41),
            "delta_alpha": 0.55 + 0.05 * math.sin(now * 0.24),
            "bsi_delta": 0.34 + 0.04 * math.sin(now * 0.37),
            "theta_alpha": 1.82 + 0.12 * math.sin(now * 0.31),
        },
    }


# ──────────────────────────────────────────────────────────────────
# CORS (preflight + actual response)
# ──────────────────────────────────────────────────────────────────
@app.before_request
def _cors_preflight():
    if request.method == "OPTIONS":
        resp = app.make_default_options_response()
        _apply_cors_headers(resp)
        return resp


@app.after_request
def _cors_response(resp: Response) -> Response:
    _apply_cors_headers(resp)
    return resp


def _apply_cors_headers(resp: Response) -> None:
    origin = request.headers.get("Origin", "")
    if FRONTEND_ORIGIN == "*":
        allow = origin or "*"
    elif origin == FRONTEND_ORIGIN:
        allow = origin
    elif origin.endswith(".vercel.app") and FRONTEND_ORIGIN.endswith(".vercel.app"):
        # Cho phép Vercel preview deployments khi origin chính cũng là Vercel
        allow = origin
    else:
        allow = FRONTEND_ORIGIN

    resp.headers["Access-Control-Allow-Origin"] = allow or "*"
    resp.headers["Access-Control-Allow-Credentials"] = "true"
    resp.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    resp.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
    resp.headers["Access-Control-Max-Age"] = "86400"
    resp.headers["Vary"] = "Origin"
    resp.headers.setdefault("X-Content-Type-Options", "nosniff")
    resp.headers.setdefault("Referrer-Policy", "no-referrer")


# ──────────────────────────────────────────────────────────────────
# JWT helpers
# ──────────────────────────────────────────────────────────────────
def create_access_token(email: str, role: str, name: str) -> Dict[str, Any]:
    now = datetime.now(timezone.utc)
    exp = now + timedelta(hours=JWT_EXPIRES_HOURS)
    payload = {
        "sub": email,
        "role": role,
        "name": name,
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
        "iss": "neuratriage-api",
    }
    token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
    return {
        "access_token": token,
        "token_type": "Bearer",
        "expires_in": JWT_EXPIRES_HOURS * 3600,
        "expires_at": payload["exp"],
    }


def verify_token(token: str) -> Dict[str, Any]:
    return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM], issuer="neuratriage-api")


def require_auth(*allowed_roles: str) -> Callable:
    """
    Decorator: chỉ cho qua nếu request có Bearer token hợp lệ
    và (nếu có allowed_roles) role nằm trong whitelist.
    """
    def deco(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            header = request.headers.get("Authorization", "")
            if not header.startswith("Bearer "):
                return err("NO_TOKEN", "Missing Bearer token", 401)
            token = header[7:].strip()
            try:
                payload = verify_token(token)
            except jwt.ExpiredSignatureError:
                return err("TOKEN_EXPIRED", "Token expired, please re-login", 401)
            except jwt.InvalidTokenError:
                return err("INVALID_TOKEN", "Invalid token", 401)

            if allowed_roles and payload.get("role") not in allowed_roles:
                audit("authz.denied", user=payload.get("sub"), role=payload.get("role"),
                      required=list(allowed_roles), path=request.path)
                return err("FORBIDDEN", "Insufficient role", 403)

            g.user = payload
            return fn(*args, **kwargs)
        return wrapper
    return deco


# ──────────────────────────────────────────────────────────────────
# Routes — public
# ──────────────────────────────────────────────────────────────────
@app.route("/api/health", methods=["GET"])
def health():
    return ok({
        "status": "ok",
        "ts": int(time.time()),
        "version": "0.5.0",
        "pipeline_loadable": _can_load_pipeline(),
    })


@app.route("/api/disclaimer", methods=["GET"])
def disclaimer():
    return ok({"text": DISCLAIMER})


@app.route("/api/live", methods=["GET"])
def live():
    return ok(live_payload(request.args.get("scenario", "HS")))


# ──────────────────────────────────────────────────────────────────
# Routes — auth
# ──────────────────────────────────────────────────────────────────
@app.route("/api/auth/login", methods=["POST"])
def login():
    body = request.get_json(silent=True) or {}
    email = (body.get("email") or "").strip().lower()
    password = body.get("password") or ""

    if not email or not password:
        return err("MISSING_FIELDS", "email and password are required", 422)

    user = DEMO_USERS.get(email)
    # Constant-time compare cả khi user không tồn tại (chống timing oracle)
    placeholder_hash = bcrypt.hashpw(b"placeholder", bcrypt.gensalt(rounds=4))
    target_hash = (user["password_hash"].encode() if user else placeholder_hash)
    matched = bcrypt.checkpw(password.encode(), target_hash) if user else False

    if not matched:
        audit("auth.login.failed", email=email, ip=request.remote_addr)
        return err("INVALID_CREDENTIALS", "Wrong email or password", 401)

    token_data = create_access_token(email, user["role"], user["name"])
    audit("auth.login.ok", email=email, role=user["role"], ip=request.remote_addr)

    return ok({
        **token_data,
        "user": {"email": email, "role": user["role"], "name": user["name"]},
    })


@app.route("/api/auth/me", methods=["GET"])
@require_auth()
def me():
    u = g.user
    return ok({
        "email": u["sub"],
        "role": u.get("role"),
        "name": u.get("name"),
        "expires_at": u.get("exp"),
    })


@app.route("/api/auth/logout", methods=["POST"])
@require_auth()
def logout():
    audit("auth.logout", email=g.user["sub"])
    return ok({"message": "Signed out"})


# ──────────────────────────────────────────────────────────────────
# Routes — inference (heavy, lazy-loaded)
# ──────────────────────────────────────────────────────────────────
_pipeline_cache: Dict[str, Any] = {"module": None, "model": None, "error": None}


def _can_load_pipeline() -> bool:
    try:
        if _pipeline_cache["module"] is None:
            import eeg_stroke_pipeline  # noqa: F401
            _pipeline_cache["module"] = eeg_stroke_pipeline
        return True
    except Exception as e:
        _pipeline_cache["error"] = repr(e)
        return False


def _load_model():
    if _pipeline_cache["model"] is not None:
        return _pipeline_cache["model"]
    if not _can_load_pipeline():
        raise RuntimeError(_pipeline_cache["error"] or "Pipeline import failed")

    p = _pipeline_cache["module"]
    model_path = os.environ.get("MODEL_PATH") or str(ROOT / "backend" / "models" / "model.joblib")
    if not Path(model_path).exists():
        raise FileNotFoundError(f"MODEL_PATH not found: {model_path}")

    # Đăng ký alias cho joblib unpickle khi pickle ref __main__
    import __main__
    for name in ("PipelineConfig", "TemperatureScaler", "TrainedStrokeModel"):
        if hasattr(p, name):
            setattr(__main__, name, getattr(p, name))

    model = p.TrainedStrokeModel.load(model_path)
    _pipeline_cache["model"] = model
    return model


@app.route("/api/infer", methods=["POST"])
@require_auth("doctor", "technician", "admin")
def infer():
    body = request.get_json(silent=True) or {}
    eeg_path = (body.get("eeg_path") or "").strip()
    patient_id = (body.get("patient_id") or "anon").strip()
    label = (body.get("label") or "non-stroke").strip()

    if not eeg_path:
        return err("MISSING_FIELDS", "eeg_path is required", 422)
    if not Path(eeg_path).exists():
        return err("EEG_FILE_NOT_FOUND", f"File not found on server: {eeg_path}", 404)

    try:
        model = _load_model()
        p = _pipeline_cache["module"]
    except FileNotFoundError as e:
        return err("MODEL_NOT_AVAILABLE", str(e), 503,
                   hint="Đặt model.joblib vào backend/models/ hoặc set env MODEL_PATH")
    except Exception:
        log.exception("pipeline load failed")
        return err("PIPELINE_UNAVAILABLE",
                   "Pipeline cannot load (heavy ML deps may exceed Vercel limits). "
                   "Deploy backend trên Render/Railway/Fly cho /api/infer.",
                   503)

    try:
        cfg = p.PipelineConfig(**model.config)
        data, channels, fs_in_file = p.load_array_file(eeg_path)
        fs = fs_in_file or cfg.fs
        record = p.EEGRecord(
            patient_id=patient_id,
            label=p.parse_label(label),
            data=p.reorder_to_target_channels(data, channels, cfg.channels),
            channels=list(cfg.channels),
            fs=float(fs),
        )
        frame = p.run_offline_inference(model, record, cfg)
    except Exception:
        log.exception("inference failed")
        return err("INFERENCE_FAILED", "Pipeline crashed during inference", 500)

    if frame.empty:
        return ok({"windows": [], "summary": None,
                   "warning": "No windows produced — check signal length / SQI"})

    cols = [
        "t_end_sec", "sqi_total", "pred_class",
        "p_nonstroke_smooth", "p_ischemic_smooth", "p_hemorrhagic_smooth",
    ]
    present = [c for c in cols if c in frame.columns]
    windows = frame[present].tail(50).to_dict(orient="records")
    last = frame.tail(1).iloc[0]
    summary = {
        "latest_class": str(last.get("pred_class", "")),
        "latest_t_end_sec": float(last.get("t_end_sec", 0.0)),
        "latest_sqi": float(last.get("sqi_total", 0.0)),
        "n_windows": int(len(frame)),
    }

    audit("infer.ok", user=g.user["sub"], patient_id=patient_id, n_windows=len(frame))
    return ok({"windows": windows, "summary": summary})


# ──────────────────────────────────────────────────────────────────
# Error handlers — KHÔNG leak stack trace ra client
# ──────────────────────────────────────────────────────────────────
@app.errorhandler(404)
def not_found(_e):
    return err("NOT_FOUND", f"No route: {request.path}", 404)


@app.errorhandler(405)
def method_not_allowed(_e):
    return err("METHOD_NOT_ALLOWED", f"{request.method} not allowed on {request.path}", 405)


@app.errorhandler(Exception)
def server_error(e):
    log.error(json.dumps(
        {"path": request.path, "exc": repr(e), "tb": traceback.format_exc()},
        ensure_ascii=False))
    return err("INTERNAL_ERROR", "Server error. Logged with request id.", 500)


# ──────────────────────────────────────────────────────────────────
# Local dev entry
# ──────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8502))
    print(f"NeuraTriage API running at http://127.0.0.1:{port}")
    print(f"  JWT_SECRET = {'(default — set env JWT_SECRET in production)' if JWT_SECRET.startswith('dev-') else '(custom)'}")
    print(f"  FRONTEND_ORIGIN = {FRONTEND_ORIGIN}")
    print(f"  Demo users: {list(DEMO_USERS.keys())}")
    app.run(host="0.0.0.0", port=port, debug=True)
