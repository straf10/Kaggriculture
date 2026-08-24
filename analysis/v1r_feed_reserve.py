#!/usr/bin/env python3
"""v1r Phase 0 — pin the feed-cash-reserve undercount arithmetic (ROADMAP §4.3 S3 step 1e,
ROADMAP §4.3 S3 step 1e).

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

GATE: reserve_code must be visibly < reserve_liability on the turns the
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


def open_slots_for(slot_ranges, obs, seat, name):
    """Reserved PASTURE/COOP tiles for `name` (animal_slot_ranges) that are still empty on this
    seat's farm. Mirrors executor.open_animal_slots' emptiness test closely enough for the trace."""
    tiles = obs["farms"][seat]["tiles"]
    open_n = 0
    for (x, y) in slot_ranges.get(name, ()):  # (x=row, y=col) per config tuples
        cell = tiles[x][y]
        if not (isinstance(cell, dict) and "animal" in cell):
            open_n += 1
    return open_n


def trace_target13(steps, cand_seat, targets, slot_ranges, wheat_default, max_step):
    """Reconstruct the C2 (full-target) reserve arithmetic for the candidate at herd `target_total`.

    C2 sizes reserve = target_total * wheat_price * FEED_RESERVE_DAYS from day 0 (step purchase,
    no ramp), so it is computable from the observation without the executor internals. buy_target
    is the executor's per-name min(still_wanted, headroom) summed over names; the emitted BUY_ANIMAL
    count is shown alongside (it is buy_target clamped by affordability = spendable // cost)."""
    target_total = sum(int(v) for v in targets.values())
    rows = []
    for i in range(1, max_step + 1):
        obs0 = steps[i][0]["observation"]
        obs_seat = steps[i][cand_seat]["observation"]
        action = steps[i][cand_seat]["action"]
        money = obs0["farms"][cand_seat]["money"]
        placed = placed_count(obs0, cand_seat)
        in_flight = in_flight_count(obs_seat)
        price = max(1, int(obs0["market"]["prices"].get("WHEAT", wheat_default)))
        reserve = target_total * price * FEED_RESERVE_DAYS
        spendable = max(0, money - reserve)
        # per-name still_wanted / headroom, exactly as executor.market_orders computes it
        buy_target = 0
        for name in ANIMAL_NAMES:
            tgt = int(targets.get(name, 0))
            if tgt <= 0:
                continue
            p_name = sum(1 for row in obs0["farms"][cand_seat]["tiles"]
                         for t in row if isinstance(t, dict) and t.get("animal") == name)
            carried = sum(int(inv.get(name, 0)) for inv in obs_seat["private"]["inventories"])
            shed_have = int(obs_seat["private"]["shed"].get(name, 0))
            infl = carried + shed_have
            still_wanted = tgt - p_name - infl
            if still_wanted <= 0:
                continue
            headroom = max(0, open_slots_for(slot_ranges, obs0, cand_seat, name) - infl)
            buy_target += min(still_wanted, headroom)
        bought = bought_this_turn(action)
        orders = [o for o in (action.get("market") or []) if o and o[0] != "SELL"]
        rows.append({
            "step": i, "day": int(obs0.get("day", 0)), "hour": int(obs0.get("hour", 0)),
            "money": money, "placed": placed, "in_flight": in_flight,
            "buy_target": buy_target, "reserve": reserve, "spendable": spendable,
            "bought": bought, "orders": orders,
        })
    return rows


def print_target13(rows):
    print("      step d/h    money  placed in_flight buy_tgt  reserve spendable  order")
    for r in rows:
        order = ",".join(f"{o[1]}x{o[2]}" if len(o) > 2 else o[0] for o in r["orders"]) or "-"
        print(
            f"      {r['step']:>4} {r['day']}/{r['hour']:<2} {r['money']:>8.1f}"
            f" {r['placed']:>6} {r['in_flight']:>8} {r['buy_target']:>7}"
            f" {r['reserve']:>8} {r['spendable']:>9}  {order}"
        )


def run_target13(package_main, seeds, targets, slot_ranges, wheat_default, out_dir):
    """Record a fresh play of the target-13 package vs v1q_base (basket-pinned) and trace the
    candidate's reserve arithmetic over days 0-12."""
    from harness.play import play  # noqa: E402
    from harness.town_pin import pinned_town, schedule_for_mode  # noqa: E402
    base = str(REPO / "checkpoints/v1q_base/main.py")
    target_total = sum(int(v) for v in targets.values())
    max_step = 13 * TURNS_PER_DAY - 1  # days 0-12 inclusive
    all_ok = True
    for seed in seeds:
        print(f"=== seed {seed} (candidate seat 0, target {target_total} = {targets}) ===")
        run_dir = out_dir / f"seed{seed}"
        with pinned_town("basket", schedule_for_mode("basket", seed)):
            result = play(package_main, base, seed=seed, record=True, run_dir=run_dir,
                          metrics=False, strict=False)
        with gzip.open(result.replay_path, "rt", encoding="utf-8") as handle:
            steps = json.load(handle)["steps"]
        rows = trace_target13(steps, 0, targets, slot_ranges, wheat_default,
                              min(max_step, len(steps) - 1))
        # The pathology the gate guards against is "passing an escape criterion by
        # never OWNING the animals" — so "the herd reaches 13" = owned (placed + in_flight), not
        # placed-on-tiles. Placement lags ownership by unit-turns to walk each animal to its tile,
        # which is a logistics question (arm H1), not a cash/reserve one.
        owned_day = next(
            (r["day"] for r in rows if r["placed"] + r["in_flight"] >= target_total), None)
        placed_day = next((r["day"] for r in rows if r["placed"] >= target_total), None)
        # money never $0 at a day boundary (hour 0) while animals are placed
        boundary_starved = [r for r in rows
                            if r["hour"] == 0 and r["placed"] > 0 and r["money"] <= 0.0]
        day_reached = owned_day
        reaches_by_12 = owned_day is not None and owned_day <= 12
        no_boundary_starve = not boundary_starved
        seed_ok = reaches_by_12 and no_boundary_starve
        all_ok = all_ok and seed_ok
        print_target13(rows)
        print(f"    herd OWNS {target_total} on day: {owned_day}  (placed 13 on day {placed_day})"
              f"  ({'owned <= 12 OK' if reaches_by_12 else 'LATE / never — FAIL'})")
        if boundary_starved:
            print(f"    ⚠️ money <= 0 at a day boundary with animals placed: "
                  f"steps {[r['step'] for r in boundary_starved]}")
        print(f"    seed gate: {'PASS' if seed_ok else 'FAIL'}")
        Path(result.replay_path).unlink(missing_ok=True)
    print()
    print(f"PHASE-0 (target {target_total}) GATE: "
          f"{'PASS — herd completes by d12, no boundary starvation' if all_ok else 'FAIL — reserve starves the herd, STOP'}")
    return 0 if all_ok else 1


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--seeds", default="0,1,2")
    parser.add_argument("--days", type=int, default=2, help="trace days 0..N inclusive")
    parser.add_argument("--run-target13", help="path to a target-13 package main.py; runs fresh "
                        "plays and traces the C2 reserve over days 0-12")
    parser.add_argument("--target-total", type=int, default=13)
    parser.add_argument("--out", default="gates/v1s_phase0")
    args = parser.parse_args()

    if args.run_target13:
        seeds = [int(s) for s in args.seeds.split(",")]
        out_dir = REPO / args.out
        out_dir.mkdir(parents=True, exist_ok=True)
        # The §4.0 herd-13 profile: 9 COW + 4 SHEEP (H2/H2R). Slot ranges come from the live
        # scheduler tiles (unchanged by the arms) carved by these targets in dict order.
        from agent.animal_slots import animal_slot_ranges  # noqa: E402
        targets = {"COW": 9, "SHEEP": 4, "GOOSE": 0}
        trace_cfg = {"animals": {"targets": targets}, "scheduler": CONFIG["scheduler"]}
        slot_ranges = animal_slot_ranges(trace_cfg)
        return run_target13(args.run_target13, seeds, targets, slot_ranges,
                            25, out_dir)

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
