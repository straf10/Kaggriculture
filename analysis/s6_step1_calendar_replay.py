#!/usr/bin/env python3
"""S6 step 1 — Phase 0, criterion 3: the same-town replay instrument (ROADMAP §4.3 S6 step 1).

The gate's third leg: replay each candidate donor against our three existing tapes with the town
held fixed, and require its realised premium $/unit ratio to be >= the **Valmorlee** tape's. This is
the same instrument step 0 used (analysis/s6_step0_leg1.py) — reused here with the candidate tapes
added to the pairing pool, so a candidate and Valmorlee are measured against the *same* opponents in
the *same* towns and their ratios are directly comparable.

Each candidate is frozen from ONE representative trace of its recorded 08-16 episodes (the median-
reward seat). NB the desync caveat: a candidate that runs a town-*adaptive* policy (low cross-trace
agreement) will desync when frozen and replayed in foreign towns, so its ratio here is a LOWER bound
on its true calendar quality. The recorded-episode same-town ratio (s6_step1_phase0.py calendar) is
the no-desync reference for those.

Usage:
    python analysis/s6_step1_calendar_replay.py --seeds 0-23
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from itertools import combinations
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from analysis.donor_streams import DONORS, available, make_donor_tape  # noqa: E402
from analysis.s1_extract_donors import action_stream  # noqa: E402
from analysis.s6_step0_leg1 import _dist, _parse_seeds, run_pairing  # noqa: E402
from analysis.tape_agent import make_tape_agent  # noqa: E402
from analysis.v1v_shop_demand import units_per_tick  # noqa: E402

PREMIUM = ("STRAWBERRY", "WOOL", "MILK")
ARCHIVE = ROOT / "data" / "archive" / "raw" / "2026-08-16"
INCUMBENTS = ["Valmorlee", "Ueddy", "Kaito"]

# Representative traces (median-reward seat) from s6_step1_phase0. Candidate -> (episode_id, seat).
# The good-calendar teams were surfaced by the all-42-team recorded-episode scan (calendar --all),
# NOT the reward-biased shortlist — the town-controlled ratio is the selector, not reward.
CANDIDATES = {
    "ReCurSiON": (93566154, 0),      # THE winner: field-best STR calendar (rec 1.339) + reconstructible
                                     #   (mktUnan 0.954, mktPrem-agr 0.873) — faithful when frozen
    "boatlee": (93503484, 0),        # STR 1.117 + reconstructible (agr 0.96) — second good calendar
    # kawashigi (best adaptive calendar, agr 0.32) and Victor (agr 0.98, neutral calendar) are already
    # settled by the recorded-episode scan (calendar --all) and do not need the replay's Valmorlee bar.
}


def build_candidate_tape(episode_id: int, seat: int):
    replay = json.loads((ARCHIVE / f"{episode_id}.json").read_text())
    if replay["configuration"].get("townCenterSellInterval") != 24:
        raise ValueError(f"{episode_id}: not current-engine")
    agent = make_tape_agent(action_stream(replay, seat))
    agent.__name__ = f"cand_{episode_id}_{seat}"
    return agent


def focal_ratios(rows, focal, opponents, product):
    """median realised ratio for `focal` vs same-town opponents restricted to `opponents`."""
    out = []
    for r in rows:
        for fs, os_ in ((0, 1), (1, 0)):
            if r[f"seat{fs}_agent"] != focal or r[f"seat{os_}_agent"] not in opponents:
                continue
            fr = r[f"seat{fs}"]["realised"].get(product)
            orr = r[f"seat{os_}"]["realised"].get(product)
            if fr and orr and fr["units"] and orr["units"]:
                out.append(fr["realised"] / orr["realised"])
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", default="0-23")
    ap.add_argument("--out", type=Path, default=ROOT / "data" / "derived" / "s6_step1_calendar_replay.json")
    args = ap.parse_args()
    seeds = _parse_seeds(args.seeds)

    for eid in DONORS:
        if not available(eid):
            raise SystemExit(f"incumbent donor {eid} absent — needs the gitignored tapes locally")
    tapes = {team: make_donor_tape(eid) for eid, team in DONORS.items()}
    for name, (eid, seat) in CANDIDATES.items():
        tapes[name] = build_candidate_tape(eid, seat)

    names = list(tapes)  # incumbents + candidates
    rows = []
    # Every candidate vs every incumbent (both seat orders).
    for cand in CANDIDATES:
        for inc in INCUMBENTS:
            print(f"pairing: {cand} vs {inc} ({len(seeds)} seeds, both orders)")
            rows += run_pairing(cand, tapes[cand], inc, tapes[inc], seeds)
            rows += run_pairing(inc, tapes[inc], cand, tapes[cand], seeds)
    # Incumbent-incumbent pairs (both orders) — gives Valmorlee its own same-town ratio.
    for a, b in combinations(INCUMBENTS, 2):
        print(f"pairing: {a} vs {b} ({len(seeds)} seeds, both orders)")
        rows += run_pairing(a, tapes[a], b, tapes[b], seeds)
        rows += run_pairing(b, tapes[b], a, tapes[a], seeds)

    # R21 shop draw over the seed set.
    drain = defaultdict(list)
    for r in rows:
        for p in PREMIUM:
            drain[p].append(r["shop_drain"][p])
    drain_dist = {p: _dist(drain[p]) for p in PREMIUM}
    wool_zero = sum(1 for r in rows if r["shop_drain"]["WOOL"] == 0)

    # Each candidate's ratio vs the incumbent pool; Valmorlee's ratio vs {Ueddy,Kaito}.
    results = {}
    for cand in CANDIDATES:
        results[cand] = {p: _dist(focal_ratios(rows, cand, set(INCUMBENTS), p)) for p in PREMIUM}
    results["Valmorlee"] = {p: _dist(focal_ratios(rows, "Valmorlee", {"Ueddy", "Kaito"}, p))
                            for p in PREMIUM}

    args.out.write_text(json.dumps({
        "seeds": args.seeds, "n_rows": len(rows),
        "shop_drain": drain_dist,
        "wool_zero": f"{wool_zero}/{len(rows)}",
        "ratios": results,
    }, indent=1))

    print(f"\n{'='*76}\nCRITERION 3 — same-town realised premium $/u ratio (median [p10-p90])\n{'='*76}")
    print(f"R21 shop drain: " + "  ".join(
        f"{p} med={drain_dist[p]['p50']}(n0={sum(1 for x in drain[p] if x==0)})" for p in PREMIUM))
    print(f"WOOL zero-drain: {wool_zero}/{len(rows)}\n")
    print(f"{'tape':<18}{'STRAWBERRY':>22}{'WOOL':>22}{'MILK':>22}{'n(STR)':>8}")
    order = ["Valmorlee"] + list(CANDIDATES)
    for name in order:
        cells = ""
        for p in PREMIUM:
            d = results[name][p]
            cells += (f"{d['p50']:>10.3f} [{d['p10']:.2f}-{d['p90']:.2f}]" if d else f"{'—':>22}")
        n = results[name]["STRAWBERRY"]["n"] if results[name]["STRAWBERRY"] else 0
        print(f"{name:<18}{cells}{n:>8}")

    vbar = results["Valmorlee"]
    print(f"\nGATE (candidate ratio >= Valmorlee's on premium products):")
    for cand in CANDIDATES:
        verdict = []
        for p in PREMIUM:
            c = results[cand][p]
            v = vbar[p]
            if c and v:
                verdict.append(f"{p[:3]}:{'PASS' if c['p50'] >= v['p50'] else 'fail'}({c['p50']:.2f}v{v['p50']:.2f})")
        print(f"  {cand:<18} {'  '.join(verdict)}")
    print(f"\nwrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
