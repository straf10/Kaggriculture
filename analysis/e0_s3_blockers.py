#!/usr/bin/env python3
"""E0 — ROADMAP §4.3 S3 step 1 pre-diagnostic: *which code path* stops our production.

Read-only. Imports `agent/` as a library and replays each day's hour-0 observation through
`agent.planner.make_day_plan`, so the plan the agent actually formed that morning (raw crop
targets, capacity-trimmed targets, hands_target) is recorded next to what the farm actually
looked like. Nothing under `agent/` is modified or monkeypatched at runtime except a local
wrapper around the module-private `_capacity_limited_targets`, which is restored on exit.

L2 (ROADMAP §3.2) named three blockers but not their mechanism:
  (a) crew never reaches 11+ hands            -> is the ceiling plan.hands_target or the fib budget?
  (b) 27,8% idle unit-turns                   -> is the task pool empty, or is it contention?
  (c) farm shuts down at d17 (0 tiles by d28) -> which per-crop day gate closes, and when?

Usage:
    .venv/Scripts/python.exe analysis/e0_s3_blockers.py --seeds 0 1 2 3 \
        --opponent harness/bench_agents/meta_route.py --out baselines/2026-08-12/e0_blockers.json
"""
from __future__ import annotations

import argparse
import gzip
import json
import statistics
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from agent import planner as planner_module  # noqa: E402
from agent.config import CONFIG  # noqa: E402
from agent.state import parse  # noqa: E402
from harness.play import play  # noqa: E402

TURNS_PER_DAY = CONFIG["runtime"]["turns_per_day"]
CROPS_TRACKED = ("CARROT", "STRAWBERRY", "WHEAT", "MELON")


def _observation(steps: list, index: int, seat: int) -> dict:
    """The seat's own observation at `index`, with the shared keys seat 0 always carries.

    kaggle_environments only repeats the shared state on seat 0's observation; seat 1's copy
    holds its own `player`/`private` and whatever the engine chose to duplicate. Merging
    seat-0-shared under seat-own is what makes `parse()` see a complete snapshot for seat 1.
    """
    shared = dict(steps[index][0]["observation"])
    own = dict(steps[index][seat]["observation"])
    shared.update(own)
    shared["player"] = seat
    return shared


def _tile_census(tiles: list) -> dict:
    planted: dict[str, int] = {}
    weeds = 0
    animals = 0
    for row in tiles:
        for tile in row:
            if not isinstance(tile, dict):
                continue
            if tile.get("kind") == "PLANT":
                planted[tile.get("crop", "?")] = planted.get(tile.get("crop", "?"), 0) + 1
            elif tile.get("kind") == "WEED":
                weeds += 1
            if "animal" in tile:
                animals += 1
    return {"planted": planted, "weeds": weeds, "animals": animals}


def trace_seat(env_json: dict, seat: int) -> list[dict]:
    """One row per day: what the farm was, and what the planner asked for that morning."""
    steps = env_json["steps"]
    n_days = len(steps) // TURNS_PER_DAY
    rows = []

    captured: dict = {}
    original = planner_module._capacity_limited_targets

    def _spy(snapshot, config, raw_targets):
        result = original(snapshot, config, raw_targets)
        captured["raw"] = dict(raw_targets)
        captured["limited"] = dict(result)
        return result

    planner_module._capacity_limited_targets = _spy
    try:
        for day in range(n_days):
            index = day * TURNS_PER_DAY
            if index >= len(steps):
                break
            observation = _observation(steps, index, seat)
            snapshot = parse(observation)
            captured.clear()
            plan = planner_module.make_day_plan(snapshot, CONFIG, env_json.get("configuration"))
            census = _tile_census(snapshot.my_tiles)
            # The engine wipes farm["hands"] at every day rollover and the agent re-hires during
            # hour 0, so the hour-0 observation always reads 0 hands. Read the crew that actually
            # worked the day from mid-day, and the day's hire count from its last hour.
            midday = min(index + TURNS_PER_DAY // 2, len(steps) - 1)
            end_of_day = min(index + TURNS_PER_DAY - 1, len(steps) - 1)
            midday_snapshot = parse(_observation(steps, midday, seat))
            hires_today = parse(_observation(steps, end_of_day, seat)).hires_today
            rows.append({
                "day": day,
                "money": round(snapshot.money),
                "hands": len(midday_snapshot.hand_positions),
                "hires_today": hires_today,
                "money_midday": round(midday_snapshot.money),
                "hands_target": plan.hands_target,
                "quadrants": list(snapshot.my_quadrants),
                "animals_placed": census["animals"],
                "weed_tiles": census["weeds"],
                "planted": {crop: census["planted"].get(crop, 0) for crop in CROPS_TRACKED},
                "planted_total": sum(census["planted"].values()),
                "raw_targets": captured.get("raw", {}),
                "plant_targets": dict(plan.plant_targets),
                "max_new_plants": plan.max_new_plants,
                "capacity_trimmed": {
                    crop: captured.get("raw", {}).get(crop, 0) - captured.get("limited", {}).get(crop, 0)
                    for crop in captured.get("raw", {})
                    if captured.get("raw", {}).get(crop, 0) > captured.get("limited", {}).get(crop, 0)
                },
                "phase": plan.season_phase,
            })
    finally:
        planner_module._capacity_limited_targets = original
    return rows


def diagnose(rows: list[dict], metrics: dict) -> dict:
    """Turn the per-day trace into the three named answers, in one place."""
    hands_capped = [r for r in rows if r["hands"] < r["hands_target"]]
    strawberry_target_zero = next(
        (r["day"] for r in rows if r["day"] > 0 and r["raw_targets"].get("STRAWBERRY", 0) == 0), None
    )
    strawberry_gone = next(
        (r["day"] for r in rows if r["day"] > 5 and r["planted"]["STRAWBERRY"] == 0), None
    )
    farm_empty = next((r["day"] for r in rows if r["day"] > 5 and r["planted_total"] == 0), None)
    peak_planted = max((r["planted_total"] for r in rows), default=0)
    daily = metrics.get("daily", [])
    total = sum(
        r["worker_turns_moving"] + r["worker_turns_working"] + r["worker_turns_idle"] for r in daily
    )
    return {
        # (a) is the crew ceiling the config target, or money?
        "hands_target_by_day": {r["day"]: r["hands_target"] for r in rows},
        "hands_actual_by_day": {r["day"]: r["hands"] for r in rows},
        "days_hands_below_target": [r["day"] for r in hands_capped],
        "max_hands_target": max((r["hands_target"] for r in rows), default=0),
        "max_hands_actual": max((r["hands"] for r in rows), default=0),
        # (c) which crop gate closes, and when
        "first_day_strawberry_raw_target_zero": strawberry_target_zero,
        "first_day_no_strawberry_planted": strawberry_gone,
        "first_day_farm_empty": farm_empty,
        "peak_planted_tiles": peak_planted,
        "planted_at_d20": next((r["planted_total"] for r in rows if r["day"] == 20), None),
        "planted_at_d24": next((r["planted_total"] for r in rows if r["day"] == 24), None),
        "days_capacity_gate_trimmed": [r["day"] for r in rows if r["capacity_trimmed"]],
        # (b) idle share
        "worker_turns_idle_pct": (
            100.0 * sum(r["worker_turns_idle"] for r in daily) / total if total else None
        ),
        "worker_turns_working_pct": (
            100.0 * sum(r["worker_turns_working"] for r in daily) / total if total else None
        ),
        "crop_tile_days": metrics.get("crop_tile_days"),
        "final_bank": metrics.get("final_bank"),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seeds", type=int, nargs="+", default=[0, 1, 2, 3])
    parser.add_argument("--agent", default="main.py")
    parser.add_argument("--opponent", default="harness/bench_agents/meta_route.py")
    parser.add_argument("--out", default=None)
    args = parser.parse_args()

    results = []
    with tempfile.TemporaryDirectory() as tmp:
        for seed in args.seeds:
            for seat in (0, 1):
                agents = (
                    (args.agent, args.opponent) if seat == 0 else (args.opponent, args.agent)
                )
                result = play(*agents, seed=seed, record=True, run_dir=Path(tmp), metrics=True)
                with gzip.open(result.replay_path, "rt", encoding="utf-8") as f:
                    env_json = json.load(f)
                rows = trace_seat(env_json, seat)
                metrics = result.metrics[seat]
                results.append({
                    "seed": seed,
                    "seat": seat,
                    "bank": result.rewards[seat],
                    "rows": rows,
                    "diagnosis": diagnose(rows, metrics),
                })
                print(
                    f"seed={seed} seat={seat} bank=${result.rewards[seat]:,.0f} "
                    f"tile_days={metrics['crop_tile_days']} "
                    f"peak_tiles={results[-1]['diagnosis']['peak_planted_tiles']} "
                    f"d24_tiles={results[-1]['diagnosis']['planted_at_d24']} "
                    f"max_hands={results[-1]['diagnosis']['max_hands_actual']}"
                    f"/{results[-1]['diagnosis']['max_hands_target']} "
                    f"idle={results[-1]['diagnosis']['worker_turns_idle_pct']:.1f}%",
                    flush=True,
                )

    summary = {
        "n_runs": len(results),
        "median_bank": statistics.median(r["bank"] for r in results),
        "median_crop_tile_days": statistics.median(
            r["diagnosis"]["crop_tile_days"] for r in results
        ),
        "median_idle_pct": statistics.median(
            r["diagnosis"]["worker_turns_idle_pct"] for r in results
        ),
        "max_hands_actual": max(r["diagnosis"]["max_hands_actual"] for r in results),
        "max_hands_target": max(r["diagnosis"]["max_hands_target"] for r in results),
        "hands_ever_below_target": sorted(
            {d for r in results for d in r["diagnosis"]["days_hands_below_target"]}
        ),
        "first_day_strawberry_raw_target_zero": sorted(
            {r["diagnosis"]["first_day_strawberry_raw_target_zero"] for r in results}
        ),
        "first_day_no_strawberry_planted": sorted(
            {r["diagnosis"]["first_day_no_strawberry_planted"] for r in results}
        ),
        "first_day_farm_empty": sorted({r["diagnosis"]["first_day_farm_empty"] for r in results}),
        "median_planted_d20": statistics.median(
            r["diagnosis"]["planted_at_d20"] for r in results
        ),
        "median_planted_d24": statistics.median(
            r["diagnosis"]["planted_at_d24"] for r in results
        ),
        "days_capacity_gate_trimmed": sorted(
            {d for r in results for d in r["diagnosis"]["days_capacity_gate_trimmed"]}
        ),
    }
    print("\n== E0 summary ==")
    print(json.dumps(summary, indent=2))

    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(
            json.dumps({"summary": summary, "runs": results}, indent=1), encoding="utf-8"
        )
        print(f"\nwrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
