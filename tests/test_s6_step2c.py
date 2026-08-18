"""S6 step 2c — pin the channel-wide town-INVARIANCE the STOP rests on (ROADMAP §4.3 / §3.3).

Phase 0.5 refuted the strawberry mechanism but drew its conclusion channel-wide from one product.
Step 2c tested the untested 58 WOOL/MILK steps (and WHEAT/MELON for context) and confirmed BRANCH (i):
the donor's action at every non-strawberry sell channel is invariant to the town's shop draw at the
step level — the level a 50-town majority vote operates on. These guards pin the load-bearing facts so
a future session cannot quietly re-open the 'erased conditioning' family:

  1. WOOL is the sharpest instrument (40% of towns never draw a YARN_STORE) yet the modal action never
     moves with the draw: 0 of the 20 contested steps with both sub-populations differ in modal action.
  2. MILK likewise (0 of its usable within-step splits differ).
  3. The residual is bounded — a whole-episode WOOL volume drift ~$1.2k/ep ceiling (over-estimate),
     6x below the strawberry ceiling already judged negligible — not a step-level rule.
  4. The vote already reproduces every product's modal per-episode volume (WOOL 200, MILK 296, WHEAT
     457, STRAWBERRY 290, MELON 114) — nothing erased to restore.
  5. FERTILIZER has no shop channel at all (analytic elimination, the largest disagreeing channel).

They skip when the gitignored donor streams are absent (§2.4b), so a public checkout stays green.
"""
import pytest

from analysis.s6_step2b_phase05 import RECON, ARCHIVE
from analysis.s6_step2c import sweep, SHOPS

_recon_present = RECON.exists()
_traces_present = False
if _recon_present:
    import json
    _eps = json.loads(RECON.read_text())["episodes_used"]
    _traces_present = all((ARCHIVE / f"{eid}.json").exists() for eid, _seat in _eps)

requires_streams = pytest.mark.skipif(
    not (_recon_present and _traces_present),
    reason="gitignored reconstruction / donor replays absent (§2.4b)")


@pytest.fixture(scope="module")
def rec():
    return sweep()


@requires_streams
def test_verdict_is_branch_i_channel_wide(rec):
    assert rec["verdict"].startswith("BRANCH (i)")


@requires_streams
def test_wool_action_is_invariant_to_the_yarn_draw(rec):
    """WOOL is the sharpest case (40% of towns draw zero yarn); the modal action never moves with
    the draw at any contested step where both sub-populations are present."""
    ws = rec["products"]["WOOL"]["within_step_drain_split"]
    assert ws["n_contested_steps_with_both_subpops"] >= 15   # a real, non-thin drain split exists
    assert ws["n_steps_modal_action_differs"] == 0           # and the action never conditions on it


@requires_streams
def test_milk_action_is_invariant_to_the_shop_draw(rec):
    ws = rec["products"]["MILK"]["within_step_drain_split"]
    assert ws["n_steps_modal_action_differs"] == 0


@requires_streams
def test_wool_shop_correlation_is_near_zero(rec):
    """corr(units sold, shop count) at contested steps: own shed carries it, shop identity ~0."""
    c = rec["products"]["WOOL"]["feature_corr_with_units"]
    assert abs(c["shops"]) < 0.2
    assert c["shed"] > c["shops"]


@requires_streams
def test_wool_drift_ceiling_is_bounded_and_below_strawberry(rec):
    """The one residual is a whole-episode volume drift, not a step rule — an over-estimated ceiling
    well below the ~$7.8k strawberry ceiling already judged negligible."""
    dc = rec["products"]["WOOL"]["drift_ceiling"]
    assert dc is not None
    assert 0 < dc["ceiling_dollars_per_ep"] < 2000


@requires_streams
def test_vote_reproduces_every_products_modal_volume(rec):
    """Nothing was erased to restore: the majority-vote reconstruction emits each product's modal
    per-episode volume."""
    for p in ("WOOL", "MILK", "WHEAT", "STRAWBERRY", "MELON"):
        assert rec["products"][p]["vote"]["reproduces_modal"], p


@requires_streams
def test_fertilizer_has_no_shop_channel(rec):
    """FERTILIZER — the largest disagreeing channel (53 steps) — drains into no shop and is excluded
    from TOWN_CENTER_PRODUCTS, so there is no town-conditioning channel to have been erased."""
    assert "FERTILIZER" not in {p for prods in SHOPS.values() for p in prods}
    assert rec["fertilizer_channel"]["in_any_SHOPS_entry"] is False
    assert rec["fertilizer_channel"]["in_TOWN_CENTER_PRODUCTS"] is False
