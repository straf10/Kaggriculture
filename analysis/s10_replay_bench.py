#!/usr/bin/env python3
"""S10 P1 — the replay bench (Instrument A framework, reusable).

Every ladder episode of a live submission is a `(seed, teams, seat_0_stream,
seat_1_stream, recorded_rewards)` tuple.  A *bench* run recomposes that episode
in `harness.play.play`:

  α-control (P1.2):    both seats are `make_tape_agent(<recorded stream>)`.
                        The engine is deterministic given seed+actions; the
                        replay must reproduce the recorded rewards bit-exactly.
                        Death if <95% bit-exact.
  H2 calibration (P1.4): candidate seat runs `agent.tape_overlay.TapeOverlay`
                        in `mode="liquidate"` with the frozen H2 parameters
                        (F=25, first_day=22, h_max=12, d_days=4, force_step=686);
                        opponent seat is a tape.  The overlay is imported
                        read-only — no `agent/` change is made here.

The bench is INSTRUMENT A, not the seed harness.  Live seeds must NOT enter
`harness/seeds.py::NAMED_SEED_SETS` (plan §P1.7) — they would corrupt the
screen→confirm ledger semantics.  Bench inputs are (episode, seed) pairs
loaded from `data/archive/raw/live_<sub>/`, never from `--seed-set`.

Zero foresight (plan §P1.1):  the candidate reads only the current `obs` — no
peek at recorded post-state, no read of the opponent's stream.  The
`TapeOverlay` obeys that contract by construction (its inputs are seat-local).

Manifest (P1.3):  `data/derived/s10_bench_manifest.json` — per episode, the
seed, our seat, opponent, and (if resolvable) opponent's public-board rank/
score.  Written once by `manifest`; the calibration outputs join on
`episode_id`.

CLI:
    python analysis/s10_replay_bench.py manifest [<sub> ...]
    python analysis/s10_replay_bench.py alpha [<sub> ...]           # P1.2
    python analysis/s10_replay_bench.py h2_calibration              # P1.4 (55586926+55675634)

Workers are pinned at 4 (plan §Πάγιοι Κανόνες 5), overridable via
`S10_BENCH_WORKERS`.
"""
from __future__ import annotations

import json
import os
import sys
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "engine_reference"))

from analysis.s8_replay_io import (SUBMISSIONS, ladder_episodes, load,  # noqa: E402
                                    meta, replay_paths, our_seat)
from analysis.tape_agent import make_tape_agent  # noqa: E402
from harness.play import play  # noqa: E402

PASS = {"farmer": ["PASS"], "hands": [], "market": []}
DERIVED = ROOT / "data" / "derived"
DERIVED.mkdir(parents=True, exist_ok=True)
DEFAULT_WORKERS = int(os.environ.get("S10_BENCH_WORKERS", "4"))

# P3.3: same semantics as gates/confirm_log.jsonl — one line per bench "look" so
# repeated tuning-driven readings of the confirm set are visible in git.
BENCH_LEDGER = ROOT / "gates" / "s10_bench_ledger.jsonl"


def _append_bench_ledger(entry: dict) -> None:
    BENCH_LEDGER.parent.mkdir(parents=True, exist_ok=True)
    with BENCH_LEDGER.open("a") as f:
        f.write(json.dumps(entry) + "\n")

# H2 frozen parameters — must match agent/tape_overlay.py defaults exactly.
H2_PARAMS = dict(mode="liquidate", liq_floor_price=25, liq_first_day=22,
                 liq_h_max=12, liq_d_days=4, liq_force_step=686)

# P3.3: screen/confirm split.  Screen = 55726984 (the current-generation
# submission whose stream is H2-augmented already — cannot be used for H2
# calibration).  Confirm = 55586926 + 55675634 (412 eps, plan §P1.4 dataset).
SCREEN_SUBS = ("55726984",)
CONFIRM_SUBS = ("55586926", "55675634")


def _extract_streams(steps):
    """Per-seat action stream indexed by obs["step"].  Mirrors
    `analysis/s9_h2_k10.py::_streams` and the alignment convention verified in
    `analysis/s8_replay_io.py` (stream[k] == steps[k+1][seat]["action"])."""
    return [[(steps[i + 1][seat].get("action") or dict(PASS))
             for i in range(len(steps) - 1)] for seat in (0, 1)]


# ---------------------------------------------------------------------------
# Job scheduling
# ---------------------------------------------------------------------------
# The full 55586926+55675634+55726984 corpus is ~500 replays x 5-30 MB.  Building
# a list of `(steps=...)` jobs pickles ~2-3 GB into worker queues and stalls the
# pool.  Workers load their replay from disk instead — jobs are just paths.
def _enum_jobs(submissions, seat_required=False, limit=None):
    n = 0
    for sub in submissions:
        for p in replay_paths(sub):
            eid = int(p.name.split("-")[1])
            yield (sub, eid, str(p))
            n += 1
            if limit and n >= limit:
                return


def _load_meta_and_streams(path_str):
    d = load(Path(path_str))
    m = meta(d)
    return m


# ---------------------------------------------------------------------------
# α-control (P1.2)
# ---------------------------------------------------------------------------
def _alpha_one(job):
    sub, eid, path = job
    m = _load_meta_and_streams(path)
    # Skip mirror/validation — the enumerator does not (it just walks disk); the
    # α/H2 semantics only make sense on ladder eps.  Same filter as
    # `ladder_episodes`.
    from analysis.s8_replay_io import is_excluded
    excl, _r = is_excluded(m)
    if excl:
        return None
    streams = _extract_streams(m["steps"])
    a = make_tape_agent(streams[0])
    b = make_tape_agent(streams[1])
    r = play(a, b, seed=m["seed"], record=False, metrics=False, strict=False)
    exact_0 = abs(float(r.rewards[0]) - float(m["rewards"][0])) < 1e-6
    exact_1 = abs(float(r.rewards[1]) - float(m["rewards"][1])) < 1e-6
    return dict(submission=sub, episode_id=eid, seed=m["seed"],
                teams=list(m["teams"]),
                recorded=[float(m["rewards"][0]), float(m["rewards"][1])],
                replayed=[float(r.rewards[0]), float(r.rewards[1])],
                bit_exact=(exact_0 and exact_1),
                bit_exact_seat0=exact_0, bit_exact_seat1=exact_1,
                clean=r.clean)


def run_alpha(submissions, workers=DEFAULT_WORKERS, limit=None):
    jobs = list(_enum_jobs(submissions, limit=limit))
    print(f"alpha: {len(jobs)} disk replays across {list(submissions)}, workers={workers}",
          flush=True)
    rows = []
    with ProcessPoolExecutor(max_workers=workers) as ex:
        for i, row in enumerate(ex.map(_alpha_one, jobs, chunksize=1), 1):
            if row is not None:
                rows.append(row)
            if i % 25 == 0:
                print(f"  {i}/{len(jobs)}", flush=True)
    n = len(rows)
    exact = sum(1 for r in rows if r["bit_exact"])
    share = exact / max(n, 1)
    verdict = "PASSED" if share >= 0.99 else ("DEATH" if share < 0.95 else "WARN")
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "verdict": f"alpha {verdict}: {exact}/{n} bit-exact ({share:.4f})",
        "workers": workers,
        "n": n,
        "n_bit_exact": exact,
        "share_bit_exact": share,
        "submissions": list(submissions),
        "rows": rows,
    }


# ---------------------------------------------------------------------------
# H2 calibration (P1.4)
# ---------------------------------------------------------------------------
def _h2_one(job):
    # Deferred import in the worker — TapeOverlay pulls in agent.config which
    # touches package-level state; keeping it worker-local also lets us avoid
    # importing agent/ in the parent process.
    from agent.tape_overlay import TapeOverlay
    from analysis.s8_replay_io import is_excluded
    sub, eid, path = job
    m = _load_meta_and_streams(path)
    excl, _r = is_excluded(m)
    if excl:
        return None
    seat = our_seat(m["teams"])
    if seat is None:
        return None
    streams = _extract_streams(m["steps"])
    overlay = TapeOverlay(streams[seat], **H2_PARAMS)
    if seat == 0:
        a, b = overlay.act, make_tape_agent(streams[1])
    else:
        a, b = make_tape_agent(streams[0]), overlay.act
    r = play(a, b, seed=m["seed"], record=False, metrics=False, strict=False)
    base_us = float(m["rewards"][seat])
    base_opp = float(m["rewards"][1 - seat])
    new_us = float(r.rewards[seat])
    new_opp = float(r.rewards[1 - seat])
    return dict(submission=sub, episode_id=eid, seed=m["seed"],
                seat=seat, opponent=m["teams"][1 - seat],
                base_us=base_us, base_opp=base_opp,
                new_us=new_us, new_opp=new_opp,
                base_win=base_us > base_opp,
                new_win=new_us > new_opp,
                d_bank=new_us - base_us,
                clean=r.clean)


def _mcnemar_binomial_p(b, c):
    """Two-sided exact binomial McNemar test.  For b + c ≤ 1000 use scipy-free
    Clopper–Pearson-style two-sided binomial.  For small b (0-5) and any c the
    exact tail is closed-form."""
    from math import comb
    n = b + c
    if n == 0:
        return 1.0
    m = min(b, c)
    # Two-sided p = 2 * P(X ≤ m | X ~ Binom(n, 0.5)), capped at 1.
    tail = sum(comb(n, k) for k in range(m + 1)) / (2 ** n)
    return min(1.0, 2 * tail)


def run_h2_calibration(workers=DEFAULT_WORKERS, limit=None):
    jobs = list(_enum_jobs(CONFIRM_SUBS, limit=limit))
    print(f"h2_calibration: {len(jobs)} disk replays (confirm={CONFIRM_SUBS}), "
          f"workers={workers}", flush=True)
    rows = []
    with ProcessPoolExecutor(max_workers=workers) as ex:
        for i, row in enumerate(ex.map(_h2_one, jobs, chunksize=1), 1):
            if row is not None:
                rows.append(row)
            if i % 25 == 0:
                print(f"  {i}/{len(jobs)}", flush=True)

    base_w = sum(1 for r in rows if r["base_win"])
    base_l = len(rows) - base_w
    new_w = sum(1 for r in rows if r["new_win"])
    new_l = len(rows) - new_w
    # McNemar: c = base_loss → new_win (flipped to a win), b = base_win → new_loss.
    c = sum(1 for r in rows if (not r["base_win"]) and r["new_win"])
    b = sum(1 for r in rows if r["base_win"] and (not r["new_win"]))
    p = _mcnemar_binomial_p(b, c)
    # Same-direction check: recorded 232-180 → 255-157 in the s9-phase2-gate memory.
    same_direction = (c > 0) and (b == 0)
    verdict_txt = ("PASSED" if same_direction and p < 0.001
                   else "DEATH" if (b > c or not (c > 0 and b == 0))
                   else "WARN")
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "verdict": (f"h2_calibration {verdict_txt}: base {base_w}-{base_l} "
                    f"→ new {new_w}-{new_l}; McNemar c={c} b={b} p={p:.2e}"),
        "workers": workers,
        "n": len(rows),
        "confirm_subs": list(CONFIRM_SUBS),
        "h2_params": H2_PARAMS,
        "base_wins": base_w, "base_losses": base_l,
        "new_wins": new_w, "new_losses": new_l,
        "mcnemar_c": c, "mcnemar_b": b, "mcnemar_p": p,
        "same_direction_and_significant": (same_direction and p < 0.001),
        "rows": rows,
    }


# ---------------------------------------------------------------------------
# Manifest (P1.3)
# ---------------------------------------------------------------------------
def _rating_zone(score):
    if score is None:
        return None
    s = float(score)
    if s < 1500: return "<1500"
    if s < 1700: return "1500-1700"
    if s < 1900: return "1700-1900"
    if s < 2100: return "1900-2100"
    if s < 2400: return "2100-2400"
    return "2400+"


def build_manifest(submissions):
    rows = []
    for sub in submissions:
        for eid, m in ladder_episodes(sub):
            seat = our_seat(m["teams"])
            opp = m["teams"][1 - seat] if seat is not None else None
            rows.append({
                "submission": sub,
                "episode_id": eid,
                "seed": m["seed"],
                "our_seat": seat,
                "opponent": opp,
                # Board score/rank and LastSubmissionDate need the public board — left
                # as null placeholders here; join is `analysis/s7_ladder_census.py`'s job
                # if needed.  Bench statistics do not depend on them.
                "board_score": None,
                "board_rank": None,
                "last_submission_date": None,
                "controlled": None,
                "rating_zone": _rating_zone(None),
            })
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "verdict": f"manifest {len(rows)} rows across {list(submissions)}",
        "n": len(rows),
        "rows": rows,
    }


def _write(path: Path, obj: dict):
    path.write_text(json.dumps(obj, indent=2))
    print(f"wrote {path} ({obj.get('verdict', '')})", flush=True)


# ---------------------------------------------------------------------------
# P3.2 reporter — W/L by seat / generation / opponent
# ---------------------------------------------------------------------------
def report_h2(path: Path = DERIVED / "s10_bench_h2_calibration.json"):
    d = json.loads(path.read_text())
    rows = d["rows"]
    by_seat = {0: [0, 0, 0, 0], 1: [0, 0, 0, 0]}   # [base_w, base_l, new_w, new_l]
    by_gen = {}
    flipped = {"c_win": [], "b_loss": []}
    for r in rows:
        s = r["seat"]
        by_seat[s][0] += 1 if r["base_win"] else 0
        by_seat[s][1] += 0 if r["base_win"] else 1
        by_seat[s][2] += 1 if r["new_win"] else 0
        by_seat[s][3] += 0 if r["new_win"] else 1
        by_gen.setdefault(r["submission"], [0, 0, 0, 0])
        by_gen[r["submission"]][0] += 1 if r["base_win"] else 0
        by_gen[r["submission"]][1] += 0 if r["base_win"] else 1
        by_gen[r["submission"]][2] += 1 if r["new_win"] else 0
        by_gen[r["submission"]][3] += 0 if r["new_win"] else 1
        if (not r["base_win"]) and r["new_win"]:
            flipped["c_win"].append({"episode_id": r["episode_id"],
                                     "opponent": r["opponent"], "seat": s,
                                     "submission": r["submission"]})
        elif r["base_win"] and (not r["new_win"]):
            flipped["b_loss"].append({"episode_id": r["episode_id"],
                                      "opponent": r["opponent"], "seat": s,
                                      "submission": r["submission"]})
    report = {
        "verdict": d["verdict"],
        "n": d["n"],
        "mcnemar": {"c": d["mcnemar_c"], "b": d["mcnemar_b"], "p": d["mcnemar_p"]},
        # Note: rating_zone breakdown is deliberately absent — the manifest carries
        # zone=null (no live board-score join in this pass, plan §P1.3).  This
        # report is by seat and by submission-generation only, matching what the
        # bench actually knows.
        "by_seat": {str(k): {"base_w_l": [v[0], v[1]], "new_w_l": [v[2], v[3]]}
                    for k, v in by_seat.items()},
        "by_generation": {k: {"base_w_l": [v[0], v[1]], "new_w_l": [v[2], v[3]]}
                          for k, v in by_gen.items()},
        "flipped": flipped,
    }
    out = DERIVED / "s10_bench_h2_calibration_report.json"
    _write(out, report)
    return report


def main():
    args = sys.argv[1:]
    if not args:
        print("usage: python analysis/s10_replay_bench.py {manifest|alpha|h2_calibration} [args]")
        sys.exit(2)
    mode, rest = args[0], args[1:]

    if mode == "manifest":
        subs = tuple(rest) or tuple(SUBMISSIONS.keys())
        out = build_manifest(subs)
        _write(DERIVED / "s10_bench_manifest.json", out)
        return

    if mode == "alpha":
        subs = tuple(rest) or tuple(SUBMISSIONS.keys())
        out = run_alpha(subs)
        _write(DERIVED / "s10_bench_alpha.json", out)
        _append_bench_ledger({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "mode": "alpha", "submissions": list(subs),
            "dataset": "confirm" if any(s in CONFIRM_SUBS for s in subs) else "screen",
            "n": out["n"], "n_bit_exact": out["n_bit_exact"],
            "share_bit_exact": out["share_bit_exact"], "verdict": out["verdict"],
        })
        return

    if mode == "h2_calibration":
        limit = int(rest[0]) if rest else None
        out = run_h2_calibration(limit=limit)
        _write(DERIVED / "s10_bench_h2_calibration.json", out)
        _append_bench_ledger({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "mode": "h2_calibration",
            "dataset": "confirm", "submissions": list(CONFIRM_SUBS),
            "n": out["n"], "c": out["mcnemar_c"], "b": out["mcnemar_b"],
            "p": out["mcnemar_p"], "verdict": out["verdict"],
        })
        return

    if mode == "report_h2":
        report_h2()
        return

    print(f"unknown mode: {mode}")
    sys.exit(2)


if __name__ == "__main__":
    main()
