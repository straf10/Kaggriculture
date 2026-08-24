"""Tests for harness/town_pin.py and its integration into compare() (§Β.0′).

The pin exists because shop unlock and weed spawning share one per-day RNG stream
(MASTERPLAN §2 #7), so an occupancy change on *either* farm re-rolls the whole shop sequence
and an unpinned occupancy gate silently compares two different towns. Two things therefore
have to be true and stay true, and both are tested here rather than argued:

1. The patch is **exactly reversible** — town_pin monkeypatches the installed engine module,
   so a leaked patch would contaminate every later test and every later gate in the process.
2. Both arms of a comparison play the **same** town on a given seed, and which town that was
   is recorded — a pinned verdict is only valid for the towns actually pinned.
"""
import contextlib
from types import SimpleNamespace
from unittest.mock import patch

import kaggle_environments.envs.kaggriculture.kaggriculture as engine
import pytest
from kaggle_environments import make

from harness.compare import compare
from harness.play import play
from harness.town_pin import (
    SHOP_TYPES,
    basket_for,
    no_shops,
    pinned_shops,
    pinned_town,
    schedule_for,
    schedule_for_mode,
)

pytestmark_small_seed_warning = pytest.mark.filterwarnings(
    "ignore:compare\\(\\).*seeds.*:UserWarning"
)

# End of day 2 is the first shop unlock (next_day % townShopUnlockInterval == 0 with the
# default interval of 3); end of day 5 is the second. 145 steps = 6 full days + 1, i.e. the
# cheapest episode that shows a *sequence* of unlocks rather than a single draw.
TWO_UNLOCK_STEPS = 145


# --------------------------------------------------------------------------- reversibility


def test_pinned_shops_restores_end_of_day_exactly():
    original = engine._end_of_day
    with pinned_shops(schedule_for(0)):
        assert engine._end_of_day is not original
    assert engine._end_of_day is original


def test_pin_restores_end_of_day_even_when_the_body_raises():
    original = engine._end_of_day
    with pytest.raises(RuntimeError):
        with pinned_shops(schedule_for(0)):
            raise RuntimeError("boom")
    assert engine._end_of_day is original


def test_pins_nest_and_unwind_in_order():
    """The context manager snapshots what was installed **on entry**, not a module-level
    original — so an inner pin restores the outer one rather than the unpatched engine."""
    original = engine._end_of_day
    with pinned_shops(schedule_for(0)):
        outer = engine._end_of_day
        with no_shops():
            assert engine._end_of_day is not outer
        assert engine._end_of_day is outer
    assert engine._end_of_day is original


def test_pinned_town_with_mode_none_patches_nothing():
    """`town_pin=None` (the default everywhere) must leave the engine untouched, so every
    result produced before §Β.0′ stays reproducible byte-for-byte."""
    original = engine._end_of_day
    with pinned_town(None, None):
        assert engine._end_of_day is original
    assert engine._end_of_day is original


# --------------------------------------------------------------------------- what it pins


def _played_town(seed=0, steps=TWO_UNLOCK_STEPS):
    """The town after a short two-pass episode, read off the engine's own state (play() does
    not surface the town, and recording a replay just to read one key would be slower)."""
    env = make("kaggriculture", configuration={"seed": seed, "episodeSteps": steps})
    env.run(["pass", "pass"])
    return list(env.state[0].observation.town["unlocked_shops"])


def test_pinned_shops_forces_the_requested_unlock_order():
    schedule = ["YARN_STORE", "BAKERY"]
    with pinned_shops(schedule):
        assert _played_town() == schedule


def test_pinned_shops_accepts_duplicates_for_the_post_balance_change_regime():
    """The announced balance change draws shops **with replacement**; the current engine draws
    without. A pinned basket must be able to produce a town the current engine cannot."""
    with pinned_shops(["YARN_STORE", "YARN_STORE"]):
        assert _played_town() == ["YARN_STORE", "YARN_STORE"]


def test_no_shops_leaves_the_town_empty():
    with no_shops():
        assert _played_town() == []


def test_unpinned_episode_still_draws_its_own_town():
    """The floor case: without a pin the engine keeps drawing normally — so the pinned runs
    above are measuring the pin, not an artefact of the shortened episode."""
    unlocked = _played_town()
    assert len(unlocked) == 2
    assert all(shop in SHOP_TYPES for shop in unlocked)


def test_the_same_pin_survives_a_full_play_call():
    """The pin has to hold through harness.play (the path every gate actually uses), not only
    through a bare env.run."""
    with pinned_shops(["YARN_STORE", "BAKERY"]):
        result = play("pass", "pass", 0, steps=TWO_UNLOCK_STEPS, record=False, metrics=False)
        assert result.clean
        assert _played_town() == ["YARN_STORE", "BAKERY"]


# --------------------------------------------------------------------------- seed -> town


def test_schedule_for_is_deterministic_and_a_full_permutation():
    assert schedule_for(7) == schedule_for(7)
    assert sorted(schedule_for(7)) == sorted(SHOP_TYPES)


def test_basket_for_is_deterministic_and_drawn_with_replacement():
    assert basket_for(7) == basket_for(7)
    assert len(basket_for(7)) == 8
    assert set(basket_for(7)) <= set(SHOP_TYPES)
    # With replacement, *some* seed in a small range must repeat a type — otherwise the helper
    # is silently producing permutations and the post-balance-change regime is not modelled.
    assert any(len(set(basket_for(seed))) < 8 for seed in range(20))


def test_pins_differ_across_seeds():
    """§Β.0′ point 1: pinning a *constant* town samples one town n times instead of reducing
    noise. Both mode helpers must therefore be functions of the seed."""
    assert len({tuple(schedule_for_mode("schedule", seed)) for seed in range(8)}) > 1
    assert len({tuple(schedule_for_mode("basket", seed)) for seed in range(8)}) > 1


def test_schedule_for_mode_none_and_no_shops():
    assert schedule_for_mode(None, 0) is None
    assert schedule_for_mode("no_shops", 0) == []


def test_schedule_for_mode_rejects_unknown_mode():
    with pytest.raises(ValueError, match="unknown mode"):
        schedule_for_mode("nope", 0)


# --------------------------------------------------------------------------- compare() wiring


def _fake_play(a, b, seed, **kwargs):
    rewards = (100.0, 50.0) if a == "A" else (50.0, 100.0)
    return SimpleNamespace(rewards=rewards, metrics={0: {}, 1: {}})


@pytestmark_small_seed_warning
def test_compare_rejects_unknown_town_pin():
    with pytest.raises(ValueError, match="town_pin"):
        compare("A", "B", [0], record=False, town_pin="nope")


@pytestmark_small_seed_warning
def test_compare_pins_the_same_town_for_both_orientations():
    """The whole point of §Β.0′: A@0/B@1 and B@0/A@1 must play inside ONE pin per seed. If the
    two orientations opened separate pins with different schedules, the comparison would be
    between two towns again — the exact defect the pin removes."""
    events = []

    @contextlib.contextmanager
    def recording_pin(mode, schedule):
        events.append(("enter", mode, tuple(schedule or ())))
        try:
            yield
        finally:
            events.append(("exit", mode, tuple(schedule or ())))

    def spying_play(a, b, seed, **kwargs):
        events.append(("play", a, seed))
        return _fake_play(a, b, seed, **kwargs)

    with patch("harness.compare.pinned_town", recording_pin), \
         patch("harness.compare.play", side_effect=spying_play):
        compare("A", "B", [0, 1], both_seats=True, record=False, town_pin="basket")

    for seed in (0, 1):
        expected = tuple(basket_for(seed))
        start = events.index(("enter", "basket", expected))
        end = events.index(("exit", "basket", expected))
        assert events[start + 1:end] == [("play", "A", seed), ("play", "B", seed)]


@pytestmark_small_seed_warning
def test_compare_records_the_pinned_towns_in_meta_and_result(tmp_path):
    """§Β.0′ point 2 (G15): a results.jsonl must say which towns produced it, not merely that
    a pin was on — a pinned verdict only holds for the towns actually pinned."""
    import json

    with patch("harness.compare.play", side_effect=_fake_play):
        result = compare("A", "B", [0, 1], both_seats=False, record=False,
                         run_dir=tmp_path, town_pin="schedule")

    assert result.town_pin == "schedule"
    assert result.town_schedules == {"0": schedule_for(0), "1": schedule_for(1)}
    meta = json.loads((tmp_path / "results.jsonl").read_text(encoding="utf-8").splitlines()[0])
    assert meta["town_pin"] == "schedule"
    assert meta["town_schedules"]["0"] == schedule_for(0)


@pytestmark_small_seed_warning
def test_compare_unpinned_records_no_towns(tmp_path):
    import json

    with patch("harness.compare.play", side_effect=_fake_play):
        result = compare("A", "B", [0], both_seats=False, record=False, run_dir=tmp_path)

    assert result.town_pin is None
    assert result.town_schedules == {}
    meta = json.loads((tmp_path / "results.jsonl").read_text(encoding="utf-8").splitlines()[0])
    assert meta["town_pin"] is None


@pytestmark_small_seed_warning
def test_compare_resume_rejects_town_pin_mismatch(tmp_path):
    """Resuming a pinned run as unpinned (or under another mode) would average two different
    town distributions into one mean_diff while every seed still looks 'done'."""
    with patch("harness.compare.play", side_effect=_fake_play):
        compare("A", "B", [0], both_seats=False, record=False, run_dir=tmp_path,
                town_pin="basket")

    with patch("harness.compare.play", side_effect=_fake_play):
        with pytest.raises(ValueError, match="town_pin"):
            compare("A", "B", [1], both_seats=False, record=False, run_dir=tmp_path,
                    resume=True)
        with pytest.raises(ValueError, match="town_pin"):
            compare("A", "B", [1], both_seats=False, record=False, run_dir=tmp_path,
                    resume=True, town_pin="schedule")


@pytestmark_small_seed_warning
def test_compare_resume_of_a_pre_pin_run_still_works(tmp_path):
    """A results.jsonl written before §Β.0′ has no town_pin key at all; it is an unpinned run
    and must keep resuming as one instead of tripping the new check."""
    import json

    with patch("harness.compare.play", side_effect=_fake_play):
        compare("A", "B", [0], both_seats=False, record=False, run_dir=tmp_path)

    path = tmp_path / "results.jsonl"
    lines = path.read_text(encoding="utf-8").splitlines()
    meta = json.loads(lines[0])
    del meta["town_pin"]
    del meta["town_schedules"]
    path.write_text("\n".join([json.dumps(meta), *lines[1:]]) + "\n", encoding="utf-8")

    with patch("harness.compare.play", side_effect=_fake_play):
        result = compare("A", "B", [0, 1], both_seats=False, record=False, run_dir=tmp_path,
                         resume=True)
    assert result.n_effective == 2
