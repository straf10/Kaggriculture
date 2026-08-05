"""Layer 3 market-order executor."""
from .constants import CROPS, market_price
from .planner import DayPlan
from .scheduler import ResourceLedger
from .state import Snapshot


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
    carrot_in_shed = int(snapshot.shed.get("CARROT", 0))
    if carrot_in_shed > 0:
        if plan.force_liquidation:
            sell_units = carrot_in_shed
        else:
            floor = int(plan.sell_floor_price.get("CARROT", 5))
            safety_units = int(executor_config["opponent_price_safety_units"])
            inventory = int(snapshot.market_inventory.get("CARROT", 0))
            sell_units = 0
            while (
                sell_units < carrot_in_shed
                and market_price("CARROT", inventory + sell_units + safety_units) > floor
            ):
                sell_units += 1
        if sell_units:
            orders.append(["SELL", "CARROT", sell_units])

    if not plan.force_liquidation:
        seed_buffer = int(executor_config["seed_buffer"])
        seed_count = int(ledger.seeds.get("CARROT", 0))
        seeds_to_buy = max(0, seed_buffer - seed_count)
        affordable = int(ledger.money // CROPS["CARROT"]["seed"])
        seeds_to_buy = min(seeds_to_buy, affordable)
        if seeds_to_buy:
            orders.append(["BUY_SEED", "CARROT", seeds_to_buy])

    max_orders = int(executor_config["max_market_orders"])
    if len(orders) > max_orders:
        raise AssertionError(f"market order budget exceeded: {len(orders)} > {max_orders}")
    return orders
