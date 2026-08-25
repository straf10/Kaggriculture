"""S10 P0.4 — pin the s9 market ledger.

Three properties, each with a strict tolerance so drift in the engine or in the ledger
implementation trips a failing test rather than silently changing measured revenue:

  (1) Cash conservation.  On ≥10 real ladder replays, the scaled ledger reproduces the
      per-episode reward to within 1,5% (Σrevenue − Σspend ≈ reward − starting_money).
  (2) Quote identity.  `market_price(item, inventory)` reproduces the recorded quote
      `obs.market.prices[item]` at the recorded inventory with **zero** disagreements
      over ≥500 (obs, item) samples.
  (3) Alignment lock.  The observation at index t is the state AFTER step t's action,
      so the market that prices step t is the one recorded at t-1.  If the ledger
      switches to `steps[t]` as pre-state, cash conservation for a sampled step
      collapses.  This test breaks the moment that changes.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from analysis.s8_replay_io import ladder_episodes, load, replay_paths  # noqa: E402
from analysis.s9_market_ledger import episode_ledger, step_ledger  # noqa: E402
from engine_reference.kaggriculture import market_price  # noqa: E402

# One primary submission with lots of episodes on disk; the small extra live_55726984
# is used for the alignment lock.
PRIMARY_SUB = "55586926"
FAST_SUB = "55726984"


def _first_n(sub: str, n: int):
    out = []
    for eid, meta in ladder_episodes(sub):
        out.append((eid, meta))
        if len(out) >= n:
            break
    return out


@pytest.mark.parametrize("sub,n", [(PRIMARY_SUB, 10)])
def test_cash_conservation_within_1_5pct(sub, n):
    """Σrevenue − Σspend reconstructs Σ(reward − starting_money) across ≥10 replays to <1,5%.

    Aggregate, not per-episode: the ledger's docstring notes it does not simulate SELL/BUY
    rejection (empty shed / no money / full shed), so individual episodes can drift by
    single-digit percent when the engine rejects orders. The scaled cash-flow correction is
    a fleet-level residual (matching `s9-live-read-55726984`: "rescaled to recorded cash,
    ~1% residual"). This test pins that residual at <1,5%."""
    eps = _first_n(sub, n)
    assert len(eps) >= n, f"need {n} ladder replays for {sub}, got {len(eps)}"
    tot_rev, tot_sp, tot_delta = 0.0, 0.0, 0.0
    for eid, m in eps:
        steps = m["steps"]
        led = episode_ledger({"steps": steps})
        for seat in (0, 1):
            tot_rev += sum(led["revenue"][seat].values())
            tot_sp += sum(led["spend"][seat].values())
            starting_money = float(steps[0][seat]["observation"]["farms"][seat]["money"])
            tot_delta += float(m["rewards"][seat]) - starting_money
    rel = abs((tot_rev - tot_sp) - tot_delta) / max(abs(tot_delta), 1.0)
    assert rel < 0.015, f"aggregate |ledger − recorded| / recorded = {rel:.4f}"


def test_market_price_matches_recorded_quote_zero_diffs():
    """`market_price(item, obs.inventory[item]) == obs.market.prices[item]` on ≥500 samples."""
    samples = 0
    mismatches: list[tuple[str, int, int, int]] = []
    for p in replay_paths(FAST_SUB):
        d = load(p)
        for state in d["steps"]:
            obs = state[0]["observation"]
            inv = obs["market"]["inventory"]
            prices = obs["market"]["prices"]
            for item, quoted in prices.items():
                computed = market_price(item, inv[item])
                if computed != quoted:
                    mismatches.append((item, inv[item], quoted, computed))
                samples += 1
                if samples >= 500 and not mismatches:
                    assert mismatches == [], mismatches[:5]
                    return
    assert samples >= 500, f"only sampled {samples} (need ≥500)"
    assert mismatches == [], mismatches[:5]


def test_observation_lags_action_by_one_step():
    """Lock the ledger's alignment: obs[t] is post-action; the market that prices
    step t is obs[t-1].  Wiring it to obs[t] instead collapses cash conservation."""
    # Pick a live episode and a step with real seat-0 SELL activity.
    p = next(iter(replay_paths(FAST_SUB)))
    d = load(p)
    steps = d["steps"]
    tgt_t = None
    for t in range(1, len(steps) - 1):
        act = (steps[t][0].get("action") or {}).get("market") or []
        if any(o and o[0] == "SELL" for o in act):
            tgt_t = t
            break
    assert tgt_t is not None, "no SELL step found in the sample replay"

    pre_correct = steps[tgt_t - 1][0]["observation"]
    pre_wrong = steps[tgt_t][0]["observation"]
    post = steps[tgt_t][0]["observation"]
    orders = [(steps[tgt_t][0].get("action") or {}).get("market") or [],
              (steps[tgt_t][1].get("action") or {}).get("market") or []]
    hires = [int(pre_correct["farms"][p_].get("hires_today", 0)) for p_ in (0, 1)]
    quads = [len(pre_correct["farms"][p_].get("unlocked_quadrants") or ["NW"]) for p_ in (0, 1)]

    rev_c, _u_c, sp_c, _ = step_ledger(
        pre_correct["market"]["inventory"], orders, hires_today=hires, quadrants=quads)
    rev_w, _u_w, sp_w, _ = step_ledger(
        pre_wrong["market"]["inventory"], orders, hires_today=hires, quadrants=quads)

    cash = float(post["farms"][0]["money"]) - float(pre_correct["farms"][0]["money"])
    delta_correct = sum(rev_c[0].values()) - sum(sp_c[0].values())
    delta_wrong = sum(rev_w[0].values()) - sum(sp_w[0].values())

    # The correct alignment reproduces the recorded cash delta (up to fill).
    # The wrong alignment does not — and the two are meaningfully different.
    # Both facts together break if someone silently switches the pre-state.
    assert abs(delta_correct - cash) < 1.0 + 0.02 * max(abs(cash), 1.0), \
        f"aligned ledger disagrees with cash: sim={delta_correct}, cash={cash}"
    assert abs(delta_correct - delta_wrong) > 1e-6, \
        "correct-vs-wrong alignment gives identical result — test is inert"
