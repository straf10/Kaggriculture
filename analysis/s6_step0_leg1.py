#!/usr/bin/env python3
"""S6 step 0, leg 1 — the same-town control (ROADMAP §4.3 S6 step 0; can end the pass).

§4.1b established that comparing realised $/unit *across* episodes measures the town's random
shop draw, not the agent. The controlled comparison is **the two seats inside one episode**:
one shared town, one shared market, both seats visible. So we replay each donor tape against a
same-route opponent (another meta-line tape — R26/A2), both seats, and for each episode record
both seats' realised $/unit on STRAWBERRY / WOOL / MILK together with that episode's shop drain.

The pre-registered mechanism (S6 step 0): *our shipped tape's market queue is frozen at its
donor's ordering, so it cannot condition on the town, and if that costs realised price the tape
sits below 1,0× against a same-town opponent running the same route.*

Kill: if a tape already sits at >=1,05x against same-town opponents on all three products, the
mechanism is refuted — do not build C-A/C-B.

Also runs each tape against `meta_route` and `checkpoints/v1u_base/main.py` so the figure is not
one pairing. R21: the seed set's realised shop-draw distribution is reported next to the ratios.

Usage:
    python analysis/s6_step0_leg1.py --seeds 0-47 --robust-seeds 0-23
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections import defaultdict
from itertools import permutations
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from kaggle_environments import make  # noqa: E402

from analysis.donor_streams import DONORS, available, make_donor_tape  # noqa: E402
from analysis.v1v_shop_demand import units_per_tick  # noqa: E402
from harness.metrics import _transition_events  # noqa: E402
from harness.play import resolve_agent  # noqa: E402

PREMIUM = ("STRAWBERRY", "WOOL", "MILK")
V1U_BASE = Path("checkpoints/v1u_base/main.py")
META_ROUTE = Path("harness/bench_agents/meta_route.py")


def _realised_both_seats(env_json: dict) -> tuple[dict, dict]:
    """Realised premium $/unit + units for both seats, via a market-only replay of every
    transition. Skips extract_metrics' per-tile loss-counter scan (not needed here), so leg 1
    runs several times faster than the full metrics pass."""
    steps = env_json["steps"]
    configuration = env_json.get("configuration", {})
    rev = [defaultdict(float), defaultdict(float)]
    units = [defaultdict(int), defaultdict(int)]
    for i in range(1, len(steps)):
        _actions, _overflow, sales, _aborted, _harv = _transition_events(
            steps[i - 1], steps[i], configuration)
        for seat in (0, 1):
            for sale in sales[seat]:
                if sale["item"] in PREMIUM:
                    rev[seat][sale["item"]] += sale["price"]
                    units[seat][sale["item"]] += 1
    out = []
    for seat in (0, 1):
        out.append({p: {"realised": rev[seat][p] / units[seat][p], "units": units[seat][p]}
                    for p in PREMIUM if units[seat].get(p)})
    return out[0], out[1]


def _shop_drain(env_json: dict) -> dict:
    shops = list(env_json["steps"][-1][0]["observation"]["town"].get("unlocked_shops") or ())
    upt = units_per_tick(shops)
    return {p: upt.get(p, 0) for p in PREMIUM}


def _parse_seeds(spec: str) -> list[int]:
    out: list[int] = []
    for part in spec.split(","):
        if "-" in part:
            a, b = part.split("-")
            out.extend(range(int(a), int(b) + 1))
        else:
            out.append(int(part))
    return out


def run_pairing(name_a, agent_a, name_b, agent_b, seeds, run_dir=None) -> list[dict]:
    """Play agent_a @ seat0 vs agent_b @ seat1 over seeds; record both seats + shop drain.
    Runs in-memory (no gzip round-trip): env.run -> toJSON -> market-only extraction."""
    a = resolve_agent(agent_a) if isinstance(agent_a, str) else agent_a
    b = resolve_agent(agent_b) if isinstance(agent_b, str) else agent_b
    rows = []
    for seed in seeds:
        env = make("kaggriculture", configuration={"seed": seed})
        env.run([a, b])
        env_json = env.toJSON()
        statuses = [{s["status"] for step in env_json["steps"] for s in (step[seat],)}
                    for seat in (0, 1)]
        if any(st - {"ACTIVE", "DONE", "INACTIVE"} for st in statuses):
            print(f"    seed {seed} {name_a} v {name_b}: NOT CLEAN {statuses}", file=sys.stderr)
            continue
        r0, r1 = _realised_both_seats(env_json)
        rows.append({
            "seed": seed,
            "seat0_agent": name_a, "seat1_agent": name_b,
            "shop_drain": _shop_drain(env_json),
            "seat0": {"bank": env_json["rewards"][0], "realised": r0},
            "seat1": {"bank": env_json["rewards"][1], "realised": r1},
        })
    return rows


def _focal_opp_ratios(rows, focal, product):
    """(focal_realised, opp_realised, ratio, drain) for episodes where focal is a seat and
    both seats sold `product`. focal appears as seat0 in some rows and seat1 in others."""
    out = []
    for r in rows:
        for fs, os_ in ((0, 1), (1, 0)):
            if r[f"seat{fs}_agent"] != focal:
                continue
            fr = r[f"seat{fs}"]["realised"].get(product)
            orr = r[f"seat{os_}"]["realised"].get(product)
            if fr and orr and orr["units"] and fr["units"]:
                out.append((fr["realised"], orr["realised"],
                            fr["realised"] / orr["realised"], r["shop_drain"][product]))
    return out


def _dist(xs):
    if not xs:
        return None
    s = sorted(xs)
    q = lambda p: s[min(len(s) - 1, int(p * (len(s) - 1)))]  # noqa: E731
    return {"n": len(s), "p10": q(.10), "p25": q(.25), "p50": statistics.median(s),
            "p75": q(.75), "p90": q(.90), "mean": statistics.fmean(s)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", default="0-47", help="tape-vs-tape (the kill test) seed set")
    ap.add_argument("--robust-seeds", default="0-23", help="tape vs meta_route / v1u_base")
    ap.add_argument("--out", type=Path, default=Path("data/derived/s6_step0_leg1.json"))
    args = ap.parse_args()

    for eid in DONORS:
        if not available(eid):
            raise SystemExit(f"donor {eid} absent — leg 1 needs the gitignored tapes locally")

    tapes = {team: make_donor_tape(eid) for eid, team in DONORS.items()}
    teams = list(tapes)  # [Valmorlee, Ueddy, Kaito]
    seeds = _parse_seeds(args.seeds)
    robust_seeds = _parse_seeds(args.robust_seeds)
    run_dir = Path("runs/s6_leg1")

    all_rows: list[dict] = []
    # Self-pairing: a tape against an *identical-route* opponent. This is the purest test of the
    # C-A mechanism — identical production and identical sells, so any seat0/seat1 realised-price
    # difference is pure queue-position/seat interaction, the only thing in-place reordering owns.
    self_rows: list[dict] = []
    for a in teams:
        print(f"self-pair: {a} @seat0 vs {a} @seat1  ({len(seeds)} seeds)")
        self_rows += run_pairing(a + "#0", tapes[a], a + "#1", tapes[a], seeds, run_dir)
    all_rows += self_rows
    # Core: every ordered tape-vs-tape pair (covers each tape at both seats vs each other).
    for a, b in permutations(teams, 2):
        print(f"tape-vs-tape: {a} @seat0 vs {b} @seat1  ({len(seeds)} seeds)")
        all_rows += run_pairing(a, tapes[a], b, tapes[b], seeds, run_dir)

    # Robustness: each tape vs meta_route and v1u_base, both seats.
    robust_opps = {"meta_route": str(META_ROUTE)}
    if V1U_BASE.exists():
        robust_opps["v1u_base"] = str(V1U_BASE)
    for team in teams:
        for oname, ospec in robust_opps.items():
            print(f"robust: {team} vs {oname}  ({len(robust_seeds)} seeds, both seats)")
            all_rows += run_pairing(team, tapes[team], oname, ospec, robust_seeds, run_dir)
            all_rows += run_pairing(oname, ospec, team, tapes[team], robust_seeds, run_dir)

    # ---- Summaries -------------------------------------------------------------------
    is_self = lambda r: "#" in r["seat0_agent"] or "#" in r["seat1_agent"]  # noqa: E731
    self_rows = [r for r in all_rows if is_self(r)]
    tape_rows = [r for r in all_rows
                 if not is_self(r) and r["seat0_agent"] in teams and r["seat1_agent"] in teams]
    robust_rows = [r for r in all_rows if not is_self(r) and r not in tape_rows]

    # Self-pair: seat0/seat1 realised ratio at identical route — pure queue/seat interaction.
    self_ratios = {}
    for team in teams:
        self_ratios[team] = {}
        for p in PREMIUM:
            xs = []
            for r in self_rows:
                if r["seat0_agent"] == team + "#0":
                    a = r["seat0"]["realised"].get(p)
                    b = r["seat1"]["realised"].get(p)
                    if a and b and a["units"] and b["units"]:
                        xs.append(a["realised"] / b["realised"])
            self_ratios[team][p] = _dist(xs)

    # R21: realised shop draw over the tape-vs-tape seed set.
    drain_dist = {p: _dist([r["shop_drain"][p] for r in tape_rows]) for p in PREMIUM}
    drain_hist = {p: dict(sorted(
        {d: sum(1 for r in tape_rows if r["shop_drain"][p] == d)
         for d in {rr["shop_drain"][p] for rr in tape_rows}}.items()))
        for p in PREMIUM}
    wool_zero = sum(1 for r in tape_rows if r["shop_drain"]["WOOL"] == 0)

    ratios = {}   # team -> product -> distribution vs same-town tapes
    kill = {}     # team -> bool (>=1.05x on all three)
    for team in teams:
        ratios[team] = {}
        ge = []
        for p in PREMIUM:
            fo = _focal_opp_ratios(tape_rows, team, p)
            d = _dist([x[2] for x in fo])
            ratios[team][p] = d
            ge.append(d is not None and d["p50"] >= 1.05)
        kill[team] = all(ge)

    # Robustness: tape realised vs each non-tape opponent, per product (same-town, diff production)
    robust_ratios = {team: {} for team in teams}

    def robust_pair_ratios(team, oname, product):
        out = []
        for r in robust_rows:
            for fs, os_ in ((0, 1), (1, 0)):
                if r[f"seat{fs}_agent"] == team and r[f"seat{os_}_agent"] == oname:
                    fr = r[f"seat{fs}"]["realised"].get(product)
                    orr = r[f"seat{os_}"]["realised"].get(product)
                    if fr and orr:
                        out.append(fr["realised"] / orr["realised"])
        return out
    for team in teams:
        for oname in ("meta_route", "v1u_base"):
            robust_ratios[team][oname] = {
                p: _dist(robust_pair_ratios(team, oname, p)) for p in PREMIUM}

    summary = {
        "n_self_episodes": len(self_rows),
        "n_tape_episodes": len(tape_rows),
        "n_robust_episodes": len(robust_rows),
        "self_pair_seat0_over_seat1": self_ratios,
        "seed_set_shop_drain": drain_dist,
        "seed_set_shop_hist": drain_hist,
        "wool_zero_towns": f"{wool_zero}/{len(tape_rows)} ({wool_zero / max(1, len(tape_rows)):.0%})",
        "same_town_tape_ratios": ratios,
        "kill_ge_1_05_on_all_three": kill,
        "robust_ratios": robust_ratios,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps({"summary": summary, "rows": all_rows}, indent=1),
                        encoding="utf-8")

    # ---- Print -----------------------------------------------------------------------
    print(f"\n{'='*72}\nLEG 1 — same-town control\n{'='*72}")
    print(f"self-pair episodes: {len(self_rows)}   tape-vs-tape: {len(tape_rows)}   "
          f"robust: {len(robust_rows)}")
    print(f"\nSelf-pair (identical route) seat0/seat1 realised ratio — pure queue/seat interaction:")
    print(f"  {'tape':<11}{'STRAWBERRY':>22}{'WOOL':>22}{'MILK':>22}")
    for team in teams:
        cells = ""
        for p in PREMIUM:
            d = self_ratios[team][p]
            cells += (f"{d['p50']:>10.3f} [{d['p10']:.2f}-{d['p90']:.2f}]" if d else f"{'—':>22}")
        print(f"  {team:<11}{cells}")
    print(f"\nR21 — shop drain over the tape-vs-tape seed set (units/tick):")
    for p in PREMIUM:
        print(f"  {p:<11} {drain_hist[p]}  median={drain_dist[p]['p50']}")
    print(f"  WOOL zero-drain towns: {summary['wool_zero_towns']}")

    print(f"\nSame-town ratio  (tape realised $/u  /  same-town tape opponent's), median [p10..p90]:")
    print(f"  {'tape':<11}{'STRAWBERRY':>22}{'WOOL':>22}{'MILK':>22}")
    for team in teams:
        cells = ""
        for p in PREMIUM:
            d = ratios[team][p]
            cells += (f"{d['p50']:>10.3f} [{d['p10']:.2f}-{d['p90']:.2f}]" if d else f"{'—':>22}")
        print(f"  {team:<11}{cells}")
        print(f"  {'':11}{'  n=' + str(ratios[team]['STRAWBERRY']['n']) if ratios[team]['STRAWBERRY'] else '':>22}")

    print(f"\nKILL TEST (>=1.05x median on ALL three products vs same-town tapes):")
    for team in teams:
        print(f"  {team:<11} {'REFUTES mechanism (STOP)' if kill[team] else 'does not refute'}")
    any_kill = any(kill.values())
    print(f"\n  => {'MECHANISM REFUTED — stop, do not build C-A/C-B' if any_kill else 'mechanism NOT refuted — proceed'}")

    print(f"\nRobustness — tape realised / opponent realised (same town, different production):")
    for team in teams:
        for oname in ("meta_route", "v1u_base"):
            cells = ""
            for p in PREMIUM:
                d = robust_ratios[team][oname][p]
                cells += (f"{d['p50']:>8.3f}(n{d['n']})" if d else f"{'—':>12}")
            print(f"  {team:<11} vs {oname:<10}{cells}")
    print(f"\nwrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
