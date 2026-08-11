#!/usr/bin/env python3
"""B0 — targeted replay fetch for the *current* top-N ladder teams.

`data/archive/scrape.py` downloads whatever is missing in insertion order, which in
practice means the oldest un-fetched episodes. For Phase B we want the opposite: the
newest games of the handful of teams at the top of today's leaderboard. This script
reads the already-crawled `episodes.csv` metadata, picks those teams' most recent
public completed episodes, and pulls just those replays from the same public CDN
`scrape.py` uses — a few dozen requests instead of thousands.

Replays land in `data/archive/raw/` (gzipped, same layout as scrape.py), so the next
`repack.py` run folds them into `replays.parquet` normally. Nothing here parses
actions; it only fetches.

Usage:
    python analysis/b0_fetch_top_replays.py --top 5 --per-team 12 [--since 2026-08-05]
"""
from __future__ import annotations

import argparse
import gzip
import time
from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq
import requests

ARCHIVE = Path(__file__).resolve().parent.parent / "data" / "archive"
RAW = ARCHIVE / "raw"
REPLAY_URL = "https://www.kaggleusercontent.com/episodes/{id}.json"


def _session() -> requests.Session:
    s = requests.Session()
    s.headers["User-Agent"] = "kaggriculture-dataset-builder (georgymamarin)"
    return s


def _already_local() -> set[int]:
    have = set()
    if (ARCHIVE / "replays.parquet").exists():
        have = set(pq.read_table(ARCHIVE / "replays.parquet",
                                 columns=["episode_id"])["episode_id"].to_pylist())
    return have | {int(p.name.split(".")[0]) for p in RAW.glob("*.json.gz")}


def fetch_ids(args) -> None:
    """Fetch an explicit id list — e.g. the official daily top-episode dataset.

    Newest last in that listing, so --limit takes from the end.
    """
    ids = [int(x) for x in Path(args.ids_file).read_text().split()]
    if args.limit:
        ids = ids[-args.limit:]
    have = _already_local()
    todo = [i for i in ids if i not in have]
    print(f"{len(ids)} ids requested, {len(ids) - len(todo)} already local, {len(todo)} to fetch")
    session, got, missing = _session(), 0, 0
    for eid in todo:
        r = session.get(REPLAY_URL.format(id=eid), timeout=180)
        if r.status_code == 200 and r.content:
            (RAW / f"{eid}.json.gz").write_bytes(gzip.compress(r.content, 6))
            got += 1
        else:
            missing += 1
        if got and got % 10 == 0:
            print(f"  {got} downloaded", flush=True)
        time.sleep(0.5)
    print(f"downloaded {got}, unavailable {missing}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--top", type=int, default=5)
    ap.add_argument("--per-team", type=int, default=12)
    ap.add_argument("--since", default=None, help="only episodes ending on/after YYYY-MM-DD")
    ap.add_argument("--ids-file", default=None,
                    help="newline-separated episode ids to fetch instead of the team query. "
                         "Use with the official daily dataset listing "
                         "(kaggle datasets files kaggle/kaggriculture-episodes-YYYY-MM-DD), "
                         "which is the only source guaranteed to be on the current engine.")
    ap.add_argument("--limit", type=int, default=None, help="cap on ids fetched from --ids-file")
    args = ap.parse_args()

    RAW.mkdir(exist_ok=True)
    if args.ids_file:
        return fetch_ids(args)
    teams = pd.read_csv(ARCHIVE / "teams.csv")
    teams["ladder_score"] = pd.to_numeric(teams.ladder_score, errors="coerce")
    top = teams.dropna(subset=["ladder_score"]).sort_values(
        "ladder_score", ascending=False).head(args.top)
    name_of = dict(zip(top.team_id, top.team_name))
    print("target teams:")
    for r in top.itertuples():
        print(f"  {r.ladder_score:8.1f}  {r.team_id}  {r.team_name}")

    eps = pd.read_csv(ARCHIVE / "episodes.csv")
    eps = eps[eps.type.eq("EPISODE_TYPE_PUBLIC") & eps.state.eq("COMPLETED")
              & eps.team_0.ne(eps.team_1)]
    if args.since:
        eps = eps[eps.end_time.astype(str) >= args.since]
    eps = eps.sort_values("end_time", ascending=False)

    have = set()
    if (ARCHIVE / "replays.parquet").exists():
        have = set(pq.read_table(ARCHIVE / "replays.parquet",
                                 columns=["episode_id"])["episode_id"].to_pylist())
    on_disk = {int(p.name.split(".")[0]) for p in RAW.glob("*.json.gz")}

    wanted: list[tuple[int, int, str]] = []       # (episode_id, team_id, end_time)
    for team in top.team_id:
        mine = eps[(eps.team_0 == team) | (eps.team_1 == team)]
        picked = 0
        for row in mine.itertuples():
            if picked >= args.per_team:
                break
            wanted.append((int(row.episode_id), int(team), str(row.end_time)))
            picked += 1
        newest = mine.end_time.max() if len(mine) else "—"
        print(f"  {name_of.get(team, team)}: {len(mine)} known episodes, "
              f"queued {picked}, newest {newest}")

    todo = [w for w in wanted if w[0] not in have and w[0] not in on_disk]
    print(f"\n{len(wanted)} queued, {len(wanted) - len(todo)} already local, "
          f"{len(todo)} to download")

    session = requests.Session()
    session.headers["User-Agent"] = "kaggriculture-dataset-builder (georgymamarin)"
    got = missing = 0
    for eid, team, _ in todo:
        r = session.get(REPLAY_URL.format(id=eid), timeout=180)
        if r.status_code == 200 and r.content:
            (RAW / f"{eid}.json.gz").write_bytes(gzip.compress(r.content, 6))
            got += 1
        else:
            missing += 1
            print(f"  episode {eid} ({name_of.get(team, team)}): "
                  f"unavailable (HTTP {r.status_code})")
        if got and got % 10 == 0:
            print(f"  {got} downloaded", flush=True)
        time.sleep(0.8)
    print(f"\ndownloaded {got}, unavailable {missing}. "
          f"Run data/archive/repack.py to fold them into replays.parquet.")


if __name__ == "__main__":
    main()
