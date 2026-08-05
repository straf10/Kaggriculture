"""Executable form of MASTERPLAN §2/§7 engine ground truth (plan.md §2.1, §2.3).

Imports from the **installed** kaggle-environments package, not engine_reference/, so a
future `pip install -U kaggle-environments` that changes behavior fails this suite loudly
(plan.md §2.2 — version-bump detector). engine_reference/kaggriculture.py is the read-only
reference copy the line numbers below point at.

Tier A tests call engine functions directly on hand-built farm/private dicts.
Tier B tests drive `env.step()` through kaggle_environments' public interpreter loop.
"""
import copy
import math

import pytest
from kaggle_environments import make
from kaggle_environments.envs.kaggriculture import kaggriculture as k

PASS = {"farmer": ["PASS"], "hands": [], "market": []}


def make_env(seed, *, episode_steps=10, turns_per_day=24, **overrides):
    cfg = {"seed": seed, "episodeSteps": episode_steps, "turnsPerDay": turns_per_day}
    cfg.update(overrides)
    return make("kaggriculture", configuration=cfg)


def new_farm_private():
    """A bare farm/private pair with the farmer parked on the NW shed-access tile."""
    farm = k._new_farm(10, 3000)
    private = k._new_private()
    farm["farmer"] = [0, 0]
    return farm, private


# --------------------------------------------------------------------------- Tier A: market


def _expected_price(item):
    """Independent reimplementation of the pricing model documented in kaggriculture.py:27-37,
    used as a frozen contract rather than re-calling the engine's own _shape/market_price."""
    p = k.MARKET_PARAMS[item]
    base, I0, T = p["base"], p["I0"], p["T"]

    def shape(func, x):
        x = max(0.0, x)
        return {
            "linear": x,
            "sq": x * x,
            "sqrt": math.sqrt(x),
            "log": math.log(1.0 + x),
            "log10": math.log10(1.0 + x),
        }[func]

    def price_at(inventory):
        if inventory < I0:
            f, target = p["below_func"], p["below_target"]
            amp = target * base / shape(f, T)
            raw = base + amp * shape(f, I0 - inventory)
        else:
            f, target = p["above_func"], p["above_target"]
            amp = target * base / shape(f, T)
            raw = base - amp * shape(f, inventory - I0)
        return max(k.PRICE_FLOOR, int(round(raw)))

    return price_at


@pytest.mark.parametrize("item", list(k.MARKET_PARAMS))
def test_market_price_table(item):
    """kaggriculture.py:178-192 — price(I0-T)/price(I0+T)/price(I0+2T) match the documented
    scarcity/glut pricing model, independently reimplemented above."""
    p = k.MARKET_PARAMS[item]
    I0, T = p["I0"], p["T"]
    expected = _expected_price(item)
    for inventory in (I0 - T, I0, I0 + T, I0 + 2 * T):
        assert k.market_price(item, inventory) == expected(inventory), (item, inventory)


def test_market_price_known_examples():
    """Literal cross-check against MASTERPLAN/plan.md worked examples."""
    I0 = k.MARKET_I0
    assert k.market_price("WHEAT", I0 - 400) == 45
    assert k.market_price("WHEAT", I0 + 400) == 20
    assert k.market_price("WHEAT", I0 + 800) == 19
    assert k.market_price("MELON", I0 - 300) == 300
    assert k.market_price("MELON", I0 + 300) == 1
    assert k.market_price("MELON", I0 + 600) == 1


# --------------------------------------------------------------------------- Tier A: hire cost


def test_hire_cost_fib():
    """kaggriculture.py:667-676 — n-th hire of the day costs fib(n), fib(0)=1."""
    assert [k._hire_cost(n) for n in range(8)] == [1, 1, 2, 3, 5, 8, 13, 21]


# --------------------------------------------------------------------------- Tier A: care bonus


def test_care_bonus_plus_one_not_two():
    """MASTERPLAN §7#1 — a single fed+cared non-production day adds +1 to pending_care_bonus,
    not +2 (one bonus for the fed+cared combination, not one per action). kaggriculture.py:804-808."""
    farm = k._new_farm(10, 3000)
    farm["tiles"][0][0] = k._new_animal("SHEEP", 0)  # first_yield_day=6, interval=3
    tile = farm["tiles"][0][0]
    tile["fed_today"] = True
    tile["cared_today"] = True
    k._daily_refresh_animals(farm, 6)  # next_day=7 -> days_since_first=1, not a production day
    assert farm["tiles"][0][0]["pending_care_bonus"] == 1


def test_care_bonus_full_payout_on_fed_production_day():
    """Accumulated pending_care_bonus is paid out in full on the next fed production day."""
    farm = k._new_farm(10, 3000)
    farm["tiles"][0][0] = k._new_animal("SHEEP", 0)
    tile = farm["tiles"][0][0]
    tile["pending_care_bonus"] = 3
    tile["fed_today"] = True
    tile["cared_today"] = False
    k._daily_refresh_animals(farm, 5)  # next_day=6 -> days_since_first=0, production day
    assert farm["tiles"][0][0]["yield_units"] == 1 + 3  # base + full accumulated bonus
    assert farm["tiles"][0][0]["pending_care_bonus"] == 0


def test_care_bonus_zeroed_on_unfed_production_day():
    """An unfed production day still produces the base unit but discards any pending bonus."""
    farm = k._new_farm(10, 3000)
    farm["tiles"][0][0] = k._new_animal("SHEEP", 0)
    tile = farm["tiles"][0][0]
    tile["pending_care_bonus"] = 3
    tile["fed_today"] = False
    tile["cared_today"] = False
    k._daily_refresh_animals(farm, 5)
    assert farm["tiles"][0][0]["yield_units"] == 1  # base only, bonus lost
    assert farm["tiles"][0][0]["pending_care_bonus"] == 0


# --------------------------------------------------------------------------- Tier B: fertilizer sell


def test_fertilizer_sell_accepted():
    """MASTERPLAN §7#2 — FERTILIZER is a sellable PRODUCTS entry like any crop/animal good."""
    env = make_env(2, episode_steps=4)
    env.state[0].observation.private["shed"]["FERTILIZER"] = 1
    env.step([{"farmer": ["PASS"], "hands": [], "market": [["SELL", "FERTILIZER", 1]]}, PASS])
    obs = env.state[0].observation
    assert obs.farms[0]["money"] == 3100.0
    assert obs.private["shed"].get("FERTILIZER", 0) == 0


# --------------------------------------------------------------------------- Tier A: DIG semantics


def test_dig_semantics():
    """MASTERPLAN §7#3 — kaggriculture.py:428-435. DIG clears plant/weed/empty structure,
    but is a no-op on a structure with a placed animal."""
    farm, private = new_farm_private()

    farm["tiles"][0][0] = k._new_plant("WHEAT", 0, 24)
    k._apply_unit_action(farm, private, 0, ["DIG"], 10, 0, 24)
    assert farm["tiles"][0][0] is None

    farm["tiles"][0][0] = {"kind": "WEED"}
    k._apply_unit_action(farm, private, 0, ["DIG"], 10, 0, 24)
    assert farm["tiles"][0][0] is None

    farm["tiles"][0][0] = {"kind": "COOP"}
    k._apply_unit_action(farm, private, 0, ["DIG"], 10, 0, 24)
    assert farm["tiles"][0][0] is None

    farm["tiles"][0][0] = k._new_animal("GOOSE", 0)
    before = copy.deepcopy(farm["tiles"][0][0])
    k._apply_unit_action(farm, private, 0, ["DIG"], 10, 0, 24)
    assert farm["tiles"][0][0] == before


# --------------------------------------------------------------------------- planting-day watering


def test_planting_day_counts_as_unwatered_tier_a():
    """kaggriculture.py:208 — _new_plant starts consecutive_unwatered at 1: the planting day
    itself counts as an unwatered day."""
    tile = k._new_plant("CARROT", 0, 24)
    assert tile["consecutive_unwatered"] == 1


def test_planting_day_counts_as_unwatered_tier_b():
    """MASTERPLAN §7#4 — a seed planted but not watered the same day becomes a weed that
    same night (2 unwatered days reached: the planting day + the first unwatered end-of-day)."""
    env = make_env(1, episode_steps=10, turns_per_day=4)
    buy = {"farmer": ["PASS"], "hands": [], "market": [["BUY_SEED", "CARROT", 1]]}
    plant = {"farmer": ["PLANT", "CARROT"], "hands": [], "market": []}
    env.step([buy, PASS])
    env.step([plant, PASS])
    farm = env.state[0].observation.farms[0]
    fx, fy = farm["farmer"]
    assert farm["tiles"][fy][fx]["kind"] == "PLANT"
    env.step([PASS, PASS])
    env.step([PASS, PASS])  # end of day fires here (turnsPerDay=4)
    farm = env.state[0].observation.farms[0]
    assert farm["tiles"][fy][fx] == {"kind": "WEED"}


# --------------------------------------------------------------------------- Tier A: melon cap


def test_melon_cap_day10():
    """MASTERPLAN §7#5 — kaggriculture.py:383-387,16. Watering every day drives melon
    yield_units to the max_yield cap (6) exactly at age 10; ages 11-12 add nothing further."""
    farm, private = new_farm_private()
    farm["tiles"][0][0] = k._new_plant("MELON", 0, 24)
    for day in range(0, 13):
        farm["tiles"][0][0]["watered_today"] = False
        k._apply_unit_action(farm, private, 0, ["WATER"], 10, day, 24)
        if day == 10:
            assert farm["tiles"][0][0]["yield_units"] == 6
    assert farm["tiles"][0][0]["yield_units"] == 6  # unchanged through day 12


# --------------------------------------------------------------------------- Tier A: strawberry


def test_strawberry_exactly_4_yields():
    """MASTERPLAN §7#6,#7 — kaggriculture.py:767-780. Strawberry (ongoing) produces exactly
    4 times, at ages 10/12/14/16, then max_lifespan_step is set and no further production."""
    farm, private = new_farm_private()
    farm["tiles"][0][0] = k._new_plant("STRAWBERRY", 0, 24)
    production_days = []
    prev_units = 0
    for day in range(0, 20):
        farm["tiles"][0][0]["watered_today"] = True  # never miss water: isolate yield mechanics
        k._daily_refresh_plants(farm, day, 24)
        tile = farm["tiles"][0][0]
        units = tile["yield_units"]
        if units != prev_units:
            production_days.append(day + 1)  # next_day is when the production posts
        prev_units = units
    assert production_days == [10, 12, 14, 16]
    assert farm["tiles"][0][0]["yield_units"] == 4
    assert farm["tiles"][0][0]["max_lifespan_step"] == 17 * 24  # (next_day+1)*turns_per_day


# --------------------------------------------------------------------------- Tier A: fertilizer availability


def test_fertilizer_available_no_care_required():
    """MASTERPLAN §7#8 — kaggriculture.py:809,492-499. fertilizer_available is set for every
    surviving animal regardless of CARE, and COLLECT_FERTILIZER does not stack same-turn."""
    farm, private = new_farm_private()
    farm["tiles"][0][0] = k._new_animal("GOOSE", 0)
    k._daily_refresh_animals(farm, 0)  # fed_today False, still survives (1 unfed day)
    assert farm["tiles"][0][0]["fertilizer_available"] is True

    k._apply_unit_action(farm, private, 0, ["COLLECT_FERTILIZER"], 10, 1, 24)
    k._apply_unit_action(farm, private, 0, ["COLLECT_FERTILIZER"], 10, 1, 24)
    assert private["inventories"][0].get("FERTILIZER") == 1


# --------------------------------------------------------------------------- Tier A: shed access


def test_shed_access_tiles():
    """MASTERPLAN §7#9 — kaggriculture.py:118-121,327-329. Exactly the 4 inner-corner tiles
    are shed-adjacent (NWSE order); DROP is a no-op from anywhere else."""
    assert k._shed_access_tiles(10) == [(4, 4), (5, 4), (4, 5), (5, 5)]

    farm, private = new_farm_private()
    farm["farmer"] = [0, 0]  # not shed-adjacent
    private["inventories"][0]["WHEAT"] = 5
    k._apply_unit_action(farm, private, 0, ["DROP"], 10, 0, 24)
    assert private["shed"].get("WHEAT", 0) == 0
    assert private["inventories"][0].get("WHEAT") == 5


# --------------------------------------------------------------------------- Tier B: 10-order cap


def test_market_order_cap_10():
    """MASTERPLAN §2#2 — kaggriculture.py:537. Raw order list is truncated to 10 before type
    dispatch: HIRE/BUY_LAND count against the cap like anything else and are dropped if past it."""
    env = make_env(3, episode_steps=6, turns_per_day=24, startingMoney=1_000_000)
    orders = [["BUY_SEED", "WHEAT", 1] for _ in range(10)] + [["HIRE"], ["BUY_LAND"]]
    env.step([{"farmer": ["PASS"], "hands": [], "market": orders}, PASS])
    obs = env.state[0].observation
    assert obs.private["seeds"]["WHEAT"] == 10  # all 10 BUY_SEED executed
    assert len(obs.farms[0]["hands"]) == 0  # HIRE (11th) dropped
    assert obs.farms[0]["unlocked_quadrants"] == ["NW"]  # BUY_LAND (12th) dropped


# --------------------------------------------------------------------------- Tier B: market interleaving


def test_market_interleaving_lockstep_same_index():
    """MASTERPLAN §2#3 — kaggriculture.py:539-603. Both players quoting the same item at the
    same order-list index get the identical per-unit price (symmetric within an index)."""
    env = make_env(44, episode_steps=4, startingMoney=1_000_000)
    env.state[0].observation.private["shed"]["WHEAT"] = 100
    env.state[1].observation.private["shed"]["WHEAT"] = 100
    order = {"farmer": ["PASS"], "hands": [], "market": [["SELL", "WHEAT", 50]]}
    env.step([order, order])
    obs = env.state[0].observation
    assert obs.farms[0]["money"] == obs.farms[1]["money"]


def test_market_interleaving_earlier_index_exhausts_first():
    """A player whose SELL sits at an earlier list index locks in better prices as the
    shared inventory glut moves, versus an otherwise identical order placed later."""
    env = make_env(45, episode_steps=4, startingMoney=1_000_000)
    env.state[0].observation.private["shed"]["WHEAT"] = 200
    env.state[1].observation.private["shed"]["WHEAT"] = 200
    filler = [["BUY_SEED", "CARROT", 1]] * 5
    early = {"farmer": ["PASS"], "hands": [], "market": [["SELL", "WHEAT", 50]] + filler}
    late = {"farmer": ["PASS"], "hands": [], "market": filler + [["SELL", "WHEAT", 50]]}
    env.step([early, late])
    obs = env.state[0].observation
    # player 0 (early index) sells into a less-glutted market than player 1 (late index)
    assert obs.farms[0]["money"] > obs.farms[1]["money"]


# --------------------------------------------------------------------------- Tier B: hands mapping


def test_hands_action_mapping():
    """MASTERPLAN §2#1 — kaggriculture.py:264-268,914-916. hands[i] action maps to
    farm['hands'][i]. Fewer actions than hands leave the extras idle; more actions than
    hands are silently dropped (pos=None no-op) with no crash or conflict."""
    env = make_env(3, episode_steps=8, turns_per_day=24)
    env.step([{"farmer": ["PASS"], "hands": [], "market": [["HIRE"], ["HIRE"]]}, PASS])
    hands_before = [tuple(p) for p in env.state[0].observation.farms[0]["hands"]]
    assert len(hands_before) == 2

    # fewer actions (1) than hands (2): second hand stays put
    env.step([{"farmer": ["PASS"], "hands": [["NORTH"]], "market": []}, PASS])
    hands_after = env.state[0].observation.farms[0]["hands"]
    assert tuple(hands_after[1]) == hands_before[1]
    assert tuple(hands_after[0]) != hands_before[0]

    # more actions (3) than hands (2): the 3rd is a silent no-op, no crash
    env.step([{"farmer": ["PASS"], "hands": [["NORTH"], ["NORTH"], ["NORTH"]], "market": []}, PASS])
    assert len(env.state[0].observation.farms[0]["hands"]) == 2
    assert env.state[0].status == "ACTIVE"


def test_hand_spawn_ignores_locked():
    """MASTERPLAN discussion.md:34 — kaggriculture.py:510-518,309-317. With no extra quadrant
    unlocked, the first hired hand spawns on the LOCKED tile (5,4) and can still move off it."""
    env = make_env(3, episode_steps=6, turns_per_day=24)
    env.step([{"farmer": ["PASS"], "hands": [], "market": [["HIRE"]]}, PASS])
    farm = env.state[0].observation.farms[0]
    assert farm["hands"] == [[5, 4]]
    assert farm["tiles"][4][5] == "LOCKED"

    env.step([{"farmer": ["PASS"], "hands": [["WEST"]], "market": []}, PASS])
    assert env.state[0].observation.farms[0]["hands"] == [[4, 4]]


# --------------------------------------------------------------------------- Tier A: decay


def test_decay_per_2_steps():
    """MASTERPLAN pre-#5 — kaggriculture.py:730-744. Once step >= max_lifespan_step, yield
    drains 1 unit every 2 steps (turns, not days); hitting 0 turns the tile into a weed."""
    farm = k._new_farm(10, 3000)
    farm["tiles"][0][0] = {
        "kind": "PLANT", "crop": "WHEAT", "planted_day": 0,
        "watered_today": False, "consecutive_unwatered": 0,
        "yield_units": 3, "max_lifespan_step": 100, "fertilized_until_day": -1,
    }
    for step in (98, 99):
        k._decay_plants(farm, step)
        assert farm["tiles"][0][0]["yield_units"] == 3  # before mls: untouched

    k._decay_plants(farm, 100)
    assert farm["tiles"][0][0]["yield_units"] == 2
    k._decay_plants(farm, 101)
    assert farm["tiles"][0][0]["yield_units"] == 2  # odd offset: no decay
    k._decay_plants(farm, 102)
    assert farm["tiles"][0][0]["yield_units"] == 1
    k._decay_plants(farm, 104)
    assert farm["tiles"][0][0] == {"kind": "WEED"}


# --------------------------------------------------------------------------- Tier B: weed RNG coupling


def test_weed_rng_seat_coupling():
    """MASTERPLAN §2#6 (new finding) — kaggriculture.py:848-855,814-818. _end_of_day shares one
    rng instance across both players' _spawn_weeds calls (player 0 first): how many empty tiles
    player 0 has changes how many rng draws player 1's weed roll starts from. Confirmed via a
    seed where the resulting weed pattern for player 1 differs depending on player 0's tile-fill."""

    def run(plant_tiles_for_player0):
        env = make_env(1, episode_steps=10, turns_per_day=4, weedSpawnChance=0.9)
        if plant_tiles_for_player0:
            env.step([{"farmer": ["PASS"], "hands": [], "market": [["BUY_SEED", "CARROT", 5]]}, PASS])
            for _ in range(5):
                env.step([{"farmer": ["PLANT", "CARROT"], "hands": [], "market": []}, PASS])
        while env.state[0].observation.get("step") < 4:
            env.step([PASS, PASS])
        return env.state[1].observation.farms[1]["tiles"]

    tiles_idle = run(False)
    tiles_planted = run(True)
    assert tiles_idle != tiles_planted


# --------------------------------------------------------------------------- Tier B: atomic PLANT


def test_plant_atomic_block():
    """MASTERPLAN §2#4 — kaggriculture.py:897-910. If total PLANT demand for a crop this turn
    exceeds available seeds, ALL PLANT requests for that crop become PASS (none partially wins)."""
    env = make_env(5, episode_steps=6, turns_per_day=24)
    buy = {"farmer": ["PASS"], "hands": [], "market": [["BUY_SEED", "MELON", 1]]}
    env.step([buy, buy])
    env.step([{"farmer": ["PASS"], "hands": [], "market": [["HIRE"]]}, {"farmer": ["PASS"], "hands": [], "market": [["HIRE"]]}])
    # move the hand off its (locked) spawn tile onto an empty NW tile
    move = {"farmer": ["PASS"], "hands": [["WEST"]], "market": []}
    env.step([move, move])
    env.step([move, move])

    plant_both = {"farmer": ["PLANT", "MELON"], "hands": [["PLANT", "MELON"]], "market": []}
    env.step([plant_both, {"farmer": ["PASS"], "hands": [["PASS"]], "market": []}])
    farm = env.state[0].observation.farms[0]
    fx, fy = farm["farmer"]
    hx, hy = farm["hands"][0]
    assert farm["tiles"][fy][fx] is None
    assert farm["tiles"][hy][hx] is None
    assert env.state[0].observation.private["seeds"]["MELON"] == 1  # neither PLANT consumed a seed


# --------------------------------------------------------------------------- Tier B: floor sales


def test_floor_sales_no_inventory_growth():
    """kaggriculture.py:636-637 — sales that clear at the $1 floor do not increase market
    inventory. MELON's fragile above-curve floors after ~158 net units (MASTERPLAN §1); dumping
    far more than that should still leave inventory close to that crossover, not proportional
    to units sold. (Small residual wobble is town-center demand, which runs every turn
    regardless of player actions — kaggriculture.py:722-725 — not a market-mechanics bug.)"""
    env = make_env(8, episode_steps=4, startingMoney=100_000_000)
    env.state[0].observation.private["shed"]["MELON"] = 50_000
    inv_before = env.state[0].observation.market["inventory"]["MELON"]
    env.step([{"farmer": ["PASS"], "hands": [], "market": [["SELL", "MELON", 50_000]]}, PASS])
    obs = env.state[0].observation
    assert obs.private["shed"].get("MELON", 0) == 0  # all 50k units did sell
    assert obs.market["prices"]["MELON"] <= 5  # floored, not still worth a meaningful price
    # inventory grew only while price > floor; nowhere near 50k units' worth of growth
    assert obs.market["inventory"]["MELON"] - inv_before < 300


# --------------------------------------------------------------------------- Tier B: determinism


def test_determinism_same_seed():
    """Υ3 — kaggriculture.py:235,848. Same seed + identical scripted actions, two fresh envs,
    produce an identical final state (excluding the framework-assigned episode `id`)."""

    def run():
        env = make_env(123, episode_steps=10, turns_per_day=4, weedSpawnChance=0.5)
        a0 = {"farmer": ["PLANT", "CARROT"], "hands": [], "market": [["BUY_SEED", "CARROT", 1], ["HIRE"]]}
        a1 = {"farmer": ["NORTH"], "hands": [], "market": [["BUY_SEED", "WHEAT", 1]]}
        for _ in range(9):
            env.step([a0, a1])
        return env.toJSON()

    j1, j2 = run(), run()
    j1.pop("id", None)
    j2.pop("id", None)
    assert j1 == j2
