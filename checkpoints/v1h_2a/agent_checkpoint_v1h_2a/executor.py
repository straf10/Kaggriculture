"""Layer 3 market-order executor."""
from .constants import ANIMALS, CROPS, LAND_ORDER, LAND_PRICES, market_price
from .debug import emit_receipt
from .planner import DayPlan
from .scheduler import ResourceLedger, animal_placed, open_animal_slots, placed_count
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

    if config.get("animals", {}).get("enabled", False):
        # v1g: this block used to sit AFTER BUY_SEED/BUY_ANIMAL below, so wheat for animals
        # ALREADY PLACED only got whatever cash those two left over. _ORDER_TIER already
        # documents WHEAT (tier 1) as senior to BUY_ANIMAL (tier 2) and BUY_SEED (tier 3), but
        # that tier only governed truncation order, not actual money reservation order — the
        # two silently disagreed. At 1-3 animals a new purchase was at most ~$300-500,
        # one-time, so this never bit; at v1g's 8 COW + 5 SHEEP ($400/$500 each, several
        # bought the same ramp-up day) a single heavy BUY_ANIMAL day could crowd out that
        # day's wheat entirely, and a dev-screen run showed exactly that: thousands of
        # consecutive_unfed>=2 escapes concentrated during herd ramp-up. Reserving wheat money
        # first, ahead of BUY_SEED/BUY_ANIMAL, fixes the actual spend order to match the tier
        # comment's stated intent.
        #
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

    if not plan.force_liquidation:
        seed_buffer = int(executor_config["seed_buffer"])
        # v1h': WHEAT joins as SW's crop. It costs $10/seed (the cheapest in CROPS) and its
        # target is 0 until SW is unlocked and STRAWBERRY's planting window has closed, so this
        # buys nothing at all before then — _remaining_unplanted_targets reads plan.plant_targets,
        # which the planner leaves out entirely until both conditions hold.
        for crop in ("CARROT", "STRAWBERRY", "WHEAT"):
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

    if config.get("animals", {}).get("enabled", False) and not plan.force_liquidation:
        # plan.md §5.1 v1d / v1g: only buy up to as many empty, already-built structure slots
        # as `name` actually has waiting — buying more would just have the surplus sit in the
        # shed as dead capital (the same MASTERPLAN §3.2#7 lesson land-without-hands teaches,
        # generalized from "never buy a second one" to "never buy past open homes" now that a
        # name can have N slots). New investment stops once liquidation starts (no runway left
        # to recoup an animal's cost), same as crops.
        #
        # v1g: a debug trace of a dev-screen episode found the actual mechanism behind
        # catastrophic animals_escaped counts — day 0, as soon as PASTURE finished building,
        # the loop below spent almost the entire $3000 starting bankroll buying 5 animals in
        # one hour. With no crop income yet, that left ~$0 for wheat on BOTH day 0 and day 1
        # (the wheat-purchase block above already gives already-placed animals first claim on
        # cash, but these were bought and placed within the same hour it was reserving for —
        # money for their own near-term feed was never set aside). Two straight unfed days is
        # exactly the engine's escape threshold (consecutive_unfed >= 2), so the whole batch
        # escaped together. Reserve enough cash to feed the herd this hour's purchases would
        # create for FEED_RESERVE_DAYS before spending further on NEW animals.
        FEED_RESERVE_DAYS = 2
        wheat_price_est = max(1, int(snapshot.market_prices.get("WHEAT", 25)))
        total_placed = sum(placed_count(snapshot, name) for name in plan.animal_purchases)
        for name, target in plan.animal_purchases.items():
            placed = placed_count(snapshot, name)
            carried = sum(inv.get(name, 0) for inv in snapshot.inventories)
            shed_have = int(snapshot.shed.get(name, 0))
            in_flight = carried + shed_have
            still_wanted = target - placed - in_flight
            if still_wanted <= 0:
                continue
            open_slots = len(open_animal_slots(snapshot, config, name))
            headroom = max(0, open_slots - in_flight)
            buy_target = min(still_wanted, headroom)
            if buy_target <= 0:
                continue
            cost = int(ANIMALS[name]["cost"])
            reserve = (total_placed + buy_target) * wheat_price_est * FEED_RESERVE_DAYS
            spendable = max(0, available_money - reserve)
            affordable = int(spendable // cost)
            buy_n = min(buy_target, affordable)
            if buy_n <= 0:
                continue
            orders.append(["BUY_ANIMAL", name, buy_n])
            available_money -= buy_n * cost
            total_placed += buy_n

    # v1h': owned_extra counts quadrants past NW, which is exactly the index the engine itself
    # uses to price and pick the next one (_do_buy_land: LAND_ORDER[len(unlocked)-1]). Buying
    # is therefore a walk down land["quadrants"] in LAND_ORDER order, not an NE special case —
    # and the assert-by-config below keeps the two lists from silently drifting apart.
    land_config = config.get("land", {})
    wanted_quadrants = tuple(land_config.get("quadrants", ()))
    owned_extra = sum(1 for quadrant in snapshot.my_quadrants if quadrant != "NW")
    if (
        not plan.force_liquidation
        and land_config.get("enabled", False)
        and owned_extra < len(wanted_quadrants)
        and owned_extra < len(LAND_ORDER)
        and LAND_ORDER[owned_extra] == wanted_quadrants[owned_extra]
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
        # BUY_LAND is atomic (like HIRE), so the engine no-ops it once every quadrant is owned.
        # v1h': the same reserve applies to each purchase. SW costs twice NE ($2000 vs $1000)
        # and therefore lands later on its own, without a second, separately-tuned threshold —
        # the trigger stays "the shed has genuine surplus beyond survival needs", which is what
        # made it self-regulating in v1c.
        cost = int(LAND_PRICES[owned_extra])
        reserve = int(land_config.get("min_reserve", 0))
        if available_money >= cost + reserve:
            orders.append(["BUY_LAND"])
            available_money -= cost

    # v1h.2 D1: hour-0 HIRE could not see same-turn SELL proceeds. After the 1.32.6 town-
    # centre cut (1 tick/day from day 0), day 1 often ends near $0; day 2 hour 0 then has
    # overnight fertilizer in the shed (EOD auto-drop) but available_money is still 0 because
    # SELL credits land only after this turn's market resolves. Emitting SELL without HIRE
    # left the day with 0 hands — the lone farmer spent it on FEED and the day-1-skipped crop
    # tiles ((2,2) STRAWBERRY, (3,4) CARROT) died at EOD. Seed-independent.
    #
    # Credit queued SELLs into the hire budget ONLY when cash alone cannot afford even the
    # first hire (the cashless-morning hole). Engine fact: market orders are processed by
    # index, so SELL at i funds HIRE at i+1 in the same list — construction order
    # SELL-then-HIRE is load-bearing. Cap added HIREs so truncation cannot reorder HIRE
    # ahead of that SELL (tier-sort would put HIRE first → silent no-op at $0).
    if snapshot.hour == 0 and plan.hands_target > len(snapshot.hand_positions):
        hire_budget = available_money
        first_cost = _hire_cost(snapshot.hires_today, farm_hand_cost_mult)
        using_sell_credit = hire_budget < first_cost
        if using_sell_credit:
            for order in orders:
                if order[0] == "SELL":
                    product, qty = order[1], int(order[2])
                    inventory = int(snapshot.market_inventory.get(product, 0))
                    for i in range(qty):
                        hire_budget += market_price(product, inventory + i)
        hires_needed = plan.hands_target - len(snapshot.hand_positions)
        if using_sell_credit:
            slots_left = max(0, int(executor_config["max_market_orders"]) - len(orders))
            hires_needed = min(hires_needed, slots_left)
        hires_already = snapshot.hires_today
        for offset in range(hires_needed):
            cost = _hire_cost(hires_already + offset, farm_hand_cost_mult)
            if hire_budget < cost:
                break
            orders.append(["HIRE"])
            hire_budget -= cost
            available_money = max(0, available_money - cost)

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
