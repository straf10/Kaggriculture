"""Clean-room meta-bench opponents (current_phase.md §Β.2 / MASTERPLAN §3.2ter).

Two deterministic profiles built from **published statistics only** — never from
competitor trajectories or notebook blobs (Ανοιχτό #11):

- ``meta_route`` — v23-fork (~40 teams, ELO 3.117-3.131)
- ``meta_route_sheep`` — v25 sheep-first basin

Reuses ``agent/`` as a **read-only** library (planner/scheduler/executor scaffolding)
with a private config and thin wrappers for MELON + the meta sell calendar. Does **not**
mutate ``agent.config.CONFIG``, so a same-process opponent (e.g. ``main.py``) is not
poisoned.

Inherited agent weaknesses (documented in ``gates/b2_meta_bench/profile_validation.md``):
hands 11-12 are rarely hired (fib cost), capacity gate may trim crops under load.
"""
from __future__ import annotations

import os
import sys
from contextlib import contextmanager
from dataclasses import replace

# Bench files may insert the repo root; submission agents must not (§Α.2).
# get_last_callable execs this file *without* defining __file__, but does put
# harness/bench_agents/ on sys.path — recover the repo root from that or cwd.
def _ensure_repo_root_on_path() -> None:
    candidates = []
    try:
        candidates.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
    except NameError:
        pass
    for entry in list(sys.path):
        if not entry:
            continue
        abs_entry = os.path.abspath(entry)
        if os.path.basename(abs_entry) == "bench_agents":
            candidates.append(os.path.abspath(os.path.join(abs_entry, "..", "..")))
    candidates.append(os.getcwd())
    for root in candidates:
        if os.path.isdir(os.path.join(root, "agent")) and os.path.isdir(os.path.join(root, "harness")):
            if root not in sys.path:
                sys.path.insert(0, root)
            return


_ensure_repo_root_on_path()

from agent.config import CONFIG as _AGENT_CONFIG  # noqa: E402
from agent.constants import ANIMALS, CROPS, market_price  # noqa: E402
import copy  # noqa: E402
from agent.executor import (  # noqa: E402
    _remaining_unplanted_targets,
    market_orders as _base_market_orders,
)
from agent.planner import (  # noqa: E402
    DayPlan,
    _capacity_limited_targets,
    make_day_plan as _base_make_day_plan,
)
from agent.policy import (  # noqa: E402
    _needs_replan,
    reset_or_get_runtime,
)
from agent.scheduler import (  # noqa: E402
    assign,
    build_tasks as _base_build_tasks,
    make_ledger,
)
from agent.scheduler import (  # noqa: E402
    _GROWN_CROPS as _BASE_GROWN_CROPS,
    _HARVEST_READY_AGE as _BASE_HARVEST_READY_AGE,
    _WATER_WINDOWS as _BASE_WATER_WINDOWS,
    _harvest_ready_age,
    _water_window,
)
from agent import scheduler as _scheduler_mod  # noqa: E402
from agent.state import parse  # noqa: E402

# Published sell prior (MASTERPLAN §3.2ter). Withhold until this day, then sell.
_SELL_OPEN_DAY = {
    "WHEAT": 2,
    "FERTILIZER": 3,
    "WOOL": 9,
    "MELON": 10,
    "MILK": 10,
    "STRAWBERRY": 18,
    "EGG": 10,
    "CARROT": 2,
}

# Melon first so day-0 planting budget prefers the profile-critical crop.
_META_GROWN_CROPS = ("MELON", "STRAWBERRY", "WHEAT", "CARROT")


def _nw_tiles_nearest_first() -> list[tuple[int, int]]:
    """All NW tiles (x<5, y<5), nearest to shed spawn (4,4) first."""
    spawn = (4, 4)
    tiles = [(x, y) for x in range(5) for y in range(5)]
    tiles.sort(key=lambda p: (abs(p[0] - spawn[0]) + abs(p[1] - spawn[1]), p[1], p[0]))
    return tiles


def _ne_tiles_nearest_first() -> list[tuple[int, int]]:
    spawn = (5, 4)
    tiles = [(x, y) for x in range(5, 10) for y in range(5)]
    tiles.sort(key=lambda p: (abs(p[0] - spawn[0]) + abs(p[1] - spawn[1]), p[1], p[0]))
    return tiles


def _sw_tiles_nearest_first() -> list[tuple[int, int]]:
    spawn = (4, 5)
    # Skip (4,5) — shed-access tile used by PICKUP/DROP.
    tiles = [(x, y) for x in range(5) for y in range(5, 10) if (x, y) != (4, 5)]
    tiles.sort(key=lambda p: (abs(p[0] - spawn[0]) + abs(p[1] - spawn[1]), p[1], p[0]))
    return tiles


def _build_profile_config(
    *,
    melon_tiles: int,
    day0_wheat_seeds: int,
    cows: int,
    sheep: int,
    wheat_tiles: int,
    hands_early: int,
    hands_late: int,
    opening_animals: dict,
    strawberry_last_plant_day: int = 22,
) -> dict:
    """Private config — deep copy of the submission CONFIG + melon overlay.

    Starting from the gated v1h_2d-shaped config keeps animal/land/sell logistics that
    already clear a metric gate; we only rewrite crop tile lists for the published
    melon/strawberry/wheat footprint. Never mutates ``agent.config.CONFIG``.
    """
    cfg = copy.deepcopy(_AGENT_CONFIG)
    cfg["guards"]["debug"] = False

    # Keep the proven pasture layout; carve melon from near-shed crop tiles (carrot +
    # lowest-priority NW strawberry), then fill strawberry to ~23 across NW leftovers + NE.
    pasture = list(cfg["scheduler"]["animal_structure_tiles"]["PASTURE"])
    pasture_n = cows + sheep
    pasture = pasture[:pasture_n]
    cfg["scheduler"]["animal_structure_tiles"]["PASTURE"] = tuple(pasture)
    cfg["scheduler"]["animal_structure_tiles"]["COOP"] = ()
    used = set(pasture)

    nw = [p for p in _nw_tiles_nearest_first() if p not in used]
    melon_list = nw[:melon_tiles]
    used.update(melon_list)
    straw_nw = [p for p in nw[melon_tiles:] if p not in used]
    # Aim ~23 strawberry total: leftover NW + NE fill.
    ne = [p for p in _ne_tiles_nearest_first() if p not in used]
    need_ne = max(0, 23 - len(straw_nw))
    straw_ne = ne[:need_ne]
    sw = _sw_tiles_nearest_first()
    wheat_list = sw[:wheat_tiles]

    cfg["planner"].update({
        "carrot_tiles": 0,
        "strawberry_tiles": len(straw_nw),
        "strawberry_last_plant_day": strawberry_last_plant_day,
        "max_new_plants_per_day": 10,
        "hands_target": hands_early,
        "sw_hands_target": hands_late,
        "capacity_safety_factor": 1.2,
        "ne_carrot_tiles": 0,
        "ne_strawberry_tiles": len(straw_ne),
        "ne_max_new_plants_per_day": 6,
        "sw_wheat_tiles": len(wheat_list),
        "sw_max_new_plants_per_day": 5,
        "wheat_last_plant_day": 22,
        "melon_tiles": len(melon_list),
        "melon_last_plant_day": 18,
        "day0_wheat_seed_target": day0_wheat_seeds,
    })
    cfg["scheduler"]["target_tiles"] = {
        "MELON": tuple(melon_list),
        "STRAWBERRY": tuple(straw_nw) + tuple(straw_ne),
        "WHEAT": tuple(wheat_list),
        "CARROT": (),
    }
    cfg["executor"]["seed_buffer"] = 12
    cfg["executor"]["sell_floor_price"]["MELON"] = 10
    cfg["animals"]["targets"] = {"COW": cows, "SHEEP": sheep, "GOOSE": 0}
    # Only MELON uses the published withhold day — withholding milk/wool/strawberry made the
    # bench strictly dominated by v1h_2d (0-24). Melon still opens on day 10.
    cfg["meta"] = {
        "sell_open_day": {"MELON": 10},
        "opening_animals": dict(opening_animals),
    }
    return cfg


# v23-fork crop profile on top of v1h_2d logistics. Herd stays at the gated 4c/6s size
# (10 animals) — published 8c/6s is unreachable with the inherited fib hire cap at 10 hands.
META_ROUTE_CONFIG = _build_profile_config(
    melon_tiles=10,
    day0_wheat_seeds=7,
    cows=4,
    sheep=6,
    wheat_tiles=18,
    hands_early=6,
    hands_late=10,
    opening_animals={"COW": 2, "SHEEP": 2},
)

# v25 sheep-first opening; same mature herd cap.
META_ROUTE_SHEEP_CONFIG = _build_profile_config(
    melon_tiles=5,
    day0_wheat_seeds=5,
    cows=4,
    sheep=6,
    wheat_tiles=16,
    hands_early=6,
    hands_late=10,
    opening_animals={"COW": 1, "SHEEP": 4},
)


@contextmanager
def _melon_grown_crops():
    """Temporarily teach the shared scheduler about MELON without leaving it patched."""
    grown = _META_GROWN_CROPS
    harvest = {crop: _harvest_ready_age(crop) for crop in grown}
    water = {
        crop: _water_window(crop)
        for crop in grown
        if not CROPS[crop]["ongoing"]
    }
    _scheduler_mod._GROWN_CROPS = grown
    _scheduler_mod._HARVEST_READY_AGE = harvest
    _scheduler_mod._WATER_WINDOWS = water
    try:
        yield
    finally:
        _scheduler_mod._GROWN_CROPS = _BASE_GROWN_CROPS
        _scheduler_mod._HARVEST_READY_AGE = _BASE_HARVEST_READY_AGE
        _scheduler_mod._WATER_WINDOWS = _BASE_WATER_WINDOWS


def make_meta_day_plan(snapshot, config: dict, env_config=None) -> DayPlan:
    """Extend the library planner with MELON + parallel WHEAT (no strawberry-gate wait)."""
    plan = _base_make_day_plan(snapshot, config, env_config)
    planner = config["planner"]
    liquidation = plan.force_liquidation
    targets = dict(plan.plant_targets)

    melon_n = int(planner.get("melon_tiles", 0))
    if (
        not liquidation
        and melon_n > 0
        and snapshot.day <= int(planner.get("melon_last_plant_day", 18))
    ):
        targets["MELON"] = melon_n

    # Base planner withholds WHEAT until strawberry_last_plant_day closes. Meta runs both.
    sw_unlocked = config.get("land", {}).get("enabled", False) and "SW" in snapshot.my_quadrants
    if (
        sw_unlocked
        and not liquidation
        and snapshot.day <= int(planner.get("wheat_last_plant_day", 22))
    ):
        targets["WHEAT"] = int(planner.get("sw_wheat_tiles", 0))

    if "CARROT" in targets and targets["CARROT"] <= 0:
        targets.pop("CARROT", None)

    targets = _capacity_limited_targets(snapshot, config, targets)

    max_new = int(plan.max_new_plants)
    if targets.get("MELON", 0) > 0:
        max_new = max(max_new, int(planner.get("max_new_plants_per_day", 12)))

    # Day-0 signature animals only; full herd from day 3 so feed logistics match v1h_2d.
    animals_cfg = config.get("animals", {})
    final_c = int(animals_cfg.get("targets", {}).get("COW", 0))
    final_s = int(animals_cfg.get("targets", {}).get("SHEEP", 0))
    opening = config.get("meta", {}).get("opening_animals", {"COW": 2, "SHEEP": 2})
    if snapshot.day < 3:
        animal_purchases = {
            "COW": min(final_c, int(opening.get("COW", 2))),
            "SHEEP": min(final_s, int(opening.get("SHEEP", 2))),
        }
    else:
        animal_purchases = {"COW": final_c, "SHEEP": final_s}
    animal_purchases = {k: v for k, v in animal_purchases.items() if v > 0}
    structures = {}
    for name, count in animal_purchases.items():
        structure = ANIMALS[name]["structure"]
        structures[structure] = structures.get(structure, 0) + count

    return replace(
        plan,
        plant_targets=targets,
        max_new_plants=max_new,
        animal_purchases=animal_purchases,
        structures_to_build=structures,
    )


def build_meta_tasks(snapshot, plan: DayPlan, config: dict):
    with _melon_grown_crops():
        return _base_build_tasks(snapshot, plan, config)


def _calendar_allows(product: str, day: int, config: dict) -> bool:
    open_day = config.get("meta", {}).get("sell_open_day", {}).get(product)
    if open_day is None:
        return True
    return day >= int(open_day)


def _sell_units(product: str, qty_available: int, inventory: int, floor: int, safety: int) -> int:
    sell = 0
    while (
        sell < qty_available
        and market_price(product, inventory + sell + safety) > floor
    ):
        sell += 1
    return sell


def meta_market_orders(
    snapshot,
    plan: DayPlan,
    ledger,
    scheduled_unit_actions,
    config: dict,
    farm_hand_cost_mult: int = 1,
):
    """Library market_orders + MELON seeds/sells + meta sell calendar gate."""
    orders = _base_market_orders(
        snapshot, plan, ledger, scheduled_unit_actions, config,
        farm_hand_cost_mult=farm_hand_cost_mult,
    )
    executor = config["executor"]
    safety = int(executor["opponent_price_safety_units"])
    day = snapshot.day

    # Drop premature sells (meta withhold prior).
    filtered = []
    for order in orders:
        if order and order[0] == "SELL":
            product = order[1]
            if not _calendar_allows(product, day, config):
                continue
        filtered.append(order)
    orders = filtered

    # MELON seed top-up (base executor only knows CARROT/STRAWBERRY/WHEAT).
    if not plan.force_liquidation and plan.plant_targets.get("MELON", 0) > 0:
        seed_buffer = int(executor["seed_buffer"])
        seed_count = int(ledger.seeds.get("MELON", 0))
        remaining = _remaining_unplanted_targets(snapshot, plan, config, "MELON")
        want = max(0, min(seed_buffer, remaining) - seed_count)
        # Day-0 signature: buy the full melon package immediately while cash exists.
        if day == 0 and snapshot.hour <= 2:
            want = max(want, int(plan.plant_targets["MELON"]) - seed_count)
        money = ledger.money
        # Approximate remaining cash after already-queued buys.
        for order in orders:
            if order[0] == "BUY_SEED":
                money -= int(order[2]) * int(CROPS[order[1]]["seed"])
            elif order[0] == "BUY_ANIMAL":
                from agent.constants import ANIMALS
                money -= int(order[2]) * int(ANIMALS[order[1]]["cost"])
            elif order[0] == "BUY_PRODUCT" and order[1] == "WHEAT":
                money -= int(order[2]) * max(1, int(snapshot.market_prices.get("WHEAT", 25)))
            elif order[0] == "BUY_LAND":
                money -= 1000
        affordable = int(max(0, money) // CROPS["MELON"]["seed"])
        buy = min(want, affordable)
        if buy > 0:
            orders.append(["BUY_SEED", "MELON", buy])

    # Day-0 wheat seeds (feed/plant signature), even before SW unlock.
    day0_wheat = int(config["planner"].get("day0_wheat_seed_target", 0))
    if day == 0 and day0_wheat > 0 and snapshot.hour <= 2:
        have = int(ledger.seeds.get("WHEAT", 0))
        need = max(0, day0_wheat - have)
        if need:
            already = sum(
                int(o[2]) for o in orders
                if o and o[0] == "BUY_SEED" and o[1] == "WHEAT"
            )
            need = max(0, need - already)
            if need:
                orders.append(["BUY_SEED", "WHEAT", need])

    # MELON sells on/after calendar day.
    if _calendar_allows("MELON", day, config):
        in_shed = int(snapshot.shed.get("MELON", 0))
        if in_shed > 0:
            floor = (
                int(executor["liquidation_floor_price"])
                if plan.force_liquidation
                else int(plan.sell_floor_price.get("MELON", executor["sell_floor_price"]["MELON"]))
            )
            inventory = int(snapshot.market_inventory.get("MELON", 0))
            units = _sell_units("MELON", in_shed, inventory, floor, safety)
            if units > 0 and not any(o[0] == "SELL" and o[1] == "MELON" for o in orders):
                orders.append(["SELL", "MELON", units])

    max_orders = int(executor["max_market_orders"])
    if len(orders) > max_orders:
        # Keep HIRE/BUY ahead of SELL when truncating (same tiers as executor).
        tier = {
            "HIRE": 0, "BUY_PRODUCT": 1, "BUY_ANIMAL": 2,
            "BUY_SEED": 3, "BUY_LAND": 4, "SELL": 5,
        }
        orders = sorted(orders, key=lambda o: tier.get(o[0], 9))[:max_orders]
    return orders


def _run_policy(obs, configuration, config: dict):
    snapshot = parse(obs)
    runtime = reset_or_get_runtime(snapshot)
    farm_hand_cost_mult = int((configuration or {}).get("farmHandCostMult", 1))

    if _needs_replan(runtime, snapshot):
        runtime.plan = make_meta_day_plan(snapshot, config, configuration)
        runtime.planned_day = snapshot.day
    runtime.last_quadrants = snapshot.my_quadrants
    runtime.last_hand_count = len(snapshot.hand_positions)

    tasks = build_meta_tasks(snapshot, runtime.plan, config)
    ledger = make_ledger(snapshot)
    farmer_action, hand_actions, commitments = assign(
        tasks, snapshot, runtime.committed_tasks, config,
    )
    runtime.committed_tasks = commitments
    unit_actions = [farmer_action, *hand_actions]
    orders = meta_market_orders(
        snapshot, runtime.plan, ledger, unit_actions, config,
        farm_hand_cost_mult=farm_hand_cost_mult,
    )
    return {
        "farmer": farmer_action,
        "hands": hand_actions,
        "market": orders,
    }


def meta_route(obs, configuration=None):
    """v23-fork profile bench opponent."""
    return _run_policy(obs, configuration, META_ROUTE_CONFIG)


def meta_route_sheep(obs, configuration=None):
    """v25 sheep-first basin bench opponent."""
    return _run_policy(obs, configuration, META_ROUTE_SHEEP_CONFIG)


# Path-loader entrypoint (get_last_callable): default is the v23-fork profile.
agent = meta_route
