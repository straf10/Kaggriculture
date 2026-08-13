#!/usr/bin/env python3
"""v1o.3 diagnostic — is the animal visit actually being *bundled*?

ROADMAP §4.3 S3 step 1b's whole economic argument is that finishing a visit in place is an
efficiency gain rather than a zero-sum re-tiering: the unit is already standing on the tile, so
the next op costs 1 turn instead of `2*distance + 1`. That claim is falsifiable, and this is what
falsifies it.

`harness.compare` aggregates `worker_turns_idle` and `worker_turns_total` but **not**
`worker_turns_moving`, so the commute share — the number the argument lives or dies on — is not
visible in any gate artefact. It is in `harness.metrics` per episode, and that is what this reads.

Two things are printed per arm:

  * the moving / working / idle split of every unit-turn. Bundling must move turns out of
    **moving** and into **working**. If moving does not fall, the bundle is not being taken and
    the implementation is wrong, not the idea.
  * the per-op count of the three tasks the tier ladder starves — CARE, animal HARVEST and
    COLLECT_FERTILIZER — recovered from the recorded action stream, next to the animal-side loss
    counters. This separates "the unit stayed" from "the unit stayed and the work got done".

Usage:
    .venv/Scripts/python.exe analysis/v1o3_visit_efficiency.py \
        --arms checkpoints/v1o3_a/main.py checkpoints/v1o_2/main.py \
        --opponent harness/bench_agents/meta_route.py --seeds 0 1 2 3
"""
from __future__ import annotations

import argparse
import gzip
import json
import statistics
import tempfile
import sys
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from harness.play import play  # noqa: E402

# The ops that only ever happen on an animal tile. FEED is deliberately excluded: it already sits
# at tier 0 and survives (8-25 escapes/ep), so it is not what this measures.
ANIMAL_OPS = ("CARE", "COLLECT_FERTILIZER")
# HARVEST is shared with crops, so it is counted separately and only where the tile carries an
# animal — see _count_ops.
_MOVES = {"NORTH", "SOUTH", "EAST", "WEST"}


def _count_ops(env_json: dict, seat: int) -> dict[str, int]:
    """Count executed ops from the recorded action stream, resolving HARVEST against the tile it
    was performed on so animal shearing/milking is not confused with crop harvesting.

    The step/action pairing mirrors harness/metrics.py exactly: the action recorded at
    `steps[i]` is the one produced from the observation at `steps[i-1]`, so positions and tiles
    must be read from the *previous* step.
    """
    counts: dict[str, int] = defaultdict(int)
    steps = env_json["steps"]
    for index in range(1, len(steps)):
        action = steps[index][seat].get("action")
        if not isinstance(action, dict):
            continue
        farm = steps[index - 1][seat]["observation"]["farms"][seat]
        positions = [tuple(farm.get("farmer", (0, 0))), *(tuple(p) for p in farm.get("hands", []))]
        unit_actions = [action.get("farmer", ["PASS"]), *(action.get("hands") or [])]
        unit_actions = unit_actions[:len(positions)]
        for unit_index, unit_action in enumerate(unit_actions):
            if not (isinstance(unit_action, list) and unit_action):
                continue
            op = unit_action[0]
            if op in _MOVES or op == "PASS":
                continue
            if op == "HARVEST":
                x, y = positions[unit_index]
                tile = farm["tiles"][y][x]
                counts["HARVEST_animal" if isinstance(tile, dict) and "animal" in tile
                       else "HARVEST_crop"] += 1
            elif op in ANIMAL_OPS:
                counts[op] += 1
    return counts


def run_arm(agent: str, opponent: str, seeds: list[int], run_dir: Path) -> dict:
    moving, working, idle, banks = [], [], [], []
    escaped, underfed, wool, fertilizer, milk = [], [], [], [], []
    ops: dict[str, list[int]] = defaultdict(list)
    for seed in seeds:
        for seat in (0, 1):
            pair = (agent, opponent) if seat == 0 else (opponent, agent)
            result = play(*pair, seed=seed, record=True, run_dir=run_dir, metrics=True)
            with gzip.open(result.replay_path, "rt", encoding="utf-8") as handle:
                env_json = json.load(handle)
            metrics = result.metrics[seat]
            total = metrics["worker_turns_total"] or 1
            moving.append(100.0 * metrics["worker_turns_moving"] / total)
            working.append(100.0 * metrics["worker_turns_working"] / total)
            idle.append(100.0 * metrics["worker_turns_idle"] / total)
            banks.append(result.rewards[seat])
            escaped.append(metrics["animals_escaped"])
            underfed.append(metrics["animals_underfed_days"])
            wool.append(metrics["units_sold_by_product"].get("WOOL", 0))
            fertilizer.append(metrics["units_sold_by_product"].get("FERTILIZER", 0))
            milk.append(metrics["units_sold_by_product"].get("MILK", 0))
            counted = _count_ops(env_json, seat)
            for name in ("CARE", "COLLECT_FERTILIZER", "HARVEST_animal", "HARVEST_crop"):
                ops[name].append(counted.get(name, 0))
    return {
        "bank": statistics.median(banks),
        "moving_pct": statistics.median(moving),
        "working_pct": statistics.median(working),
        "idle_pct": statistics.median(idle),
        "animals_escaped": sum(escaped),
        "animals_underfed_days": statistics.median(underfed),
        "WOOL_units": statistics.median(wool),
        "FERTILIZER_units": statistics.median(fertilizer),
        "MILK_units": statistics.median(milk),
        **{f"op_{name}": statistics.median(values) for name, values in ops.items()},
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--arms", nargs=2, required=True, metavar=("A", "B"))
    parser.add_argument("--opponent", default="harness/bench_agents/meta_route.py")
    parser.add_argument("--seeds", type=int, nargs="+", default=[0, 1, 2, 3])
    args = parser.parse_args()

    with tempfile.TemporaryDirectory(prefix="v1o3_visits_") as scratch:
        a = run_arm(args.arms[0], args.opponent, args.seeds, Path(scratch))
        b = run_arm(args.arms[1], args.opponent, args.seeds, Path(scratch))

    print(f"\nA = {args.arms[0]}\nB = {args.arms[1]}\nopponent = {args.opponent}\n"
          f"seeds = {args.seeds} x both seats (medians unless noted)\n")
    print(f"{'':<26} {'A':>10} {'B':>10} {'delta':>10}")
    for key in (
        "bank",
        "moving_pct", "working_pct", "idle_pct",
        "op_CARE", "op_HARVEST_animal", "op_COLLECT_FERTILIZER", "op_HARVEST_crop",
        "WOOL_units", "FERTILIZER_units", "MILK_units",
        "animals_escaped", "animals_underfed_days",
    ):
        print(f"{key:<26} {a[key]:>10.1f} {b[key]:>10.1f} {a[key] - b[key]:>+10.1f}")
    print("\n(animals_escaped is a sum over all runs, not a median.)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
