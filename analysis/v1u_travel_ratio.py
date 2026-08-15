#!/usr/bin/env python3
"""v1u — the travel-ratio (greedy-regret) diagnostic for deferred item ④.

ROADMAP §4.3 deferred item ③ / `docs/plans/item4_min_cost_assignment.md` step 1. Answers, before
any matching rewrite is built: **of the unit-turns we spend moving rather than working, how many
are walks a better *matching* could have avoided (regret), and how many are geometrically forced
(the floor)?**

`agent/scheduler.py:assign()` is a greedy one-at-a-time matcher with a known 2×-optimal worst
case. This script measures the *achievable* travel it leaves on the table, per turn, by comparing
its assignment against the min-cost bipartite matching a legal item-④ (Hungarian, per priority
tier) would compute over the *same* candidate set under the *same* hard constraints (G-1…G-6).

METHOD (full pre-registration in `baselines/2026-08-15/item4_step1_report.md`):

  * The candidate set is captured **at the source**: `agent.policy.assign` is wrapped with a
    transparent recorder in this process only, and our agent runs as an in-process callable. The
    wrapper returns the real `assign()` result unchanged (behaviour byte-identical) and computes
    the regret inline from the live `(tasks, snapshot, committed)` triple. Wrapping the *policy*
    binding, not the *scheduler* one, leaves every opponent untouched.
  * `_greedy_trace()` re-implements the greedy loop and records each committed pair's distance; its
    output is asserted equal to the real `assign()` every turn (void-on-mismatch guard, R18-style).
  * `_optimal_assignment()` pins `committed` first (G-2), then matches **per priority tier, highest
    first** (G-1 is structural, never a cost term), with cargo (G-4), `allowed_unit`, position
    exclusivity (G-6) and seeds (G-5) enforced as constraints, via scipy `linear_sum_assignment`.
  * Regret = Σ distance(greedy) − Σ distance(optimal). Pinning committed identically in both makes
    ongoing walks cancel, so regret accrues only at commitment turns — it books each committed walk
    once, and is directly comparable to `worker_turns_moving`. See report §2.4 for the caveats this
    measurement states rather than hides.

This is offline analysis: it is allowed to be slow, and it uses scipy. It changes no `agent/` code
and makes no submission. Engine must be 1.32.7 (D28); `gates/` replays (1.32.6, and carrying no
candidate set) are deliberately **not** pooled — see report §2.5.

Usage:
    .venv/bin/python analysis/v1u_travel_ratio.py --seeds 0 1 2 3 4 5 \
        --out data/derived/v1u_travel_ratio-2026-08-15.json
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
import tempfile
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from scipy.optimize import linear_sum_assignment

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

import agent.policy as policy  # noqa: E402
from agent import scheduler as sched  # noqa: E402
from agent.config import CONFIG  # noqa: E402
from harness.play import play  # noqa: E402

_REAL_ASSIGN = sched.assign

# Cost sentinel for the matchings. distances on a 10×10 board are ≤ 18, so an ineligible pair at
# 1e6 is never chosen while any real (≤18) or idle (a small constant, set locally) option exists —
# the solver completes as many *legal* tasks as it can before idling a unit, never buying a distance
# saving by leaving legal work undone (the ROADMAP §3.4 anti-pattern).
_INELIGIBLE_COST = 1e6


def _manhattan(a: tuple[int, int], b: tuple[int, int]) -> int:
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def _carries_cargo(snapshot, unit_index: int, task) -> bool:
    """G-4, mirroring assign()'s inner `_carries_cargo`: FEED needs WHEAT in *that* unit's
    inventory, PLACE needs the animal; everything else is unconditionally eligible."""
    inv = snapshot.inventories[unit_index] if unit_index < len(snapshot.inventories) else {}
    if task.kind == "FEED":
        return inv.get("WHEAT", 0) > 0
    if task.kind == "PLACE":
        return inv.get(task.item, 0) > 0
    return True


# --------------------------------------------------------------------------------------------
# Greedy reconstruction — a line-for-line copy of scheduler.assign()'s loop that additionally
# records, per committed pair, (unit_index, task, distance, switching). Its actions/commitments
# are asserted equal to the real assign() every turn.
# --------------------------------------------------------------------------------------------
@dataclass
class _GreedyResult:
    farmer: list
    hands: list
    commitments: dict
    assignments: list  # (unit_index, task, distance, switching)


def _greedy_trace(tasks, snapshot, committed, config) -> _GreedyResult:
    committed = committed or {}
    unit_positions = [snapshot.farmer_pos, *snapshot.hand_positions]
    actions = [["PASS"] for _ in unit_positions]
    remaining_tasks = list(tasks)
    unassigned_units = set(range(len(unit_positions)))
    seeds_remaining = dict(snapshot.seeds)
    new_commitments: dict[int, str] = {}
    assignments: list = []
    zones = sched._zone_partition(tasks, snapshot, config, committed)

    def carries_cargo(unit_index: int, task) -> bool:
        return _carries_cargo(snapshot, unit_index, task)

    def carries_wheat(unit_index: int) -> bool:
        inv = snapshot.inventories[unit_index] if unit_index < len(snapshot.inventories) else {}
        return inv.get("WHEAT", 0) > 0

    while remaining_tasks and unassigned_units:
        candidates = []
        for task in remaining_tasks:
            eligible_units = [
                unit_index
                for unit_index in unassigned_units
                if (task.allowed_unit is None or task.allowed_unit == unit_index)
                and carries_cargo(unit_index, task)
            ]
            if zones and task.allowed_unit is None:
                task_zone = sched._tile_quadrant(task.pos)
                zoned_units = [
                    unit_index for unit_index in eligible_units
                    if zones.get(unit_index) == task_zone or carries_wheat(unit_index)
                ]
                if zoned_units:
                    eligible_units = zoned_units
            if not eligible_units:
                continue
            best_distance = min(
                _manhattan(unit_positions[u], task.pos) for u in eligible_units
            )
            slack = task.deadline_step - snapshot.step - (best_distance + 1)
            urgent = slack <= config["scheduler"]["urgency_slack_margin"]
            urgency_tier = 0 if urgent else 1
            task_slack = slack if urgent else 0
            for unit_index in eligible_units:
                unit_pos = unit_positions[unit_index]
                if (
                    task.kind == "PLANT"
                    and unit_pos == task.pos
                    and seeds_remaining.get(task.item, 0) <= 0
                ):
                    continue
                distance = _manhattan(unit_pos, task.pos)
                switching = 0 if committed.get(unit_index) == task.id else 1
                candidates.append((
                    (
                        task.priority, switching, urgency_tier, task_slack,
                        distance, task.pos[1], task.pos[0], unit_index, task.id,
                    ),
                    task,
                ))
        if not candidates:
            break

        sort_key, task = min(candidates, key=lambda candidate: candidate[0])
        unit_index = sort_key[-2]
        distance = sort_key[4]
        switching = sort_key[1]
        assignments.append((unit_index, task, distance, switching))
        unit_pos = unit_positions[unit_index]
        if unit_pos != task.pos:
            actions[unit_index] = sched._move_toward(unit_pos, task.pos)
            new_commitments[unit_index] = task.id
        elif task.kind in {"PLANT", "PLACE"}:
            actions[unit_index] = [task.kind, task.item]
            if task.kind == "PLANT":
                seeds_remaining[task.item] -= 1
        elif task.kind == "PICKUP":
            actions[unit_index] = [task.kind, task.item, task.count]
        else:
            actions[unit_index] = [task.kind]

        unassigned_units.remove(unit_index)
        remaining_tasks = [
            candidate for candidate in remaining_tasks
            if (
                candidate.id != task.id
                if candidate.allowed_unit is not None
                else candidate.pos != task.pos
            )
        ]

    return _GreedyResult(actions[0], actions[1:], new_commitments, assignments)


# --------------------------------------------------------------------------------------------
# Optimal baseline — PRIMARY (decision-driving): the "re-match" frame.
#
# Hold the served task set fixed to exactly what greedy served this turn (same work, same
# deadlines met/missed, same priorities), pin the pairs a legal item-④ must not move — committed
# (G-2) and allowed_unit — and re-match only the *free* units to their *free* served positions to
# minimise total travel. This isolates pure matching inefficiency: it is provably ≥ 0 (greedy's
# own assignment is a feasible re-matching, so the optimum can only be ≤ it), it cannot shrink the
# denominator (§3.4 — the set of completed tasks is held constant), and it cannot buy distance by
# missing a deadline or down-tiering a priority (the two ways §2.3/the brief warn of), because it
# never changes *which* task is done, only *which unit* does it.
#
# What it deliberately does NOT credit: item ④ completing *more* tasks than greedy per turn
# (a cardinality gain). That is measured separately and reported as a secondary signal, because
# the extra tasks cost travel too and their episode-level value is step 2's job, not this pass's.
# --------------------------------------------------------------------------------------------
def _rematch_optimal(greedy_assignments, snapshot, committed) -> float:
    """Total travel of the min-distance re-matching of greedy's own served set (see header)."""
    committed = committed or {}
    unit_positions = [snapshot.farmer_pos, *snapshot.hand_positions]
    pinned_travel = 0.0
    free_units: list = []
    free_tasks: list = []
    for (u, task, dist, _sw) in greedy_assignments:
        pinned = task.allowed_unit is not None or committed.get(u) == task.id
        if pinned:
            pinned_travel += dist
        else:
            free_units.append(u)
            free_tasks.append(task)

    n = len(free_units)
    if n == 0:
        return pinned_travel

    cost = np.full((n, n), _INELIGIBLE_COST, dtype=float)
    for i, u in enumerate(free_units):
        for j, task in enumerate(free_tasks):
            if _carries_cargo(snapshot, u, task):
                cost[i, j] = _manhattan(unit_positions[u], task.pos)
    row_ind, col_ind = linear_sum_assignment(cost)
    free_travel = float(sum(cost[r, c] for r, c in zip(row_ind, col_ind)))
    # Greedy's own matching is feasible, so an ineligible-forced optimum is impossible.
    assert free_travel < _INELIGIBLE_COST, "re-match infeasible — greedy's own matching should bound it"
    return pinned_travel + free_travel


# --------------------------------------------------------------------------------------------
# Secondary: does a max-cardinality matching (per priority tier, highest first, honouring the
# hard constraints only) complete tasks greedy stranded? Counts only — distance-independent, so
# no urgency/slack question arises. Used for the cardinality-gap signal, never for the decision.
# --------------------------------------------------------------------------------------------
def _max_cardinality(tasks, snapshot, committed) -> int:
    committed = committed or {}
    unit_positions = [snapshot.farmer_pos, *snapshot.hand_positions]
    available = set(range(len(unit_positions)))
    tasks_by_id = {t.id: t for t in tasks}
    served_positions: set = set()
    served_ids: set = set()
    count = 0

    def is_live(task) -> bool:
        if task.id in served_ids:
            return False
        if task.allowed_unit is None and task.pos in served_positions:
            return False
        return True

    def mark_served(task) -> None:
        (served_ids if task.allowed_unit is not None else served_positions).add(
            task.id if task.allowed_unit is not None else task.pos)

    for u in sorted(committed):  # pin committed (G-2)
        if u not in available:
            continue
        task = tasks_by_id.get(committed[u])
        if task is None or not is_live(task):
            continue
        if task.allowed_unit is not None and task.allowed_unit != u:
            continue
        if not _carries_cargo(snapshot, u, task):
            continue
        count += 1
        available.discard(u)
        mark_served(task)

    live = [t for t in tasks if is_live(t)]
    for prio in sorted({t.priority for t in live}):
        if not available:
            break
        tier = [t for t in live if t.priority == prio and is_live(t)]
        nodes: list = []
        pos_group: dict = defaultdict(list)
        for t in tier:
            if t.allowed_unit is not None:
                if t.allowed_unit in available and _carries_cargo(snapshot, t.allowed_unit, t):
                    nodes.append(({t.allowed_unit}, t))
            else:
                pos_group[t.pos].append(t)
        for pos, ts in pos_group.items():
            elig = {u for u in available for t in ts if _carries_cargo(snapshot, u, t)}
            if elig:
                nodes.append((elig, min(ts, key=lambda t: t.id)))
        if not nodes:
            continue
        avail_list = sorted(available)
        n_r, n_c = len(avail_list), len(nodes)
        # eligible real edges cost 0, idle 1, ineligible large -> min-cost maximises real matches.
        cost = np.full((n_r, n_c + n_r), 1.0, dtype=float)
        for ci, (elig, _rep) in enumerate(nodes):
            for ri, u in enumerate(avail_list):
                cost[ri, ci] = 0.0 if u in elig else _INELIGIBLE_COST
        row_ind, col_ind = linear_sum_assignment(cost)
        for ri, ci in zip(row_ind, col_ind):
            if ci >= n_c or cost[ri, ci] >= _INELIGIBLE_COST:
                continue
            u = avail_list[ri]
            _elig, rep = nodes[ci]
            count += 1
            available.discard(u)
            mark_served(rep)
        live = [t for t in live if is_live(t)]
    return count


# --------------------------------------------------------------------------------------------
# Per-turn recorder + episode driver.
# --------------------------------------------------------------------------------------------
@dataclass
class _Turn:
    day: int
    step: int
    seat: int
    feed_open: bool
    n_units: int
    greedy_travel: float
    optimal_travel: float
    greedy_decision_travel: float   # Σ distance over switching==1 (fresh commitments)
    regret: float                   # greedy_travel − optimal_travel
    k_greedy: int
    k_optimal: int


_CAPTURE: list = []            # active episode's turns
_SEAT_UNDER_TEST: dict = {"seat": None}
_VOID: dict = {"reason": None}


def _wrapped_assign(tasks, snapshot, committed=None, config=CONFIG):
    committed = committed or {}
    real = _REAL_ASSIGN(tasks, snapshot, committed, config)

    # Only record the agent-under-test's own calls (the opponent never routes through
    # agent.policy.assign, but guard on the seat anyway).
    if snapshot.player != _SEAT_UNDER_TEST["seat"]:
        return real

    trace = _greedy_trace(tasks, snapshot, committed, config)
    if (trace.farmer, trace.hands, trace.commitments) != real:
        _VOID["reason"] = (
            f"greedy reconstruction diverged from assign() at step {snapshot.step} "
            f"seat {snapshot.player}"
        )
        return real

    greedy_travel = sum(d for _, _, d, _ in trace.assignments)
    optimal_travel = _rematch_optimal(trace.assignments, snapshot, committed)
    decision_travel = sum(d for _, _, d, sw in trace.assignments if sw == 1)
    _CAPTURE.append(_Turn(
        day=snapshot.day, step=snapshot.step, seat=snapshot.player,
        feed_open=any(t.kind == "FEED" for t in tasks),
        n_units=len(snapshot.hand_positions) + 1,
        greedy_travel=greedy_travel, optimal_travel=optimal_travel,
        greedy_decision_travel=decision_travel,
        regret=greedy_travel - optimal_travel,
        k_greedy=len(trace.assignments),
        k_optimal=_max_cardinality(tasks, snapshot, committed),
    ))
    return real


def _run_episode(our_agent, opponent, seed: int, seat: int, run_dir: Path) -> dict:
    """One episode with our agent at `seat`. Returns the aggregated capture + real moving turns."""
    global _CAPTURE
    _CAPTURE = []
    _SEAT_UNDER_TEST["seat"] = seat
    _VOID["reason"] = None
    pair = (our_agent, opponent) if seat == 0 else (opponent, our_agent)
    result = play(*pair, seed=seed, record=False, run_dir=run_dir, metrics=True)
    if _VOID["reason"]:
        raise RuntimeError(f"MEASUREMENT VOID (seed {seed}, seat {seat}): {_VOID['reason']}")
    metrics = result.metrics[seat]
    return {
        "turns": list(_CAPTURE),
        "moving_turns": int(metrics["worker_turns_moving"]),
        "working_turns": int(metrics["worker_turns_working"]),
        "idle_turns": int(metrics["worker_turns_idle"]),
        "total_turns": int(metrics["worker_turns_total"]),
        "bank": result.rewards[seat],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seeds", type=int, nargs="+", default=[0, 1, 2, 3, 4, 5])
    parser.add_argument("--opponents", nargs="+", default=[
        "harness/bench_agents/meta_route.py",
        "harness/bench_agents/meta_route_sheep.py",
        "checkpoints/v1o_2/main.py",
    ])
    parser.add_argument("--town-pin", default="basket")
    parser.add_argument("--out", default="data/derived/v1u_travel_ratio-2026-08-15.json")
    args = parser.parse_args()

    # Install the recorder on the policy binding only (opponents keep the original scheduler one).
    policy.assign = _wrapped_assign
    our_agent = policy.agent

    from harness.town_pin import pinned_town, schedule_for_mode  # noqa: E402

    all_turns: list = []
    moving_total = working_total = idle_total = worker_total = 0
    episodes_meta: list = []

    with tempfile.TemporaryDirectory(prefix="v1u_") as scratch:
        run_dir = Path(scratch)
        for opponent in args.opponents:
            for seed in args.seeds:
                schedule = schedule_for_mode(args.town_pin, seed) if args.town_pin else None
                for seat in (0, 1):
                    with pinned_town(args.town_pin, schedule):
                        ep = _run_episode(our_agent, opponent, seed, seat, run_dir)
                    all_turns.extend(ep["turns"])
                    moving_total += ep["moving_turns"]
                    working_total += ep["working_turns"]
                    idle_total += ep["idle_turns"]
                    worker_total += ep["total_turns"]
                    episodes_meta.append({
                        "opponent": Path(opponent).stem, "seed": seed, "seat": seat,
                        "moving_turns": ep["moving_turns"],
                        "working_turns": ep["working_turns"],
                        "bank": ep["bank"],
                        "n_turns": len(ep["turns"]),
                    })
                    print(f"  {Path(opponent).stem:<18} seed {seed} seat {seat}: "
                          f"{len(ep['turns'])} turns, moving={ep['moving_turns']}, "
                          f"working={ep['working_turns']}")

    # ---- Aggregate ----
    regret_total = sum(t.regret for t in all_turns)
    greedy_travel_total = sum(t.greedy_travel for t in all_turns)
    optimal_travel_total = sum(t.optimal_travel for t in all_turns)
    decision_travel_total = sum(t.greedy_decision_travel for t in all_turns)
    card_gap_total = sum(t.k_optimal - t.k_greedy for t in all_turns)
    card_gap_turns = sum(1 for t in all_turns if t.k_optimal != t.k_greedy)

    regret_pct_of_moving = 100.0 * regret_total / moving_total if moving_total else 0.0
    # Forced-walk floor on the *decision* travel (the non-cancelling part): the fraction of the
    # commute a perfect matcher still pays. optimal_decision = greedy_decision − regret.
    optimal_decision_travel = decision_travel_total - regret_total
    floor = (optimal_decision_travel / decision_travel_total) if decision_travel_total else 1.0

    # Distribution: by feed-round-open, by season half, by day.
    def _bucket(pred):
        turns = [t for t in all_turns if pred(t)]
        return {
            "n_turns": len(turns),
            "regret": round(sum(t.regret for t in turns), 1),
            "greedy_decision_travel": round(sum(t.greedy_decision_travel for t in turns), 1),
        }

    by_feed = {
        "feed_open": _bucket(lambda t: t.feed_open),
        "feed_closed": _bucket(lambda t: not t.feed_open),
    }
    by_season = {
        "early_day_le_15": _bucket(lambda t: t.day <= 15),
        "late_day_gt_15": _bucket(lambda t: t.day > 15),
    }
    by_day = {}
    for day in sorted({t.day for t in all_turns}):
        by_day[day] = _bucket(lambda t, d=day: t.day == d)

    # Regret concentration: what share of total regret sits in the worst 5% of turns?
    regrets_sorted = sorted((t.regret for t in all_turns), reverse=True)
    top5 = regrets_sorted[:max(1, len(regrets_sorted) // 20)]
    conc_top5_pct = 100.0 * sum(top5) / regret_total if regret_total else 0.0

    decision = (
        "PROCEED to step 2 (whole task pool)" if regret_pct_of_moving >= 8
        else "PROCEED but re-scope ④ to the feed round only" if regret_pct_of_moving >= 3
        else "STOP item ④ — commute is a geometric floor, not a matching loss"
    )

    out = {
        "engine": "1.32.7",
        "seeds": args.seeds,
        "opponents": [Path(o).stem for o in args.opponents],
        "town_pin": args.town_pin,
        "n_episodes": len(episodes_meta),
        "n_turns_captured": len(all_turns),
        "worker_turns": {
            "moving": moving_total, "working": working_total,
            "idle": idle_total, "total": worker_total,
        },
        "regret_total_walk_steps": round(regret_total, 1),
        "greedy_travel_total": round(greedy_travel_total, 1),
        "optimal_travel_total": round(optimal_travel_total, 1),
        "greedy_decision_travel_total": round(decision_travel_total, 1),
        "decision_travel_vs_moving_ratio": round(
            decision_travel_total / moving_total, 4) if moving_total else None,
        "DECISION_METRIC_regret_pct_of_moving_turns": round(regret_pct_of_moving, 3),
        "forced_walk_floor_optimal_over_greedy_decision": round(floor, 4),
        "regret_concentration_top5pct_turns": round(conc_top5_pct, 1),
        "cardinality_gap_total_tasks": card_gap_total,
        "cardinality_gap_turns": card_gap_turns,
        "distribution": {"by_feed": by_feed, "by_season": by_season, "by_day": by_day},
        "episodes": episodes_meta,
        "DECISION": decision,
        "thresholds": {"proceed_ge": 8.0, "rescope_feed_3_to_8": [3.0, 8.0], "stop_lt": 3.0},
    }

    out_path = Path(args.out)
    if not out_path.is_absolute():
        out_path = REPO / out_path
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, indent=2), encoding="utf-8")

    # ---- Print ----
    print("\n" + "=" * 74)
    print(f"episodes            {len(episodes_meta)}  ({len(args.seeds)} seeds × 2 seats × "
          f"{len(args.opponents)} opponents)")
    print(f"turns captured      {len(all_turns)}")
    print(f"worker turns        moving={moving_total}  working={working_total}  idle={idle_total}")
    print(f"greedy decision travel {decision_travel_total:.0f}  vs moving turns {moving_total}  "
          f"(ratio {out['decision_travel_vs_moving_ratio']})")
    print(f"regret (walk-steps) {regret_total:.1f}")
    print(f"forced-walk floor   optimal/greedy decision travel = {floor:.4f}  "
          f"(⇒ ≤ {(1-floor)*100:.1f}% is the ceiling ④ can return)")
    print(f"regret concentration top-5% turns hold {conc_top5_pct:.1f}% of all regret")
    print(f"cardinality gap     {card_gap_total} tasks over {card_gap_turns} turns")
    print("-" * 74)
    print(f"feed-open   regret {by_feed['feed_open']['regret']:>9}  "
          f"decision-travel {by_feed['feed_open']['greedy_decision_travel']:>9}")
    print(f"feed-closed regret {by_feed['feed_closed']['regret']:>9}  "
          f"decision-travel {by_feed['feed_closed']['greedy_decision_travel']:>9}")
    print("-" * 74)
    print(f">>> DECISION METRIC: regret = {regret_pct_of_moving:.3f}% of moving turns")
    print(f">>> {decision}")
    print("=" * 74)
    try:
        shown = out_path.relative_to(REPO)
    except ValueError:
        shown = out_path
    print(f"\nwrote {shown}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
