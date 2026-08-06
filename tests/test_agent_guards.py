"""Incremental guard tests for the rule-based agent."""
import copy
import json
import os
import subprocess
import sys
from pathlib import Path

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


def _minimal_observation(*, player=0, step=0, hands=()):
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
        "town": {"unlocked_shops": []},
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
    CONFIG["animals"]["enabled"] = False
    try:
        action = agent(_minimal_observation(hands=((5, 4), (4, 5))))
    finally:
        CONFIG["animals"]["enabled"] = True
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
    # review.md L9 — TOWN_CENTER_DEMAND_SCHEDULE was vendored but never pinned by a test.
    assert _vendored.TOWN_CENTER_DEMAND_SCHEDULE == engine.TOWN_CENTER_DEMAND_SCHEDULE
    for item, params in engine.MARKET_PARAMS.items():
        equilibrium, capacity = params["I0"], params["T"]
        for inventory in (equilibrium - capacity, equilibrium, equilibrium + capacity):
            assert _vendored.market_price(item, inventory) == engine.market_price(item, inventory)


def test_l3_hire_cost_matches_engine():
    """review.md L3 — executor._hire_cost is a hand-copied reimplementation of the engine's
    fib-cost sequence with no parity test, unlike the rest of the vendored constants."""
    from agent.executor import _hire_cost

    for n in range(8):
        assert _hire_cost(n) == engine._hire_cost(n)


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
    CONFIG["animals"]["enabled"] = False
    try:
        observation = _minimal_observation(step=22)
        observation["private"]["seeds"]["CARROT"] = 1
        snapshot = parse(observation)
        plan = make_day_plan(snapshot, CONFIG)
        tasks = build_tasks(snapshot, plan, CONFIG)
        farmer_action, _, _ = assign(tasks, snapshot)
    finally:
        CONFIG["animals"]["enabled"] = True
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
    assert make_ledger(snapshot).market_slots == 10


def test_m7_market_orders_truncates_instead_of_raising():
    """review.md M7 — exceeding the market order budget used to `raise AssertionError`, which
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


def test_g2_multi_unit_assignment_reserves_observed_seeds():
    observation = _minimal_observation(
        step=6 * 24,
        hands=((3, 4), (3, 3), (4, 3)),
    )
    observation["private"]["seeds"]["CARROT"] = 1
    snapshot = parse(observation)
    plan = make_day_plan(snapshot, CONFIG)
    farmer_action, hand_actions, _ = assign(build_tasks(snapshot, plan, CONFIG), snapshot)
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
    """review.md C1/§5#5 — a wide farm (target tiles at distance 5-9 from the shed spawn) with
    only two units must not be handed the full plant_targets count: the day's unit-turns can't
    keep that many tiles watered, and the old config-only planner had no way to notice. The
    capacity gate should trim the target instead of setting the scheduler up to plant more
    than it can water (the structural v1c root cause, review.md §1)."""
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
    """review.md C1/§1.2 + §5#1: with one unit and two same-priority tasks, a distant task
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
    """review.md H4 — the harness side (KAGGRI_RECEIPT parsing in play.py) already existed;
    this is the missing transmitter: a committed WATER must emit an expected_transition
    receipt now and a reconciliation receipt the next time this seat is observed."""
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
        CONFIG["guards"]["debug"] = False


def test_g5_feed_never_assigned_to_a_unit_without_wheat():
    """plan.md G5 — FEED's wheat is per-unit cargo from an earlier PICKUP (unlike PLANT's
    shared seed pool draw), so a unit carrying none of it must never be routed to FEED, even
    standing right on the animal's tile — assigning it would be a silent no-op the engine
    swallows without error (review.md's G11 failure mode), and the animal would go right on
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
    _needs_replan already watches `last_quadrants != snapshot.my_quadrants` (review.md M4); this
    exercises that path end-to-end through agent() and confirms the resulting plan actually
    reflects NE's bonus target tiles, not just that *some* replan happened."""
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

    assert runtime.planned_day == 0  # still day 0 — this was an on-event replan, not a day roll
    assert plan_after.plant_targets["CARROT"] > carrot_target_before


def test_v1c_land_purchase_waits_for_animals_to_be_placed_first():
    """A v1c+v1d interaction bug found via a full smoke-test replay: BUY_LAND's own gate
    (hands_target hands hired) is satisfiable as early as day 0 hour ~2, well before COW/SHEEP
    are actually bought (hour 4/6) and placed. Land grabbing its $2000 first left too little
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


