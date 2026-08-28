"""S16 Phase 2 step 1 (docs/plans/s16_slot_comparison.md §2.1) — the shipped `55675634`
main.py inlines its own copy of tile recovery + the market overlay
(`analysis/build_tape_overlay_submission.py::MAIN_TEMPLATE`), separate from
`agent/tape_overlay.py::TapeOverlay`. G13 (ROADMAP §9) requires the two to yield an
identical trajectory. **This test must pass before any `recovery_calibration` bench
number is trusted** — if it fails, the bench is measuring an agent we never shipped,
which the plan calls a STOP, not a threshold to relax.

Builds the real inlined main.py from the actual reconstruction on disk (the same
route the shipped submission packages) and plays it against the module-based
`TapeOverlay(mode="augment")` — same stream, same opponent, same seeds — through
`harness.play.play()`, which for a `.py` path hands off to `env.run()`'s own
file-loading (the same convention the Kaggle server uses), not a hand-rolled import.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

RECONSTRUCTION = ROOT / "data" / "derived" / "s6_step1_reconstruction_ReCurSiON.json"

pytestmark = pytest.mark.skipif(
    not RECONSTRUCTION.exists(),
    reason="reconstruction stream not on disk (gitignored competition data)",
)

SEEDS = (0, 1, 2, 3, 4)


@pytest.fixture(scope="module")
def built_main_path(tmp_path_factory):
    from analysis.build_tape_overlay_submission import build
    return build("ReCurSiON", package=False, mode="augment")


@pytest.fixture(scope="module")
def stream():
    rec = json.loads(RECONSTRUCTION.read_text())
    return rec["stream"]


def test_inlined_overlay_matches_agent_module_across_seeds(built_main_path, stream):
    from agent.tape_overlay import TapeOverlay
    from harness.play import play

    for seed in SEEDS:
        # A fresh TapeOverlay per seed: it is seat-local, per-episode state (mirrors
        # what the harness/server does — a fresh process per episode).
        module_agent = TapeOverlay(stream, mode="augment").act
        r_inline = play(str(built_main_path), "starter", seed=seed,
                         record=False, metrics=False, strict=False)
        r_module = play(module_agent, "starter", seed=seed,
                         record=False, metrics=False, strict=False)
        assert r_inline.clean, f"seed={seed}: inlined main.py not clean: {r_inline.health}"
        assert r_module.clean, f"seed={seed}: agent/tape_overlay.py not clean: {r_module.health}"
        assert r_inline.rewards == r_module.rewards, (
            f"seed={seed}: inlined vs module TapeOverlay diverge — "
            f"{r_inline.rewards} != {r_module.rewards}. The bench (s16_bench_three_arm.json) "
            "would be measuring an agent never shipped as 55675634 — STOP, do not proceed."
        )


def test_the_test_actually_detects_a_divergence(stream, tmp_path):
    """Verify the assertion above is not vacuously true: hand-break the inlined copy
    (drop tile recovery entirely) and confirm the two trajectories then disagree on at
    least one of a handful of seeds. This is the 'reddens on the pre-fix version' check
    (plan §4 rule 5) applied to a verification test rather than a bug fix."""
    from analysis.build_tape_overlay_submission import MAIN_TEMPLATE, build
    from agent.tape_overlay import TapeOverlay
    from harness.play import play

    broken_template = MAIN_TEMPLATE.replace(
        "farmer_a, hands_a = _recover_tile_actions(farm, farmer_a, hands_a)",
        "pass  # tile recovery intentionally disabled for this test",
    )
    assert broken_template != MAIN_TEMPLATE

    import analysis.build_tape_overlay_submission as build_mod
    rec = json.loads(RECONSTRUCTION.read_text())
    stream_json = json.dumps(rec["stream"], separators=(",", ":"))
    broken_main = tmp_path / "main.py"
    broken_main.write_text(broken_template.format(
        team="ReCurSiON", n_traces=rec["n_traces"],
        prod_agr=rec["prod_modal_share_mean"], market_agr=rec["market_modal_share_mean"],
        n_steps=len(rec["stream"]), sha256="deadbeef",
        stream_json=stream_json, n_recovery_rules=6,
    ), encoding="utf-8")

    diverged = False
    for seed in SEEDS:
        module_agent = TapeOverlay(rec["stream"], mode="augment").act
        r_broken = play(str(broken_main), "starter", seed=seed,
                         record=False, metrics=False, strict=False)
        r_module = play(module_agent, "starter", seed=seed,
                         record=False, metrics=False, strict=False)
        if r_broken.rewards != r_module.rewards:
            diverged = True
            break
    assert diverged, "disabling tile recovery in the inlined copy should change at least one seed"
