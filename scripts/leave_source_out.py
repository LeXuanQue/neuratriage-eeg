"""Leave-source-out (source-swap) evaluation of stroke-vs-control EEG classifiers.

Every published IS/NS EEG comparison we can build pairs one stroke source with one
control source, so in-source cross-validation cannot tell pathology from recording
setup. With two sources per class we train on one (stroke, control) pair and test on
the OTHER pair, so every test recording comes from a device/site the model never saw:

  stroke : xuanwu (Figshare 21679035, acute IS, ZhenTec, MI task)
           tianjin (figshare 30509165, chronic stroke IS+HS, Neuracle, rest segments)
  control: physionet (eegmmidb rest, BCI2000)   oslo (ds003775 rest, BioSemi)

Models (CPU):
  feat_lgbm    : the deployed entropy+MFDFA features (no SQI) + LightGBM
  riemann      : 18x18 covariance -> tangent space -> logistic regression
  riemann_rc   : same, each subject re-centred on its own mean covariance
  eegnet       : EEGNet (Lawhern et al. 2018) on raw 4 s windows
  eegnet_ea    : EEGNet + per-subject Euclidean Alignment (He & Wu 2019)
Re-centring / EA use only the subject's own unlabelled windows (deployable after a
short calibration), never labels.

Run with the experiment venv on F: (torch, pyriemann):
  F:/eeg_extra/.venv_dl/Scripts/python.exe scripts/leave_source_out.py
"""
from __future__ import annotations

import argparse
import json
import sys
import warnings
from concurrent.futures import ProcessPoolExecutor
from itertools import product
from pathlib import Path

warnings.filterwarnings("ignore")

ROOT = Path(__file__).resolve().parent.parent
_BACKEND = str(ROOT / "backend")
sys.path.insert(0, _BACKEND)

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from sklearn.metrics import roc_auc_score  # noqa: E402

try:
    import torch
    from torch import nn
except ImportError:  # the app venv has no torch; only the EEGNet parts need it
    torch = None
    nn = None

EXTRA = Path("F:/eeg_extra")
CACHE = EXTRA / "cache_lso"
WIN_SEC = 4.0


# ---------------------------------------------------------------- evaluation helpers
def source_swap_splits(stroke: list[str], control: list[str]) -> list[tuple[list[str], list[str]]]:
    """Train on one (stroke, control) pair, test on the disjoint remaining pair."""
    splits = []
    for s, c in product(stroke, control):
        s_test = [x for x in stroke if x != s]
        c_test = [x for x in control if x != c]
        for st, ct in product(s_test, c_test):
            splits.append(([s, c], [st, ct]))
    return splits


def patient_level_auc(pids: np.ndarray, y: np.ndarray, prob: np.ndarray) -> float:
    df = pd.DataFrame({"p": pids, "y": y, "prob": prob}).groupby("p").agg(y=("y", "first"), prob=("prob", "mean"))
    return float(roc_auc_score(df["y"], df["prob"])) if df["y"].nunique() == 2 else float("nan")


def slice_fraction(x: np.ndarray, frac: tuple[float, float]) -> np.ndarray:
    """Keep the [frac0, frac1) fraction of a recording along time (e.g. one PhysioNet run)."""
    n = x.shape[1]
    return x[:, int(round(frac[0] * n)):int(round(frac[1] * n))]


def filter_min_age(manifest: pd.DataFrame, participants: pd.DataFrame, min_age: float) -> pd.DataFrame:
    """Oslo control subjects at least `min_age` old (os-XXX <-> sub-XXX)."""
    ages = dict(zip(participants["participant_id"].str.replace("sub-", "os-", regex=False), participants["age"]))
    keep = manifest["patient_id"].map(lambda p: ages.get(p, -1) >= min_age)
    return manifest[keep].reset_index(drop=True)


def to_microvolts(x: np.ndarray) -> np.ndarray:
    """Bring a recording to microvolts. Sources are stored in V (xuanwu, physionet) or uV
    (tianjin, oslo); scalp EEG has a std of ~1e-5 V vs ~10 uV, so a 1e-2 cut-off is safe.
    Decided from physical amplitude only, never from labels."""
    return x * 1e6 if np.nanmedian(np.nanstd(x, axis=1)) < 1e-2 else x


def _inv_sqrtm(c: np.ndarray) -> np.ndarray:
    w, v = np.linalg.eigh(c)
    return (v * (1.0 / np.sqrt(np.maximum(w, 1e-12)))) @ v.T


def euclidean_align(x: np.ndarray, groups: np.ndarray) -> np.ndarray:
    """Per-subject EA: whiten each subject's windows by its mean spatial covariance."""
    out = np.empty_like(x)
    for g in np.unique(groups):
        idx = groups == g
        r = np.mean([w @ w.T / w.shape[1] for w in x[idx]], axis=0)
        out[idx] = np.einsum("ij,wjt->wit", _inv_sqrtm(r), x[idx])
    return out


# ---------------------------------------------------------------- data
def _manifests(n_ns: int) -> dict[str, pd.DataFrame]:
    physionet = pd.read_csv(ROOT / "dataset_healthy" / "manifest_healthy.csv").head(n_ns)
    oslo_all = pd.read_csv(EXTRA / "npz" / "manifest_oslo.csv")
    oslo_parts = pd.read_csv(EXTRA / "oslo_ds003775" / "participants.tsv", sep="\t").drop_duplicates("participant_id")
    m = {
        "xuanwu": pd.read_csv(ROOT / "dataset_ischemic" / "manifest_ischemic.csv"),
        "physionet": physionet,
        "tianjin": pd.read_csv(EXTRA / "npz" / "manifest_tianjin.csv"),
        "oslo": oslo_all.head(n_ns),
        # Controls for the two confounds that could transfer across devices:
        "oslo45": filter_min_age(oslo_all, oslo_parts, 45),           # age-matched to stroke (~55 y)
        "physionet_eo": physionet.assign(frac0=0.0, frac1=0.5),         # run 1: eyes open
        "physionet_ec": physionet.assign(frac0=0.5, frac1=1.0),         # run 2: eyes closed
    }
    for name, df in m.items():
        df["source"] = name
    return m


EXPERIMENTS: dict[str, list[tuple[list[str], list[str]]]] = {
    "main": source_swap_splits(["xuanwu", "tianjin"], ["physionet", "oslo"]),
    "age": source_swap_splits(["xuanwu", "tianjin"], ["physionet", "oslo45"]),
    # Stroke data are eyes-open; Oslo is eyes-closed. If the model learned "eyes
    # closed = control", testing against eyes-OPEN controls collapses the AUC.
    "eyes": [
        (["xuanwu", "oslo45"], ["tianjin", "physionet_eo"]),
        (["xuanwu", "oslo45"], ["tianjin", "physionet_ec"]),
        (["tianjin", "oslo45"], ["xuanwu", "physionet_eo"]),
        (["tianjin", "oslo45"], ["xuanwu", "physionet_ec"]),
        (["xuanwu", "physionet_eo"], ["tianjin", "oslo45"]),
        (["tianjin", "physionet_eo"], ["xuanwu", "oslo45"]),
    ],
}


def _windows_for_file(args: tuple) -> dict | None:
    import warnings as _w
    _w.filterwarnings("ignore")
    sys.path.insert(0, _BACKEND)
    from eeg_stroke_pipeline import (
        PipelineConfig, build_feature_row_from_windows, compute_sqi, load_array_file,
        parse_label, preprocess_eeg, preprocess_eeg_for_sqi, reorder_to_target_channels,
    )
    pid, label_raw, path, fs_m, cap, frac = args
    cfg = PipelineConfig()
    data, chans, fs_file = load_array_file(path)
    fs = float(fs_m) if fs_m == fs_m else (fs_file or cfg.fs)
    x_raw = to_microvolts(reorder_to_target_channels(data, chans, cfg.channels))
    if frac is not None:
        x_raw = slice_fraction(x_raw, frac)
    x = preprocess_eeg(x_raw, fs, cfg)
    x_sqi = preprocess_eeg_for_sqi(x_raw, fs, cfg)
    n_win, e_len, step = int(WIN_SEC * cfg.fs), int(cfg.entropy_window_sec * cfg.fs), int(cfg.entropy_step_sec * cfg.fs)
    ends = list(range(n_win, x.shape[1] + 1, step))
    if len(ends) > cap:
        ends = [ends[i] for i in np.unique(np.round(np.linspace(0, len(ends) - 1, cap)).astype(int))]
    wins, feats = [], []
    for end in ends:
        if compute_sqi(x_sqi[:, end - e_len:end], cfg.fs, cfg)["sqi_total"] < cfg.sqi_threshold:
            continue
        w = x[:, end - n_win:end]
        if not np.isfinite(w).all():
            continue
        f = build_feature_row_from_windows(entropy_window=w[:, -e_len:], mfdfa_window=w,
                                           channels=list(cfg.channels), fs=cfg.fs, config=cfg)
        wins.append(w.astype(np.float32))
        feats.append({k: v for k, v in f.items() if not k.startswith("sqi_")})
    if not wins:
        return None
    return {"pid": pid, "label": parse_label(label_raw), "windows": np.stack(wins), "feats": feats}


def load_source(name: str, manifest: pd.DataFrame, cap_per_patient: int, workers: int) -> dict:
    cache = CACHE / f"{name}_cap{cap_per_patient}.npz"
    if cache.exists():
        z = np.load(cache, allow_pickle=True)
        return {k: z[k] for k in z.files}
    files_per_pid = manifest.groupby("patient_id").size()
    has_frac = "frac0" in manifest.columns
    jobs = [(r.patient_id, r.label, r.path, r.fs,
             max(1, int(np.ceil(cap_per_patient / files_per_pid[r.patient_id]))),
             (r.frac0, r.frac1) if has_frac else None) for r in manifest.itertuples()]
    with ProcessPoolExecutor(workers) as ex:
        res = [r for r in ex.map(_windows_for_file, jobs) if r is not None]
    w = np.concatenate([r["windows"] for r in res])
    feats = pd.DataFrame([f for r in res for f in r["feats"]])
    pids = np.concatenate([[r["pid"]] * len(r["windows"]) for r in res])
    y = np.concatenate([[r["label"]] * len(r["windows"]) for r in res])
    CACHE.mkdir(parents=True, exist_ok=True)
    out = {"windows": w, "feat_values": feats.to_numpy(np.float32), "feat_names": np.array(feats.columns),
           "pids": pids, "y": y}
    np.savez(cache, **out)
    return out


# ---------------------------------------------------------------- models
def model_feat_lgbm(tr: dict, te: dict, seed: int) -> np.ndarray:
    import lightgbm as lgb
    clf = lgb.LGBMClassifier(objective="binary", is_unbalance=True, n_estimators=300, num_leaves=31,
                             learning_rate=0.05, random_state=seed, verbosity=-1)
    clf.fit(tr["feat_values"], tr["y"])
    return clf.predict_proba(te["feat_values"])[:, 1]


def _covs(x: np.ndarray) -> np.ndarray:
    from pyriemann.estimation import Covariances
    return Covariances("oas").fit_transform(x.astype(np.float64))


def _recenter(c: np.ndarray, groups: np.ndarray) -> np.ndarray:
    from pyriemann.utils.mean import mean_riemann
    out = np.empty_like(c)
    for g in np.unique(groups):
        idx = groups == g
        p = _inv_sqrtm(mean_riemann(c[idx]))
        out[idx] = p @ c[idx] @ p
    return out


def model_riemann(tr: dict, te: dict, seed: int, recenter: bool) -> np.ndarray:
    from pyriemann.tangentspace import TangentSpace
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler
    ctr, cte = _covs(tr["windows"]), _covs(te["windows"])
    if recenter:
        ctr, cte = _recenter(ctr, tr["pids"]), _recenter(cte, te["pids"])
    clf = make_pipeline(TangentSpace(metric="riemann"), StandardScaler(),
                        LogisticRegression(C=0.1, class_weight="balanced", max_iter=2000, random_state=seed))
    clf.fit(ctr, tr["y"])
    return clf.predict_proba(cte)[:, 1]


if nn is not None:
    class EEGNet(nn.Module):
        """EEGNet-8,2 (Lawhern et al., 2018) with a single logit output."""

        def __init__(self, n_channels: int, n_samples: int, f1: int = 8, d: int = 2, dropout: float = 0.5) -> None:
            super().__init__()
            f2 = f1 * d
            self.net = nn.Sequential(
                nn.Conv2d(1, f1, (1, 64), padding=(0, 32), bias=False), nn.BatchNorm2d(f1),
                nn.Conv2d(f1, f2, (n_channels, 1), groups=f1, bias=False), nn.BatchNorm2d(f2), nn.ELU(),
                nn.AvgPool2d((1, 4)), nn.Dropout(dropout),
                nn.Conv2d(f2, f2, (1, 16), padding=(0, 8), groups=f2, bias=False),
                nn.Conv2d(f2, f2, 1, bias=False), nn.BatchNorm2d(f2), nn.ELU(),
                nn.AvgPool2d((1, 8)), nn.Dropout(dropout), nn.Flatten(),
            )
            with torch.no_grad():
                n_flat = self.net(torch.zeros(1, 1, n_channels, n_samples)).shape[1]
            self.head = nn.Linear(n_flat, 1)

        def forward(self, x: "torch.Tensor") -> "torch.Tensor":
            return self.head(self.net(x)).squeeze(-1)
else:
    EEGNet = None


def _prep_for_net(x: np.ndarray, pids: np.ndarray, ea: bool) -> np.ndarray:
    x = x[:, :, ::2]                                         # 256 -> 128 Hz (signal is <= 35 Hz)
    if ea:
        x = euclidean_align(x, pids)
    else:                                                    # per-window, per-channel z-score
        x = (x - x.mean(axis=2, keepdims=True)) / (x.std(axis=2, keepdims=True) + 1e-6)
    return x[:, None].astype(np.float32)


def model_eegnet(tr: dict, te: dict, seed: int, ea: bool, epochs: int = 30) -> np.ndarray:
    torch.manual_seed(seed)
    np.random.seed(seed)
    xtr, xte = _prep_for_net(tr["windows"], tr["pids"], ea), _prep_for_net(te["windows"], te["pids"], ea)
    ytr = tr["y"].astype(np.float32)
    net = EEGNet(xtr.shape[2], xtr.shape[3])
    opt = torch.optim.Adam(net.parameters(), lr=1e-3, weight_decay=1e-4)
    pos_weight = torch.tensor((ytr == 0).sum() / max(1, (ytr == 1).sum()))
    loss_fn = nn.BCEWithLogitsLoss(pos_weight=pos_weight)
    xt, yt = torch.from_numpy(xtr), torch.from_numpy(ytr)
    for _ in range(epochs):                                  # fixed budget: no test-set early stopping
        net.train()
        for idx in torch.randperm(len(xt)).split(64):
            opt.zero_grad()
            loss_fn(net(xt[idx]), yt[idx]).backward()
            opt.step()
    net.eval()
    with torch.no_grad():
        return torch.sigmoid(torch.cat([net(b) for b in torch.from_numpy(xte).split(256)])).numpy()


def model_riemann_app(tr: dict, te: dict, seed: int) -> np.ndarray:
    """The exact model shipped to the real-time path (backend/riemann_model.py):
    trace-normalised OAS covariance, Riemannian mean reference, logistic regression."""
    from riemann_model import RiemannStrokeModel
    m = RiemannStrokeModel.fit(tr["windows"], tr["y"], channels=[f"c{i}" for i in range(tr["windows"].shape[1])],
                               fs=256.0, window_sec=WIN_SEC)
    return np.array([m.predict_proba_from_window(w)[1] for w in te["windows"]])


MODELS: dict = {
    "riemann_app": model_riemann_app,
    "feat_lgbm": lambda tr, te, s: model_feat_lgbm(tr, te, s),
    "riemann": lambda tr, te, s: model_riemann(tr, te, s, recenter=False),
    "riemann_rc": lambda tr, te, s: model_riemann(tr, te, s, recenter=True),
    "eegnet": lambda tr, te, s: model_eegnet(tr, te, s, ea=False),
    "eegnet_ea": lambda tr, te, s: model_eegnet(tr, te, s, ea=True),
}


def _concat(parts: list[dict]) -> dict:
    return {k: np.concatenate([p[k] for p in parts]) for k in ("windows", "feat_values", "pids", "y")}


def _in_source_cv(data: dict, sources: list[str], fn, seed: int, folds: int = 5) -> dict:
    """Ordinary patient-grouped CV inside one (stroke, control) pair: the optimistic baseline."""
    from sklearn.model_selection import StratifiedGroupKFold
    d = _concat([data[s] for s in sources])
    prob = np.zeros(len(d["y"]))
    for tr_idx, te_idx in StratifiedGroupKFold(folds, shuffle=True, random_state=seed).split(d["y"], d["y"], d["pids"]):
        tr = {k: v[tr_idx] for k, v in d.items()}
        te = {k: v[te_idx] for k, v in d.items()}
        prob[te_idx] = fn(tr, te, seed)
    return {"window_auc": float(roc_auc_score(d["y"], prob)), "patient_auc": patient_level_auc(d["pids"], d["y"], prob)}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cap", type=int, default=24, help="max windows per patient")
    ap.add_argument("--n-ns", type=int, default=50)
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--models", default=",".join(MODELS))
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--experiment", default="main", choices=list(EXPERIMENTS))
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    out_path = Path(args.out or ROOT / "results" / f"leave_source_out{'' if args.experiment == 'main' else '_' + args.experiment}.json")
    if torch is not None:
        torch.set_num_threads(10)

    splits = EXPERIMENTS[args.experiment]
    needed = sorted({s for tr, te in splits for s in tr + te})
    manifests = _manifests(args.n_ns)
    data = {}
    for name in needed:
        data[name] = load_source(name, manifests[name], args.cap, args.workers)
        print(f"[data] {name:12s} windows={len(data[name]['y'])} patients={len(np.unique(data[name]['pids']))}", flush=True)
    # Same feature columns everywhere (sources share the pipeline, but be explicit).
    names = next(iter(data.values()))["feat_names"]
    assert all((d["feat_names"] == names).all() for d in data.values())

    results = {"experiment": args.experiment, "in_source_cv": {}, "source_swap": []}
    for model in args.models.split(","):
        fn = MODELS[model]
        if args.experiment == "main":
            cv = _in_source_cv(data, ["xuanwu", "physionet"], fn, args.seed)
            results["in_source_cv"][model] = cv
            print(f"[{model}] in-source CV (xuanwu vs physionet): win AUC {cv['window_auc']:.3f} pt AUC {cv['patient_auc']:.3f}", flush=True)
        for train, test in splits:
            tr, te = _concat([data[s] for s in train]), _concat([data[s] for s in test])
            prob = fn(tr, te, args.seed)
            r = {"model": model, "train": train, "test": test,
                 "window_auc": float(roc_auc_score(te["y"], prob)),
                 "patient_auc": patient_level_auc(te["pids"], te["y"], prob)}
            results["source_swap"].append(r)
            print(f"[{model}] train {'+'.join(train):22s} -> test {'+'.join(test):22s} "
                  f"win AUC {r['window_auc']:.3f}  pt AUC {r['patient_auc']:.3f}", flush=True)
        out_path.write_text(json.dumps(results, indent=2), encoding="utf-8")

    print(f"\nSummary ({args.experiment}: mean over {len(splits)} source swaps)")
    print(f"{'model':11s} {'in-src ptAUC':>12s} {'swap winAUC':>11s} {'swap ptAUC':>10s}")
    sw = pd.DataFrame(results["source_swap"])
    for model in args.models.split(","):
        s = sw[sw["model"] == model]
        cv = results["in_source_cv"].get(model, {}).get("patient_auc", float("nan"))
        print(f"{model:11s} {cv:12.3f} {s['window_auc'].mean():11.3f} {s['patient_auc'].mean():10.3f}")


if __name__ == "__main__":
    main()
