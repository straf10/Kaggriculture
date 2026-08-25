"""Deterministic metrics extraction from an ``env.toJSON()`` replay."""
import copy
import statistics

from kaggle_environments.envs.kaggriculture import kaggriculture as engine

_MOVES = {"NORTH", "SOUTH", "EAST", "WEST"}


def _action(step, seat):
    action = step[seat].get("action")
    return action if isinstance(action, dict) else {"farmer": ["PASS"], "hands": [], "market": []}


def _apply_unit_actions(farms, privates, actions, configuration, day):
    board_size = int(configuration.get("boardSize", 10))
    turns_per_day = max(1, int(configuration.get("turnsPerDay", 24)))
    shed_capacity = int(configuration.get("shedCapacity", 100))
    overflow = [0, 0]
    successful_ongoing_harvests = [set(), set()]

    for seat in (0, 1):
        action = actions[seat]
        farmer_action = action.get("farmer", ["PASS"])
        hands_actions = action.get("hands", [])
        if not isinstance(hands_actions, list):
            hands_actions = []
        unit_actions = [farmer_action, *hands_actions]
        plant_demand = {}
        for unit_action in unit_actions:
            if isinstance(unit_action, list) and len(unit_action) >= 2 and unit_action[0] == "PLANT":
                crop = unit_action[1]
                plant_demand[crop] = plant_demand.get(crop, 0) + 1
        blocked = {
            crop
            for crop, demand in plant_demand.items()
            if demand > privates[seat]["seeds"].get(crop, 0)
        }

        for unit_index, unit_action in enumerate(unit_actions):
            if (
                isinstance(unit_action, list)
                and len(unit_action) >= 2
                and unit_action[0] == "PLANT"
                and unit_action[1] in blocked
            ):
                unit_action = ["PASS"]

            if isinstance(unit_action, list) and unit_action and unit_action[0] == "DROP":
                pos = engine._farmer_position(farms[seat], unit_index)
                if pos is not None and engine._is_shed_adjacent(pos, board_size):
                    inventory = engine._farmer_inventory(privates[seat], unit_index)
                    incoming = sum(inventory.values())
                    room = max(0, shed_capacity - sum(privates[seat]["shed"].values()))
                    overflow[seat] += max(0, incoming - room)

            harvest = None
            if (
                isinstance(unit_action, list)
                and unit_action
                and unit_action[0] == "HARVEST"
            ):
                pos = engine._farmer_position(farms[seat], unit_index)
                if pos is not None:
                    x, y = pos
                    tile = farms[seat]["tiles"][y][x]
                    if (
                        isinstance(tile, dict)
                        and tile.get("kind") == "PLANT"
                        and tile.get("yield_units", 0) > 0
                        and tile.get("max_lifespan_step", -1) >= 0
                    ):
                        harvest = (pos, (tile.get("crop"), tile.get("planted_day")))

            engine._apply_unit_action(
                farms[seat],
                privates[seat],
                unit_index,
                unit_action,
                board_size,
                day,
                turns_per_day,
                shed_capacity,
            )
            if harvest is not None:
                (x, y), crop_instance = harvest
                tile = farms[seat]["tiles"][y][x]
                if (
                    isinstance(tile, dict)
                    and tile.get("kind") == "PLANT"
                    and tile.get("yield_units", 0) == 0
                ):
                    successful_ongoing_harvests[seat].add(((x, y), crop_instance))
    return overflow, successful_ongoing_harvests


def _simulate_market(farms, privates, market, actions, configuration):
    max_orders = max(1, int(configuration.get("maxMarketOrdersPerTurn", 10)))
    board_size = int(configuration.get("boardSize", 10))
    hire_mult = int(configuration.get("farmHandCostMult", 1))
    shed_capacity = int(configuration.get("shedCapacity", 100))
    queues = [
        list(action.get("market", []))[:max_orders]
        if isinstance(action.get("market", []), list)
        else []
        for action in actions
    ]
    sales = [[], []]
    aborted = False

    for order_index in range(max((len(queue) for queue in queues), default=0)):
        order_states = [
            engine._parse_order(queue[order_index]) if order_index < len(queue) else None
            for queue in queues
        ]
        for seat, order_state in enumerate(order_states):
            if order_state is None:
                continue
            if order_state["type"] == "HIRE":
                engine._do_hire(farms[seat], privates[seat], board_size, hire_mult)
                order_states[seat] = None
            elif order_state["type"] == "BUY_LAND":
                engine._do_buy_land(farms[seat], board_size)
                order_states[seat] = None

        idx_esc = 0
        while True:
            idx_esc += 1
            if idx_esc >= 100_000:
                # review_89d99f0_2026-08-05.md L2: mirror the engine's own runaway-loop guard (kaggriculture.py
                # market loop) — a pathological replay must not hang metrics extraction.
                # review.md M11: unlike the engine (which prints a WARNING), this used to break
                # silently — sales/average_sell_price/units_sold_at_or_below_5 would then be
                # silently incomplete for this transition with no signal anywhere. Surface it.
                aborted = True
                break
            quoted = [None, None]
            for seat, order_state in enumerate(order_states):
                if order_state is None or order_state["remaining"] <= 0:
                    continue
                op, item = order_state["type"], order_state["item"]
                if op == "SELL" and item in engine.PRODUCTS:
                    price = engine.market_price(item, market["inventory"][item], market.get("params"))
                elif op == "BUY_PRODUCT" and item in ("WHEAT", "FERTILIZER"):
                    price = engine.market_price(item, market["inventory"][item] - 1, market.get("params"))
                elif op == "BUY_SEED" and item in engine.CROPS:
                    price = engine.CROPS[item]["seed"]
                elif op == "BUY_ANIMAL" and item in engine.ANIMALS:
                    price = engine.ANIMALS[item]["cost"]
                else:
                    order_states[seat] = None
                    continue
                quoted[seat] = (op, item, price, order_state)

            if all(quote is None for quote in quoted):
                break

            committed_any = False
            for seat, quote in enumerate(quoted):
                if quote is None:
                    continue
                op, item, price, order_state = quote
                committed = engine._commit_unit(
                    op,
                    item,
                    price,
                    farms[seat],
                    privates[seat],
                    market,
                    shed_capacity,
                )
                if committed:
                    order_state["remaining"] -= 1
                    committed_any = True
                    if op == "SELL":
                        sales[seat].append({"item": item, "price": price, "order_index": order_index})
                else:
                    order_states[seat] = None
            if not committed_any:
                break
        engine._refresh_prices(market)
    return sales, aborted


# S10 P2.1: order-side sell counters.  `_simulate_market` returns COMMITTED sales only; a
# `_commit_unit` rejection (empty shed) breaks the inner walk early, so its counters cannot
# see units the engine never reached.  The two counters below read the raw action queue:
#
#   `_sell_units_ordered_by_product`  — raw SELL quantities in the action, one dict per seat.
#       This is the denominator for fill (committed / ordered).
#   `_sell_units_ordered_at_floor`    — the same per-unit lockstep walk that
#       analysis/s9_market_ledger.py performs, but only counting units that would price at
#       PRICE_FLOOR ($1).  A $1 sale does not add to inventory (`_commit_unit`), so the
#       price walk stays at $1 for the rest of that batch; the count is an UPPER BOUND on
#       destroyed units in the episode (the acceptance target: ~182,7/ep on 55726984).
def _sell_units_ordered_by_product(actions, max_orders):
    out = [{}, {}]
    for seat in (0, 1):
        # The engine truncates the raw queue to maxMarketOrdersPerTurn BEFORE parsing
        # (kaggriculture._process_market), and so does _simulate_market. Orders past the
        # cap are never quoted, so they are not "ordered units" — counting them would
        # silently depress fill (committed/ordered).
        for order in (actions[seat].get("market") or [])[:max_orders]:
            if isinstance(order, list) and len(order) >= 3 and order[0] == "SELL":
                item = order[1]
                # Match engine._process_market: a SELL of a non-PRODUCT item (e.g. an animal)
                # is silently dropped, not quoted — do not count it as an ordered unit.
                if item not in engine.PRODUCTS:
                    continue
                try:
                    q = int(order[2])
                except (TypeError, ValueError):
                    continue
                if q > 0:
                    out[seat][item] = out[seat].get(item, 0) + q
    return out


def _sell_units_ordered_at_floor(actions, market, max_orders):
    """Per-seat per-product count of SELL units that would price at PRICE_FLOOR if every
    unit committed.  Interleaves the two seats' units in engine order (matching
    engine._process_market's per-unit round-robin), so the walk-down of a shared item is
    simulated correctly."""
    inv = dict(market["inventory"])
    params = market.get("params")
    # Truncate to the engine's order cap first, then filter — same order of operations
    # as _process_market / _simulate_market.
    queues = [
        [(o[1], int(o[2])) for o in (actions[s].get("market") or [])[:max_orders]
         if isinstance(o, list) and len(o) >= 3 and o[0] == "SELL"
         and o[1] in engine.PRODUCTS and int(o[2]) > 0]
        for s in (0, 1)
    ]
    remaining = [list(q) for q in queues]
    at_floor = [{}, {}]
    # Mirror _process_market: for each order slot i, quote one unit for BOTH seats at the
    # SAME inventory, then commit both (updating inv only for non-floor units).  Seats do
    # not see each other's within-round advance — that is what makes bulk-dump pricing
    # correct.  Advance to the next unit for both seats and repeat until both are exhausted.
    max_slots = max(len(remaining[0]), len(remaining[1]))
    for i in range(max_slots):
        while True:
            quoted = [None, None]
            for seat in (0, 1):
                if i >= len(remaining[seat]):
                    continue
                item, left = remaining[seat][i]
                if left <= 0:
                    continue
                quoted[seat] = (item, engine.market_price(item, inv[item], params))
            if quoted[0] is None and quoted[1] is None:
                break
            # Commit both units at once — the engine's per-unit lockstep only advances the
            # shared inventory after both seats have quoted and committed at the SAME inv.
            for seat, q in enumerate(quoted):
                if q is None:
                    continue
                item, price = q
                if price == engine.PRICE_FLOOR:
                    at_floor[seat][item] = at_floor[seat].get(item, 0) + 1
                else:
                    inv[item] += 1
                left = remaining[seat][i][1] - 1
                remaining[seat][i] = (item, left)
    return at_floor


def _transition_events(previous_step, current_step, configuration):
    farms = copy.deepcopy(previous_step[0]["observation"]["farms"])
    market = copy.deepcopy(previous_step[0]["observation"]["market"])
    privates = [
        copy.deepcopy(previous_step[seat]["observation"]["private"])
        for seat in (0, 1)
    ]
    actions = [_action(current_step, seat) for seat in (0, 1)]
    previous_day = int(previous_step[0]["observation"].get("day", 0))

    overflow, successful_ongoing_harvests = _apply_unit_actions(
        farms, privates, actions, configuration, previous_day
    )
    # S10 P2.1: order-side counters BEFORE simulating commits — a `_commit_unit` rejection
    # breaks _simulate_market's inner walk early and hides the tail.
    max_orders = max(1, int(configuration.get("maxMarketOrdersPerTurn", 10)))
    ordered_by_product = _sell_units_ordered_by_product(actions, max_orders)
    ordered_at_floor = _sell_units_ordered_at_floor(actions, market, max_orders)
    sales, market_sim_aborted = _simulate_market(farms, privates, market, actions, configuration)

    current_day = int(current_step[0]["observation"].get("day", previous_day))
    if current_day != previous_day:
        shed_capacity = int(configuration.get("shedCapacity", 100))
        for seat in (0, 1):
            incoming = sum(sum(inventory.values()) for inventory in privates[seat]["inventories"])
            room = max(0, shed_capacity - sum(privates[seat]["shed"].values()))
            overflow[seat] += max(0, incoming - room)
    return (actions, overflow, sales, market_sim_aborted, successful_ongoing_harvests,
            ordered_by_product, ordered_at_floor)


def extract_metrics(env_json: dict, seat: int, diagnostics: list | None = None) -> dict:
    """`env_json` is env.toJSON() (or an equivalent replay dict loaded from disk).

    `diagnostics` is `PlayResult.diagnostics` (KAGGRI_RECEIPT records, only non-empty when
    `CONFIG["guards"]["debug"]` was on for the agent process — see agent/debug.py and
    agent/receipts.py). When given, `unexplained_noops` counts `reconciliation` receipts for
    this seat where `ok is False`: reconcile() checks the actual committed WATER/PLANT/HARVEST
    against the farm tile at the position the action targeted, and that tile is never touched
    by the day-boundary farmer/hands reset (`_apply_unit_action` lands before `_end_of_day` in
    the engine's own turn order) — so every `ok=False` here is a genuine expected-vs-actual
    mismatch (review_89d99f0_2026-08-05.md H4), not a boundary artifact to swallow. Without diagnostics this is
    `None`, not `0` — the absence of receipts is not proof of zero unexplained no-ops."""
    opponent = 1 - seat
    steps = env_json["steps"]
    bank_curve = [step[0]["observation"]["farms"][seat]["money"] for step in steps]
    opp_bank_curve = [step[0]["observation"]["farms"][opponent]["money"] for step in steps]

    final_bank = env_json["rewards"][seat]
    opponent_final_bank = env_json["rewards"][opponent]
    if final_bank > opponent_final_bank:
        outcome = "win"
    elif final_bank < opponent_final_bank:
        outcome = "loss"
    else:
        outcome = "tie"

    weeds_lost = 0
    unexpected_weeds_lost = 0
    # v1h.2: an ongoing crop that was harvested to zero yield is retired by
    # the engine as a PLANT->WEED transition, and that is a success, not a loss. The engine
    # does not retire it in the same turn as the harvest: it retires it at the next
    # max_lifespan_step decay tick, which is measured 17-24 steps later (seed 1: harvests at
    # steps 389/392/416/419/438, retirements at 408/432/456). The confirmed-harvest set is
    # therefore accumulated over the whole episode, not read from the transition that happens
    # to contain the WEED. Keyed by (position, crop, planted_day), so a *replanted* crop on the
    # same tile is a different key and can never inherit the previous plant's exemption.
    harvested_to_zero: set = set()
    water_weeds_lost = 0
    decay_weeds_lost = 0
    animals_escaped = 0
    animals_underfed_days = 0
    clipped_production_ticks = 0
    plant_decay_units_lost = 0
    shed_overflow_burnt = 0
    sales = []
    worker_turns_moving = 0
    worker_turns_working = 0
    worker_turns_idle = 0
    # S10 P2.1: differential fill/floor-sink counters.
    sell_units_ordered = 0
    sell_units_ordered_by_product: dict = {}
    floor_units_ordered = 0
    floor_units_ordered_by_product: dict = {}
    sell_units_ordered_by_day: dict = {}
    shed_peak = 0
    configuration = env_json.get("configuration", {})
    # harness/report.py needs a per-day breakdown to plot losses/utilization
    # over the episode instead of one flat total; keyed by day index, densified below so a day
    # with zero transitions still appears as a zero row instead of a gap.
    daily_by_day: dict = {}
    # harness/report.py's acceptance criterion is pinpointing *which* tile/step caused a loss,
    # not just a daily count — one record per water_weeds_lost/plant_decay occurrence.
    loss_events = []
    # review.md M11: True if any transition's market simulation hit the 100k-iteration
    # runaway-loop guard — when that happens, sales/average_sell_price/units_sold_at_or_below_5
    # are incomplete for that transition, so this episode's metrics can't be trusted as gate
    # input even though every individual counter still returned a (silently partial) number.
    market_sim_aborted = False
    for index in range(1, len(steps)):
        previous_step, current_step = steps[index - 1], steps[index]
        previous_observation = previous_step[seat]["observation"]
        current_observation = current_step[seat]["observation"]
        previous_tiles = previous_observation["farms"][seat]["tiles"]
        current_tiles = current_observation["farms"][seat]["tiles"]
        previous_engine_step = int(previous_observation.get("step", index - 1))
        day_row = daily_by_day.setdefault(int(previous_observation.get("day", 0)), {
            "water_weeds_lost": 0, "plant_decay_units_lost": 0,
            "worker_turns_moving": 0, "worker_turns_working": 0, "worker_turns_idle": 0,
            "clipped_production_ticks": 0, "animals_underfed_days": 0,
        })

        (
            actions,
            overflow,
            transition_sales,
            transition_aborted,
            successful_ongoing_harvests,
            transition_ordered,
            transition_ordered_at_floor,
        ) = _transition_events(
            previous_step,
            current_step,
            configuration,
        )
        shed_overflow_burnt += overflow[seat]
        harvested_to_zero.update(successful_ongoing_harvests[seat])
        sale_day = int(previous_observation.get("day", 0))
        for sale in transition_sales[seat]:
            sale["day"] = sale_day
        sales.extend(transition_sales[seat])
        market_sim_aborted = market_sim_aborted or transition_aborted
        # S10 P2.1: accumulate order-side counters for this seat only.
        for item, q in transition_ordered[seat].items():
            sell_units_ordered += q
            sell_units_ordered_by_product[item] = sell_units_ordered_by_product.get(item, 0) + q
            # P5.1: same units keyed by day, so a dropped SELL can be attributed to a day.
            sell_units_ordered_by_day[sale_day] = sell_units_ordered_by_day.get(sale_day, 0) + q
        for item, q in transition_ordered_at_floor[seat].items():
            floor_units_ordered += q
            floor_units_ordered_by_product[item] = floor_units_ordered_by_product.get(item, 0) + q
        # shed_peak: max over EVERY observation this seat sees. Sampling only
        # `previous_observation` would never look at steps[-1], so a peak reached on the
        # final step (or an end-of-episode liquidation stall) went unrecorded.
        for obs in (previous_observation, current_observation):
            shed_sum = sum((obs.get("private") or {}).get("shed", {}).values())
            if shed_sum > shed_peak:
                shed_peak = shed_sum

        farm = previous_observation["farms"][seat]
        unit_actions = [actions[seat].get("farmer", ["PASS"]), *actions[seat].get("hands", [])]
        unit_actions = unit_actions[:1 + len(farm.get("hands", []))]
        unit_positions = [tuple(farm.get("farmer", (0, 0))), *(tuple(pos) for pos in farm.get("hands", []))]
        # review_89d99f0_2026-08-05.md M8: a HARVEST this seat's own unit just performed can legitimately zero
        # out yield_units (ongoing crop) or clear "animal" off the tile's product state on the
        # very step the decay-window/escape heuristics below would otherwise misfire on —
        # exclude positions this seat harvested from this turn.
        harvested_positions = {
            unit_positions[unit_index]
            for unit_index, unit_action in enumerate(unit_actions)
            if unit_index < len(unit_positions)
            and isinstance(unit_action, list)
            and unit_action
            and unit_action[0] == "HARVEST"
        }

        for y, row in enumerate(previous_tiles):
            for x, previous_tile in enumerate(row):
                current_tile = current_tiles[y][x]
                harvested_here = (x, y) in harvested_positions
                if isinstance(previous_tile, dict) and previous_tile.get("kind") == "PLANT":
                    if isinstance(current_tile, dict) and current_tile.get("kind") == "WEED":
                        weeds_lost += 1
                        lifespan = previous_tile.get("max_lifespan_step", -1)
                        crop_instance = (
                            previous_tile.get("crop"),
                            previous_tile.get("planted_day"),
                        )
                        successful_harvest_retirement = (
                            lifespan >= 0
                            and previous_engine_step >= lifespan
                            and (previous_engine_step - lifespan) % 2 == 0
                            and ((x, y), crop_instance) in harvested_to_zero
                        )
                        if not successful_harvest_retirement:
                            unexpected_weeds_lost += 1
                        if (
                            current_observation.get("day") != previous_observation.get("day")
                            and not previous_tile.get("watered_today")
                            and previous_tile.get("consecutive_unwatered", 0) >= 1
                        ):
                            water_weeds_lost += 1
                            day_row["water_weeds_lost"] += 1
                            loss_events.append({
                                "type": "water_weeds_lost", "step": previous_engine_step,
                                "day": int(previous_observation.get("day", 0)), "pos": [x, y],
                            })
                    lifespan = previous_tile.get("max_lifespan_step", -1)
                    if (
                        lifespan >= 0
                        and previous_engine_step >= lifespan
                        and (previous_engine_step - lifespan) % 2 == 0
                        and not harvested_here
                    ):
                        previous_yield = previous_tile.get("yield_units", 0)
                        current_yield = (
                            current_tile.get("yield_units", 0)
                            if isinstance(current_tile, dict) and current_tile.get("kind") == "PLANT"
                            else 0
                        )
                        if current_yield < previous_yield:
                            plant_decay_units_lost += previous_yield - current_yield
                            day_row["plant_decay_units_lost"] += previous_yield - current_yield
                            loss_events.append({
                                "type": "plant_decay_units_lost", "step": previous_engine_step,
                                "day": int(previous_observation.get("day", 0)), "pos": [x, y],
                                "units": previous_yield - current_yield,
                            })
                            if isinstance(current_tile, dict) and current_tile.get("kind") == "WEED":
                                decay_weeds_lost += 1
                if isinstance(previous_tile, dict) and "animal" in previous_tile:
                    if (
                        isinstance(current_tile, dict)
                        and "animal" not in current_tile
                        and current_tile.get("kind") == previous_tile.get("kind")
                        and not harvested_here
                    ):
                        animals_escaped += 1
                    elif (
                        current_observation.get("day") != previous_observation.get("day")
                        and not harvested_here
                    ):
                        # G8: engine.py:805 clips `yield_units + base + bonus` to
                        # `max_held` on every scheduled production tick — if the tile was
                        # already sitting at max_held going into a due tick, that tick's whole
                        # production was silently discarded for lack of a HARVEST. We can't see
                        # the engine's internal `base`/`bonus`, but "already at cap on a due
                        # tick" is a sufficient (if slightly conservative) proxy since base >= 1
                        # always.
                        animal_data = engine.ANIMALS.get(previous_tile.get("animal"))
                        if animal_data is not None:
                            next_day = int(current_observation.get("day", 0))
                            days_since_first = (
                                next_day
                                - previous_tile.get("placed_day", next_day)
                                - animal_data["first_yield_day"]
                            )
                            interval = animal_data["interval"]
                            if (
                                days_since_first >= 0
                                and interval > 0
                                and days_since_first % interval == 0
                                and previous_tile.get("yield_units", 0) >= animal_data["max_held"]
                            ):
                                clipped_production_ticks += 1
                                day_row["clipped_production_ticks"] += 1
                                loss_events.append({
                                    "type": "clipped_production_ticks", "step": previous_engine_step,
                                    "day": int(previous_observation.get("day", 0)), "pos": [x, y],
                                })
                    # review.md M4: leading indicator for an escape — engine's own
                    # `_daily_refresh_animals` (kaggriculture.py:791-795) bumps
                    # consecutive_unfed on any day-boundary where fed_today is still False;
                    # two in a row is the escape itself (animals_escaped above), one alone is
                    # the warning sign the wheat-shortfall receipt should have already caught.
                    if (
                        current_observation.get("day") != previous_observation.get("day")
                        and not harvested_here
                        and not previous_tile.get("fed_today", False)
                    ):
                        animals_underfed_days += 1
                        day_row["animals_underfed_days"] += 1

        for unit_action in unit_actions:
            op = unit_action[0] if isinstance(unit_action, list) and unit_action else "PASS"
            if op in _MOVES:
                worker_turns_moving += 1
                day_row["worker_turns_moving"] += 1
            elif op == "PASS":
                worker_turns_idle += 1
                day_row["worker_turns_idle"] += 1
            else:
                worker_turns_working += 1
                day_row["worker_turns_working"] += 1

    prices_by_item = {}
    for sale in sales:
        prices_by_item.setdefault(sale["item"], []).append(sale["price"])
    average_sell_price = {
        item: statistics.mean(prices)
        for item, prices in prices_by_item.items()
    }
    # v1k: occupancy is an acceptance dimension, not just a replay-profile
    # visualization. Match analysis.replay_profile's end-of-day definition exactly so the
    # local gate is directly comparable with the ladder baseline (415 crop tile-days/ep).
    turns_per_day = int(configuration.get("turnsPerDay", 24))
    crop_tile_days = 0
    for day in range(len(steps) // turns_per_day):
        step_index = min(day * turns_per_day + turns_per_day - 1, len(steps) - 1)
        tiles = steps[step_index][0]["observation"]["farms"][seat]["tiles"]
        crop_tile_days += sum(
            1
            for row in tiles
            for tile in row
            if isinstance(tile, dict) and tile.get("kind") == "PLANT"
        )
    # v1l: gross market revenue from plant products only (not animals /
    # fertilizer). Acceptance requires this to move positively when the crop mix changes.
    _CROP_REVENUE_ITEMS = ("WHEAT", "CARROT", "STRAWBERRY", "TOMATO", "MELON")
    crop_revenue = sum(
        int(sale["price"])
        for sale in sales
        if sale.get("item") in _CROP_REVENUE_ITEMS
    )
    # §Β.0: per-product avg realized price alone doesn't say whether the
    # elite-ceiling herd size actually saturates a product's cliff — need units sold alongside it.
    units_sold_by_product = {
        item: len(prices)
        for item, prices in prices_by_item.items()
    }
    # v1m: realized $/u per product (crop_revenue is only the sum). Same
    # sale stream as average_sell_price; revenue_by_product makes the gate's MELON $/u
    # = revenue/units checkable without re-scanning market_sales.
    revenue_by_product = {
        item: int(sum(prices))
        for item, prices in prices_by_item.items()
    }
    realized_price_per_unit = {
        item: (revenue_by_product[item] / units_sold_by_product[item])
        for item in revenue_by_product
    }
    # S10 P2.1: committed floor units — a SELL at PRICE_FLOOR pays $1 and does NOT add to
    # market inventory (`_commit_unit` in the engine), so the unit is destroyed, not traded.
    # This is the pair to `floor_units_ordered` above (walk-based upper bound).
    floor_units = 0
    floor_units_by_product: dict = {}
    for sale in sales:
        if int(sale["price"]) <= engine.PRICE_FLOOR:
            floor_units += 1
            floor_units_by_product[sale["item"]] = floor_units_by_product.get(sale["item"], 0) + 1
    sell_units_committed = len(sales)
    # P5.1: the committed side of the same per-day split. dropped(day) = ordered − committed.
    sell_units_committed_by_day: dict = {}
    for sale in sales:
        d = int(sale.get("day", 0))
        sell_units_committed_by_day[d] = sell_units_committed_by_day.get(d, 0) + 1
    # S10 P2.1: tail_share_by_product — share of a product's revenue that arrived on day >= 20.
    # A change that shifts revenue into the tail without changing the total still shows here.
    tail_revenue = {}
    for sale in sales:
        if int(sale.get("day", 0)) >= 20:
            item = sale["item"]
            tail_revenue[item] = tail_revenue.get(item, 0) + int(sale["price"])
    tail_share_by_product = {
        item: (tail_revenue.get(item, 0) / revenue_by_product[item])
        for item in revenue_by_product
        if revenue_by_product[item] > 0
    }

    if diagnostics is None:
        unexplained_noops = None
    else:
        unexplained_noops = sum(
            1 for d in diagnostics
            if d.get("seat") == seat and d.get("kind") == "reconciliation" and d.get("ok") is False
        )

    empty_day_row = {
        "water_weeds_lost": 0, "plant_decay_units_lost": 0,
        "worker_turns_moving": 0, "worker_turns_working": 0, "worker_turns_idle": 0,
        "clipped_production_ticks": 0, "animals_underfed_days": 0,
    }
    daily = [
        {"day": day, **daily_by_day.get(day, empty_day_row)}
        for day in range(max(daily_by_day, default=-1) + 1)
    ]

    return {
        "final_bank": final_bank,
        "opponent_final_bank": opponent_final_bank,
        "outcome": outcome,
        "status": env_json["statuses"][seat],
        "bank_curve": bank_curve,
        "opponent_bank_curve": opp_bank_curve,
        "weeds_lost": weeds_lost,
        "unexpected_weeds_lost": unexpected_weeds_lost,
        "water_weeds_lost": water_weeds_lost,
        "decay_weeds_lost": decay_weeds_lost,
        "animals_escaped": animals_escaped,
        "animals_underfed_days": animals_underfed_days,
        "clipped_production_ticks": clipped_production_ticks,
        "plant_decay_units_lost": plant_decay_units_lost,
        "shed_overflow_burnt": shed_overflow_burnt,
        "units_sold_at_or_below_5": sum(1 for sale in sales if sale["price"] <= 5),
        "average_sell_price": average_sell_price,
        "units_sold_by_product": units_sold_by_product,
        "revenue_by_product": revenue_by_product,
        "realized_units_by_product": units_sold_by_product,
        "realized_revenue_by_product": revenue_by_product,
        "realized_price_per_unit": realized_price_per_unit,
        "floor_units": floor_units,
        "floor_units_by_product": floor_units_by_product,
        "floor_units_ordered": floor_units_ordered,
        "floor_units_ordered_by_product": floor_units_ordered_by_product,
        "sell_units_ordered": sell_units_ordered,
        "sell_units_ordered_by_product": sell_units_ordered_by_product,
        "sell_units_committed": sell_units_committed,
        "sell_units_ordered_by_day": sell_units_ordered_by_day,
        "sell_units_committed_by_day": sell_units_committed_by_day,
        "shed_peak": shed_peak,
        "tail_share_by_product": tail_share_by_product,
        "market_sales": sales,
        "worker_turns_moving": worker_turns_moving,
        "worker_turns_working": worker_turns_working,
        "worker_turns_idle": worker_turns_idle,
        "worker_turns_total": (
            worker_turns_moving + worker_turns_working + worker_turns_idle
        ),
        "crop_tile_days": crop_tile_days,
        "crop_revenue": crop_revenue,
        "unexplained_noops": unexplained_noops,
        "daily": daily,
        "loss_events": loss_events,
        "market_sim_aborted": market_sim_aborted,
    }
