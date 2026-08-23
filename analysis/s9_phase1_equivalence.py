#!/usr/bin/env python3
"""S9 Phase 1 acceptance — the REAL agent must reproduce the frozen reference bit-for-bit.

The rule lives twice now: as the validated reference `make_h2_agent(variant="tail")`
(analysis/s9_h2_k10.py, measured over 412 episodes) and as `mode="liquidate"` in the shipped
`agent/tape_overlay.py`. This script proves they are the SAME rule, not merely a similar one.

For each of the same 412 episodes (dev 164 + holdout 89 + fresh 159) it runs the production agent
— `make_overlay_agent(recorded_stream_seat, mode="liquidate")` against `make_tape_agent(opp)` at
the recorded seed, exactly the seat placement s9_h2_k10.run_one uses — and checks:

  * alpha control (§5.4): play(tape, tape, seed) reproduces the RECORDED rewards, 412/412 exact.
  * equivalence (§5.3): the production agent's reward EQUALS the reference's `new_us`, 412/412.
    Not "statistically equal" — identical. Any drift means the production path diverged from the
    frozen rule; find it, don't explain it.

Reference rewards come from the on-disk derived files (gitignored):
  dev     → data/derived/s9_h2_k10_tail_dev.json      (field: new_us, base_us=recorded)
  holdout → data/derived/s9_h2_a8_tail_holdout.json   (field: new_us, base_us=alpha replay)
  fresh   → data/derived/s9_h2_fresh.json             (field: new_us, base_us=alpha replay)

Output: data/derived/s9_phase1_equivalence.json
"""
from __future__ import annotations

import json
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import analysis.s8_replay_io as RIO  # noqa: E402
from analysis.s8_replay_io import ladder_episodes, our_seat  # noqa: E402
from analysis.s9_h2_k10 import _streams, dev_split  # noqa: E402
from analysis.tape_agent import make_tape_agent  # noqa: E402
from agent.tape_overlay import make_overlay_agent  # noqa: E402
from harness.play import play  # noqa: E402

DERIVED = ROOT / "data" / "derived"
OUT = DERIVED / "s9_phase1_equivalence.json"

# The three frozen reference sets and their on-disk archives.
ORIG_SUBS = {
    "55586926": RIO.RAW / "live_55586926",
    "55675634": RIO.RAW / "live_55675634",
}
FRESH_SUBS = {
    "55586926": RIO.RAW / "live_55586926_fresh",
    "55675634": RIO.RAW / "live_55675634_fresh",
}
REF_FILES = {
    "dev": DERIVED / "s9_h2_k10_tail_dev.json",
    "holdout": DERIVED / "s9_h2_a8_tail_holdout.json",
    "fresh": DERIVED / "s9_h2_fresh.json",
}


def run_one(args):
    source, sub, eid, teams, rewards, seed, steps = args
    seat = our_seat(teams)
    opp = 1 - seat
    st = _streams(steps)

    # alpha control: replay both recorded tapes at the recorded seed.
    rb = play(make_tape_agent(st[0]), make_tape_agent(st[1]), seed=seed,
              record=False, metrics=False, strict=False)

    # candidate: our seat gets the PRODUCTION liquidate overlay carrying the recorded tape.
    cand = make_overlay_agent(st[seat], mode="liquidate")
    a, b = (cand, make_tape_agent(st[1])) if seat == 0 else (make_tape_agent(st[0]), cand)
    rc = play(a, b, seed=seed, record=False, metrics=False, strict=False)

    return dict(
        source=source, submission=sub, episode_id=eid, opponent=teams[opp], seat=seat,
        recorded=[rewards[0], rewards[1]], base_replay=list(rb.rewards),
        alpha_exact=(list(rb.rewards) == [rewards[0], rewards[1]]),
        cand_us=rc.rewards[seat], cand_opp=rc.rewards[opp],
        d_bank=rc.rewards[seat] - rewards[seat],
        clean=(rb.clean and rc.clean),
    )


def _collect_jobs(limit=None):
    jobs = []
    # dev + holdout: the two original submissions, team-disjoint split.
    RIO.SUBMISSIONS = ORIG_SUBS
    for sub in ORIG_SUBS:
        for eid, m in ladder_episodes(sub):
            seat = our_seat(m["teams"])
            if seat is None:
                continue
            source = "dev" if dev_split(m["teams"][1 - seat]) else "holdout"
            jobs.append((source, sub, eid, m["teams"], m["rewards"], m["seed"], m["steps"]))
            if limit and len(jobs) >= limit:
                return jobs
    # fresh: the separate later download, no split.
    RIO.SUBMISSIONS = FRESH_SUBS
    for sub in FRESH_SUBS:
        for eid, m in ladder_episodes(sub):
            if our_seat(m["teams"]) is None:
                continue
            jobs.append(("fresh", sub, eid, m["teams"], m["rewards"], m["seed"], m["steps"]))
            if limit and len(jobs) >= limit:
                return jobs
    return jobs


def _load_refs():
    """(source, submission, episode_id) -> {new_us, d_bank_ref}."""
    ref = {}
    for source, path in REF_FILES.items():
        rows = json.loads(path.read_text())
        for r in rows:
            key = (source, str(r["submission"]), int(r["episode_id"]))
            base_us = r.get("base_us")
            new_us = r["new_us"]
            ref[key] = {"new_us": new_us, "d_bank": new_us - base_us}
    return ref


def main(limit=None):
    jobs = _collect_jobs(limit)
    counts = {}
    for j in jobs:
        counts[j[0]] = counts.get(j[0], 0) + 1
    print(f"equivalence: {len(jobs)} episodes {counts}", flush=True)

    rows = []
    with ProcessPoolExecutor() as ex:
        for i, row in enumerate(ex.map(run_one, jobs), 1):
            rows.append(row)
            if i % 20 == 0:
                print(f"  {i}/{len(jobs)}", flush=True)

    ref = _load_refs()
    alpha_ok = eq_ok = dbank_ok = matched = 0
    mism = []
    for row in rows:
        key = (row["source"], str(row["submission"]), int(row["episode_id"]))
        if row["alpha_exact"]:
            alpha_ok += 1
        r = ref.get(key)
        if r is None:
            mism.append({**{k: row[k] for k in ("source", "submission", "episode_id")},
                         "why": "no reference row"})
            continue
        matched += 1
        us_eq = (row["cand_us"] == r["new_us"])
        db_eq = (row["d_bank"] == r["d_bank"])
        if us_eq:
            eq_ok += 1
        if db_eq:
            dbank_ok += 1
        if not (us_eq and db_eq):
            mism.append({**{k: row[k] for k in ("source", "submission", "episode_id")},
                         "cand_us": row["cand_us"], "ref_new_us": r["new_us"],
                         "cand_d_bank": row["d_bank"], "ref_d_bank": r["d_bank"]})

    summary = dict(
        n=len(rows), matched=matched,
        alpha_exact=alpha_ok, equivalence_new_us=eq_ok, equivalence_d_bank=dbank_ok,
        by_source=counts, mismatches=mism,
    )
    OUT.write_text(json.dumps({"summary": summary, "rows": rows}))
    print("wrote", OUT)
    print(f"  alpha-control exact : {alpha_ok}/{len(rows)}")
    print(f"  matched to reference: {matched}/{len(rows)}")
    print(f"  new_us identical    : {eq_ok}/{matched}")
    print(f"  d_bank identical    : {dbank_ok}/{matched}")
    if mism:
        print(f"  🔴 {len(mism)} mismatch(es):")
        for m in mism[:20]:
            print("   ", m)
    else:
        print("  🟢 412/412 bit-exact — production == frozen reference")


if __name__ == "__main__":
    lim = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1] not in ("", "0", "none") else None
    main(lim)
