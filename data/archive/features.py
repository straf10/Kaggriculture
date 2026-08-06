#!/usr/bin/env python3
"""Extracts per-seat behavioral features from every replay into episode_features.csv.

The point of the table: replay JSONs are heavy, and questions like "how big a crew
does the winner run" should not require parsing gigabytes. One row per (episode, seat).
Hires come from farm state (hires_today), not submitted HIRE orders — the engine
rejects orders once money runs short, so orders overcount.
"""
import csv
import json
from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq

HERE = Path(__file__).parent
PARQUET = HERE / "replays.parquet"
OUT = HERE / "episode_features.csv"


def features(episode_id, replay):
    steps = replay["steps"]
    rows = []
    # market prices are shared between seats; summarize once per episode
    prices = {}
    for s in steps:
        for prod, price in s[0]["observation"]["market"]["prices"].items():
            lo, hi = prices.get(prod, (price, price))
            prices[prod] = (min(lo, price), max(hi, price))
    for seat in (0, 1):
        crops, first_land, peak_crew, hires_by_day = {}, None, 0, {}
        money = []
        for t, step in enumerate(steps):
            farm = step[0]["observation"]["farms"][seat]
            day = t // 24
            money.append(farm["money"])
            hires_by_day[day] = max(hires_by_day.get(day, 0), farm["hires_today"])
            peak_crew = max(peak_crew, len(farm["hands"]))
            a = step[seat].get("action") or {}
            for order in (a.get("market") or []):
                if isinstance(order, list) and order and order[0] == "BUY_LAND" \
                        and first_land is None:
                    first_land = day
            for unit in [a.get("farmer") or []] + list(a.get("hands") or []):
                if isinstance(unit, list) and unit and unit[0] == "PLANT" and len(unit) > 1:
                    crops[unit[1]] = crops.get(unit[1], 0) + 1
        final = money[-1] if money else None
        elbow = None
        if final and final > 0:
            cross = next((t for t, m in enumerate(money) if m > final * .1), None)
            elbow = None if cross is None else cross // 24
        row = {"episode_id": episode_id, "seat": seat, "final_money": final,
               "peak_crew": peak_crew, "total_hires": sum(hires_by_day.values()),
               "first_land_day": first_land, "elbow_day": elbow,
               "tiles_planted": sum(crops.values())}
        for c, n in crops.items():            # crop vocabulary comes from the data
            row[f"plants_{c.lower()}"] = n
        for prod, (lo, hi) in sorted(prices.items()):
            row[f"price_{prod.lower()}_min"] = lo
            row[f"price_{prod.lower()}_max"] = hi
        rows.append(row)
    return rows


def main():
    have = {}
    if OUT.exists():        # incremental: keep rows for episodes already done
        old = pd.read_csv(OUT)
        have = {int(e) for e in old.episode_id.unique()}
    pf = pq.ParquetFile(PARQUET)
    new_rows, done = [], 0
    for batch in pf.iter_batches(batch_size=20):
        tbl = batch.to_pydict()
        for eid, blob in zip(tbl["episode_id"], tbl["replay_json"]):
            if eid in have:
                continue
            try:
                new_rows.extend(features(eid, json.loads(blob)))
            except Exception as e:
                print(f"  episode {eid}: skipped ({e})")
            done += 1
            if done % 50 == 0:
                print(f"  parsed {done} new replays")
    if have and not new_rows:
        print(f"episode_features.csv: up to date ({len(have)} episodes)")
        return
    new = pd.DataFrame(new_rows)
    out = pd.concat([old, new], ignore_index=True) if have else new
    out = out.sort_values(["episode_id", "seat"])
    plant_cols = [c for c in out.columns if c.startswith("plants_")]
    out[plant_cols] = out[plant_cols].fillna(0).astype(int)
    lead = ["episode_id", "seat", "final_money", "peak_crew", "total_hires",
            "first_land_day", "elbow_day", "tiles_planted"]
    out = out[lead + sorted(plant_cols) + sorted(c for c in out.columns
                                                 if c.startswith("price_"))]
    out.to_csv(OUT, index=False)
    print(f"episode_features.csv: {out.episode_id.nunique()} episodes, {len(out)} rows, "
          f"{len(out.columns)} columns")


def write_daily_stats(here):
    """daily_stats.csv: one row per UTC day — the meta's longitudinal series.
    Everything derives from episodes.csv, so the whole history rebuilds every run."""
    import pandas as pd
    eps = pd.read_csv(here / "episodes.csv")
    eps["end"] = pd.to_datetime(eps.end_time, format="mixed", utc=True)
    eps["winner_bank"] = eps[["bank_0", "bank_1"]].max(axis=1)
    lad = eps[eps.type.eq("EPISODE_TYPE_PUBLIC") & eps.state.eq("COMPLETED")
              & eps.winner_bank.gt(0)].copy()
    lad["day"] = lad.end.dt.date
    feats = here / "episode_features.csv"
    have_replay = set()
    if feats.exists():
        have_replay = set(pd.read_csv(feats).episode_id.unique())
    rows = []
    for day, g in lad.groupby("day"):
        rows.append({
            "date": day, "ladder_games": len(g),
            "teams_active": pd.unique(g[["team_0", "team_1"]].values.ravel()).size,
            "median_winner_bank": round(g.winner_bank.median(), 1),
            "p90_winner_bank": round(g.winner_bank.quantile(.9), 1),
            "record_bank": g.winner_bank.max(),
            "replay_coverage": round(g.episode_id.isin(have_replay).mean(), 3),
        })
    pd.DataFrame(rows).to_csv(here / "daily_stats.csv", index=False)
    print(f"daily_stats.csv: {len(rows)} days")


if __name__ == "__main__":
    main()
    write_daily_stats(HERE)
