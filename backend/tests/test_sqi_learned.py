"""Learned SQI v2 channel scorer: frozen JSON export, numpy runtime, score mapping."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

BACKEND = Path(__file__).resolve().parent.parent
SCRIPTS = BACKEND.parent / "scripts"
for p in (BACKEND, SCRIPTS):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import sqi_learned as L  # noqa: E402
import sqi_v2 as S  # noqa: E402

FEATURES = ("a", "b", "c")


def _toy(n: int = 600, seed: int = 0):
    rng = np.random.default_rng(seed)
    x = np.c_[rng.lognormal(0, 1.5, n), rng.standard_t(2, n), rng.normal(size=n)]
    y = (x[:, 0] + rng.normal(0, 1, n) > 1.5).astype(int)
    x[rng.random(n) < 0.05, 1] = np.nan
    return x, y


def _const_scorer(p: float, threshold: float = 0.5) -> L.LearnedScorer:
    logit = float(np.log(p / (1 - p)))
    return L.LearnedScorer(
        features=("kurtosis",), medians=(0.0,), quantiles=((0.0,), (1.0,)), references=(0.0, 1.0),
        coef=(0.0,), intercept=logit, threshold=threshold,
    )


@pytest.mark.unit
def test_numpy_runtime_matches_the_sklearn_pipeline() -> None:
    from tuar_sqi_eval import fit_logistic
    from sqi_learned_scorer import export_pipeline

    x, y = _toy()
    model = fit_logistic(x, y)
    scorer = L.learned_scorer_from_dict(export_pipeline(model, FEATURES, threshold=0.4))
    x_new, _ = _toy(n=200, seed=1)
    x_new[0] = [1e6, -1e6, np.nan]  # beyond the fitted quantiles on both sides, plus a gap
    want = model.predict_proba(x_new)[:, 1]
    got = np.array([scorer.probability(dict(zip(FEATURES, row))) for row in x_new])
    np.testing.assert_allclose(got, want, atol=1e-9)


@pytest.mark.unit
def test_export_round_trips_through_json() -> None:
    import json

    from tuar_sqi_eval import fit_logistic
    from sqi_learned_scorer import export_pipeline

    x, y = _toy()
    d = export_pipeline(fit_logistic(x, y), FEATURES, threshold=0.3)
    back = L.learned_scorer_from_dict(json.loads(json.dumps(d)))
    assert back.features == FEATURES and back.threshold == 0.3


@pytest.mark.unit
def test_missing_feature_key_is_imputed_with_the_training_median() -> None:
    s = L.LearnedScorer(features=("a",), medians=(2.0,), quantiles=((0.0,), (4.0,)), references=(0.0, 1.0),
                        coef=(1.0,), intercept=0.0, threshold=0.5)
    assert s.probability({}) == pytest.approx(s.probability({"a": 2.0}))


@pytest.mark.unit
def test_score_mapping_puts_the_threshold_on_channel_ok() -> None:
    t = 0.3
    assert L.score_from_probability(0.0, t) == pytest.approx(1.0)
    assert L.score_from_probability(t, t) == pytest.approx(S.CHANNEL_OK)
    assert L.score_from_probability(1.0, t) == pytest.approx(0.0)
    ps = np.linspace(0, 1, 101)
    scores = [L.score_from_probability(p, t) for p in ps]
    assert all(a >= b for a, b in zip(scores, scores[1:]))
    assert all((s >= S.CHANNEL_OK) == (p <= t) for p, s in zip(ps, scores))


@pytest.mark.unit
def test_operating_threshold_flags_the_chosen_share_of_clean_channels() -> None:
    from sqi_learned_scorer import operating_threshold

    p_clean = np.linspace(0, 1, 1001)
    t = operating_threshold(p_clean, quantile=0.95)
    assert np.mean(p_clean > t) == pytest.approx(0.05, abs=0.002)


def _window(seed: int = 0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    x = rng.normal(0, 20, size=(3, 1024))
    x[2] = 0.0  # flat channel
    return x


@pytest.mark.unit
def test_assess_window_uses_the_scorer_for_the_score_only() -> None:
    x = _window()
    plain = S.assess_window(x, 256.0)
    bad = S.assess_window(x, 256.0, scorer=_const_scorer(0.99))
    good = S.assess_window(x, 256.0, scorer=_const_scorer(0.01))
    for ch_plain, ch_bad, ch_good in zip(plain.channels[:2], bad.channels[:2], good.channels[:2]):
        assert ch_bad.score < S.CHANNEL_OK <= ch_good.score
        assert ch_good.reasons == ch_plain.reasons  # reasons still come from the rules
    # flat stays flat whatever the scorer says
    assert good.channels[2].score == 0.0 and good.channels[2].reasons == ("flat",)


@pytest.mark.unit
def test_channel_flagged_by_the_scorer_gets_its_strongest_rule_reason() -> None:
    rng = np.random.default_rng(3)
    t = np.arange(1024) / 256.0
    x = rng.normal(0, 20, size=(2, 1024))
    x[0] += 60 * np.sin(2 * np.pi * 0.2 * t)  # mild drift: some severity, maybe below the reason cut
    q = S.assess_window(x, 256.0, scorer=_const_scorer(0.99))
    assert q.channels[0].score < S.CHANNEL_OK
    assert q.channels[0].reasons, "a channel the interface marks bad must come with a reason"


@pytest.mark.unit
def test_inconsistent_scorer_file_is_rejected_at_load() -> None:
    good = {"features": ["a", "b"], "medians": [0, 0], "quantiles": [[0, 0], [1, 1]], "references": [0, 1],
            "coef": [1, 1], "intercept": 0, "threshold": 0.5}
    L.learned_scorer_from_dict(good)
    for key, bad in (("coef", [1]), ("medians", [0]), ("references", [0, 0.5, 1]), ("quantiles", [[0], [1]]),
                     ("threshold", 1.5)):
        with pytest.raises(ValueError):
            L.learned_scorer_from_dict({**good, key: bad})
