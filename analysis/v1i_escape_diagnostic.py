#!/usr/bin/env python3
"""v1i — written mechanism for the non-zero `animals_escaped_a` in the mirror DEV arm.

current_phase.md §1 Απόφαση Δ (2) is absolute: every non-zero priced counter **of the
candidate** needs a declared mechanism, and "I don't know why" is a bug and a STOP regardless
of price or delta. `gates/v1i_dev_mirror` reported `animals_escaped_a = 4` — on 2 of 48 seeds,
seat-symmetrically (seed 40: whoever sits at seat 0; seed 45: whoever sits at seat 1). This
script establishes *why*, and in particular whether v1i caused it.

The decisive comparison is a control, not a narrative: replay the same seed and orientation
with the **baseline in both seats**. If the same seat still loses the same animals on the same
day with no v1i code anywhere in the episode, the mechanism belongs to the seed's town draw and
the seat's feed contention, not to the increment.

Receipts (`KAGGRI_DEBUG=1`) add the leading indicator the escape path was built around:
`wheat_shortfall` (agent/executor.py) fires whenever the agent wanted feed money it did not
have.

Usage:
    KAGGRI_DEBUG=1 python analysis/v1i_escape_diagnostic.py --seeds 40,45
"""
import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from harness.metrics import extract_metrics  # noqa: E402
from harness.play import play  # noqa: E402

CANDIDATE = "main.py"
BASELINE = "checkpoints/v1m_d2/main.py"


def escape_events(env_json, seat: int) -> list[dict]:
    """Every tile that held an animal one step and did not the next, with day and position.

    Mirrors `harness.metrics`' own escape test (a tile keeps its structure `kind` but loses
    its `animal`, and the transition is not a HARVEST), but keeps the coordinates and the day
    that the aggregate counter throws away.
    """
    steps = env_json["steps"]
    events = []
    for index in range(len(steps) - 1):
        previous = steps[index][0]["observation"]
        current = steps[index + 1][0]["observation"]
        previous_tiles = previous["farms"][seat]["tiles"]
        current_tiles = current["farms"][seat]["tiles"]
        for y, row in enumerate(previous_tiles):
            for x, previous_tile in enumerate(row):
                if not (isinstance(previous_tile, dict) and "animal" in previous_tile):
                    continue
                current_tile = current_tiles[y][x]
                if (
                    isinstance(current_tile, dict)
                    and "animal" not in current_tile
                    and current_tile.get("kind") == previous_tile.get("kind")
                ):
                    events.append({
                        "day": int(previous.get("day", 0)),
                        "hour": int(previous.get("hour", 0)),
                        "pos": [x, y],
                        "animal": previous_tile.get("animal"),
                        "consecutive_unfed": previous_tile.get("consecutive_unfed"),
                        "money": previous["farms"][seat].get("money"),
                        "shed_wheat": steps[index][seat]["observation"]["private"]["shed"]
                        .get("WHEAT", 0),
                    })
    return events


def run(agent_a, agent_b, seed, seat_of_interest, run_dir):
    result = play(agent_a, agent_b, seed=seed, record=True, run_dir=run_dir, metrics=False)
    with __import__("gzip").open(result.replay_path, "rt", encoding="utf-8") as handle:
        env_json = json.load(handle)
    metrics = extract_metrics(env_json, seat_of_interest, diagnostics=result.diagnostics)
    shortfalls = [
        d for d in result.diagnostics
        if d.get("seat") == seat_of_interest and d.get("kind") == "wheat_shortfall"
    ]
    by_day = defaultdict(int)
    for shortfall in shortfalls:
        by_day[shortfall["step"] // 24] += 1
    return {
        "agents": [agent_a, agent_b],
        "seat": seat_of_interest,
        "bank": env_json["rewards"][seat_of_interest],
        "animals_escaped": metrics["animals_escaped"],
        "animals_underfed_days": metrics["animals_underfed_days"],
        "escape_events": escape_events(env_json, seat_of_interest),
        "wheat_shortfall_turns": len(shortfalls),
        "wheat_shortfall_by_day": dict(sorted(by_day.items())),
        "first_shortfalls": shortfalls[:5],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--seeds", default="40,45")
    parser.add_argument("--out", default="gates/v1i_escape_diagnostic")
    args = parser.parse_args()

    out_dir = REPO / args.out
    out_dir.mkdir(parents=True, exist_ok=True)
    run_dir = out_dir / "replays"

    report = {}
    for seed in [int(s) for s in args.seeds.split(",")]:
        # gates/v1i_dev_mirror: seed 40's escapes land on whoever holds seat 0, seed 45's on
        # whoever holds seat 1 — so measure that seat, and put the candidate in it.
        seat = 0 if seed == 40 else 1
        candidate_pair = (CANDIDATE, BASELINE) if seat == 0 else (BASELINE, CANDIDATE)
        report[f"seed{seed}"] = {
            "seat_measured": seat,
            "candidate_arm": run(*candidate_pair, seed, seat, run_dir),
            # The control: no v1i anywhere in the episode.
            "baseline_control": run(BASELINE, BASELINE, seed, seat, run_dir),
        }

    (out_dir / "diagnosis.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
