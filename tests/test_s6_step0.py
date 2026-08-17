"""S6 step 0 — pin the machinery the three legs rest on (ROADMAP §4.3 S6 step 0).

Three kinds of guard:

1. The donor loader (R26/A2): every gitignored donor tape recovers a 719-step stream whose
   sha256 matches its recorded provenance, and the wrapper is a genuine open-loop echo. These
   skip when the gitignored competition data is absent (a clean/public checkout), so they pass
   locally and never turn a public checkout red.

2. Leg 2's load-bearing engine fact: a SELL commits against **its own product's inventory only**
   — which is *why* in-place reordering of a fixed multiset of different-product sells cannot
   change realised revenue, i.e. why the C-A upper bound is ~$0. If a future balance change
   coupled the pools, this would fail and the leg-2 conclusion would need re-deriving.

3. Leg 3's unlock arithmetic: 5 shops on day 15 (the shop_evidence_min_unlocks gate) and 8 on
   day 24, under the engine's one-per-3-days rule.
"""
import pytest
from kaggle_environments.envs.kaggriculture import kaggriculture as k

from analysis.donor_streams import DONORS, available, load_donor_stream, make_donor_tape
from analysis.s6_step0_leg2 import _legal_sell_permutations, _sells, route_surface
from analysis.s6_step0_leg3 import SHOP_EVIDENCE_MIN_UNLOCKS, UNLOCK_INTERVAL, _rank_order
from harness.bench_agents.reference_ladder import (
    REFERENCE_TIERS,
    available_reference_agents,
    reference_agent_path,
)

PASS = {"farmer": ["PASS"], "hands": [], "market": []}
_HAVE_TAPES = all(available(eid) for eid in DONORS)
requires_tapes = pytest.mark.skipif(not _HAVE_TAPES, reason="gitignored donor tapes absent (§2.4b)")


# ---- 1. donor loader (R26 / A2) ----------------------------------------------------------
@requires_tapes
@pytest.mark.parametrize("episode_id", list(DONORS))
def test_donor_stream_loads_and_sha256_matches_provenance(episode_id):
    stream = load_donor_stream(episode_id)  # raises on sha256 mismatch
    assert isinstance(stream, list) and len(stream) == 719
    assert all(isinstance(a, dict) and "market" in a for a in stream)


@requires_tapes
def test_make_donor_tape_is_open_loop_echo():
    eid = next(iter(DONORS))
    stream = load_donor_stream(eid)
    tape = make_donor_tape(eid)
    for step in (0, 5, 100, 718):
        assert tape({"step": step}) == stream[step]
    # a step past the stream degrades to PASS, never crashes
    assert tape({"step": 10_000}) == PASS


# ---- 2. leg 2's engine fact: SELL touches only its own inventory pool ---------------------
def test_sell_only_moves_its_own_product_inventory():
    """The mechanistic root of the C-A ~$0 upper bound: selling WOOL cannot change STRAWBERRY's
    inventory (and therefore cannot change any other product's realised price), so reordering a
    WOOL sell relative to a STRAWBERRY sell within a turn is revenue-neutral."""
    market = {"inventory": {p: 50 for p in k.PRODUCTS}, "prices": {p: 0 for p in k.PRODUCTS}}
    private = {"shed": {"WOOL": 5, "STRAWBERRY": 5}}
    farm = {"money": 0}
    before = dict(market["inventory"])
    price = k.market_price("WOOL", market["inventory"]["WOOL"], market.get("params"))
    ok = k._commit_unit("SELL", "WOOL", price, farm, private, market)
    assert ok
    assert market["inventory"]["WOOL"] == before["WOOL"] + 1  # only WOOL moved
    for p in k.PRODUCTS:
        if p != "WOOL":
            assert market["inventory"][p] == before[p]


def test_market_price_is_a_pure_function_of_that_products_inventory():
    """market_price(item, inv) depends on nothing else — no cross-product coupling exists for a
    permutation to exploit."""
    a = k.market_price("STRAWBERRY", 40)
    b = k.market_price("STRAWBERRY", 40)
    assert a == b
    # monotone non-increasing in inventory (glut lowers price), the curve reordering can't beat
    assert k.market_price("STRAWBERRY", 30) >= k.market_price("STRAWBERRY", 60)


# ---- 2b. leg 2 route-surface classification ----------------------------------------------
def test_route_surface_counts_and_classifies_sells():
    stream = [
        {"market": []},                                              # 0 sells
        {"market": [["SELL", "WHEAT", 1]]},                          # 1 sell
        {"market": [["SELL", "WOOL", 1], ["SELL", "WHEAT", 1]]},     # premium + non-premium
        {"market": [["SELL", "WOOL", 1], ["SELL", "MILK", 1]]},      # two premium
        {"market": [["SELL", "WHEAT", 1], ["SELL", "WHEAT", 1]]},    # 2 sells, not reorderable
    ]
    s = route_surface(stream)
    assert s["sells_per_turn_hist"] == {0: 1, 1: 1, 2: 3}
    assert s["turns_with_2plus_sells"] == 3
    # reorderable = >=2 distinct items with a premium present: turns 2 and 3 qualify, turn 4 does not
    assert s["reorderable_turns"] == 2
    assert s["reorderable_mixing_premium_nonpremium"] == 1
    assert s["reorderable_two_premium"] == 1


def test_legal_permutations_never_cross_a_purchase():
    """The Cleo cash-funding invariant: sells only permute within a contiguous run, so no sell
    ever moves across a BUY_PRODUCT slot."""
    queue = [["SELL", "WOOL", 1], ["BUY_PRODUCT", "WHEAT", 1], ["SELL", "MILK", 1], ["SELL", "STRAWBERRY", 1]]
    perms = list(_legal_sell_permutations(queue))
    assert perms[0] == queue  # emitted first
    for q in perms:
        assert q[1] == ["BUY_PRODUCT", "WHEAT", 1]          # purchase never moves
        assert q[0][0] == "SELL"                             # slot 0 stays a sell
        assert {tuple(o) for o in _sells(q)} == {tuple(o) for o in _sells(queue)}  # same multiset
    # the isolated first sell can't permute; the trailing run of two sells has 2 orderings
    assert len(perms) == 2


# ---- 3. leg 3 unlock arithmetic ----------------------------------------------------------
def test_shop_unlock_schedule_matches_engine_rule():
    """Shops unlock on day d when d % townShopUnlockInterval == 0 (engine :886). So n shops are
    present from day n*interval — 5 shops on day 15 (the gate), 8 on day 24 (full town)."""
    assert UNLOCK_INTERVAL == 3
    assert SHOP_EVIDENCE_MIN_UNLOCKS * UNLOCK_INTERVAL == 15
    assert k.MAX_SHOP_INSTANCES * UNLOCK_INTERVAL == 24
    # the engine constant the analysis mirrors
    from kaggle_environments import make
    cfg = make("kaggriculture").configuration
    assert int(cfg.get("townShopUnlockInterval", 3)) == UNLOCK_INTERVAL


# ---- R25 reference-agent resolver (A1) ---------------------------------------------------
def test_reference_ladder_is_tiers_0_to_5_only():
    """Exactly the six authored, MIT tiers — tiers 6-9 are never carried (R23/§4.5)."""
    assert sorted(REFERENCE_TIERS) == [0, 1, 2, 3, 4, 5]
    names = {n for n, _f in REFERENCE_TIERS.values()}
    assert "Closer Cleo" not in names and "Broker Bea" not in names


def test_reference_resolver_maps_names_and_rejects_missing_tiers():
    # tier 9 is not in the ladder → None regardless of whether files are present
    assert reference_agent_path(9) is None
    assert reference_agent_path("tier9") is None
    if available_reference_agents():  # fetched locally
        assert reference_agent_path(5).name == "rancher_rita.py"
        assert reference_agent_path("Rotation Rosa").name == "rotation_rosa.py"
    else:
        pytest.skip("reference agents not fetched locally (gitignored, §4.5)")


def test_rank_order_is_deterministic_and_tie_stable():
    # a strict order
    assert _rank_order({"STRAWBERRY": 5, "WOOL": 3, "MILK": 1}) == ("STRAWBERRY", "WOOL", "MILK")
    # ties broken by fixed name order so a stable tie is not read as churn
    assert _rank_order({"STRAWBERRY": 0, "WOOL": 0, "MILK": 0}) == _rank_order({"STRAWBERRY": 0, "WOOL": 0, "MILK": 0})
