#!/usr/bin/env python3
"""v1r Phase 0 — pin the feed-cash-reserve undercount arithmetic (ROADMAP §4.3 S3 step 1e,
prompt.md §3.2).

Step 1d established the *downstream* chain (zero shed WHEAT => no feed => escape at the day
1->2 boundary) and located the *upstream* cause not in the HIRE settlement (there is none —
both agents are at $2.980,0 with 6 hands at step 1) but in the day-0 animal purchase schedule.
This script pins the exact defect: agent/executor.py's feed-cash reserve is

    reserve = (total_placed + buy_target) * wheat_price_est * FEED_RESERVE_DAYS

which counts animals already standing on tiles plus the ones a single BUY order would add, but
NOT the animals already bought on previous turns and still carried in a unit's hands or sitting
in the shed. Every one of those eats one WHEAT per day the moment it is placed. Spreading the
purchases across consecutive turns (which arm A1's geometry causes) bypasses the guard entirely.

For each turn of days 0-2, on BOTH agents, this prints from the ALREADY-RECORDED replay
(gates/v1q_onboarding_escape/replays/...):

    money | placed | in_flight | bought_this_turn | reserve_code | reserve_liability | order

  reserve_code      = (placed + bought)             * wheat_price * FEED_RESERVE_DAYS  (the bug)
  reserve_liability = (placed + in_flight + bought) * wheat_price * FEED_RESERVE_DAYS  (correct)

GATE (prompt.md §3.2): reserve_code must be visibly < reserve_liability on the turns the
candidate buys (in_flight > 0), and the two must converge when nothing is in flight. If they do
not diverge as described, §2's located defect is wrong — stop and say so.

Usage:
    .venv/bin/python analysis/v1r_feed_reserve.py --seeds 0,1,2
Reuses last pass's replays; runs no new episodes.
"""
import argparse
import gzip
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from agent.config import CONFIG  # noqa: E402
from agent.constants import ANIMALS  # noqa: E402

ANIMAL_NAMES = tuple(ANIMALS)  # ("GOOSE", "COW", "SHEEP")
FEED_RESERVE_DAYS = 2  # the value shipped in agent/executor.py (arm-X default)
TURNS_PER_DAY = CONFIG["runtime"]["turns_per_day"]
REPLAY_ROOT = REPO / "gates" / "v1q_onboarding_escape" / "replays"


def placed_count(obs, seat):
    """Animals standing on tiles for this seat."""
    tiles = obs["farms"][seat]["tiles"]
    return sum(
        1 for row in tiles for t in row if isinstance(t, dict) and "animal" in t
    )


def in_flight_count(obs_for_seat):
    """Animals bought but not yet placed: shed + every unit's inventory. Read from the seat's
    OWN observation entry (steps[i][seat]["observation"]["private"]) — private is per-seat."""
    priv = obs_for_seat["private"]
    total = sum(int(priv["shed"].get(name, 0)) for name in ANIMAL_NAMES)
    for inv in priv["inventories"]:
        total += sum(int(inv.get(name, 0)) for name in ANIMAL_NAMES)
    return total


def bought_this_turn(action):
    """Animals this seat's action bought (emitted BUY_ANIMAL orders). The reserve never binds
    on the candidate, so the emitted count equals its buy_target on these turns."""
    return sum(
        int(o[2]) for o in (action.get("market") or []) if o and o[0] == "BUY_ANIMAL"
    )


def wheat_price(obs):
    # executor uses max(1, int(snapshot.market_prices.get("WHEAT", 25)))
    return max(1, int(obs["market"]["prices"].get("WHEAT", 25)))


def trace_orientation(steps, cand_seat, base_seat, max_step):
    rows = {"candidate(arm_A1)": [], "baseline(v1q_base)": []}
    for label, seat in (("candidate(arm_A1)", cand_seat), ("baseline(v1q_base)", base_seat)):
        for i in range(1, max_step + 1):
            obs0 = steps[i][0]["observation"]  # farms + market mirrored on the seat-0 entry
            obs_seat = steps[i][seat]["observation"]  # per-seat private
            action = steps[i][seat]["action"]
            money = obs0["farms"][seat]["money"]
            placed = placed_count(obs0, seat)
            in_flight = in_flight_count(obs_seat)
            bought = bought_this_turn(action)
            price = wheat_price(obs0)
            reserve_code = (placed + bought) * price * FEED_RESERVE_DAYS
            reserve_liability = (placed + in_flight + bought) * price * FEED_RESERVE_DAYS
            orders = [o for o in (action.get("market") or []) if o and o[0] != "SELL"]
            rows[label].append({
                "step": i,
                "day": int(obs0.get("day", 0)),
                "hour": int(obs0.get("hour", 0)),
                "money": money,
                "placed": placed,
                "in_flight": in_flight,
                "bought": bought,
                "reserve_code": reserve_code,
                "reserve_liability": reserve_liability,
                "orders": orders,
            })
    return rows


def print_rows(label, rows):
    print(f"    {label}")
    print("      step d/h    money  placed in_flight bought  resv_code  resv_liab  order")
    for r in rows:
        order = ",".join(f"{o[1]}x{o[2]}" if len(o) > 2 else o[0] for o in r["orders"]) or "-"
        flag = "  <-- code<liab" if r["reserve_code"] < r["reserve_liability"] else ""
        print(
            f"      {r['step']:>4} {r['day']}/{r['hour']:<2} {r['money']:>8.1f}"
            f" {r['placed']:>6} {r['in_flight']:>8} {r['bought']:>6}"
            f" {r['reserve_code']:>10} {r['reserve_liability']:>10}  {order}{flag}"
        )


def gate(rows):
    """§3.2 gate: on turns the candidate has animals in flight, code < liability;
    when nothing is in flight, they converge (equal)."""
    diverges_when_in_flight = all(
        r["reserve_code"] < r["reserve_liability"]
        for r in rows if r["in_flight"] > 0
    )
    converges_when_empty = all(
        r["reserve_code"] == r["reserve_liability"]
        for r in rows if r["in_flight"] == 0
    )
    any_in_flight = any(r["in_flight"] > 0 for r in rows)
    return diverges_when_in_flight and converges_when_empty and any_in_flight


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--seeds", default="0,1,2")
    parser.add_argument("--days", type=int, default=2, help="trace days 0..N inclusive")
    args = parser.parse_args()

    max_step = (args.days + 1) * TURNS_PER_DAY - 1
    seeds = [int(s) for s in args.seeds.split(",")]
    all_pass = True

    for seed in seeds:
        print(f"=== seed {seed} ===")
        for orientation, cand_seat, base_seat in (("A@0_B@1", 0, 1), ("A@1_B@0", 1, 0)):
            replay = REPLAY_ROOT / orientation / f"seed{seed}_seat0-main_seat1-main.json.gz"
            if not replay.exists():
                print(f"  {orientation}: MISSING replay {replay} — run v1q first")
                all_pass = False
                continue
            with gzip.open(replay, "rt", encoding="utf-8") as handle:
                steps = json.load(handle)["steps"]
            rows = trace_orientation(steps, cand_seat, base_seat, min(max_step, len(steps) - 1))
            cand = rows["candidate(arm_A1)"]
            gate_ok = gate(cand)
            all_pass = all_pass and gate_ok
            print(f"  --- {orientation} (candidate seat {cand_seat}) — gate {'PASS' if gate_ok else 'FAIL'}")
            print_rows("candidate(arm_A1)", cand)
            print_rows("baseline(v1q_base)", rows["baseline(v1q_base)"])

    print()
    print(f"PHASE-0 GATE: {'PASS — reserve undercount confirmed' if all_pass else 'FAIL — §2 defect not reproduced, STOP'}")
    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())
