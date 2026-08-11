#!/usr/bin/env python3
"""v1o.1 diagnostic — where does the extra crop revenue go?

The v1o.1 smoke screen measured crop tile-days +25%..+49% and crop revenue +61%..+70% while
final bank went from +$603 (INCONCLUSIVE) to -$7.913 (REGRESSED). Something is eating the gain.
This prints the per-product units/revenue/$-per-unit split for two agents on the same seeds and
the same opponent, which is the only way to tell "the extra strawberry crashed its own price"
apart from "the extra watering starved the animals".

Usage:
    .venv/Scripts/python.exe analysis/v1o1_product_split.py \
        --arms runs/v1o1_screen/sb12/main.py checkpoints/v1i/main.py \
        --opponent harness/bench_agents/meta_route.py --seeds 0 1 2 3
"""
from __future__ import annotations

import argparse
import statistics
import sys
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from harness.play import play  # noqa: E402

PRODUCTS = ("STRAWBERRY", "CARROT", "WHEAT", "MELON", "MILK", "WOOL", "FERTILIZER", "EGG")


def run_arm(agent: str, opponent: str, seeds: list[int]) -> dict:
    units: dict[str, list[int]] = defaultdict(list)
    revenue: dict[str, list[int]] = defaultdict(list)
    banks, tile_days, idle_pct, escaped, underfed = [], [], [], [], []
    for seed in seeds:
        for seat in (0, 1):
            pair = (agent, opponent) if seat == 0 else (opponent, agent)
            result = play(*pair, seed=seed, record=False, metrics=True)
            m = result.metrics[seat]
            for product in PRODUCTS:
                units[product].append(m["units_sold_by_product"].get(product, 0))
                revenue[product].append(m["revenue_by_product"].get(product, 0))
            banks.append(result.rewards[seat])
            tile_days.append(m["crop_tile_days"])
            total = m["worker_turns_total"] or 1
            idle_pct.append(100.0 * m["worker_turns_idle"] / total)
            escaped.append(m["animals_escaped"])
            underfed.append(m["animals_underfed_days"])
    return {
        "bank": statistics.median(banks),
        "crop_tile_days": statistics.median(tile_days),
        "idle_pct": statistics.median(idle_pct),
        "animals_escaped": sum(escaped),
        "animals_underfed_days": statistics.median(underfed),
        "units": {p: statistics.median(units[p]) for p in PRODUCTS},
        "revenue": {p: statistics.median(revenue[p]) for p in PRODUCTS},
        "revenue_mean": {p: statistics.mean(revenue[p]) for p in PRODUCTS},
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--arms", nargs=2, required=True, metavar=("A", "B"))
    parser.add_argument("--opponent", default="harness/bench_agents/meta_route.py")
    parser.add_argument("--seeds", type=int, nargs="+", default=[0, 1, 2, 3])
    args = parser.parse_args()

    a = run_arm(args.arms[0], args.opponent, args.seeds)
    b = run_arm(args.arms[1], args.opponent, args.seeds)

    print(f"\nA = {args.arms[0]}\nB = {args.arms[1]}\nopponent = {args.opponent}\n"
          f"seeds = {args.seeds} x both seats\n")
    print(f"{'':<12} {'A units':>8} {'B units':>8} {'A $/u':>8} {'B $/u':>8} "
          f"{'A rev':>9} {'B rev':>9} {'Δ rev':>9}")
    total_a = total_b = 0
    for product in PRODUCTS:
        ua, ub = a["units"][product], b["units"][product]
        ra, rb = a["revenue_mean"][product], b["revenue_mean"][product]
        total_a += ra
        total_b += rb
        print(f"{product:<12} {ua:>8.0f} {ub:>8.0f} "
              f"{(ra / ua if ua else 0):>8.1f} {(rb / ub if ub else 0):>8.1f} "
              f"{ra:>9.0f} {rb:>9.0f} {ra - rb:>+9.0f}")
    print(f"{'TOTAL':<12} {'':>8} {'':>8} {'':>8} {'':>8} "
          f"{total_a:>9.0f} {total_b:>9.0f} {total_a - total_b:>+9.0f}")
    print()
    for key in ("bank", "crop_tile_days", "idle_pct", "animals_escaped", "animals_underfed_days"):
        print(f"{key:<24} A={a[key]:>10.1f}  B={b[key]:>10.1f}  Δ={a[key] - b[key]:>+10.1f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
