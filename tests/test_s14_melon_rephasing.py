"""S14 — the MELON re-phasing model must price the market the way the engine does.

Two properties the whole verdict rests on, each pinned against an independent oracle:

1. `melon_day` is the engine's **per-unit lockstep** (`kaggriculture.py:612` — both seats are
   quoted at the same pre-commit inventory), not a sequential price walk that prices one
   seat's whole order before the other's.  The oracle is `s9_market_ledger.step_ledger`, the
   replayer already validated against recorded ground truth (ROADMAP §3.1 rule 12).  A
   sequential re-implementation reddens `test_melon_day_is_lockstep_not_a_sequential_walk`.
2. MELON's only sink is the town centre's 1 unit/day — no shop lists it.  If an engine bump
   gives a shop a melon, `_melon_sink_per_day` must fail loudly rather than let the drain
   model go quietly stale.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from analysis import s9_live_read_55726984 as s9  # noqa: E402
from analysis.s9_market_ledger import step_ledger  # noqa: E402
from engine_reference.kaggriculture import MARKET_I0, PRODUCTS, market_price  # noqa: E402


def _ledger_lockstep(x, n_us, n_op):
    """The oracle: one market turn with both seats selling MELON, per the validated replayer."""
    inv = {p: MARKET_I0 for p in PRODUCTS}
    inv["MELON"] = MARKET_I0 + x
    rev, _units, _spend, inv_after = step_ledger(
        inv, [[["SELL", "MELON", n_us]], [["SELL", "MELON", n_op]]])
    return rev[0]["MELON"], rev[1]["MELON"], inv_after["MELON"] - MARKET_I0


def _sequential(x, n_us, n_op):
    """The WRONG model this test exists to exclude: seat 0's whole order, then seat 1's."""
    us = op = 0.0
    for _ in range(n_us):
        p = market_price("MELON", MARKET_I0 + x)
        us += p
        if p > 1:
            x += 1
    for _ in range(n_op):
        p = market_price("MELON", MARKET_I0 + x)
        op += p
        if p > 1:
            x += 1
    return us, op, x


@pytest.mark.parametrize("x, n_us, n_op", [(0, 7, 5), (46, 9, 4), (-10, 8, 8), (120, 6, 6)])
def test_melon_day_matches_the_validated_market_replayer(x, n_us, n_op):
    assert s9.melon_day(x, n_us, n_op) == pytest.approx(_ledger_lockstep(x, n_us, n_op))


def test_melon_day_is_lockstep_not_a_sequential_walk():
    """The two models must actually disagree, or property (1) is untested."""
    x, n_us, n_op = 40, 9, 9
    lock = s9.melon_day(x, n_us, n_op)
    seq = _sequential(x, n_us, n_op)
    assert lock[2] == seq[2]                 # same units, same end inventory
    assert lock[0] != pytest.approx(seq[0])  # but not the same split
    assert lock == pytest.approx(_ledger_lockstep(x, n_us, n_op))


def test_floor_units_do_not_raise_inventory():
    """`_commit_unit`: a sale at PRICE_FLOOR adds no supply, so the walk must stall there."""
    x_floor = 200  # deep past the point where price(x) == 1
    assert market_price("MELON", MARKET_I0 + x_floor) == 1
    us, _op, x_end = s9.melon_day(x_floor, 30, 0)
    assert us == 30 and x_end == x_floor


def test_melon_season_drains_one_unit_per_day():
    """No shop consumes MELON; the town centre eats exactly 1/day (`_town_consume`)."""
    ours = {20: 1}
    alone = s9.melon_season(ours, {}, 0, first_day=20, last_day=30)[0]
    delayed = s9.melon_season({29: 1}, {}, 0, first_day=20, last_day=30)[0]
    # nine days of drain sit between the two sales, so the later one is quoted strictly higher
    assert delayed > alone
    assert delayed == market_price("MELON", MARKET_I0 - 9)


def test_melon_sink_asserts_no_shop_carries_melon(monkeypatch):
    assert s9._melon_sink_per_day() == 1
    monkeypatch.setitem(s9.SHOPS, "YARN_STORE", ["WOOL", "MELON"])
    with pytest.raises(AssertionError):
        s9._melon_sink_per_day()
