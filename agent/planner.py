"""Layer 1 economic planner."""
from dataclasses import dataclass, field

from .constants import SHED_ACCESS
from .state import Snapshot


@dataclass(frozen=True)
class DayPlan:
    plant_targets: dict[str, int] = field(default_factory=dict)
    hands_target: int = 0
    buy_land: bool = False
    animal_purchases: dict[str, int] = field(default_factory=dict)
    structures_to_build: dict[str, int] = field(default_factory=dict)
    sell_floor_price: dict[str, int] = field(default_factory=dict)
    seed_orders: dict[str, int] = field(default_factory=dict)
    season_phase: str = "OPEN"
    force_liquidation: bool = False


#: review.md C1/§1.3: both crops' watering trigger (scheduler.py needs_water) fires on
#: alternating days — `consecutive_unwatered >= 1` means "skip a day, water the next" — not
#: every day a tile is alive. A demand model that charged a full (distance+1) every day
#: overshot real demand roughly 2x and throttled plant_targets even at v1b's already-working
#: scale; tuned against the working baseline instead of derived from first principles, so this
#: is deliberately approximate (see module docstring), not an exact schedule simulation.
_WATERING_DAYS_PER_TILE_PER_DAY = 0.5


def _capacity_limited_targets(snapshot: Snapshot, config: dict, raw_targets: dict[str, int]) -> dict[str, int]:
    """review.md C1/§1.3 + §5#2: the planner used to set plant_targets from config constants
    alone, with no notion of whether the fleet can actually keep that many tiles watered.
    Every target tile costs roughly (distance-from-shed-spawn + 1) unit-turns on the days it
    needs watering (units respawn at the shed every EOD, so this commute is a recurring cost,
    not a one-off) — if that total demand exceeds `safety_factor` of the day's unit-turn
    supply, trim target counts (never below what's already planted, since that watering
    obligation already exists) until it fits, instead of quietly setting up more plants than
    the day can water and losing them to `consecutive_unwatered` deaths (the v1c root cause,
    review.md §1).
    """
    scheduler_config = config["scheduler"]
    turns_per_day = config["runtime"]["turns_per_day"]
    spawn = SHED_ACCESS[0]
    num_units = 1 + len(snapshot.hand_positions)
    supply = num_units * turns_per_day
    safety_factor = float(config["planner"].get("capacity_safety_factor", 0.8))
    if supply <= 0:
        return dict(raw_targets)

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

    while sum(demand_for(crop, limits[crop]) for crop in limits) > safety_factor * supply:
        reducible = [crop for crop in limits if limits[crop] > floors[crop]]
        if not reducible:
            break
        crop = max(reducible, key=lambda c: limits[c])
        limits[crop] -= 1

    return limits


def make_day_plan(snapshot: Snapshot, config: dict) -> DayPlan:
    """Build the conservative v1a carrot plan."""
    planner_config = config["planner"]
    executor_config = config["executor"]
    if not planner_config.get("enabled", False):
        return DayPlan()

    # review.md L6: "enabled" used to be dead — liquidation fired unconditionally off
    # liquidation_day regardless of this flag's value. ablation.endgame_enabled=False
    # reproduces that v1b behavior (unconditional on liquidation_day) as a control: the flag
    # is already True by default, so it should be a no-op — a non-zero diff here would mean
    # the ablation infrastructure itself is broken, not that this flag matters.
    liquidation_active = (
        (config["endgame"].get("enabled", False) if config["ablation"]["endgame_enabled"] else True)
        and snapshot.day >= config["endgame"]["liquidation_day"]
    )
    phase = "LIQUIDATE" if liquidation_active else "GROW"
    carrot_target = 0 if phase == "LIQUIDATE" else int(planner_config["carrot_tiles"])
    strawberry_target = (
        int(planner_config["strawberry_tiles"])
        if phase != "LIQUIDATE" and snapshot.day <= planner_config["strawberry_last_plant_day"]
        else 0
    )
    raw_targets = {"CARROT": carrot_target, "STRAWBERRY": strawberry_target}
    plant_targets = (
        _capacity_limited_targets(snapshot, config, raw_targets)
        if config["ablation"]["capacity_gate"] else raw_targets
    )
    return DayPlan(
        plant_targets=plant_targets,
        hands_target=int(planner_config["hands_target"]),
        sell_floor_price=dict(executor_config["sell_floor_price"]),
        season_phase=phase,
        force_liquidation=phase == "LIQUIDATE",
    )
