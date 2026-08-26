"""S10 P2.2 — the two market parsers must agree.

`harness/metrics.py::_simulate_market` and `analysis/s9_market_ledger.py::step_ledger`
both walk the engine's per-unit market pricing but from different call sites (gate vs
live-replay analysis).  If they drift, gate output and the s9 live read stop being
directly comparable, and the "single parser" invariant the plan (P2.2) requires is
lost silently.

Layer 1 (CI, synthetic corpus): cross-check on synthetic replays with looser threshold.
Layer 2 (live replays, skip on clean checkout): cross-check on ≥5 real replays, <2% gap.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from analysis.s8_replay_io import ladder_episodes, our_seat, replay_paths  # noqa: E402
from analysis.s9_market_ledger import episode_ledger  # noqa: E402
from harness.metrics import extract_metrics  # noqa: E402

requires_live = pytest.mark.skipif(
    not replay_paths("55586926"),
    reason="gitignored live replays absent (§2.4b)")


def _first_n_env_jsons(sub: str, n: int):
    out = []
    for eid, m in ladder_episodes(sub):
        if our_seat(m["teams"]) is None:
            continue
        env = {"steps": m["steps"], "configuration": m["configuration"],
               "rewards": m["rewards"], "statuses": ["DONE", "DONE"]}
        out.append((eid, m, env))
        if len(out) >= n:
            break
    return out


def _check_parsers_agree(eps, threshold):
    tot_metric_rev = 0.0
    tot_ledger_rev = 0.0
    for eid, m, env in eps:
        led = episode_ledger({"steps": m["steps"]})
        for seat in (0, 1):
            met = extract_metrics(env, seat)
            metric_rev_by_p = met["realized_revenue_by_product"]
            ledger_rev_by_p = led["revenue"][seat]
            all_products = set(metric_rev_by_p) | set(ledger_rev_by_p)
            for p in all_products:
                tot_metric_rev += float(metric_rev_by_p.get(p, 0))
                tot_ledger_rev += float(ledger_rev_by_p.get(p, 0))
    agg_gap = abs(tot_metric_rev - tot_ledger_rev) / max(tot_metric_rev, tot_ledger_rev, 1.0)
    assert agg_gap < threshold, f"aggregate realized revenue gap = {agg_gap:.4f}"


# ---------------------------------------------------------------------------
# Layer 1 — CI (synthetic corpus)
# ---------------------------------------------------------------------------

def test_two_parsers_agree_synthetic(synthetic_corpus):
    """Cross-check harness metrics vs ledger on synthetic replays."""
    eps = _first_n_env_jsons(synthetic_corpus["sub"], 3)
    assert len(eps) >= 3
    _check_parsers_agree(eps, 0.05)


# ---------------------------------------------------------------------------
# Layer 2 — live replays (skip on clean checkout)
# ---------------------------------------------------------------------------

@requires_live
def test_two_parsers_agree_on_realized_revenue():
    eps = _first_n_env_jsons("55586926", 5)
    assert len(eps) >= 5
    _check_parsers_agree(eps, 0.02)
