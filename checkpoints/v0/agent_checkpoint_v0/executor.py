"""Layer 3 market-order executor."""
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
    """Return no market orders for v0."""
    del snapshot, plan, ledger, scheduled_unit_actions, config
    return []
