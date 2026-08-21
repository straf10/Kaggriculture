#!/usr/bin/env python3
"""S6 step 1 — build the majority-vote reconstruction and prove its shed headroom (§4.5(b)).

Once Phase 0 selects a donor, §4.5(b)'s method reconstructs a *policy* from multiple traces of one
submission: per decision point, the modal action across the donor's own episodes. This is a
measurement of the policy, not a copy of one performance (V16-RC5). This module:

  build     — majority-vote the donor's traces into one route; record the disagreement set (the
              state-dependent part the adaptive layer must later cover); save it (gitignored).
  fidelity  — S1.2 protocol: replay the reconstruction against the donor's own recorded opponents
              under the recorded seeds; compare bank to the recorded donor bank within a tolerance.
              A reconstruction worse than the raw tape is not a platform.
  shed      — the headroom the whole pass exists for: the reconstruction's shed-occupancy curve vs
              the Valmorlee tape's. T2 measured the Valmorlee tape at a *sustained* 98/100; if the
              reconstruction is also pinned near full, the cross-turn lever is still blocked.

Everything derived from the donor's action streams is gitignored (§2.4b / R11). No `agent/` change.

Usage:
    python analysis/s6_step1_reconstruct.py build --team ReCurSiON
    python analysis/s6_step1_reconstruct.py fidelity --team ReCurSiON --n 12
    python analysis/s6_step1_reconstruct.py shed --team ReCurSiON --seeds 0-15
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from kaggle_environments import make  # noqa: E402

from analysis.donor_streams import make_donor_tape  # noqa: E402
from analysis.s1_extract_donors import action_stream  # noqa: E402
from analysis.s6_step1_phase0 import (  # noqa: E402
    ARCHIVE,
    LIVE_ENGINE,
    _load_inventory,
    _reload_streams,
)
from analysis.tape_agent import make_tape_agent  # noqa: E402

DERIVED = ROOT / "data" / "derived"
VALMORLEE_EID = 91456307
PASS_ACTION = {"farmer": ["PASS"], "hands": [], "market": []}


def _decanon_prod(canon: str):
    if canon == "PASS":
        return ["PASS"], []
    farmer, hands = json.loads(canon)
    return farmer, hands


def _team_members(team: str) -> list[dict]:
    rows = _load_inventory()
    live = [r for r in rows if r["version"] == LIVE_ENGINE and r["clean"] and r["team"] == team]
    if not live:
        raise SystemExit(f"no live clean traces for team {team!r}")
    # one submission = one opening fingerprint; take the largest opening cluster (the shared line)
    by_open = defaultdict(list)
    for r in live:
        by_open[r["fp_prod_open"]].append(r)
    fp, members = max(by_open.items(), key=lambda kv: len(kv[1]))
    return sorted(members, key=lambda m: (m["episode_id"], m["seat"]))


def build_reconstruction(team: str, cap: int) -> dict:
    members = _team_members(team)[:cap]
    traces = [(_reload_streams(m["episode_id"], m["seat"])[:2]) for m in members]
    prod_streams = [t[0] for t in traces]
    market_streams = [t[1] for t in traces]
    T = min(len(p) for p in prod_streams)
    n = len(traces)

    stream = []
    disagree_prod, disagree_market = [], []
    prod_modal_share, mkt_modal_share = [], []
    for t in range(T):
        pc = Counter(prod_streams[i][t] for i in range(n))
        mc = Counter(market_streams[i][t] for i in range(n))
        p_canon, p_cnt = pc.most_common(1)[0]
        m_canon, m_cnt = mc.most_common(1)[0]
        prod_modal_share.append(p_cnt / n)
        mkt_modal_share.append(m_cnt / n)
        if p_cnt < n:
            disagree_prod.append(t)
        if m_cnt < n:
            disagree_market.append(t)
        farmer, hands = _decanon_prod(p_canon)
        market = json.loads(m_canon)
        stream.append({"farmer": farmer, "hands": hands, "market": market})

    out = {
        "team": team, "n_traces": n, "n_steps": T,
        "episodes_used": [(m["episode_id"], m["seat"]) for m in members],
        "prod_modal_share_mean": statistics.fmean(prod_modal_share),
        "market_modal_share_mean": statistics.fmean(mkt_modal_share),
        "n_disagree_prod": len(disagree_prod), "n_disagree_market": len(disagree_market),
        "disagree_market_steps": disagree_market,
        "stream": stream,
    }
    return out


def _run_shed_curve(agent_a, agent_b, seed: int, focal_seat: int) -> list[int]:
    env = make("kaggriculture", configuration={"seed": seed})
    env.run([agent_a, agent_b])
    ej = env.toJSON()
    curve = []
    for st in ej["steps"]:
        sh = st[focal_seat]["observation"].get("private", {}).get("shed")
        if isinstance(sh, dict):
            curve.append(sum(sh.values()))
    return curve, ej["rewards"][focal_seat], ej


def cmd_build(args) -> int:
    rec = build_reconstruction(args.team, args.cap)
    path = DERIVED / f"s6_step1_reconstruction_{args.team}.json"
    path.write_text(json.dumps(rec, separators=(",", ":")))
    print(f"team={rec['team']}  traces={rec['n_traces']}  steps={rec['n_steps']}")
    print(f"production modal-share mean: {rec['prod_modal_share_mean']:.4f}  "
          f"disagree steps: {rec['n_disagree_prod']}")
    print(f"market     modal-share mean: {rec['market_modal_share_mean']:.4f}  "
          f"disagree steps: {rec['n_disagree_market']}  "
          f"({rec['n_disagree_market']}/{rec['n_steps']} = "
          f"{rec['n_disagree_market']/rec['n_steps']:.1%} state-dependent)")
    print(f"wrote {path} (gitignored)")
    return 0


def _load_reconstruction(team: str) -> dict:
    path = DERIVED / f"s6_step1_reconstruction_{team}.json"
    if not path.exists():
        raise SystemExit(f"{path} missing — run `build --team {team}` first")
    return json.loads(path.read_text())


def cmd_fidelity(args) -> int:
    """S1.2: reconstruction (as donor seat) vs each recorded opponent under its recorded seed;
    compare to the recorded DONOR bank. The reconstruction is town-independent while the real policy
    adapts, so this measures how faithfully the fixed modal route stands in for the policy."""
    from harness.play import play
    rec = _load_reconstruction(args.team)
    recon = make_tape_agent(rec["stream"])
    members = _team_members(args.team)[:args.n]
    errs, banks = [], []
    print(f"fidelity — reconstruction vs recorded opponents ({len(members)} episodes):")
    for m in members:
        replay = json.loads((ARCHIVE / f"{m['episode_id']}.json").read_text())
        seed = replay["info"].get("seed")
        donor_seat = m["seat"]
        opp = make_tape_agent(action_stream(replay, 1 - donor_seat))
        a, b = (recon, opp) if donor_seat == 0 else (opp, recon)
        res = play(a, b, seed=seed, steps=720, record=False, strict=False, metrics=False)
        rep_bank = res.rewards[donor_seat]
        rec_bank = replay["rewards"][donor_seat]
        err = abs(rep_bank - rec_bank) / abs(rec_bank) if rec_bank else None
        errs.append(err)
        banks.append(rep_bank)
        print(f"  ep {m['episode_id']} s{donor_seat}: recon=${rep_bank:>10,.0f}  "
              f"recorded=${rec_bank:>10,.0f}  err={err:.2%}  clean={res.clean}")
    med = statistics.median([e for e in errs if e is not None])
    print(f"\nmedian abs error: {med:.2%}   median recon bank: ${statistics.median(banks):,.0f}")
    return 0


def cmd_shed(args) -> int:
    """Shed-occupancy curve of the reconstruction vs the Valmorlee tape, same opponents & seeds.
    Reports peak / median / p90 and the fraction of season-steps at >=90/100 (metering-blocked)."""
    from analysis.s6_step0_leg1 import _parse_seeds
    rec = _load_reconstruction(args.team)
    recon = make_tape_agent(rec["stream"])
    valmorlee = make_donor_tape(VALMORLEE_EID)
    opp = make_donor_tape(VALMORLEE_EID)  # a fixed same-line opponent for both, so the town matches
    seeds = _parse_seeds(args.seeds)

    def curves(agent, name):
        allc = []
        for s in seeds:
            c, _bank, _ej = _run_shed_curve(agent, opp, s, 0)
            allc.append(c)
        flat = [x for c in allc for x in c]
        peaks = [max(c) for c in allc]
        blocked = sum(1 for x in flat if x >= 90) / len(flat)
        print(f"  {name:<16} peak(med)={statistics.median(peaks):>4.0f}  season median={statistics.median(flat):>4.0f}  "
              f"p90={sorted(flat)[int(0.9*len(flat))]:>4}  >=90/100: {blocked:.1%}")
        return {"peak_med": statistics.median(peaks), "median": statistics.median(flat),
                "p90": sorted(flat)[int(0.9 * len(flat))], "blocked_frac": blocked}

    print(f"shed occupancy over {len(seeds)} seeds (vs Valmorlee-tape opponent, seat 0):")
    r = curves(recon, args.team)
    v = curves(valmorlee, "Valmorlee tape")
    out = {"team": args.team, "seeds": args.seeds, "reconstruction": r, "valmorlee_tape": v}
    (DERIVED / f"s6_step1_shed_{args.team}.json").write_text(json.dumps(out, indent=1))
    print(f"\nheadroom: reconstruction blocked {r['blocked_frac']:.1%} of steps vs "
          f"Valmorlee tape {v['blocked_frac']:.1%}")
    return 0


def cmd_bank(args) -> int:
    """Score the reconstruction in the ladder's currency (§2.1.4): median bank + W/L vs each
    incumbent tape, both seats. The gate comparison is against the raw Valmorlee tape (the incumbent,
    per the brief), not v1u_base. Reuses the leg-1 pairing machinery; R21 draw reported."""
    from analysis.donor_streams import DONORS
    from analysis.s6_step0_leg1 import _dist, _parse_seeds, run_pairing
    rec = _load_reconstruction(args.team)
    recon = make_tape_agent(rec["stream"])
    incumbents = {team: make_donor_tape(eid) for eid, team in DONORS.items()}
    seeds = _parse_seeds(args.seeds)

    print(f"reconstruction bank vs incumbent tapes ({len(seeds)} seeds, both seats):")
    print(f"{'opponent':<12}{'recon med bank':>16}{'opp med bank':>16}{'W-L-T':>10}{'mean diff':>12}")
    summary = {}
    for team, opp in incumbents.items():
        rows = run_pairing(args.team, recon, team, opp, seeds) + run_pairing(team, opp, args.team, recon, seeds)
        rb, ob, diffs = [], [], []
        w = l = t = 0
        for r in rows:
            for fs in (0, 1):
                if r[f"seat{fs}_agent"] == args.team:
                    my, their = r[f"seat{fs}"]["bank"], r[f"seat{1-fs}"]["bank"]
                    rb.append(my); ob.append(their); diffs.append(my - their)
                    w += my > their; l += my < their; t += my == their
        summary[team] = {"recon_median": statistics.median(rb), "opp_median": statistics.median(ob),
                         "record": f"{w}-{l}-{t}", "mean_diff": statistics.fmean(diffs)}
        print(f"{team:<12}{statistics.median(rb):>16,.0f}{statistics.median(ob):>16,.0f}"
              f"{w:>4}-{l}-{t}{statistics.fmean(diffs):>12,.0f}")
    (DERIVED / f"s6_step1_bank_{args.team}.json").write_text(json.dumps(summary, indent=1))
    print(f"\n(vs the raw Valmorlee tape is the gate comparison — the tape is the incumbent, not v1u_base)")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build"); b.add_argument("--team", required=True); b.add_argument("--cap", type=int, default=50)
    f = sub.add_parser("fidelity"); f.add_argument("--team", required=True); f.add_argument("--n", type=int, default=12)
    s = sub.add_parser("shed"); s.add_argument("--team", required=True); s.add_argument("--seeds", default="0-15")
    bk = sub.add_parser("bank"); bk.add_argument("--team", required=True); bk.add_argument("--seeds", default="0-11")
    args = ap.parse_args()
    return {"build": cmd_build, "fidelity": cmd_fidelity, "shed": cmd_shed, "bank": cmd_bank}[args.cmd](args)


if __name__ == "__main__":
    raise SystemExit(main())
