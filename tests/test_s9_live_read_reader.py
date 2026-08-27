"""S14 — the S9 live-read instrument must read gzipped replays.

`analysis/s9_live_read_55726984.py` used to glob `*.json` directly, which went blind
the moment the live archive was gzipped (`episode-*-replay.json.gz`): `load_live()`
raised `SystemExit("no replays")` on a directory full of episodes.  The fix routes it
through `analysis.s8_replay_io`, the single replay reader (ROADMAP §3, reuse rule).

Reddens on the pre-fix version: it globbed `*.json` and called `Path.read_text()`.
"""
from __future__ import annotations

import gzip
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from analysis import s9_live_read_55726984 as s9  # noqa: E402
from analysis import s8_replay_io  # noqa: E402


def _fake_replay(episode_id: int, seed: int) -> dict:
    """Two-step, two-seat replay with no orders — enough to exercise the reader."""
    def obs(player):
        return {
            "player": player,
            "day": 0,
            "step": 0,
            "farms": [{"money": 100.0 + 10 * p, "tiles": [[None]],
                       "unlocked_quadrants": ["NW"], "hands": []} for p in (0, 1)],
            "town": {"unlocked_shops": []},
        }
    step = [{"observation": obs(0), "action": []}, {"observation": obs(1), "action": []}]
    return {
        "info": {"EpisodeId": episode_id, "seed": seed, "TeamNames": ["STRAF", "OPPONENT"]},
        "rewards": [100.0, 90.0],
        "steps": [step, step],
        "configuration": {},
    }


def test_load_live_reads_gzipped_replays(tmp_path, monkeypatch):
    d = tmp_path / "live_55726984"
    d.mkdir()
    payload = _fake_replay(12345, 7)
    with gzip.open(d / "episode-12345-replay.json.gz", "wt") as fh:
        json.dump(payload, fh)

    monkeypatch.setitem(s8_replay_io.SUBMISSIONS, "55726984", d)
    monkeypatch.setattr(s9, "LIVE", d)

    eps, self_play, skipped = s9.load_live()

    assert [e["episode_id"] for e in eps] == [12345]
    assert (self_play, skipped) == (0, 0)
    assert eps[0]["seat"] == 0 and eps[0]["win"] is True


def test_plain_json_replays_still_read(tmp_path, monkeypatch):
    """The gz fix must not drop support for uncompressed replays."""
    d = tmp_path / "live_55726984"
    d.mkdir()
    (d / "episode-999-replay.json").write_text(json.dumps(_fake_replay(999, 3)))

    monkeypatch.setitem(s8_replay_io.SUBMISSIONS, "55726984", d)
    monkeypatch.setattr(s9, "LIVE", d)

    eps, _self_play, _skipped = s9.load_live()
    assert [e["episode_id"] for e in eps] == [999]


def test_episode_times_ignores_the_cli_trailer(tmp_path, monkeypatch):
    """`kaggle competitions episodes -v` appends a hint line to its own CSV.

    DictReader renders it as a row whose `type` is None; the pre-fix parser did
    `"PUBLIC" not in row.get("type", "")` and raised TypeError on it.
    """
    csv_path = tmp_path / "eps.csv"
    csv_path.write_text(
        "id,createTime,endTime,state,type\n"
        "101131483,2026-08-27 19:58:31.674000,2026-08-27 20:00:33.736000,"
        "EpisodeState.COMPLETED,EpisodeType.EPISODE_TYPE_PUBLIC\n"
        "97977511,2026-08-23 23:07:25.524000,2026-08-23 23:11:44.104000,"
        "EpisodeState.COMPLETED,EpisodeType.EPISODE_TYPE_VALIDATION\n"
        "\n"
        'Use "kaggle competitions replay <episode_id>" to download a replay.\n'
    )
    monkeypatch.setattr(s9, "EP_CSV", csv_path)

    times = s9.load_episode_times()

    assert list(times) == [101131483]  # validation dropped, trailer ignored
