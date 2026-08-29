"""analysis/archive_sync.py — the collector automation (ROADMAP §3.2/§9/§11).

No real network/CLI calls: every test that would otherwise shell out to `kaggle`
monkeypatches `archive_sync._run_kaggle` with a fake that writes to disk the way the
real CLI would, so the file-management logic (gzip, dedupe, caching, selection) is
exercised without hitting Kaggle.
"""
from __future__ import annotations

import csv
import gzip
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from analysis import archive_sync as asy  # noqa: E402
from fixtures.replays import write_synthetic_replay  # noqa: E402


def _fake_completed(stdout="", returncode=0, stderr=""):
    return subprocess.CompletedProcess(args=[], returncode=returncode, stdout=stdout, stderr=stderr)


# --------------------------------------------------------------------------- env / auth

def test_env_from_dotenv_merges_without_shell_sourcing(tmp_path, monkeypatch):
    (tmp_path / ".env").write_text("KAGGLE_API_TOKEN=abc123\n# comment\nFOO=bar\n")
    monkeypatch.setattr(asy, "ROOT", tmp_path)
    env = asy._env_from_dotenv()
    assert env["KAGGLE_API_TOKEN"] == "abc123"
    assert env["FOO"] == "bar"


def test_run_kaggle_raises_without_token(tmp_path, monkeypatch):
    monkeypatch.setattr(asy, "ROOT", tmp_path)
    monkeypatch.setattr(asy, "KAGGLE_BIN", tmp_path / "fake_kaggle")
    (tmp_path / "fake_kaggle").write_text("#!/bin/sh\n")
    monkeypatch.delenv("KAGGLE_API_TOKEN", raising=False)
    with pytest.raises(SystemExit, match="KAGGLE_API_TOKEN"):
        asy._run_kaggle(["competitions", "list"])


# --------------------------------------------------------------------------- gzip

def test_gzip_replay_compresses_and_removes_original(tmp_path):
    p = tmp_path / "episode-1-replay.json"
    p.write_text(json.dumps({"a": 1}))
    gz = asy._gzip_replay(p)
    assert gz == tmp_path / "episode-1-replay.json.gz"
    assert gz.exists() and not p.exists()
    with gzip.open(gz, "rt") as fh:
        assert json.load(fh) == {"a": 1}


def test_gzip_replay_idempotent_when_already_gzipped(tmp_path):
    p = tmp_path / "episode-1-replay.json"
    p.write_text("{}")
    gz1 = asy._gzip_replay(p)
    # second call: json_path is already gone, must not raise
    gz2 = asy._gzip_replay(p)
    assert gz1 == gz2 and gz1.exists()


def test_sweep_ungzipped_cleans_up_interrupted_run(tmp_path):
    (tmp_path / "episode-1-replay.json").write_text("{}")
    (tmp_path / "episode-2-replay.json.gz").write_bytes(gzip.compress(b"{}"))
    n = asy._sweep_ungzipped(tmp_path)
    assert n == 1
    assert not (tmp_path / "episode-1-replay.json").exists()
    assert (tmp_path / "episode-1-replay.json.gz").exists()


def test_on_disk_ids_reads_both_formats(tmp_path):
    (tmp_path / "episode-1-replay.json").write_text("{}")
    (tmp_path / "episode-2-replay.json.gz").write_bytes(gzip.compress(b"{}"))
    assert asy._on_disk_ids(tmp_path) == {1, 2}


# --------------------------------------------------------------------------- active_submissions

def test_active_submissions_picks_latest_n_by_date(monkeypatch):
    csv_text = (
        "ref,fileName,date,description,status,publicScore,privateScore\n"
        '111,submission.tar.gz,2026-08-10 10:00:00,"old",SubmissionStatus.COMPLETE,100,\n'
        '333,submission.tar.gz,2026-08-25 10:00:00,"newest",SubmissionStatus.COMPLETE,300,\n'
        '222,submission.tar.gz,2026-08-20 10:00:00,"mid",SubmissionStatus.COMPLETE,200,\n'
    )
    monkeypatch.setattr(asy, "_run_kaggle", lambda args, **kw: _fake_completed(stdout=csv_text))
    assert asy.active_submissions(2) == ["333", "222"]


def test_active_submissions_raises_on_cli_failure(monkeypatch):
    monkeypatch.setattr(asy, "_run_kaggle", lambda args, **kw: _fake_completed(returncode=1, stderr="boom"))
    with pytest.raises(SystemExit, match="boom"):
        asy.active_submissions(2)


# --------------------------------------------------------------------------- ours

def test_download_missing_replays_skips_present_and_gzips_new(tmp_path, monkeypatch):
    monkeypatch.setattr(asy, "RAW", tmp_path)
    sub_dir = tmp_path / "live_SUB"
    sub_dir.mkdir()
    (sub_dir / "episode-1-replay.json.gz").write_bytes(gzip.compress(b"{}"))

    calls = []

    def fake_run(args, **kw):
        calls.append(args)
        eid = args[2]
        (sub_dir / f"episode-{eid}-replay.json").write_text(json.dumps({"info": {"EpisodeId": int(eid)}}))
        return _fake_completed()

    monkeypatch.setattr(asy, "_run_kaggle", fake_run)
    dl, fail = asy.download_missing_replays("SUB", [1, 2, 3], sleep=0)

    assert dl == 2 and fail == 0
    # id 1 was already on disk -> never fetched
    fetched_ids = {c[2] for c in calls}
    assert fetched_ids == {"2", "3"}
    assert (sub_dir / "episode-2-replay.json.gz").exists()
    assert not (sub_dir / "episode-2-replay.json").exists()


def test_download_missing_replays_records_failure_without_aborting(tmp_path, monkeypatch):
    monkeypatch.setattr(asy, "RAW", tmp_path)

    def fake_run(args, **kw):
        return _fake_completed(returncode=1, stderr="not found")

    monkeypatch.setattr(asy, "_run_kaggle", fake_run)
    dl, fail = asy.download_missing_replays("SUB", [1, 2], sleep=0)
    assert dl == 0 and fail == 2


def test_download_missing_replays_second_run_is_a_noop(tmp_path, monkeypatch):
    """Idempotent/resumable: a second call with the same wanted ids downloads nothing."""
    monkeypatch.setattr(asy, "RAW", tmp_path)
    sub_dir = tmp_path / "live_SUB"
    sub_dir.mkdir()

    def fake_run(args, **kw):
        eid = args[2]
        (sub_dir / f"episode-{eid}-replay.json").write_text("{}")
        return _fake_completed()

    monkeypatch.setattr(asy, "_run_kaggle", fake_run)
    asy.download_missing_replays("SUB", [1, 2], sleep=0)

    calls = []
    monkeypatch.setattr(asy, "_run_kaggle", lambda args, **kw: calls.append(args) or _fake_completed())
    dl, fail = asy.download_missing_replays("SUB", [1, 2], sleep=0)
    assert dl == 0 and fail == 0 and calls == []


def test_sync_episodes_csv_writes_expected_filename(tmp_path, monkeypatch):
    monkeypatch.setattr(asy, "RAW", tmp_path)
    monkeypatch.setattr(asy, "_run_kaggle", lambda args, **kw: _fake_completed(stdout="id,createTime\n1,2026-08-01\n"))
    out = asy.sync_episodes_csv("999")
    assert out == tmp_path / "live_999_episodes.csv"
    assert out.read_text() == "id,createTime\n1,2026-08-01\n"


def test_cmd_ours_reports_missing_and_downloads(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(asy, "RAW", tmp_path)
    ep_csv = (
        "id,createTime,endTime,state,type\n"
        "1,2026-08-01 00:00:00.000000,2026-08-01 00:01:00.000000,EpisodeState.COMPLETED,EpisodeType.EPISODE_TYPE_PUBLIC\n"
        "2,2026-08-02 00:00:00.000000,2026-08-02 00:01:00.000000,EpisodeState.COMPLETED,EpisodeType.EPISODE_TYPE_PUBLIC\n"
    )

    def fake_run(args, **kw):
        if args[:2] == ["competitions", "episodes"]:
            return _fake_completed(stdout=ep_csv)
        if args[:2] == ["competitions", "replay"]:
            eid = args[2]
            (tmp_path / "live_SUB" / f"episode-{eid}-replay.json").write_text("{}")
            return _fake_completed()
        raise AssertionError(f"unexpected kaggle call: {args}")

    (tmp_path / "live_SUB").mkdir()
    monkeypatch.setattr(asy, "_run_kaggle", fake_run)
    args = asy.argparse.Namespace(submissions=["SUB"], sleep=0, limit=None)
    rc = asy.cmd_ours(args)
    assert rc == 0
    out = capsys.readouterr().out
    assert "2 episodes listed, 0 on disk, 2 missing" in out
    assert asy._on_disk_ids(tmp_path / "live_SUB") == {1, 2}


def test_cmd_ours_exit_code_reflects_failures(tmp_path, monkeypatch):
    monkeypatch.setattr(asy, "RAW", tmp_path)
    ep_csv = (
        "id,createTime,endTime,state,type\n"
        "1,2026-08-01 00:00:00.000000,2026-08-01 00:01:00.000000,EpisodeState.COMPLETED,EpisodeType.EPISODE_TYPE_PUBLIC\n"
    )

    def fake_run(args, **kw):
        if args[:2] == ["competitions", "episodes"]:
            return _fake_completed(stdout=ep_csv)
        return _fake_completed(returncode=1, stderr="gone")

    monkeypatch.setattr(asy, "_run_kaggle", fake_run)
    args = asy.argparse.Namespace(submissions=["SUB"], sleep=0, limit=None)
    assert asy.cmd_ours(args) == 1


# --------------------------------------------------------------------------- board

def test_cmd_board_skips_existing_snapshot_without_force(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(asy, "RAW", tmp_path)
    out_dir = tmp_path / "live_leaderboard_2026-08-29"
    out_dir.mkdir()
    (out_dir / "board.csv").write_text("Rank,TeamName\n")

    monkeypatch.setattr(asy, "_run_kaggle", lambda *a, **k: (_ for _ in ()).throw(AssertionError("should not call")))
    args = asy.argparse.Namespace(date="2026-08-29", force=False)
    rc = asy.cmd_board(args)
    assert rc == 0
    assert "skipping" in capsys.readouterr().out


def test_cmd_board_unzips_the_download(tmp_path, monkeypatch):
    """`-d` downloads a kaggriculture.zip, not a bare CSV (verified live 2026-08-29) —
    a pre-fix cmd_board left the zip in place and reported 0 files."""
    import zipfile
    monkeypatch.setattr(asy, "RAW", tmp_path)

    def fake_run(args, **kw):
        out_dir = Path(args[args.index("-p") + 1])
        with zipfile.ZipFile(out_dir / "kaggriculture.zip", "w") as zf:
            zf.writestr("kaggriculture-publicleaderboard-2026-08-29T08:13:25.csv", "Rank,TeamName\n1,Foo\n")
        return _fake_completed()

    monkeypatch.setattr(asy, "_run_kaggle", fake_run)
    args = asy.argparse.Namespace(date="2026-08-29", force=False)
    rc = asy.cmd_board(args)
    assert rc == 0
    out_dir = tmp_path / "live_leaderboard_2026-08-29"
    assert not (out_dir / "kaggriculture.zip").exists()
    csvs = list(out_dir.glob("*.csv"))
    assert len(csvs) == 1
    assert csvs[0].read_text() == "Rank,TeamName\n1,Foo\n"


def test_cmd_board_force_refetches(tmp_path, monkeypatch):
    monkeypatch.setattr(asy, "RAW", tmp_path)
    out_dir = tmp_path / "live_leaderboard_2026-08-29"
    out_dir.mkdir()
    (out_dir / "board.csv").write_text("stale")

    def fake_run(args, **kw):
        (out_dir / "board2.csv").write_text("Rank,TeamName\n1,Foo\n")
        return _fake_completed()

    monkeypatch.setattr(asy, "_run_kaggle", fake_run)
    args = asy.argparse.Namespace(date="2026-08-29", force=True)
    rc = asy.cmd_board(args)
    assert rc == 0
    assert len(list(out_dir.glob("*.csv"))) == 2


# --------------------------------------------------------------------------- manifest

def test_build_manifest_indexes_seat_rows_and_hashes(tmp_path, monkeypatch):
    monkeypatch.setattr(asy, "RAW", tmp_path)
    monkeypatch.setattr(asy, "MANIFEST_PATH", tmp_path / "manifest.csv")
    sub_dir = tmp_path / "live_55726984"
    sub_dir.mkdir()
    write_synthetic_replay(sub_dir, 12345, teams=("STRAF", "OppX"), seed=1, gzip_it=True)

    rows = asy.build_manifest()
    assert len(rows) == 2
    ep = {r["seat"]: r for r in rows}
    assert ep["0"]["team"] == "STRAF" and ep["1"]["team"] == "OppX"
    assert ep["0"]["sha256"] == ep["1"]["sha256"]
    assert len(ep["0"]["sha256"]) == 64


def test_build_manifest_reuses_cache_for_unchanged_files(tmp_path, monkeypatch):
    monkeypatch.setattr(asy, "RAW", tmp_path)
    monkeypatch.setattr(asy, "MANIFEST_PATH", tmp_path / "manifest.csv")
    sub_dir = tmp_path / "live_55726984"
    sub_dir.mkdir()
    write_synthetic_replay(sub_dir, 12345, teams=("STRAF", "OppX"), seed=1, gzip_it=True)

    rows1 = asy.build_manifest()
    asy.write_manifest(rows1)

    calls = {"n": 0}
    real_load = asy.load

    def counting_load(p):
        calls["n"] += 1
        return real_load(p)

    monkeypatch.setattr(asy, "load", counting_load)
    rows2 = asy.build_manifest()
    assert rows2 == rows1
    assert calls["n"] == 0  # cached, file never reopened


def test_build_manifest_rehashes_when_file_changes(tmp_path, monkeypatch):
    monkeypatch.setattr(asy, "RAW", tmp_path)
    monkeypatch.setattr(asy, "MANIFEST_PATH", tmp_path / "manifest.csv")
    sub_dir = tmp_path / "live_55726984"
    sub_dir.mkdir()
    p = write_synthetic_replay(sub_dir, 12345, teams=("STRAF", "OppX"), seed=1, gzip_it=False)

    rows1 = asy.build_manifest()
    asy.write_manifest(rows1)

    write_synthetic_replay(sub_dir, 12345, teams=("STRAF", "OppY"), seed=2, gzip_it=False)
    import os
    os.utime(p, None)  # force a distinct mtime
    rows2 = asy.build_manifest()
    teams2 = {r["team"] for r in rows2}
    assert "OppY" in teams2


# --------------------------------------------------------------------------- top K N

def test_cmd_top_selects_by_team_and_reports_shortfall(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(asy, "RAW", tmp_path)
    monkeypatch.setattr(asy, "MANIFEST_PATH", tmp_path / "manifest.csv")
    sub_dir = tmp_path / "live_55726984"
    sub_dir.mkdir()
    write_synthetic_replay(sub_dir, 1001, teams=("STRAF", "TopTeam"), seed=1, gzip_it=True)
    write_synthetic_replay(sub_dir, 1002, teams=("STRAF", "TopTeam"), seed=2, gzip_it=True)

    board_dir = tmp_path / "live_leaderboard_2026-08-29"
    board_dir.mkdir()
    with open(board_dir / "board.csv", "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["Rank", "TeamId", "TeamName", "LastSubmissionDate", "Score", "SubmissionCount"])
        w.writerow([1, 1, "TopTeam", "2026-08-28 00:00:00", 3000.0, 5])
        w.writerow([2, 2, "SecondTeam", "2026-08-28 00:00:00", 2500.0, 5])

    args = asy.argparse.Namespace(k=2, n=3, no_sync=True, sleep=0, limit=None)
    rc = asy.cmd_top(args)
    assert rc == 0
    out = capsys.readouterr().out
    assert "TopTeam: 2/3 replays  [SHORT by 1" in out
    assert "SecondTeam: 0/3 replays  [SHORT by 3" in out

    manifest_json = json.loads((tmp_path / "top2_2026-08-29" / "manifest.json").read_text())
    assert len(manifest_json["selection"]["TopTeam"]) == 2
    assert manifest_json["selection"]["SecondTeam"] == []
