"""Layer 2 deterministic task scheduler."""
from dataclasses import dataclass, field

from .planner import DayPlan
from .state import Snapshot


@dataclass(frozen=True)
class Task:
    id: str
    kind: str
    pos: tuple[int, int]
    priority: int
    item: str | None = None
    count: int = 1
    deadline_step: int = 719
    prerequisites: tuple[str, ...] = ()
    required_inventory: dict[str, int] = field(default_factory=dict)
    reservation_key: str | None = None


@dataclass
class ResourceLedger:
    seeds: dict[str, int]
    unit_inventory: list[dict]
    shed_free: int
    money: float
    market_slots: int = 10


def build_tasks(snapshot: Snapshot, plan: DayPlan) -> list[Task]:
    """Return no tasks for v0."""
    del snapshot, plan
    return []


def make_ledger(snapshot: Snapshot) -> ResourceLedger:
    shed_used = sum(snapshot.shed.values())
    return ResourceLedger(
        seeds=dict(snapshot.seeds),
        unit_inventory=[dict(inv) for inv in snapshot.inventories],
        shed_free=max(0, 100 - shed_used),
        money=snapshot.money,
    )


def assign(tasks: list[Task], snapshot: Snapshot) -> tuple[list[str], list[list[str]]]:
    """Return index-aligned PASS actions for every current unit."""
    del tasks
    return ["PASS"], [["PASS"] for _ in snapshot.hand_positions]
