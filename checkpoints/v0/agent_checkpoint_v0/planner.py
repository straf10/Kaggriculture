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
    """Return the inert v0 plan."""
    del snapshot, config
    return DayPlan()
