#!/usr/bin/env python3
"""S7 leg 1 — extract the deployment-neighbourhood bench from our own live replays.

Every gate in this repo scored the reconstruction against arms it has never lost to on the
ladder (own lineage, `meta_route`, six reference tiers, three donor tapes). Leg 0 established
that the ~1.036-pt gap to ReCurSiON is real strength measured against 1.800-2.500 opponents at
a **43,4%** converged win rate, and that the live ladder is judged in *wins* against
*opponents we actually meet*. **We now hold 178 replays containing both seats' full action
streams for 165 distinct opponent teams in exactly the band where we lose.**

This script — an S1-style extractor for our own live replays instead of the top-of-ladder
donors — does two things and nothing else (§4.3 S7 leg 1):

  1. For every held live replay of `55586926` (excluding STRAF-vs-STRAF validation), pull the
     opponent's full 719-action stream (matching the format `analysis/donor_streams.py` and
     `analysis/s1_extract_donors.py` write), sha256 it, and record provenance
     `(episode_id, seat, team, sha256, config, opp_recorded_bank, our_recorded_bank)`. The
     stream itself is competition data (§2.4b / R11) — held **gitignored** under
     `data/derived/s7_leg1_bench/`. Only the manifest (no stream bytes) is emitted alongside.

  2. Verify each stream stands on its own by replaying it against a fixed neutral opponent
     (`checkpoints/v1u_base/main.py` at seed=0), and flag the ones that either error out or
     collapse to a **no-op parade** — the failure mode the brief pre-registered. Retention
     figure is reported per stratum, as S2 did for the three donor tapes.

Opponent stratum uses leg 0's `--controlled` rule (R36 replacement): the team's current board
score is the score that played us only if `LastSubmissionDate` predates our episode; teams that
re-submitted since are dropped (leg 0 measured 26% re-submission in 2 days). Bands:
**1.800-2.100** and **2.100+** are the two strata leg 2 will actually score against — the
converged-regime bands that carry the loss.

Reads: `data/archive/raw/live_55586926/*.json`, `data/archive/raw/live_55586926_episodes.csv`,
`data/archive/raw/live_leaderboard_2026-08-20/...csv`. Writes (all gitignored, §2.4b / R11):
`data/derived/s7_leg1_bench/*.json` (per-opponent stream + provenance) and
`data/derived/s7_leg1_bench_manifest.json` (the roll-up + verdict string, R35).

No `agent/` change. No episode played on Kaggle. No upload (R27).

Usage:
    python analysis/s7_leg1_bench.py extract               # sha + provenance, no episodes
    python analysis/s7_leg1_bench.py verify [--sample N]   # play each tape vs v1u_base
    python analysis/s7_leg1_bench.py report                # print the manifest
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import gzip
import hashlib
import json
import statistics
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from analysis.tape_agent import make_tape_agent  # noqa: E402
from harness.play import play  # noqa: E402

LIVE = ROOT / "data" / "archive" / "raw" / "live_55586926"
EP_CSV = ROOT / "data" / "archive" / "raw" / "live_55586926_episodes.csv"
LB_CSV = (ROOT / "data" / "archive" / "raw" / "live_leaderboard_2026-08-20"
          / "kaggriculture-publicleaderboard-2026-08-20T10:57:31.csv")
DERIVED = ROOT / "data" / "derived"
BENCH_DIR = DERIVED / "s7_leg1_bench"
MANIFEST = DERIVED / "s7_leg1_bench_manifest.json"

OUR_TEAM = "STRAF"
NEUTRAL_OPP = "checkpoints/v1u_base/main.py"
NEUTRAL_SEED = 0
COLLAPSE_FLOOR = 5000.0  # a tape that banks less than $5k against v1u_base is a no-op parade
PASS_ACTION = {"farmer": ["PASS"], "hands": [], "market": []}


def _sha256(stream: list) -> str:
    return hashlib.sha256(json.dumps(stream, sort_keys=True).encode("utf-8")).hexdigest()


def _load_replay(path: Path) -> dict:
    if path.suffix == ".gz":
        return json.loads(gzip.decompress(path.read_bytes()).decode("utf-8"))
    return json.loads(path.read_text(encoding="utf-8"))


def _action_stream(replay: dict, seat: int) -> list:
    """Same alignment as analysis.s1_extract_donors.action_stream (verified against the
    engine's own replay convention): entry t (t in 0..718) is `steps[t+1][seat]["action"]`;
    `steps[0]` is the pre-first-action reset placeholder."""
    steps = replay["steps"]
    return [steps[t][seat].get("action") or dict(PASS_ACTION) for t in range(1, len(steps))]


def _load_episode_times() -> dict[int, dt.datetime]:
    if not EP_CSV.exists():
        raise SystemExit(f"episode listing missing: {EP_CSV} (§2.4b)")
    out = {}
    with open(EP_CSV, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            eid = r.get("id") or ""
            if eid.isdigit():
                out[int(eid)] = dt.datetime.fromisoformat(r["createTime"].split(".")[0])
    return out


def _load_board() -> dict[str, tuple]:
    if not LB_CSV.exists():
        raise SystemExit(f"leaderboard snapshot missing: {LB_CSV} (§2.4b)")
    out = {}
    with open(LB_CSV, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            out[r["TeamName"]] = (int(r["Rank"]), float(r["Score"]),
                                  dt.datetime.fromisoformat(r["LastSubmissionDate"]))
    return out


def _band_of(score: float | None) -> str:
    if score is None:
        return "unknown"
    if score < 1800:
        return "<1800"
    if score < 2100:
        return "1800-2100"
    return "2100+"


def extract() -> dict:
    """Read every held live replay; write per-opponent stream + provenance under BENCH_DIR.

    Every stream is written locally-only (gitignored competition data, §2.4b). The returned
    manifest carries no stream bytes.
    """
    BENCH_DIR.mkdir(parents=True, exist_ok=True)
    played_at = _load_episode_times()
    board = _load_board()

    files = sorted(list(LIVE.glob("*.json")) + list(LIVE.glob("*.json.gz")))
    if not files:
        raise SystemExit(f"no live replays at {LIVE} (§2.4b)")

    opponents: list[dict] = []
    self_play = 0
    non_current = 0
    for path in files:
        replay = _load_replay(path)
        info = replay.get("info", {})
        teams = info.get("TeamNames") or [None, None]
        if teams == [OUR_TEAM, OUR_TEAM]:
            self_play += 1
            continue
        if OUR_TEAM not in teams:
            continue
        cfg = replay.get("configuration", {}) or {}
        if cfg.get("townCenterSellInterval") != 24:
            non_current += 1
            continue
        our_seat = 1 if teams[1] == OUR_TEAM else 0
        opp_seat = 1 - our_seat
        opp_team = teams[opp_seat]
        eid = info.get("EpisodeId")
        seed = info.get("seed")
        rewards = replay.get("rewards") or [None, None]

        opp_stream = _action_stream(replay, opp_seat)
        our_stream = _action_stream(replay, our_seat)
        sha = _sha256(opp_stream)

        our_ep_time = played_at.get(eid)
        b = board.get(opp_team)
        controlled = None
        if b and our_ep_time is not None:
            controlled = b[2] <= our_ep_time  # LastSubmissionDate predates our episode
        opp_score = b[1] if b else None
        opp_rank = b[0] if b else None
        band = _band_of(opp_score) if controlled else "uncontrolled"

        record = {
            "note": f"live opponent from replay {eid} vs {opp_team}",
            "episode_id": eid,
            "engine_seed": seed,
            "engine_config": cfg,
            "our_seat": our_seat,
            "our_recorded_bank": rewards[our_seat],
            "our_action_stream_sha256": _sha256(our_stream),
            "opp_seat": opp_seat,
            "opp_team": opp_team,
            "opp_recorded_bank": rewards[opp_seat],
            "opp_action_stream_sha256": sha,
            "opp_n_steps": len(opp_stream),
            "opp_board_rank": opp_rank,
            "opp_board_score": opp_score,
            "opp_last_sub": b[2].isoformat() if b else None,
            "our_ep_time": our_ep_time.isoformat() if our_ep_time else None,
            "controlled": controlled,
            "band": band,
            "opp_action_stream": opp_stream,     # gitignored (§2.4b)
            "our_action_stream": our_stream,     # gitignored (§2.4b)
        }
        out_path = BENCH_DIR / f"{eid}_seat{opp_seat}_{sha[:8]}.json"
        out_path.write_text(json.dumps(record, indent=1), encoding="utf-8")

        opponents.append({k: v for k, v in record.items()
                          if k not in ("opp_action_stream", "our_action_stream")})

    strata = _stratify(opponents)
    manifest = {
        "pass": "S7 leg 1 — deployment-neighbourhood bench (extraction only)",
        "date": dt.date.today().isoformat(),
        "our_team": OUR_TEAM,
        "held_live_replays": len(files),
        "self_play_excluded": self_play,
        "non_current_engine_excluded": non_current,
        "distinct_opponent_teams": len({o["opp_team"] for o in opponents}),
        "opponents_extracted": len(opponents),
        "strata": strata,
        "opponents": opponents,
        "verify_status": "not_run",
        "verdict": (
            f"EXTRACT {len(opponents)} opponents from {len(files)} replays "
            f"(self-play excluded {self_play}, non-current-engine {non_current}); "
            f"controlled 1800-2100: {strata['controlled_bands']['1800-2100']['n']}, "
            f"2100+: {strata['controlled_bands']['2100+']['n']}"
        ),
    }
    MANIFEST.write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    print(_summary(manifest))
    return manifest


def _stratify(opponents: list[dict]) -> dict:
    controlled = [o for o in opponents if o["controlled"]]
    uncontrolled = [o for o in opponents if not o["controlled"]]
    unknown = [o for o in opponents if o["opp_board_score"] is None]
    out = {
        "total": len(opponents),
        "controlled_total": len(controlled),
        "uncontrolled_total": len(uncontrolled),
        "unknown_board": len(unknown),
        "controlled_bands": {},
        "raw_bands": {},
    }
    for band in ("<1800", "1800-2100", "2100+"):
        sub = [o for o in controlled if o["band"] == band]
        out["controlled_bands"][band] = {
            "n": len(sub),
            "our_recorded_win_rate": (
                sum(1 for o in sub if (o["our_recorded_bank"] or 0)
                    > (o["opp_recorded_bank"] or 0)) / len(sub) if sub else 0.0),
        }
    for band in ("<1800", "1800-2100", "2100+"):
        sub = [o for o in opponents if o["opp_board_score"] is not None and _band_of(
            o["opp_board_score"]) == band]
        out["raw_bands"][band] = {"n": len(sub)}
    return out


def verify(sample: int | None = None) -> dict:
    """Play each opp tape vs the neutral opponent at NEUTRAL_SEED and flag the collapses.

    Collapse := `opp_bank <= COLLAPSE_FLOOR` OR the episode wasn't clean. Both are what
    "desyncs into a no-op parade" looks like from the outside — the tape's actions have no
    valid preconditions in the new game, so they fall through as no-ops and the tape banks
    almost nothing (or the engine crashes it). The brief pre-registered this as the natural
    attrition figure for a neighbourhood bench.
    """
    if not MANIFEST.exists():
        raise SystemExit(f"run `extract` first — no manifest at {MANIFEST}")
    manifest = json.loads(MANIFEST.read_text())
    opps = manifest["opponents"]
    if sample is not None:
        opps = opps[:sample]

    print(f"verifying {len(opps)} opponent tapes vs {NEUTRAL_OPP} at seed={NEUTRAL_SEED} "
          f"(collapse floor ${COLLAPSE_FLOOR:.0f})...")
    verified: list[dict] = []
    started = time.time()
    for i, o in enumerate(opps):
        stream_path = BENCH_DIR / f"{o['episode_id']}_seat{o['opp_seat']}_{o['opp_action_stream_sha256'][:8]}.json"
        stream = json.loads(stream_path.read_text())["opp_action_stream"]
        opp_tape = make_tape_agent(stream)
        t0 = time.time()
        result = play(opp_tape, NEUTRAL_OPP, seed=NEUTRAL_SEED,
                      strict=False, metrics=False, record=False)
        dt_s = time.time() - t0
        opp_bank = result.rewards[0]
        neutral_bank = result.rewards[1]
        clean = result.clean and opp_bank is not None
        collapsed = (not clean) or (opp_bank is not None and opp_bank <= COLLAPSE_FLOOR)
        verified.append({
            "episode_id": o["episode_id"], "opp_team": o["opp_team"],
            "band": o["band"], "controlled": o["controlled"],
            "opp_recorded_bank": o["opp_recorded_bank"],
            "opp_v1u_base_bank": opp_bank, "v1u_base_bank": neutral_bank,
            "clean": clean, "collapsed": collapsed,
        })
        if (i + 1) % 20 == 0:
            elapsed = time.time() - started
            eta = elapsed / (i + 1) * (len(opps) - i - 1)
            print(f"  {i + 1:>3}/{len(opps)}  elapsed {elapsed:.0f}s  eta {eta:.0f}s  "
                  f"({dt_s:.1f}s last)")

    retention = _retention_report(verified)
    manifest["verify_status"] = ("full" if sample is None else f"sample_{len(opps)}")
    manifest["verify_neutral_opponent"] = NEUTRAL_OPP
    manifest["verify_seed"] = NEUTRAL_SEED
    manifest["verify_collapse_floor"] = COLLAPSE_FLOOR
    manifest["verified"] = verified
    manifest["retention"] = retention
    manifest["verdict"] = (
        f"VERIFY {len(opps)} tapes vs {NEUTRAL_OPP}: "
        f"kept {retention['kept_total']}/{retention['n']} "
        f"({100.0 * retention['kept_total'] / max(1, retention['n']):.1f}%); "
        f"controlled 1800-2100 kept {retention['controlled_bands']['1800-2100']['kept']}/"
        f"{retention['controlled_bands']['1800-2100']['n']}, "
        f"2100+ kept {retention['controlled_bands']['2100+']['kept']}/"
        f"{retention['controlled_bands']['2100+']['n']}"
    )
    MANIFEST.write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    print("\n" + _summary(manifest))
    return manifest


def _retention_report(verified: list[dict]) -> dict:
    out = {"n": len(verified), "kept_total": sum(1 for v in verified if not v["collapsed"]),
           "collapsed_total": sum(1 for v in verified if v["collapsed"]),
           "controlled_bands": {}}
    for band in ("<1800", "1800-2100", "2100+"):
        sub = [v for v in verified if v["controlled"] and v["band"] == band]
        kept = [v for v in sub if not v["collapsed"]]
        out["controlled_bands"][band] = {
            "n": len(sub), "kept": len(kept),
            "median_opp_bank_kept": (statistics.median(
                v["opp_v1u_base_bank"] for v in kept) if kept else None),
        }
    return out


def report() -> None:
    if not MANIFEST.exists():
        raise SystemExit(f"nothing to report — no manifest at {MANIFEST}")
    print(_summary(json.loads(MANIFEST.read_text())))


def _summary(m: dict) -> str:
    lines = [
        "=" * 78,
        "S7 leg 1 — deployment-neighbourhood bench",
        "=" * 78,
        f"held live replays              {m['held_live_replays']}",
        f"  self-play excluded           {m['self_play_excluded']}",
        f"  non-current engine excluded  {m['non_current_engine_excluded']}",
        f"opponents extracted            {m['opponents_extracted']}",
        f"distinct opponent teams        {m['distinct_opponent_teams']}",
        "",
        "stratification (leg 0's controlled rule — team's LastSubmissionDate predates our episode):",
        f"  controlled total             {m['strata']['controlled_total']}",
        f"  uncontrolled                 {m['strata']['uncontrolled_total']}",
        f"  unknown (no board row)       {m['strata']['unknown_board']}",
    ]
    for band, row in m["strata"]["controlled_bands"].items():
        lines.append(f"  controlled {band:<10}   n={row['n']:>3}  our_recorded_wr="
                     f"{row['our_recorded_win_rate']:.1%}")
    lines.append("")
    lines.append("raw bands (mixed controlled + uncontrolled — for reference only):")
    for band, row in m["strata"]["raw_bands"].items():
        lines.append(f"  raw {band:<10}          n={row['n']:>3}")
    if m.get("verify_status") == "not_run":
        lines.append("")
        lines.append("verification: NOT RUN — call `verify` next")
    elif m.get("retention"):
        r = m["retention"]
        lines.append("")
        lines.append(f"verification: {m['verify_status']} vs {m['verify_neutral_opponent']} "
                     f"at seed={m['verify_seed']}, collapse floor ${m['verify_collapse_floor']:.0f}")
        lines.append(f"  kept overall: {r['kept_total']}/{r['n']} "
                     f"({100.0 * r['kept_total'] / max(1, r['n']):.1f}%)")
        for band, row in r["controlled_bands"].items():
            floor = f"${row['median_opp_bank_kept']:,.0f}" if row["median_opp_bank_kept"] else "—"
            lines.append(f"  controlled {band:<10}   kept {row['kept']:>3}/{row['n']:<3}  "
                         f"median_kept_bank {floor}")
    lines.append("")
    lines.append("VERDICT: " + m.get("verdict", ""))
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("cmd", choices=["extract", "verify", "report"])
    ap.add_argument("--sample", type=int, default=None,
                    help="verify: only play the first N tapes (smoke)")
    args = ap.parse_args()
    if args.cmd == "extract":
        extract()
    elif args.cmd == "verify":
        verify(sample=args.sample)
    else:
        report()


if __name__ == "__main__":
    main()
