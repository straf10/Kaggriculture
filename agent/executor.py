"""Layer 3 market-order executor."""
from .constants import CROPS, market_price
from .debug import emit_receipt
from .planner import DayPlan
from .scheduler import ResourceLedger
from .state import Snapshot


def _hire_cost(n_already_today: int) -> int:
    first, second = 1, 1
    for _ in range(n_already_today):
        first, second = second, first + second
    return first


def _remaining_unplanted_targets(snapshot: Snapshot, plan: DayPlan, config: dict, crop: str) -> int:
    """review.md M5: how many of today's target tiles for `crop` are not yet planted. Buying
    seeds up to a fixed buffer regardless of this left leftover stock (up to seed_buffer per
    crop, no resale) once every target tile was already planted."""
    target_tiles = config["scheduler"]["target_tiles"].get(crop, ())
    limit = plan.plant_targets.get(crop, 0)
    remaining = 0
    for x, y in target_tiles[:limit]:
        tile = snapshot.my_tiles[y][x]
        if not (isinstance(tile, dict) and tile.get("kind") == "PLANT"):
            remaining += 1
    return remaining


def market_orders(
    snapshot: Snapshot,
    plan: DayPlan,
    ledger: ResourceLedger,
    scheduled_unit_actions: list[list[str]],
    config: dict,
) -> list[list]:
    """Allocate the v1a SELL/BUY_SEED orders within all hard budgets."""
    del scheduled_unit_actions
    executor_config = config["executor"]
    if not executor_config.get("enabled", False):
        return []

    orders = []
    available_money = ledger.money
    for product in ("STRAWBERRY", "CARROT"):
        product_in_shed = int(snapshot.shed.get(product, 0))
        if product_in_shed <= 0:
            continue
        if plan.force_liquidation:
            sell_units = product_in_shed
        else:
            floor = int(plan.sell_floor_price.get(product, 5))
            safety_units = int(executor_config["opponent_price_safety_units"])
            inventory = int(snapshot.market_inventory.get(product, 0))
            sell_units = 0
            while (
                sell_units < product_in_shed
                and market_price(product, inventory + sell_units + safety_units) > floor
            ):
                sell_units += 1
        if sell_units:
            orders.append(["SELL", product, sell_units])

    if not plan.force_liquidation:
        seed_buffer = int(executor_config["seed_buffer"])
        for crop in ("CARROT", "STRAWBERRY"):
            if plan.plant_targets.get(crop, 0) <= 0:
                continue
            seed_count = int(ledger.seeds.get(crop, 0))
            if config["ablation"]["seed_cap_by_remaining_targets"]:
                remaining_unplanted = _remaining_unplanted_targets(snapshot, plan, config, crop)
                seeds_to_buy = max(0, min(seed_buffer, remaining_unplanted) - seed_count)
            else:
                # v1b behavior: flat seed_buffer target regardless of how many target tiles
                # actually still need a seed.
                seeds_to_buy = max(0, seed_buffer - seed_count)
            affordable = int(available_money // CROPS[crop]["seed"])
            seeds_to_buy = min(seeds_to_buy, affordable)
            if seeds_to_buy:
                orders.append(["BUY_SEED", crop, seeds_to_buy])
                available_money -= seeds_to_buy * CROPS[crop]["seed"]

    if snapshot.hour == 0 and plan.hands_target > len(snapshot.hand_positions):
        hires_needed = plan.hands_target - len(snapshot.hand_positions)
        hires_already = snapshot.hires_today
        for offset in range(hires_needed):
            cost = _hire_cost(hires_already + offset)
            if available_money < cost:
                break
            orders.append(["HIRE"])
            available_money -= cost

    max_orders = int(executor_config["max_market_orders"])
    if len(orders) > max_orders:
        # review.md M7: raising here would turn one budget slip into a submission ERROR and a
        # lost episode. Truncate defensively instead and leave a receipt to catch it in dev.
        emit_receipt({
            "kind": "market_order_budget_truncated",
            "step": snapshot.step,
            "requested": len(orders),
            "max_orders": max_orders,
        })
        orders = orders[:max_orders]
    return orders
