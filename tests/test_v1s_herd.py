"""v1s — ROADMAP §4.3 S3 step 2 guards: the herd-13 slot assignment and the day-gated ramp.

Two separable pieces of the herd-13 increment, pinned in isolation (prompt.md §7 deliverable 5):

  * the 13-slot PASTURE assignment — flipping `animals.targets` reassigns which COW/SHEEP holds
    which tile, in `targets` dict order (agent.animal_slots.animal_slot_ranges). §0.2 of the brief
    calls this out as the exact class of change the v1p.1/v1p.1b family blew up on, so the tile
    identity for both the H1 (4C+9S) and H2 (9C+4S) layouts is pinned to the exact tuples.
  * the ramp — planner._herd_ramp_cap and make_day_plan's per-day clamp of animal_purchases,
    defaulting to None (shipped step-purchase behaviour).
"""
import copy

from agent.animal_slots import animal_slot_ranges
from agent.config import CONFIG
from agent.planner import _herd_ramp_cap, make_day_plan
from agent.state import parse


def _obs(day, *, enabled=True):
    """A minimal day-`day` observation on an empty NW farm (money to spare)."""
    farm = {
        "money": 3000,
        "tiles": [[None] * 10 for _ in range(10)],
        "farmer": [4, 4],
        "hands": [],
        "unlocked_quadrants": ["NW"],
        "hires_today": 0,
    }
    return {
        "player": 0,
        "step": day * 24,
        "day": day,
        "hour": 0,
        "farms": [copy.deepcopy(farm), copy.deepcopy(farm)],
        "private": {"shed": {}, "seeds": {}, "inventories": [{}]},
        "market": {"inventory": {}, "prices": {}},
        "town": {"unlocked_shops": []},
    }


# --------------------------------------------------------------- 13-slot tile assignment

def test_v1s_h2_profile_assigns_the_documented_9cow_4sheep_tiles():
    """H2 (9C+4S): COW takes the first 9 PASTURE tiles, SHEEP the next 4, in targets dict order.
    These are the exact distances §0.2 of the brief cites (COW 2,2,2,3,3,4,4,5,6; SHEEP 6,7,7,8)."""
    config = copy.deepcopy(CONFIG)
    config["animals"]["targets"] = {"COW": 9, "SHEEP": 4, "GOOSE": 0}
    ranges = animal_slot_ranges(config)
    assert ranges["COW"] == (
        (4, 2), (3, 3), (2, 4), (3, 2), (2, 3), (4, 0), (0, 4), (0, 3), (0, 2),
    )
    assert ranges["SHEEP"] == ((2, 0), (0, 1), (1, 0), (0, 0))
    # SHEEP now lands strictly farther than every COW — the composition/tile-reassignment §0.2
    # warns about. Pin the Manhattan distances from the (4,4) shed so a future tuple edit trips it.
    spawn = (4, 4)
    dist = lambda t: abs(t[0] - spawn[0]) + abs(t[1] - spawn[1])
    assert [dist(t) for t in ranges["COW"]] == [2, 2, 2, 3, 3, 4, 4, 5, 6]
    assert [dist(t) for t in ranges["SHEEP"]] == [6, 7, 7, 8]


def test_v1s_h1_profile_assigns_the_documented_4cow_9sheep_tiles():
    """H1 (4C+9S): COW keeps its exact original four tiles (2,2,2,3); SHEEP extends into the three
    unclaimed worst tiles (7,7,8). Nothing already claimed by COW moves (brief §3.3, arm H1)."""
    config = copy.deepcopy(CONFIG)
    config["animals"]["targets"] = {"COW": 4, "SHEEP": 9, "GOOSE": 0}
    ranges = animal_slot_ranges(config)
    assert ranges["COW"] == ((4, 2), (3, 3), (2, 4), (3, 2))
    assert ranges["SHEEP"] == (
        (2, 3), (4, 0), (0, 4), (0, 3), (0, 2), (2, 0), (0, 1), (1, 0), (0, 0),
    )
    # COW's four tiles are byte-identical to the shipped 4C+6S layout — H1 adds no reassignment.
    shipped = copy.deepcopy(CONFIG)
    shipped["animals"]["targets"] = {"COW": 4, "SHEEP": 6, "GOOSE": 0}
    assert animal_slot_ranges(shipped)["COW"] == ranges["COW"]


# --------------------------------------------------------------- the day-gated ramp

def test_v1s_herd_ramp_cap_none_is_shipped_behaviour():
    """ramp None → no clamp (returns None), every day."""
    targets = {"COW": 9, "SHEEP": 4}
    for day in (0, 5, 10, 20, 30):
        assert _herd_ramp_cap(None, day, targets) is None
        assert _herd_ramp_cap([], day, targets) is None


def test_v1s_herd_ramp_cap_6_12_13_rungs():
    """§4.0's profile [[5, 6], [10, 12]]: 6 through d5, 12 through d10, full target thereafter."""
    ramp = [[5, 6], [10, 12]]
    targets = {"COW": 9, "SHEEP": 4}  # sum 13
    assert _herd_ramp_cap(ramp, 0, targets) == 6
    assert _herd_ramp_cap(ramp, 5, targets) == 6
    assert _herd_ramp_cap(ramp, 6, targets) == 12
    assert _herd_ramp_cap(ramp, 10, targets) == 12
    assert _herd_ramp_cap(ramp, 11, targets) == 13  # past the last rung → full summed target
    assert _herd_ramp_cap(ramp, 20, targets) == 13


def test_v1s_make_day_plan_ramp_clamps_purchases_in_dict_order():
    """make_day_plan spends the per-day cap across names in targets dict order (COW before SHEEP)."""
    config = copy.deepcopy(CONFIG)
    config["animals"]["targets"] = {"COW": 9, "SHEEP": 4, "GOOSE": 0}
    config["animals"]["ramp"] = [[5, 6], [10, 12]]

    d3 = make_day_plan(parse(_obs(3)), config)
    assert d3.animal_purchases == {"COW": 6}  # cap 6 spent entirely on COW; SHEEP gets nothing
    assert d3.structures_to_build == {"PASTURE": 6}

    d8 = make_day_plan(parse(_obs(8)), config)
    assert d8.animal_purchases == {"COW": 9, "SHEEP": 3}  # cap 12: COW 9, SHEEP 12-9
    assert d8.structures_to_build == {"PASTURE": 12}

    d12 = make_day_plan(parse(_obs(12)), config)
    assert d12.animal_purchases == {"COW": 9, "SHEEP": 4}  # uncapped: full 13
    assert d12.structures_to_build == {"PASTURE": 13}


def test_v1s_make_day_plan_ramp_none_matches_step_purchase():
    """ramp None (the shipped default) buys the full target from day 0 — no clamp at any day."""
    config = copy.deepcopy(CONFIG)
    config["animals"]["targets"] = {"COW": 9, "SHEEP": 4, "GOOSE": 0}
    config["animals"]["ramp"] = None
    for day in (0, 5, 12):
        plan = make_day_plan(parse(_obs(day)), config)
        assert plan.animal_purchases == {"COW": 9, "SHEEP": 4}
        assert plan.structures_to_build == {"PASTURE": 13}
