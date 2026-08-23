#!/usr/bin/env python3
"""S8 Phase 3 — overlay firing check on live replays of submission 55675634.

Did the tile recovery and market overlay actually fire in the packaged submission?
Compares live replay actions against the reconstruction tape to detect divergences.

Alignment: stream[i] ↔ steps[i+1][seat].action
"""
from __future__ import annotations

import json
import os
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LIVE_DIR = ROOT / "data" / "archive" / "raw" / "live_55675634"
RECON_PATH = ROOT / "data" / "derived" / "s6_step1_reconstruction_ReCurSiON.json"
DERIVED = ROOT / "data" / "derived"

TILE_OPS = {"WATER", "PLANT", "DIG", "HARVEST", "FEED", "CARE", "COLLECT_FERTILIZER"}
PULL_FORWARD_STEP = 336


def canon(x) -> str:
    return json.dumps(x, sort_keys=True, separators=(",", ":"))


def load_tape() -> list[dict]:
    d = json.loads(RECON_PATH.read_text())
    return d["stream"]


def analyse_episode(path: Path, tape: list[dict]) -> dict | None:
    d = json.loads(path.read_text())
    info = d.get("info", {})
    teams = info.get("TeamNames", [])
    steps = d["steps"]
    rewards = d.get("rewards", [None, None])
    seed = info.get("seed")
    eid = info.get("EpisodeId")

    straf_seats = [i for i, t in enumerate(teams) if t == "STRAF"]
    if not straf_seats:
        return None

    results = []
    for seat in straf_seats:
        opp = teams[1 - seat] if len(teams) > 1 else "?"

        tile_firings = []
        tile_rule_counter = Counter()
        market_early_sells = []
        total_market_straw_sells = 0
        total_market_straw_units = 0
        total_straw_revenue = 0
        production_mismatches = 0
        n_steps_compared = 0

        for i in range(min(len(tape), len(steps) - 1)):
            tape_act = tape[i]
            live_cell = steps[i + 1][seat]
            live_act = live_cell.get("action")
            if not live_act:
                continue
            n_steps_compared += 1

            tape_farmer = tape_act.get("farmer", ["PASS"])
            tape_hands = tape_act.get("hands", [])
            live_farmer = live_act.get("farmer", ["PASS"])
            live_hands = live_act.get("hands", [])

            if canon(live_farmer) != canon(tape_farmer):
                tape_op = tape_farmer[0] if tape_farmer else "PASS"
                live_op = live_farmer[0] if live_farmer else "PASS"
                if tape_op in TILE_OPS:
                    rule = f"{tape_op}->{live_op}"
                    tile_firings.append({"step": i, "channel": "farmer", "rule": rule})
                    tile_rule_counter[rule] += 1
                else:
                    production_mismatches += 1

            for h_idx in range(max(len(tape_hands), len(live_hands))):
                th = tape_hands[h_idx] if h_idx < len(tape_hands) else ["PASS"]
                lh = live_hands[h_idx] if h_idx < len(live_hands) else ["PASS"]
                if canon(lh) != canon(th):
                    tape_op = th[0] if th else "PASS"
                    live_op = lh[0] if lh else "PASS"
                    if tape_op in TILE_OPS:
                        rule = f"{tape_op}->{live_op}"
                        tile_firings.append({"step": i, "channel": f"hand_{h_idx}",
                                             "rule": rule})
                        tile_rule_counter[rule] += 1
                    else:
                        production_mismatches += 1

            tape_market = tape_act.get("market", [])
            live_market = live_act.get("market", [])

            tape_straw_sells = set()
            for o in tape_market:
                if isinstance(o, list) and len(o) >= 3 and o[0] == "SELL" and o[1] == "STRAWBERRY":
                    tape_straw_sells.add(o[2])

            for o in live_market:
                if isinstance(o, list) and len(o) >= 3 and o[0] == "SELL" and o[1] == "STRAWBERRY":
                    total_market_straw_sells += 1
                    total_market_straw_units += o[2]
                    if i < PULL_FORWARD_STEP and o[2] not in tape_straw_sells:
                        market_early_sells.append({"step": i, "units": o[2]})

        first_straw_sell_step = None
        for i in range(min(len(tape), len(steps) - 1)):
            live_act = steps[i + 1][seat].get("action")
            if not live_act:
                continue
            for o in live_act.get("market", []):
                if isinstance(o, list) and len(o) >= 3 and o[0] == "SELL" and o[1] == "STRAWBERRY":
                    first_straw_sell_step = i
                    break
            if first_straw_sell_step is not None:
                break

        early_units = sum(s["units"] for s in market_early_sells)

        results.append({
            "episode_id": eid,
            "seat": seat,
            "opponent": opp,
            "seed": seed,
            "reward": rewards[seat],
            "n_steps_compared": n_steps_compared,
            "tile_recovery_firings": len(tile_firings),
            "tile_rule_distribution": dict(tile_rule_counter),
            "production_mismatches_non_tile": production_mismatches,
            "market_early_sells_count": len(market_early_sells),
            "market_early_sells_units": early_units,
            "first_straw_sell_step": first_straw_sell_step,
            "total_straw_sells": total_market_straw_sells,
            "total_straw_units": total_market_straw_units,
        })

    return results


def main():
    tape = load_tape()
    print(f"Tape length: {len(tape)} steps")

    files = sorted(LIVE_DIR.glob("*.json"))
    print(f"Live replays: {len(files)}")

    all_results = []
    for f in files:
        ep_results = analyse_episode(f, tape)
        if ep_results:
            all_results.extend(ep_results)

    print(f"Analysed {len(all_results)} STRAF seats across {len(files)} episodes\n")

    tile_firings = [r["tile_recovery_firings"] for r in all_results]
    early_sells = [r["market_early_sells_count"] for r in all_results]
    early_units = [r["market_early_sells_units"] for r in all_results]
    first_steps = [r["first_straw_sell_step"] for r in all_results if r["first_straw_sell_step"] is not None]
    prod_mismatches = [r["production_mismatches_non_tile"] for r in all_results]

    print("=== TILE RECOVERY CHANNEL ===")
    print(f"  Firings/episode: median={sorted(tile_firings)[len(tile_firings)//2]}, "
          f"mean={sum(tile_firings)/len(tile_firings):.1f}, "
          f"min={min(tile_firings)}, max={max(tile_firings)}")
    print(f"  Episodes with 0 firings: {sum(1 for x in tile_firings if x == 0)}/{len(tile_firings)}")

    global_rules = Counter()
    for r in all_results:
        global_rules.update(r["tile_rule_distribution"])
    print(f"  Rule distribution (global):")
    for rule, cnt in global_rules.most_common():
        print(f"    {rule}: {cnt}")

    print(f"\n  Non-tile production mismatches: median={sorted(prod_mismatches)[len(prod_mismatches)//2]}, "
          f"total={sum(prod_mismatches)}")

    print(f"\n=== MARKET OVERLAY CHANNEL ===")
    print(f"  Early sells (before step {PULL_FORWARD_STEP})/episode: "
          f"median={sorted(early_sells)[len(early_sells)//2]}, "
          f"mean={sum(early_sells)/len(early_sells):.1f}, "
          f"min={min(early_sells)}, max={max(early_sells)}")
    print(f"  Early units/episode: median={sorted(early_units)[len(early_units)//2]}, "
          f"mean={sum(early_units)/len(early_units):.1f}")
    print(f"  Episodes with 0 early sells: {sum(1 for x in early_sells if x == 0)}/{len(early_sells)}")
    if first_steps:
        print(f"  First STRAWBERRY sell step: median={sorted(first_steps)[len(first_steps)//2]}, "
              f"min={min(first_steps)}, max={max(first_steps)}")

    total_sells = [r["total_straw_sells"] for r in all_results]
    total_units = [r["total_straw_units"] for r in all_results]
    print(f"  Total STRAW sells/episode: median={sorted(total_sells)[len(total_sells)//2]}, "
          f"mean={sum(total_sells)/len(total_sells):.1f}")
    print(f"  Total STRAW units/episode: median={sorted(total_units)[len(total_units)//2]}, "
          f"mean={sum(total_units)/len(total_units):.1f}")

    out_path = DERIVED / "s8_overlay_firing.json"
    out_path.write_text(json.dumps(all_results, indent=2))
    print(f"\nWrote {out_path}")


if __name__ == "__main__":
    main()
