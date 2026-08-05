"""Tests for the harness itself (review.md M7). The harness is the instrument every v1a-v1e
go/no-go decision (plan.md §3.3) will be read off of; before this file it had zero coverage.
Fast fake/tiny agents throughout (steps<=6) so this suite stays quick.
"""
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from harness.checkpoint import agent_fingerprint, create_checkpoint
from harness.compare import compare
from harness.play import play, resolve_agent
from harness.profile import report, timed

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
    assert agent_fingerprint(str(checkpoint_main)) != agent_fingerprint(str(REPO_ROOT / "main.py"))


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
