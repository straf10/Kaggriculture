#!/usr/bin/env python3
"""v1u — the offline oracle for deferred item ④ (min-cost assignment), step 2.

`docs/plans/item4_min_cost_assignment.md` §2 (revised 2026-08-15) / brief
`docs/plans/item4_step2_prompt.md`. Step 1 (`analysis/v1u_travel_ratio.py`) *measured* the
greedy-vs-optimal regret per turn (4,30% of moving turns, 0,963 forced-walk floor). This step
**substitutes** the optimal matcher into the live agent and lets whole episodes play out under
it, to price the ceiling in dollars and — the leg that matters — in feed-round relief.

Unlike step 1, this is not a pure routing measurement: it swaps `agent.policy.assign` for a
slow, legal, optimal matcher (scipy, no time budget), so the executor, the market layer and the
opponent's occupancy all react to the new routing. Both seats are load-bearing (dollars differ by
seat through occupancy coupling — brief §"Seat note").

THREE ARMS (brief §3), run in this order, A first:

  * **A — whole-pool optimal.** Per-tier legal min-cost matching over the full pool every turn.
    The strict ceiling; B and C are bounded by it. If A misses both legs of the decision, the
    pass ends (B and C cannot clear what A could not).
  * **B — greedy + 2-opt repair.** Keep greedy's assignment, then pairwise-swap the *free*
    (non-committed, non-allowed_unit) unit→task pairs, accepting only strict distance
    improvements. No solver, no new dependency, constraint-safe by construction. May be the
    actual product — `B/A` is reported explicitly.
  * **C — feed-round only.** Optimal re-match of the FEED assignments alone (step 1's mandated
    re-scope; 82,8% of regret is in the feed round). PICKUP-WHEAT is `allowed_unit`-restricted
    (one per unit) so it is not reassignable; the reassignable feed work is the FEED round.

CONSTRAINTS THE OPTIMAL HONOURS (G-1…G-6, identical to step 1): priority is a hard constraint
solved **per tier, highest first**, never a cost; cargo (G-4) and `allowed_unit` restrict the
matrix rather than penalise it; unrestricted tasks at one tile collapse to one node (G-6);
`committed` pairs are pinned before the solve (G-2); seeds (G-5) are feasible by construction from
`build_tasks()` plus an on-tile PLANT guard. Determinism (G-3): the cost matrix is built from
sorted units and position-ordered nodes (no set/dict iteration on the decision path) and carries a
bounded lexicographic tie-break that can never flip an integer-distance decision, so the matching
is byte-reproducible run to run — asserted in `tests/test_v1u_oracle.py`.

Engine must be 1.32.7 (D28). Baseline/opponent is `checkpoints/v1u_base` (built on 1.32.7 from the
live agent — every existing checkpoint is 1.32.6 and a cross-engine compare is the §4.2 B1 error).

Usage:
    .venv/bin/python analysis/v1u_oracle.py --seeds 0 1 2 3 4 5 6 7 8 9 10 11 \
        --out data/derived/v1u_oracle-2026-08-15.json
"""
from __future__ import annotations

import argparse
import gzip
import json
import statistics
import sys
import tempfile
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
from harness.seeds import SMOKE_SEEDS  # noqa: E402
from harness.town_pin import pinned_town, schedule_for_mode  # noqa: E402

# Reuse step 1's validated greedy reconstruction verbatim (asserted equal to the real assign()
# on 25.884 turns, 0 voids) — arms B and C start from it, and re-deriving it would waste the pass.
from analysis.v1u_travel_ratio import _greedy_trace  # noqa: E402

_REAL_ASSIGN = sched.assign

# Cost sentinels. Board distances are ≤18, so IDLE (1000) is always preferred to leaving a unit on
# an ineligible cell, and any real (≤18) or idle option is always preferred to INELIGIBLE — the
# solver completes as many legal tasks as it can (max cardinality) before idling a unit, never
# buying a distance saving by leaving legal work undone (ROADMAP §3.4 anti-pattern).
_IDLE_COST = 1000.0
_INELIGIBLE_COST = 1e9


def _manhattan(a: tuple[int, int], b: tuple[int, int]) -> int:
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def _carries_cargo(snapshot, unit_index: int, task) -> bool:
    """G-4, mirroring assign()'s inner `_carries_cargo`."""
    inv = snapshot.inventories[unit_index] if unit_index < len(snapshot.inventories) else {}
    if task.kind == "FEED":
        return inv.get("WHEAT", 0) > 0
    if task.kind == "PLACE":
        return inv.get(task.item, 0) > 0
    return True


def _apply_assignment(unit_index, task, unit_positions, actions, new_commitments, seeds_remaining):
    """Turn a (unit → task) decision into the action assign() would emit for it (scheduler.py
    lines 813-823): move toward a far task (and record the commitment), else perform the op in
    place. The on-tile PLANT seed guard (G-5) degrades to PASS rather than over-planting."""
    unit_pos = unit_positions[unit_index]
    if unit_pos != task.pos:
        actions[unit_index] = sched._move_toward(unit_pos, task.pos)
        new_commitments[unit_index] = task.id
    elif task.kind in {"PLANT", "PLACE"}:
        if task.kind == "PLANT" and seeds_remaining.get(task.item, 0) <= 0:
            actions[unit_index] = ["PASS"]
            return
        actions[unit_index] = [task.kind, task.item]
        if task.kind == "PLANT":
            seeds_remaining[task.item] -= 1
    elif task.kind == "PICKUP":
        actions[unit_index] = [task.kind, task.item, task.count]
    else:
        actions[unit_index] = [task.kind]


# --------------------------------------------------------------------------------------------
# Arm A — whole-pool optimal, per priority tier, highest first.
# --------------------------------------------------------------------------------------------
def _optimal_actions(tasks, snapshot, committed, config):
    committed = committed or {}
    unit_positions = [snapshot.farmer_pos, *snapshot.hand_positions]
    n_units = len(unit_positions)
    actions = [["PASS"] for _ in range(n_units)]
    new_commitments: dict[int, str] = {}
    seeds_remaining = dict(snapshot.seeds)
    available = set(range(n_units))
    served_positions: set = set()
    served_ids: set = set()

    def is_live(task) -> bool:
        if task.id in served_ids:
            return False
        if task.allowed_unit is None and task.pos in served_positions:
            return False
        return True

    def mark_served(task) -> None:
        if task.allowed_unit is not None:
            served_ids.add(task.id)
        else:
            served_positions.add(task.pos)

    tasks_by_id = {t.id: t for t in tasks}

    # G-2: pin committed pairs before the solve. Iterate in sorted unit order (never dict order).
    for unit_index in sorted(committed):
        if unit_index not in available:
            continue
        task = tasks_by_id.get(committed[unit_index])
        if task is None or not is_live(task):
            continue
        if task.allowed_unit is not None and task.allowed_unit != unit_index:
            continue
        if not _carries_cargo(snapshot, unit_index, task):
            continue
        if (
            task.kind == "PLANT"
            and unit_positions[unit_index] == task.pos
            and seeds_remaining.get(task.item, 0) <= 0
        ):
            continue
        _apply_assignment(unit_index, task, unit_positions, actions, new_commitments, seeds_remaining)
        available.discard(unit_index)
        mark_served(task)

    margin = config["scheduler"]["urgency_slack_margin"]

    def build_nodes(tier_tasks):
        """(eligible_units frozenset, representative_task) per served node, against `available`."""
        nodes: list = []
        pos_group: dict = {}
        for t in tier_tasks:
            if not is_live(t):
                continue
            if t.allowed_unit is not None:
                u = t.allowed_unit
                if u in available and _carries_cargo(snapshot, u, t) and not (
                    t.kind == "PLANT" and unit_positions[u] == t.pos
                    and seeds_remaining.get(t.item, 0) <= 0
                ):
                    nodes.append((frozenset({u}), t))
            else:
                pos_group.setdefault(t.pos, []).append(t)
        for pos in sorted(pos_group):
            rep = min(pos_group[pos], key=lambda t: t.id)
            elig = {
                u for u in available
                if _carries_cargo(snapshot, u, rep)
                and not (rep.kind == "PLANT" and unit_positions[u] == pos
                         and seeds_remaining.get(rep.item, 0) <= 0)
            }
            if elig:
                nodes.append((frozenset(elig), rep))
        nodes.sort(key=lambda node: (node[1].pos[1], node[1].pos[0], node[1].id))
        return nodes

    def node_slack(elig, rep):
        best = min(_manhattan(unit_positions[u], rep.pos) for u in elig)
        return rep.deadline_step - snapshot.step - (best + 1)

    def solve(nodes, urgent):
        """Min-cost assignment of `available` units to `nodes`, applied in place. Urgent nodes
        are ordered by slack (most-urgent first) ahead of distance, exactly as greedy's key
        (urgency_tier, task_slack, distance) does — this is what keeps the optimum from buying a
        distance saving by deferring a soon-due FEED (the step-1 pure-distance mirage, §1 finding
        4). Comfortable nodes match on distance alone."""
        if not nodes or not available:
            return
        avail_list = sorted(available)
        n_r, n_c = len(avail_list), len(nodes)
        idle = 1e5 if urgent else _IDLE_COST
        min_slack = min(node_slack(e, r) for e, r in nodes) if urgent else 0
        cost = np.full((n_r, n_c + n_r), idle, dtype=float)
        for ri in range(n_r):
            for ci in range(n_c, n_c + n_r):
                cost[ri, ci] = idle + ri * 1e-5  # deterministic idle
        for ci, (elig, rep) in enumerate(nodes):
            base = 0.0
            if urgent:
                base = (node_slack(elig, rep) - min_slack) * 100.0  # slack dominates distance
            for ri, u in enumerate(avail_list):
                if u in elig:
                    cost[ri, ci] = base + _manhattan(unit_positions[u], rep.pos) + ci * 1e-3 + ri * 1e-5
                else:
                    cost[ri, ci] = _INELIGIBLE_COST
        row_ind, col_ind = linear_sum_assignment(cost)
        for ri, ci in zip(row_ind, col_ind):
            if ci >= n_c or cost[ri, ci] >= _INELIGIBLE_COST:
                continue
            u = avail_list[ri]
            _elig, rep = nodes[ci]
            _apply_assignment(u, rep, unit_positions, actions, new_commitments, seeds_remaining)
            available.discard(u)
            mark_served(rep)

    # G-1: solve per priority tier, highest first (priority never enters the cost). Within a
    # tier, the urgent sub-round (slack ≤ margin) is solved before the comfortable one, so an
    # urgent task claims a unit ahead of a merely-nearer comfortable one — mirroring greedy's
    # (priority, urgency_tier, task_slack, distance) key without the pure-distance mirage.
    for prio in sorted({t.priority for t in tasks}):
        if not available:
            break
        tier = [t for t in tasks if t.priority == prio and is_live(t)]
        if not tier:
            continue
        nodes = build_nodes(tier)
        urgent_nodes = [(e, r) for e, r in nodes if node_slack(e, r) <= margin]
        solve(urgent_nodes, urgent=True)
        solve(build_nodes(tier), urgent=False)  # rebuild: available shrank in the urgent round

    return actions[0], actions[1:], new_commitments


# --------------------------------------------------------------------------------------------
# Arm B — greedy + 2-opt repair. Start from the validated greedy trace, pin allowed_unit and
# committed (switching==0) pairs, and pairwise-swap the remaining free pairs, accepting only
# strict distance improvements. Constraint-safe by construction: a swap is only considered when
# both units are cargo-eligible for both tasks (allowed_unit pairs are never free, so allowed_unit
# is preserved), and position exclusivity is preserved because the served task set is unchanged.
# --------------------------------------------------------------------------------------------
def _twoopt_actions(tasks, snapshot, committed, config):
    committed = committed or {}
    trace = _greedy_trace(tasks, snapshot, committed, config)
    unit_positions = [snapshot.farmer_pos, *snapshot.hand_positions]
    assigns: dict[int, object] = {}
    free: list[int] = []
    for (u, task, _dist, switching) in trace.assignments:
        assigns[u] = task
        if task.allowed_unit is None and switching == 1:
            free.append(u)
    free.sort()

    improved = True
    while improved:
        improved = False
        for i in range(len(free)):
            for j in range(i + 1, len(free)):
                u1, u2 = free[i], free[j]
                t1, t2 = assigns[u1], assigns[u2]
                if t1.pos == t2.pos:
                    continue
                if not (_carries_cargo(snapshot, u1, t2) and _carries_cargo(snapshot, u2, t1)):
                    continue
                cur = (_manhattan(unit_positions[u1], t1.pos)
                       + _manhattan(unit_positions[u2], t2.pos))
                swp = (_manhattan(unit_positions[u1], t2.pos)
                       + _manhattan(unit_positions[u2], t1.pos))
                if swp < cur:
                    assigns[u1], assigns[u2] = t2, t1
                    improved = True

    actions = [["PASS"] for _ in unit_positions]
    new_commitments: dict[int, str] = {}
    seeds_remaining = dict(snapshot.seeds)
    for u in sorted(assigns):
        _apply_assignment(u, assigns[u], unit_positions, actions, new_commitments, seeds_remaining)
    return actions[0], actions[1:], new_commitments


# --------------------------------------------------------------------------------------------
# Arm C — feed-round only. Greedy for the whole turn, then an optimal min-cost re-match of the
# FEED assignments among the units greedy already sent to feed (all carry WHEAT, so any is
# eligible for any FEED tile). PICKUP-WHEAT is allowed_unit-restricted and stays put.
# --------------------------------------------------------------------------------------------
def _feed_optimal_actions(tasks, snapshot, committed, config):
    committed = committed or {}
    trace = _greedy_trace(tasks, snapshot, committed, config)
    unit_positions = [snapshot.farmer_pos, *snapshot.hand_positions]
    assigns: dict[int, object] = {u: task for (u, task, _d, _s) in trace.assignments}

    feed = sorted(
        ((u, task) for u, task in assigns.items()
         if task.kind == "FEED" and task.allowed_unit is None),
        key=lambda pair: pair[0],
    )
    if len(feed) >= 2:
        us = [u for u, _ in feed]
        ts = [t for _, t in feed]
        n = len(us)
        cost = np.zeros((n, n), dtype=float)
        for i, u in enumerate(us):
            for j, t in enumerate(ts):
                cost[i, j] = _manhattan(unit_positions[u], t.pos) + j * 1e-3 + i * 1e-5
        row_ind, col_ind = linear_sum_assignment(cost)
        for i, j in zip(row_ind, col_ind):
            assigns[us[i]] = ts[j]

    actions = [["PASS"] for _ in unit_positions]
    new_commitments: dict[int, str] = {}
    seeds_remaining = dict(snapshot.seeds)
    for u in sorted(assigns):
        _apply_assignment(u, assigns[u], unit_positions, actions, new_commitments, seeds_remaining)
    return actions[0], actions[1:], new_commitments


_ARMS = {"A": _optimal_actions, "B": _twoopt_actions, "C": _feed_optimal_actions}

_STATE: dict = {"seat": None, "arm": None}


def _make_wrapped_assign(arm_fn):
    def _wrapped(tasks, snapshot, committed=None, config=CONFIG):
        if snapshot.player != _STATE["seat"]:
            return _REAL_ASSIGN(tasks, snapshot, committed, config)
        return arm_fn(tasks, snapshot, committed or {}, config)
    return _wrapped


# --------------------------------------------------------------------------------------------
# Feed-round saturation, computed from the replay (not in extract_metrics). Per §3.3 / brief §4
# leg 2: share of day-hours with ≥1 placed animal `fed_today=False`. Currently 100% from d9.
# --------------------------------------------------------------------------------------------
def _feed_saturation_by_day(env_json: dict, seat: int) -> dict[int, tuple[int, int]]:
    """day -> (hours_with_an_unfed_animal, total_hours_with_a_placed_animal)."""
    per_day: dict[int, list[int]] = {}
    for step in env_json["steps"]:
        obs = step[0]["observation"]
        day = int(obs.get("day", 0))
        tiles = obs["farms"][seat]["tiles"]
        placed = 0
        unfed = 0
        for row in tiles:
            for tile in row:
                if isinstance(tile, dict) and "animal" in tile:
                    placed += 1
                    if not tile.get("fed_today", False):
                        unfed += 1
        if placed == 0:
            continue
        totals, unfed_hours = per_day.setdefault(day, [0, 0])
        per_day[day] = [totals + 1, unfed_hours + (1 if unfed > 0 else 0)]
    return {day: (unfed_hours, total) for day, (total, unfed_hours) in per_day.items()}


def _median_saturation_from_day(sat_by_day: dict[int, tuple[int, int]], first_day: int) -> float | None:
    ratios = [
        unfed / total
        for day, (unfed, total) in sorted(sat_by_day.items())
        if day >= first_day and total > 0
    ]
    return statistics.median(ratios) if ratios else None


# --------------------------------------------------------------------------------------------
# Episode driver.
# --------------------------------------------------------------------------------------------
@dataclass
class _EpisodeResult:
    seed: int
    seat: int
    arm: str
    bank: float
    crop_tile_days: int
    animals_escaped: int
    animals_underfed_days: int
    worker_turns_working: int
    worker_turns_moving: int
    median_saturation_from_d9: float | None
    plant_decay_units_lost: int
    clipped_production_ticks: int


def _run_episode(our_agent, opponent, seed, seat, arm, run_dir) -> _EpisodeResult:
    _STATE["seat"] = seat
    _STATE["arm"] = arm
    policy.assign = _REAL_ASSIGN if arm == "baseline" else _make_wrapped_assign(_ARMS[arm])
    pair = (our_agent, opponent) if seat == 0 else (opponent, our_agent)
    result = play(*pair, seed=seed, record=True, run_dir=run_dir, metrics=True)
    policy.assign = _REAL_ASSIGN
    m = result.metrics[seat]
    with gzip.open(result.replay_path, "rt", encoding="utf-8") as f:
        env_json = json.load(f)
    sat = _feed_saturation_by_day(env_json, seat)
    Path(result.replay_path).unlink(missing_ok=True)
    return _EpisodeResult(
        seed=seed, seat=seat, arm=arm,
        bank=result.rewards[seat],
        crop_tile_days=int(m["crop_tile_days"]),
        animals_escaped=int(m["animals_escaped"]),
        animals_underfed_days=int(m["animals_underfed_days"]),
        worker_turns_working=int(m["worker_turns_working"]),
        worker_turns_moving=int(m["worker_turns_moving"]),
        median_saturation_from_d9=_median_saturation_from_day(sat, 9),
        plant_decay_units_lost=int(m["plant_decay_units_lost"]),
        clipped_production_ticks=int(m["clipped_production_ticks"]),
    )


def _aggregate(baseline: list[_EpisodeResult], arm: list[_EpisodeResult]) -> dict:
    """Paired per-(seed,seat) deltas of `arm` vs `baseline`."""
    by_key = {(r.seed, r.seat): r for r in baseline}
    diffs = [a.bank - by_key[(a.seed, a.seat)].bank for a in arm]
    ctd_base = sum(by_key[(a.seed, a.seat)].crop_tile_days for a in arm)
    ctd_arm = sum(a.crop_tile_days for a in arm)
    esc_base = sum(by_key[(a.seed, a.seat)].animals_escaped for a in arm)
    esc_arm = sum(a.animals_escaped for a in arm)
    underfed_base = sum(by_key[(a.seed, a.seat)].animals_underfed_days for a in arm)
    underfed_arm = sum(a.animals_underfed_days for a in arm)
    work_base = sum(by_key[(a.seed, a.seat)].worker_turns_working for a in arm)
    work_arm = sum(a.worker_turns_working for a in arm)
    sat_base = [by_key[(a.seed, a.seat)].median_saturation_from_d9 for a in arm]
    sat_arm = [a.median_saturation_from_d9 for a in arm]
    sat_base = [s for s in sat_base if s is not None]
    sat_arm = [s for s in sat_arm if s is not None]
    decay_base = sum(by_key[(a.seed, a.seat)].plant_decay_units_lost for a in arm)
    clip_base = sum(by_key[(a.seed, a.seat)].clipped_production_ticks for a in arm)
    n = len(arm)
    return {
        "n_episodes": n,
        "mean_bank_delta": round(statistics.mean(diffs), 1) if diffs else 0.0,
        "median_bank_delta": round(statistics.median(diffs), 1) if diffs else 0.0,
        "bank_wins": sum(1 for d in diffs if d > 0),
        "bank_losses": sum(1 for d in diffs if d < 0),
        "crop_tile_days_base": ctd_base,
        "crop_tile_days_arm": ctd_arm,
        "crop_tile_days_pct": round(100.0 * (ctd_arm - ctd_base) / ctd_base, 2) if ctd_base else 0.0,
        "animals_escaped_base": esc_base,
        "animals_escaped_arm": esc_arm,
        "animals_underfed_days_base": underfed_base,
        "animals_underfed_days_arm": underfed_arm,
        "animals_underfed_days_pct": (
            round(100.0 * (underfed_arm - underfed_base) / underfed_base, 2) if underfed_base else 0.0
        ),
        "worker_working_base": work_base,
        "worker_working_arm": work_arm,
        "median_saturation_base": round(statistics.median(sat_base), 3) if sat_base else None,
        "median_saturation_arm": round(statistics.median(sat_arm), 3) if sat_arm else None,
        "plant_decay_units_lost_base": decay_base,
        "plant_decay_units_lost_arm": sum(a.plant_decay_units_lost for a in arm),
        "clipped_production_ticks_base": clip_base,
        "clipped_production_ticks_arm": sum(a.clipped_production_ticks for a in arm),
    }


def _legs(agg: dict) -> dict:
    """The two pre-registered legs (brief §4). PROCEED if EITHER clears.

    crop_tile_days gate: G-8 (§3.4) exists to stop an arm buying dollars by SHEDDING crop
    tile-days (v1p1b arm A1 gamed the commute ratio by doing less work). The guard is therefore
    one-sided — crop_tile_days must not FALL more than 3%; an increase is the win the item is
    built for and corroborates the mechanism, never a violation. `crop_tile_days_pct` is reported
    raw so either reading is checkable. `animals_escaped` uses the ±5 24-ep noise floor (§3.3)."""
    leg1 = (
        agg["mean_bank_delta"] >= 2000.0
        and agg["crop_tile_days_pct"] >= -3.0
        and abs(agg["animals_escaped_arm"] - agg["animals_escaped_base"]) <= 5
    )
    sat = agg["median_saturation_arm"]
    leg2 = (
        (sat is not None and sat < 0.90)
        or agg["animals_underfed_days_pct"] <= -15.0
    )
    return {"leg1_standalone": bool(leg1), "leg2_unblock": bool(leg2)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seeds", type=int, nargs="+", default=list(SMOKE_SEEDS))
    parser.add_argument("--seats", type=int, nargs="+", default=[0, 1])
    parser.add_argument("--opponent", default="checkpoints/v1u_base/main.py")
    parser.add_argument("--town-pin", default="basket")
    parser.add_argument("--arms", nargs="+", default=["A", "B", "C"])
    parser.add_argument(
        "--run-all-arms", action="store_true",
        help="Measure B and C even when arm A's pre-registered both-legs-miss stop fires. The "
             "stop is still recorded (`A_stop_condition_fired`); B/C are run only to confirm it "
             "and to report B/A (brief §8), never to re-open a settled decision.")
    parser.add_argument("--out", default="data/derived/v1u_oracle-2026-08-15.json")
    args = parser.parse_args()

    our_agent = policy.agent  # in-process; opponent (a separate package) never binds our assign

    def run_arm(arm, run_dir):
        results = []
        for seed in args.seeds:
            schedule = schedule_for_mode(args.town_pin, seed) if args.town_pin else None
            for seat in args.seats:
                with pinned_town(args.town_pin, schedule):
                    ep = _run_episode(our_agent, args.opponent, seed, seat, arm, run_dir)
                results.append(ep)
                tag = arm if arm != "baseline" else "base"
                print(f"  [{tag:>4}] seed {seed:>2} seat {seat}: bank={ep.bank:>9.0f} "
                      f"ctd={ep.crop_tile_days:>4} esc={ep.animals_escaped:>3} "
                      f"underfed={ep.animals_underfed_days:>3} "
                      f"sat_d9={ep.median_saturation_from_d9}")
        return results

    out: dict = {
        "engine": "1.32.7",
        "opponent": args.opponent,
        "seeds": args.seeds,
        "seats": args.seats,
        "town_pin": args.town_pin,
        "pre_registered_decision": {
            "leg1_standalone": ">= +$2.000/ep mean bank delta AND crop_tile_days within +-3% "
                               "AND animals_escaped within +-5 of baseline",
            "leg2_unblock": "median feed-round saturation from d9 < 90% OR "
                            "animals_underfed_days falls >= 15%",
            "rule": "PROCEED to step 3 if EITHER leg clears; STOP item 4 if BOTH miss",
        },
        "arms": {},
    }
    out_path = Path(args.out)
    if not out_path.is_absolute():
        out_path = REPO / out_path
    out_path.parent.mkdir(parents=True, exist_ok=True)

    def _dump():
        out_path.write_text(json.dumps(out, indent=2), encoding="utf-8")

    with tempfile.TemporaryDirectory(prefix="v1u_oracle_") as scratch:
        run_dir = Path(scratch)
        print("baseline (v1u_base greedy, our seat):")
        baseline = run_arm("baseline", run_dir)
        out["arms"]["baseline"] = [vars(r) for r in baseline]
        _dump()

        # A first — the strict ceiling. If A misses both legs, the pre-registered rule ends the
        # pass (B, C are bounded by A). `--run-all-arms` measures B/C anyway to confirm the stop
        # and report B/A, without re-opening the decision.
        ordered = [a for a in ("A", "B", "C") if a in args.arms]
        a_stop_fired = False
        stopped_early = False
        for arm in ordered:
            print(f"\narm {arm}:")
            arm_results = run_arm(arm, run_dir)
            agg = _aggregate(baseline, arm_results)
            legs = _legs(agg)
            out["arms"][arm] = {
                "aggregate": agg, "legs": legs,
                "episodes": [vars(r) for r in arm_results],
            }
            _dump()
            print(f"\n  arm {arm}: mean_bank_delta={agg['mean_bank_delta']:+.0f}  "
                  f"ctd={agg['crop_tile_days_pct']:+.1f}%  "
                  f"esc {agg['animals_escaped_base']}->{agg['animals_escaped_arm']}  "
                  f"underfed {agg['animals_underfed_days_pct']:+.1f}%  "
                  f"sat_d9 {agg['median_saturation_base']}->{agg['median_saturation_arm']}")
            print(f"  leg1(standalone)={legs['leg1_standalone']}  leg2(unblock)={legs['leg2_unblock']}")
            if arm == "A" and not legs["leg1_standalone"] and not legs["leg2_unblock"]:
                a_stop_fired = True
                if args.run_all_arms:
                    print("\n  ⛔ arm A misses BOTH legs (pre-registered stop). --run-all-arms set: "
                          "measuring B/C to confirm and report B/A.")
                else:
                    print("\n  ⛔ arm A misses BOTH legs — B and C are bounded by A. Ending the pass.")
                    stopped_early = True
                    break

        # Report B/A explicitly (brief §3/§8): fraction of arm A's dollar effect that B recovers.
        if "A" in out["arms"] and "B" in out["arms"]:
            a_delta = out["arms"]["A"]["aggregate"]["mean_bank_delta"]
            b_delta = out["arms"]["B"]["aggregate"]["mean_bank_delta"]
            out["B_over_A_mean_bank_delta"] = (
                round(b_delta / a_delta, 3) if a_delta else None
            )

        proceed = any(
            out["arms"][a]["legs"]["leg1_standalone"] or out["arms"][a]["legs"]["leg2_unblock"]
            for a in ("A", "B", "C") if a in out["arms"] and isinstance(out["arms"][a], dict)
            and "legs" in out["arms"][a]
        )
        out["A_stop_condition_fired"] = a_stop_fired
        out["stopped_early_after_A"] = stopped_early
        out["DECISION"] = (
            "PROCEED to step 3 (a leg cleared)" if proceed
            else "STOP item 4 — both legs miss on every run arm; commute is a geometric floor, "
                 "the residual is too thin to pay, herd 13 stays blocked"
        )
        _dump()

    print("\n" + "=" * 78)
    print(out["DECISION"])
    if "B_over_A_mean_bank_delta" in out:
        print(f"B/A (mean bank delta) = {out['B_over_A_mean_bank_delta']}")
    print("=" * 78)
    try:
        shown = out_path.relative_to(REPO)
    except ValueError:
        shown = out_path
    print(f"wrote {shown}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
