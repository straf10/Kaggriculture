"""Layer 3 market-order executor."""
from .constants import ANIMALS, CROPS, LAND_ORDER, LAND_PRICES, market_price
from .debug import emit_receipt
from .planner import DayPlan
from .scheduler import ResourceLedger, animal_placed, animal_structure_ready
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
    # plan.md §5.1 v1d: animal products (EGG/MILK/WOOL) and byproduct FERTILIZER sell through
    # the same conservative marginal-price loop as the two crops — v1e is where a real
    # per-product marginal-threshold allocator belongs (plan.md §5), this just keeps v1d from
    # letting its own harvests pile up unsold in the shed.
    for product in ("STRAWBERRY", "CARROT", "EGG", "MILK", "WOOL", "FERTILIZER"):
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

    if config.get("animals", {}).get("enabled", False):
        # plan.md §5.1 v1d: only buy an animal once its structure slot is actually built and
        # empty — buying earlier would just have it sit in the shed as dead capital (the same
        # MASTERPLAN §3.2#7 lesson land-without-hands teaches, applied to animals-without-a-
        # home) — and never buy a second one of the same target (already placed, already
        # carried by a unit, or already waiting in the shed for pickup). New investment stops
        # once liquidation starts (no runway left to recoup an animal's cost), same as crops.
        if not plan.force_liquidation:
            for name in plan.animal_purchases:
                if animal_placed(snapshot, name):
                    continue
                if any(inv.get(name, 0) > 0 for inv in snapshot.inventories):
                    continue
                if int(snapshot.shed.get(name, 0)) > 0:
                    continue
                if animal_structure_ready(snapshot, config, name) is None:
                    continue
                cost = int(ANIMALS[name]["cost"])
                if available_money < cost:
                    continue
                orders.append(["BUY_ANIMAL", name, 1])
                available_money -= cost

        # Wheat is bought once a day, at the top of the day, for every animal already placed
        # (not yet-to-be-placed ones) — this is the "≥1 turn earlier" plan.md §5.1 asks for:
        # by hour 0 the shed already holds the day's wheat, leaving the whole day's slack for
        # PICKUP -> FEED instead of racing FEED's zero-slack `consecutive_unfed` deadline.
        # Unlike BUY_ANIMAL/new seeds, this must NOT be gated on force_liquidation: planner.py's
        # make_day_plan deliberately keeps already-placed animals fed through the endgame
        # ("they keep producing until the episode ends") — gating this on liquidation starved
        # both animals to death within 2 days of liquidation_day in a v1d smoke test.
        if snapshot.hour == 0:
            placed_animals = sum(
                1 for row in snapshot.my_tiles for tile in row
                if isinstance(tile, dict) and "animal" in tile
            )
            if placed_animals > 0:
                wheat_have = int(snapshot.shed.get("WHEAT", 0)) + sum(
                    inv.get("WHEAT", 0) for inv in snapshot.inventories
                )
                wheat_needed = max(0, placed_animals - wheat_have)
                if wheat_needed > 0:
                    wheat_price = max(1, int(snapshot.market_prices.get("WHEAT", 25)))
                    affordable = int(available_money // wheat_price)
                    wheat_to_buy = min(wheat_needed, affordable)
                    if wheat_to_buy:
                        orders.append(["BUY_PRODUCT", "WHEAT", wheat_to_buy])
                        available_money -= wheat_to_buy * wheat_price

    if (
        not plan.force_liquidation
        and config.get("land", {}).get("enabled", False)
        and "NE" not in snapshot.my_quadrants
        and len(snapshot.hand_positions) >= plan.hands_target
        and all(animal_placed(snapshot, name) for name in plan.animal_purchases)
    ):
        # plan.md §5 v1c / MASTERPLAN §3.2#7: only buy once hands_target hands are already
        # observed hired — land bought before a workforce exists to work it is dead capital.
        # The animal_placed check is load-bearing, not decorative: BUY_LAND's own hands_target
        # gate is satisfiable as early as day 0 hour ~2, well before COW/SHEEP are bought
        # (hour 4/6) and placed — a v1c+v1d smoke test showed land's cost grabbing the shed's
        # cash first left too little for the very next day's wheat purchase, starving both
        # animals to death by day 2. Requiring animals already placed defers land until after
        # that (much cheaper, ~$900 total) obligation is already paid for.
        # BUY_LAND is atomic (like HIRE), so the engine no-ops it for a seed >= LAND_ORDER's
        # length; scoped to NE only here (see config.py's "land" comment).
        cost = int(LAND_PRICES[LAND_ORDER.index("NE")])
        reserve = int(config["land"].get("min_reserve", 0))
        if available_money >= cost + reserve:
            orders.append(["BUY_LAND"])
            available_money -= cost

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
