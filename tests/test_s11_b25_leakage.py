"""S11 B2.5 — the PASS-replay leakage test, written before trusting the predictor.

Patches `steps[t][opp]["action"]` to PASS across a whole (already-recorded) replay
and asserts `per_step_ledger` / `predict_dump_events` are bit-identical to the
unpatched run. If they differ, the estimator secretly read the opponent's raw
action somewhere — exactly the bug this test caught in the shipped B2.0' spike
(`_step_identity`'s "our own committed sales" used to run through
`harness.metrics._transition_events`, which simulates BOTH seats jointly, so the
opponent's real action could shift our own computed sale price by $1-2 within a
step; fixed by `_our_committed_sales_isolated`, which always forces the opponent's
action to PASS internally).

Runs on a synthetic replay generated from the real engine (no live corpus needed).
"""
from __future__ import annotations

import copy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from analysis.s8_replay_io import load, meta  # noqa: E402
from analysis.s10_opponent_inventory import (  # noqa: E402
    PREMIUM, per_step_ledger, predict_dump_events,
)
from fixtures.replays import write_synthetic_replay  # noqa: E402

PASS = {"farmer": ["PASS"], "hands": [], "market": []}


def _active_agent(sell_item, plant_crop):
    """Plants/waters/harvests a crop, feeds/collects from nothing (no animal
    purchased — kept simple), and trades on the market every turn — busy
    enough to exercise both the tile-based (B2.1) and money-channel (B2.0'
    core) paths, and to overlap same-product SELLs with the other seat."""
    def act(i):
        if i == 0:
            return {"farmer": ["BUY_SEED", plant_crop, 4], "hands": [],
                    "market": [["SELL", sell_item, 2]]}
        if i == 1:
            return {"farmer": ["PLANT", plant_crop], "hands": [],
                    "market": [["SELL", sell_item, 2]]}
        if 2 <= i <= 12:
            return {"farmer": ["WATER"], "hands": [],
                    "market": [["SELL", sell_item, 1], ["BUY_PRODUCT", "WHEAT", 1]]}
        if i == 13:
            return {"farmer": ["HARVEST"], "hands": [], "market": []}
        return {"farmer": ["PASS"], "hands": [],
                "market": [["SELL", sell_item, 3]]}
    return act


def test_ledger_and_predictor_are_leakage_safe(tmp_path):
    d = tmp_path / "b25_leakage"
    d.mkdir()

    p = write_synthetic_replay(
        d, 300001, seed=7, episode_steps=90,
        teams=("STRAF", "OppA"),
        seat0_action=_active_agent("MELON", "MELON"),
        seat1_action=_active_agent("MELON", "MELON"),  # same product, same steps -> interleaving
        shed_preload={"MELON": 40, "STRAWBERRY": 40, "WHEAT": 40},
        gzip_it=False,
    )
    dl = load(p)
    m = meta(dl)
    replay = {"steps": m["steps"], "configuration": m["configuration"]}
    our_seat_idx = 0
    opp = 1 - our_seat_idx

    ledger_real = per_step_ledger(replay, our_seat_idx)
    assert ledger_real, "expected a non-empty ledger from a real synthetic episode"

    patched_steps = copy.deepcopy(m["steps"])
    for t in range(1, len(patched_steps)):
        patched_steps[t][opp]["action"] = dict(PASS)
    replay_patched = {"steps": patched_steps, "configuration": m["configuration"]}

    ledger_patched = per_step_ledger(replay_patched, our_seat_idx)

    assert ledger_real == ledger_patched, (
        "per_step_ledger is not leakage-safe: output changed when the "
        "opponent's action was patched to PASS")

    for product in PREMIUM:
        preds_real = predict_dump_events(ledger_real, product)
        preds_patched = predict_dump_events(ledger_patched, product)
        assert preds_real == preds_patched, (
            f"predict_dump_events({product}) is not leakage-safe")


def test_ledger_changes_when_opponent_activity_changes(tmp_path):
    """Sanity check on the test above: the ledger DOES depend on the
    opponent's real activity when it isn't patched to PASS (this is not a
    test that always trivially passes regardless of input)."""
    d = tmp_path / "b25_sanity"
    d.mkdir()

    p_a = write_synthetic_replay(
        d, 300002, seed=11, episode_steps=40,
        teams=("STRAF", "OppA"),
        seat0_action=_active_agent("MELON", "MELON"),
        seat1_action=lambda i: PASS,
        shed_preload={"MELON": 40},
        gzip_it=False,
    )
    p_b = write_synthetic_replay(
        d, 300003, seed=11, episode_steps=40,
        teams=("STRAF", "OppA"),
        seat0_action=_active_agent("MELON", "MELON"),
        seat1_action=_active_agent("MELON", "MELON"),
        shed_preload={"MELON": 40},
        gzip_it=False,
    )
    m_a = meta(load(p_a))
    m_b = meta(load(p_b))
    ledger_a = per_step_ledger(
        {"steps": m_a["steps"], "configuration": m_a["configuration"]}, 0)
    ledger_b = per_step_ledger(
        {"steps": m_b["steps"], "configuration": m_b["configuration"]}, 0)
    assert ledger_a != ledger_b
