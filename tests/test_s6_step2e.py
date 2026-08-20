"""S6 step 2e — pin the loss-tail analysis (ROADMAP §3.3).

The pass asks whether 2d's desync mechanism or §4.1b's town composition explains the 2.14x bank
spread across the 84 ladder episodes. Guards pin the load-bearing findings:

  1. The set is 84 (the STRAF-vs-STRAF validation episode is excluded).
  2. Leg A: decay counters are uniform — the own-farm loss does not vary across episodes.
  3. Leg B: desync depth does not correlate with final bank.
  4. Leg C: shop composition (premium drain) explains a substantial fraction of bank variance.
  5. Leg C: desync adds nothing after composition is partialled out.
  6. Leg D: episodes flippable by full recovery are a small fraction.

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
    """84 ladder episodes; the STRAF-vs-STRAF validation episode is excluded."""
    assert result["n_episodes"] == 84


@requires_live
def test_decay_uniform(result):
    """Own-farm decay is uniform across episodes — the loss tail is not in weed/decay."""
    dd = result["legA"]["decay_units_distrib"]
    assert dd["max"] - dd["min"] <= 5
    assert dd["stdev"] < 2.0
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
    """Episodes flippable by full desync recovery are a small fraction (≤ 5% of total)."""
    assert result["legD"]["n_flippable"] <= 4
    assert result["legD"]["flipped_share_of_total"] <= 0.05


@requires_live
def test_win_rate_consistent(result):
    """Win rate is consistent with the brief's 65% stable convergence."""
    assert 0.55 <= result["win_rate"] <= 0.80
