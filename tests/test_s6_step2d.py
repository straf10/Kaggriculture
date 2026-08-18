"""S6 step 2d leg A — pin the branch (iv) mechanism the STOP-and-re-brief rests on (ROADMAP §3.3).

Steps 2b/2c closed the MARKET layer as town-invariant. Step 2d ran the same instrument on the 88
PRODUCTION-disagreement steps no prior pass had examined and confirmed BRANCH (iv): the donor's farm
hands run a closed-loop, town-reactive tile control the fixed-index 50-town vote cannot carry — but its
recoverable dollar surface is the own-farm wheat loss step 2a already bounded ($597/ep, below the gate
on its free half, 0.09% of the gap). These guards pin the load-bearing facts so a future session cannot
misread the finding in either direction — neither "it's the fixed-4 variant again" (it is not) nor
"town-reactive, therefore go build it" (bounded small, on the shelf):

  1. The residual is NOT the fixed {43,45,46,49} variant — it is carried by many towns (town-varying).
  2. The main-farmer script is town-INVARIANT (0/88): the disagreement is entirely in the hands.
  3. The DECISIVE tile-reactivity split: a majority of hand-slot disagreements track a disjoint local
     tile content at an identical board position — closed-loop control.
  4. Worker count is NOT the channel (§4.5b headcount hypothesis): far fewer steps than tile content.
  5. The vote reproduces the modal production action at every disagreement step (faithful open-loop).

leg A needs only the gitignored donor streams (no kaggle_environments); it skips on a public checkout.
"""
import pytest

from analysis.s6_step2b_phase05 import ARCHIVE, RECON

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
def a():
    from analysis.s6_step2d import leg_a
    return leg_a()


@requires_streams
def test_disagreement_set_matches_reconstruction(a):
    """The canonical token recomputed here reproduces the reconstruction's n_disagree_prod = 88."""
    import json
    n = json.loads(RECON.read_text())["n_disagree_prod"]
    assert a["n_disagree_prod"] == n == 88


@requires_streams
def test_residual_is_not_the_fixed4_variant(a):
    """Unlike the market channel, the production residual is town-varying — carried by many traces,
    not the fixed {43,45,46,49} late-season submission variant."""
    det = a["determinism"]
    assert det["residual_is_fixed4_variant"] is False
    assert det["n_carrier_traces"] >= 15


@requires_streams
def test_main_farmer_script_is_town_invariant(a):
    """The main farmer's op is identical across all 50 towns at every disagreement step; the
    disagreement lives entirely in the hands' tile-level actions."""
    ch = a["channel_decomposition"]
    assert ch["farmer_op_differs"] == 0
    assert ch["hands_content_differs"] >= 80


@requires_streams
def test_hands_are_closed_loop_tile_reactive(a):
    """DECISIVE: a majority of hand-slot disagreements have the deviator standing on a tile whose
    content is disjoint from the modal towns' — the hand reads the local board (closed-loop control a
    fixed-index vote cannot carry). Many occur at an identical board position (not positional drift)."""
    tr = a["tile_reactivity"]
    assert tr["hand_slot_disagreements"] >= 50
    assert tr["reactivity_rate"] >= 0.5          # >half track a disjoint local tile
    assert tr["pos_identical_across_towns"] >= 20  # same position, different action → reads the tile
    assert tr["involves_weed_tile"] >= 1          # the weedSpawnChance mechanism is present


@requires_streams
def test_worker_count_is_not_the_channel(a):
    """§4.5(b)'s worker-count-adaptation hypothesis predicts the disagreement in hands LENGTH; it is in
    hands CONTENT instead. Headcount jitter is a minority of the disagreement steps."""
    ch = a["channel_decomposition"]
    assert ch["worker_count_disagree_steps"] < ch["hands_content_differs"]


@requires_streams
def test_vote_reproduces_modal_production_everywhere(a):
    """The reconstruction is a faithful OPEN-LOOP copy: it emits the modal production action at every
    one of the 88 disagreement steps."""
    assert a["vote"]["reproduces_all"] is True
    assert a["vote"]["reproduces_modal_at"] == a["n_disagree_prod"]
