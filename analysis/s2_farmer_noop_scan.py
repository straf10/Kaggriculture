#!/usr/bin/env python3
"""S2 addendum — decompose the FARMER/HANDS no-ops the market scan cannot see.

`analysis/s2_replay_fidelity.py` measures BUY_SEED/SELL/BUY_LAND/HIRE no-ops only; its
docstring explicitly leaves PLANT/WATER/HARVEST/DIG undecomposed. But ROADMAP §4.3 S2 names
`_spawn_weeds` as a primary desync driver, and the repair layer the tape needs must be sized
by *that* damage, not by its downstream SELL symptom. This script fills the gap.

Mechanics that make the measurement well-posed (engine_reference/kaggriculture.py):
  - Unit MOVES are never blocked by weeds (only by board edges, l.326) and are deterministic
    from fixed start positions ⇒ every unit is ALWAYS exactly where the tape recorded it,
    regardless of opponent. The desync is purely tile-content, never positional.
  - PLANT no-ops iff the target tile is non-empty (l.423). `_spawn_weeds` only spawns on
    empty (None) tiles (l.839). So an opponent-driven weed landing on a tile the tape means
    to PLANT is THE collision, and DIG clears it (l.490). That is the recoverable damage.

For each (donor, opponent) it replays the donor tape (seat 0) under the donor's own engine
seed and classifies every farmer/hands unit-action against the pre-action tile it stands on:
  PLANT: landed | blocked-by-WEED (recoverable via DIG) | blocked-by-PLANT | blocked-by-seeds
  WATER/HARVEST/FERTILIZE: landed | no-op (tile not a matching PLANT / nothing to take)
It also counts, for each WEED-blocked PLANT tile, whether the tape later re-attempts a PLANT
on the SAME tile (i.e. whether clearing the weed would actually recover a crop).

Usage:
    python analysis/s2_farmer_noop_scan.py
"""
from __future__ import annotations

import gzip
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from analysis.tape_agent import make_tape_agent  # noqa: E402
from harness.bench_agents import meta_route  # noqa: E402
from harness.play import play  # noqa: E402

DONORS_DIR = ROOT / "baselines" / "2026-08-11" / "donors"
OUT_PATH = ROOT / "baselines" / "2026-08-11" / "s2_farmer_noop_scan.json"
TURNS_PER_DAY = 24

TILE_OPS = {"PLANT", "WATER", "HARVEST", "FERTILIZE", "DIG"}


def load_donors() -> list[dict]:
    return [json.loads(p.read_text()) for p in sorted(DONORS_DIR.glob("*_seat*.json"))]


def _unit_actions(action: dict) -> list:
    """[(idx, action_tokens)] for farmer (idx 0) then each hand (idx 1..)."""
    out = [(0, action.get("farmer") or ["PASS"])]
    for h, a in enumerate(action.get("hands") or []):
        out.append((h + 1, a))
    return out


def _pos(farm, idx):
    if idx == 0:
        return farm["farmer"]
    hands = farm["hands"]
    return hands[idx - 1] if idx - 1 < len(hands) else None


def scan_replay(env_json: dict, seat: int, action_stream: list) -> dict:
    """Classify farmer/hands tile-ops against the pre-action tile each unit stands on.

    action_stream[t] is submitted at obs.step==t; pre-state is steps[t][seat].observation.
    """
    steps = env_json["steps"]
    n = min(len(action_stream), len(steps) - 1)
    cls = Counter()
    weed_blocked_tiles = {}     # (x,y) -> first day blocked
    plant_attempt_tiles = {}    # (x,y) -> set of days a PLANT was attempted (any outcome)
    per_day_weed = Counter()

    for t in range(n):
        rec = steps[t][seat]
        obs = rec["observation"]
        day = obs["step"] // TURNS_PER_DAY
        farm = obs["farms"][seat]
        priv = obs.get("private") or {}
        seeds = dict(priv.get("seeds") or {})
        tiles = farm["tiles"]
        action = action_stream[t] or {}

        # replicate the engine's atomic-PLANT seed guard (l.920-928) for accuracy
        demand = Counter()
        for _idx, a in _unit_actions(action):
            if isinstance(a, list) and len(a) >= 2 and a[0] == "PLANT":
                demand[a[1]] += 1
        seed_blocked = {c for c, d in demand.items() if d > seeds.get(c, 0)}

        for idx, a in _unit_actions(action):
            if not isinstance(a, list) or not a or a[0] not in TILE_OPS:
                continue
            op = a[0]
            p = _pos(farm, idx)
            if p is None:
                continue
            x, y = p[0], p[1]
            tile = tiles[y][x]
            tkind = tile.get("kind") if isinstance(tile, dict) else (tile if tile else "EMPTY")

            if op == "PLANT":
                crop = a[1] if len(a) >= 2 else None
                plant_attempt_tiles.setdefault((x, y), set()).add(day)
                if crop in seed_blocked:
                    cls["PLANT_blocked_seeds"] += 1
                elif tile is None:
                    cls["PLANT_landed"] += 1
                elif tkind == "WEED":
                    cls["PLANT_blocked_WEED"] += 1
                    per_day_weed[day] += 1
                    weed_blocked_tiles.setdefault((x, y), day)
                elif tkind == "PLANT":
                    cls["PLANT_blocked_PLANT"] += 1
                else:
                    cls["PLANT_blocked_other"] += 1
            elif op == "WATER":
                if isinstance(tile, dict) and tkind == "PLANT" and not tile.get("watered_today"):
                    cls["WATER_landed"] += 1
                else:
                    cls["WATER_noop"] += 1
            elif op == "HARVEST":
                if isinstance(tile, dict) and tile.get("yield_units", 0) > 0:
                    cls["HARVEST_landed"] += 1
                else:
                    cls["HARVEST_noop"] += 1
            elif op == "FERTILIZE":
                if isinstance(tile, dict) and tkind == "PLANT":
                    cls["FERTILIZE_landed"] += 1
                else:
                    cls["FERTILIZE_noop"] += 1
            elif op == "DIG":
                if tile is not None and not (isinstance(tile, dict) and "animal" in tile):
                    cls["DIG_landed"] += 1
                else:
                    cls["DIG_noop"] += 1

    # how many weed-blocked tiles get a later PLANT re-attempt (recoverable crop)?
    recoverable = 0
    for (x, y), blocked_day in weed_blocked_tiles.items():
        later = {d for d in plant_attempt_tiles.get((x, y), set()) if d > blocked_day}
        if later:
            recoverable += 1

    return {
        "classification": dict(cls),
        "plant_blocked_weed": cls["PLANT_blocked_WEED"],
        "distinct_weed_blocked_tiles": len(weed_blocked_tiles),
        "weed_blocked_tiles_replanted_later": recoverable,
        "weed_blocks_by_day": dict(sorted(per_day_weed.items())),
    }


def run(donor: dict, opp_name: str, opp_spec) -> dict:
    stream = donor["donor_action_stream"]
    tape = make_tape_agent(stream)
    seed = donor["engine_seed"]
    result = play(tape, opp_spec, seed=seed, steps=720, record=True,
                  run_dir=ROOT / "runs" / "s2_farmer_scan", strict=False, metrics=False)
    env_json = json.loads(gzip.decompress(result.replay_path.read_bytes()).decode())
    scan = scan_replay(env_json, 0, stream)
    scan["donor_final_bank"] = result.rewards[0]
    scan["recorded_home_bank"] = donor["donor"]["recorded_final_bank"]
    return scan


def main() -> None:
    donors = load_donors()
    by_eid = {d["episode_id"]: d for d in donors}
    tapes = {d["episode_id"]: make_tape_agent(d["donor_action_stream"]) for d in donors}
    # hardest opponent per donor = the other-donor tape used in the failure map (cyclic next)
    order = sorted(by_eid)
    out = {}
    for i, eid in enumerate(order):
        donor = by_eid[eid]
        team = donor["donor"]["team_name"]
        nxt = order[(i + 1) % len(order)]
        opponents = [("meta_route", meta_route.agent),
                     (f"donor_{nxt}", tapes[nxt])]
        out[f"{eid}_{team}"] = {}
        for opp_name, opp_spec in opponents:
            scan = run(donor, opp_name, opp_spec)
            out[f"{eid}_{team}"][opp_name] = scan
            c = scan["classification"]
            print(f"{team:<16} vs {opp_name:<14} bank ${scan['donor_final_bank']:>9,.0f}  "
                  f"PLANT: {c.get('PLANT_landed',0):>3} land / "
                  f"{scan['plant_blocked_weed']:>2} weed-block "
                  f"({scan['weed_blocked_tiles_replanted_later']} recov) / "
                  f"{c.get('PLANT_blocked_PLANT',0)} plant-block / "
                  f"{c.get('PLANT_blocked_seeds',0)} seed-block  |  "
                  f"WATER noop {c.get('WATER_noop',0)}  HARVEST noop {c.get('HARVEST_noop',0)}")
    OUT_PATH.write_text(json.dumps(out, indent=2))
    print(f"\nwrote {OUT_PATH}")


if __name__ == "__main__":
    main()
