"""S6 step 2e — pin the loss-tail analysis (ROADMAP §3.3).

The pass asks whether 2d's desync mechanism or §4.1b's town composition explains the 2.14x bank
spread across the 84 ladder episodes. Guards pin the load-bearing findings:

  1. Every held ladder replay is used; self-play validation episodes are excluded.
  2. Leg A: decay counters do not track bank — the loss tail is not in weed/decay.
  3. Leg B: desync depth does not correlate with final bank.
  4. Leg C: shop composition (premium drain) explains a substantial fraction of bank variance.
  5. Leg C: desync adds nothing after composition is partialled out.
  6. Leg D: episodes flippable by full recovery are a small fraction.

🔴 **Re-pinned 2026-08-20 (S7 leg 0) after the live set grew 84 → 178 episodes.** The pass
REPLICATED on the 2,1x sample and got sharper — r(drain,bank) 0,579 -> 0,605, partial
r(desync|drain) +0,007 -> -0,029, flippable 2/84 (+2,4 pts) -> 11/178 (+6,2 pts), both still
negligible. Two guards were phrased against the smaller sample and are corrected here rather
than frozen: the episode count is no longer a constant, and leg A's claim is "does not track
bank" (r = -0,029) — the raw range widened 12-15 -> 12-21 on 2,1x the draws while the stdev
stayed 0,6, so a range test was the wrong instrument for it. `test_win_rate_consistent` is
DELETED: S7 leg 0 measured the 65% it pinned as the placement burst (converged rate 43,4%).

Needs the gitignored live replays; skips on a public checkout.
"""
import pytest

from analysis.s6_step2b_phase05 import LIVE

_live_present = any(LIVE.glob("*.json*"))

requires_live = pytest.mark.skipif(
    not _live_present,
    reason="gitignored live replays absent (§2.4b)")


@pytest.fixture(scope="module")
def result():
    from analysis.s6_step2e import run
    return run()


@requires_live
def test_episode_count(result):
    """Every held ladder episode is used; self-play validation episodes are excluded."""
    assert result["n_episodes"] >= 84


@requires_live
def test_decay_does_not_track_bank(result):
    """Own-farm decay does not track the bank outcome — the loss tail is not in weed/decay."""
    dd = result["legA"]["decay_units_distrib"]
    assert dd["stdev"] < 2.0
    assert abs(result["legA"]["r_decay_bank"]) < 0.15
    sub = result["legA"]["sub70k"]
    top = result["legA"]["top_quartile"]
    assert abs(sub["decay_mean"] - top["decay_mean"]) < 2.0


@requires_live
def test_desync_does_not_correlate_with_bank(result):
    """Desync depth is uncorrelated with final bank — no tail in desyncs."""
    r = result["legB"]["r_desync_bank"]
    assert r is not None
    assert abs(r) < 0.15


@requires_live
def test_composition_explains_bank_spread(result):
    """Shop composition (premium drain) explains a meaningful fraction of bank variance."""
    r = result["legC"]["r_drain_bank"]
    assert r is not None
    assert r > 0.4
    r2 = result["legC"]["r2_drain_bank"]
    assert r2 is not None
    assert r2 > 0.15


@requires_live
def test_desync_adds_nothing_after_composition(result):
    """After partialling out composition, desync explains nothing."""
    pr = result["legC"]["partial_r_desync_given_drain"]
    assert pr is not None
    assert abs(pr) < 0.15


@requires_live
def test_flipped_episodes_small(result):
    """Episodes flippable by full desync recovery are a small fraction (<= 10% of total)."""
    assert result["legD"]["flipped_share_of_total"] <= 0.10

