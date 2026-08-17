#!/usr/bin/env python3
"""T2 — test the pull-forward-only (augment) design Phase 0 §3 prescribed: keep the tape's sells
verbatim, only ADD early strawberry sells before the tape's own strawberry window (~step 336),
so shed occupancy is monotonically <= the tape's. Pass = beats the RAW TAPE on the acceptance
gate's first number (median final bank) AND on strawberry $/unit, with shed_overflow_burnt not
worse. Fail on bank => STOP."""
from __future__ import annotations
import json, sys, statistics
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from harness.play import play
from agent.tape_overlay import make_overlay_agent

DONORS = ROOT / "baselines" / "2026-08-11" / "donors"
META_ROUTE = str(ROOT / "harness" / "bench_agents" / "meta_route.py")
VALMORLEE, KAITO = 91456307, 90891564


def _stream(ep):
    return json.loads((DONORS / f"{ep}_seat0.json").read_text())["donor_action_stream"]


def _tape(stream):
    n = len(stream)
    def a(obs, configuration=None):
        s = obs.get("step", 0) if hasattr(obs, "get") else int(getattr(obs, "step", 0))
        return stream[s] if 0 <= s < n else {"farmer": ["PASS"], "hands": [], "market": []}
    return a


def _m(r):
    m = r.metrics[0]
    return (r.rewards[0], m.get("average_sell_price", {}).get("STRAWBERRY"),
            m.get("units_sold_by_product", {}).get("STRAWBERRY", 0),
            m.get("shed_overflow_burnt"), m.get("animals_escaped"))


def med(xs):
    xs = [x for x in xs if x is not None]
    return statistics.median(xs) if xs else None


def main():
    seeds = list(range(8))
    valm = _stream(VALMORLEE)
    raw = _tape(valm)
    opponents = {"raw_tape_opp": _tape(_stream(VALMORLEE)), "kaito_opp": _tape(_stream(KAITO)),
                 "meta_route": META_ROUTE}
    # augment probe over a few floors on the early window
    floors = [8, 40, 80, 120]
    for opp_name, opp in opponents.items():
        print(f"=== opponent: {opp_name} ===")
        R = [ _m(play(raw, opp, seed=s, metrics=True, strict=False, record=False)) for s in seeds ]
        rb, rp, ru, rburn = med([x[0] for x in R]), med([x[1] for x in R]), med([x[2] for x in R]), med([x[3] for x in R])
        print(f"  RAW TAPE     bank ${rb:,.0f}  straw ${rp:.1f}/u  units {ru:.0f}  burnt {rburn}")
        for fl in floors:
            O = []
            for s in seeds:
                ov = make_overlay_agent(valm, mode="augment", floor_override={"STRAWBERRY": fl})
                O.append(_m(play(ov, opp, seed=s, metrics=True, strict=False, record=False)))
            ob, op, ou, oburn, oesc = (med([x[0] for x in O]), med([x[1] for x in O]),
                                       med([x[2] for x in O]), med([x[3] for x in O]), med([x[4] for x in O]))
            bank_tag = "PASS" if ob > rb else "fail"
            print(f"  augment ${fl:3d} bank ${ob:,.0f} [{bank_tag}]  straw ${op:.1f}/u  "
                  f"units {ou:.0f}  burnt {oburn}  esc {oesc}")
        print()


if __name__ == "__main__":
    main()
