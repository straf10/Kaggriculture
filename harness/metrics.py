"""Deterministic metrics extraction from an ``env.toJSON()`` replay."""
import copy
import statistics

from kaggle_environments.envs.kaggriculture import kaggriculture as engine

_MOVES = {"NORTH", "SOUTH", "EAST", "WEST"}


def _action(step, seat):
    action = step[seat].get("action")
    return action if isinstance(action, dict) else {"farmer": ["PASS"], "hands": [], "market": []}


def _apply_unit_actions(farms, privates, actions, configuration):
    board_size = int(configuration.get("boardSize", 10))
    turns_per_day = max(1, int(configuration.get("turnsPerDay", 24)))
    shed_capacity = int(configuration.get("shedCapacity", 100))
    day = int(actions[0].get("_day", 0))
    overflow = [0, 0]

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
    return overflow


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

        while True:
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
    return sales


def _transition_events(previous_step, current_step, configuration):
    farms = copy.deepcopy(previous_step[0]["observation"]["farms"])
    market = copy.deepcopy(previous_step[0]["observation"]["market"])
    privates = [
        copy.deepcopy(previous_step[seat]["observation"]["private"])
        for seat in (0, 1)
    ]
    actions = [_action(current_step, seat) for seat in (0, 1)]
    previous_day = int(previous_step[0]["observation"].get("day", 0))
    for action in actions:
        action["_day"] = previous_day

    overflow = _apply_unit_actions(farms, privates, actions, configuration)
    sales = _simulate_market(farms, privates, market, actions, configuration)

    current_day = int(current_step[0]["observation"].get("day", previous_day))
    if current_day != previous_day:
        shed_capacity = int(configuration.get("shedCapacity", 100))
        for seat in (0, 1):
            incoming = sum(sum(inventory.values()) for inventory in privates[seat]["inventories"])
            room = max(0, shed_capacity - sum(privates[seat]["shed"].values()))
            overflow[seat] += max(0, incoming - room)
    return actions, overflow, sales


def extract_metrics(env_json: dict, seat: int) -> dict:
    """`env_json` is env.toJSON() (or an equivalent replay dict loaded from disk)."""
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
    water_weeds_lost = 0
    decay_weeds_lost = 0
    animals_escaped = 0
    plant_decay_units_lost = 0
    shed_overflow_burnt = 0
    sales = []
    worker_turns_moving = 0
    worker_turns_working = 0
    worker_turns_idle = 0
    configuration = env_json.get("configuration", {})

    for index in range(1, len(steps)):
        previous_step, current_step = steps[index - 1], steps[index]
        previous_observation = previous_step[seat]["observation"]
        current_observation = current_step[seat]["observation"]
        previous_tiles = previous_observation["farms"][seat]["tiles"]
        current_tiles = current_observation["farms"][seat]["tiles"]
        previous_engine_step = int(previous_observation.get("step", index - 1))

        for y, row in enumerate(previous_tiles):
            for x, previous_tile in enumerate(row):
                current_tile = current_tiles[y][x]
                if isinstance(previous_tile, dict) and previous_tile.get("kind") == "PLANT":
                    if isinstance(current_tile, dict) and current_tile.get("kind") == "WEED":
                        weeds_lost += 1
                        if (
                            current_observation.get("day") != previous_observation.get("day")
                            and not previous_tile.get("watered_today")
                            and previous_tile.get("consecutive_unwatered", 0) >= 1
                        ):
                            water_weeds_lost += 1
                    lifespan = previous_tile.get("max_lifespan_step", -1)
                    if (
                        lifespan >= 0
                        and previous_engine_step >= lifespan
                        and (previous_engine_step - lifespan) % 2 == 0
                    ):
                        previous_yield = previous_tile.get("yield_units", 0)
                        current_yield = (
                            current_tile.get("yield_units", 0)
                            if isinstance(current_tile, dict) and current_tile.get("kind") == "PLANT"
                            else 0
                        )
                        if current_yield < previous_yield:
                            plant_decay_units_lost += previous_yield - current_yield
                            if isinstance(current_tile, dict) and current_tile.get("kind") == "WEED":
                                decay_weeds_lost += 1
                if isinstance(previous_tile, dict) and "animal" in previous_tile:
                    if (
                        isinstance(current_tile, dict)
                        and "animal" not in current_tile
                        and current_tile.get("kind") == previous_tile.get("kind")
                    ):
                        animals_escaped += 1

        actions, overflow, transition_sales = _transition_events(
            previous_step,
            current_step,
            configuration,
        )
        shed_overflow_burnt += overflow[seat]
        sales.extend(transition_sales[seat])

        farm = previous_observation["farms"][seat]
        unit_actions = [actions[seat].get("farmer", ["PASS"]), *actions[seat].get("hands", [])]
        unit_actions = unit_actions[:1 + len(farm.get("hands", []))]
        for unit_action in unit_actions:
            op = unit_action[0] if isinstance(unit_action, list) and unit_action else "PASS"
            if op in _MOVES:
                worker_turns_moving += 1
            elif op == "PASS":
                worker_turns_idle += 1
            else:
                worker_turns_working += 1

    prices_by_item = {}
    for sale in sales:
        prices_by_item.setdefault(sale["item"], []).append(sale["price"])
    average_sell_price = {
        item: statistics.mean(prices)
        for item, prices in prices_by_item.items()
    }

    return {
        "final_bank": final_bank,
        "opponent_final_bank": opponent_final_bank,
        "outcome": outcome,
        "status": env_json["statuses"][seat],
        "bank_curve": bank_curve,
        "opponent_bank_curve": opp_bank_curve,
        "weeds_lost": weeds_lost,
        "water_weeds_lost": water_weeds_lost,
        "decay_weeds_lost": decay_weeds_lost,
        "animals_escaped": animals_escaped,
        "plant_decay_units_lost": plant_decay_units_lost,
        "shed_overflow_burnt": shed_overflow_burnt,
        "units_sold_at_or_below_5": sum(1 for sale in sales if sale["price"] <= 5),
        "average_sell_price": average_sell_price,
        "market_sales": sales,
        "worker_turns_moving": worker_turns_moving,
        "worker_turns_working": worker_turns_working,
        "worker_turns_idle": worker_turns_idle,
    }
