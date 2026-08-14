#!/usr/bin/env python3
"""v1q — trace, per escaped animal, the exact mechanism of the onboarding-escape defect
(ROADMAP §4.3 S3 step 1d, prompt.md §2). This defect has been misattributed four times
(v1j, v1h', v1o.2/v1o.3, v1p.1); it is deterministic (~2,00 escapes/episode under arm A1,
in both COW/SHEEP orientations, on 24/24 SMOKE orientations — ROADMAP §3.3), which makes it
the cheapest bug in the repo to actually trace instead of guess at again.

Engine rule (engine_reference/kaggriculture.py, verified 2026-08-14):
  - `_new_animal` (:216-227) creates the animal with fed_today=False, consecutive_unfed=0.
  - `_daily_refresh_animals` (:792-804): at each day boundary, fed_today False =>
    consecutive_unfed += 1; >= 2 => the animal escapes and the structure remains.
  - FEED (:492-500) requires the acting unit to already hold 1 WHEAT in its own inventory,
    AND to be standing on the animal's tile (actions carry no target position — every op
    applies to the unit's current tile, confirmed against a probe replay).

agent/scheduler.py::_build_animal_tasks (:355-451) builds an UNCONDITIONAL FEED Task for
every tile with fed_today=False, every single hour — there is no PLACE-time feasibility
check anywhere in the current code. So "was a FEED task offered" is always yes by
construction; the open question this script exists to answer is whether the tile was
*reachable* that day (Branch A — no unit had time+wheat to get there) or *reachable but
lost the greedy assign() contention* (Branch B) — see prompt.md §2.5's three-way branch.

Usage:
    KAGGRI_DEBUG=1 .venv/bin/python analysis/v1q_onboarding_escape.py --seeds 0,1,2
"""
import argparse
import gzip
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from agent.config import CONFIG  # noqa: E402
from agent.constants import SHED_ACCESS  # noqa: E402
from harness.play import play  # noqa: E402
from harness.town_pin import pinned_town, schedule_for_mode  # noqa: E402

CANDIDATE = "checkpoints/v1p1b_armA1/main.py"  # arm A1 — the config that measured 48 escapes
BASELINE = "checkpoints/v1q_base/main.py"  # rebuilt inert baseline (fingerprint a22cd401…)

TURNS_PER_DAY = CONFIG["runtime"]["turns_per_day"]


def manhattan(a, b):
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def dist_to_shed(pos):
    return min(manhattan(pos, access) for access in SHED_ACCESS)


def unit_positions(obs, seat):
    """[farmer_pos, hand0_pos, hand1_pos, ...] — same order as private.inventories."""
    mine = obs["farms"][seat]
    return [tuple(mine["farmer"])] + [tuple(h) for h in mine.get("hands", [])]


def unit_action_list(action):
    """[farmer_action, hand0_action, ...] — same order/index as unit_positions()."""
    return [action.get("farmer", [])] + list(action.get("hands", []))


def find_escape_events(steps, seat):
    """Every tile that held an animal one step and did not the next, with day/hour/pos —
    mirrors analysis/v1i_escape_diagnostic.py's own escape test."""
    events = []
    for index in range(len(steps) - 1):
        previous = steps[index][0]["observation"]
        current = steps[index + 1][0]["observation"]
        prev_tiles = previous["farms"][seat]["tiles"]
        cur_tiles = current["farms"][seat]["tiles"]
        for y, row in enumerate(prev_tiles):
            for x, prev_tile in enumerate(row):
                if not (isinstance(prev_tile, dict) and "animal" in prev_tile):
                    continue
                cur_tile = cur_tiles[y][x]
                if (
                    isinstance(cur_tile, dict)
                    and "animal" not in cur_tile
                    and cur_tile.get("kind") == prev_tile.get("kind")
                ):
                    events.append({
                        "escape_step": index,  # last step the animal was observed alive
                        "day": int(previous.get("day", 0)),
                        "hour": int(previous.get("hour", 0)),
                        "pos": (x, y),
                        "animal": prev_tile.get("animal"),
                        "consecutive_unfed_at_escape": prev_tile.get("consecutive_unfed"),
                    })
    return events


def find_place_step(steps, seat, pos, escape_step):
    """The most recent step at which this tile's animal-presence transitioned False->True
    at or before escape_step (the PLACE action executed the turn before this observation)."""
    x, y = pos
    for index in range(escape_step, 0, -1):
        prev_tile = steps[index - 1][0]["observation"]["farms"][seat]["tiles"][y][x]
        cur_tile = steps[index][0]["observation"]["farms"][seat]["tiles"][y][x]
        prev_has = isinstance(prev_tile, dict) and "animal" in prev_tile
        cur_has = isinstance(cur_tile, dict) and "animal" in cur_tile
        if cur_has and not prev_has:
            return index
    return 0


def find_placing_unit(steps, seat, pos, animal, placed_step):
    """Which unit index (0=farmer, 1+=hands, matching private.inventories order) executed
    the PLACE. kaggle_environments' own convention: steps[i]["observation"] is the state
    AFTER steps[i]["action"] was applied, and that action was chosen from steps[i-1]'s
    observation — so the acting unit's pre-action position is steps[placed_step-1]'s, while
    the action that actually produced the animal is recorded at steps[placed_step] itself
    (verified directly against a probe replay: the PLACE action and its resulting tile state
    appear in the SAME steps[] entry)."""
    if placed_step == 0:
        return None  # animal present at episode/window start — not a traced PLACE
    obs = steps[placed_step - 1][0]["observation"]
    # steps[i][0] is always seat 0's log entry — "observation" mirrors both farms so seat is
    # just an index into it, but "action" is logged per-acting-agent: seat 1's own action for
    # this turn lives at steps[i][1], not steps[i][0] (confirmed against a probe replay: seat
    # 1's actual PLACE for the same tile/step was invisible at index 0 and present at index 1).
    action = steps[placed_step][seat]["action"]
    positions = unit_positions(obs, seat)
    actions = unit_action_list(action)
    for unit_index, (unit_pos, unit_action) in enumerate(zip(positions, actions)):
        if unit_pos == pos and unit_action and unit_action[0] == "PLACE" and unit_action[1:2] == [animal]:
            return unit_index
    return None


def day_boundary_steps(placed_day, escape_day):
    """Step indices at the START of each day from placed_day to escape_day inclusive."""
    return {day: day * TURNS_PER_DAY for day in range(placed_day, escape_day + 1)}


def daily_trace(steps, seat, pos, placed_step, escape_step):
    """Per-day: fed_today at day-end (last observed hour of that day), consecutive_unfed,
    whether the tile was reachable that day (Branch A/B test — turns_left_today at PLACE-day
    origin vs distance from shed with wheat), and what every unit was doing at the day's last
    hour (contention evidence for Branch B)."""
    x, y = pos
    placed_day = steps[placed_step][0]["observation"].get("day", 0) if placed_step < len(steps) else None
    escape_day = steps[escape_step][0]["observation"].get("day", 0)
    days = sorted(set(range(placed_day, escape_day + 1))) if placed_day is not None else [escape_day]

    trace = []
    for day in days:
        day_start_step = day * TURNS_PER_DAY
        day_end_step = min((day + 1) * TURNS_PER_DAY - 1, len(steps) - 1)
        if day_start_step >= len(steps):
            break
        start_obs = steps[day_start_step][0]["observation"]
        end_obs = steps[day_end_step][0]["observation"]
        tile_start = start_obs["farms"][seat]["tiles"][y][x]
        tile_end = end_obs["farms"][seat]["tiles"][y][x]
        if not (isinstance(tile_end, dict) and "animal" in tile_end):
            # escaped or not yet placed by day-end; use the last step it existed
            tile_end = steps[min(escape_step, day_end_step)][0]["observation"]["farms"][seat]["tiles"][y][x]

        turns_left_at_start = TURNS_PER_DAY - start_obs.get("hour", 0)
        distance_shed_to_tile = dist_to_shed((x, y))

        # Branch A/B feasibility test: at the START of this day, could ANY unit realistically
        # reach the tile with wheat before day-end? (mirrors arm P's own precondition formula,
        # prompt.md §3.2 Arm P)
        positions = unit_positions(start_obs, seat)
        inventories = start_obs["private"]["inventories"]
        shed_wheat_at_start = int(start_obs["private"]["shed"].get("WHEAT", 0))
        best_slack = None
        for unit_index, unit_pos in enumerate(positions):
            carries_wheat = inventories[unit_index].get("WHEAT", 0) > 0 if unit_index < len(inventories) else False
            if carries_wheat:
                needed = manhattan(unit_pos, (x, y)) + 1
            elif shed_wheat_at_start > 0:
                needed = manhattan(unit_pos, SHED_ACCESS[0]) + distance_shed_to_tile + 2
            else:
                continue
            slack = turns_left_at_start - needed
            if best_slack is None or slack > best_slack:
                best_slack = slack
        feasible_today = bool(best_slack is not None and best_slack >= 0)

        # Contention evidence: what was every unit doing at the day's last hour (proxy for
        # "who had the FEED task and did something else instead"). Same steps[i][seat] rule
        # as find_placing_unit — "action" is per-acting-agent, not mirrored like "observation".
        end_action = steps[min(day_end_step, len(steps) - 1)][seat]["action"]
        end_positions = unit_positions(end_obs, seat)
        end_inventories = end_obs["private"]["inventories"]
        unit_activity = [
            {
                "unit": idx,
                "pos": pos_,
                "action": act,
                "carries_wheat": end_inventories[idx].get("WHEAT", 0) if idx < len(end_inventories) else 0,
                "distance_to_tile": manhattan(pos_, (x, y)),
            }
            for idx, (pos_, act) in enumerate(zip(end_positions, unit_action_list(end_action)))
        ]

        trace.append({
            "day": day,
            "fed_today_at_day_end": bool(tile_end.get("fed_today")) if isinstance(tile_end, dict) else None,
            "consecutive_unfed_at_day_end": tile_end.get("consecutive_unfed") if isinstance(tile_end, dict) else None,
            "turns_left_at_day_start": turns_left_at_start,
            "shed_wheat_at_day_start": shed_wheat_at_start,
            "distance_shed_to_tile": distance_shed_to_tile,
            "best_feasibility_slack": best_slack,
            "feasible_today": feasible_today,
            "unit_activity_at_day_end": unit_activity,
        })
    return trace


def trace_one(steps, seat, event, label):
    pos = event["pos"]
    escape_step = event["escape_step"]
    placed_step = find_place_step(steps, seat, pos, escape_step)
    placed_obs = steps[placed_step][0]["observation"]
    placing_unit = find_placing_unit(steps, seat, pos, event["animal"], placed_step)

    turns_left_today_at_place = TURNS_PER_DAY - placed_obs.get("hour", 0)
    shed_wheat_at_place = int(placed_obs["private"]["shed"].get("WHEAT", 0))
    inventories_at_place = placed_obs["private"]["inventories"]
    wheat_by_unit_at_place = [inv.get("WHEAT", 0) for inv in inventories_at_place]
    distance_shed_to_tile = dist_to_shed(pos)

    return {
        "label": label,
        "animal": event["animal"],
        "tile": pos,
        "placed_day": int(placed_obs.get("day", 0)),
        "placed_step": placed_step,
        "placing_unit": placing_unit,
        "escape_step": escape_step,
        "escape_day": event["day"],
        "consecutive_unfed_at_escape": event["consecutive_unfed_at_escape"],
        "at_place": {
            "turns_left_today": turns_left_today_at_place,
            "shed_wheat": shed_wheat_at_place,
            "wheat_by_unit": wheat_by_unit_at_place,
            "distance_shed_to_tile": distance_shed_to_tile,
        },
        "daily_trace": daily_trace(steps, seat, pos, placed_step, escape_step),
    }


def run_seed(seed, out_dir):
    # CANDIDATE and BASELINE are both packaged as .../main.py, so harness.play's own
    # filename sanitizer (Path(name).stem) collapses both to "main" — the two orientations'
    # replay paths collide. Read and fully consume each orientation's replay JSON before
    # starting the next play() call, or the second write silently clobbers the first.
    out = {}
    for orientation_name, agent_a, agent_b, candidate_seat, baseline_seat in (
        ("A@0_B@1", CANDIDATE, BASELINE, 0, 1),
        ("A@1_B@0", BASELINE, CANDIDATE, 1, 0),
    ):
        run_dir = out_dir / "replays" / orientation_name
        with pinned_town("basket", schedule_for_mode("basket", seed)):
            result = play(agent_a, agent_b, seed=seed, record=True, run_dir=run_dir, metrics=False, strict=False)
        with gzip.open(result.replay_path, "rt", encoding="utf-8") as handle:
            env_json = json.load(handle)
        steps = env_json["steps"]

        candidate_events = find_escape_events(steps, candidate_seat)
        baseline_events = find_escape_events(steps, baseline_seat)

        out[orientation_name] = {
            "seed": seed,
            "candidate_seat": candidate_seat,
            "baseline_seat": baseline_seat,
            "candidate_escape_count": len(candidate_events),
            "baseline_escape_count": len(baseline_events),
            "candidate_traces": [
                trace_one(steps, candidate_seat, ev, "candidate(arm_A1)") for ev in candidate_events
            ],
            "baseline_traces": [
                trace_one(steps, baseline_seat, ev, "baseline(v1q_base)") for ev in baseline_events
            ],
        }
    return out


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--seeds", default="0,1,2")
    parser.add_argument("--out", default="gates/v1q_onboarding_escape")
    args = parser.parse_args()

    out_dir = REPO / args.out
    out_dir.mkdir(parents=True, exist_ok=True)

    report = {}
    for seed in [int(s) for s in args.seeds.split(",")]:
        report[f"seed{seed}"] = run_seed(seed, out_dir)

    (out_dir / "diagnosis.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
