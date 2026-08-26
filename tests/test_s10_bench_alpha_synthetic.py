"""S11 B3.4 — alpha-control on synthetic replays.

Guards the single most precise property of the instrument: `play` + `make_tape_agent` +
`_extract_streams` reproduce the engine's recorded rewards **bit-exactly** when both seats
replay their recorded action streams.

Runs on freshly generated engine episodes (no shed manipulation, so `play()` can
reproduce the same initial state), always executes in CI.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from analysis.s8_replay_io import load, meta, replay_paths  # noqa: E402
from analysis.s10_replay_bench import _extract_streams  # noqa: E402
from analysis.tape_agent import make_tape_agent  # noqa: E402
from harness.play import play  # noqa: E402
from fixtures.replays import write_synthetic_replay  # noqa: E402

PASS = {"farmer": ["PASS"], "hands": [], "market": []}


def _buy_then_sell(item, buy_steps=5):
    """Agent that buys `item` for `buy_steps` turns, then sells forever."""
    def act(i):
        if i < buy_steps:
            return {"farmer": ["PASS"], "hands": [],
                    "market": [["BUY_PRODUCT", item, 2]]}
        return {"farmer": ["PASS"], "hands": [],
                "market": [["SELL", item, 2]]}
    return act


def test_alpha_bit_exact_on_synthetic(tmp_path):
    """Tape replay of a synthetic episode reproduces rewards bit-exactly."""
    d = tmp_path / "alpha_corpus"
    d.mkdir()

    configs = [
        (200001, 42, _buy_then_sell("WHEAT"), None),
        (200002, 43, None, _buy_then_sell("WHEAT")),
        (200003, 44, _buy_then_sell("WHEAT"), _buy_then_sell("FERTILIZER")),
    ]
    failures = []
    for eid, seed, act0, act1 in configs:
        p = write_synthetic_replay(
            d, eid, seed=seed, episode_steps=30,
            teams=("STRAF", "OppA"),
            seat0_action=act0, seat1_action=act1,
        )
        dl = load(p)
        m = meta(dl)
        streams = _extract_streams(m["steps"])
        a = make_tape_agent(streams[0])
        b = make_tape_agent(streams[1])
        r = play(a, b, seed=m["seed"], record=False, metrics=False, strict=False,
                 steps=m["n_steps"])
        exact_0 = abs(float(r.rewards[0]) - float(m["rewards"][0])) < 1e-6
        exact_1 = abs(float(r.rewards[1]) - float(m["rewards"][1])) < 1e-6
        if not (exact_0 and exact_1):
            failures.append({
                "episode_id": m["episode_id"],
                "recorded": list(m["rewards"]),
                "replayed": list(r.rewards),
            })
    assert not failures, f"bit-exact failures: {failures}"


def test_extract_streams_alignment(synthetic_corpus):
    """stream[k] == steps[k+1][seat]["action"] — the documented alignment contract."""
    sub = synthetic_corpus["sub"]
    p = replay_paths(sub)[0]
    d = load(p)
    m = meta(d)
    steps = m["steps"]
    streams = _extract_streams(steps)
    for seat in (0, 1):
        for k in range(len(streams[seat])):
            expected = steps[k + 1][seat].get("action") or dict(PASS)
            assert streams[seat][k] == expected, (
                f"seat {seat} step {k}: stream != steps[k+1][seat]['action']")
