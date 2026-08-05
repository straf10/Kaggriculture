"""analysis/replay_profile.py (plan.md §1.5.5): team selection + per-day profile extraction."""
import pandas as pd

from analysis.replay_profile import (
    _tile_counts,
    extract_profile,
    select_episode_seats,
    select_top_teams,
    wilson_lower_bound,
)


def test_wilson_lower_bound_more_games_at_same_rate_gives_higher_confidence():
    """A 6/8 record is a noisier 75% than 60/80 — the lower bound must reflect that."""
    small = wilson_lower_bound(6, 8)
    large = wilson_lower_bound(60, 80)
    assert large > small


def test_wilson_lower_bound_zero_games_is_zero():
    assert wilson_lower_bound(0, 0) == 0.0


def test_select_top_teams_excludes_below_min_games_and_self_play():
    episodes = pd.DataFrame([
        # team 1 (strong, n=8): 8 wins over team 2
        *[{"type": "EPISODE_TYPE_PUBLIC", "team_0": 1, "team_1": 2, "bank_0": 100, "bank_1": 10}
          for _ in range(8)],
        # team 3 (also strong, n=7 only — below MIN_GAMES, must be excluded)
        *[{"type": "EPISODE_TYPE_PUBLIC", "team_0": 3, "team_1": 2, "bank_0": 100, "bank_1": 10}
          for _ in range(7)],
        # self-play validation episode for team 1 — must not count towards its record
        {"type": "EPISODE_TYPE_VALIDATION", "team_0": 1, "team_1": 1, "bank_0": 50, "bank_1": 50},
        # team_0 == team_1 but type PUBLIC (shouldn't happen, but must still be excluded)
        {"type": "EPISODE_TYPE_PUBLIC", "team_0": 4, "team_1": 4, "bank_0": 50, "bank_1": 50},
    ])
    top = select_top_teams(episodes)
    assert 1 in top
    assert 3 not in top
    assert 4 not in top


def test_select_episode_seats_only_top_team_side_and_only_with_replay():
    episodes = pd.DataFrame([
        {"episode_id": 10, "type": "EPISODE_TYPE_PUBLIC", "team_0": 1, "team_1": 2,
         "bank_0": 100, "bank_1": 10},
        {"episode_id": 11, "type": "EPISODE_TYPE_PUBLIC", "team_0": 2, "team_1": 1,
         "bank_0": 10, "bank_1": 100},
        # replay not downloaded for this one yet — must be excluded regardless of team
        {"episode_id": 12, "type": "EPISODE_TYPE_PUBLIC", "team_0": 1, "team_1": 2,
         "bank_0": 100, "bank_1": 10},
    ])
    pairs = select_episode_seats(episodes, top_teams={1}, have_replay={10, 11})
    assert set(pairs) == {(10, 0), (11, 1)}


def test_tile_counts_ignores_locked_empty_and_unoccupied_structures():
    tiles = [
        ["LOCKED", None, {"kind": "PLANT", "crop": "MELON"}],
        [{"kind": "COOP"}, {"kind": "COOP", "animal": "GOOSE"}, {"kind": "PASTURE", "animal": "COW"}],
    ]
    plants, animals = _tile_counts(tiles)
    assert plants == {"MELON": 1}
    assert animals == {"GOOSE": 1, "COW": 1}


PASS = {"farmer": ["PASS"], "hands": [], "market": []}


def _finish(env, first_action=PASS):
    actions = [first_action, PASS]
    while not env.done:
        env.step(actions)
        actions = [PASS, PASS]
    return env.toJSON()


def test_extract_profile_first_quadrant_is_day_zero_and_daily_rows_cover_every_day():
    from kaggle_environments import make
    env = make("kaggriculture", configuration={"seed": 0, "episodeSteps": 48, "turnsPerDay": 24})
    replay = _finish(env)

    profile = extract_profile(replay, seat=0)
    assert len(profile["daily"]) == 2
    assert profile["first_quadrant_day"][1] == 0
    assert profile["daily"][0]["day"] == 0
    assert profile["daily"][1]["day"] == 1
