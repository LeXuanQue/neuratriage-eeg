"""SessionManager — one RealTimeStrokeDetector per active streaming session.

Spec: NeuraTriage_Backend_Master_Prompt.md §3.3.
"""
from __future__ import annotations

import logging
import threading
from typing import Dict, List, Optional

from eeg_stroke_pipeline import (
    DEFAULT_CHANNELS,
    PipelineConfig,
    RealTimeStrokeDetector,
)

from .model_manager import ModelManager


logger = logging.getLogger("neuratriage.sessions")


class SessionManager:
    _instance: Optional["SessionManager"] = None
    _instance_lock = threading.Lock()

    def __init__(self) -> None:
        self._sessions: Dict[str, RealTimeStrokeDetector] = {}
        self._lock = threading.Lock()

    @classmethod
    def get(cls) -> "SessionManager":
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def create_session(
        self,
        session_id: str,
        device_channels: List[str],
        fs: float = 256.0,
        config_overrides: Optional[Dict[str, object]] = None,
    ) -> RealTimeStrokeDetector:
        model = ModelManager.get().get_model()
        cfg_dict = dict(model.config)
        cfg_dict["channels"] = list(DEFAULT_CHANNELS)
        cfg_dict["fs"] = float(fs)
        cfg_dict["impute_missing_channels"] = True
        if config_overrides:
            cfg_dict.update(config_overrides)

        try:
            config = PipelineConfig(**cfg_dict)
        except TypeError:
            allowed = set(PipelineConfig().__dict__.keys())
            filtered = {k: v for k, v in cfg_dict.items() if k in allowed}
            config = PipelineConfig(**filtered)

        detector = RealTimeStrokeDetector(model, config=config, preprocess_online=True)
        with self._lock:
            self._sessions[session_id] = detector
        logger.info(
            "Session %s created (device_channels=%s, fs=%.1f Hz)",
            session_id,
            device_channels,
            fs,
        )
        return detector

    def get_session(self, session_id: str) -> Optional[RealTimeStrokeDetector]:
        return self._sessions.get(session_id)

    def close_session(self, session_id: str) -> bool:
        with self._lock:
            existed = self._sessions.pop(session_id, None) is not None
        if existed:
            logger.info("Session %s closed", session_id)
        return existed

    def list_active_sessions(self) -> List[str]:
        return list(self._sessions.keys())


def get_session_manager() -> SessionManager:
    return SessionManager.get()
