"""Guards for the local Bradley-Terry ladder (ROADMAP R22 / §4.3 S6 step 3).

The BT fit is the part that can be silently wrong — a ranking that looks plausible but is
not actually a BT fit would be worse than no ranking, because it would be trusted. These
pin it against cases whose answer is known analytically, plus the two §2 disciplines the
module exists to enforce (both seats; a connected comparison graph).
"""
import math

import pytest

from harness.ladder import Duel, bradley_terry, run_ladder, shop_draw_summary, to_elo


def row(a, b, wins_a, wins_b, ties=0):
    return {"agent_a": a, "agent_b": b, "wins_a": wins_a, "wins_b": wins_b,
            "ties": ties, "errors": 0, "games": wins_a + wins_b + ties,
            "mean_margin_a": 0.0}


def test_even_series_gives_equal_strength():
    s = bradley_terry([row("a", "b", 5, 5)])
    assert s["a"] == pytest.approx(s["b"])


def test_stronger_agent_ranks_higher_and_scales_with_dominance():
    close = bradley_terry([row("a", "b", 6, 4)])
    wide = bradley_terry([row("a", "b", 9, 1)])
    assert close["a"] > close["b"]
    assert wide["a"] / wide["b"] > close["a"] / close["b"]


def test_ties_count_as_half_a_win_each():
    assert bradley_terry([row("a", "b", 0, 0, ties=10)])["a"] == pytest.approx(
        bradley_terry([row("a", "b", 5, 5)])["a"])


def test_prior_keeps_an_undefeated_agent_finite():
    """A graded bench is designed to contain agents the challenger sweeps 100%."""
    s = bradley_terry([row("a", "b", 10, 0)])
    assert math.isfinite(s["a"]) and s["a"] > s["b"] > 0


def test_transitivity_is_inferred_through_a_shared_opponent():
    """The whole point of BT over win rate: `a` never plays `c`, but outranks it."""
    s = bradley_terry([row("a", "b", 9, 1), row("b", "c", 9, 1)])
    assert s["a"] > s["b"] > s["c"]


def test_beating_a_strong_opponent_outranks_beating_a_weak_one():
    """The defect this whole module exists to fix — win rate cannot tell these apart."""
    rows = [
        row("strong", "weak", 10, 0),      # establishes the gradient
        row("x", "strong", 6, 4),          # x beat the strong one 60%
        row("y", "weak", 6, 4),            # y beat the weak one 60%
    ]
    s = bradley_terry(rows)
    assert s["x"] > s["y"], "identical 60% records must not produce identical strengths"


def test_to_elo_is_400_points_per_ten_times_strength_anchored_at_the_mean():
    elo = to_elo({"a": 10.0, "b": 1.0})
    assert elo["a"] - elo["b"] == pytest.approx(400.0)
    assert (elo["a"] + elo["b"]) / 2 == pytest.approx(1500.0)


def test_bradley_terry_on_no_rows_is_empty_not_an_error():
    assert bradley_terry([]) == {}
    assert to_elo({}) == {}


def test_duel_row_reports_both_seats_separately():
    """§2.1.1 — an agent that wins only from seat 0 has a market-ordering dependency."""
    d = Duel("a", "b", (0, 1))
    d.wins_a, d.wins_b = 2, 2
    d.wins_a_by_seat = {0: 2, 1: 0}
    d.games_by_seat = {0: 2, 1: 2}
    r = d.row()
    assert (r["wins_a_seat0"], r["games_seat0"]) == (2, 2)
    assert (r["wins_a_seat1"], r["games_seat1"]) == (0, 2)


def test_shop_draw_summary_flags_zero_drain_towns():
    """R21 — a 0-YARN_STORE town (34% of towns) is a different game (§4.1b)."""
    towns = [["YARN_STORE", "SMOOTHIE_SHOP"], ["SMOOTHIE_SHOP"], ["BAKERY"]]
    sd = shop_draw_summary(towns)
    assert sd["episodes"] == 3
    assert sd["products"]["WOOL"]["zero_drain_episodes"] == 2
    assert sd["products"]["WOOL"]["max"] == 2       # single-product shop, multiplier 2
    assert sd["products"]["STRAWBERRY"]["max"] == 1


def test_run_ladder_end_to_end_ranks_a_real_bench():
    """Smoke: a real (tiny) ladder run, with the trivial agents whose order is known."""
    result = run_ladder("starter", {"pass": "pass"}, [0], challenger_name="starter", steps=48)
    assert result["errors"] == 0
    names = [s["agent"] for s in result["standings"]]
    assert set(names) == {"starter", "pass"}
    # Every pairing is played from both seats: 1 seed x 2 seats.
    assert result["pairings"][0]["games"] == 2
    assert (result["pairings"][0]["games_seat0"], result["pairings"][0]["games_seat1"]) == (1, 1)
