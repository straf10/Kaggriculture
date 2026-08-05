"""Submission policy glue."""
from dataclasses import dataclass

from .config import CONFIG
from .executor import market_orders
from .planner import DayPlan, make_day_plan
from .scheduler import assign, build_tasks, make_ledger
from .state import Snapshot, parse


@dataclass
class RuntimeContext:
    last_step: int = -1
    planned_day: int = -1
    plan: DayPlan | None = None


_RUNTIME_BY_PLAYER: dict[int, RuntimeContext] = {}


def reset_or_get_runtime(snapshot: Snapshot) -> RuntimeContext:
    """Return a seat-local context and reset it at an episode boundary."""
    runtime = _RUNTIME_BY_PLAYER.get(snapshot.player)
    if runtime is None or snapshot.step == 0 or snapshot.step < runtime.last_step:
        runtime = RuntimeContext()
        _RUNTIME_BY_PLAYER[snapshot.player] = runtime
    runtime.last_step = snapshot.step
    return runtime


def agent(obs):
    """Run the current planner → scheduler → executor policy."""
    snapshot = parse(obs)
    runtime = reset_or_get_runtime(snapshot)
    if runtime.plan is None or runtime.planned_day != snapshot.day:
        runtime.plan = make_day_plan(snapshot, CONFIG)
        runtime.planned_day = snapshot.day

    tasks = build_tasks(snapshot, runtime.plan, CONFIG)
    ledger = make_ledger(snapshot)
    farmer_action, hand_actions = assign(tasks, snapshot)
    unit_actions = [farmer_action, *hand_actions]
    orders = market_orders(snapshot, runtime.plan, ledger, unit_actions, CONFIG)
    return {
        "farmer": farmer_action,
        "hands": hand_actions,
        "market": orders,
    }
