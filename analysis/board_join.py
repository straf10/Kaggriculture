"""Board-join utilities — one implementation for the entire codebase.

Extracted from `s7_ladder_census.py::leg_c` (S11 B1.1) so that both the S7 census
and the S10 bench manifest share the same snapshot loading, timestamp parsing, and
closest-board matching.  Every leaderboard snapshot on disk is registered here.

Public API
----------
board_at(episode_time)  — team → (rank, score, last_sub_dt) from the closest snapshot.
rating_zone(score)      — the S10 P1.3 zone string for a board score.
episode_times(submission) — episode_id → naive-UTC datetime from the episodes CSV.
"""
from __future__ import annotations

import csv
import datetime as dt
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "archive" / "raw"

_SNAPSHOT_REGISTRY: list[tuple[str, str]] = [
    ("2026-08-18T10:04:36",
     "live_leaderboard_2026-08-18/kaggriculture-publicleaderboard-2026-08-18T10:04:36.csv"),
    ("2026-08-20T10:57:31",
     "live_leaderboard_2026-08-20/kaggriculture-publicleaderboard-2026-08-20T10:57:31.csv"),
    ("2026-08-23T08:36:50",
     "live_leaderboard_2026-08-23/kaggriculture-publicleaderboard-2026-08-23T08:36:50.csv"),
    ("2026-08-24T21:32:15",
     "live_leaderboard_2026-08-24/kaggriculture-publicleaderboard-2026-08-24T21:32:15.csv"),
    ("2026-08-25T12:08:46",
     "live_leaderboard_2026-08-24/kaggriculture-publicleaderboard-2026-08-25T12:08:46.csv"),
]

_EPISODES_CSV = {
    "55586926": RAW / "live_55586926_episodes.csv",
    "55675634": RAW / "live_55675634_episodes.csv",
    "55726984": ROOT / "data" / "derived" / "s9_live_55726984_episodes.csv",
}

RATING_EDGES = [
    (0,    1500, "<1500"),
    (1500, 1700, "1500-1700"),
    (1700, 1900, "1700-1900"),
    (1900, 2100, "1900-2100"),
    (2100, 2400, "2100-2400"),
    (2400, 1e9,  "2400+"),
]


def _to_naive_utc(s: str) -> dt.datetime:
    """Parse an ISO timestamp to a naive-UTC datetime."""
    s = s.split(".")[0].rstrip("Z")
    d = dt.datetime.fromisoformat(s)
    if d.tzinfo is not None:
        d = d.astimezone(dt.timezone.utc).replace(tzinfo=None)
    return d


def _load_lb(path: Path) -> list[dict]:
    rows = []
    with open(path, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            rows.append({
                "rank": int(r["Rank"]),
                "team_id": r["TeamId"],
                "team": r["TeamName"],
                "last_sub": r["LastSubmissionDate"],
                "score": float(r["Score"]),
            })
    rows.sort(key=lambda r: r["rank"])
    return rows


_snapshots_cache: list[tuple[dt.datetime, dict[str, tuple[int, float, dt.datetime]]]] | None = None


def _load_snapshots() -> list[tuple[dt.datetime, dict[str, tuple[int, float, dt.datetime]]]]:
    global _snapshots_cache
    if _snapshots_cache is not None:
        return _snapshots_cache
    snaps = []
    for ts_str, rel in _SNAPSHOT_REGISTRY:
        p = RAW / rel
        if not p.exists():
            continue
        snap_dt = _to_naive_utc(ts_str)
        board: dict[str, tuple[int, float, dt.datetime]] = {}
        for r in _load_lb(p):
            board[r["team"]] = (r["rank"], r["score"], _to_naive_utc(r["last_sub"]))
        snaps.append((snap_dt, board))
    _snapshots_cache = snaps
    return snaps


def board_at(episode_time: dt.datetime) -> dict[str, tuple[int, float, dt.datetime]]:
    """Return team → (rank, score, last_sub_naive_utc) from the closest snapshot."""
    snaps = _load_snapshots()
    if not snaps:
        return {}
    return min(snaps, key=lambda sb: abs((sb[0] - episode_time).total_seconds()))[1]


def rating_zone(score) -> str | None:
    if score is None:
        return None
    s = float(score)
    for lo, hi, label in RATING_EDGES:
        if lo <= s < hi:
            return label
    return None


def episode_times(submission: str) -> dict[int, dt.datetime]:
    """episode_id → naive-UTC createTime from the episodes CSV."""
    p = _EPISODES_CSV.get(submission)
    if p is None or not p.exists():
        return {}
    result = {}
    with open(p, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            if (r.get("id") or "").isdigit():
                result[int(r["id"])] = _to_naive_utc(r["createTime"])
    return result


def invalidate_cache():
    """For testing — force snapshots to reload."""
    global _snapshots_cache
    _snapshots_cache = None
