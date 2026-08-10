"""Submission policy glue."""
from dataclasses import dataclass, field

from .config import CONFIG
from .debug import emit_receipt
from .executor import market_orders
from .planner import DayPlan, make_day_plan
from .receipts import expected_transition, reconcile
from .scheduler import assign, build_tasks, make_ledger
from .sell_ahead import OpponentSupplyTracker
from .state import Snapshot, parse


def _new_supply_tracker() -> OpponentSupplyTracker:
    return OpponentSupplyTracker(
        CONFIG["executor"].get("sell_ahead", {}).get("predict_horizon_turns", 6)
    )


@dataclass
class RuntimeContext:
    last_step: int = -1
    planned_day: int = -1
    plan: DayPlan | None = None
    last_quadrants: tuple = ()
    last_hand_count: int = 0
    committed_tasks: dict = field(default_factory=dict)
    pending_receipts: list = field(default_factory=list)
    # current_phase.md §v1i Η2. Lives here, not module-global, for the same reason the rest of
    # RuntimeContext does: the tracker is seat-local and must reset at an episode boundary,
    # or a second episode in the same process would start with the first one's history (G13).
    supply_tracker: OpponentSupplyTracker = field(default_factory=_new_supply_tracker)


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
    """review_89d99f0_2026-08-05.md M4: plan.md §3.1 calls for a replan on the day boundary *or* when observed
    state diverges from the plan (e.g. a land purchase actually landing) — only the per-day
    trigger existed. `my_quadrants` changing mid-day is one such event v1b can already
    observe (BUY_LAND/animal purchases aren't wired into the executor yet). Hand count is
    another, and a load-bearing one: HIRE orders placed at hour 0 don't show up in
    `hand_positions` until hour 1 (hands are hired *this* turn's market step, hands[] only
    reflects it next observation), so the capacity gate in make_day_plan (review_89d99f0_2026-08-05.md C1 §5#2)
    would otherwise plan the whole day around whatever unit count happened to be on the board
    at hour 0 — freshly wiped to 0 by end-of-day, before this turn's hires land."""
    return (
        runtime.plan is None
        or runtime.planned_day != snapshot.day
        or runtime.last_quadrants != snapshot.my_quadrants
        or runtime.last_hand_count != len(snapshot.hand_positions)
    )


def agent(obs, configuration=None):
    """Run the current planner → scheduler → executor policy.

    review.md M3: kaggle_environments' Agent.act() inspects __code__.co_argcount and, for a
    2-arg agent function, calls agent(observation, configuration) — this second parameter is
    how farmHandCostMult reaches the agent at all. Keep it optional so direct unit-style
    calls (agent(obs)) still work."""
    snapshot = parse(obs)
    runtime = reset_or_get_runtime(snapshot)
    farm_hand_cost_mult = int((configuration or {}).get("farmHandCostMult", 1))
    # §v1i Η2: fold this turn's inventory move into the opponent-supply history *before*
    # anything reads a prediction, so the estimate always includes the freshest observation.
    runtime.supply_tracker.observe(snapshot, configuration)

    if CONFIG["guards"].get("debug", False) and runtime.pending_receipts:
        reconcile(runtime.pending_receipts, snapshot)
    runtime.pending_receipts = []

    if _needs_replan(runtime, snapshot):
        # v1g.2: `configuration` also carries the town's sell intervals, which is what lets
        # agent.demand compute NPC demand exactly instead of assuming the 1.32.5 defaults —
        # and, in particular, what makes the sell floors follow the announced
        # townCenterSellInterval 12 -> 24 change on their own (current_phase.md §0bis).
        runtime.plan = make_day_plan(snapshot, CONFIG, configuration)
        runtime.planned_day = snapshot.day
    runtime.last_quadrants = snapshot.my_quadrants
    runtime.last_hand_count = len(snapshot.hand_positions)

    tasks = build_tasks(snapshot, runtime.plan, CONFIG)
    ledger = make_ledger(snapshot)
    farmer_action, hand_actions, commitments = assign(tasks, snapshot, runtime.committed_tasks, CONFIG)
    runtime.committed_tasks = commitments
    unit_actions = [farmer_action, *hand_actions]
    orders = market_orders(
        snapshot, runtime.plan, ledger, unit_actions, CONFIG,
        farm_hand_cost_mult=farm_hand_cost_mult,
        supply_tracker=runtime.supply_tracker,
    )
    runtime.supply_tracker.record_our_orders(orders)

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
