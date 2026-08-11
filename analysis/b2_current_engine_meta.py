#!/usr/bin/env python3
"""B2 — the top-of-ladder profile measured ONLY on current-engine (1.32.6) episodes.

Why this exists, and why B1 is not enough: the 1.32.6 balance change (engine_deltas D27)
landed in live episodes between 2026-08-07 and 2026-08-08. Replays older than that ran a
town centre that absorbed 140 units/product/season instead of 30 — the regime in which
MELON was a good crop. Any behaviour measured on those replays describes a game that no
longer exists. `analysis/b1_top5_profile.py` reads whatever replays we hold for a team,
and 56 of its first 66 were pre-change.

This script therefore takes an explicit id list — the official daily top-episode dataset
(`kaggle datasets files kaggle/kaggriculture-episodes-YYYY-MM-DD`), which is rating-sorted
and guaranteed to be on the engine of that day — asserts the config, and profiles every
seat in it. Team names come from the replay's own `info.TeamNames`.

Same boundary as the other analysis scripts: per-day aggregate state plus market-order
cadence. No per-unit action sequence is stored or emitted here.

Usage:
    python analysis/b2_current_engine_meta.py --ids-file <ids.txt> [--expect-interval 24]
"""
from __future__ import annotations

import argparse
import gzip
import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from analysis.b1_top5_profile import median, profile_seat  # noqa: E402

ARCHIVE = Path(__file__).resolve().parent.parent / "data" / "archive"
RAW = ARCHIVE / "raw"

DAYS_MONEY = (5, 10, 15, 20, 24, 29)
DAYS_TILES = (10, 15, 17, 20, 24, 27, 29)
DAYS_UNITS = (5, 10, 15, 20, 29)


def agg(rows: list[dict]) -> dict:
    out = {"seats": len(rows),
           "final_money_median": median([r["final_money"] for r in rows])}
    for field, days in (("money_at", DAYS_MONEY), ("tiles_at", DAYS_TILES),
                        ("hands_at", DAYS_UNITS), ("animals_at", DAYS_UNITS)):
        out[field] = {d: median([r[field].get(d) for r in rows]) for d in days}
    out["animals_peak"] = {sp: median([r["animals_peak"].get(sp, 0) for r in rows])
                           for sp in ("COW", "SHEEP", "GOOSE")}
    out["quadrants_final"] = median([r["quadrants_final"] for r in rows])
    out["first_quadrant_day"] = {q: median([r["first_quadrant_day"].get(q) for r in rows
                                            if r["first_quadrant_day"].get(q) is not None])
                                 for q in (2, 3, 4)}
    prods = sorted({k for r in rows for k in r["tile_days"]}
                   | {k for r in rows for k in r["revenue"]})
    out["per_product"] = {}
    for p in prods:
        td = median([r["tile_days"].get(p, 0) for r in rows])
        rv = median([r["revenue"].get(p, 0) for r in rows])
        out["per_product"][p] = {
            "tile_days": td, "revenue": rv,
            "dollars_per_tile_day": round(rv / td, 1) if td else None,
            "first_sell_day": median([r["first_sell_day"].get(p) for r in rows
                                      if p in r["first_sell_day"]]),
            "batch_median": median([r["batch_median"].get(p) for r in rows
                                    if p in r["batch_median"]]),
            "units_sold": median([r["units_sold"].get(p, 0) for r in rows]),
        }
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ids-file", required=True)
    ap.add_argument("--limit", type=int, default=None, help="take the newest N ids")
    ap.add_argument("--expect-interval", type=int, default=24,
                    help="required townCenterSellInterval; episodes on any other engine "
                         "config are skipped and counted, never silently mixed in")
    ap.add_argument("--min-seats", type=int, default=6, help="per-team reporting threshold")
    ap.add_argument("--out", default="data/derived/b2_current_engine_meta.json")
    args = ap.parse_args()

    ids = [int(x) for x in Path(args.ids_file).read_text().split()]
    if args.limit:
        ids = ids[-args.limit:]

    all_rows: list[dict] = []
    winners: list[dict] = []
    losers: list[dict] = []
    by_team: dict = defaultdict(list)
    skipped_engine = skipped_missing = 0

    for eid in ids:
        path = RAW / f"{eid}.json.gz"
        if not path.exists():
            skipped_missing += 1
            continue
        replay = json.loads(gzip.decompress(path.read_bytes()).decode())
        if replay["configuration"].get("townCenterSellInterval") != args.expect_interval:
            skipped_engine += 1
            continue
        names = replay["info"].get("TeamNames") or ["?", "?"]
        rewards = replay.get("rewards") or [None, None]
        for seat in (0, 1):
            row = profile_seat(replay, seat)
            row["episode_id"], row["seat"], row["team"] = eid, seat, names[seat]
            all_rows.append(row)
            by_team[names[seat]].append(row)
            if None not in rewards and rewards[0] != rewards[1]:
                (winners if rewards[seat] > rewards[1 - seat] else losers).append(row)
        if len(all_rows) % 40 == 0:
            print(f"  parsed {len(all_rows)} seats", flush=True)

    print(f"\nseats profiled: {len(all_rows)}   "
          f"skipped (wrong engine config): {skipped_engine}   "
          f"skipped (replay not local): {skipped_missing}")
    if not all_rows:
        print("Nothing to profile — fetch replays first "
              "(analysis/b0_fetch_top_replays.py --ids-file ...).")
        return

    summary = {"population": agg(all_rows),
               "winners": agg(winners) if winners else None,
               "losers": agg(losers) if losers else None,
               "engine_town_center_sell_interval": args.expect_interval,
               "by_team": {t: agg(rs) for t, rs in by_team.items()
                           if len(rs) >= args.min_seats}}
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    print(f"wrote {args.out}")

    def show(label: str, a: dict) -> None:
        print(f"\n=== {label} ({a['seats']} seats) final ${a['final_money_median']:,.0f}")
        print(f"  money   {a['money_at']}")
        print(f"  tiles   {a['tiles_at']}")
        print(f"  hands   {a['hands_at']}")
        print(f"  animals {a['animals_at']}  peak {a['animals_peak']}  "
              f"quadrants {a['quadrants_final']} {a['first_quadrant_day']}")
        print(f"  {'product':>11} {'tile_days':>9} {'revenue':>10} {'$/td':>8} "
              f"{'sell d1':>7} {'batch':>6} {'units':>6}")
        for p, v in a["per_product"].items():
            if not v["tile_days"] and not v["revenue"]:
                continue
            print(f"  {p:>11} {v['tile_days'] or 0:9.0f} {v['revenue'] or 0:10.0f} "
                  f"{(v['dollars_per_tile_day'] or 0):8.1f} "
                  f"{str(v['first_sell_day']):>7} {str(v['batch_median']):>6} "
                  f"{v['units_sold'] or 0:6.0f}")

    show("POPULATION (current engine)", summary["population"])
    if summary["winners"]:
        show("winners", summary["winners"])
        show("losers", summary["losers"])
    for team, a in sorted(summary["by_team"].items(),
                          key=lambda kv: -(kv[1]["final_money_median"] or 0)):
        show(team, a)


if __name__ == "__main__":
    main()
