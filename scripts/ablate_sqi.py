"""Ablation: check SQI vs entropy features as confound source."""
import sys, warnings
warnings.filterwarnings("ignore")
sys.path.insert(0, r"C:\Users\Admin\eeg-stroke-app\backend")
from pathlib import Path
import numpy as np, pandas as pd
from sklearn.metrics import f1_score, roc_auc_score
from sklearn.model_selection import GroupKFold
import lightgbm as lgb
from eeg_stroke_pipeline import ENTROPY_FEATURES, MFDFA_FEATURES, SQI_FEATURES

ROOT = Path(r"C:\Users\Admin\eeg-stroke-app")
ft = pd.read_csv(ROOT / "dataset_real" / "feature_table_combined.csv")
label_map = {0:0, 1:1, "non-stroke":0, "nonstroke":0, "normal":0, "ischemic":1}
ft["label"] = ft["label"].map(label_map).astype(int)
print(f"Windows: {len(ft):,}  Label dist: {dict(ft['label'].value_counts().sort_index())}\n")

def run(feats, name):
    X = ft[feats].astype(float).to_numpy()
    y = ft["label"].to_numpy(dtype=int)
    groups = ft["patient_id"].to_numpy()
    kf = GroupKFold(n_splits=5)
    f1s, aucs = [], []
    for fold, (tr, te) in enumerate(kf.split(X, y, groups), 1):
        clf = lgb.LGBMClassifier(
            is_unbalance=True, n_estimators=400,
            random_state=42, n_jobs=-1, verbosity=-1
        )
        clf.fit(X[tr], y[tr])
        probs = clf.predict_proba(X[te])[:, 1]
        preds = (probs >= 0.5).astype(int)
        f1s.append(f1_score(y[te], preds, average="macro", zero_division=0))
        aucs.append(roc_auc_score(y[te], probs) if len(np.unique(y[te])) > 1 else float("nan"))
        print(f"  fold {fold}  F1={f1s[-1]:.3f}  AUC={aucs[-1]:.3f}")
    print(f"  MEAN  F1={np.mean(f1s):.3f} +/- {np.std(f1s):.3f}   AUC={np.mean(aucs):.3f}\n")
    return np.mean(f1s), np.mean(aucs)

results = {}
for feats, name in [
    (list(SQI_FEATURES),                                                  "SQI-only (5 feats)"),
    (list(ENTROPY_FEATURES),                                              "ApFu-only, no SQI"),
    (list(MFDFA_FEATURES),                                                "MFDFA-only, no SQI"),
    (list(ENTROPY_FEATURES) + list(MFDFA_FEATURES),                       "ApFu+MFDFA, no SQI"),
    (list(ENTROPY_FEATURES) + list(SQI_FEATURES),                         "ApFu+SQI (original)"),
    (list(ENTROPY_FEATURES) + list(MFDFA_FEATURES) + list(SQI_FEATURES),  "Full (original)"),
]:
    print(f"=== {name} ===")
    f1, auc = run(feats, name)
    results[name] = (f1, auc)

print("=" * 55)
print(f"{'Condition':<30}  {'F1':>6}  {'AUC':>6}")
print("-" * 55)
for name, (f1, auc) in results.items():
    print(f"{name:<30}  {f1:6.3f}  {auc:6.3f}")
print("=" * 55)
