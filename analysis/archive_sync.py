#!/usr/bin/env python3
"""Automated collection for the live-episode archive (ROADMAP §3.2 / §9 / §11).

Every download used to be by hand: `kaggle competitions episodes/replay/leaderboard`,
auth from the gitignored `.env`, CLI in `.venv/`. That is fine for one pass but loses
ground the moment nobody remembers to run it — this script is the same three CLI verbs,
scripted, gzip'd, idempotent.

Subcommands:
    ours       for each active submission, sync `episodes -v` and download only the
               replays we don't already have on disk.
    board      leaderboard snapshot into data/archive/raw/live_leaderboard_<date>/.
    top K N    up to N replays for each of the top-K teams on the current board,
               drawn from replays already on disk (see the docstring on cmd_top for
               why this does not fetch arbitrary teams' games directly).
    manifest   provenance (episode_id, seat, team, sha256) for every replay on disk,
               required by §3.2. Incrementally cached by (path, mtime, size) so a
               22 GB archive isn't re-hashed every run.

All reading/parsing of replay files goes through `analysis/s8_replay_io` — one reader,
reused (ROADMAP §3). This module only drives the `kaggle` CLI and manages files on disk.

Usage:
    python analysis/archive_sync.py ours
    python analysis/archive_sync.py board
    python analysis/archive_sync.py top 5 10
    python analysis/archive_sync.py manifest
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import gzip
import io
import json
import os
import subprocess
import sys
import time
import zipfile
from collections import defaultdict
from hashlib import sha256
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from analysis.s8_replay_io import _eid_from_name, load, meta, parse_episodes_csv  # noqa: E402

RAW = ROOT / "data" / "archive" / "raw"
MANIFEST_PATH = ROOT / "data" / "archive" / "manifest.csv"
KAGGLE_BIN = ROOT / ".venv" / "bin" / "kaggle"
COMPETITION = "kaggriculture"
OUR_TEAM = "STRAF"


# --------------------------------------------------------------------------- kaggle CLI

def _env_from_dotenv() -> dict:
    """Merge `.env`'s KEY=VALUE lines into os.environ.

    Reading the file directly (rather than requiring `source .env` first) is what makes
    this runnable non-interactively from launchd, which starts with none of the user's
    shell profile.
    """
    env = dict(os.environ)
    dotenv = ROOT / ".env"
    if dotenv.exists():
        for line in dotenv.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            env[k.strip()] = v.strip()
    return env


def _run_kaggle(args: list[str], **kw) -> subprocess.CompletedProcess:
    if not KAGGLE_BIN.exists():
        raise SystemExit(f"kaggle CLI not found at {KAGGLE_BIN} — is .venv set up?")
    env = _env_from_dotenv()
    if "KAGGLE_API_TOKEN" not in env:
        raise SystemExit("KAGGLE_API_TOKEN not set — check .env")
    return subprocess.run([str(KAGGLE_BIN), *args], env=env, capture_output=True, text=True, **kw)


def active_submissions(n: int = 2) -> list[str]:
    """The `n` most recent submission refs (ROADMAP §9 slot policy: latest `n` active).

    `kaggle competitions submissions <comp> -v` already lists newest-first; sorted by
    the `date` column defensively rather than trusted blindly.
    """
    r = _run_kaggle(["competitions", "submissions", COMPETITION, "-v"])
    if r.returncode != 0:
        raise SystemExit(f"kaggle competitions submissions failed: {r.stderr.strip()}")
    rows = list(csv.DictReader(io.StringIO(r.stdout)))
    rows = [row for row in rows if (row.get("ref") or "").strip().isdigit()]
    rows.sort(key=lambda row: row.get("date") or "", reverse=True)
    return [row["ref"] for row in rows[:n]]


# --------------------------------------------------------------------------- gzip

def _gzip_replay(json_path: Path) -> Path:
    """Compress a freshly-downloaded replay in place (~31 MB -> ~1.3 MB) and drop the
    original. Idempotent: a no-op if the .gz already exists and json_path is gone."""
    gz_path = json_path.with_suffix(json_path.suffix + ".gz")
    if json_path.exists():
        with open(json_path, "rb") as src, gzip.open(gz_path, "wb", compresslevel=6) as dst:
            dst.write(src.read())
        json_path.unlink()
    return gz_path


def _sweep_ungzipped(dir_: Path) -> int:
    """Gzip any `episode-*-replay.json` left un-gzipped by an interrupted prior run.
    Makes `ours` resumable without re-downloading anything."""
    n = 0
    for p in dir_.glob("episode-*-replay.json"):
        _gzip_replay(p)
        n += 1
    return n


def _on_disk_ids(dir_: Path) -> set[int]:
    ids = set()
    for pat in ("episode-*-replay.json", "episode-*-replay.json.gz"):
        for p in dir_.glob(pat):
            ids.add(_eid_from_name(p))
    return ids


# --------------------------------------------------------------------------- ours

def sync_episodes_csv(sub: str) -> Path:
    """Run `episodes -v` for `sub` and write it to data/archive/raw/live_<sub>_episodes.csv
    (same naming as the hand-downloaded ones already on disk, e.g. live_55675634_episodes.csv)."""
    r = _run_kaggle(["competitions", "episodes", sub, "-v"])
    if r.returncode != 0:
        raise SystemExit(f"kaggle competitions episodes {sub} failed: {r.stderr.strip()}")
    out = RAW / f"live_{sub}_episodes.csv"
    out.write_text(r.stdout)
    return out


def download_missing_replays(sub: str, ids: list[int], *, sleep: float = 0.3,
                              limit: int | None = None) -> tuple[int, int]:
    dir_ = RAW / f"live_{sub}"
    dir_.mkdir(parents=True, exist_ok=True)
    _sweep_ungzipped(dir_)
    have = _on_disk_ids(dir_)
    todo = [i for i in ids if i not in have]
    if limit is not None:
        todo = todo[:limit]
    downloaded = failed = 0
    for i, eid in enumerate(todo):
        r = _run_kaggle(["competitions", "replay", str(eid), "-p", str(dir_), "-q"])
        candidate = dir_ / f"episode-{eid}-replay.json"
        if r.returncode == 0 and candidate.exists():
            _gzip_replay(candidate)
            downloaded += 1
        else:
            failed += 1
            print(f"  episode {eid}: download failed ({r.stderr.strip() or 'no file produced'})")
        if sleep and i < len(todo) - 1:
            time.sleep(sleep)
    return downloaded, failed


def cmd_ours(args) -> int:
    subs = args.submissions or active_submissions(2)
    print(f"active submissions: {subs}")
    total_dl = total_fail = 0
    for sub in subs:
        csv_path = sync_episodes_csv(sub)
        rows = parse_episodes_csv(csv_path)
        ids = sorted(rows)
        dir_ = RAW / f"live_{sub}"
        dir_.mkdir(parents=True, exist_ok=True)
        have = _on_disk_ids(dir_)
        missing = [i for i in ids if i not in have]
        print(f"{sub}: {len(ids)} episodes listed, {len(have)} on disk, {len(missing)} missing")
        dl, fail = download_missing_replays(sub, ids, sleep=args.sleep, limit=args.limit)
        total_dl += dl
        total_fail += fail
        print(f"{sub}: downloaded {dl}, failed {fail}")
    print(f"total: downloaded {total_dl}, failed {total_fail}")
    return 1 if total_fail else 0


# --------------------------------------------------------------------------- board

def cmd_board(args) -> int:
    date = args.date or dt.date.today().isoformat()
    out_dir = RAW / f"live_leaderboard_{date}"
    if out_dir.exists() and list(out_dir.glob("*.csv")) and not args.force:
        print(f"{out_dir} already has a snapshot, skipping (use --force to re-fetch)")
        return 0
    out_dir.mkdir(parents=True, exist_ok=True)
    r = _run_kaggle(["competitions", "leaderboard", COMPETITION, "-d", "-p", str(out_dir)])
    if r.returncode != 0:
        raise SystemExit(f"kaggle competitions leaderboard failed: {r.stderr.strip()}")
    # `-d` downloads a zip, not a bare CSV (verified live 2026-08-29) — unzip it so the
    # dir matches the existing hand-downloaded snapshots (plain
    # kaggriculture-publicleaderboard-<ts>.csv), then drop the zip.
    for zpath in out_dir.glob("*.zip"):
        with zipfile.ZipFile(zpath) as zf:
            zf.extractall(out_dir)
        zpath.unlink()
    got = list(out_dir.glob("*.csv"))
    print(f"leaderboard snapshot -> {out_dir} ({len(got)} file(s))")
    return 0 if got else 1


def _latest_board_csv() -> Path | None:
    cands = sorted(RAW.glob("live_leaderboard_*/*.csv"))
    return cands[-1] if cands else None


def load_leaderboard(path: Path) -> list[dict]:
    with open(path, newline="", encoding="utf-8-sig") as fh:
        rows = list(csv.DictReader(fh))
    rows.sort(key=lambda row: int(row["Rank"]))
    return rows


# --------------------------------------------------------------------------- manifest

def _raw_bytes(path: Path) -> bytes:
    if path.name.endswith(".gz"):
        with gzip.open(path, "rb") as fh:
            return fh.read()
    return path.read_bytes()


def _replay_pool() -> list[Path]:
    """Every replay file anywhere under data/archive/raw/ — not just the three
    hardcoded `live_<sub>` dirs in s8_replay_io.SUBMISSIONS, so this also indexes the
    older dated pulls (2026-08-14/16/21) and any `top` selections."""
    pool: dict[str, Path] = {}
    for pat in ("**/episode-*-replay.json", "**/episode-*-replay.json.gz",
                "**/[0-9]*.json", "**/[0-9]*.json.gz"):
        for p in RAW.glob(pat):
            pool[str(p)] = p
    return sorted(pool.values())


def build_manifest(force: bool = False) -> list[dict]:
    """(Re)build the provenance index (§3.2: episode_id, seat, team, sha256), one row
    per (episode, seat). Cached by (path, mtime, size) — unchanged files are not
    re-opened or re-hashed, so a 22 GB archive stays cheap to re-index after the
    first pass."""
    cache: dict[tuple, list[dict]] = defaultdict(list)
    if MANIFEST_PATH.exists() and not force:
        with open(MANIFEST_PATH, newline="") as fh:
            for row in csv.DictReader(fh):
                cache[(row["path"], row["mtime"], row["size"])].append(row)

    rows: list[dict] = []
    for p in _replay_pool():
        st = p.stat()
        key = (str(p), str(st.st_mtime), str(st.st_size))
        if key in cache:
            rows.extend(cache[key])
            continue
        try:
            raw = _raw_bytes(p)
            d = load(p)
        except Exception as e:  # noqa: BLE001 — a corrupt/partial download must not kill the run
            print(f"  skipping unreadable {p}: {e}")
            continue
        digest = sha256(raw).hexdigest()
        m = meta(d)
        source = p.parent.name
        for seat, team in enumerate(m["teams"]):
            rows.append({
                "episode_id": str(m["episode_id"]),
                "seat": str(seat),
                "team": team or "",
                "sha256": digest,
                "source": source,
                "path": str(p),
                "mtime": str(st.st_mtime),
                "size": str(st.st_size),
            })
    rows.sort(key=lambda r: (r["episode_id"], r["seat"]))
    return rows


def write_manifest(rows: list[dict]) -> None:
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    fields = ["episode_id", "seat", "team", "sha256", "source", "path", "mtime", "size"]
    with open(MANIFEST_PATH, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def cmd_manifest(args) -> int:
    rows = build_manifest(force=args.force)
    write_manifest(rows)
    n_episodes = len({r["episode_id"] for r in rows})
    print(f"manifest: {n_episodes} episodes, {len(rows)} seat-rows -> {MANIFEST_PATH}")
    return 0


# --------------------------------------------------------------------------- top K N

def cmd_top(args) -> int:
    """N replays for each of the top-K teams on the current board.

    This does NOT fetch an arbitrary team's episodes directly — the Kaggle episodes
    API is keyed by submission_id, and we only have our own. Per ROADMAP §11 ("the
    untracked collector chain... does not need rebuilding"), every input comes from
    `kaggle competitions replay/episodes/leaderboard` — all submission-scoped. So the
    only honest source of "N games of team X" is games where X played against one of
    OUR submissions, which our own archive already accumulates. This command (a)
    optionally syncs `ours` first to maximise that pool, (b) refreshes the manifest
    (cheap, cached), (c) selects up to N episodes per top-K team from it. A shortfall
    is reported, not silently padded.
    """
    if not args.no_sync:
        cmd_ours(argparse.Namespace(submissions=None, sleep=args.sleep, limit=args.limit))
    board_csv = _latest_board_csv()
    if board_csv is None:
        raise SystemExit("no leaderboard snapshot on disk — run `board` first")
    board = load_leaderboard(board_csv)
    top_teams = [row["TeamName"] for row in board if row["TeamName"] != OUR_TEAM][: args.k]
    print(f"top-{args.k} teams ({board_csv.name}): {top_teams}")

    rows = build_manifest(force=False)
    write_manifest(rows)
    by_team: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        by_team[row["team"]].append(row)

    date = dt.date.today().isoformat()
    out_dir = RAW / f"top{args.k}_{date}"
    out_dir.mkdir(parents=True, exist_ok=True)
    selection: dict[str, list[dict]] = {}
    for team in top_teams:
        cands = sorted(by_team.get(team, []), key=lambda r: -int(r["episode_id"]))
        picked = cands[: args.n]
        selection[team] = [{"episode_id": int(r["episode_id"]), "seat": int(r["seat"]),
                            "path": r["path"], "sha256": r["sha256"]} for r in picked]
        shortfall = args.n - len(picked)
        status = "OK" if shortfall <= 0 else f"SHORT by {shortfall} — no more official source"
        print(f"  {team}: {len(picked)}/{args.n} replays  [{status}]")

    manifest_out = out_dir / "manifest.json"
    manifest_out.write_text(json.dumps({
        "date": date, "k": args.k, "n": args.n, "board": board_csv.name,
        "selection": selection,
    }, indent=2, sort_keys=True))
    print(f"selection manifest -> {manifest_out}")
    return 0


# --------------------------------------------------------------------------- main

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_ours = sub.add_parser("ours", help="sync episodes + download missing replays for active submissions")
    p_ours.add_argument("--submissions", nargs="+", default=None,
                        help="explicit submission ids instead of auto-detecting the latest 2")
    p_ours.add_argument("--sleep", type=float, default=0.3, help="seconds between replay downloads")
    p_ours.add_argument("--limit", type=int, default=None, help="cap replays downloaded per submission")
    p_ours.set_defaults(func=cmd_ours)

    p_board = sub.add_parser("board", help="leaderboard snapshot")
    p_board.add_argument("--date", default=None, help="override YYYY-MM-DD (default: today)")
    p_board.add_argument("--force", action="store_true", help="re-fetch even if today's snapshot exists")
    p_board.set_defaults(func=cmd_board)

    p_top = sub.add_parser("top", help="N replays for each of the top-K teams")
    p_top.add_argument("k", type=int)
    p_top.add_argument("n", type=int)
    p_top.add_argument("--no-sync", action="store_true", help="skip the pre-sync `ours` step")
    p_top.add_argument("--sleep", type=float, default=0.3)
    p_top.add_argument("--limit", type=int, default=None)
    p_top.set_defaults(func=cmd_top)

    p_manifest = sub.add_parser("manifest", help="rebuild the provenance index")
    p_manifest.add_argument("--force", action="store_true", help="ignore the cache, re-hash everything")
    p_manifest.set_defaults(func=cmd_manifest)

    args = ap.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
