#!/usr/bin/env python3
"""T2 viability probe — with the sell-ahead controller ACTUALLY engaged (a strawberry floor near
the ~$120 equilibrium price, not the inert $8), can the overlay beat the raw tape's realised
STRAWBERRY $/unit against a strawberry-flooding opponent? One decisive probe over a few principled
floors — if none beats the tape, the closed-loop-market hypothesis is refuted for this tape and we
STOP (not a parameter search: we are testing whether the mechanism can win at all)."""
from __future__ import annotations
import json, statistics, sys
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


def _straw(m):
    return (m.get("average_sell_price", {}).get("STRAWBERRY"),
            m.get("units_sold_by_product", {}).get("STRAWBERRY", 0))


def _med(xs):
    xs = [x for x in xs if x is not None]
    return statistics.median(xs) if xs else None


def main():
    seeds = list(range(6))
    valm = _stream(VALMORLEE)
    raw = _tape(valm)
    opponents = {"raw_tape_opp": _tape(_stream(VALMORLEE)), "kaito_opp": _tape(_stream(KAITO)),
                 "meta_route": META_ROUTE}
    floors = [8, 40, 80, 120, 160]

    for opp_name, opp in opponents.items():
        print(f"=== opponent: {opp_name} ===")
        raw_p, raw_u, raw_b = [], [], []
        for seed in seeds:
            r = play(raw, opp, seed=seed, metrics=True, strict=False, record=False)
            p, u = _straw(r.metrics[0]); raw_p.append(p); raw_u.append(u); raw_b.append(r.rewards[0])
        print(f"  RAW TAPE   straw ${_med(raw_p):.1f}/u  units {_med(raw_u):.0f}  bank ${_med(raw_b):,.0f}")
        for fl in floors:
            ps, us, bs = [], [], []
            for seed in seeds:
                ov = make_overlay_agent(valm, floor_override={"STRAWBERRY": fl})
                r = play(ov, opp, seed=seed, metrics=True, strict=False, record=False)
                p, u = _straw(r.metrics[0]); ps.append(p); us.append(u); bs.append(r.rewards[0])
            mp = _med(ps)
            tag = "PASS" if mp and mp > _med(raw_p) else "fail"
            print(f"  floor ${fl:3d}  straw ${mp:.1f}/u  units {_med(us):.0f}  "
                  f"bank ${_med(bs):,.0f}   [{tag} vs raw ${_med(raw_p):.1f}]")
        print()


if __name__ == "__main__":
    main()
