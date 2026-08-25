"""Operational replay metrics introduced by the v0.5 foundation."""
import pytest
from kaggle_environments import make
from kaggle_environments.envs.kaggriculture import kaggriculture as engine

from harness.metrics import _transition_events, extract_metrics

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
    assert metrics["unexpected_weeds_lost"] == 1
    assert metrics["water_weeds_lost"] == 1
    assert metrics["animals_escaped"] == 1


def test_metrics_detect_clipped_animal_production():
    """G8 — engine.py:805 clips `yield_units + base + bonus` to `max_held` on every
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
    """Absence of receipts must read as 'not measured' (None), not a false 0."""
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


def test_v1k_metrics_report_crop_tile_days_and_total_worker_turns():
    env = make(
        "kaggriculture",
        configuration={"seed": 0, "episodeSteps": 4, "turnsPerDay": 2, "weedSpawnChance": 0},
    )
    farm = env.state[0].observation.farms[0]
    plant = engine._new_plant("STRAWBERRY", 0, 2)
    plant["watered_today"] = True
    plant["consecutive_unwatered"] = 0
    farm["tiles"][0][0] = plant
    replay = _finish(env)

    metrics = extract_metrics(replay, 0)
    assert metrics["crop_tile_days"] == 2
    assert metrics["worker_turns_total"] == (
        metrics["worker_turns_moving"]
        + metrics["worker_turns_working"]
        + metrics["worker_turns_idle"]
    )
    assert metrics["worker_turns_idle"] == metrics["worker_turns_total"]
    assert metrics["crop_revenue"] == 0


def test_v1m_metrics_report_realized_price_per_unit_by_product():
    """v1m — crop_revenue is a sum; gate needs realized $/u per product."""
    env = make(
        "kaggriculture",
        configuration={"seed": 0, "episodeSteps": 2, "turnsPerDay": 2, "weedSpawnChance": 0},
    )
    replay = _finish(env)
    metrics = extract_metrics(replay, 0)
    assert "revenue_by_product" in metrics
    assert "realized_price_per_unit" in metrics
    assert isinstance(metrics["revenue_by_product"], dict)
    assert isinstance(metrics["realized_price_per_unit"], dict)
    for item, revenue in metrics["revenue_by_product"].items():
        units = metrics["units_sold_by_product"][item]
        assert units > 0
        assert metrics["realized_price_per_unit"][item] == pytest.approx(revenue / units)


def test_v1l_metrics_report_crop_revenue_from_plant_sales_only():
    env = make(
        "kaggriculture",
        configuration={"seed": 0, "episodeSteps": 2, "turnsPerDay": 2, "weedSpawnChance": 0},
    )
    replay = _finish(env)
    # Inject market sales into the finished replay the same way extract_metrics reads them.
    steps = replay["steps"]
    # extract_metrics reconstructs sales from engine info; for a unit test, patch via a
    # minimal synthetic sales path by checking the returned field exists and ignores animals.
    metrics = extract_metrics(replay, 0)
    assert "crop_revenue" in metrics
    assert isinstance(metrics["crop_revenue"], int)
    assert metrics["crop_revenue"] >= 0


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


def test_v1h2d_successful_ongoing_harvest_retirement_is_expected():
    env = make(
        "kaggriculture",
        configuration={"seed": 0, "episodeSteps": 4, "turnsPerDay": 2, "weedSpawnChance": 0},
    )
    farm = env.state[0].observation.farms[0]
    farm["farmer"] = [0, 0]
    farm["tiles"][0][0] = {
        "kind": "PLANT", "crop": "STRAWBERRY", "planted_day": -10,
        "watered_today": True, "consecutive_unwatered": 0,
        "yield_units": 1, "max_lifespan_step": 0, "fertilized_until_day": -1,
    }
    replay = _finish(env, {"farmer": ["HARVEST"], "hands": [], "market": []})

    metrics = extract_metrics(replay, 0)
    assert metrics["weeds_lost"] == 1
    assert metrics["unexpected_weeds_lost"] == 0
    assert metrics["plant_decay_units_lost"] == 0


def test_v1h2d_retirement_is_expected_even_when_it_lands_turns_after_the_harvest():
    """The engine does not retire a harvested ongoing crop in the harvest's own turn: it
    retires it at the next max_lifespan_step decay tick. Measured on a real episode (seed 1),
    that gap is 17-24 steps — harvests at 389/392/416/419/438, retirements at 408/432/456 —
    so a same-transition-only exclusion marks every one of them as an unexpected loss and
    prices ~8 healthy retirements per episode as $2,400/ep of damage.

    The second tile is the other half of the guard: the accumulated set must not turn into a
    blanket amnesty for whatever else weeds over on a later turn.
    """
    env = make(
        "kaggriculture",
        configuration={"seed": 0, "episodeSteps": 12, "turnsPerDay": 2, "weedSpawnChance": 0},
    )
    farm = env.state[0].observation.farms[0]
    farm["farmer"] = [0, 0]
    plant = {
        "kind": "PLANT", "crop": "STRAWBERRY", "planted_day": -10,
        "watered_today": True, "consecutive_unwatered": 0,
        "yield_units": 1, "max_lifespan_step": 4, "fertilized_until_day": -1,
    }
    farm["tiles"][0][0] = dict(plant)  # harvested to zero on step 0, retires on step 4
    farm["tiles"][0][1] = dict(plant)  # never harvested, retires on the same schedule
    replay = _finish(env, {"farmer": ["HARVEST"], "hands": [], "market": []})

    metrics = extract_metrics(replay, 0)
    assert metrics["weeds_lost"] == 2
    assert metrics["unexpected_weeds_lost"] == 1  # only the tile nobody harvested
    # Both tiles are still charged for the unit that was on them when the decay tick landed:
    # an ongoing crop regrows after being harvested, and the regrown unit is a real loss.
    # Retirement being expected does not make the produce left on the plant free.
    assert metrics["plant_decay_units_lost"] == 2


def test_v1h2d_unharvested_decay_remains_unexpected_and_hard_loss():
    env = make(
        "kaggriculture",
        configuration={"seed": 0, "episodeSteps": 4, "turnsPerDay": 2, "weedSpawnChance": 0},
    )
    farm = env.state[0].observation.farms[0]
    farm["farmer"] = [0, 0]
    farm["tiles"][0][0] = {
        "kind": "PLANT", "crop": "STRAWBERRY", "planted_day": -10,
        "watered_today": True, "consecutive_unwatered": 0,
        "yield_units": 1, "max_lifespan_step": 0, "fertilized_until_day": -1,
    }
    replay = _finish(env)

    metrics = extract_metrics(replay, 0)
    assert metrics["weeds_lost"] == 1
    assert metrics["unexpected_weeds_lost"] == 1
    assert metrics["plant_decay_units_lost"] == 1


# ---------------------------------------------------------------------------
# S10 P2.1 — the differential floor/fill counters.
#
# These were added for the S10 gate but shipped with no coverage at all: the only
# test touching them was a live-replay parity test, which skips on any checkout
# without the gitignored corpus (i.e. always, in CI). Everything below runs on a
# synthetic `make("kaggriculture")` episode, so it runs everywhere.
# ---------------------------------------------------------------------------
def _run(env, action_for_step, other=PASS):
    """Step the env to completion, choosing seat 0's action per step index."""
    i = 0
    while not env.done:
        env.step([action_for_step(i), other])
        i += 1
    return env.toJSON()


def _sell(item, qty):
    return {"farmer": ["PASS"], "hands": [], "market": [["SELL", item, qty]]}


def test_s10_floor_counters_count_dollar_one_sales():
    """A bulk dump walks the price to $1; those units are destroyed, not traded."""
    env = make("kaggriculture", configuration={"seed": 0, "episodeSteps": 4})
    env.state[0].observation.private["shed"]["MELON"] = 200
    replay = _finish(env, _sell("MELON", 200))
    m = extract_metrics(replay, 0)

    floor_sales = [s for s in m["market_sales"] if s["price"] == 1]
    assert m["floor_units"] == len(floor_sales) > 0
    assert m["floor_units_by_product"]["MELON"] == m["floor_units"]
    # The ordered walk assumes every unit commits, so it can only be an upper bound.
    assert m["floor_units_ordered"] >= m["floor_units"]


def test_s10_sell_fill_is_committed_over_ordered():
    """Ordering more than the shed holds is the open-loop desync P5.1 quantifies."""
    env = make("kaggriculture", configuration={"seed": 0, "episodeSteps": 4})
    env.state[0].observation.private["shed"]["MELON"] = 10
    replay = _finish(env, _sell("MELON", 50))
    m = extract_metrics(replay, 0)

    assert m["sell_units_ordered"] == 50
    assert m["sell_units_committed"] == 10          # the shed ran out
    assert m["sell_units_committed"] == len(m["market_sales"])
    assert m["realized_units_by_product"]["MELON"] == 10


def test_s10_ordered_counters_honour_the_engine_order_cap():
    """🔴 Regression: the engine truncates the queue to maxMarketOrdersPerTurn BEFORE
    quoting (kaggriculture._process_market), and so does _simulate_market. An ordered
    counter that reads the untruncated action counts units the engine never sees and
    silently depresses fill below 1,0 on an episode where every unit committed."""
    env = make("kaggriculture",
               configuration={"seed": 0, "episodeSteps": 4, "maxMarketOrdersPerTurn": 3})
    env.state[0].observation.private["shed"]["MELON"] = 50
    over_cap = {"farmer": ["PASS"], "hands": [],
                "market": [["SELL", "MELON", 1] for _ in range(9)]}
    replay = _finish(env, over_cap)
    m = extract_metrics(replay, 0)

    assert m["sell_units_ordered"] == 3, "orders past the cap must not be counted"
    assert m["sell_units_committed"] == 3
    assert m["sell_units_ordered"] == m["sell_units_committed"]   # fill is exactly 1,0


def test_s10_shed_peak_sees_the_final_observation():
    """🔴 Regression: shed_peak sampled only `previous_observation`, so the last step of
    the episode was never looked at. Here the shed grows monotonically (bought goods land
    in the shed), so the true peak IS the final observation."""
    env = make("kaggriculture", configuration={"seed": 0, "episodeSteps": 6})
    env.state[0].observation.farms[0]["money"] = 100000
    buy = {"farmer": ["PASS"], "hands": [], "market": [["BUY_PRODUCT", "WHEAT", 3]]}
    replay = _run(env, lambda i: buy)          # buy on EVERY step, so the shed only grows
    m = extract_metrics(replay, 0)

    sheds = [sum(step[0]["observation"]["private"]["shed"].values())
             for step in replay["steps"]]
    assert sheds[-1] > sheds[-2], "fixture must still be growing on the last step"
    assert m["shed_peak"] == max(sheds) == sheds[-1]


def test_s10_per_day_counters_sum_to_the_episode_totals():
    """P5.1's day axis must be a partition of the same units, not a second measurement."""
    env = make("kaggriculture", configuration={"seed": 0, "episodeSteps": 6, "turnsPerDay": 2})
    env.state[0].observation.private["shed"]["MELON"] = 40
    replay = _run(env, lambda i: _sell("MELON", 4))
    m = extract_metrics(replay, 0)

    assert sum(m["sell_units_ordered_by_day"].values()) == m["sell_units_ordered"]
    assert sum(m["sell_units_committed_by_day"].values()) == m["sell_units_committed"]
    assert set(m["sell_units_committed_by_day"]) <= set(m["sell_units_ordered_by_day"])


def test_s10_tail_share_by_product_is_the_day_20_plus_revenue_share():
    """A change that moves revenue into the tail without changing the total shows here."""
    env = make("kaggriculture",
               configuration={"seed": 0, "episodeSteps": 24, "turnsPerDay": 1,
                              "weedSpawnChance": 0})
    env.state[0].observation.private["shed"]["MELON"] = 40
    # Sell MELON only from day 20 onwards; every MELON dollar is tail revenue.
    replay = _run(env, lambda i: _sell("MELON", 2) if i >= 20 else PASS)
    m = extract_metrics(replay, 0)

    assert m["revenue_by_product"].get("MELON", 0) > 0
    assert m["tail_share_by_product"]["MELON"] == pytest.approx(1.0)
    for item, share in m["tail_share_by_product"].items():
        assert 0.0 <= share <= 1.0


def test_s10_realized_aliases_track_their_sources():
    """`realized_*_by_product` are the plan's names for the existing dicts — if they ever
    stop being the same object/value, the P2.2 parity test is comparing the wrong thing."""
    env = make("kaggriculture", configuration={"seed": 0, "episodeSteps": 4})
    env.state[0].observation.private["shed"]["MELON"] = 20
    replay = _finish(env, _sell("MELON", 20))
    m = extract_metrics(replay, 0)

    assert m["realized_units_by_product"] == m["units_sold_by_product"]
    assert m["realized_revenue_by_product"] == m["revenue_by_product"]


def test_s10_transition_events_consumers_survive_the_widened_tuple():
    """🔴 Regression: `_transition_events` returns a 7-tuple since S10 P2, but three
    analysis/ callers unpacked exactly 5. They kept importing cleanly and failed only when
    called — so an import check could not see it, and `s6_step2b_phase05` swallowed the
    ValueError into its `skipped_transitions` counter, turning a hard break into a silently
    empty result. Pin the contract from the consumer side, where it actually broke."""
    env = make("kaggriculture", configuration={"seed": 0, "episodeSteps": 4})
    env.state[0].observation.private["shed"]["MELON"] = 20
    replay = _finish(env, _sell("MELON", 20))
    steps, cfg = replay["steps"], replay["configuration"]

    # The producer may grow further; consumers must not pin its arity.
    assert len(_transition_events(steps[0], steps[1], cfg)) >= 5

    from analysis.s6_step0_leg1 import _realised_both_seats
    from analysis.s6_step1_phase0 import _realised_premium

    # The assertion that matters is "does not raise ValueError: too many values to unpack".
    rev, units = _realised_both_seats(replay)
    assert rev is not None and units is not None

    assert len(_realised_premium(steps, cfg)) == 4
