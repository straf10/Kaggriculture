#!/usr/bin/env python3
"""The §5.1 target profile, rebuilt on `archive_sync.py top`'s selected traces.

`analysis/b1_top4_profile_2026_08_21.py` and its dependency `b1_top5_profile.py` were
both pruned in eafcd43 ("prune 53 superseded one-off analysis scripts") along with the
untracked collector chain that fed them (ROADMAP §11) — so the 2026-08-21 fit is two
weeks stale and cannot be re-run as-is. This is a from-scratch rewrite that reads
directly off `analysis.s8_replay_io` (the one shared replay reader, ROADMAP §3) and
`analysis.s9_market_ledger.episode_ledger` (the one shared per-unit sale ledger) — no
second reader, no second ledger.

Per team: money d5/d10/d15/d20/d24/end, planted tiles, hands, animals, quadrant unlock
days, crop tile-days per crop, sell calendar (first sell day + batch size) per product.
Reported as PER-TEAM MEDIAN across that team's traces, plus the RANGE across teams —
never one pooled number (§5.2: cross-town $/unit variance is 99-100% between-town, so
pooling erases exactly the between-team signal this profile exists to show).

This does not re-open the S7 Leg A re-donor route: the top-4 policy is state-adaptive
(cross-trace agreement 0.25-0.37), so it is read as a descriptive target, never copied.

Usage:
    python analysis/archive_sync.py board
    python analysis/archive_sync.py top 5 10
    python analysis/b1_top_profile.py --selection data/archive/raw/top5_<date>/manifest.json
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from analysis.s8_replay_io import load  # noqa: E402
from analysis.s9_market_ledger import episode_ledger  # noqa: E402

DERIVED = ROOT / "data" / "derived"
CHECK_DAYS = [5, 10, 15, 20, 24, 27, 29]
QUADRANT_MILESTONES = (2, 3, 4)

FIELDS = [
    "final_money", "money_at", "tiles_at", "hands_at", "animals_at", "animals_peak",
    "quadrants_final", "first_quadrant_day", "first_animal_day", "tile_days",
    "first_sell_day", "batch_median", "sell_orders", "revenue", "units_sold",
]


# --------------------------------------------------------------------------- per-episode

def _day_snapshots(steps: list, seat: int) -> dict[int, dict]:
    """One snapshot per game day: money, planted tile count (+ per-crop), hand count,
    animal head count (+ per-species), unlocked quadrant count. Later steps of the same
    day overwrite earlier ones, so each day's snapshot is its end-of-day state."""
    snaps: dict[int, dict] = {}
    for st in steps[1:]:
        obs = st[seat]["observation"]
        day = obs["day"]
        farm = obs["farms"][obs["player"]]
        crop_tiles: Counter = Counter()
        animals: Counter = Counter()
        for row in farm["tiles"]:
            for t in row:
                if not t or isinstance(t, str):
                    continue
                if t.get("kind") == "PLANT" and t.get("crop"):
                    crop_tiles[t["crop"]] += 1
                elif t.get("kind") == "PASTURE" and t.get("animal"):
                    animals[t["animal"]] += 1
        snaps[day] = {
            "money": float(farm["money"]),
            "tiles": sum(crop_tiles.values()),
            "crop_tiles": crop_tiles,
            "hands": len(farm.get("hands") or []),
            "animals": animals,
            "quadrants": len(farm.get("unlocked_quadrants") or []),
        }
    return snaps


def _sell_events(steps: list, seat: int) -> dict[str, list[tuple[int, int]]]:
    """{product: [(day, order_qty), ...]} from the raw SELL orders this seat submitted —
    the *posted* batch size, not the realised fill (episode_ledger reports that)."""
    events: dict[str, list[tuple[int, int]]] = defaultdict(list)
    for t in range(1, len(steps)):
        cell = steps[t][seat]
        act = cell.get("action") or {}
        day = cell["observation"]["day"]
        for order in (act.get("market") or []):
            if not isinstance(order, list) or len(order) < 3 or order[0] != "SELL":
                continue
            try:
                qty = int(order[2])
            except (TypeError, ValueError):
                continue
            if qty > 0:
                events[order[1]].append((day, qty))
    return events


def profile_seat(replay: dict, seat: int) -> dict:
    steps = replay["steps"]
    snaps = _day_snapshots(steps, seat)
    days = sorted(snaps)
    last_day = days[-1] if days else None

    def at(day):
        cands = [d for d in days if d <= day]
        return snaps[cands[-1]] if cands else None

    def _animal_total(day):
        return sum((at(day) or {}).get("animals", {}).values()) if at(day) else None

    money_at = {str(d): (at(d) or {}).get("money") for d in CHECK_DAYS}
    tiles_at = {str(d): (at(d) or {}).get("tiles") for d in CHECK_DAYS}
    hands_at = {str(d): (at(d) or {}).get("hands") for d in CHECK_DAYS}
    # Total head count per day (matches ROADMAP §5.1's "Animals d5/d10/.../end" row);
    # the per-species breakdown lives in `animals_peak` instead — this dict must stay
    # single-level, scalar-per-key, like every other *_at field (`_agg_team`/
    # `_range_across_teams` only handle one level of nesting).
    animals_at = {str(d): _animal_total(d) for d in CHECK_DAYS}
    if last_day is not None:
        money_at["end"] = snaps[last_day]["money"]
        animals_at["end"] = sum(snaps[last_day]["animals"].values())
        quadrants_final = snaps[last_day]["quadrants"]
    else:
        money_at["end"] = None
        animals_at["end"] = None
        quadrants_final = None

    first_quadrant_day = {}
    for n in QUADRANT_MILESTONES:
        for d in days:
            if snaps[d]["quadrants"] >= n:
                first_quadrant_day[str(n)] = d
                break

    first_animal_day: dict[str, int] = {}
    animals_peak: Counter = Counter()
    for d in days:
        for sp, cnt in snaps[d]["animals"].items():
            animals_peak[sp] = max(animals_peak[sp], cnt)
            if cnt > 0 and sp not in first_animal_day:
                first_animal_day[sp] = d

    tile_days: Counter = Counter()
    for d in days:
        for crop, cnt in snaps[d]["crop_tiles"].items():
            tile_days[crop] += cnt

    events = _sell_events(steps, seat)
    first_sell_day = {p: min(d for d, _ in evs) for p, evs in events.items()}
    batch_median = {p: statistics.median([q for _, q in evs]) for p, evs in events.items()}
    sell_orders = {p: len(evs) for p, evs in events.items()}

    led = episode_ledger(replay)
    revenue = led["revenue"][seat]
    units_sold = led["units"][seat]

    return {
        "final_money": money_at["end"],
        "money_at": money_at,
        "tiles_at": tiles_at,
        "hands_at": hands_at,
        "animals_at": animals_at,
        "animals_peak": dict(animals_peak),
        "quadrants_final": quadrants_final,
        "first_quadrant_day": first_quadrant_day,
        "first_animal_day": first_animal_day,
        "tile_days": dict(tile_days),
        "first_sell_day": first_sell_day,
        "batch_median": batch_median,
        "sell_orders": sell_orders,
        "revenue": revenue,
        "units_sold": units_sold,
    }


# --------------------------------------------------------------------------- aggregation

def _median(xs) -> float | None:
    xs = [x for x in xs if x is not None]
    return round(statistics.median(xs), 1) if xs else None


def _agg_team(profiles: list[dict], field: str):
    """Median across one team's traces. Preserves the field's shape: a dict field
    (money_at, tile_days, ...) becomes a dict of per-key medians."""
    sample = next((p[field] for p in profiles if field in p), None)
    if isinstance(sample, dict):
        keys = sorted({k for p in profiles for k in (p.get(field) or {})})
        return {k: _median([p.get(field, {}).get(k) for p in profiles]) for k in keys}
    return _median([p.get(field) for p in profiles])


def _range_across_teams(team_aggs: dict[str, dict], field: str):
    """Min-max range of the per-team medians — never a pooled number (§5.1/§5.2)."""
    vals = [t[field] for t in team_aggs.values() if t.get(field) is not None]
    if not vals:
        return None
    sample = vals[0]
    if isinstance(sample, dict):
        keys = sorted({k for v in vals for k in v})
        out = {}
        for k in keys:
            xs = [v.get(k) for v in vals if v.get(k) is not None]
            out[k] = [min(xs), max(xs)] if xs else None
        return out
    xs = [v for v in vals if v is not None]
    return [min(xs), max(xs)] if xs else None


# --------------------------------------------------------------------------- driver

def build_profile(selection: dict[str, list[dict]]) -> dict:
    team_profiles: dict[str, list[dict]] = {}
    team_aggs: dict[str, dict] = {}
    skipped = 0
    for team, entries in selection.items():
        profiles = []
        for entry in entries:
            path = Path(entry["path"])
            if not path.exists():
                skipped += 1
                continue
            replay = load(path)
            profiles.append(profile_seat(replay, entry["seat"]))
        if not profiles:
            continue
        team_profiles[team] = profiles
        team_aggs[team] = {"episodes": len(profiles),
                            **{f: _agg_team(profiles, f) for f in FIELDS}}

    n_teams = len(team_aggs)
    n_episodes = sum(len(p) for p in team_profiles.values())
    verdict = (
        f"{n_episodes} traces across {n_teams} teams, generated {dt.date.today().isoformat()} "
        f"via analysis/archive_sync.py top (official submission-scoped API only, no "
        f"competitor notebook code opened). Descriptive target profile, not a route: S7 Leg A "
        f"measured the top-4 policy as state-adaptive (cross-trace agreement 0.25-0.37), so "
        f"per-team medians are attenuated by within-team variance and this is read as a shape "
        f"to aim at, never copied." + (f" {skipped} selected replay(s) missing on disk, skipped."
                                        if skipped else "")
    )
    return {
        "generated_at": dt.date.today().isoformat(),
        "verdict": verdict,
        "teams": team_aggs,
        "range_across_teams": {f: _range_across_teams(team_aggs, f) for f in FIELDS},
    }


def _print_report(profile: dict) -> None:
    print(profile["verdict"])
    for team, agg in sorted(profile["teams"].items(), key=lambda kv: -(kv[1].get("final_money") or 0)):
        print(f"\n=== {team} ({agg['episodes']} eps)  final ${agg['final_money']:,.0f}"
              if agg.get("final_money") is not None else f"\n=== {team} ({agg['episodes']} eps)")
        print(f"  money   {agg['money_at']}")
        print(f"  tiles   {agg['tiles_at']}")
        print(f"  hands   {agg['hands_at']}   quadrants {agg['quadrants_final']}  "
              f"(first extra day {agg['first_quadrant_day']})")
        print(f"  animals peak {agg['animals_peak']}  first day {agg['first_animal_day']}")
        print(f"  tile-days {agg['tile_days']}")
    print("\n=== range across teams ===")
    for field in FIELDS:
        print(f"  {field}: {profile['range_across_teams'][field]}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--selection", required=True,
                    help="a manifest.json written by `analysis/archive_sync.py top K N`")
    ap.add_argument("--out", default=str(DERIVED / "b1_top_profile.json"))
    args = ap.parse_args()

    sel_path = Path(args.selection)
    sel = json.loads(sel_path.read_text())
    selection = sel.get("selection", sel)  # accept either the wrapper or a bare {team: [...]} map

    profile = build_profile(selection)
    profile["source_manifest"] = str(sel_path)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(profile, indent=2, sort_keys=True))
    print(f"wrote {out} (gitignored unless allow-listed)\n")
    _print_report(profile)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
