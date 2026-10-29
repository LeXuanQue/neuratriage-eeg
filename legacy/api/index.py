"""
NeuraTriage EEG — unified Flask server.

Serves frontend static files at / and all /api/* endpoints.

Run locally:
  .venv\\Scripts\\python.exe api\\index.py
  .venv\\Scripts\\python.exe api\\index.py --port 8080

Demo credentials:
  admin@neuratriage.com   / demo1234
  doctor@neuratriage.com  / demo1234
"""
from __future__ import annotations

import math
import sys
import time
from functools import wraps
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
FRONTEND_DIR = ROOT / "frontend"
sys.path.insert(0, str(ROOT / "backend"))

import uuid

import bcrypt
import jwt
from flask import Flask, jsonify, request, send_from_directory
from werkzeug.utils import secure_filename

# ── Config ────────────────────────────────────────────────────────────────────

SECRET = "neuratriage-dev-secret-2026-eeg"  # change to env var in production
TOKEN_TTL = 8 * 3600                     # 8 hours
CLASS_KEYS = ("NS", "IS", "HS")
UPLOAD_DIR = ROOT / "tmp" / "uploads"
ALLOWED_EXTS = {".edf", ".bdf", ".fif", ".npz"}

# Demo users — hashed at startup, no database needed for research demo
_USERS: list[dict] = [
    {
        "id": "1",
        "email": "admin@neuratriage.com",
        "name": "Admin",
        "role": "admin",
        "_pw": bcrypt.hashpw(b"demo1234", bcrypt.gensalt()),
    },
    {
        "id": "2",
        "email": "doctor@neuratriage.com",
        "name": "Dr. Nguyen",
        "role": "clinician",
        "_pw": bcrypt.hashpw(b"demo1234", bcrypt.gensalt()),
    },
]

# ── App ───────────────────────────────────────────────────────────────────────

app = Flask(__name__, static_folder=str(FRONTEND_DIR), static_url_path="")


def ok(data: Any = None):
    return jsonify({"success": True, "data": data})


def err(message: str, code: str = "ERROR", status: int = 400):
    return jsonify({"success": False, "error": {"message": message, "code": code}}), status


@app.after_request
def add_cors(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    return response


@app.route("/api/", defaults={"path": ""}, methods=["OPTIONS"])
@app.route("/api/<path:path>", methods=["OPTIONS"])
def options_handler(path=""):
    return "", 204


# ── Auth middleware ───────────────────────────────────────────────────────────

def require_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        header = request.headers.get("Authorization", "")
        if not header.startswith("Bearer "):
            return err("Missing token", "MISSING_TOKEN", 401)
        token = header[7:]
        try:
            payload = jwt.decode(token, SECRET, algorithms=["HS256"])
        except jwt.ExpiredSignatureError:
            return err("Token expired", "TOKEN_EXPIRED", 401)
        except jwt.InvalidTokenError:
            return err("Invalid token", "INVALID_TOKEN", 401)
        request.user_id = payload["sub"]
        return f(*args, **kwargs)
    return decorated


def _find_user(email: str) -> dict | None:
    return next((u for u in _USERS if u["email"] == email), None)


def _user_public(u: dict) -> dict:
    return {"id": u["id"], "email": u["email"], "name": u["name"], "role": u["role"]}


# ── Auth endpoints ────────────────────────────────────────────────────────────

@app.route("/api/auth/login", methods=["POST"])
def login():
    body     = request.get_json(silent=True) or {}
    email    = (body.get("email") or "").strip().lower()
    password = (body.get("password") or "").encode()
    if not email or not password:
        return err("Email and password required", "MISSING_FIELDS")
    user = _find_user(email)
    if not user or not bcrypt.checkpw(password, user["_pw"]):
        return err("Invalid email or password", "INVALID_CREDENTIALS", 401)
    exp   = int(time.time()) + TOKEN_TTL
    token = jwt.encode({"sub": user["id"], "exp": exp}, SECRET, algorithm="HS256")
    return ok({"access_token": token, "expires_at": exp, "user": _user_public(user)})


@app.route("/api/auth/me")
@require_auth
def me():
    user = next((u for u in _USERS if u["id"] == request.user_id), None)
    if not user:
        return err("User not found", "USER_NOT_FOUND", 404)
    return ok(_user_public(user))


@app.route("/api/auth/logout", methods=["POST"])
def logout():
    return ok({"message": "Logged out"})


# ── Health / Disclaimer ───────────────────────────────────────────────────────

@app.route("/api/health")
def health():
    return ok({"status": "ok", "app": "NeuraTriage EEG", "version": "0.1.0"})


@app.route("/api/disclaimer")
def disclaimer():
    return ok({
        "text": (
            "For research use only. Not validated for clinical diagnosis. "
            "Always consult a qualified physician for any medical decisions."
        ),
        "version": "1.0",
    })


# ── Live simulation ───────────────────────────────────────────────────────────

def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def _norm_probs(ns: float, ischemic: float, hemorrhagic: float) -> dict:
    vals  = [max(0.01, float(ns)), max(0.01, float(ischemic)), max(0.01, float(hemorrhagic))]
    total = sum(vals)
    return {k: vals[i] / total for i, k in enumerate(CLASS_KEYS)}


def _sim_probs(scenario: str, now: float) -> dict:
    wave   = math.sin(now * 0.72)
    slow   = math.sin(now * 0.18)
    ripple = math.sin(now * 1.31)
    if scenario == "NS":
        return _norm_probs(0.80 + 0.04 * wave, 0.13 + 0.025 * slow, 0.07 + 0.015 * ripple)
    if scenario == "IS":
        ramp = 0.5 + 0.5 * math.sin(now * 0.22)
        return _norm_probs(0.20 - 0.04 * ramp, 0.64 + 0.12 * ramp + 0.03 * wave, 0.13 + 0.02 * ripple)
    ramp = 0.5 + 0.5 * math.sin(now * 0.20)
    return _norm_probs(0.06 + 0.025 * slow, 0.17 + 0.035 * wave, 0.70 + 0.12 * ramp + 0.025 * ripple)


@app.route("/api/live")
def live():
    scenario = (request.args.get("scenario") or "HS").upper()
    if scenario not in CLASS_KEYS:
        scenario = "HS"
    now      = time.time()
    probs    = _sim_probs(scenario, now)
    dominant = max(probs, key=probs.get)
    sqi      = _clamp(0.90 + 0.045 * math.sin(now * 0.27), 0.74, 0.98)
    status   = "alert-hold" if dominant in {"IS", "HS"} and probs[dominant] >= 0.72 else "monitor"
    scale    = {"HS": 1.0, "IS": 0.78, "NS": 0.42}[scenario]
    wobble   = math.sin(now * 0.55) * 0.012
    history  = [
        {**_sim_probs(scenario, now - (79 - i)), "t": i - 79}
        for i in range(80)
    ]
    return ok({
        "source":            "backend-sim",
        "timestamp_ms":      int(now * 1000),
        "scenario":          scenario,
        "mode":              scenario,
        "status":            status,
        "dominant":          dominant,
        "probabilities":     probs,
        "sqi":               sqi,
        "time_to_alert_sec": 4.2 if status.startswith("alert") else None,
        "patient": {
            "name": "Nguyen Van T.", "initials": "NV",
            "mrn":  "MRN-2026-04812", "age": 67,
            "sex":  "M", "bed": "ED-04", "onset_min": 42,
        },
        "device": {
            "name":        "g.tec g.HIamp",
            "sample_rate": 256,
            "battery":     int(_clamp(87 + 4 * math.sin(now * 0.08), 78, 94)),
            "channels":    19,
            "stream":      "connected",
        },
        "history":  history,
        "features": [
            {"name": "FuEn (T4)",             "value": 0.135 * scale + wobble},
            {"name": "delta_h MFDFA (Fp2)",   "value": 0.118 * scale - wobble * 0.6},
            {"name": "alpha-power (O1)",       "value": -0.096 * scale + wobble * 0.4},
            {"name": "ApEn (C3)",              "value": 0.082 * scale + wobble * 0.8},
            {"name": "Hurst H(2) (P4)",        "value": 0.068 * scale - wobble * 0.3},
            {"name": "theta/alpha ratio (Fz)", "value": 0.061 * scale + wobble * 0.5},
        ],
        "metrics": {
            "apen_mean":   0.84 + 0.04  * math.sin(now * 0.33),
            "fuen_mean":   0.91 + 0.035 * math.sin(now * 0.29),
            "h2":          0.71 + 0.025 * math.sin(now * 0.41),
            "delta_alpha": 0.55 + 0.05  * math.sin(now * 0.24),
            "bsi_delta":   0.34 + 0.04  * math.sin(now * 0.37),
            "theta_alpha": 1.82 + 0.12  * math.sin(now * 0.31),
        },
    })


# ── File upload ──────────────────────────────────────────────────────────────

@app.route("/api/upload", methods=["POST"])
@require_auth
def upload_file():
    if "file" not in request.files:
        return err("No file provided", "NO_FILE")
    f = request.files["file"]
    if not f.filename:
        return err("Empty filename", "EMPTY_FILENAME")
    ext = Path(f.filename).suffix.lower()
    if ext not in ALLOWED_EXTS:
        return err(
            f"Unsupported format '{ext}'. Accepted: .edf .bdf .fif .npz",
            "UNSUPPORTED_FORMAT",
        )
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    safe_name = f"{uuid.uuid4().hex}_{secure_filename(f.filename)}"
    dest = UPLOAD_DIR / safe_name
    f.save(str(dest))
    return ok({
        "file_path":     str(dest),
        "original_name": f.filename,
        "size_bytes":    dest.stat().st_size,
    })


# ── Inference ─────────────────────────────────────────────────────────────────

@app.route("/api/infer", methods=["POST"])
@require_auth
def infer():
    body       = request.get_json(silent=True) or {}
    eeg_path   = body.get("eeg_path", "")
    patient_id = body.get("patient_id", "unknown")
    label      = body.get("label", "non-stroke")

    try:
        import eeg_stroke_pipeline as p
    except ImportError as exc:
        return err(f"Pipeline not available: {exc}", "PIPELINE_UNAVAILABLE", 503)

    model_path = next(
        (str(c) for c in [ROOT / "out" / "model.joblib",
                          ROOT / "dataset_npz" / "model_smoke.joblib"]
         if c.exists()),
        None,
    )
    if model_path is None:
        return err("No trained model found. Run training first.", "NO_MODEL", 503)
    if not eeg_path or not Path(eeg_path).exists():
        return err(f"EEG file not found: {eeg_path}", "FILE_NOT_FOUND", 404)

    try:
        import __main__
        for name in ("PipelineConfig", "TemperatureScaler", "TrainedStrokeModel"):
            if hasattr(p, name):
                setattr(__main__, name, getattr(p, name))
        trained = p.TrainedStrokeModel.load(model_path)
        cfg     = p.PipelineConfig(**trained.config)
        data, channels, fs_file = p.load_array_file(eeg_path)
        record  = p.EEGRecord(
            patient_id=patient_id,
            label=p.parse_label(label),
            data=p.reorder_to_target_channels(data, channels, cfg.channels),
            channels=list(cfg.channels),
            fs=float(fs_file or cfg.fs),
        )
        frame = p.run_offline_inference(trained, record, cfg)
        if frame.empty:
            return err(
                "No windows produced — check signal length and SQI threshold.",
                "NO_WINDOWS",
            )
        last = frame.tail(1).iloc[0]
        timeline = [
            {
                "t":   float(row.get("t_end_sec", i)),
                "NS":  float(row.get("p_nonstroke_smooth", 0)),
                "IS":  float(row.get("p_ischemic_smooth", 0)),
                "HS":  float(row.get("p_hemorrhagic_smooth", 0)),
                "sqi": float(row.get("sqi_total", 0)),
                "cls": str(row.get("pred_class", "")),
            }
            for i, (_, row) in enumerate(frame.iterrows())
        ]
        # Dominant class across all windows (majority vote by window count)
        from collections import Counter
        votes = Counter(w["cls"] for w in timeline)
        overall_class = votes.most_common(1)[0][0] if votes else str(last.get("pred_class", ""))
        mean_ns  = float(frame["p_nonstroke_smooth"].mean())
        mean_is  = float(frame["p_ischemic_smooth"].mean())
        mean_hs  = float(frame["p_hemorrhagic_smooth"].mean())
        return ok({
            "windows":  len(frame),
            "model":    model_path,
            "overall": {
                "pred_class":    overall_class,
                "p_nonstroke":   mean_ns,
                "p_ischemic":    mean_is,
                "p_hemorrhagic": mean_hs,
                "sqi":           float(frame["sqi_total"].mean()),
            },
            "latest":  {
                "t_end_sec":     float(last.get("t_end_sec", 0)),
                "pred_class":    str(last.get("pred_class", "")),
                "sqi":           float(last.get("sqi_total", 0)),
                "p_nonstroke":   float(last.get("p_nonstroke_smooth", 0)),
                "p_ischemic":    float(last.get("p_ischemic_smooth", 0)),
                "p_hemorrhagic": float(last.get("p_hemorrhagic_smooth", 0)),
            },
            "timeline": timeline,
        })
    except Exception as exc:
        return err(str(exc), "INFER_ERROR", 500)


# ── Serve frontend static files ───────────────────────────────────────────────

@app.route("/", defaults={"path": ""})
@app.route("/<path:path>")
def frontend(path):
    target = FRONTEND_DIR / path
    if path and target.exists() and target.is_file():
        return send_from_directory(str(FRONTEND_DIR), path)
    return send_from_directory(str(FRONTEND_DIR), "index.html")


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="NeuraTriage EEG unified server")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8501)
    args = parser.parse_args()
    print(f"\nNeuraTriage EEG  →  http://{args.host}:{args.port}")
    print(f"Login:  admin@neuratriage.com   /  demo1234")
    print(f"        doctor@neuratriage.com  /  demo1234\n")
    app.run(host=args.host, port=args.port, debug=False, threaded=True)
