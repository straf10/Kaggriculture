#!/usr/bin/env python3
"""v1s — build the herd-13 race arms (ROADMAP §4.3 S3 step 2, prompt.md §3).

Every arm is the CURRENT (cleaned) agent codebase plus config-source-text overrides, all carrying
C2 on (`executor.feed_reserve_horizon="target"`) — the prerequisite, not a variable (§3.2). The
overrides are applied as exact source-text replacements on the live `agent/config.py`, then the
built config is re-loaded and its effective values asserted (R19: never trust a source edit, a
dict with a duplicate key does not raise).

    Arm B0  — C2 alone at herd 10   targets {4C,6S}   ramp None
    Arm H1  — count only            targets {4C,9S}   ramp None
    Arm H2  — the §4.0 profile      targets {9C,4S}   ramp None
    Arm H2R — profile on the ramp   targets {9C,4S}   ramp [[5,6],[10,12]]

Usage:
    .venv/bin/python analysis/v1s_build_arms.py                       # cut checkpoints/v1s_*
    .venv/bin/python analysis/v1s_build_arms.py --tmp /path --arm B0  # temp package (inert proof)
"""
import argparse
import hashlib
import importlib.util
import json
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
AGENT = REPO / "agent"
sys.path.insert(0, str(REPO))

from harness.checkpoint import _hash_package  # noqa: E402

# --- config-source anchors on the CURRENT agent/config.py -------------------------------------
C2_FLIP = (
    '        "feed_reserve_horizon": "in_flight",  # "in_flight" | "target"',
    '        "feed_reserve_horizon": "target",  # "in_flight" | "target"',
)
TARGETS_ANCHOR = '        "targets": {"COW": 4, "SHEEP": 6, "GOOSE": 0},'
RAMP_ANCHOR = '        "ramp": None,'


def _targets(cow, sheep):
    return (TARGETS_ANCHOR,
            f'        "targets": {{"COW": {cow}, "SHEEP": {sheep}, "GOOSE": 0}},')


def _ramp(rungs):
    return (RAMP_ANCHOR, f'        "ramp": {rungs},')


# arm -> (list of (old, new) source edits, expected effective {dotted_key: value})
ARMS = {
    "B0": ([C2_FLIP],
           {"executor.feed_reserve_horizon": "target",
            "animals.targets": {"COW": 4, "SHEEP": 6, "GOOSE": 0},
            "animals.ramp": None}),
    "H1": ([C2_FLIP, _targets(4, 9)],
           {"executor.feed_reserve_horizon": "target",
            "animals.targets": {"COW": 4, "SHEEP": 9, "GOOSE": 0},
            "animals.ramp": None}),
    "H2": ([C2_FLIP, _targets(9, 4)],
           {"executor.feed_reserve_horizon": "target",
            "animals.targets": {"COW": 9, "SHEEP": 4, "GOOSE": 0},
            "animals.ramp": None}),
    "H2R": ([C2_FLIP, _targets(9, 4), _ramp([[5, 6], [10, 12]])],
            {"executor.feed_reserve_horizon": "target",
             "animals.targets": {"COW": 9, "SHEEP": 4, "GOOSE": 0},
             "animals.ramp": [[5, 6], [10, 12]]}),
}


def apply(src, pair):
    old, new = pair
    if old not in src:
        raise SystemExit(f"anchor not found:\n{old!r}")
    if src.count(old) != 1:
        raise SystemExit(f"anchor not unique ({src.count(old)}x):\n{old!r}")
    return src.replace(old, new)


def load_config(source_text, tag):
    mod_path = Path(f"/tmp/_v1scfg_{tag}.py")
    mod_path.write_text(source_text, encoding="utf-8")
    spec = importlib.util.spec_from_file_location(f"_v1scfg_{tag}", mod_path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m.CONFIG


def _dig(cfg, dotted):
    node = cfg
    for part in dotted.split("."):
        node = node[part]
    return node


def build(arm, dest_root, *, as_checkpoint):
    edits, expected = ARMS[arm]
    version = f"v1s_{arm}"
    pkg = f"agent_checkpoint_{version}"
    src = (AGENT / "config.py").read_text(encoding="utf-8")
    for pair in edits:
        src = apply(src, pair)
    # R19: re-load the built config and assert every intended value actually took effect.
    built = load_config(src, arm)
    for dotted, want in expected.items():
        got = _dig(built, dotted)
        if got != want:
            raise SystemExit(f"{arm}: {dotted} did not take effect (got {got!r}, want {want!r})")

    dest = dest_root / version
    if dest.exists():
        if as_checkpoint:
            raise SystemExit(f"checkpoint already exists: {dest} (immutable — refusing to overwrite)")
        shutil.rmtree(dest)
    shutil.copytree(AGENT, dest / pkg, ignore=shutil.ignore_patterns("__pycache__"))
    (dest / pkg / "config.py").write_text(src, encoding="utf-8")
    (dest / "main.py").write_text(
        '"""Generated local benchmark checkpoint; not a submission entrypoint."""\n'
        f"from {pkg}.policy import agent\n",
        encoding="utf-8",
    )
    fingerprint = _hash_package(dest / pkg)
    if as_checkpoint:
        (dest / "manifest.json").write_text(
            json.dumps({"fingerprint": fingerprint, "package": pkg, "version": version},
                       indent=2, sort_keys=True),
            encoding="utf-8",
        )
    print(f"built {version}: {dest/'main.py'}  fingerprint {fingerprint[:16]}…  "
          f"[{'checkpoint' if as_checkpoint else 'temp'}]  effective={ {k: _dig(built,k) for k in expected} }")
    return dest / "main.py", fingerprint


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--tmp", help="build to this dir as temp packages (no manifest)")
    parser.add_argument("--arm", action="append", help="restrict to these arms")
    args = parser.parse_args()
    arms = args.arm or list(ARMS)
    dest_root = Path(args.tmp) if args.tmp else (REPO / "checkpoints")
    dest_root.mkdir(parents=True, exist_ok=True)
    index = {}
    for arm in arms:
        main_path, fp = build(arm, dest_root, as_checkpoint=args.tmp is None)
        index[arm] = {"main": str(main_path), "fingerprint": fp}
    if args.tmp:
        (dest_root / "index.json").write_text(json.dumps(index, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
