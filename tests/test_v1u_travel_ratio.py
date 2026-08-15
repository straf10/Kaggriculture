"""v1u — guards for the travel-ratio (greedy-regret) diagnostic's non-trivial helpers.

`analysis/v1u_travel_ratio.py` decides whether deferred item ④ (min-cost matching) gets built,
so its two load-bearing helpers are pinned here:

  * `_greedy_trace` must reconstruct `scheduler.assign()` byte-for-byte (the runtime guard raises
    on any mismatch; this pins a crafted case so a regression is caught in CI, not mid-run).
  * `_rematch_optimal` must be the *conservative* optimum: it re-matches only the free units over
    the exact set greedy served (regret ≥ 0, never negative), pins committed + allowed_unit pairs
    (G-2), and honours cargo eligibility (G-4). The classic greedy pathology — a unit consumed by
    the task that wins the key first, stranding a second task on a farther unit — must show a
    positive, correctly-valued regret.
  * `_max_cardinality` must count a legal per-tier max matching (the secondary "stranded task"
    signal), including the FEED/wheat case where cargo eligibility caps it.
"""
import copy

from agent.config import CONFIG
from agent.scheduler import Task, assign
from agent.state import parse

from analysis.v1u_travel_ratio import (
    _carries_cargo,
    _greedy_trace,
    _max_cardinality,
    _rematch_optimal,
)


def _snapshot(farmer, hands, *, inventories=None, seeds=None):
    """A minimal snapshot on an empty NW farm with `farmer`/`hands` at the given positions."""
    n_units = 1 + len(hands)
    inventories = inventories or [{} for _ in range(n_units)]
    obs = {
        "player": 0,
        "step": 0,
        "day": 0,
        "hour": 0,
        "farms": [
            {
                "money": 3000,
                "tiles": [[None] * 10 for _ in range(10)],
                "farmer": list(farmer),
                "hands": [list(h) for h in hands],
                "unlocked_quadrants": ["NW"],
                "hires_today": 0,
            },
            {"money": 0, "tiles": [[None] * 10 for _ in range(10)], "farmer": [0, 0], "hands": []},
        ],
        "private": {"shed": {}, "seeds": dict(seeds or {}), "inventories": inventories},
        "market": {"inventory": {}, "prices": {}},
        "town": {"unlocked_shops": []},
    }
    return parse(copy.deepcopy(obs))


def _water(x, y):
    """A non-urgent, unrestricted priority-0 WATER task (deadline far ⇒ never in the urgent tier)."""
    return Task(id=f"water:{x}:{y}", kind="WATER", pos=(x, y), priority=0, deadline_step=700)


# ---------------------------------------------------------------- greedy reconstruction fidelity

def test_greedy_trace_matches_real_assign_on_the_stranding_case():
    """Farmer is the best fit for both tasks; greedy consumes it on the tiebreak winner and
    strands the second on the farther hand — the documented 2× pathology. The reconstruction's
    actions/commitments must equal the real assign()'s, exactly (the runtime void-guard)."""
    snap = _snapshot((5, 5), [(5, 0)])
    tasks = [_water(5, 4), _water(4, 5)]
    trace = _greedy_trace(tasks, snap, {}, CONFIG)
    real = assign(tasks, snap, {})  # config defaults to CONFIG
    assert (trace.farmer, trace.hands, trace.commitments) == real
    # farmer -> (5,4) on the pos_y tiebreak (y=4 < y=5), hand -> (4,5).
    assigned = {u: t.pos for u, t, _d, _sw in trace.assignments}
    assert assigned == {0: (5, 4), 1: (4, 5)}


# ------------------------------------------------------------------------- re-match regret value

def test_rematch_optimal_uncrosses_the_stranded_assignment():
    """Greedy pays 1 + 6 = 7 (farmer->(5,4) dist 1, hand->(4,5) dist 6). The min-distance
    re-match of the *same two tiles* is farmer->(4,5)=1, hand->(5,4)=4 ⇒ 5. Regret = 2."""
    snap = _snapshot((5, 5), [(5, 0)])
    tasks = [_water(5, 4), _water(4, 5)]
    trace = _greedy_trace(tasks, snap, {}, CONFIG)
    greedy_travel = sum(d for _u, _t, d, _sw in trace.assignments)
    optimal_travel = _rematch_optimal(trace.assignments, snap, {})
    assert greedy_travel == 7
    assert optimal_travel == 5
    assert greedy_travel - optimal_travel == 2


def test_rematch_optimal_never_beats_an_already_optimal_greedy():
    """When the nearest-first greedy is already optimal, regret is exactly 0 (never negative)."""
    snap = _snapshot((0, 0), [(9, 0)])
    tasks = [_water(0, 0), _water(9, 0)]  # each unit sits on its own task
    trace = _greedy_trace(tasks, snap, {}, CONFIG)
    greedy_travel = sum(d for _u, _t, d, _sw in trace.assignments)
    assert greedy_travel == _rematch_optimal(trace.assignments, snap, {})


def test_rematch_optimal_pins_committed_and_allowed_unit_pairs():
    """A committed pair (G-2) and an allowed_unit pair are never re-matched away, even when a
    swap would cut distance — a legal item-④ must keep them, so they count at their own cost."""
    snap = _snapshot((5, 5), [(5, 0)])
    # Hand-built greedy assignments: unit 0 committed to the far tile, unit 1 on the near one.
    # A free re-match would swap them; pinning unit 0 (committed) forbids it.
    far = _water(4, 5)
    near = _water(5, 4)
    assignments = [(0, far, 6, 0), (1, near, 4, 1)]  # unit0 dist 6 (committed), unit1 dist 4
    committed = {0: far.id}
    # unit 0 is pinned (committed) -> stays at cost 6; unit 1 is the only free unit -> stays at 4.
    assert _rematch_optimal(assignments, snap, committed) == 10
    # Without the pin, the single free pair is unchanged too (one free unit), but the allowed_unit
    # variant is pinned regardless of committed:
    allowed = Task(id="pickup:WHEAT:0", kind="PICKUP", pos=(4, 5), priority=0,
                   deadline_step=700, allowed_unit=0)
    assert _rematch_optimal([(0, allowed, 6, 1), (1, near, 4, 1)], snap, {}) == 10


# ------------------------------------------------------------------------------ cargo eligibility

def test_carries_cargo_gates_feed_and_place_only():
    snap = _snapshot((0, 0), [(1, 1)], inventories=[{"WHEAT": 2}, {}])
    feed = Task(id="feed:0:0", kind="FEED", pos=(0, 0), priority=0)
    place = Task(id="place:COW:0:0", kind="PLACE", pos=(0, 0), priority=1, item="COW")
    water = _water(0, 0)
    assert _carries_cargo(snap, 0, feed) is True     # unit 0 holds WHEAT
    assert _carries_cargo(snap, 1, feed) is False    # unit 1 does not
    assert _carries_cargo(snap, 0, place) is False    # nobody holds the COW
    assert _carries_cargo(snap, 0, water) is True     # WATER needs no cargo
    assert _carries_cargo(snap, 1, water) is True


# --------------------------------------------------------------------------- max-cardinality count

def test_max_cardinality_counts_a_full_legal_matching():
    snap = _snapshot((0, 0), [(9, 9)])
    tasks = [_water(0, 0), _water(9, 9)]
    assert _max_cardinality(tasks, snap, {}) == 2


def test_max_cardinality_is_capped_by_cargo_eligibility():
    """Two FEED tasks but only one unit holds WHEAT ⇒ at most one can ever be served this turn."""
    snap = _snapshot((0, 0), [(1, 0)], inventories=[{"WHEAT": 1}, {}])
    feeds = [
        Task(id="feed:0:0", kind="FEED", pos=(0, 0), priority=0, deadline_step=700),
        Task(id="feed:1:0", kind="FEED", pos=(1, 0), priority=0, deadline_step=700),
    ]
    assert _max_cardinality(feeds, snap, {}) == 1
    # Give the second unit wheat too and both become serveable.
    snap2 = _snapshot((0, 0), [(1, 0)], inventories=[{"WHEAT": 1}, {"WHEAT": 1}])
    assert _max_cardinality(feeds, snap2, {}) == 2
