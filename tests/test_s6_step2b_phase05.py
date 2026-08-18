"""S6 step 2b Phase 0.5 — pin the recovered-rule facts the STOP rests on (ROADMAP §4.3 S6 step 2b).

The pass's one mechanism was *"the vote erased ReCurSiON's town-conditioned strawberry sell-timing."*
Phase 0.5 refuted it: the rule is a fixed global calendar (hour-0 pulse), town-invariant, already
reproduced by the vote. These guards pin the three load-bearing numbers so a future session cannot
quietly re-inflate the lever:

  1. Determinism — 46/50 traces sell an identical 290-unit strawberry total; the disagreement is one
     fixed 4-trace subset, not 50 towns conditioning.
  2. Invariance — at the biggest contested sell-step the action is constant while the town's price and
     strawberry-shop draw span their full range (⇒ not conditioned on shop identity or price).
  3. Own-state — units sold track own shed inventory (r high), shop identity ~0.

They skip when the gitignored donor streams are absent (§2.4b), so a public checkout stays green.
"""
import pytest

from analysis.s6_step2b_phase05 import RECON, ARCHIVE, recover

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
    return recover()


@requires_streams
def test_strawberry_schedule_is_deterministic_across_towns(rec):
    """46 of 50 traces sell an identical strawberry total; the outliers are one fixed subset."""
    d = rec["determinism"]
    assert d["per_trace_total_modal"] == 290
    assert d["n_traces_at_modal_total"] == 46
    assert [o["trace"] for o in d["outlier_traces"]] == [43, 45, 46, 49]
    # every contested sell-step is carried by exactly those four traces — a phase variant, not 50 towns
    assert set(d["disagreement_carried_by_traces"]) == {43, 45, 46, 49}


@requires_streams
def test_action_is_invariant_to_shop_identity_and_price(rec):
    """The decisive refutation of shop-identity conditioning: one action across all towns while the
    strawberry price and shop draw span their full range."""
    inv = rec["invariance_at_biggest_sell_step"]
    assert inv["n_traces_at_modal"] == rec["n_traces"]          # all towns take the modal action
    assert inv["price_max"] - inv["price_min"] >= 50            # price genuinely varied across towns
    assert inv["str_shops_max"] > inv["str_shops_min"]         # the strawberry drain genuinely varied


@requires_streams
def test_units_track_own_shed_not_shop_identity(rec):
    """Units sold are own inventory, not the town's drain."""
    c = rec["feature_corr_with_units"]
    assert c["shed_str"] > 0.8                    # own state carries it
    assert abs(c["str_shops"]) < 0.2              # shop identity does not


@requires_streams
def test_vote_already_reproduces_the_fixed_schedule(rec):
    """The reconstruction sells the 46-trace strawberry total — there is nothing erased to restore."""
    assert rec["reconstruction_strawberry_units"] == rec["determinism"]["per_trace_total_modal"]


@requires_streams
def test_calendar_is_the_hour0_pulse(rec):
    """The rule is keyed to the once-daily town-center tick (hour 0), a global constant."""
    assert rec["calendar"]["hour0_share"] > 0.6
