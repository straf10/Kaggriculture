#!/usr/bin/env python3
"""S9 review — ISSUED vs COMMITTED market orders, and the 10-order-per-turn headroom.

The plan's H3/H4 wheat argument ("290 FEED/round, we already BUY 216 WHEAT units") is read
from ISSUED orders. `_commit_unit` (kaggriculture.py:652) can refuse a BUY_PRODUCT on cash or
on a full shed and a SELL on an empty shed, so issued != committed. Both are counted here, per
seat (the seat is recovered from the identity of the `private` dict the engine is handed, so
the real two-sided market is simulated — no seat is blanked out).

Also counts the per-turn market-order occupancy that any mandatory-liquidation rule has to fit
inside: `_process_market` truncates the queue to `q[:10]` (kaggriculture.py:562) and the
discard is silent.

Output: data/derived/s9_commit_audit.json
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "engine_reference"))

import kaggriculture as engine  # noqa: E402
import harness.metrics as MET  # noqa: E402
from analysis.s8_replay_io import SUBMISSIONS, ladder_episodes, our_seat  # noqa: E402

OUT = ROOT / "data" / "derived" / "s9_commit_audit.json"
_real_commit = engine._commit_unit
SEAT_OF: dict[int, int] = {}
COMMITTED = [defaultdict(int), defaultdict(int)]
REFUSED = [defaultdict(int), defaultdict(int)]


def _patched(op, item, price, farm, private, market, shed_capacity=100):
    ok = _real_commit(op, item, price, farm, private, market, shed_capacity)
    seat = SEAT_OF.get(id(private))
    if seat is not None:
        (COMMITTED if ok else REFUSED)[seat][f"{op}:{item}"] += 1
    return ok


_real_te = MET._transition_events


def _te(prev, cur, cfg):
    """Wrap the meter so the per-seat `private` dicts it builds are registered first."""
    import copy
    privates = [copy.deepcopy(prev[s]["observation"]["private"]) for s in (0, 1)]
    SEAT_OF.clear()
    for s in (0, 1):
        SEAT_OF[id(privates[s])] = s
    # rebuild the meter's own path with our registered dicts
    farms = copy.deepcopy(prev[0]["observation"]["farms"])
    market = copy.deepcopy(prev[0]["observation"]["market"])
    actions = [MET._action(cur, s) for s in (0, 1)]
    prev_day = int(prev[0]["observation"].get("day", 0))
    MET._apply_unit_actions(farms, privates, actions, cfg, prev_day)
    MET._simulate_market(farms, privates, market, actions, cfg)


def main(limit=None):
    engine._commit_unit = _patched
    MET.engine._commit_unit = _patched
    rows = []
    n = 0
    for sub in SUBMISSIONS:
        for eid, m in ladder_episodes(sub):
            seat = our_seat(m["teams"])
            if seat is None:
                continue
            steps, cfg = m["steps"], m["configuration"]
            occ = defaultdict(int)
            occ_late = defaultdict(int)      # steps >= 690 only
            for t in range(1, len(steps)):
                mk = list((steps[t][seat].get("action") or {}).get("market") or [])
                occ[min(len(mk), 15)] += 1
                if t - 1 >= 690:
                    occ_late[min(len(mk), 15)] += 1
            for s in (0, 1):
                COMMITTED[s].clear()
                REFUSED[s].clear()
            for i in range(1, len(steps)):
                _te(steps[i - 1], steps[i], cfg)
            rows.append(dict(submission=sub, episode_id=eid, seat=seat,
                             committed=dict(COMMITTED[seat]), refused=dict(REFUSED[seat]),
                             committed_opp=dict(COMMITTED[1 - seat]),
                             refused_opp=dict(REFUSED[1 - seat]),
                             occ={str(k): v for k, v in occ.items()},
                             occ_late={str(k): v for k, v in occ_late.items()}))
            n += 1
            if n % 25 == 0:
                print(f"  {n}", flush=True)
            if limit and n >= limit:
                break
        if limit and n >= limit:
            break
    OUT.write_text(json.dumps(rows))
    print("wrote", OUT, n)


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else None)
