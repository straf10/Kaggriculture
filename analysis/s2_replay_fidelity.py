#!/usr/bin/env python3
"""S2 — how far does an open-loop donor route survive contact with a DIFFERENT opponent
(ROADMAP.md S2). No `agent/` change: `checkpoints/v1i` and `harness/bench_agents/
meta_route.py` are used read-only, exactly as harness/compare.py already does.

For each donor (baselines/<date>/donors/*.json, produced by analysis/s1_extract_donors.py)
this replays the donor's fixed 719-action tape against three opponents — meta_route,
checkpoints/v1i, and another donor's tape — on BOTH seats, always under the donor's OWN
recorded engine seed (isolates the opponent-interaction effect: same environmental
conditions the donor's route was recorded under, only the opponent changes).

Per matchup it records:
  - final bank of the donor tape vs its recorded (home-episode) final bank
  - a day-by-day money-curve comparison against the donor's home-episode curve, to find
    the FIRST day of material divergence (the headline output per ROADMAP S2 — not just
    a final number)
  - a lightweight expected-vs-actual no-op check on BUY_SEED / SELL / BUY_LAND / HIRE
    orders (money/seed/shed/quadrant/hands deltas) per day — agent/receipts.py is not
    reusable here (it instruments agent/'s own executor, and a tape agent has none), so
    this is the "own lightweight check" ROADMAP S2 explicitly allows. PLANT/WATER/HARVEST/
    DIG/MOVE/BUY_ANIMAL are not individually decomposed (would require a tile-by-tile
    diff); their aggregate effect still shows up in the bank-curve divergence above.

Usage:
    python analysis/s2_replay_fidelity.py
"""
from __future__ import annotations

import gzip
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from analysis.replay_profile import extract_profile  # noqa: E402
from analysis.tape_agent import make_tape_agent  # noqa: E402
from harness.play import play  # noqa: E402

DONORS_DIR = Path(__file__).resolve().parent.parent / "baselines" / "2026-08-11" / "donors"
OUT_PATH = Path(__file__).resolve().parent.parent / "baselines" / "2026-08-11" / "s2_failure_map.json"

META_ROUTE_PATH = "harness/bench_agents/meta_route.py"
V1I_PATH = "checkpoints/v1i/main.py"
TURNS_PER_DAY = 24
DIVERGENCE_ABS = 1000.0   # $ absolute gap
DIVERGENCE_REL = 0.15     # 15% relative gap — "material divergence" trigger (either qualifies)


def load_donors() -> list[dict]:
    donors = []
    for path in sorted(DONORS_DIR.glob("*_seat*.json")):
        donors.append(json.loads(path.read_text(encoding="utf-8")))
    return donors


def home_money_curve(donor: dict) -> dict:
    """Day -> money, from the donor's OWN recorded home episode (not our replay of it)."""
    replay = json.loads(gzip.decompress(
        (Path(__file__).resolve().parent.parent / "data" / "archive" / "raw"
         / f"{donor['episode_id']}.json.gz").read_bytes()).decode())
    prof = extract_profile(replay, donor["donor"]["seat"])
    return {d["day"]: d["money"] for d in prof["daily"]}


def first_divergence_day(home_curve: dict, new_curve: dict) -> dict:
    days = sorted(set(home_curve) & set(new_curve))
    first_day = None
    for d in days:
        h, n = home_curve[d], new_curve[d]
        gap = abs(h - n)
        rel = gap / max(1.0, abs(h))
        if gap >= DIVERGENCE_ABS and rel >= DIVERGENCE_REL:
            first_day = d
            break
    return {
        "first_divergence_day": first_day,
        "final_day_home_money": home_curve.get(max(home_curve)) if home_curve else None,
        "final_day_new_money": new_curve.get(max(new_curve)) if new_curve else None,
    }


def noop_scan(env_json: dict, seat: int, action_stream: list) -> dict:
    """Lightweight expected-vs-actual check for BUY_SEED/SELL/BUY_LAND/HIRE, per day.

    action_stream[t] is the action the tape SUBMITTED at obs.step==t (0-indexed, matching
    analysis.s1_extract_donors.action_stream's convention); the resulting state is
    env_json["steps"][t+1] (steps[0] is the pre-first-action reset record).
    """
    steps = env_json["steps"]
    per_day = {}
    n = min(len(action_stream), len(steps) - 1)
    for t in range(n):
        pre = steps[t][seat]["observation"]
        post = steps[t + 1][seat]["observation"]
        day = pre["day"]
        action = action_stream[t] or {}
        orders = action.get("market") or []
        if not orders:
            continue
        bucket = per_day.setdefault(day, {"attempted": 0, "noop": 0, "examples": []})
        seeds_pre, seeds_post = pre["private"]["seeds"], post["private"]["seeds"]
        shed_pre, shed_post = pre["private"]["shed"], post["private"]["shed"]
        hands_pre, hands_post = len(pre["farms"][seat]["hands"]), len(post["farms"][seat]["hands"])
        quads_pre = len(pre["farms"][seat]["unlocked_quadrants"])
        quads_post = len(post["farms"][seat]["unlocked_quadrants"])
        n_hire = sum(1 for o in orders if o and o[0] == "HIRE")
        if n_hire:
            bucket["attempted"] += n_hire
            applied = max(0, hands_post - hands_pre)
            missed = max(0, n_hire - applied)
            bucket["noop"] += missed
            if missed:
                bucket["examples"].append(f"HIRE x{n_hire}, only {applied} applied")
        for order in orders:
            if not order or order[0] == "HIRE":
                continue
            op = order[0]
            bucket["attempted"] += 1
            if op == "BUY_SEED" and len(order) >= 3:
                item, want = order[1], int(order[2])
                got = seeds_post.get(item, 0) - seeds_pre.get(item, 0)
                if got < want:
                    bucket["noop"] += 1
                    bucket["examples"].append(f"BUY_SEED {item} x{want}, got {got}")
            elif op == "SELL" and len(order) >= 3:
                item, want = order[1], int(order[2])
                sold = shed_pre.get(item, 0) - shed_post.get(item, 0)
                if sold < want:
                    bucket["noop"] += 1
                    bucket["examples"].append(f"SELL {item} x{want}, shed dropped by {sold}")
            elif op == "BUY_LAND":
                if quads_post <= quads_pre:
                    bucket["noop"] += 1
                    bucket["examples"].append("BUY_LAND, no new quadrant")
            # BUY_ANIMAL / BUY_PRODUCT: not decomposed (see module docstring)
        bucket["examples"] = bucket["examples"][:3]
    return per_day


def run_matchup(donor: dict, opp_name: str, opp_spec, home_curve: dict) -> dict:
    action_stream = donor["donor_action_stream"]
    donor_tape = make_tape_agent(action_stream)
    seed = donor["engine_seed"]
    results = {}
    for donor_seat in (0, 1):
        agent_a = donor_tape if donor_seat == 0 else opp_spec
        agent_b = opp_spec if donor_seat == 0 else donor_tape
        result = play(agent_a, agent_b, seed=seed, steps=720, record=True,
                      run_dir=Path("runs") / "s2_diag", strict=False, metrics=False)
        env_json = json.loads(gzip.decompress(result.replay_path.read_bytes()).decode())

        new_bank = result.rewards[donor_seat]
        opp_bank = result.rewards[1 - donor_seat]
        recorded_bank = donor["donor"]["recorded_final_bank"]
        prof = extract_profile(env_json, donor_seat)
        new_curve = {d["day"]: d["money"] for d in prof["daily"]}
        divergence = first_divergence_day(home_curve, new_curve)
        noops = noop_scan(env_json, donor_seat, action_stream)
        total_attempted = sum(b["attempted"] for b in noops.values())
        total_noop = sum(b["noop"] for b in noops.values())
        first_noop_day = min((d for d, b in noops.items() if b["noop"] > 0), default=None)

        results[f"donor_seat{donor_seat}"] = {
            "donor_final_bank": new_bank,
            "donor_recorded_home_bank": recorded_bank,
            "pct_vs_home": (new_bank - recorded_bank) / recorded_bank if recorded_bank else None,
            "opponent_final_bank": opp_bank,
            "clean": result.clean,
            "health": result.health,
            "first_divergence_day": divergence["first_divergence_day"],
            "market_orders_attempted": total_attempted,
            "market_orders_noop": total_noop,
            "first_noop_day": first_noop_day,
            "noop_by_day": noops,
        }
    return results


def main() -> None:
    donors = load_donors()
    print(f"loaded {len(donors)} donors: "
          f"{[(d['episode_id'], d['donor']['team_name']) for d in donors]}")

    donor_tapes = {d["episode_id"]: make_tape_agent(d["donor_action_stream"]) for d in donors}
    failure_map = {}

    for i, donor in enumerate(donors):
        eid = donor["episode_id"]
        team = donor["donor"]["team_name"]
        home_curve = home_money_curve(donor)
        opponents = [
            ("meta_route", META_ROUTE_PATH),
            ("checkpoints_v1i", V1I_PATH),
        ]
        other = donors[(i + 1) % len(donors)]
        if other["episode_id"] != eid:
            opponents.append((f"donor_{other['episode_id']}_{other['donor']['team_name']}",
                              donor_tapes[other["episode_id"]]))

        failure_map[f"{eid}_{team}"] = {"episode_id": eid, "team": team,
                                        "recorded_home_bank": donor["donor"]["recorded_final_bank"],
                                        "vs": {}}
        for opp_name, opp_spec in opponents:
            print(f"\n--- donor {eid} ({team}) vs {opp_name} ---")
            matchup = run_matchup(donor, opp_name, opp_spec, home_curve)
            failure_map[f"{eid}_{team}"]["vs"][opp_name] = matchup
            for seat_key, r in matchup.items():
                print(f"  {seat_key}: bank ${r['donor_final_bank']:,.0f} "
                      f"(home ${r['donor_recorded_home_bank']:,.0f}, "
                      f"{r['pct_vs_home']:+.1%})  "
                      f"first_divergence_day={r['first_divergence_day']}  "
                      f"noops={r['market_orders_noop']}/{r['market_orders_attempted']} "
                      f"first_noop_day={r['first_noop_day']}  clean={r['clean']}")

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(failure_map, indent=2), encoding="utf-8")
    print(f"\nwrote {OUT_PATH}")

    # Gate/Kill (ROADMAP S2): does even the best case clear our current ~$57k?
    our_floor = 57360
    best_cases = []
    worst_cases = []
    for key, entry in failure_map.items():
        for opp_name, matchup in entry["vs"].items():
            for seat_key, r in matchup.items():
                best_cases.append(r["donor_final_bank"])
    print(f"\nS2 kill check: current agent floor ~${our_floor:,}")
    print(f"  replayed-tape bank range: ${min(best_cases):,.0f} - ${max(best_cases):,.0f}")
    below_floor = [b for b in best_cases if b < our_floor]
    print(f"  {len(below_floor)}/{len(best_cases)} matchup-seats land BELOW our ${our_floor:,} floor")


if __name__ == "__main__":
    main()
