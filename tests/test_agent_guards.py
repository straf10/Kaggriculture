"""Incremental guard tests for the rule-based agent."""
import copy
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from kaggle_environments.envs.kaggriculture import kaggriculture as engine

from agent import _vendored
from agent.config import CONFIG
from agent.constants import ANIMALS
from agent.planner import make_day_plan
from agent.policy import _RUNTIME_BY_PLAYER, agent
from agent.scheduler import Task, assign, build_tasks, make_ledger
from agent.state import parse
from harness.play import play, resolve_agent

REPO_ROOT = Path(__file__).resolve().parent.parent
MAIN = REPO_ROOT / "main.py"


def _minimal_observation(*, player=0, step=0, hands=(), shops=()):
    farms = [
        {
            "money": 3000,
            "tiles": [[None] * 10 for _ in range(10)],
            "farmer": [4, 4],
            "hands": [list(pos) for pos in (hands if player == 0 else ())],
            "unlocked_quadrants": ["NW"],
            "hires_today": 0,
        },
        {
            "money": 3000,
            "tiles": [[None] * 10 for _ in range(10)],
            "farmer": [4, 4],
            "hands": [list(pos) for pos in (hands if player == 1 else ())],
            "unlocked_quadrants": ["NW"],
            "hires_today": 0,
        },
    ]
    return {
        "player": player,
        "step": step,
        "day": step // 24,
        "hour": step % 24,
        "farms": farms,
        "private": {"shed": {}, "seeds": {}, "inventories": [{}]},
        "market": {"inventory": {}, "prices": {}},
        "town": {"unlocked_shops": list(shops)},
    }


def _animal_tile(name, *, fed_today=False, cared_today=True, yield_units=0, placed_day=0):
    return {
        "kind": ANIMALS[name]["structure"],
        "animal": name,
        "placed_day": placed_day,
        "yield_units": yield_units,
        "consecutive_unfed": 0,
        "fed_today": fed_today,
        "cared_today": cared_today,
        "fertilizer_available": False,
        "pending_care_bonus": 0,
    }


def test_g12_main_exports_server_selected_agent():
    loaded = resolve_agent(str(MAIN), entrypoint="agent")
    assert loaded.__name__ == "agent"


def test_policy_returns_index_aligned_hand_actions():
    # animals disabled here: this test is about index alignment (G12), not the v1d animal
    # feature, and an empty farm otherwise has no tasks at all — with animals on, the two
    # always-free BUILD_PASTURE slots would legitimately draw a unit away from PASS.
    # review.md L5: restore the actual prior value, not a hardcoded literal — a hardcoded
    # restore silently "fixes" CONFIG to the wrong value (and masks it for every later test)
    # if the true default ever differs from the literal here.
    previous_enabled = CONFIG["animals"]["enabled"]
    CONFIG["animals"]["enabled"] = False
    try:
        action = agent(_minimal_observation(hands=((5, 4), (4, 5))))
    finally:
        CONFIG["animals"]["enabled"] = previous_enabled
    assert action["farmer"] == ["PASS"]
    assert action["hands"] == [["PASS"], ["PASS"]]
    assert len(action["market"]) <= 10


def test_g13_runtime_is_seat_local_and_resets_on_new_episode():
    _RUNTIME_BY_PLAYER.clear()
    agent(_minimal_observation(player=0, step=12))
    agent(_minimal_observation(player=1, step=7))
    seat_one_context = _RUNTIME_BY_PLAYER[1]

    agent(_minimal_observation(player=0, step=0))

    assert _RUNTIME_BY_PLAYER[0].last_step == 0
    assert _RUNTIME_BY_PLAYER[1] is seat_one_context
    assert _RUNTIME_BY_PLAYER[1].last_step == 7


def test_vendored_constants_and_prices_match_pinned_engine():
    assert _vendored.CROPS == engine.CROPS
    assert _vendored.ANIMALS == engine.ANIMALS
    assert _vendored.MARKET_PARAMS == engine.MARKET_PARAMS
    assert _vendored.LAND_ORDER == engine.LAND_ORDER
    assert _vendored.LAND_PRICES == engine.LAND_PRICES
    assert _vendored.SHOPS == engine.SHOPS
    # v1g.2 — the demand model reads TOWN_CENTER_PRODUCTS, so the fallback's derivation of it
    # (from MARKET_PARAMS, minus FERTILIZER) has to stay identical to the engine's own.
    assert _vendored.PRODUCTS == engine.PRODUCTS
    assert _vendored.TOWN_CENTER_PRODUCTS == engine.TOWN_CENTER_PRODUCTS
    for item, params in engine.MARKET_PARAMS.items():
        equilibrium, capacity = params["I0"], params["T"]
        for inventory in (equilibrium - capacity, equilibrium, equilibrium + capacity):
            assert _vendored.market_price(item, inventory) == engine.market_price(item, inventory)


def test_v1h1_constants_resolve_per_symbol_not_all_or_nothing():
    """v1h.1 — the 1.32.6 bump deleted `TOWN_CENTER_DEMAND_SCHEDULE` from the engine, and the
    old blanket `try: from ... import (A, B, C)` turned that single deletion into a silent
    fallback of *every* constant to the vendored copy. Nothing raised; the agent just stopped
    tracking the installed engine. Pin the two properties that prevent a recurrence."""
    from agent import constants

    # 1. Live engine values, not vendored ones. Identity, not equality: the vendored copy is
    #    value-equal by construction (asserted above), so `==` could not tell the two apart.
    assert constants.MARKET_PARAMS is engine.MARKET_PARAMS
    assert constants.market_price is engine.market_price
    assert constants.SHOPS is engine.SHOPS

    # 2. A symbol the engine does not export must degrade alone. Simulate the exact 1.32.6
    #    situation for a name that exists in neither place and confirm the others survive.
    assert constants._const("MARKET_PARAMS") is engine.MARKET_PARAMS
    with pytest.raises(AttributeError):
        constants._const("A_CONSTANT_NO_ENGINE_OR_VENDORED_COPY_HAS")


def test_v1h1_town_center_ramp_is_gone_from_the_engine():
    """v1h.1 — the flat town centre is the single most consequential balance change of the
    season (140 -> 30 units/product/season, MASTERPLAN §3.2#6). If a future engine version
    reinstates a day-stepped ramp, `agent/demand.py` silently under-counts late-season demand
    and every sell-timing decision built on it is wrong. Fail here, loudly, instead."""
    assert not hasattr(engine, "TOWN_CENTER_DEMAND_SCHEDULE")
    assert not hasattr(_vendored, "TOWN_CENTER_DEMAND_SCHEDULE")
    assert engine.MAX_SHOP_INSTANCES == 8


def test_l3_hire_cost_matches_engine():
    """review_89d99f0_2026-08-05.md L3 — executor._hire_cost is a hand-copied reimplementation of the engine's
    fib-cost sequence with no parity test, unlike the rest of the vendored constants.
    review.md M3 — the original version of this test only swept the default mult=1, so it
    never caught that _hire_cost dropped farmHandCostMult entirely; now swept across
    mult in {1, 2, 3} to lock the full `cost = mult * fib(n)` relationship."""
    from agent.executor import _hire_cost

    for mult in (1, 2, 3):
        for n in range(8):
            assert _hire_cost(n, mult) == engine._hire_cost(n, mult)


def test_m12_harvest_ready_age_derived_from_crops():
    """review.md M12 — the hardcoded `age >= 3` (CARROT) / `age >= 16` (STRAWBERRY) harvest
    triggers in scheduler.py must stay derived from CROPS, not drift into a second hand-copied
    magic number if the pinned engine's CROPS constants ever change."""
    from agent.scheduler import _HARVEST_READY_AGE, _WATER_WINDOWS

    assert _HARVEST_READY_AGE["CARROT"] == 3
    assert _HARVEST_READY_AGE["STRAWBERRY"] == 16
    # v1h': the CARROT-only window became a per-crop table when WHEAT joined. CARROT's own
    # values are unchanged — that is the point of asserting them next to WHEAT's.
    assert _WATER_WINDOWS["CARROT"] == (2, 3)
    assert _HARVEST_READY_AGE["WHEAT"] == 4
    assert _WATER_WINDOWS["WHEAT"] == (2, 4)
    # STRAWBERRY is ongoing: it gains yield from the engine's daily refresh, not from watering
    # inside a window, so it must stay out of the table (watering it is purely survival).
    assert "STRAWBERRY" not in _WATER_WINDOWS


def test_g13_sequential_episodes_are_clean_and_equal():
    first = play(str(MAIN), str(MAIN), seed=0, steps=8, record=False)
    second = play(str(MAIN), str(MAIN), seed=0, steps=8, record=False)
    assert first.clean and second.clean
    assert first.rewards == second.rewards


def test_g13_cross_process_hashseed_determinism():
    snippet = (
        "import json\n"
        "from kaggle_environments import make\n"
        f"main = {str(MAIN)!r}\n"
        "env = make('kaggriculture', configuration={'seed': 17, 'episodeSteps': 8})\n"
        "env.run([main, main])\n"
        "result = env.toJSON()\n"
        "result.pop('id', None)\n"
        "print(json.dumps(result, sort_keys=True))\n"
    )

    def run(hash_seed):
        process = subprocess.run(
            [sys.executable, "-c", snippet],
            cwd=REPO_ROOT,
            env={**os.environ, "PYTHONHASHSEED": hash_seed},
            capture_output=True,
            text=True,
            check=True,
        )
        return json.loads(process.stdout.strip().splitlines()[-1])

    assert run("0") == run("12345")


def test_g1_scheduler_does_not_start_plant_too_late():
    observation = _minimal_observation(step=23)
    observation["private"]["seeds"]["CARROT"] = 1
    snapshot = parse(observation)
    plan = make_day_plan(snapshot, CONFIG)
    tasks = build_tasks(snapshot, plan, CONFIG)
    assert not any(task.kind == "PLANT" for task in tasks)


def test_g1_scheduler_reserves_time_to_water_new_plant():
    # animals disabled: this is a G1 plant-timing test, not a v1d animal-priority test — with
    # animals on, the free/always-available BUILD_PASTURE tasks legitimately outrank a single
    # CARROT plant this late in the day and would otherwise mask what G1 is checking.
    # review.md L5: restore the actual prior value, not a hardcoded literal.
    previous_enabled = CONFIG["animals"]["enabled"]
    CONFIG["animals"]["enabled"] = False
    try:
        observation = _minimal_observation(step=22)
        observation["private"]["seeds"]["CARROT"] = 1
        snapshot = parse(observation)
        plan = make_day_plan(snapshot, CONFIG)
        tasks = build_tasks(snapshot, plan, CONFIG)
        farmer_action, _, _ = assign(tasks, snapshot)
    finally:
        CONFIG["animals"]["enabled"] = previous_enabled
    assert farmer_action == ["PLANT", "CARROT"]


def test_g9_carrot_gets_final_water_before_harvest():
    observation = _minimal_observation(step=3 * 24)
    observation["private"]["seeds"]["CARROT"] = 1
    observation["farms"][0]["tiles"][4][4] = {
        "kind": "PLANT",
        "crop": "CARROT",
        "planted_day": 0,
        "watered_today": False,
        "consecutive_unwatered": 0,
        "yield_units": 2,
        "max_lifespan_step": 4 * 24,
        "fertilized_until_day": -1,
    }
    snapshot = parse(observation)
    plan = make_day_plan(snapshot, CONFIG)
    farmer_action, _, _ = assign(build_tasks(snapshot, plan, CONFIG), snapshot)
    assert farmer_action == ["WATER"]

    observation["farms"][0]["tiles"][4][4]["watered_today"] = True
    snapshot = parse(observation)
    farmer_action, _, _ = assign(build_tasks(snapshot, plan, CONFIG), snapshot)
    assert farmer_action == ["HARVEST"]


def test_g7_executor_never_exceeds_market_cap():
    observation = _minimal_observation()
    observation["private"]["shed"]["CARROT"] = 50
    observation["market"]["inventory"]["CARROT"] = 10_000
    observation["market"]["prices"]["CARROT"] = 35
    snapshot = parse(observation)
    plan = make_day_plan(snapshot, CONFIG)
    action = agent(observation)
    assert len(action["market"]) <= CONFIG["executor"]["max_market_orders"]


def test_m7_market_orders_truncates_instead_of_raising():
    """review_89d99f0_2026-08-05.md M7 — exceeding the market order budget used to `raise AssertionError`, which
    on a submission run would turn one over-budget turn into an ERROR and a lost episode.
    It must truncate instead."""
    from agent.executor import market_orders

    tight_config = copy.deepcopy(CONFIG)
    tight_config["executor"]["max_market_orders"] = 1
    observation = _minimal_observation(step=0)
    observation["private"]["shed"]["CARROT"] = 50
    observation["private"]["shed"]["STRAWBERRY"] = 50
    observation["market"]["inventory"]["CARROT"] = 10_000
    observation["market"]["inventory"]["STRAWBERRY"] = 10_000
    observation["market"]["prices"]["CARROT"] = 35
    observation["market"]["prices"]["STRAWBERRY"] = 130
    snapshot = parse(observation)
    plan = make_day_plan(snapshot, tight_config)
    ledger = make_ledger(snapshot)
    orders = market_orders(snapshot, plan, ledger, [["PASS"]], tight_config)
    assert len(orders) == 1


def test_h8_market_truncation_keeps_hire_over_sell():
    """review.md H8 — truncation used to keep construction order (SELL orders built first),
    so a budget-tight turn could drop HIRE/BUY_LAND — the orders with the largest measured
    ROI — in favor of a SELL worth a few dollars. HIRE (tier 0) must survive a 1-order budget
    ahead of a pending SELL (tier 5), regardless of which was constructed first."""
    from agent.executor import market_orders

    tight_config = copy.deepcopy(CONFIG)
    tight_config["executor"]["max_market_orders"] = 1
    observation = _minimal_observation(step=0)
    observation["private"]["shed"]["CARROT"] = 50
    observation["market"]["inventory"]["CARROT"] = 10_000
    observation["market"]["prices"]["CARROT"] = 35
    snapshot = parse(observation)
    plan = make_day_plan(snapshot, tight_config)
    ledger = make_ledger(snapshot)
    orders = market_orders(snapshot, plan, ledger, [["PASS"]], tight_config)
    assert orders == [["HIRE"]]


def test_e1_market_truncation_emits_kept_sells_first():
    """current_phase.md §v1m.2 Ε1 — the two halves of truncation are separate decisions.
    *Which* orders survive is still tier order (H8: HIRE outranks SELL). *In what order the
    survivors are emitted* is not: the engine fills a turn's market orders in emission order,
    so a kept SELL at index 6-9 prices against inventory the same turn's earlier orders already
    moved. With a 2-order budget the HIRE must still survive over a third order, and the
    surviving SELL must be emitted ahead of it — while the un-truncated path (len <= max) is
    left exactly as it was."""
    from agent.executor import market_orders

    observation = _minimal_observation(step=0)
    observation["private"]["shed"]["CARROT"] = 50
    observation["private"]["shed"]["STRAWBERRY"] = 50
    observation["market"]["inventory"]["CARROT"] = 10
    observation["market"]["inventory"]["STRAWBERRY"] = 10
    observation["market"]["prices"]["CARROT"] = 35
    observation["market"]["prices"]["STRAWBERRY"] = 130
    snapshot = parse(observation)

    def orders_at(cap):
        config = copy.deepcopy(CONFIG)
        config["executor"]["max_market_orders"] = cap
        return market_orders(snapshot, make_day_plan(snapshot, config),
                             make_ledger(snapshot), [["PASS"]], config)

    # 8 orders are constructed here: 2 SELLs then 6 HIREs. At cap 8 nothing is truncated.
    untruncated = orders_at(8)
    assert len(untruncated) == 8
    assert [order[0] for order in untruncated] == ["SELL", "SELL"] + ["HIRE"] * 6

    # At cap 7 the cut fires: keep-by-tier drops the *lower-value* SELL (H8, unchanged), and
    # the one SELL that survives is emitted ahead of the six HIREs it was kept alongside.
    truncated = orders_at(7)
    assert len(truncated) == 7
    assert [order[0] for order in truncated] == ["SELL"] + ["HIRE"] * 6
    assert truncated[0] == ["SELL", "STRAWBERRY", 50]

    # And when the budget is tighter than the HIREs alone, tier order still decides survival —
    # emitting SELLs first must never resurrect an order the cut removed.
    assert [order[0] for order in orders_at(6)] == ["HIRE"] * 6


def test_g10_strawberry_planting_stops_after_opening_window():
    observation = _minimal_observation(step=6 * 24)
    observation["private"]["seeds"]["STRAWBERRY"] = 3
    snapshot = parse(observation)
    plan = make_day_plan(snapshot, CONFIG)
    tasks = build_tasks(snapshot, plan, CONFIG)
    assert plan.plant_targets["STRAWBERRY"] == 0
    assert not any(task.kind == "PLANT" and task.item == "STRAWBERRY" for task in tasks)


def test_strawberry_waters_for_survival_not_every_day():
    observation = _minimal_observation(step=4 * 24)
    tile = {
        "kind": "PLANT",
        "crop": "STRAWBERRY",
        "planted_day": 2,
        "watered_today": False,
        "consecutive_unwatered": 0,
        "yield_units": 0,
        "max_lifespan_step": -1,
        "fertilized_until_day": -1,
    }
    observation["farms"][0]["tiles"][2][2] = tile
    snapshot = parse(observation)
    plan = make_day_plan(snapshot, CONFIG)
    assert not any(
        task.kind == "WATER" and task.pos == (2, 2)
        for task in build_tasks(snapshot, plan, CONFIG)
    )

    tile["consecutive_unwatered"] = 1
    snapshot = parse(observation)
    assert any(
        task.kind == "WATER" and task.pos == (2, 2)
        for task in build_tasks(snapshot, plan, CONFIG)
    )


def test_v1b_hires_target_hands_at_hour_zero():
    action = agent(_minimal_observation(step=0))
    assert sum(1 for order in action["market"] if order == ["HIRE"]) == CONFIG["planner"]["hands_target"]


def test_v1h2_d1_hour0_hire_credits_same_turn_sell():
    """v1h.2 D1 — hour-0 HIRE must count queued SELL proceeds on a cashless morning.
    Engine processes market by index (SELL at i funds HIRE at i+1); keep that order."""
    from agent.executor import market_orders

    observation = _minimal_observation(step=2 * 24)  # day 2 hour 0
    observation["farms"][0]["money"] = 0
    observation["farms"][0]["hands"] = []
    observation["farms"][0]["hires_today"] = 0
    observation["private"]["shed"]["FERTILIZER"] = 3
    observation["market"]["inventory"]["FERTILIZER"] = 10_000
    observation["market"]["prices"]["FERTILIZER"] = 100
    snapshot = parse(observation)
    plan = make_day_plan(snapshot, CONFIG)
    orders = market_orders(snapshot, plan, make_ledger(snapshot), [], CONFIG)

    assert ["SELL", "FERTILIZER", 3] in orders
    assert orders.count(["HIRE"]) == CONFIG["planner"]["hands_target"]
    sell_i = next(i for i, order in enumerate(orders) if order[0] == "SELL")
    first_hire_i = next(i for i, order in enumerate(orders) if order == ["HIRE"])
    assert sell_i < first_hire_i


def test_v1h2d_eod_headroom_sells_only_wheat_beyond_feed_reserve():
    from agent.executor import market_orders

    observation = _minimal_observation(step=23)
    observation["private"]["shed"]["WHEAT"] = 105
    observation["private"]["inventories"][0]["WHEAT"] = 10
    observation["market"]["inventory"]["WHEAT"] = 0
    for x in range(10):
        observation["farms"][0]["tiles"][0][x] = _animal_tile("SHEEP")
    snapshot = parse(observation)
    plan = make_day_plan(snapshot, CONFIG)
    orders = market_orders(snapshot, plan, make_ledger(snapshot), [["PASS"]], CONFIG)

    assert ["SELL", "WHEAT", 105] in orders
    assert all(order[1] == "WHEAT" for order in orders if order[0] == "SELL")
    remaining_total = (
        int(observation["private"]["shed"]["WHEAT"]) - 105
        + int(observation["private"]["inventories"][0]["WHEAT"])
    )
    assert remaining_total == 10


def test_g2_multi_unit_assignment_reserves_observed_seeds():
    # animals disabled: this is a G2 multi-unit seed-reservation test, not a v1g animal-mass
    # test — with animals on, the 13 always-free BUILD_PASTURE/BUILD_COOP tasks (priority 2,
    # ahead of PLANT CARROT's priority 3) would outnumber the 4 units in this synthetic
    # from-scratch snapshot and starve the PLANT task entirely, which a real multi-day episode
    # never sees (that many free structures finish building well within day 0-1). Same pattern
    # already used by test_policy_returns_index_aligned_hand_actions / test_g1_scheduler_
    # reserves_time_to_water_new_plant for the same reason.
    previous_enabled = CONFIG["animals"]["enabled"]
    CONFIG["animals"]["enabled"] = False
    try:
        observation = _minimal_observation(
            step=6 * 24,
            hands=((3, 4), (3, 3), (4, 3)),
        )
        observation["private"]["seeds"]["CARROT"] = 1
        snapshot = parse(observation)
        plan = make_day_plan(snapshot, CONFIG)
        farmer_action, hand_actions, _ = assign(build_tasks(snapshot, plan, CONFIG), snapshot)
    finally:
        CONFIG["animals"]["enabled"] = previous_enabled
    plant_actions = [
        action
        for action in (farmer_action, *hand_actions)
        if action[:1] == ["PLANT"]
    ]
    assert plant_actions == [["PLANT", "CARROT"]]


def test_g6_hand_at_55_routes_across_locked_tiles():
    observation = _minimal_observation(step=6 * 24, hands=((5, 5),))
    snapshot = parse(observation)
    tasks = [
        Task("farmer", "WATER", (4, 4), 0),
        Task("hand", "WATER", (3, 4), 1),
    ]
    farmer_action, hand_actions, _ = assign(tasks, snapshot)
    assert farmer_action == ["WATER"]
    assert hand_actions == [["WEST"]]


def test_c1_planner_caps_plant_targets_when_watering_capacity_is_short():
    """review_89d99f0_2026-08-05.md C1/§5#5 — a wide farm (target tiles at distance 5-9 from the shed spawn) with
    only two units must not be handed the full plant_targets count: the day's unit-turns can't
    keep that many tiles watered, and the old config-only planner had no way to notice. The
    capacity gate should trim the target instead of setting the scheduler up to plant more
    than it can water (the structural v1c root cause, review_89d99f0_2026-08-05.md §1)."""
    wide_config = copy.deepcopy(CONFIG)
    wide_config["scheduler"]["target_tiles"] = {
        "CARROT": (
            (9, 4), (0, 4), (4, 9), (4, 0), (9, 9),
            (0, 0), (9, 0), (0, 9), (8, 4), (4, 8),
        ),  # distances 4-10 from the (4,4) shed spawn
        "STRAWBERRY": (),
    }
    wide_config["planner"]["carrot_tiles"] = 10
    wide_config["planner"]["strawberry_tiles"] = 0

    observation = _minimal_observation(step=0)  # farmer alone: no hands hired yet
    snapshot = parse(observation)
    plan = make_day_plan(snapshot, wide_config)

    assert 0 <= plan.plant_targets["CARROT"] < 10


def test_c1_slack_beats_distance_for_a_single_unit():
    """review_89d99f0_2026-08-05.md C1/§1.2 + §5#1: with one unit and two same-priority tasks, a distant task
    that is about to run out of time (low slack) must win over a near task that has plenty
    of slack — plain nearest-first would starve the distant, urgent tile until it's too late."""
    observation = _minimal_observation(step=0)
    observation["farms"][0]["farmer"] = [0, 0]
    snapshot = parse(observation)
    near_ample_slack = Task("near", "WATER", (1, 0), priority=0, deadline_step=100)
    far_low_slack = Task("far", "WATER", (9, 9), priority=0, deadline_step=20)
    farmer_action, _, _ = assign([near_ample_slack, far_low_slack], snapshot)
    assert farmer_action == ["EAST"]


def test_h4_debug_receipts_emit_and_reconcile(capsys):
    """review_89d99f0_2026-08-05.md H4 — the harness side (KAGGRI_RECEIPT parsing in play.py) already existed;
    this is the missing transmitter: a committed WATER must emit an expected_transition
    receipt now and a reconciliation receipt the next time this seat is observed."""
    # review.md L5: restore the actual prior value, not a hardcoded literal.
    previous_debug = CONFIG["guards"]["debug"]
    CONFIG["guards"]["debug"] = True
    try:
        _RUNTIME_BY_PLAYER.clear()
        observation = _minimal_observation(step=3 * 24)
        observation["private"]["seeds"]["CARROT"] = 1
        observation["farms"][0]["tiles"][4][4] = {
            "kind": "PLANT", "crop": "CARROT", "planted_day": 0,
            "watered_today": False, "consecutive_unwatered": 0,
            "yield_units": 2, "max_lifespan_step": 4 * 24,
            "fertilized_until_day": -1,
        }
        agent(observation)
        first_turn_out = capsys.readouterr().out
        assert '"kind": "expected_transition"' in first_turn_out
        assert '"action": "WATER"' in first_turn_out

        observation["farms"][0]["tiles"][4][4]["watered_today"] = True
        observation["step"] += 1
        agent(observation)
        second_turn_out = capsys.readouterr().out
        assert '"kind": "reconciliation"' in second_turn_out
        assert '"ok": true' in second_turn_out
    finally:
        CONFIG["guards"]["debug"] = previous_debug


def test_g5_feed_never_assigned_to_a_unit_without_wheat():
    """plan.md G5 — FEED's wheat is per-unit cargo from an earlier PICKUP (unlike PLANT's
    shared seed pool draw), so a unit carrying none of it must never be routed to FEED, even
    standing right on the animal's tile — assigning it would be a silent no-op the engine
    swallows without error (review_89d99f0_2026-08-05.md H4's G11 failure mode), and the animal would go right on
    starving toward `consecutive_unfed >= 2` escape."""
    observation = _minimal_observation(step=10, hands=((3, 3),))
    observation["farms"][0]["farmer"] = [4, 2]
    observation["farms"][0]["tiles"][2][4] = _animal_tile("COW", fed_today=False)
    observation["private"]["inventories"] = [{}, {"WHEAT": 1}]
    snapshot = parse(observation)
    task = Task("feed:4:2", "FEED", (4, 2), priority=0)

    farmer_action, hand_actions, _ = assign([task], snapshot)

    assert farmer_action != ["FEED"]
    assert hand_actions[0][0] in ("NORTH", "SOUTH", "EAST", "WEST", "FEED")


def test_v1h2d_feed_pickup_reserves_delivery_slack_and_inherits_escape_risk():
    observation = _minimal_observation(step=0)
    observation["farms"][0]["tiles"][0][0] = _animal_tile("SHEEP", fed_today=False)
    observation["farms"][0]["tiles"][0][0]["consecutive_unfed"] = 1
    observation["private"]["shed"]["WHEAT"] = 1
    snapshot = parse(observation)
    plan = make_day_plan(snapshot, CONFIG)

    pickups = [
        task
        for task in build_tasks(snapshot, plan, CONFIG)
        if task.kind == "PICKUP" and task.item == "WHEAT"
    ]

    assert pickups
    day_deadline = CONFIG["runtime"]["turns_per_day"] - 1
    shed = engine._shed_access_tiles(10)[0]
    delivery_distance = abs(shed[0]) + abs(shed[1])
    assert all(task.deadline_step == day_deadline - delivery_distance - 1 for task in pickups)
    assert all(task.priority == -1 for task in pickups)


def test_g8_harvest_offered_every_turn_product_is_held_not_just_at_cap():
    """plan.md G8 — `animals_needing`/`_build_animal_tasks` must offer HARVEST as soon as
    `yield_units > 0`, every turn, not only once a tile has already reached `max_held` — engine
    :805 clips a due production tick's output to `max_held` with no carry-over, so waiting
    until the cap is hit to start harvesting would already be one tick too late."""
    observation = _minimal_observation(step=10)
    observation["farms"][0]["tiles"][2][4] = _animal_tile("COW", yield_units=1)
    snapshot = parse(observation)
    plan = make_day_plan(snapshot, CONFIG)
    tasks = build_tasks(snapshot, plan, CONFIG)
    assert any(task.kind == "HARVEST" and task.pos == (4, 2) for task in tasks)


def test_v1c_buy_land_triggers_replan_and_grows_targets():
    """plan.md §5 v1c acceptance: observed BUY_LAND success (my_quadrants growing to include
    "NE") must cause a correct same-day replan, not wait for tomorrow's day boundary —
    otherwise a day's plan keeps plant_targets frozen at the pre-purchase NW-only baseline
    until the next day, wasting the newly-unlocked tiles for the rest of today. policy.py's
    _needs_replan already watches `last_quadrants != snapshot.my_quadrants` (review_89d99f0_2026-08-05.md M4); this
    exercises that path end-to-end through agent() and confirms the resulting plan actually
    reflects NE's bonus target tiles, not just that *some* replan happened.

    animals disabled: this is a CARROT-target/replan-timing test, not a v1g animal-mass test —
    with animals on, this fixture's 3-hand crew (a v1c-era count below v1g's hands_target)
    puts _animal_daily_demand's 13-animal upkeep above the day's unit-turn supply, capping
    plant_targets["CARROT"] at 0 both before and after NE unlock and masking what this test
    checks. Same pattern as test_g2_multi_unit_assignment_reserves_observed_seeds above."""
    previous_enabled = CONFIG["animals"]["enabled"]
    CONFIG["animals"]["enabled"] = False
    try:
        _RUNTIME_BY_PLAYER.clear()
        hands = ((4, 3), (3, 3), (2, 3))

        nw_only = _minimal_observation(step=10, hands=hands)
        agent(nw_only)
        runtime = _RUNTIME_BY_PLAYER[0]
        carrot_target_before = runtime.plan.plant_targets["CARROT"]

        nw_and_ne = _minimal_observation(step=11, hands=hands)
        nw_and_ne["farms"][0]["unlocked_quadrants"] = ["NW", "NE"]
        agent(nw_and_ne)
        plan_after = runtime.plan
    finally:
        CONFIG["animals"]["enabled"] = previous_enabled

    assert runtime.planned_day == 0  # still day 0 — this was an on-event replan, not a day roll
    assert plan_after.plant_targets["CARROT"] > carrot_target_before


def test_v1c_land_purchase_waits_for_animals_to_be_placed_first():
    """A v1c+v1d interaction bug found via a full smoke-test replay: BUY_LAND's own gate
    (hands_target hands hired) is satisfiable as early as day 0 hour ~2, well before COW/SHEEP
    are actually bought (hour 4/6) and placed. Land grabbing its $1000 first left too little
    cash for the very next day's wheat purchase, and both animals starved to death by day 2
    with zero engine-level errors. executor.py's land-purchase gate now also requires every
    planned animal to already be placed — this locks that ordering in."""
    from agent.executor import market_orders
    from agent.planner import DayPlan
    from agent.scheduler import make_ledger

    observation = _minimal_observation(step=1, hands=((4, 3), (3, 3), (2, 3)))
    observation["farms"][0]["money"] = 3000
    snapshot = parse(observation)
    ledger = make_ledger(snapshot)
    plan = DayPlan(hands_target=3, animal_purchases={"COW": 1, "SHEEP": 1})

    orders = market_orders(snapshot, plan, ledger, [], CONFIG)

    assert ["BUY_LAND"] not in orders


def test_v1e_liquidation_drop_excludes_carried_wheat():
    """plan.md §5 v1e: found via a smoke test once GOOSE's extra daily upkeep pushed the
    farmer into fetching WHEAT during liquidation (day >= endgame.liquidation_day) — the
    liquidation-phase DROP task used to treat ANY carried inventory as "cargo to dump",
    including WHEAT a unit had just PICKUP'd to carry to a FEED task. That handed the unit a
    same-position DROP task the very next turn, dumping the wheat straight back into the shed
    before it ever reached the animal, in an endless PICKUP/DROP loop — COW and SHEEP starved
    to consecutive_unfed >= 2 and escaped while the farmer never got there. build_tasks now
    excludes WHEAT from the liquidation DROP's cargo check; this locks that in, and confirms a
    unit carrying an actual sellable product (STRAWBERRY) still gets a DROP task as before."""
    from agent.planner import DayPlan

    hands = ((4, 3),)
    observation = _minimal_observation(step=10, hands=hands)
    observation["private"]["inventories"] = [{"WHEAT": 1}, {"STRAWBERRY": 2}]
    snapshot = parse(observation)
    plan = DayPlan(force_liquidation=True)

    tasks = build_tasks(snapshot, plan, CONFIG)

    drop_tasks = {task.allowed_unit: task for task in tasks if task.kind == "DROP"}
    assert 0 not in drop_tasks
    assert 1 in drop_tasks


def test_v1e_endgame_liquidation_sells_stranded_wheat():
    """plan.md G14: WHEAT is bought purely as animal feed and normally excluded from the
    day-to-day marginal-price sell loop (selling it there would just buy-high-sell-low against
    the agent's own feed pipeline, since the daily PICKUP->FEED loop keeps shed WHEAT near 0
    anyway) — but once liquidation starts, any WHEAT still sitting in the shed (rounding
    leftovers, or feed bought for an animal that already escaped) is real stranded value.
    executor.py's SELL loop now includes WHEAT only during force_liquidation."""
    from agent.executor import market_orders
    from agent.planner import DayPlan
    from agent.scheduler import make_ledger

    observation = _minimal_observation(step=10)
    observation["private"]["shed"]["WHEAT"] = 5
    snapshot = parse(observation)
    ledger = make_ledger(snapshot)

    growing_orders = market_orders(snapshot, DayPlan(), ledger, [], CONFIG)
    assert not any(order[:2] == ["SELL", "WHEAT"] for order in growing_orders)

    liquidating_orders = market_orders(snapshot, DayPlan(force_liquidation=True), ledger, [], CONFIG)
    assert any(order[:2] == ["SELL", "WHEAT"] for order in liquidating_orders)


def test_v1h2_d3_liquidation_respects_hard_floor():
    """v1h.2 D3 — the 1.32.6 flat town-centre demand made the day-26 full-shed dump sell
    dozens of MILK units at <=$5. Liquidation may broaden the product set (WHEAT above) and
    relax normal product floors, but it must retain the hard endgame floor."""
    from agent.executor import market_orders
    from agent.planner import DayPlan
    from agent.scheduler import make_ledger

    observation = _minimal_observation(step=CONFIG["endgame"]["liquidation_day"] * 24)
    observation["private"]["shed"]["MILK"] = 100
    observation["market"]["inventory"]["MILK"] = engine.MARKET_PARAMS["MILK"]["I0"]
    snapshot = parse(observation)
    floor = CONFIG["executor"]["liquidation_floor_price"]
    safety = CONFIG["executor"]["opponent_price_safety_units"]

    orders = market_orders(
        snapshot,
        DayPlan(sell_floor_price={"MILK": floor}, force_liquidation=True),
        make_ledger(snapshot),
        [],
        CONFIG,
    )
    milk_order = next(order for order in orders if order[:2] == ["SELL", "MILK"])
    sell_units = milk_order[2]

    assert 0 < sell_units < 100
    assert engine.market_price(
        "MILK", engine.MARKET_PARAMS["MILK"]["I0"] + sell_units - 1 + safety
    ) > floor
    assert engine.market_price(
        "MILK", engine.MARKET_PARAMS["MILK"]["I0"] + sell_units + safety
    ) <= floor


def test_v1g_animal_slot_ranges_carves_contiguous_blocks_per_name():
    """v1g: config["animals"]["targets"] moved from one reserved slot per unique animal name
    to N slots per name, carved contiguously out of a shared structure kind's tile pool in
    targets-dict order — the first COW-count tiles are COW's, the next SHEEP-count are
    SHEEP's. Two names sharing a structure must never see overlapping ranges."""
    from agent.animal_slots import animal_slot_ranges

    tiny_config = copy.deepcopy(CONFIG)
    tiny_config["scheduler"]["animal_structure_tiles"] = {
        "PASTURE": ((4, 4), (4, 3), (3, 4), (3, 3), (2, 4)),
    }
    tiny_config["animals"]["targets"] = {"COW": 3, "SHEEP": 2}

    ranges = animal_slot_ranges(tiny_config)

    assert ranges["COW"] == ((4, 4), (4, 3), (3, 4))
    assert ranges["SHEEP"] == ((3, 3), (2, 4))


def test_v1g_animal_daily_demand_sums_every_slot_not_just_one_per_name():
    """v1f's _animal_daily_demand charged one (distance + 1 + 1) term per unique animal name
    (there was only ever one slot each). v1g must charge one such term per reserved slot —
    a config with N same-named animals costs N times this, not 1x."""
    from agent.planner import _animal_daily_demand

    tiny_config = copy.deepcopy(CONFIG)
    tiny_config["scheduler"]["animal_structure_tiles"] = {
        "PASTURE": ((4, 4), (4, 3), (3, 4)),  # distances 0, 1, 1 from the (4, 4) shed spawn
    }
    tiny_config["animals"]["targets"] = {"COW": 3}

    assert _animal_daily_demand(tiny_config) == ((0 + 1) + 1) + ((1 + 1) + 1) + ((1 + 1) + 1)


def test_v1h2_d2_herd_diversifies_away_from_milk():
    """v1h.2 D2 — under 1.32.6, 6 COW per mirror side collapse MILK while WOOL remains
    healthy. The DEV pinned-basket screen selected 4C/6S over 4C/4S and 5C/4S."""
    assert CONFIG["animals"]["targets"] == {"COW": 4, "SHEEP": 6, "GOOSE": 0}


def test_v1g_zero_target_count_skips_structure_and_purchase():
    """v1g: a target count of 0 (e.g. GOOSE screened out) must produce no purchase demand and
    no structure-build demand for that name — this is the mechanism the goose keep/drop screen
    relies on, not a separate ablation flag."""
    zero_goose_config = copy.deepcopy(CONFIG)
    zero_goose_config["animals"]["targets"] = {"COW": 8, "SHEEP": 5, "GOOSE": 0}
    observation = _minimal_observation(step=0, hands=((4, 3), (3, 3), (2, 3), (2, 4), (1, 4)))
    snapshot = parse(observation)

    plan = make_day_plan(snapshot, zero_goose_config)

    assert "GOOSE" not in plan.animal_purchases
    assert plan.structures_to_build.get("COOP", 0) == 0


def test_v1g_placed_count_and_animal_placed_generalize_to_n_slots():
    """v1g: animal_placed used to mean "the one reserved slot for this name is filled", which
    for a count-of-1 name is identical to "fully placed". Now that a name can have N slots,
    placed_count must return an exact count and animal_placed must stay true as soon as at
    least one of them lands (it backs the BUY_LAND gate's "some investment already made in
    this animal type" check, not a full-herd check)."""
    from agent.scheduler import animal_placed, placed_count

    observation = _minimal_observation(step=10)
    observation["farms"][0]["tiles"][4][4] = _animal_tile("COW")
    observation["farms"][0]["tiles"][4][3] = _animal_tile("COW")
    snapshot = parse(observation)

    assert placed_count(snapshot, "COW") == 2
    assert animal_placed(snapshot, "COW") is True
    assert placed_count(snapshot, "SHEEP") == 0
    assert animal_placed(snapshot, "SHEEP") is False


def test_v1g_build_tasks_places_multiple_same_named_animals_in_parallel():
    """v1g: the old model queued at most one PICKUP + one PLACE per animal name per turn (fine
    when each name had exactly one slot). With N slots per name, build_tasks must queue a
    PLACE per still-open slot (so several units can each place a different COW in the same
    turn, not serialize one slot per turn) and a single PICKUP sized to how many more are
    actually needed."""
    from agent.planner import DayPlan

    tiny_config = copy.deepcopy(CONFIG)
    tiny_config["scheduler"]["animal_structure_tiles"] = {
        "PASTURE": ((4, 4), (3, 4), (4, 3)),
    }
    observation = _minimal_observation(step=10)
    observation["farms"][0]["tiles"][4][4] = {"kind": "PASTURE"}
    observation["farms"][0]["tiles"][4][3] = {"kind": "PASTURE"}
    observation["farms"][0]["tiles"][3][4] = {"kind": "PASTURE"}
    observation["private"]["shed"]["COW"] = 2
    snapshot = parse(observation)
    plan = DayPlan(animal_purchases={"COW": 3})

    tasks = build_tasks(snapshot, plan, tiny_config)

    place_tasks = [task for task in tasks if task.kind == "PLACE" and task.item == "COW"]
    pickup_tasks = [task for task in tasks if task.kind == "PICKUP" and task.item == "COW"]
    assert {task.pos for task in place_tasks} == {(4, 4), (3, 4), (4, 3)}
    assert len(pickup_tasks) == 1
    assert pickup_tasks[0].count == 2


def test_v1g_buy_animal_caps_at_open_slot_headroom():
    """v1g: buying more of a same-named animal than there are currently open, already-built
    homes for it would be dead capital sitting in the shed — the same MASTERPLAN §3.2#7 lesson
    land-without-hands teaches, generalized from "never buy a second one of the same target"
    (the old one-slot-per-name model) to "never buy past open homes"."""
    from agent.executor import market_orders
    from agent.planner import DayPlan
    from agent.scheduler import make_ledger

    tiny_config = copy.deepcopy(CONFIG)
    tiny_config["scheduler"]["animal_structure_tiles"] = {
        "PASTURE": ((4, 4), (3, 4)),
    }
    observation = _minimal_observation(step=10)
    observation["farms"][0]["money"] = 100_000
    observation["farms"][0]["tiles"][4][4] = {"kind": "PASTURE"}
    observation["farms"][0]["tiles"][4][3] = {"kind": "PASTURE"}
    snapshot = parse(observation)
    ledger = make_ledger(snapshot)
    plan = DayPlan(animal_purchases={"COW": 8})

    orders = market_orders(snapshot, plan, ledger, [], tiny_config)

    buy_orders = [order for order in orders if order[0] == "BUY_ANIMAL" and order[1] == "COW"]
    assert buy_orders == [["BUY_ANIMAL", "COW", 2]]


def _throttle_config():
    """CONFIG with the v1g.2 (γ) sell throttle forced ON.

    The shipped CONFIG has `dynamic_sell_floor: False` — the hypothesis was measured and
    falsified (see the comment on that key). The mechanism still has to be *correct* while it
    sits there disabled, so the tests below exercise it explicitly rather than inheriting the
    shipped flag: a disabled feature that has quietly rotted is worse than no feature. The
    evidence gate is opened to 0 for the same reason — these tests are about the demand model
    and the floor arithmetic, not about when the layer chooses to engage.
    """
    config = copy.deepcopy(CONFIG)
    config["executor"]["dynamic_sell_floor"] = True
    config["executor"]["shop_evidence_min_unlocks"] = 0
    return config


def _plan_with_shops(shops, *, day=5, shed=None, config=None):
    """A DayPlan built the way policy.agent builds it, for a town holding exactly `shops`."""
    observation = _minimal_observation(step=day * 24, shops=shops)
    observation["private"]["shed"] = dict(shed or {})
    return make_day_plan(parse(observation), config or _throttle_config())


def test_v1g2_shipped_config_keeps_the_falsified_throttle_disabled():
    """v1g.2 (γ): the throttle is OFF in the shipped agent and the plan therefore carries the
    static table verbatim. Pinned as a test because the measurement that disabled it is the
    whole result of the increment: turning the key back on is a $1,103/ep regression in a full
    town and $1,909/ep in the no-YARN_STORE town the layer was written for, with no measured
    upside in any town (0/8 episode wins everywhere)."""
    assert CONFIG["executor"]["dynamic_sell_floor"] is False

    plan = _plan_with_shops(sorted(engine.SHOPS), shed={"WOOL": 200}, config=CONFIG)

    assert plan.sell_floor_price == CONFIG["executor"]["sell_floor_price"]


def test_v1g2_evidence_gate_ignores_a_town_that_has_barely_unlocked():
    """v1g.2: shops appear one per townShopUnlockInterval in BOTH regimes, so an early town
    looks shop-poor whether or not it will ever draw the missing shop — "no buyer yet" is not
    evidence of "no buyer"."""
    config = _throttle_config()
    config["executor"]["shop_evidence_min_unlocks"] = 5

    early = _plan_with_shops(["BAKERY", "PET_CAFE"], day=4, config=config)

    assert early.sell_floor_price == CONFIG["executor"]["sell_floor_price"]


def test_v1g2_snapshot_keeps_shop_order_and_duplicates():
    """v1g.2 (α): after the announced balance change the engine draws shops WITH replacement,
    so a repeated name is a second buyer that consumes its own units every tick. Collapsing the
    list to a set would silently halve the measured demand of exactly the products a duplicated
    shop makes safe — and would also make the reading order-dependent on set iteration (G13)."""
    observation = _minimal_observation(shops=["YARN_STORE", "BAKERY", "YARN_STORE"])

    snapshot = parse(observation)

    assert snapshot.unlocked_shops == ("YARN_STORE", "BAKERY", "YARN_STORE")


def test_v1g2_npc_daily_demand_matches_engine_town_consume():
    """v1g.2 (β): the demand model is a reimplementation of `_town_consume`, so pin it against
    the engine by actually running a full day of the engine's own consumption and comparing the
    inventory it removed. Swept across shop sets (including duplicates and the empty town), the
    days that used to straddle the (now removed) town-centre ramp steps, and both the pre- and
    post-1.32.6 `townCenterSellInterval` — which is the whole point of reading the intervals out
    of `configuration` instead of hardcoding any one version's defaults. v1h.1: this test needed
    **no change** at the bump; it kept passing against the new `_town_consume` because it
    compares against the engine rather than against a transcribed rule."""
    import types

    from agent.demand import npc_daily_demand

    shop_sets = (
        [],
        ["YARN_STORE"],
        ["YARN_STORE", "YARN_STORE", "BAKERY"],
        sorted(engine.SHOPS),
    )
    configurations = (
        {"townShopSellInterval": 4, "townCenterSellInterval": 12, "turnsPerDay": 24},
        {"townShopSellInterval": 4, "townCenterSellInterval": 24, "turnsPerDay": 24},
        {"townShopSellInterval": 5, "townCenterSellInterval": 7, "turnsPerDay": 24},
    )
    for configuration in configurations:
        turns_per_day = configuration["turnsPerDay"]
        for shops in shop_sets:
            for day in (0, 9, 10, 19, 20, 29):
                market = engine._new_market()
                before = dict(market["inventory"])
                env = types.SimpleNamespace(configuration=configuration)
                state = [types.SimpleNamespace(
                    observation=types.SimpleNamespace(market=market, town={"unlocked_shops": list(shops)})
                )]
                for step in range(day * turns_per_day, (day + 1) * turns_per_day):
                    engine._town_consume(env, state, step)
                consumed = {
                    item: before[item] - market["inventory"][item]
                    for item in before
                    if before[item] != market["inventory"][item]
                }

                assert npc_daily_demand(shops, day, configuration) == consumed


def test_v1g2_zero_demand_products_keep_their_static_floor():
    """v1g.2 (γ): FERTILIZER has no buyer at all — no shop lists it and TOWN_CENTER_PRODUCTS
    excludes it — so its price is monotonically decreasing in cumulative sales and total revenue
    for a given number of units is path-independent. Throttling it can only strand stock at $0,
    which is also why §v1g.2 (δ) stays frozen: this feature must not become a third attempt at
    fertilizer timing by accident."""
    static = CONFIG["executor"]["sell_floor_price"]["FERTILIZER"]

    plan = _plan_with_shops(sorted(engine.SHOPS), shed={"FERTILIZER": 200})

    assert "FERTILIZER" not in {
        item for shop in engine.SHOPS.values() for item in shop
    }
    assert plan.sell_floor_price["FERTILIZER"] == static


def test_v1g2_missing_shop_raises_the_floor_of_its_only_product():
    """v1g.2 (γ) — the feature's whole reason to exist. WOOL is bought by exactly one shop type
    (YARN_STORE), so a town that never draws it leaves wool with town-centre demand only. Its
    glut curve is the steepest in the game (`sq`, above_target 3.20, cliff at 59 net units), so
    that is precisely where dumping is most expensive."""
    with_store = _plan_with_shops(sorted(engine.SHOPS))
    without_store = _plan_with_shops([s for s in sorted(engine.SHOPS) if s != "YARN_STORE"])

    assert without_store.sell_floor_price["WOOL"] > with_store.sell_floor_price["WOOL"]
    assert with_store.sell_floor_price["WOOL"] >= CONFIG["executor"]["sell_floor_price"]["WOOL"]


def test_v1g2_dynamic_floor_only_ever_raises_the_static_floor():
    """v1g.2: the static table stays the hard lower bound in every town, on every day. This is
    what makes `dynamic_sell_floor: False` an exact restore of pre-v1g.2 behaviour — i.e. what
    makes the $-gate a clean A/B rather than two unrelated sell policies."""
    static = CONFIG["executor"]["sell_floor_price"]
    towns = ([], ["YARN_STORE"], ["PET_CAFE", "PET_CAFE"], sorted(engine.SHOPS))

    for shops in towns:
        for day in (0, 12, 25):
            plan = _plan_with_shops(shops, day=day)
            for product, floor in static.items():
                assert plan.sell_floor_price[product] >= floor


def test_v1g2_liquidation_pressure_relaxes_the_throttle():
    """v1g.2: a floor that never lets go turns into a single endgame dump straight through the
    cliff it exists to avoid. Once the shed holds more than the days before liquidation_day can
    move at the throttled rate, the tolerated glut widens to at least the rate that clears it."""
    shops = [s for s in sorted(engine.SHOPS) if s != "YARN_STORE"]
    day = CONFIG["endgame"]["liquidation_day"] - 4

    light = _plan_with_shops(shops, day=day, shed={"WOOL": 4})
    heavy = _plan_with_shops(shops, day=day, shed={"WOOL": 400})

    assert heavy.sell_floor_price["WOOL"] < light.sell_floor_price["WOOL"]


def test_v1g2_throttle_cannot_add_a_market_order():
    """v1g.2: both frozen fertilizer attempts (§v1g.2 δ) lost money by pushing SELL WOOL past
    the engine's positional `q[:10]` cut. A floor can only shrink `sell_units` inside orders the
    executor was already emitting (and drop the ones it shrinks to zero), so this increment is
    structurally incapable of repeating that failure — pinned here so a later refactor into a
    real per-day rate budget can't quietly reintroduce the risk.

    ⚠️ **v1h.1 correction — the original claim was too strong, and 1.32.6 exposed it.** This test
    used to assert `set(throttled_sells) <= set(baseline_sells)`. That held only while the
    throttle never dropped an order at the 10-order cap. Under 1.32.6 the town centre buys 1/day
    instead of 4/day late season, so the throttle binds harder, WOOL is throttled to **zero
    units**, its order disappears — and FERTILIZER, which the cap had been cutting, moves into
    the freed slot. So the throttle *can* change **which** products are sold, indirectly, by
    changing how many orders compete for the cap. It still cannot **add** an order, and still
    cannot increase any product's units; those are the properties actually worth pinning, and
    they are what this test now asserts. The displacement itself is pinned explicitly below
    rather than left to be rediscovered.

    This does not change shipped behaviour (`dynamic_sell_floor` is `False` — §v1g.2 γ). It does
    weaken the "structurally incapable" argument for keeping the mechanism in the tree, so the
    flag stays off for one more measured reason, not fewer."""
    from agent.executor import market_orders
    from agent.scheduler import make_ledger

    shops = [s for s in sorted(engine.SHOPS) if s != "YARN_STORE"]
    observation = _minimal_observation(step=12 * 24, shops=shops)
    observation["farms"][0]["money"] = 50_000
    observation["private"]["shed"] = {
        "WOOL": 40, "MILK": 40, "CARROT": 40, "STRAWBERRY": 40, "FERTILIZER": 40,
    }
    observation["market"]["inventory"] = {
        item: params["I0"] for item, params in engine.MARKET_PARAMS.items()
    }
    snapshot = parse(observation)

    off_config = copy.deepcopy(CONFIG)
    off_config["executor"]["dynamic_sell_floor"] = False
    on_config = _throttle_config()
    baseline = market_orders(
        snapshot, make_day_plan(snapshot, off_config), make_ledger(snapshot), [], off_config
    )
    throttled = market_orders(
        snapshot, make_day_plan(snapshot, on_config), make_ledger(snapshot), [], on_config
    )

    assert len(throttled) <= len(baseline)
    baseline_sells = {order[1]: order[2] for order in baseline if order[0] == "SELL"}
    throttled_sells = {order[1]: order[2] for order in throttled if order[0] == "SELL"}

    # The two properties that actually protect against the (δ) failure: no product is sold in
    # larger size than it would have been, and the throttle never emits more orders in total
    # (`len(throttled) <= len(baseline)`, asserted above).
    for product, units in throttled_sells.items():
        assert units <= baseline_sells.get(product, units)

    # ...and the throttle is actually doing something in this town, so the above is not
    # vacuously true. Under 1.32.6 WOOL is throttled all the way out of the order list.
    assert throttled_sells.get("WOOL", 0) < baseline_sells["WOOL"]

    # v1h.1: the cap displacement, pinned deliberately. `baseline` is truncated at exactly
    # `max_market_orders`, so anything the throttle removes is immediately backfilled by the
    # order the cut had been dropping. A product appearing only in `throttled` is therefore
    # expected — but only ever one the executor already wanted to sell.
    displaced_in = set(throttled_sells) - set(baseline_sells)
    assert len(baseline) == int(CONFIG["executor"]["max_market_orders"])
    assert displaced_in <= {"FERTILIZER"}, (
        "throttle backfilled an unexpected product at the order cap; the (δ) crowd-out risk "
        "is order-position-sensitive, so any change here needs its own measurement"
    )
    # The sharpest way to state what the throttle bought here: **nothing**. Total units sold is
    # identical (40 WOOL swapped for 40 FERTILIZER); all the throttle did was choose a different
    # product to spend the same capped slot on. That is the §v1g.2 (γ) result — "no price to
    # win, only volume to lose" — reproduced at the order-cap level.
    assert sum(throttled_sells.values()) == sum(baseline_sells.values())


# --------------------------------------------------------------------------- v1h' (SW quadrant)


def _quadrant_of(x, y):
    return ("N" if y < 5 else "S") + ("W" if x < 5 else "E")


def test_v1h_wheat_tiles_are_all_sw_and_avoid_the_shed_doorway():
    """The SW target list is the whole of v1h's land use, so its structural properties are
    asserted rather than eyeballed: every tile is genuinely in SW (a stray NW/NE entry would be
    planted before the quadrant is even bought, stealing a tile from CARROT/STRAWBERRY), and
    none of them is one of the four shed-access tiles the 10-animal feed pipeline stands on."""
    wheat_tiles = CONFIG["scheduler"]["target_tiles"]["WHEAT"]
    assert wheat_tiles
    assert all(_quadrant_of(x, y) == "SW" for x, y in wheat_tiles)
    assert not set(wheat_tiles) & {tuple(t) for t in engine._shed_access_tiles(10)}
    assert len(set(wheat_tiles)) == len(wheat_tiles)
    # Nearest-shed-first: the commute is paid ~6 times per 5-day cycle, so this ordering is what
    # makes the capacity gate trim the *expensive* tiles first.
    distances = [abs(x - 4) + abs(y - 4) for x, y in wheat_tiles]
    assert distances == sorted(distances)


def test_v1h_no_animal_structure_sits_on_bought_land():
    """The BUY_LAND deadlock trap (current_phase.md §v1h): the purchase gate requires every
    planned animal to already be placed, so a PASTURE/COOP on a not-yet-bought quadrant can
    never be built, its animal can never be placed, and the land can never be bought. Already
    avoided twice by hand (COOP in v1e, PASTURE in v1g); this makes it a test."""
    for tiles in CONFIG["scheduler"]["animal_structure_tiles"].values():
        assert all(_quadrant_of(x, y) == "NW" for x, y in tiles)


def test_v1h_land_targets_follow_the_engines_own_order_and_stop_before_se():
    """BUY_LAND takes no argument — the engine picks LAND_ORDER[len(unlocked)-1] itself — so a
    config list that disagreed with LAND_ORDER would buy something other than what it names."""
    wanted = tuple(CONFIG["land"]["quadrants"])
    assert wanted == tuple(engine.LAND_ORDER[:len(wanted)])
    assert "SE" not in wanted


def test_v1h_buy_land_walks_from_ne_to_sw_at_the_right_price_then_stops():
    """One quadrant per purchase, priced by how many are already owned, and nothing once the
    configured list is exhausted — the engine would silently no-op an extra BUY_LAND, but the
    reserve check would already have committed the cash to it."""
    from agent.executor import market_orders
    from agent.planner import DayPlan

    def orders_for(quadrants, money):
        observation = _minimal_observation(step=1, hands=tuple((4, 3) for _ in range(6)))
        observation["farms"][0]["unlocked_quadrants"] = list(quadrants)
        observation["farms"][0]["money"] = money
        snapshot = parse(observation)
        plan = DayPlan(hands_target=6)  # no animal_purchases -> the animal gate is vacuous here
        return market_orders(snapshot, plan, make_ledger(snapshot), [], CONFIG)

    reserve = CONFIG["land"]["min_reserve"]
    assert ["BUY_LAND"] in orders_for(["NW"], 1000 + reserve)
    assert ["BUY_LAND"] not in orders_for(["NW"], 1000 + reserve - 1)
    # SW: $2000 + reserve — the price moved with the quadrant, it is not NE's $1000 again.
    assert ["BUY_LAND"] in orders_for(["NW", "NE"], 2000 + reserve)
    assert ["BUY_LAND"] not in orders_for(["NW", "NE"], 2000 + reserve - 1)
    # SE is not on the list at any price.
    assert ["BUY_LAND"] not in orders_for(["NW", "NE", "SW"], 100000)


def _plan_with_quadrants(quadrants, *, day, hands=8):
    observation = _minimal_observation(step=day * 24, hands=tuple((4, 3) for _ in range(hands)))
    observation["farms"][0]["unlocked_quadrants"] = list(quadrants)
    return make_day_plan(parse(observation), CONFIG)


def test_v1h_wheat_waits_for_sw_and_for_strawberrys_planting_window_to_close():
    """Two gates, both load-bearing. Without SW the tiles are LOCKED. And while STRAWBERRY is
    still being planted, _capacity_limited_targets trims whichever crop has the *largest*
    target — which would be STRAWBERRY (24) — so an early WHEAT target would be paid for out
    of STRAWBERRY's budget rather than its own."""
    last_strawberry_day = CONFIG["planner"]["strawberry_last_plant_day"]

    no_sw = _plan_with_quadrants(["NW", "NE"], day=last_strawberry_day + 3)
    assert no_sw.plant_targets.get("WHEAT", 0) == 0

    too_early = _plan_with_quadrants(["NW", "NE", "SW"], day=last_strawberry_day)
    assert too_early.plant_targets.get("WHEAT", 0) == 0

    ready = _plan_with_quadrants(["NW", "NE", "SW"], day=last_strawberry_day + 1)
    assert ready.plant_targets.get("WHEAT", 0) > 0


def test_v1h_wheat_planting_stops_in_time_to_still_mature():
    """WHEAT is one-shot: HARVEST empties the tile, and yield only peaks at max_yield_day. A
    seed planted past wheat_last_plant_day is a tile watered for the rest of the season and
    harvested by nobody."""
    last_day = CONFIG["planner"]["wheat_last_plant_day"]
    assert _plan_with_quadrants(["NW", "NE", "SW"], day=last_day).plant_targets.get("WHEAT", 0) > 0
    assert _plan_with_quadrants(["NW", "NE", "SW"], day=last_day + 1).plant_targets.get("WHEAT", 0) == 0
    assert last_day + engine.CROPS["WHEAT"]["max_yield_day"] <= CONFIG["endgame"]["liquidation_day"]


def test_v1h_crew_grows_only_once_sw_is_actually_owned():
    """v1f measured hands_target=6 as the optimum *for the workload it had*. The crew rises with
    the third quadrant, not with the intention to buy it — hands are re-hired (and re-paid)
    every single morning, so an early bump is a recurring cost against tiles that don't exist."""
    assert _plan_with_quadrants(["NW", "NE"], day=10).hands_target == CONFIG["planner"]["hands_target"]
    assert (
        _plan_with_quadrants(["NW", "NE", "SW"], day=10).hands_target
        == CONFIG["planner"]["sw_hands_target"]
    )
    # ...and it drops back for the endgame, once SW's last crop is harvestable. Carrying the
    # bigger crew into liquidation cost exactly 2 far SHEEP per episode in all four smoke seeds
    # (see planner.make_day_plan) — the endgame runs at the crew v1g's feed logistics were
    # tuned for.
    last_work_day = (
        CONFIG["planner"]["wheat_last_plant_day"] + engine.CROPS["WHEAT"]["max_yield_day"]
    )
    assert (
        _plan_with_quadrants(["NW", "NE", "SW"], day=last_work_day).hands_target
        == CONFIG["planner"]["sw_hands_target"]
    )
    assert (
        _plan_with_quadrants(["NW", "NE", "SW"], day=last_work_day + 1).hands_target
        == CONFIG["planner"]["hands_target"]
    )
    assert last_work_day < CONFIG["endgame"]["liquidation_day"]


def test_v1h_wheat_seeds_are_only_bought_once_wheat_is_actually_targeted():
    """BUY_SEED WHEAT must be inert before SW: plant_targets has no WHEAT key at all until then,
    so _remaining_unplanted_targets sees a limit of 0 and buys nothing."""
    from agent.executor import market_orders
    from agent.planner import DayPlan

    observation = _minimal_observation(step=24 * 10, hands=tuple((4, 3) for _ in range(6)))
    observation["farms"][0]["money"] = 50000
    snapshot = parse(observation)

    without = market_orders(snapshot, DayPlan(plant_targets={"CARROT": 3}),
                             make_ledger(snapshot), [], CONFIG)
    assert not [order for order in without if order[:2] == ["BUY_SEED", "WHEAT"]]

    with_wheat = market_orders(snapshot, DayPlan(plant_targets={"WHEAT": 8}),
                                make_ledger(snapshot), [], CONFIG)
    assert [order for order in with_wheat if order[:2] == ["BUY_SEED", "WHEAT"]]


def test_v1h_wheat_is_watered_inside_its_yield_window_not_only_every_other_day():
    """The engine grows a non-ongoing crop's yield_units only on a WATER inside
    [(max_yield_day+1)//2, max_yield_day]. Watering WHEAT purely on the survival rule
    (consecutive_unwatered >= 1) alternates days and would land inside that window at most
    once, turning a 3-unit tile into a 1-unit tile."""
    x, y = CONFIG["scheduler"]["target_tiles"]["WHEAT"][0]
    crop_data = engine.CROPS["WHEAT"]
    window = ((crop_data["max_yield_day"] + 1) // 2, crop_data["max_yield_day"])

    def water_tasks_at(age):
        day = 10
        observation = _minimal_observation(step=day * 24, hands=tuple((4, 4) for _ in range(8)))
        observation["farms"][0]["unlocked_quadrants"] = ["NW", "NE", "SW"]
        observation["farms"][0]["tiles"][y][x] = {
            "kind": "PLANT", "crop": "WHEAT", "planted_day": day - age,
            "watered_today": False, "consecutive_unwatered": 0, "yield_units": 0,
            "fertilized_until_day": -1,
        }
        snapshot = parse(observation)
        plan = make_day_plan(snapshot, CONFIG)
        return [
            task for task in build_tasks(snapshot, plan, CONFIG)
            if task.kind == "WATER" and task.pos == (x, y)
        ]

    # consecutive_unwatered is 0 in every case below, so the survival rule alone produces
    # nothing — any WATER task here comes from the yield window.
    for age in range(window[0], window[1] + 1):
        assert water_tasks_at(age), f"no WATER task for WHEAT at age {age}"
    assert not water_tasks_at(0)


