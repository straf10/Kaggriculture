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
    assert metrics["units_sold_by_product"]["MELON"] == 200
    assert metrics["market_sales"][0]["day"] == 0


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


def test_metrics_detect_clipped_animal_production():
    """plan.md G8 — engine.py:805 clips `yield_units + base + bonus` to `max_held` on every
    due production tick with no carry-over; a tile already sitting at `max_held` going into a
    due tick has that whole tick's production silently discarded for lack of a HARVEST."""
    env = make(
        "kaggriculture",
        configuration={"seed": 0, "episodeSteps": 4, "turnsPerDay": 2, "weedSpawnChance": 0},
    )
    farm = env.state[0].observation.farms[0]
    tile = engine._new_animal("GOOSE", -5)  # first_yield_day=4, interval=1: due every day
    tile["yield_units"] = engine.ANIMALS["GOOSE"]["max_held"]
    farm["tiles"][0][1] = tile
    replay = _finish(env)

    metrics = extract_metrics(replay, 0)
    assert metrics["clipped_production_ticks"] >= 1
    clip_events = [e for e in metrics["loss_events"] if e["type"] == "clipped_production_ticks"]
    assert len(clip_events) == metrics["clipped_production_ticks"]


def test_metrics_unexplained_noops_none_without_diagnostics():
    """plan.md §1.5.4 — absence of receipts must read as 'not measured' (None), not a false 0."""
    env = make("kaggriculture", configuration={"seed": 0, "episodeSteps": 4})
    replay = _finish(env)
    metrics = extract_metrics(replay, 0)
    assert metrics["unexplained_noops"] is None


def test_metrics_unexplained_noops_counts_failed_reconciliations_for_this_seat():
    env = make("kaggriculture", configuration={"seed": 0, "episodeSteps": 4})
    replay = _finish(env)
    diagnostics = [
        {"seat": 0, "kind": "reconciliation", "ok": False},
        {"seat": 0, "kind": "reconciliation", "ok": True},
        {"seat": 1, "kind": "reconciliation", "ok": False},  # other seat — must not count
        {"seat": 0, "kind": "expected_transition"},  # not a reconciliation — must not count
    ]
    metrics = extract_metrics(replay, 0, diagnostics=diagnostics)
    assert metrics["unexplained_noops"] == 1


def test_metrics_daily_and_loss_events_present():
    env = make(
        "kaggriculture",
        configuration={"seed": 0, "episodeSteps": 4, "turnsPerDay": 2, "weedSpawnChance": 0},
    )
    farm = env.state[0].observation.farms[0]
    farm["tiles"][0][0] = engine._new_plant("CARROT", 0, 2)
    replay = _finish(env)

    metrics = extract_metrics(replay, 0)
    assert isinstance(metrics["daily"], list) and len(metrics["daily"]) >= 1
    assert all("water_weeds_lost" in row and "day" in row for row in metrics["daily"])
    assert isinstance(metrics["loss_events"], list)
    decay_events_total = sum(
        e["units"] for e in metrics["loss_events"] if e["type"] == "plant_decay_units_lost"
    )
    assert decay_events_total == metrics["plant_decay_units_lost"]


def test_metrics_own_harvest_not_counted_as_decay():
    """review_89d99f0_2026-08-05.md M8(b) — a HARVEST on the exact step a plant crosses into its decay window
    zeroes yield_units too (by design); that must not be mistaken for decay loss."""
    env = make(
        "kaggriculture",
        configuration={"seed": 0, "episodeSteps": 4, "turnsPerDay": 2, "weedSpawnChance": 0},
    )
    farm = env.state[0].observation.farms[0]
    farm["farmer"] = [0, 0]
    farm["tiles"][0][0] = {
        "kind": "PLANT", "crop": "STRAWBERRY", "planted_day": -10,
        "watered_today": False, "consecutive_unwatered": 0,
        "yield_units": 4, "max_lifespan_step": 0, "fertilized_until_day": -1,
    }
    replay = _finish(env, {"farmer": ["HARVEST"], "hands": [], "market": []})

    metrics = extract_metrics(replay, 0)
    assert metrics["plant_decay_units_lost"] == 0
