#!/usr/bin/env python3
"""T2 diagnostic — WHY does a strawberry-only overlay regress the bank even though it only moves
strawberry sells (production byte-identical)? Decompose one matchup: revenue by product, shed
overflow burnt, animals escaped, priced losses — raw tape vs overlay(floor 8) vs overlay(floor 40).
The suspect (Phase 0 §3): the tape's shed runs at 95-100, so its strawberry sells are load-bearing
for shed capacity; delaying/metering them overflows the shed and burns higher-value products."""
from __future__ import annotations
import json, sys, statistics
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from harness.play import play
from agent.tape_overlay import make_overlay_agent

DONORS = ROOT / "baselines" / "2026-08-11" / "donors"
VALMORLEE, KAITO = 91456307, 90891564


def _stream(ep):
    return json.loads((DONORS / f"{ep}_seat0.json").read_text())["donor_action_stream"]


def _tape(stream):
    n = len(stream)
    def a(obs, configuration=None):
        s = obs.get("step", 0) if hasattr(obs, "get") else int(getattr(obs, "step", 0))
        return stream[s] if 0 <= s < n else {"farmer": ["PASS"], "hands": [], "market": []}
    return a


KEYS = ["shed_overflow_burnt", "animals_escaped", "plant_decay_units_lost",
        "crop_tile_days", "crop_revenue"]


def summarize(label, agents, opp, seeds):
    banks, rev, burnt, esc = [], {}, [], []
    per = {k: [] for k in KEYS}
    strawrev, strawunits = [], []
    for seed in seeds:
        r = play(agents(), opp, seed=seed, metrics=True, strict=False, record=False)
        m = r.metrics[0]
        banks.append(r.rewards[0])
        for k in KEYS:
            per[k].append(m.get(k))
        rb = m.get("revenue_by_product", {})
        for p, v in rb.items():
            rev.setdefault(p, []).append(v)
        strawrev.append(rb.get("STRAWBERRY", 0))
        strawunits.append(m.get("units_sold_by_product", {}).get("STRAWBERRY", 0))
    med = lambda xs: statistics.median([x for x in xs if x is not None]) if any(x is not None for x in xs) else None
    print(f"--- {label} ---")
    print(f"    bank ${med(banks):,.0f}   straw_rev ${med(strawrev):,.0f}  straw_units {med(strawunits):.0f}")
    for k in KEYS:
        print(f"    {k:22s} {med(per[k])}")
    print(f"    revenue_by_product: " + "  ".join(
        f"{p}=${med(v):,.0f}" for p, v in sorted(rev.items())))
    print()
    return med(banks)


def main():
    seeds = list(range(6))
    valm = _stream(VALMORLEE)
    for opp_name, opp in [("kaito_opp", _tape(_stream(KAITO)))]:
        print(f"========== opponent: {opp_name} ==========")
        summarize("RAW TAPE", lambda: _tape(valm), opp, seeds)
        summarize("overlay floor=8", lambda: make_overlay_agent(valm, floor_override={"STRAWBERRY": 8}), opp, seeds)
        summarize("overlay floor=40", lambda: make_overlay_agent(valm, floor_override={"STRAWBERRY": 40}), opp, seeds)


if __name__ == "__main__":
    main()
