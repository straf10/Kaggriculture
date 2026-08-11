#!/usr/bin/env python3
"""B3 — the target profile as parameters, with cross-team spread (ROADMAP.md S1.1).

Same aggregate-only boundary as `analysis/b2_current_engine_meta.py`: this script reads
the per-team medians b2 already computes (crew size, herd composition, quadrants,
planted tiles, tile-days/product, sell calendar) and adds the piece b2 does not —
the SPREAD of those team-level medians across the >=6 teams with enough seats. That
spread is what tells us which numbers are a converged target (tight spread) and which
are one team's choice (wide spread). No per-unit action sequence is read or stored here.

Usage:
    python analysis/b3_target_profile.py --ids-file <ids.txt> [--expect-interval 24]
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from analysis.b2_current_engine_meta import agg, median  # noqa: E402
from analysis.b1_top5_profile import profile_seat  # noqa: E402

ARCHIVE = Path(__file__).resolve().parent.parent / "data" / "archive"
RAW = ARCHIVE / "raw"

DAYS_MONEY = (5, 10, 15, 20, 24, 29)
DAYS_TILES = (10, 15, 17, 20, 24, 27, 29)
DAYS_UNITS = (5, 10, 15, 20, 29)


def spread(values: list) -> dict:
    """min/median/max/std over one number per team (b2's per-team median)."""
    xs = [v for v in values if v is not None]
    if not xs:
        return {"n": 0, "min": None, "median": None, "max": None, "std": None}
    out = {"n": len(xs), "min": min(xs), "median": median(xs), "max": max(xs)}
    out["std"] = round(statistics.pstdev(xs), 2) if len(xs) > 1 else 0.0
    return out


def spread_over_teams(by_team: dict, path: tuple) -> dict:
    """path e.g. ("hands_at", 10) or ("per_product", "STRAWBERRY", "tile_days")."""
    values = []
    for team_agg in by_team.values():
        node = team_agg
        ok = True
        for key in path:
            if isinstance(node, dict) and key in node:
                node = node[key]
            else:
                ok = False
                break
        values.append(node if ok else None)
    return spread(values)


def build_target_profile(by_team: dict, population: dict) -> dict:
    teams = sorted(by_team)
    profile = {"n_teams": len(teams), "teams": teams}

    profile["crew_size_ramp"] = {
        f"d{d}": {"population_median": population["hands_at"].get(str(d)) or population["hands_at"].get(d),
                  **spread_over_teams(by_team, ("hands_at", d))}
        for d in DAYS_UNITS
    }

    profile["herd_composition_peak"] = {
        sp: {"population_median": population["animals_peak"].get(sp),
             **spread_over_teams(by_team, ("animals_peak", sp))}
        for sp in ("COW", "SHEEP", "GOOSE")
    }
    profile["herd_size_ramp"] = {
        f"d{d}": {"population_median": population["animals_at"].get(str(d)) or population["animals_at"].get(d),
                  **spread_over_teams(by_team, ("animals_at", d))}
        for d in DAYS_UNITS
    }

    profile["quadrants"] = {
        "final_count": {"population_median": population["quadrants_final"],
                        **spread_over_teams(by_team, ("quadrants_final",))},
        "first_extra_quadrant_day": {
            "population_median": population["first_quadrant_day"].get(2),
            **spread_over_teams(by_team, ("first_quadrant_day", 2)),
        },
        "third_quadrant_day": {
            "population_median": population["first_quadrant_day"].get(3),
            **spread_over_teams(by_team, ("first_quadrant_day", 3)),
        },
    }

    profile["planted_tiles"] = {
        f"d{d}": {"population_median": population["tiles_at"].get(str(d)) or population["tiles_at"].get(d),
                  **spread_over_teams(by_team, ("tiles_at", d))}
        for d in DAYS_TILES
    }

    products = sorted({p for t in by_team.values() for p in t.get("per_product", {})})
    profile["tile_days_per_crop"] = {}
    profile["sell_calendar"] = {}
    for p in products:
        pop_pp = population["per_product"].get(p, {})
        td = pop_pp.get("tile_days")
        if td:  # only crops (tile_days > 0); skip animal/byproduct rows here
            profile["tile_days_per_crop"][p] = {
                "population_median": td,
                **spread_over_teams(by_team, ("per_product", p, "tile_days")),
                "dollars_per_tile_day_population": pop_pp.get("dollars_per_tile_day"),
                "dollars_per_tile_day_spread": spread_over_teams(
                    by_team, ("per_product", p, "dollars_per_tile_day")),
            }
        profile["sell_calendar"][p] = {
            "first_sell_day": {"population_median": pop_pp.get("first_sell_day"),
                               **spread_over_teams(by_team, ("per_product", p, "first_sell_day"))},
            "batch_median": {"population_median": pop_pp.get("batch_median"),
                             **spread_over_teams(by_team, ("per_product", p, "batch_median"))},
        }

    return profile


def _fmt_spread(d: dict) -> str:
    if not d or d.get("n", 0) == 0:
        return "n=0"
    return f"med={d['median']} [min={d['min']} max={d['max']} std={d['std']} n={d['n']}]"


def print_summary(profile: dict) -> None:
    print(f"\n=== B3 target profile — spread across {profile['n_teams']} teams: {profile['teams']}\n")

    print("Crew size ramp (hands):")
    for d, v in profile["crew_size_ramp"].items():
        print(f"  {d}: population={v['population_median']}  team-spread {_fmt_spread(v)}")

    print("\nHerd composition (peak, by species):")
    for sp, v in profile["herd_composition_peak"].items():
        print(f"  {sp}: population={v['population_median']}  team-spread {_fmt_spread(v)}")

    print("\nHerd size ramp (total animals):")
    for d, v in profile["herd_size_ramp"].items():
        print(f"  {d}: population={v['population_median']}  team-spread {_fmt_spread(v)}")

    print("\nQuadrants:")
    for k, v in profile["quadrants"].items():
        print(f"  {k}: population={v['population_median']}  team-spread {_fmt_spread(v)}")

    print("\nPlanted tiles:")
    for d, v in profile["planted_tiles"].items():
        print(f"  {d}: population={v['population_median']}  team-spread {_fmt_spread(v)}")

    print("\nTile-days per crop:")
    for p, v in profile["tile_days_per_crop"].items():
        print(f"  {p}: population={v['population_median']}  team-spread {_fmt_spread(v)}  "
              f"($/td population={v['dollars_per_tile_day_population']} "
              f"spread {_fmt_spread(v['dollars_per_tile_day_spread'])})")

    print("\nSell calendar (first day / median batch):")
    for p, v in profile["sell_calendar"].items():
        fd, bm = v["first_sell_day"], v["batch_median"]
        if fd["n"] == 0 and bm["n"] == 0:
            continue
        print(f"  {p}: first_day population={fd['population_median']} spread {_fmt_spread(fd)}  |  "
              f"batch population={bm['population_median']} spread {_fmt_spread(bm)}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ids-file", required=True)
    ap.add_argument("--limit", type=int, default=None, help="take the newest N ids")
    ap.add_argument("--expect-interval", type=int, default=24,
                    help="required townCenterSellInterval; episodes on any other engine "
                         "config are skipped and counted, never silently mixed in")
    ap.add_argument("--min-seats", type=int, default=6, help="per-team reporting threshold")
    ap.add_argument("--out", default="data/derived/b3_target_profile.json")
    args = ap.parse_args()

    import gzip
    from collections import defaultdict

    ids = [int(x) for x in Path(args.ids_file).read_text().split()]
    if args.limit:
        ids = ids[-args.limit:]

    all_rows: list[dict] = []
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
        for seat in (0, 1):
            row = profile_seat(replay, seat)
            row["episode_id"], row["seat"], row["team"] = eid, seat, names[seat]
            all_rows.append(row)
            by_team[names[seat]].append(row)

    print(f"seats profiled: {len(all_rows)}   skipped (wrong engine config): {skipped_engine}   "
          f"skipped (replay not local): {skipped_missing}")
    if not all_rows:
        print("Nothing to profile — fetch replays first "
              "(analysis/b0_fetch_top_replays.py --ids-file ...).")
        return

    population = agg(all_rows)
    by_team_agg = {t: agg(rs) for t, rs in by_team.items() if len(rs) >= args.min_seats}
    print(f"teams with >= {args.min_seats} seats: {sorted(by_team_agg)}")

    profile = build_target_profile(by_team_agg, population)
    profile["engine_town_center_sell_interval"] = args.expect_interval
    profile["source_ids_file"] = args.ids_file
    profile["gate"] = {
        "requirement": "profile reproduces across >=6 teams with a stated spread (ROADMAP S1)",
        "teams_used": len(by_team_agg),
        "passed": len(by_team_agg) >= 6,
    }

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(profile, indent=2, sort_keys=True), encoding="utf-8")
    print(f"\nwrote {args.out}")
    print(f"gate: {profile['gate']}")

    print_summary(profile)


if __name__ == "__main__":
    main()
