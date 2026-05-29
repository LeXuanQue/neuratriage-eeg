"""ChannelMapper — map device-specific channels onto the 18-ch pipeline layout.

Spec: NeuraTriage_Backend_Master_Prompt.md §3.2.

Missing target channels are filled with NaN; the pipeline's
impute_missing_channels=True flag (PipelineConfig default) handles imputation
downstream. Channel aliases (T7→T3, T8→T4, P7→T5, P8→T6) are applied via
eeg_stroke_pipeline.canonicalize_channel_name.
"""
from __future__ import annotations

from typing import Dict, List, Tuple

import numpy as np

from eeg_stroke_pipeline import (
    DEFAULT_CHANNELS,
    canonicalize_channel_name,
)


DEVICE_PRESETS: Dict[str, Dict[str, object]] = {
    "brain_life_focus_plus": {
        "channels": ["AF3", "AF4", "T7", "T8"],
        "fs": 256,
        "description": "Brain-Life Focus+ (4 EEG channels, PPG, fNIRS)",
    },
    "full_18ch": {
        "channels": list(DEFAULT_CHANNELS),
        "fs": 256,
        "description": "Full 18-channel EEG cap",
    },
    "custom": {
        "channels": [],
        "fs": 256,
        "description": "Custom — channels supplied at runtime",
    },
}


def map_to_pipeline(
    data: np.ndarray,
    device_channels: List[str],
    fs: float = 256.0,
    target_channels: List[str] | None = None,
) -> Tuple[np.ndarray, List[str]]:
    """Return (data_18ch, target_channel_names).

    Raises ValueError if `data.shape[0] != len(device_channels)`.
    """
    target = list(target_channels or DEFAULT_CHANNELS)
    arr = np.asarray(data, dtype=float)
    if arr.ndim != 2:
        raise ValueError(f"Expected 2-D (channels, samples); got shape {arr.shape}")
    if arr.shape[0] != len(device_channels):
        raise ValueError(
            f"Channel count mismatch: data has {arr.shape[0]} rows but "
            f"device_channels lists {len(device_channels)} names"
        )

    canon_in = [canonicalize_channel_name(ch) for ch in device_channels]
    canon_target = [canonicalize_channel_name(ch) for ch in target]

    idx_map = {name: i for i, name in enumerate(canon_in)}
    n_samples = arr.shape[1]
    rows: List[np.ndarray] = []
    for tch in canon_target:
        if tch in idx_map:
            rows.append(arr[idx_map[tch]])
        else:
            rows.append(np.full(n_samples, np.nan))
    return np.vstack(rows), target


__all__ = ["DEVICE_PRESETS", "map_to_pipeline"]
