"""v1j 2x2 smoke sweep: sw_wheat_tiles x sw_hands_target vs checkpoints/v1h_2d.

OCCUPANCY knob => --town-pin basket. SMOKE seeds only — never GO.
Edits agent/config.py between cells sequentially (never while a gate is running).
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
CONFIG = REPO / "agent" / "config.py"
VENV_PY = REPO / ".venv" / "Scripts" / "python.exe"
BASELINE = "checkpoints/v1h_2d/main.py"
OUT_ROOT = REPO / "gates" / "v1j_smoke_2x2"

# (wheat_tiles, hands, max_new_plants_per_day)
CELLS = [
    (12, 10, 3),  # baseline control — expect ~0
    (12, 12, 3),  # crew-only control — expect negative
    (24, 10, 6),  # land-only control — expect negative
    (24, 12, 6),  # diagonal — must be positive or STOP
]


def _patch_config(wheat: int, hands: int, plants: int) -> None:
    text = CONFIG.read_text(encoding="utf-8")
    text2, n1 = re.subn(
        r'("sw_hands_target":\s*)\d+',
        rf"\g<1>{hands}",
        text,
        count=1,
    )
    text2, n2 = re.subn(
        r'("sw_wheat_tiles":\s*)\d+',
        rf"\g<1>{wheat}",
        text2,
        count=1,
    )
    text2, n3 = re.subn(
        r'("sw_max_new_plants_per_day":\s*)\d+',
        rf"\g<1>{plants}",
        text2,
        count=1,
    )
    if n1 != 1 or n2 != 1 or n3 != 1:
        raise RuntimeError(f"config patch failed: hands={n1} wheat={n2} plants={n3}")
    CONFIG.write_text(text2, encoding="utf-8")
    # verify
    got = CONFIG.read_text(encoding="utf-8")
    assert f'"sw_hands_target": {hands}' in got
    assert f'"sw_wheat_tiles": {wheat}' in got
    assert f'"sw_max_new_plants_per_day": {plants}' in got


def _run_cell(wheat: int, hands: int, plants: int) -> dict:
    name = f"w{wheat}_h{hands}"
    out = OUT_ROOT / name
    out.mkdir(parents=True, exist_ok=True)
    results_path = out / "results.json"
    if results_path.exists():
        print(f"SKIP {name} — results already present")
        return json.loads(results_path.read_text(encoding="utf-8"))

    _patch_config(wheat, hands, plants)
    print(f"\n=== CELL {name} (plants/day={plants}) ===", flush=True)
    cmd = [
        str(VENV_PY),
        "-m",
        "harness.cli",
        "compare",
        "main.py",
        BASELINE,
        "--seed-set",
        "smoke",
        "--town-pin",
        "basket",
        "--metrics",
        "--metric-mechanism",
        "shed_overflow_burnt=peak production vs sell bandwidth (v1h.2d residual)",
        "--metric-mechanism",
        "water_weeds_lost=unit contention residual (v1h.2d FEED slack tradeoff)",
        "--metric-mechanism",
        "unexpected_weeds_lost=unit contention residual (v1h.2d FEED slack tradeoff)",
        "--workers",
        "6",
        "--out",
        str(out),
        "--gates-dir",
        str(OUT_ROOT / "tracked"),
    ]
    print(" ".join(cmd), flush=True)
    rr = subprocess.run(cmd, cwd=str(REPO))
    if rr.returncode != 0:
        raise RuntimeError(f"compare failed for {name} rc={rr.returncode}")
    return json.loads(results_path.read_text(encoding="utf-8"))


def _summarize(wheat: int, hands: int, result: dict) -> None:
    name = f"w{wheat}_h{hands}"
    print(
        f"{name}: verdict={result.get('verdict')} mean_diff={result.get('mean_diff'):+.1f} "
        f"median_bank_a={result.get('median_bank_a')} "
        f"overflow={result.get('shed_overflow_burnt_a')} "
        f"water_weeds={result.get('water_weeds_lost_a')} "
        f"escapes={result.get('animals_escaped_a')} "
        f"priced={result.get('priced_loss_per_episode')} "
        f"gate={result.get('metric_gate_passed')}",
        flush=True,
    )


def main() -> int:
    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    summary = []
    # Always restore baseline config at the end.
    try:
        for wheat, hands, plants in CELLS:
            result = _run_cell(wheat, hands, plants)
            _summarize(wheat, hands, result)
            summary.append(
                {
                    "wheat": wheat,
                    "hands": hands,
                    "plants": plants,
                    "verdict": result.get("verdict"),
                    "mean_diff": result.get("mean_diff"),
                    "median_bank_a": result.get("median_bank_a"),
                    "shed_overflow_burnt_a": result.get("shed_overflow_burnt_a"),
                    "water_weeds_lost_a": result.get("water_weeds_lost_a"),
                    "animals_escaped_a": result.get("animals_escaped_a"),
                    "priced_loss_per_episode": result.get("priced_loss_per_episode"),
                    "metric_gate_passed": result.get("metric_gate_passed"),
                    "wins_a": result.get("wins_a"),
                    "wins_b": result.get("wins_b"),
                }
            )
    finally:
        _patch_config(12, 10, 3)
        print("restored config to wheat=12 hands=10 plants=3", flush=True)

    (OUT_ROOT / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print("\n=== 2x2 SUMMARY ===")
    for row in summary:
        print(
            f"  {{{row['wheat']},{row['hands']}}}: mean_diff={row['mean_diff']:+.1f} "
            f"verdict={row['verdict']} median_bank={row['median_bank_a']} "
            f"overflow={row['shed_overflow_burnt_a']} weeds={row['water_weeds_lost_a']}"
        )

    diag = next(r for r in summary if r["wheat"] == 24 and r["hands"] == 12)
    if diag["mean_diff"] is None or diag["mean_diff"] <= 0:
        print(
            "\nSTOP: diagonal {24,12} is not positive — scale hypothesis falsified.",
            flush=True,
        )
        return 2
    print("\nGO-smoke: diagonal {24,12} positive — proceed to DEV screen.", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
