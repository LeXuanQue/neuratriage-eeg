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
        # The device streams 2 monopolar EEG channels, AF3 and AF4 (frontal-polar),
        # recovered from the vendor app (headers 0x24/0x26). AF3/AF4 are not in
        # DEFAULT_CHANNELS, so map_to_pipeline honestly NaN-fills rather than
        # aliasing them onto other electrodes — the live 2-ch path drives SQI /
        # No-Decision only, classification stays on the 18-ch replay path.
        "channels": ["AF3", "AF4"],
        "fs": 256,
        "description": "Brain-Life Focus+ (2 EEG channels AF3, AF4; protocol confirmed via vendor app)",
    },
    "openbci_cyton": {
        # 8 monopolar inputs vs a shared SRB2 reference (earlobe), 250 Hz. Simulated
        # first via app.services.cyton_sim before the real board is wired.
        # 4 homologous pairs (asymmetry/BSI features need both sides). Best a-priori
        # symmetric set on same-rig TUSL (results/cyton_montage/D_sym_fp.json: AUC
        # 0.869, patient AUC 0.840 vs 18-ch 0.858 / 0.750). FP1/FP2 sit on hairless
        # skin (good dry contact) and double as blink/EOG channels for the SQI gate.
        "channels": ["FP1", "FP2", "F3", "F4", "C3", "C4", "T3", "T4"],
        "fs": 250,
        "description": "OpenBCI Cyton (8 EEG channels, ADS1299, stroke-screening montage)",
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
