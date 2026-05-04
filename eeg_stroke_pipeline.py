
#!/usr/bin/env python3
"""
ApFu-MFDFA-TPELGBM-RT
=====================

Python implementation of the EEG stroke pipeline described in the revised report.

Research alignment
------------------
1) Baseline branch:
   - Approximate entropy (ApEn) + fuzzy entropy (FuEn) on 1-second EEG windows.
   - LightGBM classifier optimized by TPE.
   - This follows the main design of Tong et al. (2025), where ApFu
     (ApEn + FuEn concatenation) on 1-second segments performed best.

2) Extension branch:
   - MFDFA features extracted from a longer 4-second buffer for stability.
   - Optional MFDFAI-style detrending hook using EMD + Pearson-based IMF
     selection, inspired by Wang et al. (2025).

3) Deployment branch:
   - patient-wise group splitting
   - SQI gating / no-decision mode
   - temperature scaling calibration
   - EMA + hysteresis + cooldown for online alerts

Data convention
---------------
Recommended manifest CSV columns:

    patient_id,label,path[,fs]

Each `path` points to:
- `.npz` file with keys:
    data      -> float array, shape (n_channels, n_samples)
    channels  -> 1D array/list of channel names
    fs        -> sampling rate (optional if provided in manifest)
- OR `.npy` file with shape (n_channels, n_samples), in which case the file is
  assumed to already be ordered according to DEFAULT_CHANNELS.

Labels:
    non-stroke | ischemic | hemorrhagic
or
    0 | 1 | 2   

CLI examples
------------
Train:
    python eeg_stroke_pipeline.py train \
        --manifest manifest.csv \
        --out model.joblib \
        --n-trials 40

Evaluate a saved model on a manifest:
    python eeg_stroke_pipeline.py evaluate \
        --manifest manifest.csv \
        --model model.joblib

Offline inference on one EEG file:
    python eeg_stroke_pipeline.py infer \
        --model model.joblib \
        --input sample.npz
"""
from __future__ import annotations

import argparse
import json
import math
import os
import re
import warnings
from dataclasses import dataclass, field
from fractions import Fraction
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

_MPLCONFIGDIR = Path(__file__).resolve().parent / ".mplconfig"
os.environ.setdefault("MPLCONFIGDIR", str(_MPLCONFIGDIR))
_MPLCONFIGDIR.mkdir(parents=True, exist_ok=True)

import joblib
import numpy as np
import pandas as pd
from scipy import optimize, signal, stats
from scipy.special import softmax
from sklearn.metrics import (
    f1_score,
    log_loss,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import GroupKFold, GroupShuffleSplit

try:
    from sklearn.model_selection import StratifiedGroupKFold  # sklearn >= 1.1
except Exception:  # pragma: no cover
    StratifiedGroupKFold = None

try:
    import lightgbm as lgb
except Exception as exc:  # pragma: no cover
    raise RuntimeError("lightgbm is required for this script.") from exc

try:
    import optuna
    from optuna.samplers import TPESampler
except Exception:  # pragma: no cover
    optuna = None
    TPESampler = None

try:
    from PyEMD import EMD
except Exception:  # pragma: no cover
    EMD = None

EPS = 1e-12
RANDOM_STATE = 42

CLASS_NAMES = ["non-stroke", "ischemic", "hemorrhagic"]
# Only IS (1) and HS (2) trigger alerts in the online pipeline. NS (0) is the
# resting baseline and does not warrant a clinical action, so the alert state
# machine ignores it even if its probability dominates.
ALERTABLE_CLASSES = {1, 2}
LABEL_TO_INT = {
    "non-stroke": 0,
    "nonstroke": 0,
    "normal": 0,
    "0": 0,
    0: 0,
    "ischemic": 1,
    "is": 1,
    "infarction": 1,
    "cerebral infarction": 1,
    "1": 1,
    1: 1,
    "hemorrhagic": 2,
    "hs": 2,
    "hemorrhage": 2,
    "cerebral hemorrhage": 2,
    "2": 2,
    2: 2,
}

DEFAULT_CHANNELS = [
    "C3", "C4", "CZ", "F3", "F4", "F7", "F8", "FZ",
    "FP1", "FP2", "O1", "O2", "P3", "P4", "T3", "T4", "T5", "T6"
]

CHANNEL_ALIASES = {
    "T7": "T3",
    "T8": "T4",
    "P7": "T5",
    "P8": "T6",
}

HOMOLOGOUS_PAIRS = [
    ("FP1", "FP2"),
    ("F3", "F4"),
    ("F7", "F8"),
    ("C3", "C4"),
    ("P3", "P4"),
    ("O1", "O2"),
    ("T3", "T4"),
    ("T5", "T6"),
]

REGION_MAP = {
    "frontal_left": ["FP1", "F3", "F7"],
    "frontal_right": ["FP2", "F4", "F8"],
    "central_left": ["C3"],
    "central_right": ["C4"],
    "posterior_left": ["P3", "O1", "T5"],
    "posterior_right": ["P4", "O2", "T6"],
}

MFDFA_SUMMARY_FEATURES = [
    "hq_max",
    "tauq_min",
    "a1",
    "a2",
    "delta_alpha",
    "h2",
    "alpha0",
    "width_left",
    "width_right",
    "asymmetry_alpha",
]

SQI_FEATURES = [
    "sqi_total",
    "sqi_flatline",
    "sqi_clip",
    "sqi_line_ratio",
    "sqi_hf_ratio",
]

ENTROPY_FEATURES = (
    [f"apen_{ch}" for ch in DEFAULT_CHANNELS]
    + [f"fuen_{ch}" for ch in DEFAULT_CHANNELS]
    + [f"apen_asym_{l}_{r}" for l, r in HOMOLOGOUS_PAIRS]
    + [f"fuen_asym_{l}_{r}" for l, r in HOMOLOGOUS_PAIRS]
    + [f"apfu_absdiff_{l}_{r}" for l, r in HOMOLOGOUS_PAIRS]
)

MFDFA_FEATURES = [
    f"{region}_{feat}"
    for region in REGION_MAP
    for feat in MFDFA_SUMMARY_FEATURES
]

ALL_FEATURES = ENTROPY_FEATURES + MFDFA_FEATURES + SQI_FEATURES


@dataclass
class PipelineConfig:
    fs: float = 256.0
    channels: List[str] = field(default_factory=lambda: DEFAULT_CHANNELS.copy())
    auto_resample: bool = True
    impute_missing_channels: bool = True
    clip_artifacts: bool = True
    artifact_clip_mad_factor: float = 9.0
    bandpass_low: float = 1.0
    bandpass_high: float = 35.0
    notch_freq: Optional[float] = 50.0
    notch_q: float = 30.0
    rereference: str = "car"  # common average reference
    entropy_window_sec: float = 1.0
    entropy_step_sec: float = 0.5
    mfdfa_window_sec: float = 4.0
    sqi_threshold: float = 0.55
    drop_low_sqi_windows: bool = True
    entropy_m: int = 2
    entropy_r_factor: float = 0.2
    fuzzy_n: int = 2
    mfdfa_variant: str = "mfdfa"  # "mfdfa" or "mfdfai"
    mfdfa_q: Tuple[int, ...] = (-5, -4, -3, -2, -1, 1, 2, 3, 4, 5)
    mfdfa_order: int = 1
    mfdfa_scale_min: int = 16
    mfdfa_scale_count: int = 8
    n_outer_folds: int = 5
    n_inner_folds: int = 4
    n_trials: int = 40
    calibration_fraction: float = 0.2
    validation_fraction_within_train: float = 0.15
    ema_beta: float = 0.35
    theta_high: float = 0.80
    theta_low: float = 0.60
    enter_k: int = 2
    exit_m: int = 3
    cooldown_sec: float = 15.0
    high_freq_band: Tuple[float, float] = (35.0, 70.0)

    def to_json_dict(self) -> Dict[str, Any]:
        data = self.__dict__.copy()
        data["channels"] = list(self.channels)
        data["mfdfa_q"] = list(self.mfdfa_q)
        data["high_freq_band"] = list(self.high_freq_band)
        return data


@dataclass
class EEGRecord:
    patient_id: str
    label: int
    data: np.ndarray
    channels: List[str]
    fs: float


class TemperatureScaler:
    """Simple multiclass temperature scaling on probability outputs."""

    def __init__(self) -> None:
        self.temperature_: float = 1.0
        self.fitted_: bool = False

    def fit(self, probs: np.ndarray, y_true: np.ndarray) -> "TemperatureScaler":
        probs = np.clip(np.asarray(probs, dtype=float), EPS, 1.0 - EPS)
        y_true = np.asarray(y_true, dtype=int)
        log_probs = np.log(probs)

        def objective(log_t: float) -> float:
            t = float(np.exp(log_t))
            scaled = softmax(log_probs / t, axis=1)
            return float(log_loss(y_true, scaled, labels=np.arange(probs.shape[1])))

        result = optimize.minimize_scalar(objective, bounds=(-3.0, 3.0), method="bounded")
        if result.success:
            self.temperature_ = float(np.exp(result.x))
        else:
            self.temperature_ = 1.0
        self.fitted_ = True
        return self

    def predict_proba(self, probs: np.ndarray) -> np.ndarray:
        probs = np.clip(np.asarray(probs, dtype=float), EPS, 1.0 - EPS)
        if not self.fitted_:
            return probs
        return softmax(np.log(probs) / self.temperature_, axis=1)


@dataclass
class TrainedStrokeModel:
    model: Any
    calibrator: Optional[TemperatureScaler]
    feature_names: List[str]
    config: Dict[str, Any]
    channels: List[str]
    fs: float

    def predict_proba_from_feature_frame(self, frame: pd.DataFrame) -> np.ndarray:
        X = frame.loc[:, self.feature_names].astype(float, copy=False)
        raw = self.model.predict_proba(X)
        if self.calibrator is None:
            return raw
        return self.calibrator.predict_proba(raw)

    def predict_proba_from_features(self, feature_dict: Mapping[str, float]) -> np.ndarray:
        row = pd.DataFrame([{name: feature_dict.get(name, np.nan) for name in self.feature_names}])
        return self.predict_proba_from_feature_frame(row)[0]

    def save(self, path: str | Path) -> None:
        joblib.dump(self, path)

    @staticmethod
    def load(path: str | Path) -> "TrainedStrokeModel":
        obj = joblib.load(path)
        if not isinstance(obj, TrainedStrokeModel):
            raise TypeError("Loaded object is not a TrainedStrokeModel.")
        return obj


class OnlineEEGPreprocessor:
    """Causal preprocessor for streaming use."""

    def __init__(self, n_channels: int, fs: float, config: PipelineConfig) -> None:
        self.n_channels = n_channels
        self.fs = fs
        self.config = config
        self.sos = _build_filter_sos(fs, config, include_bandpass=True)
        self.zi = [signal.sosfilt_zi(self.sos) * 0.0 for _ in range(n_channels)]

    def transform(self, chunk: np.ndarray) -> np.ndarray:
        chunk = np.asarray(chunk, dtype=float)
        if chunk.shape[0] != self.n_channels:
            raise ValueError("Chunk channel count mismatch.")
        if self.config.impute_missing_channels:
            chunk = fill_nan_channels(chunk)
        if self.config.clip_artifacts:
            chunk = clip_channel_outliers(chunk, self.config.artifact_clip_mad_factor)
        out = np.empty_like(chunk)
        for ch in range(self.n_channels):
            filtered, self.zi[ch] = signal.sosfilt(self.sos, chunk[ch], zi=self.zi[ch])
            out[ch] = filtered
        if self.config.rereference.lower() == "car":
            out = out - out.mean(axis=0, keepdims=True)
        return out


class RealTimeStrokeDetector:
    """Streaming inference with SQI gating, EMA, hysteresis and cooldown."""

    def __init__(
        self,
        trained_model: TrainedStrokeModel,
        config: Optional[PipelineConfig] = None,
        preprocess_online: bool = True,
    ) -> None:
        self.model = trained_model
        self.config = config or PipelineConfig(**trained_model.config)
        self.fs = self.config.fs
        self.channels = self.config.channels
        self.entropy_len = int(round(self.config.entropy_window_sec * self.fs))
        self.mfdfa_len = int(round(self.config.mfdfa_window_sec * self.fs))
        self.step_len = int(round(self.config.entropy_step_sec * self.fs))
        self.buffer = np.zeros((len(self.channels), 0), dtype=float)
        self.total_samples = 0
        self.next_emit_sample = self.mfdfa_len
        self.smooth_probs: Optional[np.ndarray] = None
        self.current_alert: Optional[int] = None
        self.high_counts = np.zeros(len(CLASS_NAMES), dtype=int)
        self.low_counts = np.zeros(len(CLASS_NAMES), dtype=int)
        self.last_alert_sample = -10**12
        self.last_alert_class: Optional[int] = None
        self.preprocessor = (
            OnlineEEGPreprocessor(len(self.channels), self.fs, self.config)
            if preprocess_online else None
        )

    def update(self, chunk: np.ndarray) -> List[Dict[str, Any]]:
        chunk = np.asarray(chunk, dtype=float)
        if self.preprocessor is not None:
            chunk = self.preprocessor.transform(chunk)
        self.buffer = np.concatenate([self.buffer, chunk], axis=1)
        self.total_samples += chunk.shape[1]

        keep = self.mfdfa_len + 2 * self.step_len
        if self.buffer.shape[1] > keep:
            self.buffer = self.buffer[:, -keep:]

        events: List[Dict[str, Any]] = []
        while self.total_samples >= self.next_emit_sample:
            lag = self.total_samples - self.next_emit_sample
            end_rel = self.buffer.shape[1] - lag
            if end_rel < self.mfdfa_len:
                break

            entropy_window = self.buffer[:, end_rel - self.entropy_len : end_rel]
            mfdfa_window = self.buffer[:, end_rel - self.mfdfa_len : end_rel]
            feats = build_feature_row_from_windows(
                entropy_window=entropy_window,
                mfdfa_window=mfdfa_window,
                channels=self.channels,
                fs=self.fs,
                config=self.config,
            )
            t_sec = self.next_emit_sample / self.fs
            event = self._infer_from_feature_dict(feats, timestamp_sec=t_sec)
            events.append(event)
            self.next_emit_sample += self.step_len
        return events

    def _infer_from_feature_dict(self, feats: Mapping[str, float], timestamp_sec: float) -> Dict[str, Any]:
        sqi = float(feats["sqi_total"])
        result: Dict[str, Any] = {
            "timestamp_sec": timestamp_sec,
            "sqi_total": sqi,
            "status": "monitor",
            "predicted_class": None,
            "probabilities_raw": None,
            "probabilities_smooth": None,
            "alert_class": self.current_alert,
        }

        if sqi < self.config.sqi_threshold:
            result["status"] = "no-decision"
            return result

        probs = self.model.predict_proba_from_features(feats)
        if self.smooth_probs is None:
            smooth = probs.copy()
        else:
            beta = self.config.ema_beta
            smooth = beta * probs + (1.0 - beta) * self.smooth_probs
        self.smooth_probs = smooth

        pred_class = int(np.argmax(smooth))
        result["predicted_class"] = CLASS_NAMES[pred_class]
        result["probabilities_raw"] = probs.tolist()
        result["probabilities_smooth"] = smooth.tolist()

        cooldown_samples = int(round(self.config.cooldown_sec * self.fs))
        cooldown_active = (self.next_emit_sample - self.last_alert_sample) < cooldown_samples

        # NS (class 0) is the resting baseline; even if argmax picks it, the
        # online pipeline must not enter an alert. Only IS/HS trigger alerts.
        is_alertable = pred_class in ALERTABLE_CLASSES

        if self.current_alert is None:
            if (
                is_alertable
                and smooth[pred_class] >= self.config.theta_high
                and not (cooldown_active and self.last_alert_class == pred_class)
            ):
                self.high_counts[np.arange(len(CLASS_NAMES)) != pred_class] = 0
                self.high_counts[pred_class] += 1
            else:
                self.high_counts[:] = 0
            if is_alertable and self.high_counts[pred_class] >= self.config.enter_k:
                self.current_alert = pred_class
                self.last_alert_sample = self.next_emit_sample
                self.last_alert_class = pred_class
                result["status"] = "alert-enter"
                result["alert_class"] = CLASS_NAMES[pred_class]
            else:
                result["status"] = "monitor"
            return result

        active = self.current_alert
        if smooth[active] < self.config.theta_low:
            self.low_counts[active] += 1
        else:
            self.low_counts[active] = 0

        if self.low_counts[active] >= self.config.exit_m:
            result["status"] = "alert-exit"
            result["alert_class"] = CLASS_NAMES[active]
            self.current_alert = None
            self.low_counts[:] = 0
            self.high_counts[:] = 0
        else:
            # Allow class switch only when the new winner is also alertable
            # (IS<->HS), preventing transitions to NS from being escalated.
            if (
                is_alertable
                and pred_class != active
                and smooth[pred_class] >= self.config.theta_high
            ):
                self.high_counts[np.arange(len(CLASS_NAMES)) != pred_class] = 0
                self.high_counts[pred_class] += 1
                if self.high_counts[pred_class] >= self.config.enter_k:
                    self.current_alert = pred_class
                    self.last_alert_sample = self.next_emit_sample
                    self.last_alert_class = pred_class
                    self.high_counts[:] = 0
                    self.low_counts[:] = 0
                    result["status"] = "alert-switch"
                    result["alert_class"] = CLASS_NAMES[pred_class]
                else:
                    result["status"] = "alert-hold"
                    result["alert_class"] = CLASS_NAMES[active]
            else:
                self.high_counts[:] = 0
                result["status"] = "alert-hold"
                result["alert_class"] = CLASS_NAMES[active]
        return result


def parse_label(value: Any) -> int:
    key = str(value).strip().lower()
    if value in LABEL_TO_INT:
        return int(LABEL_TO_INT[value])
    if key in LABEL_TO_INT:
        return int(LABEL_TO_INT[key])
    raise ValueError(f"Unknown label: {value!r}")


def canonicalize_channel_name(name: Any) -> str:
    text = str(name).strip().upper()
    text = re.sub(r"^(EEG|EKG|ECG)\s+", "", text)
    text = re.sub(r"[\s._]", "", text)
    text = re.sub(r"(-REF|-LE|REF|LE)$", "", text)
    return CHANNEL_ALIASES.get(text, text)


def load_array_file(path: str | Path) -> Tuple[np.ndarray, List[str], Optional[float]]:
    path = Path(path)
    if path.suffix.lower() == ".npz":
        obj = np.load(path, allow_pickle=True)
        if "data" not in obj:
            raise ValueError(f"{path} must contain key 'data'.")
        data = np.asarray(obj["data"], dtype=float)
        channels = obj["channels"].tolist() if "channels" in obj else DEFAULT_CHANNELS.copy()
        fs = float(obj["fs"]) if "fs" in obj else None
        return data, [str(ch) for ch in channels], fs
    if path.suffix.lower() == ".npy":
        data = np.load(path)
        return np.asarray(data, dtype=float), DEFAULT_CHANNELS.copy(), None
    raise ValueError(f"Unsupported file type: {path.suffix}")


def reorder_to_target_channels(
    data: np.ndarray,
    input_channels: Sequence[str],
    target_channels: Sequence[str],
) -> np.ndarray:
    idx = {canonicalize_channel_name(ch): i for i, ch in enumerate(input_channels)}
    ordered = []
    missing = []
    for ch in target_channels:
        i = idx.get(canonicalize_channel_name(ch))
        if i is None:
            missing.append(ch)
            ordered.append(np.full(data.shape[1], np.nan))
        else:
            ordered.append(np.asarray(data[i], dtype=float))
    if missing:
        warnings.warn(f"Missing channels inserted as NaN placeholders for later preprocessing: {missing}")
    return np.vstack(ordered)


def fill_nan_channels(data: np.ndarray) -> np.ndarray:
    x = np.asarray(data, dtype=float).copy()
    if x.ndim != 2:
        raise ValueError(f"Expected 2D EEG array, got shape {x.shape}.")

    sample_fill = np.nanmedian(x, axis=0)
    sample_fill = np.where(np.isfinite(sample_fill), sample_fill, 0.0)

    for ch in range(x.shape[0]):
        row = x[ch]
        finite = np.isfinite(row)
        if finite.all():
            continue
        if not np.any(finite):
            x[ch] = sample_fill
            continue

        idx = np.flatnonzero(finite)
        missing_idx = np.flatnonzero(~finite)
        x[ch, missing_idx] = np.interp(missing_idx, idx, row[idx])

    invalid = ~np.isfinite(x)
    if np.any(invalid):
        x[invalid] = np.broadcast_to(sample_fill, x.shape)[invalid]
    x = np.nan_to_num(x, nan=0.0, posinf=0.0, neginf=0.0)
    return x


def clip_channel_outliers(data: np.ndarray, mad_factor: float) -> np.ndarray:
    x = np.asarray(data, dtype=float).copy()
    median = np.median(x, axis=1, keepdims=True)
    mad = np.median(np.abs(x - median), axis=1, keepdims=True)
    robust_sigma = np.maximum(1.4826 * mad, EPS)
    lower = median - mad_factor * robust_sigma
    upper = median + mad_factor * robust_sigma
    return np.clip(x, lower, upper)


def resample_eeg(data: np.ndarray, orig_fs: float, target_fs: float) -> np.ndarray:
    if orig_fs <= 0 or target_fs <= 0:
        raise ValueError(f"Sampling rates must be positive, got {orig_fs} and {target_fs}.")
    if abs(float(orig_fs) - float(target_fs)) <= 1e-6:
        return np.asarray(data, dtype=float)

    ratio = Fraction(float(target_fs) / float(orig_fs)).limit_denominator(1000)
    return signal.resample_poly(np.asarray(data, dtype=float), ratio.numerator, ratio.denominator, axis=1)


def load_records_from_manifest(
    manifest_path: str | Path,
    config: Optional[PipelineConfig] = None,
) -> List[EEGRecord]:
    cfg = config or PipelineConfig()
    manifest_path = Path(manifest_path)
    manifest_dir = manifest_path.resolve().parent
    df = pd.read_csv(manifest_path)
    required = {"patient_id", "label", "path"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Manifest is missing columns: {missing}")
    records: List[EEGRecord] = []
    for row in df.to_dict(orient="records"):
        data_path = Path(str(row["path"]))
        if not data_path.is_absolute():
            data_path = manifest_dir / data_path
        data, channels, fs_in_file = load_array_file(data_path)
        fs = float(row["fs"]) if "fs" in row and pd.notna(row["fs"]) else fs_in_file or cfg.fs
        ordered = reorder_to_target_channels(data, channels, cfg.channels)
        records.append(
            EEGRecord(
                patient_id=str(row["patient_id"]),
                label=parse_label(row["label"]),
                data=ordered,
                channels=list(cfg.channels),
                fs=float(fs),
            )
        )
    return records


def _build_filter_sos(fs: float, config: PipelineConfig, include_bandpass: bool = True) -> np.ndarray:
    """Build cascaded SOS for notch + (optional) bandpass.

    Used by both batch and streaming preprocessing to guarantee identical
    filter behavior between train and inference (causal sosfilt).
    """
    sos_sections = []
    if config.notch_freq is not None and 0 < config.notch_freq < fs / 2:
        b, a = signal.iirnotch(w0=config.notch_freq, Q=config.notch_q, fs=fs)
        sos_sections.append(signal.tf2sos(b, a))
    if include_bandpass:
        bp = signal.butter(
            N=4,
            Wn=[config.bandpass_low, config.bandpass_high],
            btype="bandpass",
            fs=fs,
            output="sos",
        )
        sos_sections.append(bp)
    if not sos_sections:
        return np.array([[1, 0, 0, 1, 0, 0]], dtype=float)
    return np.concatenate(sos_sections, axis=0)


def _apply_causal_sos(x: np.ndarray, sos: np.ndarray) -> np.ndarray:
    """Apply cascaded SOS causally, channel-wise, with zero initial state.

    Identical behavior to OnlineEEGPreprocessor (which initializes zi to zero)
    so train-time features match inference-time features exactly.
    """
    out = np.empty_like(x)
    for ch in range(x.shape[0]):
        zi = signal.sosfilt_zi(sos) * 0.0
        out[ch], _ = signal.sosfilt(sos, x[ch], zi=zi)
    return out


def preprocess_eeg(data: np.ndarray, fs: float, config: PipelineConfig) -> np.ndarray:
    """Batch preprocessing using CAUSAL filtering.

    Pipeline matches OnlineEEGPreprocessor exactly so train/inference features
    have identical distributions (no zero-phase vs causal mismatch).
    """
    x = np.asarray(data, dtype=float)
    if x.ndim != 2:
        raise ValueError(f"Expected 2D EEG array, got shape {x.shape}.")
    if config.impute_missing_channels:
        x = fill_nan_channels(x)
    if config.auto_resample and abs(float(fs) - float(config.fs)) > 1e-6:
        x = resample_eeg(x, fs, config.fs)
        fs = config.fs
    elif abs(float(fs) - float(config.fs)) > 1e-6:
        raise ValueError(
            f"Sampling rate mismatch: {fs} vs expected {config.fs}. "
            "Enable auto_resample or resample beforehand."
        )
    if config.clip_artifacts:
        x = clip_channel_outliers(x, config.artifact_clip_mad_factor)
    x = signal.detrend(x, axis=1, type="linear")
    sos = _build_filter_sos(fs, config, include_bandpass=True)
    x = _apply_causal_sos(x, sos)
    if config.rereference.lower() == "car":
        x = x - np.mean(x, axis=0, keepdims=True)
    return x


def preprocess_eeg_for_sqi(data: np.ndarray, fs: float, config: PipelineConfig) -> np.ndarray:
    """Preprocessing for SQI features. Skips bandpass + CAR to keep 35-70 Hz band.

    Notch is applied causally to match training pipeline.
    """
    x = np.asarray(data, dtype=float)
    if x.ndim != 2:
        raise ValueError(f"Expected 2D EEG array, got shape {x.shape}.")
    if config.impute_missing_channels:
        x = fill_nan_channels(x)
    if config.auto_resample and abs(float(fs) - float(config.fs)) > 1e-6:
        x = resample_eeg(x, fs, config.fs)
        fs = config.fs
    if config.clip_artifacts:
        x = clip_channel_outliers(x, config.artifact_clip_mad_factor)
    x = signal.detrend(x, axis=1, type="linear")
    sos = _build_filter_sos(fs, config, include_bandpass=False)
    x = _apply_causal_sos(x, sos)
    return x


def embed_sequence(x: np.ndarray, m: int) -> np.ndarray:
    x = np.asarray(x, dtype=float)
    n = x.size
    if n <= m:
        raise ValueError("Sequence too short for embedding.")
    return np.stack([x[i : i + m] for i in range(n - m + 1)], axis=0)


def chebyshev_pairwise(emb: np.ndarray) -> np.ndarray:
    diff = np.abs(emb[:, None, :] - emb[None, :, :])
    return diff.max(axis=2)


def approximate_entropy(x: np.ndarray, m: int = 2, r_factor: float = 0.2) -> float:
    x = np.asarray(x, dtype=float)
    x = x[np.isfinite(x)]
    if x.size < m + 2:
        return np.nan
    r = r_factor * np.nanstd(x)
    if r <= 0:
        return 0.0

    def _phi(mm: int) -> float:
        emb = embed_sequence(x, mm)
        dist = chebyshev_pairwise(emb)
        c = np.mean(dist <= r, axis=1)
        return float(np.mean(np.log(c + EPS)))

    return _phi(m) - _phi(m + 1)


def fuzzy_entropy(
    x: np.ndarray,
    m: int = 2,
    r_factor: float = 0.2,
    n_power: int = 2,
) -> float:
    x = np.asarray(x, dtype=float)
    x = x[np.isfinite(x)]
    if x.size < m + 2:
        return np.nan
    r = r_factor * np.nanstd(x)
    if r <= 0:
        return 0.0

    def _phi(mm: int) -> float:
        emb = embed_sequence(x, mm)
        emb = emb - emb.mean(axis=1, keepdims=True)
        dist = chebyshev_pairwise(emb)
        np.fill_diagonal(dist, np.nan)
        sim = np.exp(-np.log(2.0) * (dist / r) ** n_power)
        return float(np.nanmean(np.nanmean(sim, axis=1)))

    phi_m = _phi(m)
    phi_m1 = _phi(m + 1)
    return float(np.log(phi_m + EPS) - np.log(phi_m1 + EPS))


def compute_welch_bandpower(
    x: np.ndarray,
    fs: float,
    band: Tuple[float, float],
) -> np.ndarray:
    x = np.asarray(x, dtype=float)
    nperseg = min(x.shape[1], int(round(fs)))
    freqs, psd = signal.welch(x, fs=fs, axis=1, nperseg=max(32, nperseg))
    mask = (freqs >= band[0]) & (freqs <= band[1])
    if not np.any(mask):
        return np.zeros(x.shape[0], dtype=float)
    return np.trapezoid(psd[:, mask], freqs[mask], axis=1)


def compute_sqi(window: np.ndarray, fs: float, config: PipelineConfig) -> Dict[str, float]:
    window = np.asarray(window, dtype=float)
    stds = np.nanstd(window, axis=1)
    flatline_ratio = float(np.mean(stds < 1e-6))

    robust_scale = np.nanmedian(np.abs(window - np.nanmedian(window, axis=1, keepdims=True)))
    clip_threshold = 8.0 * robust_scale + EPS
    clip_ratio = float(np.mean(np.abs(window) > clip_threshold))

    line_band = (max(config.notch_freq - 1.0, 0.1), min(config.notch_freq + 1.0, fs / 2 - EPS)) if config.notch_freq else (49.0, 51.0)
    broadband = (1.0, min(35.0, fs / 2 - EPS))
    hf_band = (config.high_freq_band[0], min(config.high_freq_band[1], fs / 2 - EPS))
    line_ratio = float(np.median((compute_welch_bandpower(window, fs, line_band) + EPS) / (compute_welch_bandpower(window, fs, broadband) + EPS)))
    hf_ratio = float(np.median((compute_welch_bandpower(window, fs, hf_band) + EPS) / (compute_welch_bandpower(window, fs, broadband) + EPS)))

    penalties = (
        0.45 * np.clip(flatline_ratio / 0.2, 0.0, 1.0)
        + 0.20 * np.clip(clip_ratio / 0.05, 0.0, 1.0)
        + 0.20 * np.clip(line_ratio / 0.25, 0.0, 1.0)
        + 0.15 * np.clip(hf_ratio / 0.35, 0.0, 1.0)
    )
    total = float(np.clip(1.0 - penalties, 0.0, 1.0))
    return {
        "sqi_total": total,
        "sqi_flatline": flatline_ratio,
        "sqi_clip": clip_ratio,
        "sqi_line_ratio": line_ratio,
        "sqi_hf_ratio": hf_ratio,
    }


def compute_profile(x: np.ndarray) -> np.ndarray:
    x = np.asarray(x, dtype=float)
    x = x[np.isfinite(x)]
    return np.cumsum(x - np.mean(x))


def _mfdfa_from_profile(
    profile: np.ndarray,
    q_values: Sequence[int],
    order: int = 1,
    scale_min: int = 16,
    scale_count: int = 8,
) -> Dict[str, np.ndarray]:
    profile = np.asarray(profile, dtype=float)
    n = profile.size
    if n < max(64, 4 * scale_min):
        raise ValueError("Signal too short for stable MFDFA.")
    # Ihlen (2012): scale_max <= N/10 to ensure >= 10 segments per scale,
    # giving stable variance estimates of h(q). Using N/4 (3-4 segments) yields
    # high-variance, biased h(q) estimates and was a common pitfall in MFDFA.
    scale_max = max(scale_min + 2, n // 10)
    scales = np.unique(np.floor(np.geomspace(scale_min, scale_max, num=scale_count)).astype(int))
    scales = scales[(scales > order + 2) & (scales < n // 2)]
    if scales.size < 4:
        raise ValueError("Not enough valid scales for MFDFA.")

    q_values = np.asarray(q_values, dtype=float)
    fluct = []
    valid_scales = []

    for s in scales:
        ns = n // s
        if ns < 2:
            continue
        vars_ = []
        t = np.arange(s, dtype=float)
        for v in range(ns):
            seg = profile[v * s : (v + 1) * s]
            coeff = np.polyfit(t, seg, order)
            trend = np.polyval(coeff, t)
            vars_.append(np.mean((seg - trend) ** 2))
        for v in range(ns):
            start = n - (v + 1) * s
            seg = profile[start : start + s]
            coeff = np.polyfit(t, seg, order)
            trend = np.polyval(coeff, t)
            vars_.append(np.mean((seg - trend) ** 2))
        vars_ = np.maximum(np.asarray(vars_, dtype=float), EPS)

        Fqs = []
        for q in q_values:
            Fqs.append((np.mean(vars_ ** (q / 2.0))) ** (1.0 / q))
        fluct.append(Fqs)
        valid_scales.append(s)

    fluct = np.asarray(fluct, dtype=float)
    valid_scales = np.asarray(valid_scales, dtype=float)
    if fluct.shape[0] < 4:
        raise ValueError("MFDFA failed: insufficient scales after filtering.")

    log_s = np.log2(valid_scales)
    log_f = np.log2(np.maximum(fluct, EPS))
    hq = np.array([np.polyfit(log_s, log_f[:, i], 1)[0] for i in range(log_f.shape[1])], dtype=float)
    tau = q_values * hq - 1.0
    alpha = np.gradient(tau, q_values)
    f_alpha = q_values * alpha - tau

    return {
        "q": q_values,
        "scales": valid_scales,
        "hq": hq,
        "tau": tau,
        "alpha": alpha,
        "f_alpha": f_alpha,
    }


def summarize_mfdfa_spectrum(spec: Mapping[str, np.ndarray]) -> Dict[str, float]:
    q = np.asarray(spec["q"], dtype=float)
    hq = np.asarray(spec["hq"], dtype=float)
    tau = np.asarray(spec["tau"], dtype=float)
    alpha = np.asarray(spec["alpha"], dtype=float)
    f_alpha = np.asarray(spec["f_alpha"], dtype=float)

    alpha_min = float(np.min(alpha))
    alpha_max = float(np.max(alpha))
    alpha0 = float(alpha[np.argmax(f_alpha)])
    width_left = alpha0 - alpha_min
    width_right = alpha_max - alpha0

    def interp_at(xq: float, x: np.ndarray, y: np.ndarray) -> float:
        return float(np.interp(xq, x, y))

    if np.any(np.isclose(q, 2)):
        h2 = float(hq[np.argmin(np.abs(q - 2))])
    else:
        h2 = interp_at(2.0, q, hq)

    a1 = interp_at(-3.0, q, tau) - interp_at(-4.0, q, tau)
    a2 = interp_at(4.0, q, tau) - interp_at(3.0, q, tau)

    return {
        "hq_max": float(np.max(hq)),
        "tauq_min": float(np.min(tau)),
        "a1": float(a1),
        "a2": float(a2),
        "delta_alpha": float(alpha_max - alpha_min),
        "h2": h2,
        "alpha0": alpha0,
        "width_left": float(width_left),
        "width_right": float(width_right),
        "asymmetry_alpha": float(width_left - width_right),
    }


def mfdfa_features(
    x: np.ndarray,
    q_values: Sequence[int],
    order: int,
    scale_min: int,
    scale_count: int,
) -> Dict[str, float]:
    profile = compute_profile(x)
    spec = _mfdfa_from_profile(profile, q_values=q_values, order=order, scale_min=scale_min, scale_count=scale_count)
    return summarize_mfdfa_spectrum(spec)


def mfdfai_features(
    x: np.ndarray,
    q_values: Sequence[int],
    order: int,
    scale_min: int,
    scale_count: int,
) -> Dict[str, float]:
    if EMD is None:
        raise ImportError("PyEMD / EMD-signal is required for mfdfai mode.")
    profile = compute_profile(x)
    emd = EMD()
    imfs = emd.emd(profile)
    if imfs is None or len(imfs) == 0:
        spec = _mfdfa_from_profile(profile, q_values=q_values, order=order, scale_min=scale_min, scale_count=scale_count)
        return summarize_mfdfa_spectrum(spec)

    residue = profile - np.sum(imfs, axis=0)
    corrs = []
    for imf in imfs:
        if np.std(imf) < EPS or np.std(profile) < EPS:
            corrs.append(0.0)
        else:
            corr = np.corrcoef(imf, profile)[0, 1]
            if not np.isfinite(corr):
                corr = 0.0
            corrs.append(abs(float(corr)))
    top_k = min(2, len(corrs))
    top_idx = np.argsort(corrs)[-top_k:]
    trend = np.sum(imfs[top_idx], axis=0) + residue
    detrended_profile = profile - trend
    spec = _mfdfa_from_profile(
        detrended_profile,
        q_values=q_values,
        order=order,
        scale_min=scale_min,
        scale_count=scale_count,
    )
    return summarize_mfdfa_spectrum(spec)


def region_average_signals(window: np.ndarray, channels: Sequence[str]) -> Dict[str, np.ndarray]:
    idx = {ch: i for i, ch in enumerate(channels)}
    signals: Dict[str, np.ndarray] = {}
    for region, chs in REGION_MAP.items():
        available = [idx[ch] for ch in chs if ch in idx]
        if not available:
            signals[region] = np.full(window.shape[1], np.nan)
        else:
            signals[region] = np.nanmean(window[available], axis=0)
    return signals


def extract_entropy_features(
    window: np.ndarray,
    channels: Sequence[str],
    config: PipelineConfig,
) -> Dict[str, float]:
    feats = {name: np.nan for name in ENTROPY_FEATURES}
    apen: Dict[str, float] = {}
    fuen: Dict[str, float] = {}

    for i, ch in enumerate(channels):
        sig = np.asarray(window[i], dtype=float)
        ap = approximate_entropy(sig, m=config.entropy_m, r_factor=config.entropy_r_factor)
        fu = fuzzy_entropy(sig, m=config.entropy_m, r_factor=config.entropy_r_factor, n_power=config.fuzzy_n)
        apen[ch] = ap
        fuen[ch] = fu
        if f"apen_{ch}" in feats:
            feats[f"apen_{ch}"] = float(ap)
        if f"fuen_{ch}" in feats:
            feats[f"fuen_{ch}"] = float(fu)

    for left, right in HOMOLOGOUS_PAIRS:
        ap_l, ap_r = apen.get(left, np.nan), apen.get(right, np.nan)
        fu_l, fu_r = fuen.get(left, np.nan), fuen.get(right, np.nan)
        feats[f"apen_asym_{left}_{right}"] = float(ap_l - ap_r) if np.isfinite(ap_l) and np.isfinite(ap_r) else np.nan
        feats[f"fuen_asym_{left}_{right}"] = float(fu_l - fu_r) if np.isfinite(fu_l) and np.isfinite(fu_r) else np.nan
        if np.isfinite(ap_l) and np.isfinite(ap_r) and np.isfinite(fu_l) and np.isfinite(fu_r):
            feats[f"apfu_absdiff_{left}_{right}"] = float(abs((ap_l + fu_l) - (ap_r + fu_r)))
        else:
            feats[f"apfu_absdiff_{left}_{right}"] = np.nan
    return feats


def extract_mfdfa_features(
    window: np.ndarray,
    channels: Sequence[str],
    config: PipelineConfig,
) -> Dict[str, float]:
    feats = {name: np.nan for name in MFDFA_FEATURES}
    region_signals = region_average_signals(window, channels)
    extractor = mfdfai_features if config.mfdfa_variant.lower() == "mfdfai" else mfdfa_features

    for region, sig in region_signals.items():
        if np.sum(np.isfinite(sig)) < max(64, 4 * config.mfdfa_scale_min):
            continue
        try:
            summary = extractor(
                sig,
                q_values=config.mfdfa_q,
                order=config.mfdfa_order,
                scale_min=config.mfdfa_scale_min,
                scale_count=config.mfdfa_scale_count,
            )
        except Exception:
            continue
        for key, value in summary.items():
            feats[f"{region}_{key}"] = float(value)
    return feats


def build_feature_row_from_windows(
    entropy_window: np.ndarray,
    mfdfa_window: np.ndarray,
    channels: Sequence[str],
    fs: float,
    config: PipelineConfig,
    sqi_window: Optional[np.ndarray] = None,
) -> Dict[str, float]:
    feats: Dict[str, float] = {}
    feats.update(extract_entropy_features(entropy_window, channels, config))
    feats.update(extract_mfdfa_features(mfdfa_window, channels, config))
    sqi_input = sqi_window if sqi_window is not None else entropy_window
    feats.update(compute_sqi(sqi_input, fs, config))
    for name in ALL_FEATURES:
        feats.setdefault(name, np.nan)
    return feats


def validate_sampling_rate(actual_fs: float, expected_fs: float, context: str, auto_resample: bool = True) -> None:
    if abs(float(actual_fs) - float(expected_fs)) <= 1e-6:
        return
    if auto_resample:
        warnings.warn(
            f"Sampling rate mismatch for {context}: {actual_fs} vs expected {expected_fs}. "
            "Preprocessing will resample automatically."
        )
        return
    raise ValueError(
        f"Sampling rate mismatch for {context}: "
        f"{actual_fs} vs expected {expected_fs}. Resample beforehand."
    )


def build_feature_table(
    records: Sequence[EEGRecord],
    config: Optional[PipelineConfig] = None,
) -> pd.DataFrame:
    cfg = config or PipelineConfig()
    rows: List[Dict[str, Any]] = []
    entropy_len = int(round(cfg.entropy_window_sec * cfg.fs))
    mfdfa_len = int(round(cfg.mfdfa_window_sec * cfg.fs))
    step_len = int(round(cfg.entropy_step_sec * cfg.fs))
    min_len = max(entropy_len, mfdfa_len)

    for record in records:
        validate_sampling_rate(record.fs, cfg.fs, f"patient {record.patient_id}", auto_resample=cfg.auto_resample)
        x = preprocess_eeg(record.data, record.fs, cfg)
        x_sqi = preprocess_eeg_for_sqi(record.data, record.fs, cfg)
        fs_used = cfg.fs
        n_samples = x.shape[1]
        for end in range(min_len, n_samples + 1, step_len):
            entropy_window = x[:, end - entropy_len : end]
            mfdfa_window = x[:, end - mfdfa_len : end]
            sqi_window = x_sqi[:, end - entropy_len : end]
            feat = build_feature_row_from_windows(
                entropy_window=entropy_window,
                mfdfa_window=mfdfa_window,
                channels=record.channels,
                fs=fs_used,
                config=cfg,
                sqi_window=sqi_window,
            )
            if cfg.drop_low_sqi_windows and feat["sqi_total"] < cfg.sqi_threshold:
                continue
            feat["patient_id"] = record.patient_id
            feat["label"] = record.label
            feat["t_end_sec"] = end / fs_used
            rows.append(feat)

    if not rows:
        raise RuntimeError("No windows were produced. Check SQI threshold and signal lengths.")
    frame = pd.DataFrame(rows)
    cols = ["patient_id", "label", "t_end_sec"] + ALL_FEATURES
    return frame[cols]


def safe_n_splits(groups: Sequence[Any], desired: int) -> int:
    unique_groups = np.unique(np.asarray(groups))
    return max(2, min(int(desired), len(unique_groups)))


def make_group_splitter(n_splits: int):
    if StratifiedGroupKFold is not None:
        return StratifiedGroupKFold(n_splits=n_splits, shuffle=True, random_state=RANDOM_STATE)
    return GroupKFold(n_splits=n_splits)


def feature_frame_from_table(feature_table: pd.DataFrame, feature_names: Sequence[str]) -> pd.DataFrame:
    return feature_table.loc[:, list(feature_names)].astype(float, copy=False)


def take_rows(X: pd.DataFrame, indices: np.ndarray) -> pd.DataFrame:
    return X.iloc[np.asarray(indices, dtype=int)]


def multiclass_brier_score(y_true: np.ndarray, probs: np.ndarray) -> float:
    y_true = np.asarray(y_true, dtype=int)
    probs = np.asarray(probs, dtype=float)
    y_onehot = np.eye(probs.shape[1])[y_true]
    return float(np.mean(np.sum((probs - y_onehot) ** 2, axis=1)))


def expected_calibration_error(y_true: np.ndarray, probs: np.ndarray, n_bins: int = 15) -> float:
    y_true = np.asarray(y_true, dtype=int)
    probs = np.asarray(probs, dtype=float)
    conf = probs.max(axis=1)
    pred = probs.argmax(axis=1)
    acc = (pred == y_true).astype(float)
    bins = np.linspace(0.0, 1.0, n_bins + 1)
    ece = 0.0
    for i in range(n_bins):
        mask = (conf >= bins[i]) & (conf < bins[i + 1] if i < n_bins - 1 else conf <= bins[i + 1])
        if np.any(mask):
            ece += abs(acc[mask].mean() - conf[mask].mean()) * (mask.mean())
    return float(ece)


def evaluate_probabilities(y_true: np.ndarray, probs: np.ndarray) -> Dict[str, float]:
    y_true = np.asarray(y_true, dtype=int)
    probs = np.asarray(probs, dtype=float)
    pred = np.argmax(probs, axis=1)
    labels = np.arange(len(CLASS_NAMES))
    per_class_recall = recall_score(
        y_true,
        pred,
        labels=labels,
        average=None,
        zero_division=0,
    )
    macro_recall = float(np.mean(per_class_recall))
    metrics = {
        "macro_f1": float(f1_score(y_true, pred, average="macro", labels=labels, zero_division=0)),
        "balanced_accuracy": macro_recall,
        "macro_recall": macro_recall,
        "recall_nonstroke": float(per_class_recall[0]),
        "recall_ischemic": float(per_class_recall[1]),
        "recall_hemorrhagic": float(per_class_recall[2]),
        "brier_multiclass": multiclass_brier_score(y_true, probs),
        "ece": expected_calibration_error(y_true, probs),
        "log_loss": float(log_loss(y_true, probs, labels=np.arange(probs.shape[1]))),
    }
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            metrics["auc_ovr"] = float(roc_auc_score(y_true, probs, multi_class="ovr", labels=np.arange(probs.shape[1])))
    except Exception:
        metrics["auc_ovr"] = np.nan
    return metrics


def aggregate_probabilities_by_patient(
    patient_ids: Sequence[Any],
    y_true: np.ndarray,
    probs: np.ndarray,
) -> Tuple[np.ndarray, np.ndarray]:
    frame = pd.DataFrame(
        {
            "patient_id": np.asarray(patient_ids),
            "label": np.asarray(y_true, dtype=int),
        }
    )
    prob_array = np.asarray(probs, dtype=float)
    prob_cols = []
    for i, class_name in enumerate(CLASS_NAMES):
        col = f"prob_{class_name}"
        frame[col] = prob_array[:, i]
        prob_cols.append(col)

    agg_rows = []
    for patient_id, group in frame.groupby("patient_id", sort=False):
        labels = group["label"].unique()
        if len(labels) != 1:
            raise ValueError(f"Patient {patient_id} has inconsistent labels across windows: {labels}.")
        mean_probs = group[prob_cols].mean(axis=0).to_numpy(dtype=float)
        mean_probs = mean_probs / np.clip(mean_probs.sum(), EPS, None)
        agg_rows.append((int(labels[0]), mean_probs))

    patient_y = np.asarray([row[0] for row in agg_rows], dtype=int)
    patient_probs = np.vstack([row[1] for row in agg_rows]).astype(float)
    return patient_y, patient_probs


def evaluate_probabilities_with_patient_aggregation(
    patient_ids: Sequence[Any],
    y_true: np.ndarray,
    probs: np.ndarray,
) -> Dict[str, float]:
    metrics = evaluate_probabilities(y_true, probs)
    metrics["n_window_eval"] = int(len(y_true))

    patient_y, patient_probs = aggregate_probabilities_by_patient(patient_ids, y_true, probs)
    patient_metrics = evaluate_probabilities(patient_y, patient_probs)
    metrics.update({f"patient_{key}": value for key, value in patient_metrics.items()})
    metrics["n_patient_eval"] = int(len(patient_y))
    return metrics


def suggest_lgbm_params(trial: "optuna.trial.Trial", num_classes: int) -> Dict[str, Any]:
    return {
        "objective": "multiclass",
        "num_class": num_classes,
        "boosting_type": "gbdt",
        "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.2, log=True),
        "n_estimators": trial.suggest_int("n_estimators", 300, 1800),
        "num_leaves": trial.suggest_int("num_leaves", 15, 127),
        "max_depth": trial.suggest_int("max_depth", 3, 10),
        "min_child_samples": trial.suggest_int("min_child_samples", 10, 100),
        "subsample": trial.suggest_float("subsample", 0.6, 1.0),
        "subsample_freq": trial.suggest_int("subsample_freq", 0, 3),
        "colsample_bytree": trial.suggest_float("colsample_bytree", 0.6, 1.0),
        "reg_alpha": trial.suggest_float("reg_alpha", 1e-8, 10.0, log=True),
        "reg_lambda": trial.suggest_float("reg_lambda", 1e-8, 10.0, log=True),
        "class_weight": "balanced",
        "random_state": RANDOM_STATE,
        "n_jobs": 1,
        "verbosity": -1,
    }


def optimize_tpe_lgbm(
    X: pd.DataFrame,
    y: np.ndarray,
    groups: np.ndarray,
    config: PipelineConfig,
) -> Tuple[Dict[str, Any], Optional["optuna.study.Study"]]:
    if optuna is None:
        raise ImportError("optuna is required for TPE optimization. Install with: pip install optuna")

    inner_splits = safe_n_splits(groups, config.n_inner_folds)
    splitter = make_group_splitter(inner_splits)
    sampler = TPESampler(seed=RANDOM_STATE, multivariate=True)

    def objective(trial: "optuna.trial.Trial") -> float:
        params = suggest_lgbm_params(trial, num_classes=len(CLASS_NAMES))
        scores = []
        split_iter = splitter.split(X, y, groups) if StratifiedGroupKFold is not None else splitter.split(X, y, groups)
        for tr_idx, va_idx in split_iter:
            model = lgb.LGBMClassifier(**params)
            X_train = take_rows(X, tr_idx)
            X_valid = take_rows(X, va_idx)
            all_classes_present = (
                len(np.unique(y[tr_idx])) == len(CLASS_NAMES)
                and len(np.unique(y[va_idx])) == len(CLASS_NAMES)
            )
            if all_classes_present:
                model.fit(
                    X_train,
                    y[tr_idx],
                    eval_set=[(X_valid, y[va_idx])],
                    eval_metric="multi_logloss",
                    callbacks=[lgb.early_stopping(50, verbose=False)],
                )
            else:
                model.fit(X_train, y[tr_idx])
            pred = model.predict(X_valid)
            scores.append(f1_score(y[va_idx], pred, average="macro", labels=np.arange(len(CLASS_NAMES)), zero_division=0))
        return float(np.mean(scores))

    study = optuna.create_study(direction="maximize", sampler=sampler)
    study.optimize(objective, n_trials=config.n_trials, show_progress_bar=False)
    best = suggest_lgbm_params(study.best_trial, num_classes=len(CLASS_NAMES))
    return best, study

def group_split_train_calibration(
    groups: np.ndarray,
    fraction: float,
    y: Optional[np.ndarray] = None,
) -> Tuple[np.ndarray, np.ndarray]:
    if len(np.unique(groups)) < 2:
        idx = np.arange(len(groups))
        split = int(max(1, round((1.0 - fraction) * len(idx))))
        return idx[:split], idx[split:]
    gss = GroupShuffleSplit(n_splits=1, test_size=fraction, random_state=RANDOM_STATE)
    dummy_X = np.zeros((len(groups), 1))
    train_idx, calib_idx = next(gss.split(dummy_X, y, groups))
    return np.asarray(train_idx), np.asarray(calib_idx)


def fit_lgbm_with_calibration(
    X: pd.DataFrame,
    y: np.ndarray,
    groups: np.ndarray,
    params: Dict[str, Any],
    config: PipelineConfig,
) -> Tuple[Any, Optional[TemperatureScaler]]:
    train_idx, calib_idx = group_split_train_calibration(groups, config.calibration_fraction, y=y)
    if calib_idx.size < max(6, len(CLASS_NAMES)):
        model = lgb.LGBMClassifier(**params)
        model.fit(X, y)
        return model, None

    base_groups = groups[train_idx]
    subtrain_idx, val_idx = group_split_train_calibration(base_groups, config.validation_fraction_within_train, y=y[train_idx])
    X_train = take_rows(X, train_idx)
    X_subtrain = take_rows(X_train, subtrain_idx)
    y_subtrain = y[train_idx][subtrain_idx]
    X_val = take_rows(X_train, val_idx)
    y_val = y[train_idx][val_idx]

    model = lgb.LGBMClassifier(**params)
    if len(np.unique(y_val)) >= 2:
        model.fit(
            X_subtrain,
            y_subtrain,
            eval_set=[(X_val, y_val)],
                eval_metric="multi_logloss",
                callbacks=[lgb.early_stopping(50, verbose=False)],
        )
    else:
        model.fit(X_train, y[train_idx])

    calib_probs = model.predict_proba(take_rows(X, calib_idx))
    calibrator = TemperatureScaler().fit(calib_probs, y[calib_idx])
    return model, calibrator


def cross_validate_pipeline(
    feature_table: pd.DataFrame,
    config: PipelineConfig,
) -> Dict[str, Any]:
    X = feature_frame_from_table(feature_table, ALL_FEATURES)
    y = feature_table["label"].to_numpy(dtype=int)
    groups = feature_table["patient_id"].to_numpy()

    outer_splits = safe_n_splits(groups, config.n_outer_folds)
    splitter = make_group_splitter(outer_splits)
    fold_metrics = []
    best_params_all = []

    split_iter = splitter.split(X, y, groups) if StratifiedGroupKFold is not None else splitter.split(X, y, groups)
    for fold_id, (tr_idx, te_idx) in enumerate(split_iter, start=1):
        X_train, y_train, g_train = take_rows(X, tr_idx), y[tr_idx], groups[tr_idx]
        X_test, y_test = take_rows(X, te_idx), y[te_idx]

        params, study = optimize_tpe_lgbm(X_train, y_train, g_train, config)
        best_params_all.append(params)

        model, calibrator = fit_lgbm_with_calibration(X_train, y_train, g_train, params, config)
        probs = model.predict_proba(X_test)
        if calibrator is not None:
            probs = calibrator.predict_proba(probs)
        metrics = evaluate_probabilities_with_patient_aggregation(groups[te_idx], y_test, probs)
        metrics["fold"] = fold_id
        metrics["n_test"] = int(len(te_idx))
        fold_metrics.append(metrics)

    metrics_df = pd.DataFrame(fold_metrics)
    summary = metrics_df.mean(numeric_only=True).to_dict()
    summary["fold_metrics"] = fold_metrics
    summary["feature_count"] = len(ALL_FEATURES)
    summary["n_windows"] = int(len(feature_table))
    summary["n_patients"] = int(feature_table["patient_id"].nunique())
    summary["best_params_last_fold"] = best_params_all[-1] if best_params_all else {}
    return summary


def train_final_model(
    feature_table: pd.DataFrame,
    config: PipelineConfig,
) -> Tuple[TrainedStrokeModel, Dict[str, Any]]:
    X = feature_frame_from_table(feature_table, ALL_FEATURES)
    y = feature_table["label"].to_numpy(dtype=int)
    groups = feature_table["patient_id"].to_numpy()

    best_params, study = optimize_tpe_lgbm(X, y, groups, config)
    model, calibrator = fit_lgbm_with_calibration(X, y, groups, best_params, config)

    trained = TrainedStrokeModel(
        model=model,
        calibrator=calibrator,
        feature_names=list(ALL_FEATURES),
        config=config.to_json_dict(),
        channels=list(config.channels),
        fs=config.fs,
    )
    metadata = {
        "best_params": best_params,
        "optuna_best_value": float(study.best_value) if study is not None else None,
        "feature_count": len(ALL_FEATURES),
        "n_windows": int(len(feature_table)),
        "n_patients": int(feature_table["patient_id"].nunique()),
    }
    return trained, metadata


def run_offline_inference(
    trained_model: TrainedStrokeModel,
    record: EEGRecord,
    config: Optional[PipelineConfig] = None,
) -> pd.DataFrame:
    cfg = config or PipelineConfig(**trained_model.config)
    validate_sampling_rate(record.fs, cfg.fs, f"patient {record.patient_id}", auto_resample=cfg.auto_resample)
    x = preprocess_eeg(record.data, record.fs, cfg)
    x_sqi = preprocess_eeg_for_sqi(record.data, record.fs, cfg)
    fs_used = cfg.fs
    entropy_len = int(round(cfg.entropy_window_sec * cfg.fs))
    mfdfa_len = int(round(cfg.mfdfa_window_sec * cfg.fs))
    step_len = int(round(cfg.entropy_step_sec * cfg.fs))
    min_len = max(entropy_len, mfdfa_len)

    rows = []
    smooth = None
    for end in range(min_len, x.shape[1] + 1, step_len):
        entropy_window = x[:, end - entropy_len : end]
        mfdfa_window = x[:, end - mfdfa_len : end]
        sqi_window = x_sqi[:, end - entropy_len : end]
        feats = build_feature_row_from_windows(
            entropy_window, mfdfa_window, record.channels, fs_used, cfg, sqi_window=sqi_window
        )

        row = {"t_end_sec": end / fs_used, **feats}
        if feats["sqi_total"] >= cfg.sqi_threshold:
            probs = trained_model.predict_proba_from_features(feats)
            if smooth is None:
                smooth = probs.copy()
            else:
                smooth = cfg.ema_beta * probs + (1.0 - cfg.ema_beta) * smooth
            row.update({
                "p_nonstroke": probs[0],
                "p_ischemic": probs[1],
                "p_hemorrhagic": probs[2],
                "p_nonstroke_smooth": smooth[0],
                "p_ischemic_smooth": smooth[1],
                "p_hemorrhagic_smooth": smooth[2],
                "pred_class": CLASS_NAMES[int(np.argmax(smooth))],
            })
        else:
            row.update({
                "p_nonstroke": np.nan,
                "p_ischemic": np.nan,
                "p_hemorrhagic": np.nan,
                "p_nonstroke_smooth": np.nan,
                "p_ischemic_smooth": np.nan,
                "p_hemorrhagic_smooth": np.nan,
                "pred_class": "no-decision",
            })
        rows.append(row)
    return pd.DataFrame(rows)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="EEG stroke pipeline: ApFu-MFDFA-TPELGBM-RT")
    sub = parser.add_subparsers(dest="command", required=True)

    p_train = sub.add_parser("train", help="train final model and save it")
    p_train.add_argument("--manifest", required=True)
    p_train.add_argument("--out", required=True)
    p_train.add_argument("--config-json", default=None)
    p_train.add_argument("--n-trials", type=int, default=None)
    p_train.add_argument("--mfdfa-variant", choices=["mfdfa", "mfdfai"], default=None)

    p_cv = sub.add_parser("cv", help="nested group CV on manifest")
    p_cv.add_argument("--manifest", required=True)
    p_cv.add_argument("--config-json", default=None)
    p_cv.add_argument("--n-trials", type=int, default=None)
    p_cv.add_argument("--mfdfa-variant", choices=["mfdfa", "mfdfai"], default=None)

    p_eval = sub.add_parser("evaluate", help="evaluate a saved model on a manifest")
    p_eval.add_argument("--manifest", required=True)
    p_eval.add_argument("--model", required=True)
    p_eval.add_argument("--output-csv", default=None)

    p_infer = sub.add_parser("infer", help="offline inference on one EEG file")
    p_infer.add_argument("--model", required=True)
    p_infer.add_argument("--input", required=True)
    p_infer.add_argument("--patient-id", default="unknown")
    p_infer.add_argument("--label", default="non-stroke")
    p_infer.add_argument("--output-csv", default=None)

    return parser.parse_args()


def load_config(args: argparse.Namespace) -> PipelineConfig:
    cfg = PipelineConfig()
    if getattr(args, "config_json", None):
        with open(args.config_json, "r", encoding="utf-8") as f:
            payload = json.load(f)
        cfg = PipelineConfig(**payload)
    if getattr(args, "n_trials", None) is not None:
        cfg.n_trials = int(args.n_trials)
    if getattr(args, "mfdfa_variant", None) is not None:
        cfg.mfdfa_variant = str(args.mfdfa_variant)
    return cfg


def main() -> None:
    args = parse_args()

    if args.command in {"train", "cv"}:
        config = load_config(args)
        records = load_records_from_manifest(args.manifest, config)
        feature_table = build_feature_table(records, config)

        if args.command == "cv":
            summary = cross_validate_pipeline(feature_table, config)
            print(json.dumps(summary, indent=2))
            return

        trained, metadata = train_final_model(feature_table, config)
        trained.save(args.out)
        print(json.dumps(metadata, indent=2))
        return

    if args.command == "evaluate":
        trained = TrainedStrokeModel.load(args.model)
        config = PipelineConfig(**trained.config)
        records = load_records_from_manifest(args.manifest, config)
        feature_table = build_feature_table(records, config)
        probs = trained.predict_proba_from_feature_frame(feature_table)
        metrics = evaluate_probabilities_with_patient_aggregation(
            feature_table["patient_id"].to_numpy(),
            feature_table["label"].to_numpy(dtype=int),
            probs,
        )
        print(json.dumps(metrics, indent=2))
        if args.output_csv:
            out = feature_table[["patient_id", "label", "t_end_sec"]].copy()
            out["p_nonstroke"] = probs[:, 0]
            out["p_ischemic"] = probs[:, 1]
            out["p_hemorrhagic"] = probs[:, 2]
            out.to_csv(args.output_csv, index=False)
        return

    if args.command == "infer":
        trained = TrainedStrokeModel.load(args.model)
        config = PipelineConfig(**trained.config)
        data, channels, fs_in_file = load_array_file(args.input)
        fs = fs_in_file or config.fs
        record = EEGRecord(
            patient_id=str(args.patient_id),
            label=parse_label(args.label),
            data=reorder_to_target_channels(data, channels, config.channels),
            channels=config.channels,
            fs=float(fs),
        )
        df = run_offline_inference(trained, record, config)
        if args.output_csv:
            df.to_csv(args.output_csv, index=False)
        else:
            print(df[["t_end_sec", "sqi_total", "pred_class", "p_nonstroke_smooth", "p_ischemic_smooth", "p_hemorrhagic_smooth"]].tail(10).to_string(index=False))
        return


if __name__ == "__main__":
    main()
