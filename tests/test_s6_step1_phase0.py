"""S6 step 1 Phase 0 — pin the donor-selection machinery (ROADMAP §4.3 S6 step 1).

Phase 0 is "the whole risk": it decides whether S6 builds a reconstruction or STOPs to C-C. These
guards pin the three load-bearing pieces of that decision, all pure-python (no engine, no archive):

1. Stream alignment — s6_step1_phase0._seat_streams reads the SAME decision sequence as
   s1_extract_donors.action_stream (steps[1:], farmer+hands = the production channel, market
   separate, inactive/None -> an explicit PASS token). If this drifts, every fingerprint and every
   agreement rate is measuring the wrong thing.
2. The agreement math — the per-decision modal-action share, per channel, that criterion 2 rests on
   (reject a donor whose traces agree at ~60%). Pinned on synthetic traces with a known answer.
3. Premium-sell detection — the restriction of market agreement to the contested calendar.
"""
from analysis.s6_step1_phase0 import (
    OPEN_STEPS,
    _agreement_for_traces,
    _canon,
    _premium_sold_at,
    _seat_streams,
    _sha,
)
from analysis.s6_step1_reconstruct import PASS_ACTION, _decanon_prod


def _step(farmer, hands, market, status="ACTIVE"):
    return {"action": {"farmer": farmer, "hands": hands, "market": market}, "status": status}


# ---- 1. stream alignment -----------------------------------------------------------------
def test_seat_streams_reads_decision_sequence_like_s1():
    # steps[0] is the pre-first-action reset record and must be dropped (s1_extract_donors); the
    # returned streams therefore have len(steps)-1 entries, entry i = steps[i+1][seat].action.
    steps = [
        [_step(["PASS"], [], []), _step(["PASS"], [], [])],                 # 0: reset, dropped
        [_step(["BUILD_PASTURE"], [], [["HIRE"]]), _step(["PASS"], [], [])],  # 1 -> stream[0]
        [_step(["PLANT", "WHEAT"], [["WEST"]], [["SELL", "WOOL", 1]]),
         _step(["PASS"], [], [])],                                          # 2 -> stream[1]
    ]
    prod, market, status = _seat_streams(steps, 0)
    assert len(prod) == len(market) == len(status) == len(steps) - 1
    # production channel = [farmer, hands] combined; market channel separate
    assert prod[0] == _canon([["BUILD_PASTURE"], []])
    assert market[0] == _canon([["HIRE"]])
    assert prod[1] == _canon([["PLANT", "WHEAT"], [["WEST"]]])
    assert market[1] == _canon([["SELL", "WOOL", 1]])
    assert status == ["ACTIVE", "ACTIVE"]


def test_seat_streams_maps_missing_action_to_pass_token():
    steps = [
        [_step(["PASS"], [], [])],
        [{"action": None, "status": "INACTIVE"}],       # dead seat -> explicit PASS, never crashes
    ]
    prod, market, status = _seat_streams(steps, 0)
    assert prod == ["PASS"] and market == ["[]"] and status == ["INACTIVE"]


def test_open_fingerprint_window_and_hash_are_stable():
    assert OPEN_STEPS == 48
    # _sha/_canon are deterministic and order-preserving (fingerprints must not depend on dict order)
    assert _sha("abc") == _sha("abc")
    assert _canon([["A"], ["B"]]) != _canon([["B"], ["A"]])   # order matters (it is a sequence)
    assert _canon({"x": 1, "y": 2}) == _canon({"y": 2, "x": 1})  # dict order does not


# ---- 2. the agreement math ---------------------------------------------------------------
def test_agreement_share_is_modal_action_fraction_per_channel():
    # 4 traces, 2 steps. prod step0: 3x"A",1x"B" -> 0.75 ; step1: all "P" -> 1.0  => mean 0.875
    # market step0: all "m" -> 1.0 ; step1: 2x"x",2x"y" -> 0.5                    => mean 0.75
    traces = [
        (["A", "P"], ["m", "x"]),
        (["A", "P"], ["m", "x"]),
        (["A", "P"], ["m", "y"]),
        (["B", "P"], ["m", "y"]),
    ]
    a = _agreement_for_traces(traces)
    assert a["n_traces"] == 4 and a["n_steps"] == 2
    assert a["prod_agreement"] == 0.875
    assert a["market_agreement"] == 0.75
    assert a["prod_unanimous_frac"] == 0.5     # step1 only
    assert a["market_unanimous_frac"] == 0.5   # step0 only
    assert a["n_disagree_prod"] == 1 and a["n_disagree_market"] == 1


def test_agreement_perfect_when_all_traces_identical():
    traces = [(["A", "B"], ["m", "n"])] * 3
    a = _agreement_for_traces(traces)
    assert a["prod_agreement"] == 1.0 and a["market_agreement"] == 1.0
    assert a["prod_unanimous_frac"] == 1.0 and a["market_unanimous_frac"] == 1.0
    assert a["n_disagree_prod"] == 0 and a["n_disagree_market"] == 0


def test_agreement_aligns_traces_of_unequal_length_to_the_shortest():
    traces = [(["A", "A", "A"], ["m", "m", "m"]), (["A", "A"], ["m", "m"])]
    a = _agreement_for_traces(traces)
    assert a["n_steps"] == 2  # truncated to min length; no index error


# ---- 3. premium-sell detection -----------------------------------------------------------
def test_premium_sold_at_detects_only_premium_sells():
    assert _premium_sold_at(_canon([["SELL", "STRAWBERRY", 3]]))
    assert _premium_sold_at(_canon([["SELL", "WOOL", 1], ["SELL", "WHEAT", 1]]))
    assert not _premium_sold_at(_canon([["SELL", "WHEAT", 2]]))       # non-premium sell
    assert not _premium_sold_at(_canon([["BUY_PRODUCT", "STRAWBERRY", 1]]))  # a buy, not a sell
    assert not _premium_sold_at("[]")


def test_market_premium_agreement_restricted_to_premium_steps():
    # step0 sells a premium (agreement 0.5), step1 sells only wheat (excluded from premium subset)
    sell_str = _canon([["SELL", "STRAWBERRY", 1]])
    sell_str2 = _canon([["SELL", "STRAWBERRY", 2]])
    wheat = _canon([["SELL", "WHEAT", 1]])
    traces = [(["A", "A"], [sell_str, wheat]), (["A", "A"], [sell_str2, wheat])]
    a = _agreement_for_traces(traces)
    assert a["n_premium_sell_steps"] == 1
    assert a["market_agreement_premium_steps"] == 0.5   # only the premium step counts


# ---- 4. reconstruction decanon (majority-vote reassembly) ---------------------------------
def test_decanon_prod_roundtrips_the_production_channel():
    # the reconstruction reassembles [farmer, hands] from the modal production canon; it must be the
    # exact inverse of _canon so the majority-vote route is a legal action stream, not garbage.
    farmer, hands = ["PLANT", "WHEAT"], [["WEST"], ["PICKUP", "COW", 1]]
    canon = _canon([farmer, hands])
    assert _decanon_prod(canon) == (farmer, hands)


def test_decanon_prod_handles_the_inactive_pass_sentinel():
    # an inactive/None step is stored as the sentinel "PASS" (not JSON) and must decanon to a real
    # farmer PASS rather than raising a JSONDecodeError mid-reconstruction.
    assert _decanon_prod("PASS") == (["PASS"], [])
    assert PASS_ACTION == {"farmer": ["PASS"], "hands": [], "market": []}
