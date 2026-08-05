"""Layer 1 economic planner."""
from dataclasses import dataclass, field

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


def make_day_plan(snapshot: Snapshot, config: dict) -> DayPlan:
    """Build the conservative v1a carrot plan."""
    planner_config = config["planner"]
    executor_config = config["executor"]
    if not planner_config.get("enabled", False):
        return DayPlan()

    phase = "LIQUIDATE" if snapshot.day >= config["endgame"]["liquidation_day"] else "GROW"
    carrot_target = 0 if phase == "LIQUIDATE" else int(planner_config["carrot_tiles"])
    return DayPlan(
        plant_targets={"CARROT": carrot_target},
        sell_floor_price=dict(executor_config["sell_floor_price"]),
        season_phase=phase,
        force_liquidation=phase == "LIQUIDATE",
    )
