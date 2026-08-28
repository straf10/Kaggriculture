"""S16 Phase 1 — pin the new statistics (power) and window-definition logic.

The CMH/Fisher/Wilson primitives are pinned in tests/test_s13_seat_asymmetry.py and
reused verbatim here (ROADMAP §3 "reuse, do not duplicate") — this file only covers
the code `analysis/s16_slot_comparison.py` adds on top: the two-proportion power
calculation and the same-window definition (plan §1 steps 2 and 5).
"""
from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from analysis.s16_slot_comparison import (  # noqa: E402
    BURST_N, define_window, min_detectable_effect, per_opponent_table,
    two_proportion_power, zone_strata,
)


def test_power_increases_with_effect_size():
    small = two_proportion_power(90, 105, 0.05)
    large = two_proportion_power(90, 105, 0.20)
    assert small < large


def test_power_increases_with_n():
    lo_n = two_proportion_power(20, 20, 0.10)
    hi_n = two_proportion_power(500, 500, 0.10)
    assert lo_n < hi_n


def test_power_matches_the_s13_ballpark():
    # s13's plan (§1 step "Available sample") reads: n~=250/seat, ~98% at an 18-point
    # gap, ~61% at 10, ~24% at 5. Same formula family, same order of magnitude.
    assert two_proportion_power(250, 250, 0.18) > 0.90
    assert 0.45 < two_proportion_power(250, 250, 0.10) < 0.75
    assert two_proportion_power(250, 250, 0.05) < 0.40


def test_min_detectable_effect_is_between_zero_and_one():
    mde = min_detectable_effect(90, 105, power_target=0.80)
    assert mde is not None
    assert 0.0 < mde < 1.0
    # and it should actually clear 80% power at that effect
    assert two_proportion_power(90, 105, mde) == pytest.approx(0.80, abs=0.01)


def test_min_detectable_effect_shrinks_with_more_data():
    small_n = min_detectable_effect(20, 20, power_target=0.80)
    large_n = min_detectable_effect(500, 500, power_target=0.80)
    assert large_n < small_n


def _row(idx, t, win=True, zone=None, controlled=False, seat=0, opponent="X"):
    return {"ep_index": idx, "time": t, "win": win, "zone": zone,
            "controlled": controlled, "seat": seat, "opponent": opponent}


def test_define_window_is_max_of_upload_and_70th_episode():
    base = dt.datetime(2026, 8, 24, 0, 0, 0)
    rows = [_row(i, base + dt.timedelta(hours=i)) for i in range(1, 100)]
    w = define_window(rows)
    # the 70th episode (ep_index==70) is well after the hard-coded upload time
    assert w == base + dt.timedelta(hours=70)


def test_define_window_falls_back_to_upload_when_fewer_than_70_episodes():
    from analysis.s16_slot_comparison import A_UPLOADED
    rows = [_row(i, dt.datetime(2026, 8, 24) + dt.timedelta(hours=i)) for i in range(1, BURST_N)]
    assert define_window(rows) == A_UPLOADED


def test_per_opponent_table_flags_shared_opponents_only():
    rows_a = [_row(1, None, win=True, opponent="alice"), _row(2, None, win=False, opponent="bob")]
    rows_b = [_row(1, None, win=True, opponent="alice"), _row(2, None, win=True, opponent="carol")]
    tbl = per_opponent_table(rows_a, rows_b)
    assert tbl["n_opponents_met_by_both"] == 1
    assert tbl["shared_opponents"][0]["opponent"] == "alice"
    assert tbl["n_opponents_total"] == 3


def test_zone_strata_shape_matches_cmh_test_input():
    rows_a = [_row(1, None, win=True, zone="<1500", controlled=True),
              _row(2, None, win=False, zone="1500-1700", controlled=True)]
    rows_b = [_row(1, None, win=True, zone="<1500", controlled=True),
              _row(2, None, win=True, zone="1500-1700", controlled=True)]
    strata, detail = zone_strata(rows_a, rows_b, controlled_only=True)
    assert len(strata) == 6  # one per RATING_EDGES bucket
    # <1500: A 1W-0L, B 1W-0L
    assert strata[0] == (1, 0, 1, 0)
    assert detail[0]["zone"] == "<1500"
