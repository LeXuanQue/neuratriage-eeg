"""Curated demo scenarios — drive the whole app without any real headset.

Demo mode exists so a first-time viewer can understand how NeuraTriage works:
each scenario pins a stored EEG replay case plus the demo controls needed to
reach one specific, explainable end state (alert / monitor / no-decision).

Nothing here fabricates model output. A scenario only selects *which real
recording* gets streamed through the same WebSocket + detector path a live
device would use, so what the viewer sees is genuine pipeline behaviour.
"""
from __future__ import annotations

import zipfile
from pathlib import Path
from typing import Any, Optional

import numpy as np

from ..config import REPO_ROOT
from .replay_cases import resolve_replay_case


ISCHEMIC_DIR = "dataset_ischemic"
HEALTHY_DIR = "dataset_healthy"

# Preferred case per scenario. If the pinned file is missing we fall back to the
# first case in the same dataset directory so demo mode never dead-ends.
#
# `expect_at_sec` is the EEG timestamp at which the scenario's end state was
# observed when the pinned case was replayed offline through the shipped model
# (model.joblib sha256 fb8c26c9…, measured 2026-08-20): sub-01 emits its first
# event at 4.0 s and alert-enter at 4.5 s; sub-S001 stays on monitor for all
# 237 windows. It is a "what to watch for" hint for the UI, not a guarantee —
# a different model or case shifts it.
#
# `expect_models` lists the real-time models (REALTIME_MODEL) the expectation was
# actually measured with; the UI warns when the active model is not one of them.
# 2026-10-06, REALTIME_MODEL=riemann: sub-01 alert-enter at 4.5 s; sub-S001 stays
# monitor (both halves); artifact gate is model-independent; the stitched case
# follows its sources (monitor on NS parts, alert on IS parts).
# `in_riemann_training` = the recording was in the riemann model's training set,
# so it shows the pipeline working, not generalisation.
_SCENARIO_SPECS: tuple[dict[str, Any], ...] = (
    {
        "id": "ischemic-alert",
        "preferred_case": "sub-01.npz",
        "dataset_dir": ISCHEMIC_DIR,
        "class_hint": "ischemic",
        "artifact": False,
        "expected_status": "alert",
        "expect_at_sec": 4.5,
        "accent": "is",
        "loop": False,
        "stitched": False,
        "expect_models": ["features", "riemann"],
        "failure_mode": False,
        "in_riemann_training": True,
        "title": {
            "vi": "Ca thiếu máu não — chạy tới cảnh báo",
            "en": "Ischemic case — runs to an alert",
        },
        "summary": {
            "vi": "Phát lại một bản ghi EEG thiếu máu não đã lưu, đi qua đúng "
            "đường WebSocket + detector mà thiết bị thật sẽ dùng.",
            "en": "Replays a stored ischemic EEG recording through the same "
            "WebSocket + detector path a real device would use.",
        },
        "expect": {
            "vi": "Xác suất IS tăng dần, vượt ngưỡng 0.80 ở hai cửa sổ liên "
            "tiếp rồi chuyển sang alert-enter. Nút Ack / Báo MD mở khoá.",
            "en": "IS probability climbs, crosses the 0.80 gate on two "
            "consecutive windows, then flips to alert-enter. Ack / Page MD unlock.",
        },
    },
    {
        "id": "healthy-monitor",
        "preferred_case": "sub-S001.npz",
        "dataset_dir": HEALTHY_DIR,
        "class_hint": "non-stroke",
        "artifact": False,
        "expected_status": "monitor",
        "expect_at_sec": 4.0,
        "accent": "ns",
        "loop": False,
        "stitched": False,
        "expect_models": ["features", "riemann"],
        "failure_mode": False,
        "in_riemann_training": True,
        "title": {
            "vi": "Ca không đột quỵ — theo dõi, không báo động giả",
            "en": "Non-stroke case — monitors without false alarms",
        },
        "summary": {
            "vi": "Bản ghi EEG của người không đột quỵ, để thấy hệ thống im "
            "lặng đúng lúc chứ không phải chỉ biết kêu.",
            "en": "A non-stroke EEG recording, so you can see the system stay "
            "quiet instead of only knowing how to fire.",
        },
        "expect": {
            "vi": "Trạng thái giữ ở monitor, xác suất NS chiếm ưu thế, và không "
            "có dòng cảnh báo nào được ghi.",
            "en": "Status stays at monitor, NS dominates the probabilities, and "
            "no alert row is written.",
        },
    },
    {
        "id": "signal-artifact",
        "preferred_case": "sub-01.npz",
        "dataset_dir": ISCHEMIC_DIR,
        "class_hint": "ischemic",
        "artifact": True,
        "expected_status": "no-decision",
        "expect_at_sec": 4.0,
        "accent": "warn",
        "loop": False,
        "stitched": False,
        "expect_models": ["features", "riemann"],
        "failure_mode": False,
        "in_riemann_training": True,
        "title": {
            "vi": "Nhiễu tín hiệu — hệ thống từ chối kết luận",
            "en": "Signal artifact — the system refuses to conclude",
        },
        "summary": {
            "vi": "Cùng bản ghi thiếu máu não nhưng bật chèn nhiễu, để thấy cổng "
            "SQI chặn quyết định thay vì đoán bừa.",
            "en": "The same ischemic recording with artifact injection on, so you "
            "can see the SQI gate block the decision instead of guessing.",
        },
        "expect": {
            "vi": "SQI tụt xuống dưới 0.55, trạng thái thành no-decision, xác "
            "suất và nút xử trí bị khoá cho tới khi tín hiệu sạch trở lại.",
            "en": "SQI drops below 0.55, status becomes no-decision, and both the "
            "probabilities and the action buttons stay locked until the signal "
            "is clean again.",
        },
    },
    {
        "id": "continuous-visual",
        "preferred_case": "continuous_demo.npz",
        "dataset_dir": "dataset_npz",
        "class_hint": "demo",
        "artifact": False,
        "expected_status": "mixed",
        "expect_at_sec": 4.0,
        "accent": "brand",
        "loop": True,
        "stitched": True,
        "expect_models": ["features", "riemann"],
        "failure_mode": False,
        "in_riemann_training": True,
        "title": {
            "vi": "Chạy liên tục — dựng ghép nhiều bản ghi",
            "en": "Continuous run — several recordings stitched",
        },
        "summary": {
            "vi": "Bốn bản ghi nối lại (không đột quỵ → thiếu máu não → lặp lại), "
            "crossfade 0.5 giây ở mối nối và tự lặp vô hạn. Dành cho màn hình "
            "trình chiếu: sóng không bao giờ dừng.",
            "en": "Four recordings joined (non-stroke → ischemic → repeat), "
            "crossfaded over 0.5 s at each seam and looped forever. Built for a "
            "display screen: the trace never stops.",
        },
        "expect": {
            "vi": "Trạng thái chuyển qua lại giữa monitor và alert khi chạy sang "
            "đoạn bản ghi khác. Đây là file DỰNG GHÉP để xem hình, không phải "
            "bản ghi của một người bệnh.",
            "en": "The state moves back and forth between monitor and alert as "
            "playback crosses into a different source recording. This is a "
            "STITCHED file for visuals, not one patient's recording.",
        },
    },
    {
        # Known failure mode, shown on purpose. Only listed when EXTRA_REPLAY_DIR
        # points at the converted Oslo ds003775 cases (not shipped in the repo).
        # Measured 2026-10-06 with REALTIME_MODEL=riemann: alert-enter at 4.5 s and
        # in alert for 62% of the 240 s recording, although the person is healthy.
        "id": "unseen-device-false-alert",
        "preferred_case": "os-056.npz",
        "dataset_dir": None,
        "class_hint": "non-stroke",
        "artifact": False,
        "expected_status": "alert",
        "expect_at_sec": 4.5,
        "accent": "warn",
        "loop": False,
        "stitched": False,
        "expect_models": ["riemann"],
        "failure_mode": True,
        "in_riemann_training": False,
        "title": {
            "vi": "Giới hạn đã biết — người khỏe, máy lạ, nhắm mắt → báo động giả",
            "en": "Known limitation — healthy, unseen device, eyes closed → false alarm",
        },
        "summary": {
            "vi": "Người khỏe (Oslo, máy BioSemi, nghỉ nhắm mắt) mà model Riemann "
            "chưa từng thấy. Model chỉ được train với người khỏe MỞ mắt (để không bỏ "
            "sót bệnh nhân đột quỵ đang nhắm mắt), nên ca này phơi bày cái giá của lựa chọn đó.",
            "en": "A healthy person (Oslo, BioSemi device, eyes-closed rest) the riemann "
            "model has never seen. The model was trained only on eyes-OPEN controls (so a "
            "drowsy stroke patient is not missed), and this case shows the price of that choice.",
        },
        "expect": {
            "vi": "Với REALTIME_MODEL=riemann: alert-enter khoảng 4.5 giây và nằm ở trạng "
            "thái cảnh báo khoảng 62% thời gian (đo ngày 6/10/2026). Đây là BÁO ĐỘNG GIẢ: "
            "người này khỏe. Chưa đo với model đặc trưng.",
            "en": "With REALTIME_MODEL=riemann: alert-enter at about 4.5 s and in alert "
            "about 62% of the time (measured 2026-10-06). This is a FALSE ALARM: the person "
            "is healthy. Not measured with the feature model.",
        },
    },
)

# Duration lookups are pure file metadata — cache on (path, mtime, size).
_duration_cache: dict[tuple[str, float, int], float] = {}


def _read_duration_from_zip(path: Path) -> Optional[float]:
    """Read n_samples/fs from the npz members without decompressing `data`."""
    with zipfile.ZipFile(path) as archive:
        names = set(archive.namelist())
        if "data.npy" not in names or "fs.npy" not in names:
            return None
        with archive.open("data.npy") as handle:
            version = np.lib.format.read_magic(handle)
            shape, _, _ = np.lib.format._read_array_header(handle, version)
        with archive.open("fs.npy") as handle:
            fs = float(np.load(handle, allow_pickle=False))
    if len(shape) < 2 or fs <= 0:
        return None
    return float(shape[1]) / fs


def replay_duration_sec(path: Path) -> float:
    """Duration of a replay case in seconds (0.0 when it cannot be determined)."""
    try:
        stat = path.stat()
    except OSError:
        return 0.0
    key = (str(path), stat.st_mtime, stat.st_size)
    cached = _duration_cache.get(key)
    if cached is not None:
        return cached

    duration: Optional[float] = None
    try:
        duration = _read_duration_from_zip(path)
    except Exception:
        duration = None
    if duration is None:
        try:
            with np.load(path, allow_pickle=False) as bundle:
                fs = float(bundle["fs"])
                duration = float(bundle["data"].shape[1]) / fs if fs > 0 else None
        except Exception:
            duration = None

    resolved = round(float(duration), 1) if duration and duration > 0 else 0.0
    _duration_cache[key] = resolved
    return resolved


def _resolve_case(spec: dict[str, Any]) -> Optional[tuple[str, Path]]:
    preferred = str(spec["preferred_case"])
    path = resolve_replay_case(preferred)
    if path is not None:
        return preferred, path
    if not spec.get("dataset_dir"):          # pinned-only case (e.g. EXTRA_REPLAY_DIR): no fallback
        return None
    folder = REPO_ROOT / str(spec["dataset_dir"])
    if not folder.is_dir():
        return None
    for candidate in sorted(folder.glob("*.npz")):
        resolved = resolve_replay_case(candidate.name)
        if resolved is not None:
            return candidate.name, resolved
    return None


def list_demo_scenarios() -> list[dict[str, Any]]:
    """Runnable demo scenarios, skipping any whose dataset is not present."""
    scenarios: list[dict[str, Any]] = []
    for spec in _SCENARIO_SPECS:
        resolved = _resolve_case(spec)
        if resolved is None:
            continue
        case_id, path = resolved
        scenarios.append(
            {
                "id": spec["id"],
                "title": dict(spec["title"]),
                "summary": dict(spec["summary"]),
                "expect": dict(spec["expect"]),
                "replay_case": case_id,
                "dataset": spec["dataset_dir"] or "extra_replay_dir",
                "class_hint": spec["class_hint"],
                "artifact": bool(spec["artifact"]),
                "expected_status": spec["expected_status"],
                "expect_at_sec": spec["expect_at_sec"],
                "loop": bool(spec["loop"]),
                "stitched": bool(spec["stitched"]),
                "accent": spec["accent"],
                "expect_models": list(spec["expect_models"]),
                "failure_mode": bool(spec["failure_mode"]),
                "in_riemann_training": bool(spec["in_riemann_training"]),
                "duration_sec": replay_duration_sec(path),
            }
        )
    return scenarios


def get_demo_scenario(scenario_id: str) -> Optional[dict[str, Any]]:
    for scenario in list_demo_scenarios():
        if scenario["id"] == scenario_id:
            return scenario
    return None
