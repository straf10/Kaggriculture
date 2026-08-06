"""Layer 3 market-order executor."""
from .constants import ANIMALS, CROPS, LAND_ORDER, LAND_PRICES, market_price
from .debug import emit_receipt
from .planner import DayPlan
from .scheduler import ResourceLedger, animal_placed, animal_structure_ready
from .state import Snapshot


# review.md H8: truncation used to keep construction order (SELL first, HIRE/BUY_LAND last),
# so a budget-tight turn silently dropped HIRE and BUY_LAND — the two orders with the largest
# measured ROI — in favor of a SELL FERTILIZER worth a few dollars. Lower number = kept first
# when max_market_orders forces a cut. WHEAT is life-or-death for placed animals
# (consecutive_unfed >= 2 escapes them); HIRE has the largest observed ROI of any order kind.
_ORDER_TIER = {"HIRE": 0, "BUY_PRODUCT": 1, "BUY_ANIMAL": 2, "BUY_SEED": 3, "BUY_LAND": 4, "SELL": 5}


def _order_tier(order: list) -> int:
    return _ORDER_TIER.get(order[0], len(_ORDER_TIER))


def _hire_cost(n_already_today: int, mult: int = 1) -> int:
    """review.md M3: mirrors the engine's `cost = mult * _fib(n)`
    (engine_reference/kaggriculture.py:675-676) — the mult was previously dropped, so a
    non-default farmHandCostMult would make the agent underestimate cost and emit HIRE
    orders the engine silently no-ops."""
    first, second = 1, 1
    for _ in range(n_already_today):
        first, second = second, first + second
    return mult * first


def _remaining_unplanted_targets(snapshot: Snapshot, plan: DayPlan, config: dict, crop: str) -> int:
    """review_89d99f0_2026-08-05.md M5: how many of today's target tiles for `crop` are not yet planted. Buying
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
    farm_hand_cost_mult: int = 1,
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
    sell_products = ("STRAWBERRY", "CARROT", "EGG", "MILK", "WOOL", "FERTILIZER")
    if plan.force_liquidation:
        # plan.md G14: WHEAT is bought (not grown) purely as animal feed and is normally kept
        # at ~0 in the shed by the daily PICKUP->FEED loop, so it's excluded from the day-to-day
        # sell loop above (selling it there would just buy-high-sell-low against the agent's
        # own feed pipeline for no gain). But it IS a real, sellable market product — once
        # liquidation starts and no further feed cycle can pay off, any WHEAT still sitting in
        # the shed (rounding leftovers, or an animal that already escaped/died) is stranded
        # value the endgame must not leave on the table.
        sell_products += ("WHEAT",)
    for product in sell_products:
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
            remaining_unplanted = _remaining_unplanted_targets(snapshot, plan, config, crop)
            seeds_to_buy = max(0, min(seed_buffer, remaining_unplanted) - seed_count)
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

        # Wheat is bought for every animal already placed (not yet-to-be-placed ones) — this
        # is the "≥1 turn earlier" plan.md §5.1 asks for: buying as soon as a shortfall shows
        # up leaves the rest of the day's slack for PICKUP -> FEED instead of racing FEED's
        # zero-slack `consecutive_unfed` deadline. Unlike BUY_ANIMAL/new seeds, this must NOT
        # be gated on force_liquidation: planner.py's make_day_plan deliberately keeps
        # already-placed animals fed through the endgame ("they keep producing until the
        # episode ends") — gating this on liquidation starved both animals to death within 2
        # days of liquidation_day in a v1d smoke test.
        # review.md M4: was gated on `hour == 0` only, so an hour-0 cash shortfall got no
        # retry even after the same day's SELLs freed up money. Sizing wheat_needed against
        # unfed_animals (not placed_animals) keeps re-running every hour idempotent: FEED
        # flips a tile's fed_today True and consumes 1 WHEAT in the same action
        # (engine_reference/kaggriculture.py's FEED op), so wheat_have and unfed_animals both
        # drop by 1 together and wheat_needed stays 0 — sizing against the full placed_animals
        # count instead made every FEED's own consumption look like a fresh shortfall and
        # re-bought a day's worth of wheat on every hour an animal got fed.
        placed_animals = sum(
            1 for row in snapshot.my_tiles for tile in row
            if isinstance(tile, dict) and "animal" in tile
        )
        if placed_animals > 0:
            unfed_animals = sum(
                1 for row in snapshot.my_tiles for tile in row
                if isinstance(tile, dict) and "animal" in tile and not tile.get("fed_today")
            )
            wheat_have = int(snapshot.shed.get("WHEAT", 0)) + sum(
                inv.get("WHEAT", 0) for inv in snapshot.inventories
            )
            wheat_needed = max(0, unfed_animals - wheat_have)
            if wheat_needed > 0:
                wheat_price = max(1, int(snapshot.market_prices.get("WHEAT", 25)))
                affordable = int(available_money // wheat_price)
                wheat_to_buy = min(wheat_needed, affordable)
                if wheat_to_buy:
                    orders.append(["BUY_PRODUCT", "WHEAT", wheat_to_buy])
                    available_money -= wheat_to_buy * wheat_price
                if wheat_to_buy < wheat_needed:
                    # review.md M4: partial/zero wheat purchases were invisible even in a
                    # debug run — this is the leading indicator for an animal escape.
                    emit_receipt({
                        "kind": "wheat_shortfall",
                        "step": snapshot.step,
                        "placed_animals": placed_animals,
                        "unfed_animals": unfed_animals,
                        "wheat_have": wheat_have,
                        "wheat_needed": wheat_needed,
                        "wheat_bought": wheat_to_buy,
                        "available_money": available_money,
                    })

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
            cost = _hire_cost(hires_already + offset, farm_hand_cost_mult)
            if available_money < cost:
                break
            orders.append(["HIRE"])
            available_money -= cost

    max_orders = int(executor_config["max_market_orders"])
    if len(orders) > max_orders:
        # review_89d99f0_2026-08-05.md M7: raising here would turn one budget slip into a submission ERROR and a
        # lost episode. Truncate defensively instead and leave a receipt to catch it in dev.
        # review.md H8: truncate by priority (_ORDER_TIER), not construction order — a stable
        # sort keeps each tier's own relative order (e.g. SELL products stay in their existing
        # order among themselves), only reordering across tiers.
        emit_receipt({
            "kind": "market_order_budget_truncated",
            "step": snapshot.step,
            "requested": len(orders),
            "max_orders": max_orders,
            "dropped": sorted(orders, key=_order_tier)[max_orders:],
        })
        orders = sorted(orders, key=_order_tier)[:max_orders]
    return orders
