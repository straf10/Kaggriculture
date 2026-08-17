#!/usr/bin/env python3
"""T2 Phase 0 — the cash-coupling diagnostic (ROADMAP §4.3 S3 step 3; T2 pass brief).

The T2 hybrid keeps the donor tape's `farmer`/`hands` verbatim (T1 proved these run
byte-identically against every opponent) and overlays our own sell logic on the `market`
channel. But the market channel carries BOTH the tape's purchases (HIRE/BUY_SEED/
BUY_PRODUCT/BUY_ANIMAL/BUY_LAND) AND its sells (SELL). The tape's PLANT/PLACE/FEED actions
depend on seeds/animals/wheat bought by *its own* market orders, and a BUY that silently
fails (D15: invalid actions are silent no-ops) desyncs production without announcing itself.

This script measures, against several opponents, the whole thing the brief calls "the entire
risk":

  1. The donor's full purchase schedule (turn, item, qty, unit cost, money before/after).
  2. The minimum cash trajectory — how close the donor ever comes to being unable to afford
     its next purchase. That margin is the safety budget for changing sells.
  3. Whether within a single turn any BUY depends on SELL revenue *earlier in the same turn*
     (money before the turn < that buy's cost, but a same-turn earlier sell lifts it over).
     If none exist, the overlay may freely reorder/replace sells without a within-turn cash
     hazard; if some exist, those turns are constrained.

It reads only the gitignored donor record (competition data stays out of the public repo,
§2.4b) and the engine's own recorded per-step observations from a real replay — no
re-implementation of market processing, so the money/shed/inventory numbers are ground truth.

Usage:
    python analysis/t2_phase0_cash_coupling.py            # meta_route + mirror + recorded opp
    python analysis/t2_phase0_cash_coupling.py --seed 7
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
import sys
sys.path.insert(0, str(ROOT))

from harness.play import play  # noqa: E402

DONOR_PATH = ROOT / "baselines" / "2026-08-11" / "donors" / "91456307_seat0.json"
META_ROUTE = str(ROOT / "harness" / "bench_agents" / "meta_route.py")

BUY_VERBS = ("BUY_SEED", "BUY_PRODUCT", "BUY_ANIMAL", "BUY_LAND", "HIRE")
SELL_VERBS = ("SELL",)


def _load_donor():
    d = json.loads(DONOR_PATH.read_text())
    return d


def _tape_callable(stream):
    n = len(stream)

    def agent(obs, configuration=None):
        step = obs.get("step", 0) if hasattr(obs, "get") else int(getattr(obs, "step", 0))
        if 0 <= step < n:
            return stream[step]
        return {"farmer": ["PASS"], "hands": [], "market": []}
    return agent


def _fib(n):
    a, b = 1, 1
    for _ in range(n):
        a, b = b, a + b
    return a


def _turn_buy_cost(capped, prices, hires_today_start):
    """Total cost of every BUY/HIRE/BUY_LAND in this turn, in engine order.

    HIRE cost is fib(hires_today) and hires_today accumulates within the day; the tape rebuilds
    the crew every morning, so `hires_today_start` (from the observation) anchors the fib index.
    BUY_PRODUCT is market-priced (pre-turn quote — first-order; the true price drifts a little as
    inventory moves within the lockstep). Returns (total_cost, breakdown_by_verb).
    """
    from agent.constants import CROPS, ANIMALS
    total = 0.0
    hires = hires_today_start
    by_verb = {}
    for o in capped:
        if not (isinstance(o, list) and o):
            continue
        v = o[0]
        c = 0.0
        if v == "HIRE":
            c = _fib(hires)
            hires += 1
        elif v == "BUY_LAND":
            c = 0.0  # priced from unlocked-quadrant count; small vs animals, tracked separately
        elif v == "BUY_SEED" and len(o) >= 3:
            c = CROPS.get(o[1], {}).get("seed", 0) * int(o[2])
        elif v == "BUY_ANIMAL" and len(o) >= 3:
            c = ANIMALS.get(o[1], {}).get("cost", 0) * int(o[2])
        elif v == "BUY_PRODUCT" and len(o) >= 3:
            c = prices.get(o[1], 0) * int(o[2])
        else:
            continue
        total += c
        by_verb[v] = by_verb.get(v, 0.0) + c
    return total, by_verb


def analyze(env_json, seat, label):
    steps = env_json["steps"]
    config = env_json["configuration"]
    cap = max(1, int(config.get("maxMarketOrdersPerTurn", 10)))
    n = len(steps)

    money_before_curve = []   # money the agent SEES at step k (before its action)
    money_after_curve = []    # money at step k+1 (after action k executed)
    shed_curve = []

    min_money_after = None
    min_money_after_step = None

    # Self-funding: a turn whose buys exceed start-of-turn money relies on SAME-TURN sell
    # revenue that precedes them in the order list. Those are the only turns where changing
    # sells can starve a purchase within the turn.
    not_self_funded = []      # (step, money_before, buy_cost, shortfall, buys, sells)
    n_turns_with_buys = 0
    n_turns_with_sells = 0
    n_turns_at_cap = 0
    tightest_self_fund = None  # min(money_before - buy_cost) over turns that DO have buys

    purchases = []  # (step, verb, item, qty, cost)

    for k in range(n - 1):
        obs_k = steps[k][seat]["observation"]
        money_before = obs_k["farms"][seat]["money"]
        private = obs_k.get("private", {})
        shed = private.get("shed", {})
        prices = obs_k.get("market", {}).get("prices", {})
        hires_today = int(obs_k["farms"][seat].get("hires_today", 0))
        shed_total = sum(shed.values()) if isinstance(shed, dict) else 0

        money_after = steps[k + 1][seat]["observation"]["farms"][seat]["money"]

        money_before_curve.append(money_before)
        money_after_curve.append(money_after)
        shed_curve.append(shed_total)
        if min_money_after is None or money_after < min_money_after:
            min_money_after = money_after
            min_money_after_step = k + 1

        action = steps[k + 1][seat].get("action", {}) or {}  # == stream[k]
        m = action.get("market", []) if isinstance(action, dict) else []
        capped = m[:cap]
        if len(m) >= cap:
            n_turns_at_cap += 1

        buys = [o for o in capped if isinstance(o, list) and o and o[0] in BUY_VERBS]
        sells = [o for o in capped if isinstance(o, list) and o and o[0] in SELL_VERBS]
        if sells:
            n_turns_with_sells += 1
        if buys:
            n_turns_with_buys += 1
            buy_cost, _ = _turn_buy_cost(capped, prices, hires_today)
            slack = money_before - buy_cost
            if tightest_self_fund is None or slack < tightest_self_fund[0]:
                tightest_self_fund = (slack, k, money_before, buy_cost)
            if slack < 0:
                not_self_funded.append((k, money_before, buy_cost, -slack,
                                        [o for o in buys], [o for o in sells]))
            from agent.constants import CROPS, ANIMALS
            for o in buys:
                if o[0] == "BUY_SEED" and len(o) >= 3:
                    c = CROPS.get(o[1], {}).get("seed", 0) * int(o[2])
                elif o[0] == "BUY_ANIMAL" and len(o) >= 3:
                    c = ANIMALS.get(o[1], {}).get("cost", 0) * int(o[2])
                elif o[0] == "BUY_PRODUCT" and len(o) >= 3:
                    c = prices.get(o[1], 0) * int(o[2])
                else:
                    c = None
                purchases.append((k, o[0], o[1] if len(o) > 1 else None,
                                  int(o[2]) if len(o) >= 3 else 1, c))

    return {
        "label": label,
        "final_money": money_after_curve[-1] if money_after_curve else None,
        "min_money_after": min_money_after,
        "min_money_after_step": min_money_after_step,
        "n_turns_with_buys": n_turns_with_buys,
        "n_turns_with_sells": n_turns_with_sells,
        "n_turns_at_cap": n_turns_at_cap,
        "n_not_self_funded": len(not_self_funded),
        "not_self_funded": not_self_funded,
        "tightest_self_fund": tightest_self_fund,
        "peak_shed": max(shed_curve) if shed_curve else 0,
        "money_before_curve": money_before_curve,
        "money_after_curve": money_after_curve,
        "shed_curve": shed_curve,
        "n_purchases": len(purchases),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=7)
    args = ap.parse_args()

    d = _load_donor()
    donor_stream = d["donor_action_stream"]
    opp_stream = d["opponent_action_stream"]
    recorded_bank = d["donor"]["recorded_final_bank"]
    tape = _tape_callable(donor_stream)
    opp_tape = _tape_callable(opp_stream)

    run_dir = ROOT / "baselines" / "2026-08-16" / "t2_phase0_runs"
    run_dir.mkdir(parents=True, exist_ok=True)

    opponents = {
        "recorded_opp": opp_tape,   # the real episode's opponent — reproduces recorded bank
        "meta_route": META_ROUTE,   # the non-mirror acceptance bench
        "self_mirror": tape,        # tape vs tape — hardest realised-price (same products)
    }

    print(f"Donor: Valmorlee (91456307) seat 0, recorded home bank ${recorded_bank:,}")
    print(f"Seed: {args.seed}\n")

    results = {}
    for name, opp in opponents.items():
        res = play(tape, opp, seed=args.seed, run_dir=run_dir, metrics=False, strict=False)
        # reload env_json from the recorded replay
        import gzip
        with gzip.open(res.replay_path, "rt") as f:
            env_json = json.load(f)
        a = analyze(env_json, 0, name)
        results[name] = a
        print(f"=== opponent: {name} ===")
        print(f"  clean={res.clean}  final_money(seat0)=${a['final_money']:,.0f}  "
              f"(recorded ${recorded_bank:,})")
        print(f"  cash FLOOR (min money_after over episode) = "
              f"${a['min_money_after']:,.0f} at step {a['min_money_after_step']}")
        print(f"  peak shed total = {a['peak_shed']} (shedCapacity=100)")
        print(f"  turns with buys={a['n_turns_with_buys']}  with sells={a['n_turns_with_sells']}"
              f"  at 10-order cap={a['n_turns_at_cap']}")
        ts = a['tightest_self_fund']
        if ts:
            print(f"  tightest self-funding slack (money_before - turn_buy_cost) = "
                  f"${ts[0]:,.0f} at step {ts[1]} (money_before ${ts[2]:,.0f}, "
                  f"buy_cost ${ts[3]:,.0f})")
        print(f"  turns NOT self-funded (buys need same-turn sell revenue): "
              f"{a['n_not_self_funded']}")
        for dep in a['not_self_funded'][:12]:
            k, mb, bc, short, buys, sells = dep
            print(f"      step {k}: buy_cost ${bc:,.0f} > money_before ${mb:,.0f} "
                  f"(short ${short:,.0f}); sells this turn: {json.dumps(sells)[:80]}")
        print()

    out = run_dir / f"t2_phase0_seed{args.seed}.json"
    drop = ("money_before_curve", "money_after_curve", "shed_curve", "not_self_funded")
    slim = {name: {k: v for k, v in r.items() if k not in drop}
            for name, r in results.items()}
    out.write_text(json.dumps(slim, indent=2, default=str))
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
