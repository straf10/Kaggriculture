"""Operational replay metrics introduced by the v0.5 foundation."""
from kaggle_environments import make
from kaggle_environments.envs.kaggriculture import kaggriculture as engine

from harness.metrics import extract_metrics

PASS = {"farmer": ["PASS"], "hands": [], "market": []}


def _finish(env, first_action=PASS):
    actions = [first_action, PASS]
    while not env.done:
        env.step(actions)
        actions = [PASS, PASS]
    return env.toJSON()


def test_metrics_reconstruct_actual_sale_prices():
    env = make(
        "kaggriculture",
        configuration={"seed": 0, "episodeSteps": 4},
    )
    env.state[0].observation.private["shed"]["MELON"] = 200
    replay = _finish(
        env,
        {"farmer": ["PASS"], "hands": [], "market": [["SELL", "MELON", 200]]},
    )

    metrics = extract_metrics(replay, 0)
    assert len(metrics["market_sales"]) == 200
    assert metrics["market_sales"][0]["price"] == 250
    assert metrics["units_sold_at_or_below_5"] > 0
    assert metrics["average_sell_price"]["MELON"] > 1


def test_metrics_detect_end_of_day_shed_overflow():
    env = make(
        "kaggriculture",
        configuration={"seed": 0, "episodeSteps": 4, "turnsPerDay": 2},
    )
    private = env.state[0].observation.private
    private["shed"]["WHEAT"] = 95
    private["inventories"][0]["CARROT"] = 10
    replay = _finish(env)

    metrics = extract_metrics(replay, 0)
    assert metrics["shed_overflow_burnt"] == 5


def test_metrics_detect_plant_loss_and_animal_escape():
    env = make(
        "kaggriculture",
        configuration={"seed": 0, "episodeSteps": 4, "turnsPerDay": 2, "weedSpawnChance": 0},
    )
    farm = env.state[0].observation.farms[0]
    farm["tiles"][0][0] = engine._new_plant("CARROT", 0, 2)
    farm["tiles"][0][1] = engine._new_animal("GOOSE", -1)
    farm["tiles"][0][1]["consecutive_unfed"] = 1
    replay = _finish(env)

    metrics = extract_metrics(replay, 0)
    assert metrics["weeds_lost"] == 1
    assert metrics["water_weeds_lost"] == 1
    assert metrics["animals_escaped"] == 1
