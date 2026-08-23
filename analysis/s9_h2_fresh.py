#!/usr/bin/env python3
"""S9 — the FRESH out-of-sample confirm of the frozen H2 arm (review §4γ).

The dev/holdout split of the 253 on-disk replays is spent: dev designed the rule, holdout was
read once and the pre-registered A1 failed there for lack of power (4 discordant pairs where the
exact McNemar floor is 6). This runs the SAME frozen arm - no parameter touched - against 159
episodes that were never on disk when the rule was written, downloaded into separate directories
so no earlier analysis changes sample.

Criterion F1-F7 is pre-registered in baselines/2026-08-23/s9_plan_review.md §4γ, written before
this ran. Nothing here may be edited to change what passes.

Output: data/derived/s9_h2_fresh.json
"""
from __future__ import annotations

import json
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import analysis.s8_replay_io as RIO  # noqa: E402

# Point the one parser at the fresh archives. Mutated in place so `ladder_episodes` /
# `replay_paths` (which read this module-level dict) follow, and ONLY for this script.
RIO.SUBMISSIONS = {
    "55586926": RIO.RAW / "live_55586926_fresh",
    "55675634": RIO.RAW / "live_55675634_fresh",
}

from analysis.s8_replay_io import ladder_episodes, our_seat  # noqa: E402
from analysis.s9_h2_a8 import run_one  # noqa: E402

OUT = ROOT / "data" / "derived" / "s9_h2_fresh.json"


def main(limit=None):
    jobs = []
    for sub in RIO.SUBMISSIONS:
        for eid, m in ladder_episodes(sub):
            if our_seat(m["teams"]) is None:
                continue
            jobs.append((sub, eid, m["teams"], m["rewards"], m["seed"], m["steps"], "tail"))
            if limit and len(jobs) >= limit:
                break
        if limit and len(jobs) >= limit:
            break
    print(f"FRESH confirm: {len(jobs)} episodes x 2 replays", flush=True)
    rows = []
    with ProcessPoolExecutor() as ex:
        for i, row in enumerate(ex.map(run_one, jobs), 1):
            rows.append(row)
            if i % 20 == 0:
                print(f"  {i}/{len(jobs)}", flush=True)
    OUT.write_text(json.dumps(rows))
    print("wrote", OUT)


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1] not in ("", "0", "none") else None)
