"""Pure helpers of scripts/study_rating.py (blinded epoch rating and time-to-usable-signal)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent.parent / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import study_rating as R  # noqa: E402


@pytest.mark.unit
def test_epoch_bounds_cover_whole_10s_epochs_only() -> None:
    assert R.epoch_bounds(256 * 25, 256.0) == [(0, 2560), (2560, 5120)]


@pytest.mark.unit
def test_iso_to_epoch_seconds() -> None:
    a = R.iso_seconds("2026-11-17T09:30:00.000Z")
    b = R.iso_seconds("2026-11-17T09:30:12.500Z")
    assert b - a == pytest.approx(12.5)


@pytest.mark.unit
def test_ttu_is_the_start_of_the_first_60s_usable_run_after_trial_start() -> None:
    starts = np.arange(0, 200, 10.0)  # epochs at 0, 10, ..., 190 s of the recording
    usable = np.zeros(starts.size, bool)
    usable[3] = True                  # isolated usable epoch: not enough
    usable[8:14] = True               # 80..140 s: six in a row
    ttu, censored = R.time_to_usable(starts, usable, trial_start=25.0, trial_end=190.0)
    assert (ttu, censored) == (pytest.approx(55.0), False)  # 80 - 25


@pytest.mark.unit
def test_ttu_ignores_epochs_before_trial_start() -> None:
    starts = np.arange(0, 120, 10.0)
    usable = np.ones(starts.size, bool)
    ttu, censored = R.time_to_usable(starts, usable, trial_start=15.0, trial_end=120.0)
    assert ttu == pytest.approx(5.0) and censored is False  # first epoch starting >= 15 s is 20 s


@pytest.mark.unit
def test_ttu_is_censored_at_the_timeout_when_never_usable() -> None:
    starts = np.arange(0, 600, 10.0)
    ttu, censored = R.time_to_usable(starts, np.zeros(starts.size, bool), trial_start=0.0, trial_end=600.0)
    assert (ttu, censored) == (R.TIMEOUT_SEC, True)


@pytest.mark.unit
def test_cohen_kappa() -> None:
    a = np.array([1, 1, 0, 0, 1, 0])
    assert R.cohen_kappa(a, a) == pytest.approx(1.0)
    assert R.cohen_kappa(a, 1 - a) == pytest.approx(-1.0)


@pytest.mark.unit
def test_trials_from_events_pair_start_and_end_markers() -> None:
    events = [
        {"type": "trial_start", "trial": 1, "server_ts": "2026-11-17T09:00:00.000Z", "condition": "B"},
        {"type": "quality", "trial": 1, "server_ts": "2026-11-17T09:00:05.000Z", "condition": "B"},
        {"type": "trial_end", "trial": 1, "server_ts": "2026-11-17T09:03:00.000Z", "condition": "B"},
        {"type": "trial_start", "trial": 2, "server_ts": "2026-11-17T09:10:00.000Z", "condition": "G"},
    ]
    trials = R.trials_from_events(events)
    assert [(t["trial"], t["condition"]) for t in trials] == [(1, "B"), (2, "G")]
    assert trials[0]["end"] - trials[0]["start"] == pytest.approx(180.0)
    assert trials[1]["end"] is None  # no end marker: scored up to the timeout


@pytest.mark.unit
def test_prepare_shuffles_epochs_and_hides_their_source(tmp_path: Path) -> None:
    raw = tmp_path / "raw"
    raw.mkdir()
    for rid in ("aaaa", "bbbb"):
        np.savez(raw / f"{rid}.npz", data=np.zeros((2, 256 * 30), np.float32), fs=np.float64(256.0),
                 channels=np.array(["AF3", "AF4"]))
    out = R.prepare(tmp_path, seed=0, render=False)
    template = (out / "ratings_template.csv").read_text(encoding="utf-8").splitlines()
    key = (out / "epoch_key.csv").read_text(encoding="utf-8").splitlines()
    assert template[0] == "epoch_id,usable,comment" and len(template) == 1 + 6
    assert "aaaa" not in "".join(template) and "bbbb" not in "".join(template)
    assert len(key) == 1 + 6 and key[0] == "epoch_id,raw_id,start_sample"


@pytest.mark.unit
def test_score_end_to_end_on_a_synthetic_study(tmp_path: Path) -> None:
    import csv

    # one 200 s recording that starts at 09:00:00; trial 1 starts 30 s in, ends at 180 s
    (tmp_path / "raw_key.jsonl").write_text(json.dumps({
        "raw_id": "r1", "participant": "P07", "condition": "G", "trial_at_start": 1, "fs": 256.0,
        "channels": ["AF3", "AF4"], "n_samples": 256 * 200, "started_utc": "2026-11-17T09:00:00.000Z",
        "closed_utc": "2026-11-17T09:03:20.000Z", "truncated": False}) + "\n", encoding="utf-8")
    (tmp_path / "P07.jsonl").write_text("\n".join(json.dumps(e) for e in [
        {"type": "trial_start", "trial": 1, "condition": "G", "server_ts": "2026-11-17T09:00:30.000Z"},
        {"type": "trial_end", "trial": 1, "condition": "G", "server_ts": "2026-11-17T09:03:00.000Z"},
    ]) + "\n", encoding="utf-8")
    rating = tmp_path / "rating"
    rating.mkdir()
    usable_from = 70  # epochs starting at 70 s and later are usable -> TTU = 70 - 30 = 40 s
    with open(rating / "epoch_key.csv", "w", newline="", encoding="utf-8") as k, \
            open(tmp_path / "r1.csv", "w", newline="", encoding="utf-8") as r:
        kw, rw = csv.writer(k), csv.writer(r)
        kw.writerow(["epoch_id", "raw_id", "start_sample"])
        rw.writerow(["epoch_id", "usable", "comment"])
        for i, start_sec in enumerate(range(0, 200, 10)):
            kw.writerow([f"e{i}", "r1", start_sec * 256])
            rw.writerow([f"e{i}", int(start_sec >= usable_from), ""])

    res = R.score(tmp_path, tmp_path / "r1.csv", ratings2=tmp_path / "r1.csv")
    assert res["trials"] == [{"participant": "P07", "condition": "G", "trial": 1,
                              "ttu_sec": 40.0, "censored": False, "note": ""}]
    assert res["kappa"] == pytest.approx(1.0)


@pytest.mark.unit
def test_typical_scale_is_the_median_epoch_std_so_a_flat_epoch_stays_flat() -> None:
    rng = np.random.default_rng(1)
    x = rng.standard_normal((1, 256 * 50))
    x[:, : 256 * 10] = 0.0  # first epoch flat (lost contact)
    s = R.typical_scale(x, 256.0)
    assert s[0] == pytest.approx(1.0, rel=0.1)  # not pulled to 0 by the flat epoch
