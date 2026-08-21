"""S7 leg 0 — pin the deployment-neighbourhood census (ROADMAP §1.1, §3.4).

The pass replaces three standing ladder readings. Guards pin each one, because each is now load-
bearing for how every future arm is judged:

  1. The win rate falls across the episode sequence — the "65% stable" was the placement burst.
  2. The converged win rate (controlled for the opponent's submission actually being the one on
     the board) is near or below 50%, i.e. Elo-compatible with our own rating. Discharges R36.
  3. The town's premium drain moves bank (2e: r = +0,6) and does NOT move the win rate. This is
     the measurement that demotes `median_bank` in §2.1.4.
  4. Frozen-agent decay is monotone in the rating band, so a decay figure is band-local.
  5. The ladder deflates at a fixed rank slot, so a score delta is unreadable without a rank.
  6. The deployment neighbourhood is wide (>100 distinct opponents), which no six-tier reference
     bench can represent.

Needs the gitignored live replays and both leaderboard snapshots; skips on a public checkout.
"""
import pytest

from analysis.s7_ladder_census import EP_CSV, LB_SNAPSHOTS, LIVE, ROOT

_live_present = any(LIVE.glob("*.json*")) and EP_CSV.exists()
_lb_present = all((ROOT / "data" / "archive" / "raw" / rel).exists() for _, rel in LB_SNAPSHOTS)

requires_live = pytest.mark.skipif(
    not (_live_present and _lb_present),
    reason="gitignored live replays / leaderboard snapshots absent (§2.4b)")


@pytest.fixture(scope="module")
def result():
    from analysis.s7_ladder_census import run
    return run()


@requires_live
def test_win_rate_declines_across_the_sequence(result):
    """The placement burst inflates the win rate; it falls as matchmaking catches up."""
    blocks = result["leg_a_live_panel"]["blocks"]
    assert [b["block"] for b in blocks] == ["first", "middle", "last"]
    assert blocks[0]["win_rate"] > blocks[-1]["win_rate"] + 0.10
    assert blocks[0]["win_rate"] > 0.60          # the burst read that the 2e brief pinned
    assert result["leg_a_live_panel"]["win_rate"] < 0.60


@requires_live
def test_converged_win_rate_is_elo_compatible(result):
    """Controlled and converged we win about half — R36's Elo-incompatible band table is void."""
    c = result["leg_c_opponent_strength"]
    assert c["converged_n"] >= 30
    assert c["converged_win_rate"] < 0.55
    # and it degrades against stronger opponents rather than improving (R36's charge)
    bands = c["converged_controlled"]
    assert len(bands) >= 2
    assert bands[0]["win_rate"] > bands[-1]["win_rate"]


@requires_live
def test_the_control_changes_the_answer(result):
    """The frozen-submission control is not cosmetic: it cuts the sample and reshapes it."""
    c = result["leg_c_opponent_strength"]
    assert c["matched_controlled"] < c["matched_raw"] * 0.80


@requires_live
def test_drain_moves_bank_but_not_wins(result):
    """§4.1b's town draw is common-mode: 2e measured r(drain,bank)=+0,6; wins are flat/inverted."""
    rows = [r for r in result["leg_a_live_panel"]["drain_win_rate"] if r["n"] >= 7]
    assert len(rows) >= 5
    lo = [r["win_rate"] for r in rows[:2]]
    hi = [r["win_rate"] for r in rows[-2:]]
    # rich towns bank far more (2e: $54k at drain 5 -> $141k at drain 13) and win no more often
    assert min(hi) <= max(lo) + 0.05


@requires_live
def test_frozen_decay_is_monotone_in_the_band(result):
    """A decay rate is band-local: the top bleeds an order of magnitude faster than the bottom."""
    bands = {b["band"]: b for b in result["leg_b_deflation"]["bands"]}
    top = bands["2800-9999"]["per_day"]
    bottom = bands["0-800"]["per_day"]
    assert top < -20.0
    assert bottom > -10.0
    assert top < bottom


@requires_live
def test_the_ladder_deflates_at_a_fixed_rank(result):
    """Score at a fixed rank slot falls in the upper ladder — a score delta needs a rank beside it."""
    slots = {s["rank"]: s for s in result["leg_b_deflation"]["rank_slots"]}
    assert slots[100]["per_day"] < -10.0
    straf = next(t for t in result["leg_b_deflation"]["tracked"] if t["team"] == "STRAF")
    assert straf["frozen"] is True
    assert straf["d_score"] < 0 < straf["d_rank"]      # score fell, rank rose


@requires_live
def test_neighbourhood_is_wide(result):
    """165 distinct opponents over 178 episodes — a six-tier reference bench cannot represent it."""
    a = result["leg_a_live_panel"]
    assert a["distinct_opponents"] > 100
    assert a["repeat_share"] < 0.30


@requires_live
def test_verdict_string_present(result):
    """R35: the derived artefact carries its own verdict."""
    assert "CONVERGED" in result["verdict"]
    assert "DEFLATION" in result["verdict"]
