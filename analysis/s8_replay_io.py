#!/usr/bin/env python3
"""S8 — the replay-read contract, written ONCE (docs/plans/s8_submission_analysis_tasks.md §1).

Both live submissions store their episodes as `episode-<id>-replay.json` under
`data/archive/raw/live_<submission>/` — a different layout from the S6 `2026-08-16`
archive, so `s6_step1_phase0._reload_streams` (path-bound to that archive) cannot be
reused directly. Everything else is reused: `_seat_streams` and `_realised_premium`
are imported from `s6_step1_phase0` so there is exactly one parser and one premium
meter in the codebase (§1.2 / §1.4).

Alignment (verified 2026-08-22, §1.2):  stream[i] == steps[i+1][seat]["action"]  (i=0..718).
`steps[0]` is the spec default (PASS), never a decision. `_seat_streams` already reads
`steps[1:]`, so it yields the 719 decisions in `obs["step"]` order — the exact numbering
`make_tape_agent` serves.

Exclusions (§1.3), collapsed to ONE test after inspecting disk 2026-08-23:
  the sole mirror on disk (STRAF-vs-STRAF) IS the EPISODE_TYPE_VALIDATION episode —
  `55586926/94042083` carries `seed==0` and `TeamNames==["STRAF","STRAF"]`. So
  `is_excluded()` drops any replay with a STRAF-mirror OR seed==0. On disk this removes
  exactly 1 from 55586926 (→178 ladder) and 0 from 55675634 (→75 ladder), matching §1.4.
"""
from __future__ import annotations

import glob
import gzip
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# Reuse the one parser + the one premium meter (§1.2, §1.4). Do NOT write a second.
from analysis.s6_step1_phase0 import _seat_streams, _realised_premium  # noqa: E402

RAW = ROOT / "data" / "archive" / "raw"
OUR_TEAM = "STRAF"

SUBMISSIONS = {
    "55586926": RAW / "live_55586926",
    "55675634": RAW / "live_55675634",
    "55726984": RAW / "live_55726984",
}

# Extra directories (secondary downloads that were saved separately). Contents are merged
# into the parent submission's replay set; duplicates collapse by episode id.
_EXTRA_DIRS = {
    "55586926": [RAW / "live_55586926_fresh"],
    "55675634": [RAW / "live_55675634_fresh"],
}


def replay_paths(submission: str) -> list[Path]:
    """All replay files for a submission, sorted by episode id ASCENDING.

    Reads the primary directory and any registered `_fresh` sibling(s), deduping by
    episode id (keep the first occurrence, primary dir first). Accepts both
    `episode-*-replay.json` and `episode-*-replay.json.gz` (P0.6).
    """
    seen: dict[int, Path] = {}
    for d in [SUBMISSIONS[submission], *_EXTRA_DIRS.get(submission, [])]:
        if not d.exists():
            continue
        for pat in ("episode-*-replay.json", "episode-*-replay.json.gz"):
            for p in glob.glob(str(d / pat)):
                eid = _eid_from_name(Path(p))
                seen.setdefault(eid, Path(p))
    return sorted(seen.values(), key=lambda p: _eid_from_name(p))


def _eid_from_name(p: Path) -> int:
    # episode-<id>-replay.json
    return int(p.name.split("-")[1])


def load(path: Path) -> dict:
    if str(path).endswith(".gz"):
        with gzip.open(path, "rt") as f:
            return json.load(f)
    return json.loads(path.read_text())


def meta(d: dict) -> dict:
    info = d["info"]
    teams = info.get("TeamNames") or [None, None]
    rewards = d.get("rewards") or [None, None]
    return {
        "episode_id": info.get("EpisodeId"),
        "teams": teams,
        "rewards": [float(r) if r is not None else None for r in rewards],
        "seed": info.get("seed"),
        "n_steps": len(d["steps"]),
        "steps": d["steps"],
        "configuration": d.get("configuration", {}),
    }


def is_excluded(m: dict) -> tuple[bool, str]:
    """(excluded?, reason). Drops mirror/validation (§1.3). One test covers both on disk."""
    if m["teams"] == [OUR_TEAM, OUR_TEAM]:
        return True, "mirror/validation (STRAF v STRAF)"
    if m["seed"] == 0:
        return True, "validation (seed==0)"
    return False, ""


def our_seat(teams: list) -> int | None:
    """Seat index of STRAF among two distinct teams; None if neither/both (caller excludes both)."""
    seats = [i for i, n in enumerate(teams) if n == OUR_TEAM]
    return seats[0] if len(seats) == 1 else None


def opponent_clean(steps: list, seat: int) -> bool:
    """True iff the given seat's status is never a death/error over the whole episode.

    ACTIVE while playing, DONE/INACTIVE at the tail is clean; anything else (an opponent
    that crashed mid-episode) is not a real opponent (§4 Task 3). `_seat_streams` returns
    the per-step status list as its 3rd element."""
    _p, _m, status = _seat_streams(steps, seat)
    return set(status) <= {"ACTIVE", "DONE", "INACTIVE"}


def ladder_episodes(submission: str):
    """Yield (episode_id, meta_dict) for the ladder episodes of a submission, id-ascending,
    mirror/validation excluded. meta_dict carries steps+configuration for downstream use."""
    for p in replay_paths(submission):
        d = load(p)
        m = meta(d)
        excl, _reason = is_excluded(m)
        if excl:
            continue
        yield m["episode_id"], m
