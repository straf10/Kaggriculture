#!/usr/bin/env python3
"""S9 review — the H2 "floor guard with a bounded hold" ceiling.

Rule under test (plan §3, H2): a WOOL / late-STRAWBERRY sale priced below F_p is deferred and
re-sold within D_p days, subject to a shed hold cap.

This computes an ORACLE ceiling: the deferred block is re-priced at the single BEST later step
inside the window, against the RECORDED market-inventory path, unit by unit so our own impact is
charged (`_commit_unit` :652 — a $1 sale adds no inventory). It needs foresight the agent will
not have, so it is an upper bound on any implementable H2.

Reported split by whether the town drew a YARN_STORE (the rule's own precondition) and by the
hold cap, which §8 of this review measures at 16 units (min over 253 of 100 - peak post-drop
shed occupancy).

Output: data/derived/s9_h2_bound.json
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "engine_reference"))

import kaggriculture as K  # noqa: E402
from analysis.s8_replay_io import SUBMISSIONS, ladder_episodes, our_seat  # noqa: E402
from harness.metrics import _transition_events  # noqa: E402

OUT = ROOT / "data" / "derived" / "s9_h2_bound.json"
TPD = 24
F = {"WOOL": 50, "STRAWBERRY": 25}
D_DAYS = 4
CAPS = (12, 16, 20, 999)


def batch_revenue(item, inv0, n):
    inv, tot = inv0, 0
    for _ in range(n):
        p = K.market_price(item, inv)
        tot += p
        if p > 1:
            inv += 1
    return tot


def main(limit=None):
    rows = []
    n_ep = 0
    for sub in SUBMISSIONS:
        for eid, m in ladder_episodes(sub):
            seat = our_seat(m["teams"])
            if seat is None:
                continue
            steps, cfg = m["steps"], m["configuration"]
            inv_at = [steps[t][0]["observation"]["market"]["inventory"] for t in range(len(steps))]
            shops = list(steps[-1][0]["observation"]["town"].get("unlocked_shops", []))
            byb = defaultdict(list)
            for i in range(1, len(steps)):
                _a, _o, sales, _ab, _h = _transition_events(steps[i - 1], steps[i], cfg)
                t = i - 1
                for s in sales[seat]:
                    if s["item"] in F:
                        byb[(t // TPD, s["item"])].append((t, s["price"]))
            gain = {c: defaultdict(float) for c in CAPS}
            for (day, item), lst in byb.items():
                if item == "STRAWBERRY" and day < 22:
                    continue
                cheap = [(t, p) for t, p in lst if p < F[item]]
                if not cheap:
                    continue
                last = max(t for t, _p in cheap)
                for cap in CAPS:
                    take = cheap[:cap] if cap < len(cheap) else cheap
                    n = len(take)
                    actual = sum(p for _t, p in take)
                    best = actual
                    for t2 in range(last + 1, min(last + D_DAYS * TPD, len(inv_at) - 1) + 1):
                        r = batch_revenue(item, inv_at[t2][item], n)
                        if r > best:
                            best = r
                    gain[cap][item] += best - actual
            rows.append(dict(submission=sub, episode_id=eid,
                             yarn=shops.count("YARN_STORE"),
                             gain={str(c): dict(v) for c, v in gain.items()}))
            n_ep += 1
            if n_ep % 25 == 0:
                print(f"  {n_ep}", flush=True)
            if limit and n_ep >= limit:
                break
        if limit and n_ep >= limit:
            break
    OUT.write_text(json.dumps(rows))
    print("wrote", OUT, n_ep)


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else None)
