"""Submission policy glue."""
from dataclasses import dataclass, field

from .config import CONFIG
from .debug import emit_receipt
from .executor import market_orders
from .planner import DayPlan, make_day_plan
from .receipts import expected_transition, reconcile
from .scheduler import assign, build_tasks, make_ledger
from .state import Snapshot, parse


@dataclass
class RuntimeContext:
    last_step: int = -1
    planned_day: int = -1
    plan: DayPlan | None = None
    last_quadrants: tuple = ()
    last_hand_count: int = 0
    committed_tasks: dict = field(default_factory=dict)
    pending_receipts: list = field(default_factory=list)


_RUNTIME_BY_PLAYER: dict[int, RuntimeContext] = {}


def reset_or_get_runtime(snapshot: Snapshot) -> RuntimeContext:
    """Return a seat-local context and reset it at an episode boundary."""
    runtime = _RUNTIME_BY_PLAYER.get(snapshot.player)
    if runtime is None or snapshot.step == 0 or snapshot.step < runtime.last_step:
        runtime = RuntimeContext()
        _RUNTIME_BY_PLAYER[snapshot.player] = runtime
    runtime.last_step = snapshot.step
    return runtime


def _needs_replan(runtime: RuntimeContext, snapshot: Snapshot) -> bool:
    """review.md M4: plan.md §3.1 calls for a replan on the day boundary *or* when observed
    state diverges from the plan (e.g. a land purchase actually landing) — only the per-day
    trigger existed. `my_quadrants` changing mid-day is one such event v1b can already
    observe (BUY_LAND/animal purchases aren't wired into the executor yet). Hand count is
    another, and a load-bearing one: HIRE orders placed at hour 0 don't show up in
    `hand_positions` until hour 1 (hands are hired *this* turn's market step, hands[] only
    reflects it next observation), so the capacity gate in make_day_plan (review.md C1 §5#2)
    would otherwise plan the whole day around whatever unit count happened to be on the board
    at hour 0 — freshly wiped to 0 by end-of-day, before this turn's hires land."""
    return (
        runtime.plan is None
        or runtime.planned_day != snapshot.day
        or runtime.last_quadrants != snapshot.my_quadrants
        or runtime.last_hand_count != len(snapshot.hand_positions)
    )


def agent(obs):
    """Run the current planner → scheduler → executor policy."""
    snapshot = parse(obs)
    runtime = reset_or_get_runtime(snapshot)

    if CONFIG["guards"].get("debug", False) and runtime.pending_receipts:
        reconcile(runtime.pending_receipts, snapshot)
    runtime.pending_receipts = []

    if _needs_replan(runtime, snapshot):
        runtime.plan = make_day_plan(snapshot, CONFIG)
        runtime.planned_day = snapshot.day
    runtime.last_quadrants = snapshot.my_quadrants
    runtime.last_hand_count = len(snapshot.hand_positions)

    tasks = build_tasks(snapshot, runtime.plan, CONFIG)
    ledger = make_ledger(snapshot)
    farmer_action, hand_actions, commitments = assign(tasks, snapshot, runtime.committed_tasks, CONFIG)
    runtime.committed_tasks = commitments
    unit_actions = [farmer_action, *hand_actions]
    orders = market_orders(snapshot, runtime.plan, ledger, unit_actions, CONFIG)

    if CONFIG["guards"].get("debug", False):
        unit_positions = (snapshot.farmer_pos, *snapshot.hand_positions)
        for unit_index, action in enumerate(unit_actions):
            if action[:1] not in (["WATER"], ["PLANT"], ["HARVEST"]):
                continue
            receipt = expected_transition(unit_index, action, unit_positions[unit_index], snapshot, CONFIG)
            if receipt is not None:
                emit_receipt(receipt)
                runtime.pending_receipts.append(receipt)

    return {
        "farmer": farmer_action,
        "hands": hand_actions,
        "market": orders,
    }
