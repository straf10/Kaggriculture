"""S11 B2 — the reporting contract of the opponent-inventory instrument.

Three properties, each of which failed on the code as committed in 1cbbec9:

1. `R` must not depend on PRODUCTS iteration order.  The WHEAT/FERTILIZER
   activity flag used to be raised inside the same loop that consumed it, and
   WHEAT is PRODUCTS[0] while FERTILIZER is PRODUCTS[8] — so a step where only
   FERTILIZER traded kept eight products' revenue in `R`, while the same step
   with the list reversed dropped all nine.
2. B2.1 has to report the bound WIDTH against shed_cap, not just the
   violation count (plan §B2.1: "ανέφερε και τα δύο νούμερα").  The width was
   collected into a dead list and never computed.
3. B2.4's MAE is conditional on `uncertainty_width == 0` — the subset where
   the estimator already claims certainty — and B2.5's precision is only
   readable against the label base rate.  Both have to say so in the field
   names, or the ROADMAP entry built from them overstates the instrument.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from analysis import s10_opponent_inventory as oi  # noqa: E402
from analysis.s8_replay_io import load, meta  # noqa: E402
from fixtures.replays import write_synthetic_replay  # noqa: E402

PASS = {"farmer": ["PASS"], "hands": [], "market": []}


def _sell_melon(_i):
    return {"farmer": ["PASS"], "hands": [], "market": [["SELL", "MELON", 3]]}


def _wf_step(m, our_seat_idx=0):
    """Fabricate the exact step that used to expose the ordering bug: the
    opponent bought FERTILIZER (so `net_opp < 0` on PRODUCTS[8] and ONLY
    there) while a non-WF product moved enough to carry real revenue.

    Public market inventory is what `_step_identity` reads, so patching it on
    the recorded observations is enough — no re-simulation needed.
    """
    steps = m["steps"]
    prev_step, cur_step = steps[1], steps[2]
    pre = prev_step[0]["observation"]["market"]["inventory"]
    post = cur_step[0]["observation"]["market"]["inventory"]
    # only FERTILIZER goes net-negative for the opponent
    post["FERTILIZER"] = int(pre["FERTILIZER"]) - 1
    # ...and MELON carries revenue that a correct R must exclude wholesale
    post["MELON"] = int(pre["MELON"]) + 6
    return prev_step, cur_step


def test_R_is_independent_of_products_iteration_order(tmp_path):
    d = tmp_path / "wf_order"
    d.mkdir()
    p = write_synthetic_replay(
        d, 310001, seed=5, episode_steps=30,
        teams=("STRAF", "OppA"),
        seat0_action=_sell_melon, seat1_action=None,
        shed_preload={"MELON": 60}, gzip_it=False,
    )
    m = meta(load(p))
    cfg = m["configuration"]
    prev_step, cur_step = _wf_step(m)

    ident = oi._step_identity(prev_step, cur_step, cfg, 0)

    # Guard: the test is only meaningful if this step really is the shape the
    # bug needed — WF activity raised late, with revenue sitting in front of it.
    assert ident["classification"] == "AMBIGUOUS_WF"
    assert ident["products"]["FERTILIZER"]["opp_net_wf"] < 0
    assert ident["products"]["WHEAT"]["opp_net_wf"] >= 0
    assert ident["products"]["MELON"]["opp_sell_nonfloor"] > 0

    original = list(oi.PRODUCTS)
    try:
        oi.PRODUCTS = list(reversed(original))  # FERTILIZER first, WHEAT last
        reversed_ident = oi._step_identity(prev_step, cur_step, cfg, 0)
    finally:
        oi.PRODUCTS = original

    assert reversed_ident["R"] == ident["R"], (
        "R depends on PRODUCTS iteration order: the WHEAT/FERTILIZER flag is "
        "being raised inside the loop that consumes it")
    assert reversed_ident["classification"] == ident["classification"]


def test_b21_reports_width_against_shed_cap(synthetic_corpus):
    out = oi.validate_b21_b24(sub=synthetic_corpus["sub"], n_replays=2)
    b21 = out["b21"]

    assert b21["shed_cap"] > 0
    assert b21["n_product_steps"] > 0
    widths = b21["bound_width_by_product"]
    present = [w for w in widths.values() if w]
    assert present, "no bound widths were measured"
    for w in present:
        assert w["median"] <= w["p90"] <= w["max"]
        assert w["n"] > 0
    # the two numbers B2.1's acceptance asks for, both reachable from the output
    assert isinstance(b21["products_median_width_below_shed_cap"], list)
    assert isinstance(b21["products_max_width_above_shed_cap"], list)


def test_b21_verdict_does_not_hide_lower_bound_violations(synthetic_corpus):
    out = oi.validate_b21_b24(sub=synthetic_corpus["sub"], n_replays=2)
    b21 = out["b21"]

    assert "lower_bound_violation_rate" in b21
    n = b21["n_lower_bound_violations"]
    if b21["n_upper_bound_violations"] == 0:
        # a clean upper bound must not be reported as a clean instrument
        assert "LOWER BOUND" in b21["verdict"]
    if n:
        assert b21["lower_bound_violations_sample"]
        expected = round(n / b21["n_product_steps"], 4)
        assert b21["lower_bound_violation_rate"] == expected


def test_b24_mae_is_labelled_as_conditional(synthetic_corpus):
    out = oi.validate_b21_b24(sub=synthetic_corpus["sub"], n_replays=2)
    b24 = out["b24"]

    # the unqualified name is gone: it was never the estimator's overall error
    assert "mae_by_product" not in b24
    assert "mae_by_product_where_width_zero" in b24
    assert "n_width_zero_by_product" in b24
    # and the headline coverage is quotable both ways
    assert "overall_coverage_active_products" in b24
    assert "min_coverage_by_product" in b24
    if b24["overall_coverage_active_products"] is not None:
        assert b24["overall_coverage_active_products"] <= b24["overall_coverage"] + 1e-9


def test_b25_reports_precision_against_the_base_rate(synthetic_corpus):
    out = oi.evaluate_dump_predictor(sub=synthetic_corpus["sub"], n_replays=2)

    assert "prevalence" in out
    assert "lift_over_base_rate" in out
    assert "label_caveat" in out
    for p in oi.PREMIUM:
        prev = out["prevalence"][p]
        prec = out["precision"][p]
        assert prev is None or 0.0 <= prev <= 1.0
        if prec is not None and prev:
            assert out["lift_over_base_rate"][p] == round(prec / prev, 3)
    assert "prevalence" in out["verdict"]
