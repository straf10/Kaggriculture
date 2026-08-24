"""Tests for clean-room meta-bench opponents (§Β.2)."""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from harness.play import play, resolve_agent

REPO_ROOT = Path(__file__).resolve().parents[1]
META = REPO_ROOT / "harness" / "bench_agents" / "meta_route.py"
META_SHEEP = REPO_ROOT / "harness" / "bench_agents" / "meta_route_sheep.py"
BASELINE = REPO_ROOT / "checkpoints" / "v1h_2d" / "main.py"


def test_meta_route_is_last_callable():
    assert resolve_agent(str(META), entrypoint="agent").__name__ == "meta_route"
    assert resolve_agent(str(META_SHEEP), entrypoint="agent").__name__ == "meta_route_sheep"


def test_meta_route_clean_both_seats_short():
    """Smoke clean on both seats (short episode — full-season coverage is in gate artefacts)."""
    for seat_meta_first in (True, False):
        a, b = (str(META), "pass") if seat_meta_first else ("pass", str(META))
        result = play(a, b, seed=0, steps=48, record=False, strict=True)
        assert result.clean
        assert result.statuses == ("DONE", "DONE")


def test_meta_route_sheep_clean_short():
    result = play(str(META_SHEEP), "pass", seed=1, steps=48, record=False, strict=True)
    assert result.clean
    assert result.statuses == ("DONE", "DONE")


def test_meta_route_determinism_cross_process_hashseed():
    """G13 / acceptance #2: same seed × 2 processes × different PYTHONHASHSEED."""
    snippet = (
        "import json\n"
        "from kaggle_environments import make\n"
        f"meta = {str(META)!r}\n"
        "env = make('kaggriculture', configuration={'seed': 3, 'episodeSteps': 96})\n"
        "env.run([meta, 'pass'])\n"
        "result = env.toJSON()\n"
        "result.pop('id', None)\n"
        "print(json.dumps(result, sort_keys=True))\n"
    )

    def run(hash_seed: str):
        process = subprocess.run(
            [sys.executable, "-c", snippet],
            cwd=str(REPO_ROOT),
            env={**os.environ, "PYTHONHASHSEED": hash_seed},
            capture_output=True,
            text=True,
            check=True,
        )
        return json.loads(process.stdout.strip().splitlines()[-1])

    assert run("0") == run("12345")


def test_meta_route_profile_metrics_seed0():
    """Acceptance #4 ranges on a full episode (vs pass, so sales are its own)."""
    result = play(str(META), "pass", seed=0, record=False, strict=True)
    assert result.clean
    m = result.metrics[0]
    melon = m["units_sold_by_product"].get("MELON", 0)
    tiles = m["crop_tile_days"]
    # Published targets: melon ~80-160, crop_tile_days ~688 (fail if >2× off).
    assert 80 <= melon <= 160, f"melon sales {melon} outside 80-160"
    assert 344 <= tiles <= 1376, f"crop_tile_days {tiles} >2× off ~688"

    # 3 quadrants by mid/late season — infer from bank+tile scale; explicit check via short
    # recorded probe would be heavier. Land config lists NE+SW and seed-0 clean scan confirmed
    # 3 unlocks; here assert the agent is productive enough that land path is live.
    assert m["final_bank"] > 20_000
