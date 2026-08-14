#!/usr/bin/env python3
"""v1r — build the A1-stacked diagnostic packages (ROADMAP §4.3 S3 step 1e, prompt.md §3.3).

"A1-stacked" = the CURRENT (fixed) codebase + arm-A1's three config DELTAS + one feed-reserve
flag. Per the brief this is "the arm's flag on top of checkpoints/v1p1b_armA1's *config*" — arm
A1's escape-producing geometry (the thing that spreads day-0 animal purchases across turns), run
on today's code, NOT arm A1's old v1p1b planner/scheduler. These packages are diagnostic
reproducers, not shippable candidates, so they are built under a temp root and get no
`checkpoints/` version (R16). The three arm-A1 config deltas are applied as exact source-text
edits and then re-validated dict-for-dict against the real arm-A1 config package.

Usage:
    .venv/bin/python analysis/v1r_build_stacked.py --out /tmp/.../stacked
"""
import argparse
import importlib.util
import json
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
AGENT = REPO / "agent"
ARMA1_CFG = REPO / "checkpoints/v1p1b_armA1/agent_checkpoint_v1p1b_armA1/config.py"

# --- arm-A1's three config deltas, as exact source-text replacements on the live config.py ---
CARROT_TILES = ('        "carrot_tiles": 3,', '        "carrot_tiles": 1,')
PASTURE = (
    '            "PASTURE": (\n'
    "                # COW block (4): distances 2,2,2,3 from the (4,4) shed spawn.\n"
    "                (4, 2), (3, 3), (2, 4), (3, 2),",
    '            "PASTURE": (\n'
    "                # v1r A1-stacked delta: (3,4),(4,3) reassigned CARROT->PASTURE (arm A1).\n"
    "                (3, 4), (4, 3),\n"
    "                # COW block (4): distances 2,2,2,3 from the (4,4) shed spawn.\n"
    "                (4, 2), (3, 3), (2, 4), (3, 2),",
)
CARROT_TARGET = (
    '            "CARROT": (\n                (4, 4), (3, 4), (4, 3),',
    '            "CARROT": (\n                (4, 4),  # v1r A1-stacked delta: (3,4),(4,3) removed (arm A1).',
)

# Turn an arm on by REPLACING the existing default key line (live config.py already defines all
# three feed_reserve_* keys). Inserting a second key before it is a silent no-op: the later
# literal wins in the dict. Each entry is (old_line, new_line); a1_repro leaves them all default.
ARM_FLAGS = {
    "a1_repro": None,  # arm-A1 config, all flags default => confirms current code reproduces
    "c1_a1": ('        "feed_reserve_counts_in_flight": False,',
              '        "feed_reserve_counts_in_flight": True,'),
    "c2_a1": ('        "feed_reserve_horizon": "in_flight",  # "in_flight" | "target"',
              '        "feed_reserve_horizon": "target",  # "in_flight" | "target"'),
    "x_a1": ('        "feed_reserve_days": 2,',
             '        "feed_reserve_days": 3,'),
}


def apply(src, pair):
    old, new = pair
    if old not in src:
        raise SystemExit(f"anchor not found:\n{old!r}")
    if src.count(old) != 1:
        raise SystemExit(f"anchor not unique ({src.count(old)}x):\n{old!r}")
    return src.replace(old, new)


def armA1_config_source():
    src = (AGENT / "config.py").read_text(encoding="utf-8")
    for pair in (CARROT_TILES, PASTURE, CARROT_TARGET):
        src = apply(src, pair)
    return src


def load_config(source_text, tag):
    mod_path = Path(f"/tmp/_v1rcfg_{tag}.py")
    mod_path.write_text(source_text, encoding="utf-8")
    spec = importlib.util.spec_from_file_location(f"_v1rcfg_{tag}", mod_path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m.CONFIG


def validate(base_a1_src):
    """The three deltas must reproduce arm-A1's real config exactly on those three keys."""
    built = load_config(base_a1_src, "built")
    real = load_config(ARMA1_CFG.read_text(encoding="utf-8"), "real")
    checks = {
        "planner.carrot_tiles": (built["planner"]["carrot_tiles"], real["planner"]["carrot_tiles"]),
        "PASTURE": (built["scheduler"]["animal_structure_tiles"]["PASTURE"],
                    real["scheduler"]["animal_structure_tiles"]["PASTURE"]),
        "CARROT_target": (built["scheduler"]["target_tiles"]["CARROT"],
                          real["scheduler"]["target_tiles"]["CARROT"]),
    }
    for key, (b, r) in checks.items():
        if b != r:
            raise SystemExit(f"delta MISMATCH on {key}:\n built={b}\n real ={r}")
    print("delta validation PASS — built A1 config matches checkpoints/v1p1b_armA1 on all 3 keys")


def build_package(dest_root, arm, base_a1_src):
    pkg = f"agent_checkpoint_v1r_{arm}"
    src = base_a1_src
    flag = ARM_FLAGS[arm]
    if flag is not None:
        src = apply(src, flag)
    # Guard against the duplicate-key trap: live config.py already defines all three
    # feed_reserve_* keys, so the arm value must REPLACE the existing line, not be inserted
    # before it (the later literal wins in the dict). Assert the built config's effective value.
    expected = {
        "a1_repro": ("feed_reserve_counts_in_flight", False),
        "c1_a1": ("feed_reserve_counts_in_flight", True),
        "c2_a1": ("feed_reserve_horizon", "target"),
        "x_a1": ("feed_reserve_days", 3),
    }[arm]
    built = load_config(src, f"eff_{arm}")["executor"]
    if built[expected[0]] != expected[1]:
        raise SystemExit(f"{arm}: flag {expected[0]} did not take effect "
                         f"(got {built[expected[0]]!r}, want {expected[1]!r})")
    dest = dest_root / arm
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(AGENT, dest / pkg, ignore=shutil.ignore_patterns("__pycache__"))
    (dest / pkg / "config.py").write_text(src, encoding="utf-8")
    (dest / "main.py").write_text(
        '"""v1r A1-stacked diagnostic package; not a submission entrypoint."""\n'
        f"from {pkg}.policy import agent\n",
        encoding="utf-8",
    )
    return dest / "main.py"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    base_a1_src = armA1_config_source()
    validate(base_a1_src)

    built = {}
    for arm in ARM_FLAGS:
        main_path = build_package(out, arm, base_a1_src)
        built[arm] = str(main_path)
        print(f"built {arm}: {main_path}")
    (out / "index.json").write_text(json.dumps(built, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
