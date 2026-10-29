"""Thread-safe singleton for the loaded TrainedStrokeModel.

Wraps eeg_stroke_pipeline.TrainedStrokeModel.load() with the __main__ alias
shim that legacy joblib artifacts require (see api/index.py:301-304).
"""
from __future__ import annotations

import hashlib
import logging
import threading
from pathlib import Path
from typing import Optional

import eeg_stroke_pipeline as pipeline


logger = logging.getLogger("neuratriage.model")


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()[:16]


class ModelManager:
    _instance: Optional["ModelManager"] = None
    _instance_lock = threading.Lock()

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._model: Optional[pipeline.TrainedStrokeModel] = None
        self._model_path: Optional[str] = None
        self._window_model: Optional[object] = None
        self._window_model_path: Optional[str] = None

    def peek_window_model_metadata(self, path: str | Path) -> Optional[dict]:
        """Read-only: the riemann model's metadata for display, or None if absent.

        Uses the cached instance when it is the active one; otherwise loads a
        throwaway copy so asking for info never changes which model is active.
        """
        path_str = str(Path(path))
        if self._window_model is not None and self._window_model_path == path_str:
            return dict(getattr(self._window_model, "metadata", {}) or {})
        if not Path(path_str).is_file():
            return None
        from riemann_model import RiemannStrokeModel

        return dict(RiemannStrokeModel.load(path_str).metadata or {})

    def get_window_model(self, kind: str, path: str | Path) -> Optional[object]:
        """Window-level scorer for the real-time detector, or None for the feature model.

        kind = REALTIME_MODEL setting. A missing riemann model raises instead of
        silently falling back, so the UI never shows one model's output as another's.
        """
        kind = kind.strip().lower()
        if kind == "features":
            return None
        if kind != "riemann":
            raise ValueError(f"Unknown realtime_model {kind!r}; use 'features' or 'riemann'.")
        path_str = str(Path(path))
        with self._lock:
            if self._window_model is not None and self._window_model_path == path_str:
                return self._window_model
            if not Path(path_str).is_file():
                raise RuntimeError(
                    f"realtime_model='riemann' but no riemann model at {path_str}; "
                    "run scripts/train_riemann_model.py or set REALTIME_MODEL=features."
                )
            from riemann_model import RiemannStrokeModel

            self._window_model = RiemannStrokeModel.load(path_str)
            self._window_model_path = path_str
            logger.info("Loaded riemann window model from %s (sha256=%s)", path_str, _sha256_file(Path(path_str)))
            return self._window_model

    @classmethod
    def get(cls) -> "ModelManager":
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    @property
    def is_loaded(self) -> bool:
        return self._model is not None

    @property
    def model_path(self) -> Optional[str]:
        return self._model_path

    def get_model(self) -> pipeline.TrainedStrokeModel:
        if self._model is None:
            from ..envelope import EnvelopeError

            raise EnvelopeError(
                "Model not loaded. Call /api/reload-model or start the app with a valid model path.",
                "MODEL_NOT_LOADED",
                503,
            )
        return self._model

    def load_model(self, path: str | Path) -> pipeline.TrainedStrokeModel:
        path_str = str(Path(path))
        with self._lock:
            self._inject_main_aliases()
            try:
                model = pipeline.TrainedStrokeModel.load(path_str)
            except Exception as exc:
                logger.exception("Failed to load model from %s", path_str)
                raise RuntimeError(f"Failed to load model: {exc}") from exc
            self._model = model
            self._model_path = path_str
            sha256 = _sha256_file(Path(path_str))
            logger.info(
                "Loaded model from %s (features=%d, sha256=%s)",
                path_str,
                len(model.feature_names),
                sha256,
            )
            return model

    def reset(self) -> None:
        """Clear the loaded model under the lock (used before a forced reload)."""
        with self._lock:
            self._model = None
            self._model_path = None

    def auto_load(self, candidates: list[Path]) -> Optional[str]:
        for candidate in candidates:
            if candidate.is_file():
                try:
                    self.load_model(candidate)
                    return str(candidate)
                except Exception:
                    logger.warning("Skipping unloadable candidate: %s", candidate)
                    continue
        logger.warning(
            "No model loaded on startup. Searched: %s",
            [str(c) for c in candidates],
        )
        return None

    @staticmethod
    def _inject_main_aliases() -> None:
        """Mirror api/index.py:301-304 so legacy joblib pickles resolve."""
        import __main__

        for name in ("PipelineConfig", "TemperatureScaler", "TrainedStrokeModel"):
            attr = getattr(pipeline, name, None)
            if attr is not None:
                setattr(__main__, name, attr)


def get_manager() -> ModelManager:
    return ModelManager.get()
