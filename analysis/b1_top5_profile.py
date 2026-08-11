#!/usr/bin/env python3
"""B1 — behavioural profile of the *current* top-N ladder teams, from our own replays.

Why this exists: `data/archive/episode_features.csv` has no animal, quadrant, or
sell-timing columns (MASTERPLAN §3.4 "Κενό στα δεδομένα"), and the community
notebooks report end-of-episode compositions that the engine makes misleading
(one-shot crops empty their tile at HARVEST). This script measures, per day, from
the replays we hold ourselves:

  * money / hands / planted tiles / animals by species / quadrants, per day
  * first-acquisition days (land, each animal species)
  * sell cadence per product: first day, per-order batch size, day histogram
  * revenue per crop divided by that crop's planted tile-days ($/tile-day)
  * the endgame question: how many tiles stay planted on days 20-29

Same boundary as `analysis/replay_profile.py`: aggregate per-day state only. No
per-unit action sequence is stored or emitted, so nothing here can become a
trajectory prior (MASTERPLAN §3.4 / Open #11).

Usage:
    python analysis/b1_top5_profile.py [--top 5] [--per-team 12] [--out data/derived]
"""
from __future__ import annotations

import argparse
import gzip
import json
import sys
from collections import defaultdict
from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from analysis.replay_profile import extract_profile  # noqa: E402
from harness.metrics import extract_metrics  # noqa: E402

ARCHIVE = Path(__file__).resolve().parent.parent / "data" / "archive"
TURNS_PER_DAY = 24
OUR_TEAM_NAMES = {"STRAF", "straf10"}


def median(xs):
    xs = [x for x in xs if x is not None]
    if not xs:
        return None
    s = sorted(xs)
    m = len(s) // 2
    return s[m] if len(s) % 2 else 0.5 * (s[m - 1] + s[m])


def sell_events(replay: dict, seat: int) -> list[dict]:
    """Per-SELL-order records: (day, item, units). Aggregate cadence only."""
    out = []
    for t, step in enumerate(replay["steps"]):
        action = step[seat].get("action") or {}
        for order in action.get("market") or []:
            if isinstance(order, list) and len(order) >= 3 and order[0] == "SELL":
                out.append({"day": t // TURNS_PER_DAY, "item": order[1], "units": order[2]})
    return out


def profile_seat(replay: dict, seat: int) -> dict:
    prof = extract_profile(replay, seat)
    daily = prof["daily"]
    tile_days: dict = defaultdict(float)
    for day in daily:
        for key, val in day.items():
            if key.startswith("plants_"):
                tile_days[key[7:].upper()] += val

    revenue: dict = defaultdict(float)
    units_sold: dict = defaultdict(float)
    try:
        for sale in extract_metrics(replay, seat)["market_sales"]:
            revenue[sale["item"]] += sale["price"]
            units_sold[sale["item"]] += 1
    except Exception as exc:                       # a malformed replay must not kill the run
        print(f"    metrics unavailable ({exc})")

    sells = sell_events(replay, seat)
    first_sell_day, batches = {}, defaultdict(list)
    for ev in sells:
        item = ev["item"]
        first_sell_day.setdefault(item, ev["day"])
        first_sell_day[item] = min(first_sell_day[item], ev["day"])
        batches[item].append(ev["units"])

    by_day = {d["day"]: d for d in daily}
    return {
        "final_money": daily[-1]["money"] if daily else None,
        "money_at": {d: by_day[d]["money"] for d in (5, 10, 15, 20, 24, 29) if d in by_day},
        "tiles_at": {d: by_day[d]["tiles_planted"] for d in (10, 15, 17, 20, 24, 27, 29)
                     if d in by_day},
        "hands_at": {d: by_day[d]["hands"] for d in (0, 5, 10, 15, 20, 29) if d in by_day},
        "animals_at": {d: by_day[d]["animals_total"] for d in (5, 10, 15, 20, 29) if d in by_day},
        "animals_final": {k[8:].upper(): v for k, v in (daily[-2] if len(daily) > 1 else {}).items()
                          if k.startswith("animals_")},
        "animals_peak": {sp: max(d.get(f"animals_{sp.lower()}", 0) for d in daily)
                         for sp in ("COW", "SHEEP", "GOOSE")},
        "quadrants_final": daily[-1]["unlocked_quadrants"] if daily else None,
        "first_quadrant_day": prof["first_quadrant_day"],
        "first_animal_day": prof["first_animal_day"],
        "tile_days": dict(tile_days),
        "revenue": dict(revenue),
        "units_sold": dict(units_sold),
        "first_sell_day": first_sell_day,
        "batch_median": {k: median(v) for k, v in batches.items()},
        "sell_orders": {k: len(v) for k, v in batches.items()},
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--top", type=int, default=5, help="how many top teams by ladder_score")
    ap.add_argument("--per-team", type=int, default=12, help="max episodes per team")
    ap.add_argument("--since", default=None, help="only episodes ending on/after YYYY-MM-DD")
    ap.add_argument("--out", default="data/derived")
    args = ap.parse_args()

    teams = pd.read_csv(ARCHIVE / "teams.csv")
    teams["ladder_score"] = pd.to_numeric(teams.ladder_score, errors="coerce")
    top = teams.dropna(subset=["ladder_score"]).sort_values("ladder_score", ascending=False)
    top_rows = top.head(args.top)
    name_of = dict(zip(top.team_id, top.team_name))
    print("top teams by ladder_score:")
    for r in top_rows.itertuples():
        print(f"  {r.ladder_score:8.1f}  {r.team_id}  {r.team_name}")

    eps = pd.read_csv(ARCHIVE / "episodes.csv")
    eps = eps[eps.type.eq("EPISODE_TYPE_PUBLIC") & eps.state.eq("COMPLETED")
              & eps.team_0.ne(eps.team_1)]
    if args.since:
        eps = eps[eps.end_time.astype(str) >= args.since]
    eps = eps.sort_values("end_time", ascending=False)

    pf = pq.ParquetFile(ARCHIVE / "replays.parquet")
    in_parquet = set(pf.read(columns=["episode_id"]).to_pandas()["episode_id"].tolist())
    # raw/ holds the current crawl's downloads, not yet folded into the parquet by
    # repack.py. Reading it directly means a targeted fetch (analysis/b0_fetch_top_replays.py)
    # is usable immediately instead of after a 640 MB rewrite.
    in_raw = {int(p.name.split(".")[0]): p for p in (ARCHIVE / "raw").glob("*.json.gz")}
    have = in_parquet | set(in_raw)
    print(f"replays on hand: {len(have)} ({len(in_raw)} of them un-packed in raw/)   "
          f"candidate ladder episodes: {len(eps)}")

    wanted: dict = {}            # episode_id -> list[(seat, team_id)]
    per_team_count: dict = defaultdict(int)
    for row in eps.itertuples():
        if row.episode_id not in have:
            continue
        for seat, team in ((0, row.team_0), (1, row.team_1)):
            if team in set(top_rows.team_id) and per_team_count[team] < args.per_team:
                wanted.setdefault(row.episode_id, []).append((seat, team))
                per_team_count[team] += 1
    print("episodes matched per team:")
    for r in top_rows.itertuples():
        print(f"  {name_of.get(r.team_id, r.team_id)}: {per_team_count[r.team_id]}")
    if not wanted:
        print("\nNo replays for the current top teams in data/archive — rerun scrape.py first.")
        return

    by_team: dict = defaultdict(list)
    parsed = 0

    def consume(eid: int, replay: dict) -> None:
        nonlocal parsed
        for seat, team in wanted[eid]:
            by_team[team].append({"episode_id": eid, "seat": seat,
                                  **profile_seat(replay, seat)})
        parsed += 1
        if parsed % 10 == 0:
            print(f"  parsed {parsed}/{len(wanted)} episodes", flush=True)

    for eid, path in in_raw.items():
        if eid in wanted:
            consume(eid, json.loads(gzip.decompress(path.read_bytes()).decode()))
    if any(e in in_parquet for e in wanted):
        for batch in pf.iter_batches(batch_size=8, columns=["episode_id", "replay_json"]):
            tbl = batch.to_pydict()
            for eid, blob in zip(tbl["episode_id"], tbl["replay_json"]):
                if eid in wanted and eid not in in_raw:
                    consume(eid, json.loads(blob))

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    summary = {}
    for team, rows in by_team.items():
        agg = {"team_id": int(team), "team_name": name_of.get(team), "episodes": len(rows),
               "final_money_median": median([r["final_money"] for r in rows])}
        for field in ("money_at", "tiles_at", "hands_at", "animals_at"):
            keys = sorted({k for r in rows for k in r[field]})
            agg[field] = {k: median([r[field].get(k) for r in rows]) for k in keys}
        agg["animals_peak"] = {sp: median([r["animals_peak"].get(sp, 0) for r in rows])
                               for sp in ("COW", "SHEEP", "GOOSE")}
        agg["quadrants_final"] = median([r["quadrants_final"] for r in rows])
        agg["first_quadrant_day"] = {
            q: median([r["first_quadrant_day"].get(q) for r in rows
                       if r["first_quadrant_day"].get(q) is not None])
            for q in (2, 3, 4)}
        agg["first_animal_day"] = {
            sp: median([r["first_animal_day"].get(sp) for r in rows
                        if r["first_animal_day"].get(sp) is not None])
            for sp in ("COW", "SHEEP", "GOOSE")}
        prods = sorted({k for r in rows for k in r["tile_days"]}
                       | {k for r in rows for k in r["revenue"]})
        agg["per_product"] = {}
        for p in prods:
            td = median([r["tile_days"].get(p, 0) for r in rows])
            rv = median([r["revenue"].get(p, 0) for r in rows])
            agg["per_product"][p] = {
                "tile_days": td, "revenue": rv,
                "dollars_per_tile_day": round(rv / td, 1) if td else None,
                "first_sell_day": median([r["first_sell_day"].get(p) for r in rows
                                          if p in r["first_sell_day"]]),
                "batch_median": median([r["batch_median"].get(p) for r in rows
                                        if p in r["batch_median"]]),
                "sell_orders": median([r["sell_orders"].get(p, 0) for r in rows]),
                "units_sold": median([r["units_sold"].get(p, 0) for r in rows]),
            }
        summary[str(team)] = agg

    (out_dir / "b1_top5_profile.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    print(f"\nwrote {out_dir / 'b1_top5_profile.json'}")

    for team, agg in sorted(summary.items(), key=lambda kv: -(kv[1]["final_money_median"] or 0)):
        print(f"\n=== {agg['team_name']} ({agg['episodes']} eps) "
              f"final ${agg['final_money_median']:,.0f}")
        print(f"  money   {agg['money_at']}")
        print(f"  tiles   {agg['tiles_at']}")
        print(f"  hands   {agg['hands_at']}   quadrants {agg['quadrants_final']} "
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
