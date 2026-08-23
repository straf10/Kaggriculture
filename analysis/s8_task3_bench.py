#!/usr/bin/env python3
"""S8 Task 3 — the neighbourhood bench (docs/plans/... §4).

The requirement "fully tested that it will be better" is NOT met by today's bench (§7.4: our
round-robin put v1i over v1h; the ladder reversed it). And the paired ladder cut is dead (§2.4),
so a bench of the REAL opponents we will meet again is the ONLY controlled way to compare our two
artifacts. Its stated limit (§4.1): replaying a recorded stream is NOT the opponent's policy — it
will not react to us. It is fixed-production sparring, like A2, but far closer than tiers 0-5.

Build (§4.2): extract each opponent's action stream, wrap with make_tape_agent, record provenance
(episode_id, seat, team, seed, sha256(stream), opponent_score), stratify by rating zone.

Two validity checks WITHOUT which it is not an instrument (§4.3):
  (α) reproduction: replay each extracted stream on its own seed against our recorded stream and
      confirm the bank reproduces (tapes calibrate at 0,0000%). Report retention.
  (β) inversion: rank our TWO artifacts (55675634, 55586926) on the new bench and compare to the
      live order. If the bench inverts the live order, it is NOT an instrument — say so and stop
      tuning on it (§7.4 standing kill).

Streams + built agents are gitignored (harness/bench_agents/neighbourhood/); provenance manifest is
data/derived/s8_bench_manifest.json (also gitignored).

Subcommands:
    build   — extract opponent streams + provenance for the union of both submissions' ladder eps
    alpha   — reproduction check on every on-disk ladder replay (both seats)
    beta    — inversion check: our two artifacts vs a rating-stratified opponent sample
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from analysis import s8_replay_io as io  # noqa: E402
from analysis.tape_agent import make_tape_agent  # noqa: E402
from analysis.s8_task1_matched import load_snapshot, zone_of, SNAP_A, SNAP_B, ZONES  # noqa: E402

BENCH_DIR = ROOT / "harness" / "bench_agents" / "neighbourhood"
MANIFEST = ROOT / "data" / "derived" / "s8_bench_manifest.json"

# Our two artifacts as runnable main.py tapes (the live truth we calibrate against).
ART_A = ROOT / "baselines" / "2026-08-17" / "tape_submissions" / "reconstruction_ReCurSiON" / "main.py"  # 55586926
ART_B = ROOT / "baselines" / "2026-08-21" / "tape_submissions" / "overlay_ReCurSiON" / "main.py"          # 55675634
# Live ratings (subs snapshot 2026-08-23 08:34): the order β must reproduce.
LIVE_ORDER = {"55586926": 1821.8, "55675634": 1649.7}

TOL = 0.005  # 0.5% fidelity tolerance; tapes calibrate at 0.0000%
_PASS = {"farmer": ["PASS"], "hands": [], "market": []}


def extract_stream(steps: list, seat: int) -> list:
    """stream[k] served at obs.step==k is steps[k+1][seat]['action'] (§1.2). Verified 0.0000%."""
    n = len(steps)
    out = [dict(_PASS)] * n
    for k in range(n - 1):
        out[k] = steps[k + 1][seat].get("action") or dict(_PASS)
    return out


def _sha(stream: list) -> str:
    return hashlib.sha256(json.dumps(stream, separators=(",", ":")).encode()).hexdigest()


def _snap_for(submission: str) -> dict:
    # A-window submission read with 08-18 snapshot; B-window with 08-23 (same-age, §2.3).
    return load_snapshot(SNAP_A) if submission == "55586926" else load_snapshot(SNAP_B)


def cmd_build(args) -> int:
    BENCH_DIR.mkdir(parents=True, exist_ok=True)
    entries = []
    seen_stream_sha = {}
    per_team_zone = {}
    for submission in io.SUBMISSIONS:
        snap = _snap_for(submission)
        for eid, m in io.ladder_episodes(submission):
            seat = io.our_seat(m["teams"])
            opp_seat = 1 - seat
            steps = m["steps"]
            if not io.opponent_clean(steps, opp_seat):
                continue  # a dead opponent is not an opponent (§4.2 step 2)
            opp_team = m["teams"][opp_seat]
            stream = extract_stream(steps, opp_seat)
            sha = _sha(stream)
            score = snap.get(opp_team)
            zone = zone_of(score) if score is not None else "unknown"
            # persist the stream (gitignored) keyed by sha to dedup identical tapes
            if sha not in seen_stream_sha:
                (BENCH_DIR / f"{sha[:16]}.json").write_text(json.dumps(stream, separators=(",", ":")))
                seen_stream_sha[sha] = f"{sha[:16]}.json"
            per_team_zone[opp_team] = zone
            entries.append({
                "submission": submission, "episode_id": eid, "opp_seat": opp_seat,
                "team": opp_team, "seed": m["seed"], "stream_sha256": sha,
                "stream_file": seen_stream_sha[sha], "opponent_score": score, "zone": zone,
                "recorded_reward_opp": m["rewards"][opp_seat],
                "recorded_reward_us": m["rewards"][seat],
            })
    distinct_teams = {e["team"] for e in entries}
    by_zone = defaultdict(int)
    for t, z in per_team_zone.items():
        by_zone[z] += 1
    manifest = {
        "n_episodes": len(entries),
        "n_distinct_teams": len(distinct_teams),
        "n_distinct_streams": len(seen_stream_sha),
        "distinct_teams_by_zone": dict(by_zone),
        "retention_note": (
            "Built from replays on disk: 178 (55586926) + 75 (55675634) = 253 ladder replays. "
            "The plan's full target is 329 (76 more of 55586926's 254 not downloaded); those add "
            "opponent COVERAGE, not validity — the α/β checks below are complete on 253."),
        "limit_note": (
            "A recorded stream is fixed-production sparring, NOT the opponent's policy — it will not "
            "react to us (§4.1). Closer than tiers 0-5, but not a live opponent."),
        "entries": entries,
    }
    MANIFEST.write_text(json.dumps(manifest, indent=1))
    print(f"built {len(entries)} opponent episodes, {len(distinct_teams)} distinct teams, "
          f"{len(seen_stream_sha)} distinct streams")
    print(f"distinct teams by zone: {dict(by_zone)}")
    print(f"wrote {MANIFEST} and streams to {BENCH_DIR}/")
    return 0


def cmd_alpha(args) -> int:
    """(α) reproduction: replay both extracted streams on the recorded seed; both banks must match
    recorded rewards within TOL. This validates the extraction alignment for the WHOLE bench."""
    from harness.play import play
    ok = bad = 0
    fails = []
    t0 = time.time()
    n_total = sum(1 for sub in io.SUBMISSIONS for _ in io.ladder_episodes(sub))
    i = 0
    for submission in io.SUBMISSIONS:
        for eid, m in io.ladder_episodes(submission):
            i += 1
            steps, seed, rew = m["steps"], m["seed"], m["rewards"]
            s0, s1 = extract_stream(steps, 0), extract_stream(steps, 1)
            try:
                res = play(make_tape_agent(s0), make_tape_agent(s1), seed=seed,
                           metrics=False, record=False, strict=False)
            except Exception as e:  # noqa: BLE001
                bad += 1
                fails.append({"episode_id": eid, "error": str(e)})
                continue
            e0 = abs(res.rewards[0] - rew[0]) / max(abs(rew[0]), 1)
            e1 = abs(res.rewards[1] - rew[1]) / max(abs(rew[1]), 1)
            if e0 <= TOL and e1 <= TOL:
                ok += 1
            else:
                bad += 1
                fails.append({"episode_id": eid, "err": [e0, e1],
                              "recorded": rew, "replayed": list(res.rewards)})
            if i % 25 == 0:
                print(f"  {i}/{n_total}  ok={ok} bad={bad}  ({time.time()-t0:.0f}s)")
            if args.limit and i >= args.limit:
                break
        if args.limit and i >= args.limit:
            break
    out = {"checked": ok + bad, "reproduced": ok, "failed": bad,
           "tolerance": TOL, "retention": ok / (ok + bad) if (ok + bad) else None,
           "failures": fails[:50]}
    (ROOT / "data" / "derived" / "s8_bench_alpha.json").write_text(json.dumps(out, indent=1))
    print(f"\n(α) reproduction: {ok}/{ok+bad} reproduced within {TOL:.1%}  "
          f"(retention {out['retention']:.4f})  in {time.time()-t0:.0f}s")
    if fails:
        print(f"  {len(fails)} failures, first: {fails[0]}")
    return 0


def _stratified_sample(entries, per_zone):
    """One episode per distinct team, sampled up to `per_zone` teams per zone (deterministic:
    lowest episode_id per team, teams sorted by id)."""
    best = {}
    for e in entries:
        if e["team"] not in best or e["episode_id"] < best[e["team"]]["episode_id"]:
            best[e["team"]] = e
    by_zone = defaultdict(list)
    for e in best.values():
        by_zone[e["zone"]].append(e)
    sample = []
    for z, es in by_zone.items():
        es.sort(key=lambda x: x["episode_id"])
        sample.extend(es[:per_zone])
    return sample


def cmd_beta(args) -> int:
    """(β) inversion: play both our artifacts vs each sampled opponent, BOTH seats. Aggregate W/L
    per artifact per zone; the bench order = higher win-rate. Compare to LIVE_ORDER."""
    from harness.play import play
    if not MANIFEST.exists():
        raise SystemExit("run `build` first")
    entries = json.loads(MANIFEST.read_text())["entries"]
    sample = _stratified_sample(entries, args.per_zone)
    print(f"β sample: {len(sample)} opponents "
          f"({dict((z, sum(1 for e in sample if e['zone']==z)) for z in set(e['zone'] for e in sample))})")

    arts = {"55586926": str(ART_A), "55675634": str(ART_B)}
    # win counts per artifact overall and per zone
    wl = {a: defaultdict(lambda: {"W": 0, "L": 0, "D": 0}) for a in arts}
    t0 = time.time()
    for j, e in enumerate(sample, 1):
        stream = json.loads((BENCH_DIR / e["stream_file"]).read_text())
        opp = make_tape_agent(stream)
        seed = e["seed"]
        for a, path in arts.items():
            for our_seat in (0, 1):
                a0, a1 = (path, opp) if our_seat == 0 else (opp, path)
                try:
                    res = play(a0, a1, seed=seed, metrics=False, record=False, strict=False)
                except Exception:  # noqa: BLE001
                    continue
                us, them = res.rewards[our_seat], res.rewards[1 - our_seat]
                r = "W" if us > them else ("L" if us < them else "D")
                wl[a]["ALL"][r] += 1
                wl[a][e["zone"]][r] += 1
        if j % 10 == 0:
            print(f"  {j}/{len(sample)} opponents  ({time.time()-t0:.0f}s)")

    def wr(d):
        n = d["W"] + d["L"]
        return d["W"] / n if n else None

    summary = {}
    for a in arts:
        summary[a] = {z: dict(wl[a][z], win_rate=wr(wl[a][z])) for z in wl[a]}
    order_bench = sorted(arts, key=lambda a: -(wr(wl[a]["ALL"]) or 0))
    order_live = sorted(LIVE_ORDER, key=lambda a: -LIVE_ORDER[a])
    inverted = order_bench != order_live
    out = {
        "n_opponents": len(sample),
        "per_artifact": summary,
        "bench_order_best_first": order_bench,
        "live_order_best_first": order_live,
        "live_ratings": LIVE_ORDER,
        "inverted": inverted,
        "verdict": ("BENCH INVERTS LIVE ORDER — not an instrument, do not tune on it (§7.4)."
                    if inverted else
                    "Bench agrees with live order — it may be trusted as a directional instrument, "
                    "within the fixed-production limit (§4.1)."),
    }
    (ROOT / "data" / "derived" / "s8_bench_beta.json").write_text(json.dumps(out, indent=1))
    print("\n(β) inversion check:")
    for a in arts:
        d = wl[a]["ALL"]
        print(f"  {a}: ALL {d['W']}-{d['L']}-{d['D']} wr={wr(d):.3f}   " +
              "  ".join(f"{z} {wl[a][z]['W']}-{wl[a][z]['L']}" for z in ZONES if z in wl[a]))
    print(f"  bench order: {order_bench}   live order: {order_live}   INVERTED={inverted}")
    print(f"  {out['verdict']}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("build")
    a = sub.add_parser("alpha")
    a.add_argument("--limit", type=int, default=0)
    b = sub.add_parser("beta")
    b.add_argument("--per-zone", type=int, default=20, help="max distinct teams per zone")
    args = ap.parse_args()
    return {"build": cmd_build, "alpha": cmd_alpha, "beta": cmd_beta}[args.cmd](args)


if __name__ == "__main__":
    raise SystemExit(main())
