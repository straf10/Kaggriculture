#!/usr/bin/env python3
"""B1 refresh — top-4 profile from the 2026-08-21 fresh replays (§7.1 ride-along).

The original analysis/b1_top5_profile.py depends on data/archive/{teams.csv,episodes.csv,
replays.parquet}, which per §11 no longer exists — the collector chain was removed with
data/archive/. This variant reads the fresh, kaggle-CLI-fetched replays in
data/archive/raw/2026-08-21/ using the explicit (episode_id, seat, team, submission_id)
mapping produced by the Ship A donor-selection pass.

Runs at zero marginal cost inside Ship A (§11: "the same data pull re-fits §5.1's top-N
profile"). Emits the same JSON shape as b1_top5_profile.json for drop-in comparison.

The point is not to re-endorse §5.1's profile as a *target*; the fidelity finding says
"the top-4 policy is a state-adaptive population, so its per-day medians are already
attenuated by within-team variance". The point is to see WHAT changed between the
2026-08-16 top-5 (カワシギ + old field) and today's top-4 (a completely rotated field).

Usage:
    python analysis/b1_top4_profile_2026_08_21.py \
        --mapping /path/to/canonical_donor_traces.json \
        --out data/derived/b1_top4_profile_2026_08_21.json
"""
from __future__ import annotations

import argparse
import json
import sys
import statistics
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from analysis.b1_top5_profile import profile_seat  # noqa: E402

ARCHIVE = ROOT / "data" / "archive" / "raw" / "2026-08-21"


def median(xs):
    xs = [x for x in xs if x is not None]
    return statistics.median(xs) if xs else None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mapping", required=True)
    ap.add_argument("--out", default="data/derived/b1_top4_profile_2026_08_21.json")
    args = ap.parse_args()

    mapping = json.loads(Path(args.mapping).read_text())
    # Group by team (aggregating both submissions per team when both are targeted, though in this
    # pass only the higher-rated sub per team was pulled)
    by_team: dict = defaultdict(list)
    for r in mapping:
        by_team[r["team"]].append(r)

    print(f"scanning {sum(len(v) for v in by_team.values())} traces across {len(by_team)} teams")
    summary = {}
    for team, rows in by_team.items():
        profiles = []
        for r in rows:
            path = ARCHIVE / f"{r['episode_id']}.json"
            if not path.exists():
                continue
            replay = json.loads(path.read_text())
            profiles.append(profile_seat(replay, r["seat"]))
        if not profiles:
            print(f"  {team}: no replays on disk, skipping")
            continue

        agg = {"team_name": team, "episodes": len(profiles),
               "final_money_median": median([p["final_money"] for p in profiles])}
        for field in ("money_at", "tiles_at", "hands_at", "animals_at"):
            keys = sorted({k for p in profiles for k in p[field]})
            agg[field] = {str(k): median([p[field].get(k) for p in profiles]) for k in keys}
        agg["animals_peak"] = {sp: median([p["animals_peak"].get(sp, 0) for p in profiles])
                               for sp in ("COW", "SHEEP", "GOOSE")}
        agg["quadrants_final"] = median([p["quadrants_final"] for p in profiles])
        agg["first_quadrant_day"] = {
            str(q): median([p["first_quadrant_day"].get(q) for p in profiles
                            if p["first_quadrant_day"].get(q) is not None])
            for q in (2, 3, 4)}
        agg["first_animal_day"] = {
            sp: median([p["first_animal_day"].get(sp) for p in profiles
                        if p["first_animal_day"].get(sp) is not None])
            for sp in ("COW", "SHEEP", "GOOSE")}
        prods = sorted({k for p in profiles for k in p["tile_days"]}
                       | {k for p in profiles for k in p["revenue"]})
        agg["per_product"] = {}
        for prod in prods:
            td = median([p["tile_days"].get(prod, 0) for p in profiles])
            rv = median([p["revenue"].get(prod, 0) for p in profiles])
            agg["per_product"][prod] = {
                "tile_days": td, "revenue": rv,
                "dollars_per_tile_day": round(rv / td, 1) if td else None,
                "first_sell_day": median([p["first_sell_day"].get(prod) for p in profiles
                                          if prod in p["first_sell_day"]]),
                "batch_median": median([p["batch_median"].get(prod) for p in profiles
                                        if prod in p["batch_median"]]),
                "sell_orders": median([p["sell_orders"].get(prod, 0) for p in profiles]),
                "units_sold": median([p["units_sold"].get(prod, 0) for p in profiles]),
            }
        summary[team] = agg

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summary, indent=2, sort_keys=True))
    print(f"\nwrote {out} (gitignored)")

    for team, agg in sorted(summary.items(), key=lambda kv: -(kv[1]["final_money_median"] or 0)):
        print(f"\n=== {team} ({agg['episodes']} eps)  final ${agg['final_money_median']:,.0f}")
        print(f"  money   {agg['money_at']}")
        print(f"  tiles   {agg['tiles_at']}")
        print(f"  hands   {agg['hands_at']}   quadrants {agg['quadrants_final']}  "
              f"(first extra day {agg['first_quadrant_day']})")
        print(f"  animals peak {agg['animals_peak']}  first day {agg['first_animal_day']}")
        print(f"  {'product':>11} {'tile_days':>9} {'revenue':>10} {'$/td':>8} "
              f"{'sell d1':>7} {'batch':>6} {'units':>6}")
        for p, v in agg["per_product"].items():
            if not v["tile_days"] and not v["revenue"]:
                continue
            print(f"  {p:>11} {v['tile_days'] or 0:9.0f} {v['revenue'] or 0:10.0f} "
                  f"{(v['dollars_per_tile_day'] or 0):8.1f} "
                  f"{str(v['first_sell_day']):>7} {str(v['batch_median']):>6} "
                  f"{v['units_sold'] or 0:6.0f}")


if __name__ == "__main__":
    main()
