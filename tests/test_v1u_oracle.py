"""v1u — guards for the offline oracle's non-trivial helpers (`analysis/v1u_oracle.py`).

The oracle *substitutes* an optimal matcher into the live agent and plays whole episodes out, so
its assignment functions must (a) be legal — honour priority-as-a-hard-tier (G-1), position
exclusivity (G-6), cargo (G-4) and committed pinning (G-2); (b) be deterministic (G-3), since a
nondeterministic matcher would void the paired-seat compare; and (c) actually *beat* greedy on the
classic 2× stranding pathology, or the whole ceiling measurement is vacuous. The urgency split
that keeps the optimum off the step-1 pure-distance mirage is pinned too.
"""
import copy

from agent.config import CONFIG
from agent.scheduler import Task, assign
from agent.state import parse

from analysis.v1u_oracle import (
    _feed_optimal_actions,
    _feed_saturation_by_day,
    _median_saturation_from_day,
    _optimal_actions,
    _twoopt_actions,
)


def _snapshot(farmer, hands, *, inventories=None, seeds=None):
    n_units = 1 + len(hands)
    inventories = inventories or [{} for _ in range(n_units)]
    obs = {
        "player": 0, "step": 0, "day": 0, "hour": 0,
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
    """A comfortable (far-deadline) unrestricted priority-0 WATER task."""
    return Task(id=f"water:{x}:{y}", kind="WATER", pos=(x, y), priority=0, deadline_step=700)


# The classic stranding pair (same fixture as the greedy-reconstruction test): farmer is the best
# fit for both tiles; greedy consumes it on the tiebreak winner (5,4) and strands (4,5) on the far
# hand (greedy pays 1+6=7). The joint optimum uncrosses it: farmer->(4,5)=1, hand->(5,4)=4 = 5.
def test_optimal_uncrosses_the_greedy_stranding():
    snap = _snapshot((5, 5), [(5, 0)])
    tasks = [_water(5, 4), _water(4, 5)]
    greedy = assign(tasks, snap, {})
    farmer, hands, commitments = _optimal_actions(tasks, snap, {}, CONFIG)
    # greedy stranded: farmer heads to (5,4) (NORTH, y 5->4), hand to the far (4,5).
    assert greedy[0] == ["NORTH"]
    # optimum: farmer -> (4,5) is WEST; hand (5,0) -> (5,4) is SOUTH. Strictly less total travel.
    assert farmer == ["WEST"]
    assert hands == [["SOUTH"]]
    assert commitments == {0: "water:4:5", 1: "water:5:4"}


def test_optimal_is_deterministic():
    """Same inputs -> byte-identical assignment, every call (G-3). The cost matrix is built from
    sorted units / position-ordered nodes with a sub-integer tie-break, so there is no set/dict
    order on the decision path."""
    snap = _snapshot((5, 5), [(5, 0), (2, 2), (8, 8)])
    tasks = [_water(5, 4), _water(4, 5), _water(2, 3), _water(8, 7), _water(1, 1)]
    first = _optimal_actions(tasks, snap, {}, CONFIG)
    for _ in range(5):
        assert _optimal_actions(tasks, snap, {}, CONFIG) == first


def test_optimal_position_exclusivity_one_unit_per_tile():
    """G-6: two units both a step from one WATER tile — exactly one is assigned it, the other
    idles (the tile collapses to a single node)."""
    snap = _snapshot((5, 4), [(5, 6)])
    tasks = [_water(5, 5)]
    farmer, hands, commitments = _optimal_actions(tasks, snap, {}, CONFIG)
    moved = [a for a in (farmer, *hands) if a != ["PASS"]]
    assert len(moved) == 1                      # only one unit routed to the tile
    assert commitments == {0: "water:5:5"}      # farmer wins the unit tie-break, hand PASSes
    assert hands == [["PASS"]]


def test_optimal_cargo_routes_the_wheat_holder(seed=None):
    """G-4: a FEED tile is served by the unit that holds WHEAT, never the (nearer) empty one."""
    snap = _snapshot((5, 5), [(4, 5)], inventories=[{"WHEAT": 1}, {}])
    feed = Task(id="feed:0:5", kind="FEED", pos=(0, 5), priority=0, deadline_step=700)
    farmer, hands, commitments = _optimal_actions([feed], snap, {}, CONFIG)
    assert commitments == {0: "feed:0:5"}       # farmer (wheat) is routed, not the empty hand
    assert hands == [["PASS"]]


def test_optimal_pins_committed_like_greedy():
    """G-2: a unit committed to a task keeps it even when another unit already sits on the tile —
    which is exactly what greedy's switching=0 key does, so the two agree here."""
    snap = _snapshot((5, 5), [(4, 5)])          # hand is ON the (4,5) tile
    task = _water(4, 5)
    committed = {0: "water:4:5"}
    greedy = assign([task], snap, committed)
    farmer, hands, commitments = _optimal_actions([task], snap, committed, CONFIG)
    assert (farmer, hands, commitments) == greedy
    assert farmer == ["WEST"]                    # committed farmer walks in; the on-tile hand idles
    assert hands == [["PASS"]]


def test_optimal_priority_is_a_hard_tier():
    """G-1: a priority-0 WATER far away outranks a priority-2 PLANT under a unit's feet — the
    single available unit is spent on the higher tier, never traded for the cheaper near task."""
    snap = _snapshot((5, 5), [], seeds={"CARROT": 5})
    water = Task(id="water:0:0", kind="WATER", pos=(0, 0), priority=0, deadline_step=700)
    plant = Task(id="plant:CARROT:5:5", kind="PLANT", pos=(5, 5), priority=2, item="CARROT",
                 deadline_step=700, required_inventory={"CARROT_SEED": 1})
    farmer, _hands, commitments = _optimal_actions([water, plant], snap, {}, CONFIG)
    assert commitments == {0: "water:0:0"}       # routed to the tier-0 task, not the free PLANT


def test_twoopt_also_uncrosses_the_stranding():
    """Arm B (greedy + 2-opt) recovers the same swap arm A finds on the stranding pair, with no
    solver — the free pair is swapped because it strictly cuts total travel (7 -> 5)."""
    snap = _snapshot((5, 5), [(5, 0)])
    tasks = [_water(5, 4), _water(4, 5)]
    farmer, hands, commitments = _twoopt_actions(tasks, snap, {}, CONFIG)
    assert farmer == ["WEST"]
    assert hands == [["SOUTH"]]
    assert commitments == {0: "water:4:5", 1: "water:5:4"}


def test_twoopt_keeps_an_already_optimal_greedy():
    """When greedy is already optimal, 2-opt changes nothing (no strict improvement exists)."""
    snap = _snapshot((0, 0), [(9, 0)])
    tasks = [_water(0, 0), _water(9, 0)]
    assert _twoopt_actions(tasks, snap, {}, CONFIG) == assign(tasks, snap, {})


def test_feed_optimal_rematches_only_feed_tiles():
    """Arm C: FEED assignments are re-matched among the wheat-carrying units; a crossed pair of
    FEED tiles is uncrossed while a co-present WATER task keeps greedy's decision."""
    snap = _snapshot((5, 5), [(5, 0)], inventories=[{"WHEAT": 2}, {"WHEAT": 2}])
    feeds = [
        Task(id="feed:5:4", kind="FEED", pos=(5, 4), priority=0, deadline_step=700),
        Task(id="feed:4:5", kind="FEED", pos=(4, 5), priority=0, deadline_step=700),
    ]
    farmer, hands, commitments = _feed_optimal_actions(feeds, snap, {}, CONFIG)
    # Same uncrossing as the WATER stranding case, but reached by the feed-only re-match.
    assert commitments == {0: "feed:4:5", 1: "feed:5:4"}


# --------------------------------------------------------------------------- feed saturation
def _obs_step(day, animal_tiles):
    """animal_tiles: list of (x, y, fed_today)."""
    tiles = [[None] * 10 for _ in range(10)]
    for x, y, fed in animal_tiles:
        tiles[y][x] = {"kind": "PASTURE", "animal": "COW", "fed_today": fed}
    return [{"observation": {"day": day, "farms": [{"tiles": tiles}, {"tiles": tiles}]}}]


def test_feed_saturation_counts_hours_with_any_unfed_animal():
    env_json = {"steps": [
        _obs_step(9, [(0, 0, True), (1, 0, True)]),    # d9 h0: all fed -> not saturated
        _obs_step(9, [(0, 0, False), (1, 0, True)]),   # d9 h1: one unfed -> saturated
        _obs_step(9, [(0, 0, False), (1, 0, False)]),  # d9 h2: two unfed -> saturated
        _obs_step(10, [(0, 0, True)]),                 # d10 h0: fed -> not saturated
    ]}
    sat = _feed_saturation_by_day(env_json, 0)
    assert sat[9] == (2, 3)      # 2 of 3 day-9 hours had an unfed animal
    assert sat[10] == (0, 1)
    # median over days 9,10 of {0.667, 0.0} — the mean of the two middle values = 1/3.
    assert _median_saturation_from_day(sat, 9) == 1 / 3
    assert _median_saturation_from_day(sat, 10) == 0.0   # only day 10 qualifies


def test_feed_saturation_ignores_hours_with_no_placed_animals():
    env_json = {"steps": [
        _obs_step(9, []),                     # no animals placed -> not counted at all
        _obs_step(9, [(0, 0, False)]),        # one unfed -> saturated
    ]}
    sat = _feed_saturation_by_day(env_json, 0)
    assert sat[9] == (1, 1)
