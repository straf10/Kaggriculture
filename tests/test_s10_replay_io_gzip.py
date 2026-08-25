"""S10 P0.6 — replay_paths / load must accept .json.gz.

Fixture: a tmp submission dir with three synthetic replays. Gzip one, leave two plain,
and check that `replay_paths` yields exactly the three episode ids, `load` parses each,
and `ladder_episodes` filters mirror/validation the same way for both encodings.

If `load` or `replay_paths` regresses on `.json.gz`, this test fails — and the on-disk
raw dirs (data/archive/raw/live_55*, 14+GB) which are gzipped in P0.6 (γ) stop being
readable.
"""
from __future__ import annotations

import gzip
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from analysis import s8_replay_io  # noqa: E402


def _replay_blob(eid: int, teams=("STRAF", "OppA"), seed=42):
    return {
        "info": {"EpisodeId": eid, "TeamNames": list(teams), "seed": seed},
        "rewards": [3500.0, 3500.0],
        "steps": [[{}, {}]],
        "configuration": {},
    }


def test_replay_paths_and_load_read_gzipped_replays(tmp_path, monkeypatch):
    sub = "TEST"
    d = tmp_path / f"live_{sub}"
    d.mkdir()

    # 3 replays: eid 1 plain, eid 2 gzipped, eid 3 gzipped.
    for eid in (1, 2, 3):
        blob = _replay_blob(eid)
        target = d / f"episode-{eid}-replay.json"
        if eid == 1:
            target.write_text(json.dumps(blob))
        else:
            with gzip.open(str(target) + ".gz", "wt") as f:
                json.dump(blob, f)

    monkeypatch.setitem(s8_replay_io.SUBMISSIONS, sub, d)
    monkeypatch.setattr(s8_replay_io, "_EXTRA_DIRS", {})

    paths = s8_replay_io.replay_paths(sub)
    assert [s8_replay_io._eid_from_name(p) for p in paths] == [1, 2, 3]
    assert paths[0].suffix == ".json" and paths[1].suffix == ".gz" and paths[2].suffix == ".gz"

    for p in paths:
        d_ = s8_replay_io.load(p)
        assert d_["info"]["EpisodeId"] in (1, 2, 3)

    eps = list(s8_replay_io.ladder_episodes(sub))
    assert [e for e, _ in eps] == [1, 2, 3]


def test_replay_paths_dedupes_when_same_eid_in_gz_and_plain(tmp_path, monkeypatch):
    """If the same episode is present as both .json and .json.gz, only one path is yielded."""
    sub = "TEST"
    d = tmp_path / f"live_{sub}"
    d.mkdir()
    blob = _replay_blob(7)
    (d / "episode-7-replay.json").write_text(json.dumps(blob))
    with gzip.open(str(d / "episode-7-replay.json.gz"), "wt") as f:
        json.dump(blob, f)

    monkeypatch.setitem(s8_replay_io.SUBMISSIONS, sub, d)
    monkeypatch.setattr(s8_replay_io, "_EXTRA_DIRS", {})

    paths = s8_replay_io.replay_paths(sub)
    assert len(paths) == 1
