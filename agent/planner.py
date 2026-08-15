"""Layer 1 economic planner."""
from dataclasses import dataclass, field

from .animal_slots import animal_slot_ranges
from .constants import ANIMALS, CROPS, MARKET_PARAMS, SHED_ACCESS, market_price
from .demand import npc_daily_demand, shop_buyer_counts
from .state import Snapshot


@dataclass(frozen=True)
class DayPlan:
    plant_targets: dict[str, int] = field(default_factory=dict)
    hands_target: int = 0
    buy_land: bool = False
    animal_purchases: dict[str, int] = field(default_factory=dict)
    structures_to_build: dict[str, int] = field(default_factory=dict)
    max_new_plants: int = 0
    sell_floor_price: dict[str, int] = field(default_factory=dict)
    seed_orders: dict[str, int] = field(default_factory=dict)
    season_phase: str = "OPEN"
    force_liquidation: bool = False


#: review_89d99f0_2026-08-05.md C1/§1.3: both crops' watering trigger (scheduler.py needs_water) fires on
#: alternating days — `consecutive_unwatered >= 1` means "skip a day, water the next" — not
#: every day a tile is alive. A demand model that charged a full (distance+1) every day
#: overshot real demand roughly 2x and throttled plant_targets even at v1b's already-working
#: scale; tuned against the working baseline instead of derived from first principles, so this
#: is deliberately approximate (see module docstring), not an exact schedule simulation.
_WATERING_DAYS_PER_TILE_PER_DAY = 0.5


def _animal_daily_demand(config: dict) -> float:
    """v1f: the capacity gate below used to size hands purely against crop-watering demand,
    with no notion that every already-targeted animal also costs unit-turns every single day
    — FEED and CARE are both reset (and re-required) at day rollover just like crop watering
    (state.animals_needing / engine_reference/kaggriculture.py's day-rollover reset), so they
    belong in the same *recurring* demand pool crop watering already occupies. Approximated
    the same way as crop watering above (not an exact schedule simulation): one
    (distance-from-shed-spawn + 1) commute per animal per day covers the WHEAT pickup (at
    spawn, ~free) + walk + FEED, plus one more turn for CARE at the same tile (no extra walk,
    since FEED and CARE both apply to the tile the commute already reached).

    v1g: sums over every reserved slot tile across every animal name (animal_slot_ranges),
    not one tile per unique name — a config with 8 COW + 5 SHEEP costs 13x this per-tile term,
    not 2x.
    """
    animals_config = config.get("animals", {})
    if not animals_config.get("enabled", False):
        return 0.0
    spawn = SHED_ACCESS[0]
    demand = 0.0
    for tiles in animal_slot_ranges(config).values():
        for x, y in tiles:
            distance = abs(x - spawn[0]) + abs(y - spawn[1])
            demand += (distance + 1) + 1
    return demand


def _capacity_limited_targets(snapshot: Snapshot, config: dict, raw_targets: dict[str, int]) -> dict[str, int]:
    """review_89d99f0_2026-08-05.md C1/§1.3 + §5#2: the planner used to set plant_targets from config constants
    alone, with no notion of whether the fleet can actually keep that many tiles watered.
    Every target tile costs roughly (distance-from-shed-spawn + 1) unit-turns on the days it
    needs watering (units respawn at the shed every EOD, so this commute is a recurring cost,
    not a one-off) — if that total demand exceeds `safety_factor` of the day's unit-turn
    supply, trim target counts (never below what's already planted, since that watering
    obligation already exists) until it fits, instead of quietly setting up more plants than
    the day can water and losing them to `consecutive_unwatered` deaths (the v1c root cause,
    review_89d99f0_2026-08-05.md §1).

    v1f: the budget crop targets compete for is the day's unit-turn supply *minus* the fixed,
    non-crop recurring demand (animal FEED/CARE, `_animal_daily_demand`) that supply must
    also cover — without this, the gate could size crop targets against the full supply as if
    animals were free, quietly starving the animals' own daily upkeep of the hands it needs
    once crop demand fills the rest of the day.
    """
    scheduler_config = config["scheduler"]
    turns_per_day = config["runtime"]["turns_per_day"]
    spawn = SHED_ACCESS[0]
    num_units = 1 + len(snapshot.hand_positions)
    supply = num_units * turns_per_day
    safety_factor = float(config["planner"].get("capacity_safety_factor", 0.8))
    if supply <= 0:
        return dict(raw_targets)
    crop_budget = max(0.0, safety_factor * supply - _animal_daily_demand(config))

    def demand_for(crop: str, target: int) -> float:
        tiles = scheduler_config["target_tiles"].get(crop, ())
        return sum(
            (abs(x - spawn[0]) + abs(y - spawn[1]) + 1) * _WATERING_DAYS_PER_TILE_PER_DAY
            for x, y in tiles[:target]
        )

    limits = dict(raw_targets)
    floors = {}
    for crop in limits:
        tiles = scheduler_config["target_tiles"].get(crop, ())
        planted_indices = [
            target_index
            for target_index, (x, y) in enumerate(tiles)
            if isinstance(snapshot.my_tiles[y][x], dict)
            and snapshot.my_tiles[y][x].get("kind") == "PLANT"
        ]
        floors[crop] = (max(planted_indices) + 1) if planted_indices else 0

    while sum(demand_for(crop, limits[crop]) for crop in limits) > crop_budget:
        reducible = [crop for crop in limits if limits[crop] > floors[crop]]
        if not reducible:
            break
        crop = max(reducible, key=lambda c: limits[c])
        limits[crop] -= 1

    return limits


def _dynamic_sell_floors(
    snapshot: Snapshot, config: dict, env_config, static_floors: dict[str, int]
) -> dict[str, int]:
    """current_phase.md §v1g.2 (γ): raise each product's sell floor to the price implied by the
    glut the town can actually work off, and never lower it below the configured static floor.

    The mechanism, in one line: **a price floor and a sell-rate cap are the same object.**
    market_price is monotone in market inventory, so "refuse to sell below price P" is exactly
    "refuse to push inventory past the level whose price is P". Expressing the cap as a floor
    rather than as a units/day budget buys three things that matter here:

    1. It is *stateless*. No per-day sold counter to keep in sync with orders the 10-order cap
       may have truncated, and no drift between what the agent thinks it sold and what the
       engine executed.
    2. It reacts to the **opponent's** selling too, not just ours — the observed inventory
       already contains both players' supply and the town's consumption. A units/day budget on
       our own sales would happily keep trickling into a market the opponent has already
       crashed.
    3. It cannot create a single extra market order (current_phase.md §v1g.2 «10-order cap»):
       it only ever shrinks `sell_units` inside orders the executor was already going to emit,
       and an order shrunk to 0 disappears. Both fertilizer attempts died to order crowd-out;
       this increment structurally cannot repeat that failure.

    The headroom is `headroom_days` worth of NPC demand: pushing the market that far into glut
    is tolerable precisely because the town drains it back within that many days.

    Four cases are exempt, all four load-bearing:

    - **An early town has not revealed itself yet.** Shops unlock one per `townShopUnlockInterval`
      (3) days *in both regimes* — the announced balance change alters the composition of the
      final town, not the rate at which it appears. So "no shop buys WOOL" on day 4 is not
      evidence of a wool-less town, it is evidence that only one shop exists yet, and it says the
      same thing in an episode that will eventually unlock YARN_STORE as in one that never will.
      Throttling on it taxes exactly the part of the season where revenue still compounds into
      hands, animals and land. Below `shop_evidence_min_unlocks` unlocks the floors therefore
      stay static and the agent sells the way v1g_1 does.
    - **A product that already has a shop is not throttled at all.** One shop instance is 6
      ticks/day of demand on top of the town centre's 2, which is more than a 5x5 field or a
      13-slot pasture can produce — the market works our whole output off on its own and the
      throttle can only defer revenue. Measured, not assumed: a proportional version that
      throttled at *every* demand level lost $589-$1,086/ep across DEV seeds 0-7 at every
      headroom setting that bound at all, because today's engine eventually unlocks all eight
      shops and the throttle was therefore pure cost. Gating on "does a shop buy this?" is also
      what the increment is actually named after — this is a *shop*-adaptive layer, not a
      general volume governor (that is v1i's job).
    - **Zero demand is not "very low demand".** With no buyer at all the price is monotonically
      decreasing in cumulative sales, so total revenue for a given number of units is
      path-independent and throttling can only end the season with unsold stock worth $0.
      FERTILIZER is permanently in this class (no shop lists it, the town centre excludes it),
      so it keeps its static floor untouched — which also keeps the frozen §v1g.2 (δ) fertilizer
      behaviour bit-identical, deliberately.
    - **A floor that never lets go is a liquidation-day cliff.** If the shed is holding more
      than the days before `liquidation_day` can move at the throttled rate, the throttle is
      relaxed to at least the rate that clears it — otherwise the whole stock lands on the
      market in one endgame dump, straight through the very cliff this is meant to avoid.
      (`force_liquidation` ignores floors entirely, so day >= liquidation_day is already safe.)

    Sized off the day-start shed, not the current hour's, because make_day_plan runs on the day
    boundary: the floor stays constant within the day, which is what keeps this a function of
    *demand* rather than of the instantaneous price (the latter oscillates — sell, price drops,
    stop, price recovers, sell).
    """
    executor_config = config["executor"]
    if not executor_config.get("dynamic_sell_floor", False):
        return dict(static_floors)

    if len(snapshot.unlocked_shops) < int(executor_config.get("shop_evidence_min_unlocks", 5)):
        return dict(static_floors)

    headroom_days = float(executor_config.get("sell_headroom_days", 3.0))
    demand = npc_daily_demand(snapshot.unlocked_shops, snapshot.day, env_config)
    buyers = shop_buyer_counts(snapshot.unlocked_shops)
    liquidation_day = int(config["endgame"]["liquidation_day"])
    days_left = max(1, liquidation_day - snapshot.day)

    floors = dict(static_floors)
    for product, static_floor in static_floors.items():
        daily = demand.get(product, 0)
        if daily <= 0 or buyers.get(product, 0) > 0 or product not in MARKET_PARAMS:
            continue
        stock = int(snapshot.shed.get(product, 0))
        must_clear_per_day = -(-stock // days_left)
        headroom = max(int(headroom_days * daily), must_clear_per_day)
        equilibrium = int(MARKET_PARAMS[product]["I0"])
        floors[product] = max(int(static_floor), market_price(product, equilibrium + headroom))
    return floors


def _herd_ramp_cap(ramp, day: int, targets: dict) -> int | None:
    """Total-herd cap for the current day under an optional day-gated ramp.

    ROADMAP §4.3 S3 step 2 (v1s). `ramp` is None (no cap — the shipped step-purchase behaviour,
    the full targets from day 0) or a list of ``[day_threshold, cap]`` rungs sorted ascending by
    day. The cap is the first rung whose threshold is >= the current day; once day is past every
    rung the herd is uncapped (returns the full summed target, which is equivalent to no clamp).

    §4.0's profile ("6 by d5, 12 by d10, 13 thereafter") is expressed as ``[[5, 6], [10, 12]]``.
    Returns an int remaining-cap to spend across names in ``targets`` dict order, or None when
    there is no ramp — the caller then leaves every per-name count untouched.
    """
    if not ramp:
        return None
    for day_threshold, cap in ramp:
        if day <= int(day_threshold):
            return int(cap)
    return sum(int(c) for c in targets.values())


def make_day_plan(snapshot: Snapshot, config: dict, env_config=None) -> DayPlan:
    """Build the conservative v1a carrot plan.

    v1g.2: `env_config` is the engine `configuration` kaggle_environments passes as the agent's
    second argument (policy.agent). It is optional and only feeds the demand model, so every
    existing two-argument call still produces a plan — it just falls back to the engine's own
    default sell intervals.
    """
    planner_config = config["planner"]
    executor_config = config["executor"]
    if not planner_config.get("enabled", False):
        return DayPlan()

    # review_89d99f0_2026-08-05.md L6: "enabled" used to be dead — liquidation fired unconditionally off
    # liquidation_day regardless of this flag's value; it's now load-bearing.
    liquidation_active = (
        config["endgame"].get("enabled", False)
        and snapshot.day >= config["endgame"]["liquidation_day"]
    )
    phase = "LIQUIDATE" if liquidation_active else "GROW"
    carrot_target = 0 if phase == "LIQUIDATE" else int(planner_config["carrot_tiles"])
    strawberry_target = (
        int(planner_config["strawberry_tiles"])
        if phase != "LIQUIDATE" and snapshot.day <= planner_config["strawberry_last_plant_day"]
        else 0
    )
    # plan.md §5 v1c: once NE is actually unlocked, grow the same targets by the NE-mirrored
    # tile counts appended to target_tiles — never before unlock (those tiles are still
    # "LOCKED", not None, so counting them into plant_targets would only make the capacity
    # gate below model demand for tiles that can't be walked to yet).
    ne_land_unlocked = config.get("land", {}).get("enabled", False) and "NE" in snapshot.my_quadrants
    if ne_land_unlocked:
        if carrot_target:
            carrot_target += int(planner_config.get("ne_carrot_tiles", 0))
        if strawberry_target:
            strawberry_target += int(planner_config.get("ne_strawberry_tiles", 0))
    # v1h' (current_phase.md §v1h'): SW's WHEAT, gated on three things beyond the unlock.
    # `wheat_first_plant_day` is the load-bearing one: _capacity_limited_targets trims whichever
    # crop currently has the *largest* target, so a WHEAT target that appeared while STRAWBERRY
    # was still being planted would be trimmed out of STRAWBERRY's budget instead of its own
    # (STRAWBERRY's floor — what is already in the ground — only protects tiles that are planted
    # *already*). STRAWBERRY has a hard planting deadline and WHEAT does not, so WHEAT waits.
    # In practice SW is not affordable that early anyway; this keeps that a fact about the config
    # rather than a fact about the bank balance.
    #
    # v1o.1: this used to read `snapshot.day > strawberry_last_plant_day`, which coupled the two
    # windows — extending STRAWBERRY's replant window (the v1o.1 increment) would have moved
    # WHEAT's first plant day with it and emptied SW for the season. `wheat_first_plant_day`
    # defaults to the day that expression produced at the old strawberry_last_plant_day of 5.
    sw_land_unlocked = config.get("land", {}).get("enabled", False) and "SW" in snapshot.my_quadrants
    # The last WHEAT that can still be planted goes in on wheat_last_plant_day and is
    # harvest-ready max_yield_day later; after that SW is empty for the rest of the season.
    sw_work_last_day = (
        int(planner_config.get("wheat_last_plant_day", 0)) + int(CROPS["WHEAT"]["max_yield_day"])
    )
    wheat_target = (
        int(planner_config.get("sw_wheat_tiles", 0))
        if (
            sw_land_unlocked
            and phase != "LIQUIDATE"
            and snapshot.day >= int(planner_config.get("wheat_first_plant_day", 6))
            and snapshot.day <= int(planner_config.get("wheat_last_plant_day", 0))
        )
        else 0
    )
    raw_targets = {"CARROT": carrot_target, "STRAWBERRY": strawberry_target}
    if wheat_target:
        raw_targets["WHEAT"] = wheat_target
    plant_targets = _capacity_limited_targets(snapshot, config, raw_targets)

    max_new_plants = int(planner_config["max_new_plants_per_day"])
    if ne_land_unlocked:
        max_new_plants += int(planner_config.get("ne_max_new_plants_per_day", 0))
    if sw_land_unlocked:
        # Same reasoning as ne_max_new_plants_per_day: WHEAT and the two existing crops share
        # one daily planting budget in build_tasks, in CARROT -> STRAWBERRY -> WHEAT order, so
        # adding tiles without adding budget would just mean WHEAT is never actually planted.
        # WHEAT needs its own share every ~5 days as tiles are harvested empty and replanted.
        max_new_plants += int(planner_config.get("sw_max_new_plants_per_day", 0))

    # plan.md §5.1 v1d / v1g: target counts (not one-each) drive both how many of each animal
    # to buy and how many structure tiles of each kind to build. LIQUIDATE doesn't touch this:
    # animals aren't sold off early like ongoing crops, they keep producing until the episode
    # ends. A target count of 0 (e.g. GOOSE screened out) simply builds nothing for that
    # structure/name, no separate ablation flag needed.
    animals_config = config.get("animals", {})
    animal_purchases = {}
    structures_to_build = {}
    if animals_config.get("enabled", False):
        # v1s (ROADMAP §4.3 S3 step 2): optional day-gated herd ramp. `animals.ramp` is None
        # (shipped: full targets from day 0, a step purchase) or a list of [day, cap] rungs — the
        # total herd is capped for the current day and the cap is spent across names in targets
        # DICT ORDER (COW before SHEEP for the 9C+4S profile). §4.0 names the ramp as the specific
        # thing the old 12-14-animal STOP got wrong. Tile identity is unaffected — animal_slot_ranges
        # keys off the full config targets, not this plan — so the ramp only delays purchases.
        remaining_cap = _herd_ramp_cap(
            animals_config.get("ramp"), snapshot.day, animals_config.get("targets", {})
        )
        for name, count in animals_config.get("targets", {}).items():
            count = int(count)
            if count <= 0:
                continue
            if remaining_cap is not None:
                count = min(count, remaining_cap)
                remaining_cap -= count
                if count <= 0:
                    continue
            animal_purchases[name] = count
            structure = ANIMALS[name]["structure"]
            structures_to_build[structure] = structures_to_build.get(structure, 0) + count

    return DayPlan(
        plant_targets=plant_targets,
        # v1h': the crew grows with the *work*, not with the deed. It rises once SW is actually
        # observed unlocked (not when we merely intend to buy it — hands are re-hired and
        # re-paid every single morning, so an early bump is a recurring cost against tiles that
        # do not exist yet) and it drops back to the v1f-tuned 6 as soon as SW's last crop is
        # harvestable.
        #
        # That second half is not tidiness, it is a measured escape fix. Carrying 8 hands into
        # the endgame lost exactly 2 far SHEEP ((0,2)/(0,3), distance 5-6) to
        # consecutive_unfed >= 2 on day 27 in all four smoke seeds, with $35k in the bank and
        # 13-18 WHEAT sitting in the shed — pure unit contention on days 25-26, where
        # liquidation's per-unit DROP tasks share priority 0 with FEED. Neither ingredient does
        # it alone: 8 hands without SW escaped 0 animals, and SW with 6 hands escaped 0. The
        # endgame is exactly the phase v1g's feed logistics were tuned for at 6 hands, so it
        # gets 6 hands back.
        #
        # v1o.2: the "drops back to 6" half is now its own knob, `endgame_hands_target`, and it
        # only applies once SW's work is done — before SW exists the pre-SW `hands_target` is
        # still what the crew is sized to. Splitting it is what makes the endgame crew screenable
        # apart from the mid-season crew; at endgame_hands_target=6 this is the v1h' behaviour
        # unchanged.
        hands_target=int(
            planner_config["sw_hands_target"]
            if sw_land_unlocked and snapshot.day <= sw_work_last_day
            else planner_config["endgame_hands_target"]
            if sw_land_unlocked
            else planner_config["hands_target"]
        ),
        sell_floor_price=_dynamic_sell_floors(
            snapshot, config, env_config, executor_config["sell_floor_price"]
        ),
        season_phase=phase,
        force_liquidation=phase == "LIQUIDATE",
        animal_purchases=animal_purchases,
        structures_to_build=structures_to_build,
        max_new_plants=max_new_plants,
    )
