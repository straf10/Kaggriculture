"""Tests for the harness itself (review.md M7). The harness is the instrument every v1a-v1e
go/no-go decision (plan.md §3.3) will be read off of; before this file it had zero coverage.
Fast fake/tiny agents throughout (steps<=6) so this suite stays quick.
"""
import json
import shutil
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

import harness.cli as harness_cli
from harness.checkpoint import agent_fingerprint, create_checkpoint
from harness.compare import (
    VALID_STAGES,
    compare,
    priced_loss_budget,
    priced_loss_delta,
    priced_metric_loss,
)
from harness.play import play, resolve_agent
from harness.profile import report, timed
from harness.seeds import HOLDOUT_SEEDS

REPO_ROOT = Path(__file__).resolve().parent.parent

TRIVIAL_AGENT_SRC = (
    "def agent(obs):\n"
    "    return {'farmer': ['PASS'], 'hands': [], 'market': []}\n"
)

GREEK_AGENT_SRC = (
    "# σχόλιο στα ελληνικά με ύ και ώ — πρέπει να διαβαστεί ως utf-8, όχι cp1252\n"
    "def agent(obs):\n"
    "    return {'farmer': ['PASS'], 'hands': [], 'market': []}\n"
)

CRASHING_AGENT_SRC = (
    "_calls = [0]\n"
    "def agent(obs):\n"
    "    _calls[0] += 1\n"
    "    if _calls[0] > 2:\n"
    "        raise RuntimeError('boom')\n"
    "    return {'farmer': ['PASS'], 'hands': [], 'market': []}\n"
)


def _write_dev_screen_evidence(root: Path, candidate="A") -> None:
    path = root / "screen" / "results.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({
            "stage": "dev-screen",
            "code_fingerprints": [agent_fingerprint(candidate), agent_fingerprint("B")],
            "incomplete": False,
        }),
        encoding="utf-8",
    )


# --------------------------------------------------------------------------- resolve_agent


def test_resolve_agent_callable_passthrough():
    fn = lambda obs: None  # noqa: E731
    assert resolve_agent(fn) is fn


def test_resolve_agent_builtin_name():
    assert callable(resolve_agent("pass"))
    assert callable(resolve_agent("starter"))


def test_resolve_agent_py_path(tmp_path):
    agent_path = tmp_path / "trivial.py"
    agent_path.write_text(TRIVIAL_AGENT_SRC, encoding="utf-8")
    fn = resolve_agent(str(agent_path))
    assert fn.__name__ == "agent"


def test_resolve_agent_utf8_greek_comment(tmp_path):
    """review.md H1 — Path.read_text() without encoding= uses the locale default (cp1252 on
    Windows), which cannot decode U+03CD (ύ) and similar Greek characters this project's
    comments use throughout."""
    agent_path = tmp_path / "greek.py"
    agent_path.write_text(GREEK_AGENT_SRC, encoding="utf-8")
    fn = resolve_agent(str(agent_path))
    assert fn.__name__ == "agent"


def test_resolve_agent_invalid_spec_raises_valueerror():
    with pytest.raises(ValueError):
        resolve_agent(12345)
    with pytest.raises(ValueError):
        resolve_agent("not_a_builtin_and_not_an_existing_path.py")


def test_resolve_agent_entrypoint_matches_last_callable(tmp_path):
    agent_path = tmp_path / "shim.py"
    agent_path.write_text(TRIVIAL_AGENT_SRC, encoding="utf-8")
    fn = resolve_agent(str(agent_path), entrypoint="agent")
    assert fn.__name__ == "agent"


def test_resolve_agent_entrypoint_mismatch_raises():
    """review.md C2 — reproduces the exact bug found: an import placed after `def agent`
    makes Path (not agent) the last callable in the module namespace, which is what the
    Kaggle server's own loader would pick too. entrypoint= must catch this, not paper over it."""
    import tempfile
    from pathlib import Path as _Path

    with tempfile.TemporaryDirectory() as d:
        agent_path = _Path(d) / "bad_shim.py"
        agent_path.write_text(
            TRIVIAL_AGENT_SRC + "from pathlib import Path\n", encoding="utf-8"
        )
        with pytest.raises(ValueError):
            resolve_agent(str(agent_path), entrypoint="agent")


# --------------------------------------------------------------------------- play()


def test_play_writes_replay(tmp_path):
    result = play("starter", "pass", seed=0, steps=6, run_dir=tmp_path, record=True, strict=True)
    assert result.clean is True
    assert result.replay_path is not None
    assert result.replay_path.exists()


def test_play_path_spec_with_separators_does_not_break_filename(tmp_path):
    """review.md M2 — an absolute Windows path (drive letter, backslashes) used as an agent
    spec used to be written verbatim into the replay filename, which is invalid on Windows."""
    agent_path = tmp_path / "greek_agent.py"
    agent_path.write_text(GREEK_AGENT_SRC, encoding="utf-8")
    run_dir = tmp_path / "runs"
    result = play(str(agent_path), "pass", seed=0, steps=4, run_dir=run_dir, record=True, strict=True)
    assert result.replay_path.exists()


def test_play_replay_filenames_differ_by_seat_orientation(tmp_path):
    """review.md M1 — the two orientations of an A-vs-B comparison must not collide."""
    r1 = play("starter", "pass", seed=0, steps=4, run_dir=tmp_path, record=True)
    r2 = play("pass", "starter", seed=0, steps=4, run_dir=tmp_path, record=True)
    assert r1.replay_path != r2.replay_path
    assert r1.replay_path.exists() and r2.replay_path.exists()


def test_play_crashing_agent_raises_when_strict(tmp_path):
    agent_path = tmp_path / "crashing.py"
    agent_path.write_text(CRASHING_AGENT_SRC, encoding="utf-8")
    with pytest.raises(RuntimeError):
        play(str(agent_path), "pass", seed=0, steps=6, record=False, strict=True)


def test_play_crashing_agent_reports_unclean_when_not_strict(tmp_path):
    """review.md C1 — a crashing agent must never silently produce a DONE/bank number."""
    agent_path = tmp_path / "crashing.py"
    agent_path.write_text(CRASHING_AGENT_SRC, encoding="utf-8")
    result = play(str(agent_path), "pass", seed=0, steps=6, record=False, strict=False)
    assert result.clean is False
    assert result.health[0]  # non-empty: some non-ACTIVE/DONE status was seen for seat 0
    assert any(e["seat"] == 0 for e in result.agent_errors)


def test_play_collects_structured_agent_diagnostics():
    def receipt_agent(obs):
        del obs
        print('KAGGRI_RECEIPT {"kind":"expected_transition","ok":true}')
        return {"farmer": ["PASS"], "hands": [], "market": []}

    result = play(receipt_agent, "pass", seed=0, steps=4, record=False)
    assert result.clean is True
    assert result.diagnostics
    assert result.diagnostics[0]["kind"] == "expected_transition"
    assert result.diagnostics[0]["ok"] is True


def test_play_render_html_writes_bundled_visualizer(tmp_path):
    """plan.md §1.5.4 — render_html=True writes the engine's own bundled offline visualizer,
    not just a placeholder/empty file."""
    result = play("starter", "pass", seed=0, steps=4, run_dir=tmp_path, record=True, render_html=True)
    assert result.html_path is not None
    assert result.html_path.exists()
    assert result.html_path.stat().st_size > 1000


def test_play_render_html_off_by_default_leaves_html_path_none(tmp_path):
    result = play("starter", "pass", seed=0, steps=4, run_dir=tmp_path, record=True)
    assert result.html_path is None


def test_play_persists_receipts_only_when_diagnostics_nonempty(tmp_path):
    """plan.md §1.5.4 — receipts are written next to the replay only when there's something
    to write; an agent with guards.debug off (the default) produces no receipts_path at all,
    so harness/report.py can tell 'not measured' apart from 'measured, found nothing'."""
    def receipt_agent(obs):
        del obs
        print('KAGGRI_RECEIPT {"kind":"expected_transition","ok":true}')
        return {"farmer": ["PASS"], "hands": [], "market": []}

    with_receipts = play(receipt_agent, "pass", seed=0, steps=4, run_dir=tmp_path, record=True)
    assert with_receipts.receipts_path is not None
    assert with_receipts.receipts_path.exists()
    lines = with_receipts.receipts_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == len(with_receipts.diagnostics)

    without_receipts = play("starter", "pass", seed=1, steps=4, run_dir=tmp_path, record=True)
    assert without_receipts.receipts_path is None


# --------------------------------------------------------------------------- compare()


pytestmark_small_seed_warning = pytest.mark.filterwarnings(
    "ignore:compare\\(\\).*seeds.*:UserWarning"
)


@pytestmark_small_seed_warning
def test_compare_distinct_orientations_write_distinct_replay_files(tmp_path):
    result = compare("starter", "pass", [0], both_seats=True, steps=4, run_dir=tmp_path, record=True)
    replay_files = list(tmp_path.glob("*.json.gz"))
    assert len(replay_files) == 2
    assert replay_files[0].name != replay_files[1].name


@pytestmark_small_seed_warning
def test_compare_empty_seeds_does_not_crash():
    with patch("harness.compare.play") as mock_play:
        result = compare("A", "B", [], record=False)
    mock_play.assert_not_called()
    assert result.per_seed == []
    assert result.mean_diff == 0.0
    assert result.significant is None
    assert result.verdict == "INCONCLUSIVE"


@pytestmark_small_seed_warning
def test_compare_single_seed_does_not_crash_or_claim_significance():
    def fake_play(a, b, seed, **kwargs):
        rewards = (140.0, 100.0) if a == "A" else (100.0, 140.0)
        return SimpleNamespace(rewards=rewards)

    with patch("harness.compare.play", side_effect=fake_play):
        result = compare("A", "B", [0], both_seats=False, record=False)
    assert result.n_effective == 1
    assert result.se_diff == 0.0
    assert result.significant is None


@pytestmark_small_seed_warning
def test_compare_constant_diff_does_not_claim_significant_true():
    """review.md M4 — se_diff==0 (a perfectly constant diff across seeds) must not be reported
    as `significant=True`; it's an undefined statistic, not infinite confidence."""
    def fake_play(a, b, seed, **kwargs):
        rewards = (101.0, 100.0) if a == "A" else (100.0, 101.0)
        return SimpleNamespace(rewards=rewards)

    with patch("harness.compare.play", side_effect=fake_play):
        result = compare("A", "B", range(12), both_seats=False, record=False)
    assert result.se_diff == 0.0
    assert result.significant is None
    assert result.mean_diff == pytest.approx(1.0)


@pytestmark_small_seed_warning
def test_compare_negative_practical_diff_is_regressed_not_go():
    def fake_play(a, b, seed, **kwargs):
        del b, seed, kwargs
        return SimpleNamespace(rewards=(100.0, 1100.0) if a == "A" else (1100.0, 100.0))

    with patch("harness.compare.play", side_effect=fake_play):
        result = compare("A", "B", range(12), both_seats=False, record=False)

    assert result.mean_diff == -1000.0
    assert result.verdict == "REGRESSED"


@pytestmark_small_seed_warning
def test_compare_both_seats_swaps_seats():
    """review.md M7 — both_seats=True must call play() with agent_a/agent_b actually
    swapped between the two seats for the same seed, not the same orientation twice."""
    calls = []

    def fake_play(a, b, seed, **kwargs):
        calls.append((a, b, seed))
        rewards = (100.0, 50.0) if a == "A" else (50.0, 100.0)
        return SimpleNamespace(rewards=rewards)

    with patch("harness.compare.play", side_effect=fake_play):
        result = compare("A", "B", [0], both_seats=True, record=False)

    assert calls == [("A", "B", 0), ("B", "A", 0)]
    assert result.per_seed[0]["bank_a"] == 100.0
    assert result.per_seed[0]["bank_b"] == 50.0
    assert result.episode_wins_a == 2
    assert result.episode_wins_b == 0
    assert len(result.per_seed[0]["orientations"]) == 2


@pytestmark_small_seed_warning
def test_compare_resume_rejects_mismatched_code_fingerprints(tmp_path):
    """review.md M2 — resuming into a results.jsonl recorded under a different agent version
    must raise instead of silently mixing seeds from two versions into one verdict."""
    def fake_play(a, b, seed, **kwargs):
        rewards = (100.0, 50.0) if a == "A" else (50.0, 100.0)
        return SimpleNamespace(rewards=rewards)

    with patch("harness.compare.play", side_effect=fake_play):
        compare("A", "B", [0], both_seats=False, record=False, run_dir=tmp_path)

    with patch("harness.compare.play", side_effect=fake_play):
        with pytest.raises(ValueError, match="code fingerprints"):
            compare("A", "C", [1], both_seats=False, record=False, run_dir=tmp_path, resume=True)


@pytestmark_small_seed_warning
def test_compare_resume_rejects_metrics_mismatch(tmp_path):
    """review.md C3 — resuming a metrics=False run with metrics=True (or vice versa) must
    raise instead of silently averaging an unmeasured metric gate into a report that reads
    as fully measured just because every seed already looks 'done'."""
    def fake_play(a, b, seed, **kwargs):
        rewards = (100.0, 50.0) if a == "A" else (50.0, 100.0)
        metrics = {0: {"water_weeds_lost": 0, "plant_decay_units_lost": 0}, 1: {}}
        return SimpleNamespace(rewards=rewards, metrics=metrics)

    with patch("harness.compare.play", side_effect=fake_play):
        compare("A", "B", [0], both_seats=False, record=False, run_dir=tmp_path)

    with patch("harness.compare.play", side_effect=fake_play):
        with pytest.raises(ValueError, match="metrics"):
            compare("A", "B", [1], both_seats=False, record=False, run_dir=tmp_path,
                    resume=True, metrics=True)


@pytestmark_small_seed_warning
def test_compare_resume_rejects_both_seats_mismatch(tmp_path):
    """review.md C3 — resuming a single-seat run as both_seats=True must raise instead of
    silently mixing 1-orientation and 2-orientation seeds into one mean_diff."""
    def fake_play(a, b, seed, **kwargs):
        rewards = (100.0, 50.0) if a == "A" else (50.0, 100.0)
        return SimpleNamespace(rewards=rewards)

    with patch("harness.compare.play", side_effect=fake_play):
        compare("A", "B", [0], both_seats=False, record=False, run_dir=tmp_path)

    with patch("harness.compare.play", side_effect=fake_play):
        with pytest.raises(ValueError, match="both_seats"):
            compare("A", "B", [1], both_seats=True, record=False, run_dir=tmp_path, resume=True)


@pytestmark_small_seed_warning
def test_compare_resume_rejects_changed_town_schedule_contents(tmp_path):
    def fake_play(a, b, seed, **kwargs):
        rewards = (100.0, 50.0) if a == "A" else (50.0, 100.0)
        return SimpleNamespace(rewards=rewards)

    seeds = [0, 1]
    with patch("harness.compare.play", side_effect=fake_play):
        compare(
            "A", "B", seeds, both_seats=False, record=False, run_dir=tmp_path,
            town_pin="basket",
        )

    with patch("harness.compare.schedule_for_mode", return_value=["CHANGED"]):
        with pytest.raises(ValueError, match="town_schedules"):
            compare(
                "A", "B", seeds, both_seats=False, record=False, run_dir=tmp_path,
                town_pin="basket", resume=True,
            )


@pytestmark_small_seed_warning
def test_compare_warns_schedule_pin_is_historical():
    def fake_play(a, b, seed, **kwargs):
        rewards = (100.0, 50.0) if a == "A" else (50.0, 100.0)
        return SimpleNamespace(rewards=rewards)

    with patch("harness.compare.play", side_effect=fake_play):
        with pytest.warns(UserWarning, match="historical reproduction"):
            compare("A", "B", [0], both_seats=False, record=False, town_pin="schedule")


@pytestmark_small_seed_warning
def test_compare_rejects_holdout_confirm_stage_on_non_confirm_seeds(tmp_path):
    """review.md C2(a) — stage='holdout-confirm' must only accept seeds drawn from a
    registered confirm set (HOLDOUT_SEEDS/CONFIRM2_SEEDS); ad-hoc or dev-screen seeds must
    raise before a single episode is played."""
    with pytest.raises(ValueError, match="holdout-confirm"):
        compare("A", "B", range(12), record=False, stage="holdout-confirm",
                confirm_ledger_path=tmp_path / "ledger.jsonl")


@pytestmark_small_seed_warning
def test_compare_rejects_holdout_confirm_subset(tmp_path):
    with pytest.raises(ValueError, match="complete seed set"):
        compare("A", "B", list(HOLDOUT_SEEDS)[:12], record=False, stage="holdout-confirm",
                confirm_ledger_path=tmp_path / "ledger.jsonl")


@pytestmark_small_seed_warning
def test_compare_rejects_pinned_holdout_confirm(tmp_path):
    with pytest.raises(ValueError, match="town_pin=None"):
        compare("A", "B", list(HOLDOUT_SEEDS), record=False, stage="holdout-confirm",
                town_pin="basket", confirm_ledger_path=tmp_path / "ledger.jsonl")


@pytestmark_small_seed_warning
def test_compare_rejects_dev_screen_stage_on_non_dev_seeds():
    """review.md C2(a) — the dev-screen/holdout-confirm split is symmetric: dev-screen must
    equally refuse seeds outside DEV_SEEDS (e.g. confirm-set seeds tuning shouldn't touch)."""
    with pytest.raises(ValueError, match="dev-screen"):
        compare("A", "B", list(HOLDOUT_SEEDS)[:12], record=False, stage="dev-screen")


@pytestmark_small_seed_warning
def test_compare_second_confirm_raises_without_override(tmp_path):
    """review.md C1/C2 — the exact v1c failure mode: a second stage=holdout-confirm run
    against the same (agent_b fingerprint, seed set) must raise unless allow_repeat_confirm
    is explicit, and is then recorded as repeat_confirm_index instead of silently picking
    the better of two pulls."""
    def fake_play(a, b, seed, **kwargs):
        rewards = (150.0, 100.0) if a == "A" else (100.0, 150.0)
        metrics = {0: {"water_weeds_lost": 0, "plant_decay_units_lost": 0},
                   1: {"water_weeds_lost": 0, "plant_decay_units_lost": 0}}
        return SimpleNamespace(rewards=rewards, metrics=metrics)

    ledger = tmp_path / "confirm_log.jsonl"
    seeds = list(HOLDOUT_SEEDS)
    with patch("harness.compare.play", side_effect=fake_play):
        first = compare("A", "B", seeds, both_seats=False, record=False, metrics=True,
                         min_effect=10.0, stage="holdout-confirm", confirm_ledger_path=ledger)
        assert first.repeat_confirm_index == 0

        with pytest.raises(ValueError, match="already has"):
            compare("A", "B", seeds, both_seats=False, record=False, metrics=True,
                    min_effect=10.0, stage="holdout-confirm", confirm_ledger_path=ledger)

        second = compare("A", "B", seeds, both_seats=False, record=False, metrics=True,
                          min_effect=10.0, stage="holdout-confirm", confirm_ledger_path=ledger,
                          allow_repeat_confirm=True)
    assert second.repeat_confirm_index == 1


@pytestmark_small_seed_warning
def test_confirm_ledger_only_counts_metered_complete_runs(tmp_path):
    def clean_play(a, b, seed, **kwargs):
        del b, seed, kwargs
        rewards = (150.0, 100.0) if a == "A" else (100.0, 150.0)
        return SimpleNamespace(rewards=rewards)

    unmetered_ledger = tmp_path / "unmetered.jsonl"
    with patch("harness.compare.play", side_effect=clean_play):
        result = compare(
            "A", "B", list(HOLDOUT_SEEDS), both_seats=False, record=False,
            stage="holdout-confirm", confirm_ledger_path=unmetered_ledger,
        )
    assert result.incomplete is False
    assert not unmetered_ledger.exists()

    incomplete_ledger = tmp_path / "incomplete.jsonl"
    with patch("harness.compare.play", side_effect=RuntimeError("boom")):
        result = compare(
            "A", "B", list(HOLDOUT_SEEDS), both_seats=False, record=False, metrics=True,
            stage="holdout-confirm", confirm_ledger_path=incomplete_ledger,
        )
    assert result.incomplete is True
    assert not incomplete_ledger.exists()


@pytestmark_small_seed_warning
def test_compare_exposes_effective_margins():
    """review.md H1 — min_effect_used/non_inferiority_margin_used must reflect what the
    verdict was actually judged against; it drifts (2% of bank_b) unless pinned explicitly,
    and used to not be recorded anywhere in the result."""
    def fake_play(a, b, seed, **kwargs):
        rewards = (150.0, 100.0) if a == "A" else (100.0, 150.0)
        return SimpleNamespace(rewards=rewards)

    with patch("harness.compare.play", side_effect=fake_play):
        result = compare("A", "B", [0], both_seats=False, record=False, min_effect=42.0)
    assert result.min_effect_used == 42.0
    assert result.non_inferiority_margin_used == 42.0


@pytestmark_small_seed_warning
def test_cli_compare_defaults_preserve_dynamic_effect_floor(monkeypatch):
    captured = {}

    def fake_command(args):
        captured["min_effect"] = args.min_effect
        captured["non_inferiority_margin"] = args.non_inferiority_margin

    monkeypatch.setattr(harness_cli, "_cmd_compare", fake_command)
    harness_cli.main(["compare", "A", "B", "--workers", "1"])

    assert captured == {"min_effect": None, "non_inferiority_margin": None}


@pytestmark_small_seed_warning
def test_results_json_includes_incomplete_and_warnings():
    from harness.compare import CompareResult

    result = CompareResult(incomplete=True, warnings=["diagnostic warning"])
    payload = harness_cli._results_json_dict(result)

    assert payload["incomplete"] is True
    assert payload["warnings"] == ["diagnostic warning"]


@pytestmark_small_seed_warning
def test_compare_within_margin_requires_explicit_accept_for_go(tmp_path):
    """review.md H2 — a paired-seed CI entirely negative (every seed lost, just by less than
    the margin) is a confirmed small regression, not genuine equivalence — it must read as
    WITHIN_MARGIN (not NON_INFERIOR) and must never produce go=True without an explicit
    accept_within_margin=True, since the sign test here is also unanimous against agent_a."""
    def fake_play(a, b, seed, **kwargs):
        diff = -10.0 if seed % 2 == 0 else -11.0
        rewards = (100.0 + diff, 100.0) if a == "A" else (100.0, 100.0 + diff)
        metrics = {0: {"water_weeds_lost": 0, "plant_decay_units_lost": 0},
                   1: {"water_weeds_lost": 0, "plant_decay_units_lost": 0}}
        return SimpleNamespace(rewards=rewards, metrics=metrics)

    seeds = list(HOLDOUT_SEEDS)
    ledger = tmp_path / "confirm_log.jsonl"
    evidence = tmp_path / "gates"
    _write_dev_screen_evidence(evidence)
    with patch("harness.compare.play", side_effect=fake_play):
        blocked = compare("A", "B", seeds, both_seats=True, record=False, metrics=True,
                           non_inferiority_margin=50.0, stage="holdout-confirm",
                           confirm_ledger_path=ledger, screen_evidence_dir=evidence)
        accepted = compare("A", "B", seeds, both_seats=True, record=False, metrics=True,
                            non_inferiority_margin=50.0, stage="holdout-confirm",
                            confirm_ledger_path=ledger, allow_repeat_confirm=True,
                            accept_within_margin=True, screen_evidence_dir=evidence)

    assert blocked.verdict == "WITHIN_MARGIN"
    assert blocked.sign_test_p is not None and blocked.sign_test_p < 0.01
    assert blocked.go is False
    assert accepted.verdict == "WITHIN_MARGIN"
    assert accepted.go is True


@pytestmark_small_seed_warning
def test_compare_go_false_for_single_seat_holdout_confirm(tmp_path):
    def fake_play(a, b, seed, **kwargs):
        del b, kwargs
        diff = 50.0 if seed % 2 == 0 else 40.0
        rewards = (100.0 + diff, 100.0) if a == "A" else (100.0, 100.0 + diff)
        clean = {
            "water_weeds_lost": 0,
            "plant_decay_units_lost": 0,
            "animals_escaped": 0,
            "clipped_production_ticks": 0,
            "shed_overflow_burnt": 0,
            "unexpected_weeds_lost": 0,
        }
        return SimpleNamespace(rewards=rewards, metrics={0: clean, 1: clean})

    evidence = tmp_path / "gates"
    _write_dev_screen_evidence(evidence)
    with patch("harness.compare.play", side_effect=fake_play):
        result = compare(
            "A", "B", list(HOLDOUT_SEEDS), both_seats=False, record=False, metrics=True,
            min_effect=10.0, stage="holdout-confirm",
            confirm_ledger_path=tmp_path / "confirm_log.jsonl",
            screen_evidence_dir=evidence,
        )

    assert result.verdict == "IMPROVED"
    assert result.metric_gate_passed is True
    assert result.go is False


@pytestmark_small_seed_warning
def test_compare_go_requires_prior_tracked_dev_screen(tmp_path):
    def fake_play(a, b, seed, **kwargs):
        del b, kwargs
        diff = 50.0 if seed % 2 == 0 else 40.0
        rewards = (100.0 + diff, 100.0) if a == "A" else (100.0, 100.0 + diff)
        clean = {
            "water_weeds_lost": 0,
            "plant_decay_units_lost": 0,
            "animals_escaped": 0,
            "clipped_production_ticks": 0,
            "shed_overflow_burnt": 0,
            "unexpected_weeds_lost": 0,
        }
        return SimpleNamespace(rewards=rewards, metrics={0: clean, 1: clean})

    with patch("harness.compare.play", side_effect=fake_play):
        with pytest.warns(UserWarning, match="no prior complete tracked dev-screen"):
            result = compare(
                "A", "B", list(HOLDOUT_SEEDS), both_seats=True, record=False, metrics=True,
                min_effect=10.0, stage="holdout-confirm",
                confirm_ledger_path=tmp_path / "confirm_log.jsonl",
                screen_evidence_dir=tmp_path / "empty-gates",
            )

    assert result.verdict == "IMPROVED"
    assert result.metric_gate_passed is True
    assert result.prior_dev_screen_found is False
    assert result.go is False


@pytestmark_small_seed_warning
def test_compare_holdout_confirm_rejects_kaggri_ablation_env(monkeypatch, tmp_path):
    """review.md H7 — an ablated environment must never produce a 'clean' confirm artefact
    with no trace of it; this must raise before any episode is played."""
    monkeypatch.setenv("KAGGRI_ABLATION", "some_flag=0")
    with pytest.raises(ValueError, match="KAGGRI_ABLATION"):
        compare("A", "B", list(HOLDOUT_SEEDS), record=False, stage="holdout-confirm",
                confirm_ledger_path=tmp_path / "ledger.jsonl")


@pytestmark_small_seed_warning
def test_compare_records_provenance_fields():
    """review.md H5 — agent specs, seed set name, harness commit, and platform info must be
    on the result so a gate artefact is reproducible without external context."""
    def fake_play(a, b, seed, **kwargs):
        rewards = (150.0, 100.0) if a == "A" else (100.0, 150.0)
        return SimpleNamespace(rewards=rewards)

    with patch("harness.compare.play", side_effect=fake_play):
        result = compare("A", "B", [0], both_seats=False, record=False)
    assert result.agent_a_spec == "A"
    assert result.agent_b_spec == "B"
    assert result.seed_set_name.startswith("custom[")
    assert result.platform
    assert result.python_version
    assert isinstance(result.env, dict)


@pytestmark_small_seed_warning
def test_compare_workers_matches_sequential_per_seed_diffs():
    """plan.md §1.5.1 criterion (i): workers=1 (sequential) and workers>1 (ProcessPoolExecutor,
    one job per (seed, orientation)) must produce identical per-seed diffs for the same
    seeds/agents — only wall time may differ. Real episodes (not mocked play()), since the
    thing under test is process-boundary/pickling behavior, not compare()'s arithmetic."""
    seeds = range(4)
    seq = compare("starter", "pass", seeds, steps=6, record=False, workers=1)
    par = compare("starter", "pass", seeds, steps=6, record=False, workers=2)

    seq_diffs = [(row["seed"], row["diff"]) for row in seq.per_seed]
    par_diffs = [(row["seed"], row["diff"]) for row in par.per_seed]
    assert seq_diffs == par_diffs
    assert seq.mean_diff == pytest.approx(par.mean_diff)
    assert seq.verdict == par.verdict


@pytestmark_small_seed_warning
def test_compare_parallel_persists_meta_and_each_completed_seed(tmp_path):
    seeds = range(4)
    result = compare(
        "starter", "pass", seeds, steps=6, record=False, workers=2, run_dir=tmp_path
    )

    rows = [
        json.loads(line)
        for line in (tmp_path / "results.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert rows[0]["_meta"] is True
    assert sorted(row["seed"] for row in rows[1:]) == list(seeds)
    assert result.n_effective == len(seeds)


@pytestmark_small_seed_warning
def test_compare_workers_falls_back_to_sequential_for_unpicklable_callable():
    """plan.md §1.5.1 (a): a callable agent_spec that can't cross a spawned worker process
    (a local/nested function, unlike a top-level function or a file path) must degrade to
    workers=1 with a warning, not raise."""
    def local_agent(obs):
        del obs
        return {"farmer": ["PASS"], "hands": [], "market": []}

    with pytest.warns(UserWarning, match="not picklable"):
        result = compare(local_agent, "pass", [0], steps=4, record=False, workers=4)
    assert result.n_effective == 1
    assert not result.errors


@pytestmark_small_seed_warning
def test_compare_non_inferior_requires_min_n():
    """review.md M3 — NON_INFERIOR must not be reachable below the minimum sample size, even
    when the confidence interval would otherwise clear the margin."""
    def fake_play(a, b, seed, **kwargs):
        diff = 5.0 if seed % 2 == 0 else -5.0
        rewards = (100.0 + diff, 100.0) if a == "A" else (100.0, 100.0 + diff)
        return SimpleNamespace(rewards=rewards)

    with patch("harness.compare.play", side_effect=fake_play):
        small = compare("A", "B", range(4), both_seats=False, record=False,
                         non_inferiority_margin=1000.0)
        large = compare("A", "B", range(12), both_seats=False, record=False,
                         non_inferiority_margin=1000.0)

    assert small.n_effective < 12
    assert small.verdict == "INCONCLUSIVE"
    assert large.n_effective >= 12
    assert large.verdict == "NON_INFERIOR"


@pytestmark_small_seed_warning
def test_compare_rejects_invalid_stage():
    assert set(VALID_STAGES) == {"dev-screen", "holdout-confirm"}
    with pytest.raises(ValueError, match="stage"):
        compare("A", "B", [0], record=False, stage="bogus")


@pytestmark_small_seed_warning
def test_compare_metrics_off_by_default_leaves_gate_fields_unset():
    def fake_play(a, b, seed, **kwargs):
        assert kwargs.get("metrics") is False
        rewards = (150.0, 100.0) if a == "A" else (100.0, 150.0)
        return SimpleNamespace(rewards=rewards)

    with patch("harness.compare.play", side_effect=fake_play):
        result = compare("A", "B", [0], both_seats=False, record=False)
    assert result.metrics_checked is False
    assert result.metric_gate_passed is None
    # review.md C3 — None (not 0) when metrics wasn't measured: "not measured" and
    # "measured, zero" must not be indistinguishable.
    assert result.water_weeds_lost_a is None
    assert result.go is False


@pytestmark_small_seed_warning
def test_compare_metrics_reads_agent_a_seat_in_each_orientation():
    """plan.md §1.5.3 — agent_a occupies seat 0 in the 'A@0/B@1' orientation but seat 1 in
    the swapped 'B@0/A@1' orientation; the metric gate must follow agent_a's seat, not
    always read seat 0 (which would silently score the opponent's water discipline instead)."""
    def fake_play(a, b, seed, **kwargs):
        assert kwargs.get("metrics") is True
        if a == "A":  # agent_a plays seat 0 this call
            rewards = (150.0, 100.0)
            metrics = {
                0: {
                    "water_weeds_lost": 1, "plant_decay_units_lost": 2,
                    "crop_tile_days": 100, "worker_turns_idle": 10,
                    "worker_turns_total": 100, "animals_underfed_days": 2,
                },
                1: {
                    "crop_tile_days": 80, "worker_turns_idle": 20,
                    "worker_turns_total": 100, "animals_underfed_days": 3,
                },
            }
        else:  # agent_a ("A") plays seat 1 this call
            rewards = (100.0, 150.0)
            metrics = {
                0: {
                    "crop_tile_days": 81, "worker_turns_idle": 21,
                    "worker_turns_total": 101, "animals_underfed_days": 4,
                },
                1: {
                    "water_weeds_lost": 3, "plant_decay_units_lost": 4,
                    "crop_tile_days": 101, "worker_turns_idle": 11,
                    "worker_turns_total": 101, "animals_underfed_days": 5,
                },
            }
        return SimpleNamespace(rewards=rewards, metrics=metrics)

    with patch("harness.compare.play", side_effect=fake_play):
        result = compare("A", "B", [0], both_seats=True, record=False, metrics=True)

    assert result.metrics_checked is True
    assert result.water_weeds_lost_a == 1 + 3
    assert result.plant_decay_units_lost_a == 2 + 4
    assert result.crop_tile_days_a == 100 + 101
    assert result.crop_tile_days_b == 80 + 81
    assert result.worker_turns_idle_a == 10 + 11
    assert result.worker_turns_total_a == 100 + 101
    assert result.animals_underfed_days_a == 2 + 5
    assert result.metric_gate_passed is False


@pytestmark_small_seed_warning
def test_v1h2d_compare_gates_unexpected_not_raw_weeds():
    def fake_play_expected(a, b, seed, **kwargs):
        del b, seed, kwargs
        rewards = (150.0, 100.0) if a == "A" else (100.0, 150.0)
        clean = {
            "water_weeds_lost": 0,
            "plant_decay_units_lost": 0,
            "animals_escaped": 0,
            "clipped_production_ticks": 0,
            "shed_overflow_burnt": 0,
            "weeds_lost": 8,
            "unexpected_weeds_lost": 0,
        }
        return SimpleNamespace(rewards=rewards, metrics={0: clean, 1: clean})

    with patch("harness.compare.play", side_effect=fake_play_expected):
        expected = compare("A", "B", [0], both_seats=False, record=False, metrics=True)

    assert expected.weeds_lost_a == 8
    assert expected.unexpected_weeds_lost_a == 0
    assert expected.metric_gate_passed is True

    def fake_play_unexpected(a, b, seed, **kwargs):
        result = fake_play_expected(a, b, seed, **kwargs)
        result.metrics[0] = {**result.metrics[0], "weeds_lost": 1, "unexpected_weeds_lost": 1}
        return result

    with patch("harness.compare.play", side_effect=fake_play_unexpected):
        unexpected = compare("A", "B", [0], both_seats=False, record=False, metrics=True)

    assert unexpected.metric_gate_passed is False


# --------------------------------------- current_phase.md §1 Απόφαση Α + Δ (priced gate)

def _gate_counts(gate_name, arm="a"):
    """Real measured counters from a tracked gate artifact — the whole point of pinning the
    new gate to these three is that they are not hypotheticals: they are the three decisions
    the old hard-zero gate got wrong (or right) in memory.md 2026-08-09 (δ)/(ε).

    `arm="b"` returns the opponent-side counters Απόφαση Δ added; artefacts written before Δ
    have none, which is exactly the case the callers below assert on.
    """
    payload = json.loads(
        (REPO_ROOT / "gates" / gate_name / "results.json").read_text(encoding="utf-8")
    )
    counts = {
        metric: payload.get(f"{metric}_{arm}")
        for metric in ("animals_escaped", "shed_overflow_burnt",
                       "unexpected_weeds_lost", "water_weeds_lost")
    }
    episodes = payload["episode_wins_a"] + payload["episode_wins_b"] + payload["episode_ties"]
    return counts, episodes, payload["mean_diff"]


@pytest.mark.parametrize("gate_name,accepted,expected_loss", [
    # v1h_2c alone: +$2,888.5/ep bought with 39 escapes = $406.3/ep against a $288.8/ep budget.
    # (This pre-v1h.2d artifact predates the shed_overflow_burnt field, which memory.md
    # 2026-08-09 (δ) records as 1,510 — including it would only push the loss further over.)
    # Rejected under the old gate, rejected under this one: pricing is not a loosening.
    ("gate_v1h2_dev", False, 406.25),
    # EOD surplus alone: overflow eliminated but 54 escapes survive = $562.5/ep — over the $500
    # absolute cap *and* over the $153.0/ep the +$1,529.8 gain affords. Both bounds reject it.
    ("gate_v1h2d_eod_surplus", False, 562.5),
    # EOD + FEED: 84 burnt units ($131.3) + 34 lost tiles ($106.3) = $237.5/ep against
    # +$3,019.3/ep = 7.9%, inside both bounds. This is the arm the old gate wrongly rejected.
    ("gate_v1h2d_feed_slack", True, 237.5),
])
def test_v1h2d_priced_gate_decides_the_three_measured_arms(gate_name, accepted, expected_loss):
    """Απόφαση Δ moved the priced leg onto the *difference* between the arms. These three
    artefacts predate Δ and carry no B-side counters, so priced_loss_b is 0 and the delta is
    the absolute loss — which is why all three verdicts are unchanged. Δ re-scores what a
    baseline already loses; it does not re-score arms measured against a clean opponent."""
    counts, episodes, mean_diff = _gate_counts(gate_name)
    counts_b, _, _ = _gate_counts(gate_name, arm="b")
    assert all(count is None for count in counts_b.values())  # pre-Δ artefact, by construction

    loss_a, breakdown = priced_metric_loss(counts, episodes)
    loss_b, _ = priced_metric_loss({}, episodes)
    delta = priced_loss_delta(loss_a, loss_b)
    budget = priced_loss_budget(mean_diff)

    assert episodes == 96  # 48 dev seeds x both seats; a changed denominator changes every price
    assert loss_a == pytest.approx(expected_loss)
    assert loss_b == 0.0
    assert delta == pytest.approx(expected_loss)
    assert (delta <= budget) is accepted
    # The breakdown has to explain the total, or the number in the ledger is not auditable.
    assert loss_a == pytest.approx(sum(breakdown.values()))


def test_decision_d_prices_the_difference_not_the_inherited_loss():
    """current_phase.md §1 Απόφαση Δ, the measurement that forced it: the same candidate code
    measured 112 burnt units vs the meta bench and 754 vs the mirror, so the counter describes
    market conditions, not candidate quality. Whatever an arm's own opponent also burns is not
    something the increment introduced, and the clamp stops a tidier candidate from banking the
    surplus as budget for breaking something else."""
    assert priced_loss_delta(175.0, 154.0) == pytest.approx(21.0)
    assert priced_loss_delta(1_322.9, 1_300.0) == pytest.approx(22.9)
    # A candidate that breaks *less* than its arm B earns 0, never a negative loss.
    assert priced_loss_delta(10.0, 900.0) == 0.0
    assert priced_loss_delta(0.0, 0.0) == 0.0


def test_v1h2d_priced_gate_does_not_charge_a_lost_tile_twice():
    """water_weeds_lost and unexpected_weeds_lost fire on the same PLANT->WEED transition;
    the feed-slack arm reports 34 for both because they are the same 34 tiles."""
    loss, breakdown = priced_metric_loss(
        {"unexpected_weeds_lost": 34, "water_weeds_lost": 34}, 96
    )
    assert breakdown["lost_crop_tiles"] == pytest.approx(34 * 300 / 96)
    assert loss == pytest.approx(34 * 300 / 96)
    # A thirst death that the semantic counter did not see still costs a tile, and vice versa.
    assert priced_metric_loss({"water_weeds_lost": 34}, 96)[0] == pytest.approx(34 * 300 / 96)
    assert priced_metric_loss({"unexpected_weeds_lost": 34}, 96)[0] == pytest.approx(34 * 300 / 96)


def test_v1h2d_priced_gate_bounds_are_both_binding():
    """Both bounds are load-bearing: the fraction is what rejects the EOD-only arm on ratio,
    the absolute cap is what stops a large gain from buying unlimited breakage."""
    # A huge gain does not buy unlimited breakage: the absolute cap holds it at $500.
    assert priced_loss_budget(1_000_000.0) == 500.0
    # A small gain is held by the fraction, well under the cap.
    assert priced_loss_budget(1_000.0) == 100.0
    # A change that earns nothing gets no loss budget at all.
    assert priced_loss_budget(0.0) == 0.0
    assert priced_loss_budget(-5_000.0) == 0.0


@pytestmark_small_seed_warning
def test_v1h2d_priced_gate_requires_a_declared_mechanism():
    """Pricing buys tolerance for understood loss, never for unexplained loss — that is the
    bug-detector role the hard-zero gate used to play, and it is the only part of it kept."""
    def fake_play(a, b, seed, **kwargs):
        del b, seed, kwargs
        rewards = (100_000.0, 0.0) if a == "A" else (0.0, 100_000.0)
        metrics = {
            "water_weeds_lost": 0, "plant_decay_units_lost": 0, "animals_escaped": 0,
            "clipped_production_ticks": 0, "shed_overflow_burnt": 1,
            "weeds_lost": 8, "unexpected_weeds_lost": 0,
        }
        return SimpleNamespace(rewards=rewards, metrics={0: metrics, 1: metrics})

    with patch("harness.compare.play", side_effect=fake_play):
        undeclared = compare("A", "B", [0], both_seats=False, record=False, metrics=True)
        declared = compare("A", "B", [0], both_seats=False, record=False, metrics=True,
                            metric_mechanisms={"shed_overflow_burnt": "peak-production day"})
        blank = compare("A", "B", [0], both_seats=False, record=False, metrics=True,
                         metric_mechanisms={"shed_overflow_burnt": "   "})

    # $150/ep of loss against a $100,000/ep gain — comfortably inside both bounds either way.
    assert undeclared.priced_loss_per_episode == pytest.approx(150.0)
    assert undeclared.priced_loss_budget_used == 500.0
    assert undeclared.unexplained_metrics == ("shed_overflow_burnt",)
    assert undeclared.metric_gate_passed is False
    assert declared.unexplained_metrics == ()
    assert declared.metric_gate_passed is True
    assert blank.metric_gate_passed is False  # whitespace is not an explanation


@pytestmark_small_seed_warning
def test_v1h2d_structural_faults_stay_hard_zero_at_any_price():
    """clipped_production_ticks and plant_decay_units_lost are not losses to be priced: they
    mean the agent did something it did not intend. No mean_diff buys them."""
    def fake_play(a, b, seed, **kwargs):
        del b, seed, kwargs
        rewards = (100_000.0, 0.0) if a == "A" else (0.0, 100_000.0)
        metrics = {
            "water_weeds_lost": 0, "plant_decay_units_lost": 0, "animals_escaped": 0,
            "clipped_production_ticks": 1, "shed_overflow_burnt": 0,
            "weeds_lost": 0, "unexpected_weeds_lost": 0,
        }
        return SimpleNamespace(rewards=rewards, metrics={0: metrics, 1: metrics})

    with patch("harness.compare.play", side_effect=fake_play):
        result = compare("A", "B", [0], both_seats=False, record=False, metrics=True,
                          metric_mechanisms={"animals_escaped": "irrelevant to a hard zero"})

    assert result.priced_loss_per_episode == 0.0
    assert result.unexplained_metrics == ()
    assert result.metric_gate_passed is False


def _fake_play_with_counters(counters_a, counters_b, *, bank_a, bank_b):
    """A play() double where agent_a's seat reports `counters_a` and agent_b's `counters_b`,
    in both orientations. Απόφαση Δ reads two seats, so a double that fills only one is no
    longer enough to exercise the gate."""
    base = {
        "water_weeds_lost": 0, "plant_decay_units_lost": 0, "animals_escaped": 0,
        "clipped_production_ticks": 0, "shed_overflow_burnt": 0,
        "weeds_lost": 0, "unexpected_weeds_lost": 0,
    }
    seat_a = {**base, **counters_a}
    seat_b = {**base, **counters_b}

    def fake_play(a, b, seed, **kwargs):
        del b, seed, kwargs
        if a == "A":  # agent_a plays seat 0
            return SimpleNamespace(rewards=(bank_a, bank_b), metrics={0: seat_a, 1: seat_b})
        return SimpleNamespace(rewards=(bank_b, bank_a), metrics={0: seat_b, 1: seat_a})

    return fake_play


@pytestmark_small_seed_warning
def test_decision_d_still_rejects_v1m_d3_unexplained_escapes():
    """current_phase.md §1 Απόφαση Δ is explicitly not a loosening. v1m Δ3 won the melon race
    economically (+$3,421/ep, W/L 11-1) and was stopped because `animals_escaped` went 0 -> 28
    with no written mechanism. Under Δ the opponent burns far more than the candidate, so the
    priced delta is 0 and the priced leg is satisfied — and the run must *still* fail, on the
    written-mechanism rule alone. 'I don't know why' stays a STOP at any price or difference."""
    fake_play = _fake_play_with_counters(
        {"animals_escaped": 28}, {"animals_escaped": 200, "shed_overflow_burnt": 400},
        bank_a=100_000.0, bank_b=0.0,
    )
    with patch("harness.compare.play", side_effect=fake_play):
        undeclared = compare("A", "B", [0], both_seats=True, record=False, metrics=True)
        declared = compare("A", "B", [0], both_seats=True, record=False, metrics=True,
                            metric_mechanisms={"animals_escaped": "measured FEED clustering"})

    assert undeclared.animals_escaped_a == 56  # 28 per episode x both orientations
    assert undeclared.animals_escaped_b == 400
    # The priced leg alone would wave this through: the opponent loses more than we do.
    assert undeclared.priced_loss_delta == 0.0
    assert undeclared.priced_loss_delta <= undeclared.priced_loss_budget_used
    assert undeclared.unexplained_metrics == ("animals_escaped",)
    assert undeclared.metric_gate_passed is False
    # ...and the mechanism rule is the only thing standing between the two runs.
    assert declared.metric_gate_passed is True


@pytestmark_small_seed_warning
def test_decision_d_mirror_regression_arm_ignores_the_priced_budget():
    """Απόφαση Δ point 3, the v1m.2 Ε1 mirror: a correct market-only fix measures mean_diff ~0
    against our own baseline, which under Απόφαση Α made the budget 10% x ~0 = a few dollars
    against $1,322.9/ep of *inherited* loss — a gate no candidate could ever pass. As a
    regression detector (Απόφαση Β) the mirror keeps the $-verdict and the structural and
    mechanism legs, and drops the priced budget entirely."""
    mechanisms = {
        "shed_overflow_burnt": "pre-existing EOD surplus residual; emit-order changes no occupancy",
        "water_weeds_lost": "background weed RNG",
        "unexpected_weeds_lost": "same background weed mechanism as water_weeds_lost",
    }
    # +$65/ep on $48k banks, against 754 burnt units and 33 lost tiles the baseline also has.
    fake_play = _fake_play_with_counters(
        {"shed_overflow_burnt": 754, "water_weeds_lost": 33, "unexpected_weeds_lost": 33},
        {},
        bank_a=48_065.0, bank_b=48_000.0,
    )
    with patch("harness.compare.play", side_effect=fake_play):
        acceptance = compare("A", "B", [0], both_seats=True, record=False, metrics=True,
                              metric_mechanisms=mechanisms, arm_role="acceptance")
        regression = compare("A", "B", [0], both_seats=True, record=False, metrics=True,
                              metric_mechanisms=mechanisms, arm_role="regression")

    # Identical measurement, identical reporting — only the criterion differs.
    for result in (acceptance, regression):
        assert result.priced_loss_per_episode == pytest.approx(754 * 150.0 + 33 * 300.0)
        assert result.priced_loss_b == 0.0
        assert result.priced_loss_delta == pytest.approx(result.priced_loss_per_episode)
        assert result.priced_loss_budget_used == pytest.approx(6.5)
        assert result.unexplained_metrics == ()
    assert acceptance.arm_role == "acceptance"
    assert acceptance.metric_gate_passed is False  # $1,323/ep against a $6.50 budget
    assert regression.arm_role == "regression"
    assert regression.metric_gate_passed is True   # passes as a regression detector

    # The structural leg is *not* relaxed by the regression role.
    broken = _fake_play_with_counters({"clipped_production_ticks": 1}, {},
                                       bank_a=48_065.0, bank_b=48_000.0)
    with patch("harness.compare.play", side_effect=broken):
        structural = compare("A", "B", [0], both_seats=True, record=False, metrics=True,
                              arm_role="regression")
    assert structural.metric_gate_passed is False


@pytestmark_small_seed_warning
def test_decision_d_rejects_candidate_that_loses_more_than_its_arm_b():
    """The other half of 'Δ is not a loosening': differencing only forgives loss the arm B also
    has. A candidate that burns far more than what it is measured against pays for the excess,
    and the two bounds of priced_loss_budget still apply to that excess."""
    mechanisms = {"shed_overflow_burnt": "declared, so only the priced leg is under test"}
    # 100 burnt units/episode against the bench's 4, on a +$1,000/ep gain: the delta is
    # 96 x $150 = $14,400/ep against a $100/ep budget.
    fake_play = _fake_play_with_counters(
        {"shed_overflow_burnt": 100}, {"shed_overflow_burnt": 4},
        bank_a=51_000.0, bank_b=50_000.0,
    )
    with patch("harness.compare.play", side_effect=fake_play):
        result = compare("A", "B", [0], both_seats=True, record=False, metrics=True,
                          metric_mechanisms=mechanisms, arm_role="acceptance")

    assert result.shed_overflow_burnt_a == 200  # both orientations
    assert result.shed_overflow_burnt_b == 8
    assert result.priced_loss_per_episode == pytest.approx(100 * 150.0)
    assert result.priced_loss_b == pytest.approx(4 * 150.0)
    assert result.priced_loss_delta == pytest.approx(96 * 150.0)
    assert result.priced_loss_budget_used == pytest.approx(100.0)
    assert result.unexplained_metrics == ()
    assert result.metric_gate_passed is False


@pytestmark_small_seed_warning
def test_compare_rejects_invalid_arm_role():
    with pytest.raises(ValueError, match="arm_role"):
        compare("A", "B", [0], record=False, arm_role="mirror")


@pytestmark_small_seed_warning
def test_compare_reads_arm_b_counters_from_agent_b_seat_in_each_orientation():
    """Απόφαση Δ point 4 — the B-side counters must follow agent_b's seat the same way the
    _a counters follow agent_a's, or the delta silently subtracts our own losses from
    themselves in the swapped orientation."""
    def fake_play(a, b, seed, **kwargs):
        del b, seed, kwargs
        seat_a = {"shed_overflow_burnt": 10, "animals_escaped": 1, "weeds_lost": 5}
        seat_b = {"shed_overflow_burnt": 70, "animals_escaped": 2, "weeds_lost": 9}
        if a == "A":
            return SimpleNamespace(rewards=(150.0, 100.0), metrics={0: seat_a, 1: seat_b})
        return SimpleNamespace(rewards=(100.0, 150.0), metrics={0: seat_b, 1: seat_a})

    with patch("harness.compare.play", side_effect=fake_play):
        result = compare("A", "B", [0], both_seats=True, record=False, metrics=True)

    assert result.shed_overflow_burnt_a == 20 and result.shed_overflow_burnt_b == 140
    assert result.animals_escaped_a == 2 and result.animals_escaped_b == 4
    assert result.weeds_lost_a == 10 and result.weeds_lost_b == 18


@pytestmark_small_seed_warning
def test_compare_metrics_off_leaves_arm_b_counters_unmeasured():
    """review.md C3, extended to the B side: 'not measured' and 'measured, zero' must stay
    distinguishable, or a delta computed from a missing B side reads as an absolute loss."""
    def fake_play(a, b, seed, **kwargs):
        del b, seed, kwargs
        return SimpleNamespace(rewards=(150.0, 100.0) if a == "A" else (100.0, 150.0))

    with patch("harness.compare.play", side_effect=fake_play):
        result = compare("A", "B", [0], both_seats=False, record=False)

    assert result.shed_overflow_burnt_b is None
    assert result.animals_escaped_b is None
    assert result.priced_loss_b is None
    assert result.priced_loss_delta is None


@pytestmark_small_seed_warning
def test_compare_go_requires_holdout_confirm_stage_metrics_and_clean_gate(tmp_path):
    """plan.md §1.5.3 acceptance criterion — a GO must never be readable off a dev-screen
    report, nor off a holdout report where the metric gate didn't run, nor when the metric
    gate itself failed, regardless of how clean the $-verdict looks."""
    def fake_play(a, b, seed, **kwargs):
        diff = 50.0 if seed % 2 == 0 else 40.0
        rewards = (100.0 + diff, 100.0) if a == "A" else (100.0, 100.0 + diff)
        metrics = {0: {"water_weeds_lost": 0, "plant_decay_units_lost": 0},
                   1: {"water_weeds_lost": 0, "plant_decay_units_lost": 0}}
        return SimpleNamespace(rewards=rewards, metrics=metrics)

    ledger = tmp_path / "confirm_log.jsonl"
    evidence = tmp_path / "gates"
    _write_dev_screen_evidence(evidence)
    # An unmetered diagnostic does not consume the complete HOLDOUT_SEEDS ledger slot, so the
    # subsequent measured both-seats confirm can use the same one allowed final sample.
    holdout = list(HOLDOUT_SEEDS)

    with patch("harness.compare.play", side_effect=fake_play):
        dev_screen = compare("A", "B", range(12), both_seats=False, record=False,
                              metrics=True, min_effect=10.0, stage="dev-screen")
        no_metrics = compare("A", "B", holdout, both_seats=False, record=False,
                              min_effect=10.0, stage="holdout-confirm",
                              confirm_ledger_path=ledger, screen_evidence_dir=evidence)
        confirmed = compare("A", "B", holdout, both_seats=True, record=False,
                             metrics=True, min_effect=10.0, stage="holdout-confirm",
                             confirm_ledger_path=ledger, screen_evidence_dir=evidence)

    assert dev_screen.verdict == "IMPROVED"
    assert dev_screen.go is False  # clean verdict, wrong stage
    assert no_metrics.verdict == "IMPROVED"
    assert no_metrics.go is False  # clean verdict, metric gate never ran
    assert confirmed.verdict == "IMPROVED"
    assert confirmed.metric_gate_passed is True
    assert confirmed.go is True


@pytestmark_small_seed_warning
def test_compare_go_false_when_metric_gate_fails_even_at_holdout_confirm(tmp_path):
    def fake_play(a, b, seed, **kwargs):
        diff = 50.0 if seed % 2 == 0 else 40.0
        rewards = (100.0 + diff, 100.0) if a == "A" else (100.0, 100.0 + diff)
        metrics = {0: {"water_weeds_lost": 1, "plant_decay_units_lost": 0},
                   1: {"water_weeds_lost": 1, "plant_decay_units_lost": 0}}
        return SimpleNamespace(rewards=rewards, metrics=metrics)

    with patch("harness.compare.play", side_effect=fake_play):
        result = compare("A", "B", list(HOLDOUT_SEEDS), both_seats=True, record=False,
                          metrics=True, min_effect=10.0, stage="holdout-confirm",
                          confirm_ledger_path=tmp_path / "confirm_log.jsonl")

    assert result.verdict == "IMPROVED"
    assert result.metric_gate_passed is False
    assert result.go is False


# --------------------------------------------------------------------------- checkpoints


def test_checkpoint_uses_unique_namespace_and_preserves_fingerprint(tmp_path):
    checkpoint_main = create_checkpoint(
        "v0",
        source_root=REPO_ROOT,
        checkpoint_root=tmp_path,
    )
    source = checkpoint_main.read_text(encoding="utf-8")
    assert "from agent_checkpoint_v0.policy import agent" in source
    assert agent_fingerprint(str(checkpoint_main)) == agent_fingerprint(str(REPO_ROOT / "main.py"))
    assert resolve_agent(str(checkpoint_main), entrypoint="agent").__name__ == "agent"


def test_checkpoint_fingerprint_detects_agent_code_change(tmp_path):
    """A plain (non-checkpoint, no manifest.json) copy of the agent package with a source
    edit must fingerprint differently from the original agent/ — agent_fingerprint()'s
    baseline content-sensitivity, kept separate from the checkpoint-tamper-detection
    behavior covered by test_checkpoint_fingerprint_raises_on_tampered_checkpoint below."""
    shutil.copytree(REPO_ROOT / "agent", tmp_path / "agent")
    copied_main = tmp_path / "main.py"
    copied_main.write_text((REPO_ROOT / "main.py").read_text(encoding="utf-8"), encoding="utf-8")
    policy_path = tmp_path / "agent" / "policy.py"
    policy_path.write_text(policy_path.read_text(encoding="utf-8") + "\n# changed strategy\n", encoding="utf-8")
    assert agent_fingerprint(str(copied_main)) != agent_fingerprint(str(REPO_ROOT / "main.py"))


def test_checkpoint_fingerprint_raises_on_tampered_checkpoint(tmp_path):
    """review.md H3 — immutability was only a naming convention: nothing verified a
    checkpoint's package still matched its manifest at compare() time. A checkpoint edited
    after creation must raise instead of silently passing as the immutable version it
    claims to be."""
    checkpoint_main = create_checkpoint(
        "v0",
        source_root=REPO_ROOT,
        checkpoint_root=tmp_path,
    )
    checkpoint_policy = checkpoint_main.parent / "agent_checkpoint_v0" / "policy.py"
    checkpoint_policy.write_text(
        checkpoint_policy.read_text(encoding="utf-8") + "\n# changed strategy\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="does not match its manifest"):
        agent_fingerprint(str(checkpoint_main))


def test_compare_rejects_identical_checkpoint_fingerprints(tmp_path):
    checkpoint_main = create_checkpoint(
        "v0",
        source_root=REPO_ROOT,
        checkpoint_root=tmp_path,
    )
    with pytest.raises(ValueError, match="identical code fingerprints"):
        compare(str(REPO_ROOT / "main.py"), str(checkpoint_main), [0])


# --------------------------------------------------------------------------- profile


def test_timed_preserves_agent_name():
    """review.md L4 — functools.wraps so the wrapped agent's name (used in replay filenames)
    doesn't collapse to the generic 'wrapped'."""
    def my_agent(obs):
        return None

    wrapped, _times = timed(my_agent)
    assert wrapped.__name__ == "my_agent"


def test_profile_report_known_values():
    times = [0.1, 0.2, 0.05, 1.5, 0.3]
    stats = report(times, act_timeout=1.0)
    assert stats["n"] == 5
    assert stats["max"] == 1.5
    assert stats["turn1"] == 0.1
    assert stats["total"] == pytest.approx(sum(times))
    assert stats["overage_used"] == pytest.approx(0.5)  # only the 1.5s turn exceeds actTimeout
    assert stats["p99"] == 1.5


def test_profile_report_empty():
    stats = report([])
    assert stats["n"] == 0
    assert stats["turn1"] == 0.0
    assert stats["overage_used"] == 0.0
