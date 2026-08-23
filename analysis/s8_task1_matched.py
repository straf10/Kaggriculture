#!/usr/bin/env python3
"""S8 Task 1 — the three numbers in matched windows (docs/plans/... §2).

254 converged vs 75 in-burst do not compare. So compare the FIRST 75 ladder episodes of
55586926 (A_matched) against the 75 of 55675634 (B_matched); both started at 600,1, both
inside placement. A_full (all 178 on disk) is reported as CONTEXT ONLY, never as B's opponent.

The three numbers per window:
  1. count (ladder, mirror/validation excluded)              — exact
  2. W/L/D total AND per seat (seats are NOT symmetric, §2.2) — exact
  3. W/L per OPPONENT-RATING zone                             — proxy (§2.3, team rating)

Rating is a *team* score from the nearest leaderboard snapshot, not a per-submission or
per-episode rating (the replay stores no opponent rating). Three mandatory captions are
emitted verbatim into the JSON so the report cannot drop them (§2.3):
  (1) team rating, not submission — diagnostic, not decision;
  (2) match coverage — unmatched opponents go to `unknown`, never to <1800;
  (3) the burst raises the zone within one window — W/L is also cut into thirds.

Output: data/derived/s8_task1_matched.json (gitignored).
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from analysis import s8_replay_io as io  # noqa: E402

RAW = ROOT / "data" / "archive" / "raw"
OUT = ROOT / "data" / "derived" / "s8_task1_matched.json"

# Window -> leaderboard snapshot of the SAME AGE (§2.3), cancelling most deflation.
SNAP_A = RAW / "live_leaderboard_2026-08-18" / "kaggriculture-publicleaderboard-2026-08-18T10:04:36.csv"
SNAP_B = RAW / "live_leaderboard_2026-08-23" / "kaggriculture-publicleaderboard-2026-08-23T08:36:50.csv"

ZONES = ("<1800", "1800-2100", "2100+")


def zone_of(score: float) -> str:
    if score < 1800:
        return "<1800"
    if score < 2100:
        return "1800-2100"
    return "2100+"


def load_snapshot(path: Path) -> dict[str, float]:
    """TeamName -> Score. Rank column carries a BOM; utf-8-sig is mandatory (§2.3 / pitfall 3)."""
    out: dict[str, float] = {}
    with path.open(encoding="utf-8-sig") as fh:
        for row in csv.DictReader(fh):
            name = row.get("TeamName")
            try:
                out[name] = float(row["Score"])
            except (TypeError, ValueError, KeyError):
                continue
    return out


def analyse(submission: str, limit: int | None, snapshot: dict[str, float]) -> dict:
    total = {"W": 0, "L": 0, "D": 0}
    per_seat = {0: {"W": 0, "L": 0, "D": 0}, 1: {"W": 0, "L": 0, "D": 0}}
    by_zone = {z: {"W": 0, "L": 0, "D": 0} for z in ZONES}
    by_zone["unknown"] = {"W": 0, "L": 0, "D": 0}
    thirds = {"1-25": {"W": 0, "L": 0, "D": 0},
              "26-50": {"W": 0, "L": 0, "D": 0},
              "51-75": {"W": 0, "L": 0, "D": 0}}
    matched = unmatched = 0
    unmatched_names: list[str] = []
    opp_scores: list[float] = []
    rows = []

    eps = list(io.ladder_episodes(submission))
    if limit is not None:
        eps = eps[:limit]

    for idx, (eid, m) in enumerate(eps, start=1):
        seat = io.our_seat(m["teams"])
        us, opp = m["rewards"][seat], m["rewards"][1 - seat]
        res = "W" if us > opp else ("L" if us < opp else "D")
        total[res] += 1
        per_seat[seat][res] += 1
        opp_team = m["teams"][1 - seat]
        sc = snapshot.get(opp_team)
        if sc is None:
            unmatched += 1
            unmatched_names.append(opp_team)
            zone = "unknown"
        else:
            matched += 1
            opp_scores.append(sc)
            zone = zone_of(sc)
        by_zone[zone][res] += 1
        third = "1-25" if idx <= 25 else ("26-50" if idx <= 50 else "51-75")
        thirds[third][res] += 1
        rows.append({"episode_id": eid, "seat": seat, "result": res,
                     "bank_us": us, "bank_opp": opp, "opponent": opp_team,
                     "opp_score": sc, "zone": zone})

    n = len(eps)
    wr = (total["W"] / (total["W"] + total["L"])) if (total["W"] + total["L"]) else None
    opp_scores.sort()
    med = opp_scores[len(opp_scores) // 2] if opp_scores else None
    return {
        "submission": submission,
        "n_episodes": n,
        "win_rate_excl_draw": wr,
        "wld_total": total,
        "wld_per_seat": {"seat0": per_seat[0], "seat1": per_seat[1]},
        "wld_by_zone": by_zone,
        "wld_by_third": thirds,
        "match_coverage": {"matched": matched, "unmatched": unmatched,
                           "unmatched_names": sorted(set(unmatched_names))},
        "opp_score_median_matched": med,
        "opp_score_min_matched": opp_scores[0] if opp_scores else None,
        "opp_score_max_matched": opp_scores[-1] if opp_scores else None,
        "episodes": rows,
    }


def main() -> int:
    snap_a = load_snapshot(SNAP_A)
    snap_b = load_snapshot(SNAP_B)
    print(f"snapshot A (08-18): {len(snap_a)} teams   snapshot B (08-23): {len(snap_b)} teams")

    result = {
        "captions": {
            "1_team_not_submission": (
                "Rating is TEAM rating, not submission. Each team has up to 2 active "
                "submissions at different ratings; we may have faced the weaker one. A cut "
                "that does not name a submission is diagnostic, not a decision (§2 rule 5)."),
            "2_match_coverage": (
                "Opponents not found in the snapshot (new teams, renames) go to the `unknown` "
                "bucket, NEVER to <1800."),
            "3_burst_raises_zone": (
                "The burst raises the opponent zone within one window (median opponent rose "
                "~1212 -> ~1950 across the burst, §2 rule 2); W/L is also reported in thirds "
                "1-25 / 26-50 / 51-75 to show the ramp."),
        },
        "windows": {
            # A_matched: first 75 ladder of 55586926, read with the same-age 08-18 snapshot
            "A_matched": analyse("55586926", 75, snap_a),
            # B_matched: all 75 of 55675634, read with the 08-23 snapshot
            "B_matched": analyse("55675634", None, snap_b),
            # A_full: all 178 on disk, CONTEXT ONLY — never B's opponent (§2.1)
            "A_full_context_only": analyse("55586926", None, snap_a),
        },
        "same_age_score": {
            "note": (
                "55586926 uploaded 08-17 22:29; the 08-18 10:04 snapshot is age ~11,6 h and "
                "shows TEAM 1912,8 / rank 939. That 1912,8 is a TEAM score = max of "
                "{Ueddy 55575305, 55586926}; Ueddy's final was 1268,0 < 1912,8, so 1912,8 is "
                "attributable to 55586926 (rationale stated, not assumed). 55675634 at the same "
                "~11,6 h age: see the §0 submission snapshots (subs_*.txt)."),
            "team_55586926_at_age_11.6h": {"score": 1912.8, "rank": 939, "snapshot": "2026-08-18T10:04"},
            "ueddy_55575305_final": 1268.0,
        },
        "paired_cut_dead": {
            "note": (
                "The paired-opponent cut is DEAD (§2.4, n=2). Kaggle pairs by rating; the two "
                "submissions sit in different neighbourhoods, so only 2 opponents ever played "
                "both. Footnote only, never an indicator."),
            "shared_opponents_n": 2,
            "shared_opponents": ["Salut!", "Tim Zagrebelny"],
        },
    }
    OUT.write_text(json.dumps(result, indent=1))

    for wname in ("A_matched", "B_matched", "A_full_context_only"):
        w = result["windows"][wname]
        t = w["wld_total"]
        print(f"\n{wname}: n={w['n_episodes']}  W/L/D {t['W']}-{t['L']}-{t['D']}  "
              f"winrate {w['win_rate_excl_draw']:.3f}" if w["win_rate_excl_draw"] is not None
              else f"\n{wname}: n={w['n_episodes']}")
        print(f"  seat0 {w['wld_per_seat']['seat0']}  seat1 {w['wld_per_seat']['seat1']}")
        print(f"  zones: " + "  ".join(f"{z} {w['wld_by_zone'][z]['W']}-{w['wld_by_zone'][z]['L']}"
                                        for z in ZONES) +
              f"  unknown {w['wld_by_zone']['unknown']['W']}-{w['wld_by_zone']['unknown']['L']}")
        print(f"  thirds: " + "  ".join(f"{k} {v['W']}-{v['L']}" for k, v in w["wld_by_third"].items()))
        c = w["match_coverage"]
        print(f"  coverage: matched {c['matched']} / unmatched {c['unmatched']}  "
              f"opp_score med {w['opp_score_median_matched']}")
    print(f"\nwrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
