"""v1n Ρ1 — fertilizer capture diagnostic (docs/data only, no new episodes, no agent change).

current_phase.md §v1n asks one question before any increment is written: the fertilizer line is
our second largest revenue line ($13,685/ep, ~163 units) against a ceiling of ~260 units — is the
missing ~100 units *structural* (the herd is placed gradually over days 0-8, so the earliest
animal-days simply do not exist) or *fixable* (fertilizer that was available and never collected
on busy days)? If structural dominates there is no increment and §v1n closes as measured.

Mechanics, verified against engine_reference/kaggriculture.py:
  - :818  `tile["fertilizer_available"] = True` runs in `_end_of_day` for every animal tile that
          survived the night, unconditionally and *after* the escape `continue`. It is a boolean,
          not a counter: a unit not collected that day is overwritten, never accumulated.
  - :502  `COLLECT_FERTILIZER` consumes the flag and adds exactly one unit.
  - :226  a freshly placed animal starts with `fertilizer_available = False`, so a tile placed on
          day d first offers fertilizer on day d+1.

So the true per-episode ceiling is the number of *animal-days that were actually stood up*, and
the fixable gap is that number minus the collects actually emitted. Both are measured here from
the 34 tracked v1h.2d ladder replays — same aggregate-only pattern as analysis/l1_*, l2_*.

Usage: python analysis/v1n_r1_fertilizer.py
"""
from __future__ import annotations

import json
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from harness.metrics import extract_metrics  # noqa: E402

OUR = "STRAF"
TURNS_PER_DAY = 24
ROOT = Path("baselines/2026-08-10/replays_v1h2d")
OUT = Path("gates/v1n_r1_diagnostic/diagnosis.json")

# agent/config.py:231 sell_floor_price and the engine's FERTILIZER curve (kaggriculture.py:50):
# base 100, T 200, linear below_target/above_target 0.40 => amp = 0.40 * 100 / 200 = 0.2, so
# price(delta) = 100 - 0.2 * delta and the floor of $10 first binds at delta = 450 units.
SELL_FLOOR_PRICE = 10
FERTILIZER_FLOOR_DELTA = (100 - SELL_FLOOR_PRICE) / 0.2

# The herd the gated v1h.2d config actually places (config targets COW 4 / SHEEP 6 / GOOSE 0).
HERD_TARGET = 10


def _animal_coords(tiles) -> set:
    return {
        (x, y)
        for y, row in enumerate(tiles)
        for x, tile in enumerate(row)
        if isinstance(tile, dict) and "animal" in tile
    }


def _collect_ops(step_entry) -> int:
    """COLLECT_FERTILIZER ops emitted by one seat on one turn (farmer + every hand)."""
    action = step_entry.get("action") or {}
    ops = [action.get("farmer") or ["PASS"], *(action.get("hands") or [])]
    return sum(1 for op in ops if op and op[0] == "COLLECT_FERTILIZER")


def episode_row(replay: dict, seat: int) -> dict:
    steps = replay["steps"]
    n_days = len(steps) // TURNS_PER_DAY

    eod_coords = []
    sod_coords = []
    for day in range(n_days):
        eod = min(day * TURNS_PER_DAY + TURNS_PER_DAY - 1, len(steps) - 1)
        sod = min(day * TURNS_PER_DAY, len(steps) - 1)
        tiles_eod = steps[eod][0]["observation"]["farms"][seat]["tiles"]
        tiles_sod = steps[sod][0]["observation"]["farms"][seat]["tiles"]
        eod_coords.append(_animal_coords(tiles_eod))
        sod_coords.append(_animal_coords(tiles_sod))

    # A unit is offered on day d only for a tile that held a surviving animal at the end of day
    # d-1 and still holds one on day d. Day 0 offers nothing: every animal is placed that day or
    # later, and placement starts the flag at False.
    offered_by_day = [0]
    for day in range(1, n_days):
        offered_by_day.append(len(eod_coords[day - 1] & sod_coords[day]))
    offered = sum(offered_by_day)

    collects_by_day = []
    for day in range(n_days):
        start = day * TURNS_PER_DAY
        end = min(start + TURNS_PER_DAY, len(steps))
        collects_by_day.append(
            sum(_collect_ops(steps[t][seat]) for t in range(start, end))
        )
    collects = sum(collects_by_day)

    metrics = extract_metrics(replay, seat)
    units_sold = metrics["units_sold_by_product"].get("FERTILIZER", 0)
    revenue = metrics["revenue_by_product"].get("FERTILIZER", 0)
    prices = [s["price"] for s in metrics["market_sales"] if s["item"] == "FERTILIZER"]

    # Sell-side exclusion: the shared market inventory the floor would have to reach, and what
    # was left unsold in our own shed at the end of the season.
    market_fertilizer = [
        int(steps[t][0]["observation"]["market"]["inventory"].get("FERTILIZER", 0))
        for t in range(0, len(steps), TURNS_PER_DAY)
    ]
    final_private = steps[-1][seat]["observation"].get("private") or {}
    shed_left = int((final_private.get("shed") or {}).get("FERTILIZER", 0))

    return {
        "days": n_days,
        "animals_eod_final": len(eod_coords[-1]),
        "animals_peak": max(len(c) for c in eod_coords),
        "first_full_herd_day": next(
            (d for d, c in enumerate(eod_coords) if len(c) >= HERD_TARGET), None
        ),
        "naive_ceiling": HERD_TARGET * (n_days - 1),
        "offered_animal_days": offered,
        "collect_actions": collects,
        "collects_late_season": sum(collects_by_day[max(0, n_days - 10):]),
        "units_sold": units_sold,
        "fertilizer_revenue": revenue,
        "min_price": min(prices) if prices else None,
        "max_market_inventory": max(market_fertilizer) if market_fertilizer else 0,
        "shed_left_at_end": shed_left,
        "offered_by_day": offered_by_day,
        "collects_by_day": collects_by_day,
    }


def median(values):
    values = [v for v in values if v is not None]
    return statistics.median(values) if values else 0


def main() -> None:
    rows = []
    for path in sorted(ROOT.glob("episode-*-replay.json")):
        replay = json.load(open(path, encoding="utf-8"))
        teams = replay["info"].get("TeamNames") or []
        if OUR not in teams:
            continue
        rows.append(episode_row(replay, teams.index(OUR)))

    n = len(rows)
    print(f"parsed {n} episodes from {ROOT}\n")

    naive = median([r["naive_ceiling"] for r in rows])
    offered = median([r["offered_animal_days"] for r in rows])
    collects = median([r["collect_actions"] for r in rows])
    sold = median([r["units_sold"] for r in rows])
    revenue = median([r["fertilizer_revenue"] for r in rows])

    structural_gap = naive - offered
    fixable_gap = offered - collects
    sell_gap = collects - sold

    print(f"{'quantity':<42} {'median/ep':>10}")
    print(f"{'-' * 53}")
    print(f"{'naive ceiling (10 animals x days-1)':<42} {naive:>10.1f}")
    print(f"{'offered animal-days (really stood up)':<42} {offered:>10.1f}")
    print(f"{'COLLECT_FERTILIZER actions emitted':<42} {collects:>10.1f}")
    print(f"{'FERTILIZER units sold':<42} {sold:>10.1f}")
    print(f"{'FERTILIZER revenue':<42} {revenue:>10.0f}")
    print()
    print(f"{'STRUCTURAL gap (herd ramp d0-d8)':<42} {structural_gap:>10.1f}"
          f"   {100 * structural_gap / max(1, naive - collects):>5.1f}% of total gap")
    print(f"{'FIXABLE gap (offered but not collected)':<42} {fixable_gap:>10.1f}"
          f"   {100 * fixable_gap / max(1, naive - collects):>5.1f}% of total gap")
    print(f"{'SELL-SIDE gap (collected but not sold)':<42} {sell_gap:>10.1f}")
    print()
    print(f"first day the full herd of {HERD_TARGET} stands: "
          f"median day {median([r['first_full_herd_day'] for r in rows])}")
    print(f"peak animals: median {median([r['animals_peak'] for r in rows])}")
    print()
    print("sell-side exclusion (current_phase.md v1n R1 point 3):")
    print(f"  sell_floor_price[FERTILIZER]={SELL_FLOOR_PRICE} first binds at "
          f"delta={FERTILIZER_FLOOR_DELTA:.0f} units")
    print(f"  max shared market FERTILIZER inventory seen: median "
          f"{median([r['max_market_inventory'] for r in rows])}, "
          f"worst episode {max(r['max_market_inventory'] for r in rows)}")
    print(f"  min realized FERTILIZER price: worst episode "
          f"{min((r['min_price'] for r in rows if r['min_price'] is not None), default=None)}")
    print(f"  FERTILIZER left unsold in shed at episode end: median "
          f"{median([r['shed_left_at_end'] for r in rows])}")

    # Where in the season the collects are missing, day by day — a ramp-shaped deficit is
    # structural, a deficit concentrated on busy mid/late days is the fixable kind.
    max_days = max(r["days"] for r in rows)
    print("\nper-day median offered vs collected:")
    print(f"  {'day':>4} {'offered':>8} {'collected':>10} {'missed':>8}")
    per_day = []
    for day in range(max_days):
        off = median([r["offered_by_day"][day] for r in rows if day < len(r["offered_by_day"])])
        col = median([r["collects_by_day"][day] for r in rows if day < len(r["collects_by_day"])])
        per_day.append({"day": day, "offered": off, "collected": col, "missed": off - col})
        print(f"  {day:>4} {off:>8.1f} {col:>10.1f} {off - col:>8.1f}")

    payload = {
        "source": str(ROOT),
        "episodes": n,
        "median": {
            "naive_ceiling": naive,
            "offered_animal_days": offered,
            "collect_actions": collects,
            "units_sold": sold,
            "fertilizer_revenue": revenue,
            "structural_gap": structural_gap,
            "fixable_gap": fixable_gap,
            "sell_side_gap": sell_gap,
            "first_full_herd_day": median([r["first_full_herd_day"] for r in rows]),
            "animals_peak": median([r["animals_peak"] for r in rows]),
            "max_market_inventory": median([r["max_market_inventory"] for r in rows]),
            "shed_left_at_end": median([r["shed_left_at_end"] for r in rows]),
        },
        "sell_floor": {
            "price": SELL_FLOOR_PRICE,
            "binds_at_delta": FERTILIZER_FLOOR_DELTA,
            "worst_market_inventory": max(r["max_market_inventory"] for r in rows),
            "worst_realized_price": min(
                (r["min_price"] for r in rows if r["min_price"] is not None), default=None
            ),
        },
        "per_day": per_day,
        "per_episode": rows,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"\nwritten to {OUT}")


if __name__ == "__main__":
    main()
