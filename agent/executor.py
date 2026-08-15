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


def _projected_eod_stock(snapshot: Snapshot, scheduled_unit_actions: list[list[str]]) -> int:
    """Stock that will compete for shed capacity after this turn's unit actions and EOD drop."""
    total = sum(snapshot.shed.values()) + sum(
        sum(inventory.values()) for inventory in snapshot.inventories
    )
    unit_positions = (snapshot.farmer_pos, *snapshot.hand_positions)
    for unit_index, action in enumerate(scheduled_unit_actions):
        if unit_index >= len(unit_positions) or not isinstance(action, list) or not action:
            continue
        x, y = unit_positions[unit_index]
        tile = snapshot.my_tiles[y][x]
        inventory = (
            snapshot.inventories[unit_index]
            if unit_index < len(snapshot.inventories)
            else {}
        )
        op = action[0]
        if op == "HARVEST" and isinstance(tile, dict) and tile.get("yield_units", 0) > 0:
            if tile.get("kind") == "PLANT":
                crop_data = CROPS.get(tile.get("crop"))
                if (
                    crop_data is not None
                    and snapshot.day - tile.get("planted_day", snapshot.day)
                    >= crop_data["first_yield_day"]
                ):
                    total += int(tile["yield_units"])
            elif "animal" in tile:
                total += int(tile["yield_units"])
        elif (
            op == "COLLECT_FERTILIZER"
            and isinstance(tile, dict)
            and "animal" in tile
            and tile.get("fertilizer_available")
        ):
            total += 1
        elif (
            op == "FEED"
            and isinstance(tile, dict)
            and "animal" in tile
            and not tile.get("fed_today")
            and inventory.get("WHEAT", 0) > 0
        ):
            total -= 1
        elif op == "PLACE" and len(action) >= 2 and inventory.get(action[1], 0) > 0:
            total -= 1
    return total


def _projected_near_term_incoming(
    snapshot: Snapshot,
    scheduled_unit_actions: list[list[str]],
    horizon_days: int = 2,
) -> int:
    """Conservative reserve for products mechanically due before prices refresh enough."""
    unit_positions = (snapshot.farmer_pos, *snapshot.hand_positions)
    harvested = {
        unit_positions[index]
        for index, action in enumerate(scheduled_unit_actions)
        if index < len(unit_positions)
        and isinstance(action, list)
        and action[:1] == ["HARVEST"]
    }
    incoming = 0
    for y, row in enumerate(snapshot.my_tiles):
        for x, tile in enumerate(row):
            if not isinstance(tile, dict) or (x, y) in harvested:
                continue
            if tile.get("kind") == "PLANT":
                crop = CROPS.get(tile.get("crop"))
                if crop is None:
                    continue
                yield_units = int(tile.get("yield_units", 0))
                if crop["ongoing"]:
                    for offset in range(1, horizon_days + 1):
                        future_day = snapshot.day + offset
                        days_since_first = (
                            future_day
                            - tile.get("planted_day", future_day)
                            - crop["first_yield_day"]
                        )
                        if days_since_first >= 0 and days_since_first % crop["interval"] == 0:
                            yield_units = min(crop["max_yield"], yield_units + 2)
                    if (
                        snapshot.day + horizon_days
                        - tile.get("planted_day", snapshot.day)
                        >= crop["first_yield_day"]
                    ):
                        incoming += yield_units
                elif (
                    snapshot.day + horizon_days
                    - tile.get("planted_day", snapshot.day)
                    >= crop["first_yield_day"]
                ):
                    # WATER/FERTILIZE can still increase a finite crop before harvest; reserve
                    # its bounded maximum rather than pretending today's partial yield is final.
                    incoming += int(crop["max_yield"])
            elif "animal" in tile:
                animal = ANIMALS.get(tile.get("animal"))
                if animal is None:
                    continue
                yield_units = int(tile.get("yield_units", 0))
                for offset in range(1, horizon_days + 1):
                    future_day = snapshot.day + offset
                    days_since_first = (
                        future_day
                        - tile.get("placed_day", future_day)
                        - animal["first_yield_day"]
                    )
                    if days_since_first >= 0 and days_since_first % animal["interval"] == 0:
                        yield_units = min(animal["max_held"], yield_units + 2)
                incoming += yield_units
                # The engine makes one fertilizer unit available at every daily refresh.
                incoming += horizon_days
    return incoming


def _sell_batch_size(
    product: str,
    stock: int,
    inventory: int,
    safety_units: int,
    floor: int,
    hard_floor: int,
    average_rule: bool,
) -> int:
    """How many units of `product` to put in this turn's SELL order.

    The pre-v1i rule is the `average_rule=False` branch: stop at the first unit whose quoted
    price falls to `floor`. current_phase.md §v1i (1) points out that this judges the batch by
    its **marginal** unit while the engine actually pays `Σ p(inventory + i)` — the batch's
    realized average is strictly above the unit the loop tests, so the check is conservative
    and leaves revenue behind.

    The `average_rule=True` branch judges the batch by what it will actually realize: keep
    taking units while the running mean stays at or above `floor`. Two properties make this
    safe rather than merely looser:

    * `hard_floor` (`liquidation_floor_price`) is a per-unit veto that the average can never
      override, so the rule structurally cannot manufacture the <=$5 sales the structural
      metric gate hard-zeroes (current_phase.md §1 Απόφαση Α).
    * whenever `floor <= hard_floor` — every product during liquidation, and CARROT/EGG always
      — the two branches are identical by construction, so this cannot move the endgame.

    `safety_units` stays in the quoted index in both branches, unchanged: it models the
    opponent's simultaneous SELL at the same per-unit lockstep index, which is a different
    correction from the marginal/average one and current_phase.md §v1i is explicit that both
    are needed together.
    """
    sell_units = 0
    batch_total = 0
    while sell_units < stock:
        unit_price = market_price(product, inventory + sell_units + safety_units)
        if unit_price <= hard_floor:
            break
        if unit_price <= floor:
            if not average_rule:
                break
            if (batch_total + unit_price) / (sell_units + 1) < floor:
                break
        sell_units += 1
        batch_total += unit_price
    return sell_units


def _safety_units(
    snapshot: Snapshot,
    executor_config: dict,
    product: str,
    supply_tracker=None,
) -> int:
    """Units of opponent supply to assume at our own quoted index (current_phase.md §v1i Η2).

    Falls back to the configured constant whenever the controller is off or has no evidence
    yet — which is the whole of day 0 and every product the opponent has not touched, i.e.
    the "empty prior" case §v1i requires the design to work under.
    """
    constant = int(executor_config["opponent_price_safety_units"])
    sell_ahead = executor_config.get("sell_ahead", {})
    if supply_tracker is None or not sell_ahead.get("predict_safety_units", False):
        return constant
    predicted = supply_tracker.predicted_units(snapshot, product)
    if predicted is None:
        return constant
    low = int(sell_ahead.get("min_safety_units", constant))
    high = int(sell_ahead.get("max_safety_units", constant))
    return max(low, min(high, int(predicted)))


def market_orders(
    snapshot: Snapshot,
    plan: DayPlan,
    ledger: ResourceLedger,
    scheduled_unit_actions: list[list[str]],
    config: dict,
    farm_hand_cost_mult: int = 1,
    supply_tracker=None,
) -> list[list]:
    """Allocate the v1a SELL/BUY_SEED orders within all hard budgets."""
    executor_config = config["executor"]
    if not executor_config.get("enabled", False):
        return []

    orders = []
    available_money = ledger.money
    average_rule = bool(executor_config.get("sell_ahead", {}).get("average_rule", False))
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
    sell_units_by_product = {}
    for product in sell_products:
        product_in_shed = int(snapshot.shed.get(product, 0))
        if product_in_shed <= 0:
            continue
        # v1h.2 D3: liquidation used to bypass the floor and dump the whole shed. Under
        # 1.32.6's flat town-centre demand that sent 110 units to market on day 26 in the
        # diagnostic seed, including 74 MILK units at <=$5. The normal product floors proved
        # too restrictive here (they increased shed overflow), so endgame uses one weak hard
        # floor: realize every unit still worth >$5, but do not turn inventory into pennies.
        floor = (
            int(executor_config["liquidation_floor_price"])
            if plan.force_liquidation
            else int(plan.sell_floor_price.get(product, 5))
        )
        safety_units = _safety_units(snapshot, executor_config, product, supply_tracker)
        inventory = int(snapshot.market_inventory.get(product, 0))
        sell_units = _sell_batch_size(
            product,
            product_in_shed,
            inventory,
            safety_units,
            floor,
            int(executor_config["liquidation_floor_price"]),
            average_rule,
        )
        if sell_units:
            sell_units_by_product[product] = sell_units

    # v1h.2d: SW-grown WHEAT beyond the next full-herd ration is genuine surplus. Dispose of
    # that surplus at EOD before it crowds out tomorrow's less-liquid animal products, then
    # cover any remaining immediate headroom shortfall from ordinary sellable stock. Every
    # marginal unit still obeys the existing $5 hard floor. This is product/reserve-aware and
    # EOD-only: neither a blanket floor nor the rejected dynamic sell throttle.
    turns_per_day = int(config["runtime"]["turns_per_day"])
    if not plan.force_liquidation and snapshot.hour == turns_per_day - 1:
        shed_capacity = 100  # pinned engine 1.32.6 configuration
        projected_stock = _projected_eod_stock(snapshot, scheduled_unit_actions)
        placed_animals = sum(
            1
            for row in snapshot.my_tiles
            for tile in row
            if isinstance(tile, dict) and "animal" in tile
        )
        reserves = {"WHEAT": placed_animals}
        product = "WHEAT"
        product_in_shed = int(snapshot.shed.get(product, 0))
        already_selling = sell_units_by_product.get(product, 0)
        carried_wheat = sum(
            int(inventory.get(product, 0)) for inventory in snapshot.inventories
        )
        reserve_needed_in_shed = max(0, reserves[product] - carried_wheat)
        wheat_surplus = max(
            0,
            product_in_shed - already_selling - reserve_needed_in_shed,
        )
        inventory = int(snapshot.market_inventory.get(product, 0))
        # v1i deliberately does NOT route the two EOD branches through the Η2 controller. They
        # already test against `hard_floor`, where a +-4 shift of the quoted index is worth
        # cents on WHEAT's flat curve, and they are the layer that took `animals_escaped`
        # 85 -> 0 and cleared the overflow (§v1h.2d). Keeping them on the constant leaves the
        # increment attributable to the main sell loop alone.
        safety_units = int(executor_config["opponent_price_safety_units"])
        hard_floor = int(executor_config["liquidation_floor_price"])
        extra = 0
        while (
            extra < wheat_surplus
            and market_price(
                product,
                inventory + already_selling + extra + safety_units,
            ) >= hard_floor
        ):
            extra += 1
        if extra:
            sell_units_by_product[product] = already_selling + extra

        normal_sells = sum(sell_units_by_product.values())
        near_term_incoming = _projected_near_term_incoming(
            snapshot, scheduled_unit_actions
        )
        headroom_needed = max(
            0,
            projected_stock + near_term_incoming - shed_capacity - normal_sells,
        )
        if headroom_needed > 0:
            for product in dict.fromkeys(sell_products):
                if headroom_needed <= 0:
                    break
                product_in_shed = int(snapshot.shed.get(product, 0))
                already_selling = sell_units_by_product.get(product, 0)
                surplus = max(
                    0,
                    product_in_shed - already_selling - reserves.get(product, 0),
                )
                if surplus <= 0:
                    continue
                inventory = int(snapshot.market_inventory.get(product, 0))
                safety_units = int(executor_config["opponent_price_safety_units"])
                hard_floor = int(executor_config["liquidation_floor_price"])
                extra = 0
                while (
                    extra < surplus
                    and extra < headroom_needed
                    and market_price(
                        product,
                        inventory + already_selling + extra + safety_units,
                    ) >= hard_floor
                ):
                    extra += 1
                if extra:
                    sell_units_by_product[product] = already_selling + extra
                    headroom_needed -= extra

    for product in dict.fromkeys((*sell_products, "WHEAT")):
        sell_units = sell_units_by_product.get(product, 0)
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
        # ROADMAP §4.3 S3 step 1e (v1r): FEED_RESERVE_DAYS and the reserved-herd count are now
        # config-gated (agent/config.py "feed_reserve_*"), all defaulting to the shipped, inert
        # behaviour. `total_placed + buy_target` counted animals on tiles plus this order's
        # additions but NOT animals already bought on earlier turns and still carried/in the shed
        # — each of which eats one WHEAT/day once placed — so purchases spread across turns
        # bypassed the guard (see the config note). total_in_flight and target_total are summed
        # across all names once, like total_placed, so the branch below is a constant-per-turn
        # choice of *which* herd to reserve for.
        FEED_RESERVE_DAYS = int(executor_config.get("feed_reserve_days", 2))
        count_in_flight = bool(executor_config.get("feed_reserve_counts_in_flight", False))
        reserve_horizon = str(executor_config.get("feed_reserve_horizon", "in_flight"))
        wheat_price_est = max(1, int(snapshot.market_prices.get("WHEAT", 25)))
        total_placed = sum(placed_count(snapshot, name) for name in plan.animal_purchases)
        total_in_flight = sum(
            sum(inv.get(name, 0) for inv in snapshot.inventories) + int(snapshot.shed.get(name, 0))
            for name in plan.animal_purchases
        )
        target_total = sum(int(t) for t in plan.animal_purchases.values())
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
            if reserve_horizon == "target":
                # Arm C2 (ROADMAP §4.3 S3 step 1e/2): reserve for the full intended herd — the sum
                # of animal_purchases targets — regardless of how many are placed or still in flight.
                # This is the reserve shape that keeps binding as the target grows past what has been
                # bought yet (the §4.0 herd-13 profile needs the $676 liability of 13 animals sized
                # from day 0). The earlier min(target_total, max(target_total, ...)) expression was
                # dead: max(target_total, X) >= target_total, so min(target_total, that) is always
                # target_total — cleaned up and proven byte-inert vs checkpoints/v1r_armC2 (step 2).
                reserve_herd = target_total
            elif count_in_flight:
                # Arm C1: the minimal fix — count animals already in flight toward the liability.
                reserve_herd = total_placed + total_in_flight + buy_target
            else:
                # Shipped behaviour: on-tile herd plus this order's additions only (the undercount).
                reserve_herd = total_placed + buy_target
            reserve = reserve_herd * wheat_price_est * FEED_RESERVE_DAYS
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
    #
    # v1o.2 — the crew ceiling, finally located. E0 measured the crew hitting `hands_target` on
    # every single day, and a v1o.2 smoke screen then measured `sw_hands_target` 10 -> 12 -> 14
    # as **byte-identical** to 10 (mean_diff exactly $0,00, CI [0, 0], every counter equal). The
    # cause is here and it is not money: **one HIRE is one market order, the engine processes at
    # most `maxMarketOrdersPerTurn` = 10 per player per turn and silently drops the rest**
    # (engine_reference/kaggriculture.py:538 + .json "extra orders beyond this limit are
    # silently dropped"), and hands are wiped every night — so a crew rebuilt entirely inside
    # hour 0 can never exceed 10, whatever the target says. This is the real mechanism behind
    # ROADMAP §3.3's v1j STOP ("+2 hands never hired"), which had been attributed to cost.
    #
    # Two changes, one mechanism — "emit only what fits, continue next turn":
    #   * hires may now be emitted through `hire_last_hour` instead of at hour 0 only. The
    #     engine's own `hires_today` counter carries the fib() price escalation across turns
    #     within the day (:690-694, reset at :868), so hire 11 costs fib(11) whether it is
    #     bought at hour 0 or hour 2 — the split changes *when*, never *what*.
    #   * the order-slot cap is now applied unconditionally, not only on the cashless-morning
    #     sell-credit path. Without that, a 10-hire morning fills the whole budget and the
    #     truncation below — which sorts HIRE to tier 0 — silently drops that turn's SELLs.
    if snapshot.hour <= int(executor_config.get("hire_last_hour", 0)) and (
        plan.hands_target > len(snapshot.hand_positions)
    ):
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
        kept = sorted(orders, key=_order_tier)[:max_orders]
        # current_phase.md §v1m Δ2 / §v1m.2 Ε1: *which* orders survive the cut is still decided
        # by tier (HIRE first, SELL last) — H8 above is unchanged. What changes is the order the
        # survivors are *emitted* in. The engine executes a turn's market orders in emission
        # order, so a kept SELL sitting at index 6-9 prices against inventory that the same
        # turn's earlier orders have already moved. Truncation only fires on the busiest days
        # (~56 turns/ep at the cap), i.e. exactly the days with the most to sell. Stable sort:
        # SELLs keep their existing relative order, and so do the rest among themselves.
        orders = sorted(kept, key=lambda order: order[0] != "SELL")
    return orders
