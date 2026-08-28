"""S15 Phase 1 gate 2 — pin `_gate2_episode`'s counting logic against a synthetic tape,
and pin the day/hour <-> steps-index mapping against a real replay.

Everything downstream (the plant-fit and land-fit checks in `run_gate2_hand_routing`) is
arithmetic on these counts, so the counts are the only thing worth a dedicated oracle
here — `panel_g_melon`'s own primitives are already pinned in
`tests/test_s14_melon_rephasing.py`.

Same-day fix: `_gate2_window_steps` originally used `idx = day*24+hour+1`, one hour past
the observation it meant to read (`steps[idx]['observation']['day']/['hour']` is exactly
`divmod(idx, 24)`, not `divmod(idx-1, 24)`) — verified directly against real replays below.
`test_replay_index_matches_requested_day_hour` reddens on that pre-fix formula and is the
guard against the next off-by-one.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from analysis import s9_live_read_55726984 as s9  # noqa: E402
from analysis.s8_replay_io import load as load_replay, replay_paths  # noqa: E402

REFERENCE_SUBMISSION = "55726984"
REFERENCE_EPISODE = 97981710  # a real STRAF ladder episode, used throughout this S15 pass


def _reference_replay_path():
    for p in replay_paths(REFERENCE_SUBMISSION):
        if str(REFERENCE_EPISODE) in p.name:
            return p
    return None


pytestmark = pytest.mark.skipif(
    _reference_replay_path() is None,
    reason="reference live replay not on disk (gitignored competition data)",
)


def test_replay_index_matches_requested_day_hour():
    """`steps[day*24+hour]['observation']` carries that EXACT day/hour — the fact gate 2's
    window construction depends on. `idx = day*24+hour+1` (the pre-fix formula) would read
    back the NEXT hour here and fail every one of these, including the two window edges."""
    d = load_replay(_reference_replay_path())
    steps = d["steps"]
    seat = 1 if d["info"]["TeamNames"][1] == "STRAF" else 0
    for day, hour in [(0, 0), (6, 17), (6, 23), (7, 0), (7, 23), (8, 0)]:
        idx = day * 24 + hour
        o = steps[idx][seat]["observation"]
        assert (o["day"], o["hour"]) == (day, hour), (
            f"steps[{idx}] should be day={day} hour={hour}, got day={o['day']} hour={o['hour']}"
        )


def _step(farmer_action, hand_actions, free_tiles):
    """One step's seat-0 entry: an action plus an observation with `free_tiles` open cells
    on a flat 1xN board (enough to exercise the free-tile count without a real grid)."""
    tiles = [None] * free_tiles + [{"kind": "PLANT", "crop": "WHEAT"}] * 3
    return {
        "action": {"farmer": farmer_action, "hands": hand_actions},
        "observation": {
            "player": 0,
            "farms": [{"money": 0.0, "tiles": [tiles], "unlocked_quadrants": ["NW", "NE"],
                       "hands": []}],
        },
    }


def _steps_for_window():
    """steps[idx] for idx = day*24+hour must exist through d7h23 (idx 191), PLUS one more
    index (192, i.e. d8h0) for the window's closing observation — `_gate2_episode` reads
    that one index past the last window action, since the d7h23 action's EFFECT lands in
    the following observation, not the one it was decided from."""
    n = 8 * 24 + 1  # indices 0..192
    steps = [None] * n

    def put(day, hour, farmer, hands, free_tiles=10):
        idx = day * 24 + hour
        steps[idx] = [_step(farmer, hands, free_tiles)]

    # Fill the whole window with harmless PASS/PASS first so every index is populated.
    for day, hour in [(6, h) for h in range(17, 24)] + [(7, h) for h in range(24)]:
        put(day, hour, ["PASS"], [["PASS"], ["PASS"]])

    # One deliberate STRAWBERRY plant, one WHEAT plant, one PASTURE build, one move.
    put(6, 17, ["EAST"], [["PLANT", "STRAWBERRY"], ["PLANT", "WHEAT"]])
    put(6, 18, ["BUILD_PASTURE"], [["NORTH"], ["PASS"]])
    # The window's closing observation (d8h0, one past the last window action d7h23):
    # free tiles down to 5 here is what free_tiles_at_window_close must read.
    put(8, 0, ["PASS"], [["PASS"], ["PASS"]], free_tiles=5)
    return steps


def test_gate2_episode_counts_plants_moves_and_pass_correctly():
    steps = _steps_for_window()
    r = s9._gate2_episode(steps, seat=0, n_steps=len(steps))
    assert r["cnt_strawberry"] == 1
    assert r["cnt_wheat"] == 1
    assert r["cnt_pasture"] == 1
    assert r["hand_move"] == 1
    assert r["free_tiles_at_window_close"] == 5


def test_gate2_episode_idle_counts_farmer_and_hand_pass_separately():
    steps = _steps_for_window()
    r = s9._gate2_episode(steps, seat=0, n_steps=len(steps))
    # window is 31 turns; 2 turns carry a non-PASS farmer action (6h17, 6h18) -> 29 PASS
    assert r["farmer_pass"] == 29
    # hands: 62 total hand-turns (2/turn x 31), 3 are non-PASS (2 PLANTs + 1 move) -> 59 PASS
    assert r["hand_turns"] == 62
    assert r["hand_pass"] == 59
    assert r["idle"] == r["farmer_pass"] + r["hand_pass"]


def test_gate2_window_covers_exactly_31_turns():
    steps = _steps_for_window()
    window = [(6, h) for h in range(17, 24)] + [(7, h) for h in range(24)]
    assert len(window) == 31
    seen = list(s9._gate2_window_steps(window, len(steps)))
    assert len(seen) == 31
    # the corrected formula: first/last yielded idx are the window's own day*24+hour
    assert seen[0] == (6, 17, 6 * 24 + 17)
    assert seen[-1] == (7, 23, 7 * 24 + 23)
