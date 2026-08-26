"""Shared test fixtures — session-scoped synthetic replay corpus for CI.

The `synthetic_corpus` fixture generates 4 engine episodes in a temp directory and
patches `s8_replay_io.SUBMISSIONS` + `_EXTRA_DIRS` so every downstream consumer
(ledger, metrics, bench) can run against real data without the 14 GB gitignored
live corpus.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

PASS = {"farmer": ["PASS"], "hands": [], "market": []}
_SELL_MELON = lambda _i: {"farmer": ["PASS"], "hands": [], "market": [["SELL", "MELON", 5]]}
_SELL_WHEAT = lambda _i: {"farmer": ["PASS"], "hands": [], "market": [["SELL", "WHEAT", 2]]}


@pytest.fixture(scope="session")
def synthetic_corpus(tmp_path_factory):
    """Build 4 synthetic replays and patch s8_replay_io to read them.

    Returns a dict with:
      - "sub": the submission key
      - "dir": the directory containing the replays
      - "episodes": list of (episode_id, seed) tuples
    """
    from fixtures.replays import write_synthetic_replay

    sub_key = "SYNTH"
    d = tmp_path_factory.mktemp("synthetic_corpus")
    sub_dir = d / f"live_{sub_key}"
    sub_dir.mkdir()

    episodes = [
        # ep 1: seat 0 sells MELON (plain json)
        (100001, 42, {"MELON": 80}, _SELL_MELON, None, False),
        # ep 2: seat 0 sells WHEAT (gzipped)
        (100002, 43, {"WHEAT": 60}, _SELL_WHEAT, None, True),
        # ep 3: both sides sell (gzipped)
        (100003, 44, {"MELON": 50, "WHEAT": 30}, _SELL_MELON, _SELL_WHEAT, True),
        # ep 4: MELON seller (gzipped)
        (100004, 45, {"MELON": 100}, _SELL_MELON, None, True),
    ]

    written = []
    for eid, seed, preload, act0, act1, gz in episodes:
        write_synthetic_replay(
            sub_dir, eid, seed=seed, episode_steps=60,
            teams=("STRAF", "OppA"),
            seat0_action=act0, seat1_action=act1,
            shed_preload=preload, gzip_it=gz,
        )
        written.append((eid, seed))

    from analysis import s8_replay_io
    _orig_subs = dict(s8_replay_io.SUBMISSIONS)
    _orig_extra = dict(s8_replay_io._EXTRA_DIRS)

    s8_replay_io.SUBMISSIONS[sub_key] = sub_dir
    s8_replay_io._EXTRA_DIRS[sub_key] = []

    yield {"sub": sub_key, "dir": sub_dir, "episodes": written}

    s8_replay_io.SUBMISSIONS.clear()
    s8_replay_io.SUBMISSIONS.update(_orig_subs)
    s8_replay_io._EXTRA_DIRS.clear()
    s8_replay_io._EXTRA_DIRS.update(_orig_extra)
