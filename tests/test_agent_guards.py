"""Incremental guard tests for the rule-based agent."""
import json
import os
import subprocess
import sys
from pathlib import Path

from kaggle_environments.envs.kaggriculture import kaggriculture as engine

from agent import _vendored
from agent.config import CONFIG
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


def test_g12_main_exports_server_selected_agent():
    loaded = resolve_agent(str(MAIN), entrypoint="agent")
    assert loaded.__name__ == "agent"


def test_policy_returns_index_aligned_hand_actions():
    action = agent(_minimal_observation(hands=((5, 4), (4, 5))))
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
    for item, params in engine.MARKET_PARAMS.items():
        equilibrium, capacity = params["I0"], params["T"]
        for inventory in (equilibrium - capacity, equilibrium, equilibrium + capacity):
            assert _vendored.market_price(item, inventory) == engine.market_price(item, inventory)


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
    observation = _minimal_observation(step=22)
    observation["private"]["seeds"]["CARROT"] = 1
    snapshot = parse(observation)
    plan = make_day_plan(snapshot, CONFIG)
    tasks = build_tasks(snapshot, plan, CONFIG)
    farmer_action, _ = assign(tasks, snapshot)
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
    farmer_action, _ = assign(build_tasks(snapshot, plan, CONFIG), snapshot)
    assert farmer_action == ["WATER"]

    observation["farms"][0]["tiles"][4][4]["watered_today"] = True
    snapshot = parse(observation)
    farmer_action, _ = assign(build_tasks(snapshot, plan, CONFIG), snapshot)
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
    farmer_action, hand_actions = assign(build_tasks(snapshot, plan, CONFIG), snapshot)
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
    farmer_action, hand_actions = assign(tasks, snapshot)
    assert farmer_action == ["WATER"]
    assert hand_actions == [["WEST"]]


