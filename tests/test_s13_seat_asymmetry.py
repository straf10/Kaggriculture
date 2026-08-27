"""S13 Phase 1 — pin the statistics primitives (docs/plans/s13_seat_asymmetry.md §2).

No live-data dependency (matches the s10 bench test convention): these are pure
functions, checked against closed-form or cross-library references so a regression
in the CMH/Wilson/logistic math reddens here before it silently changes a verdict.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from analysis.s13_seat_asymmetry import (  # noqa: E402
    _seat_summary, _wl_table, cmh_test, fisher_p, lr_test, logistic_fit,
    mannwhitney, newcombe_diff_ci, wilson_ci,
)


def test_wilson_ci_matches_known_reference():
    # x=30, n=46 (S13 screen seat 0): textbook Wilson 95% CI ~ (0.508, 0.773)
    lo, hi = wilson_ci(30, 46)
    assert 0.50 < lo < 0.52
    assert 0.76 < hi < 0.78


def test_wilson_ci_empty_n():
    assert wilson_ci(0, 0) == (None, None)


def test_newcombe_diff_ci_contains_point_estimate():
    lo, hi = newcombe_diff_ci(30, 46, 24, 51)
    diff = 30 / 46 - 24 / 51
    assert lo < diff < hi
    # the screen's raw gap is ~0.18 with n this small -> CI should still straddle 0
    # (that is exactly why the plan calls it "a question, not a finding")
    assert lo < 0 < hi


def test_fisher_p_matches_the_screen_reading():
    # plan §1's "p ~ 0.07" is a two-proportion z-test; §2 1a pins Fisher exact
    # specifically (more conservative on this table): 0.101.
    p = fisher_p(30, 16, 24, 27)
    assert 0.09 < p < 0.11


def test_cmh_test_null_case_no_effect():
    """Four strata, each seat winning at the identical 50% rate -> CMH should not reject."""
    strata = [(10, 10, 10, 10), (20, 20, 20, 20), (5, 5, 5, 5), (15, 15, 15, 15)]
    r = cmh_test(strata)
    assert r["p_corrected"] > 0.5
    assert r["or_mh"] == pytest.approx(1.0, abs=1e-9)


def test_cmh_test_detects_a_real_stratified_effect():
    """Same seat-0 advantage repeated across strata should reject at a strict p."""
    strata = [(30, 10, 10, 30)] * 4
    r = cmh_test(strata)
    assert r["p_corrected"] < 1e-6
    assert r["or_mh"] > 1.0


def test_cmh_test_degenerate_returns_none():
    assert cmh_test([]) == {"n_strata_used": 0, "chi2_corrected": None, "p_corrected": None,
                             "chi2_uncorrected": None, "p_uncorrected": None, "or_mh": None}


def test_mannwhitney_matches_scipy_directly():
    from scipy.stats import mannwhitneyu
    x, y = [1, 2, 3, 4, 5], [3, 4, 5, 6, 7]
    ref_u, ref_p = mannwhitneyu(x, y, alternative="two-sided")
    r = mannwhitney(x, y)
    assert r["u"] == pytest.approx(float(ref_u))
    assert r["p"] == pytest.approx(float(ref_p))


def test_mannwhitney_empty_input():
    assert mannwhitney([], [1, 2]) == {"u": None, "p": None, "median_x": None, "median_y": None}


def test_logistic_fit_matches_sklearn_unpenalized():
    """Cross-library check: our IRLS fitter must land on the same coefficients as an
    independent implementation (no statsmodels available in this environment)."""
    from sklearn.linear_model import LogisticRegression

    rng = np.random.default_rng(13)
    n = 400
    x1 = rng.normal(size=n)
    x2 = rng.integers(0, 2, size=n).astype(float)
    eta = 0.3 + 0.8 * x1 - 1.2 * x2
    p = 1 / (1 + np.exp(-eta))
    y = (rng.uniform(size=n) < p).astype(float)

    X = np.column_stack([np.ones(n), x1, x2])
    ours = logistic_fit(X, y)

    ref = LogisticRegression(penalty=None, fit_intercept=False, tol=1e-12, max_iter=1000)
    ref.fit(X, y)
    ref_beta = ref.coef_[0]

    assert np.allclose(ours["beta"], ref_beta, atol=1e-3)


def test_lr_test_null_when_models_identical():
    assert lr_test(-100.0, -100.0) == pytest.approx(1.0)


def test_lr_test_matches_chi2_by_hand():
    from scipy.stats import chi2
    p = lr_test(-95.0, -100.0, df=1)
    assert p == pytest.approx(float(chi2.sf(10.0, df=1)))


def test_wl_table_and_seat_summary_reproduce_the_screen():
    """Plan §1: seat 0 30W-16L (WR 0.652), seat 1 24W-27L (WR 0.471)."""
    rows = ([{"seat": 0, "win": True}] * 30 + [{"seat": 0, "win": False}] * 16
            + [{"seat": 1, "win": True}] * 24 + [{"seat": 1, "win": False}] * 27)
    a, b, c, d = _wl_table(rows)
    assert (a, b, c, d) == (30, 16, 24, 27)
    s = _seat_summary(rows)
    assert s["seat0_wr"] == pytest.approx(0.6522, abs=1e-3)
    assert s["seat1_wr"] == pytest.approx(0.4706, abs=1e-3)
    assert s["gap"] > 0
