"""analysis/b1_top_profile.py — the §5.1 target-profile rewrite.

Day-snapshot / sell-calendar / aggregation logic is tested against hand-crafted replay
dicts (same style as tests/test_s9_live_read_reader.py::_fake_replay) so it doesn't need
a full engine run. `build_profile`'s ledger integration is tested against one real
engine episode (tests/fixtures/replays.py), so the revenue/units_sold path is exercised
against genuine market mechanics, not a stub.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from analysis import b1_top_profile as prof  # noqa: E402
from fixtures.replays import write_synthetic_replay  # noqa: E402


def _tile(kind, crop=None, animal=None):
    return {"kind": kind, "crop": crop, "animal": animal}


def _farm(money, tiles, hands, quadrants):
    return {"money": money, "tiles": tiles, "hires_today": 0,
            "hands": ["h"] * hands, "unlocked_quadrants": quadrants[:]}


def _obs(day, farm0, farm1, inventory):
    # Shared fields (farms, market) live on seat 0's observation only — s9_market_ledger
    # and the ROADMAP §4 engine note both read seat 0 for these, never seat 1's.
    return {"player": 0, "day": day, "farms": [farm0, farm1],
            "market": {"inventory": inventory}}


def _step(day, farm0, farm1, market=None, inventory=None):
    inventory = inventory or {"WHEAT": 10, "MELON": 10}
    cell0 = {"observation": _obs(day, farm0, farm1, inventory),
             "action": {"farmer": [], "hands": [], "market": market or []}}
    cell1 = {"observation": {"player": 1, "day": day}, "action": {"market": []}}
    return [cell0, cell1]


_DUMMY_OPP = _farm(0.0, [[None]], 0, ["NW"])


def _fake_steps():
    """3 days, seat 0 is the traced team; seat 1 is an idle dummy opponent."""
    day1_tiles = [[_tile("PLANT", crop="WHEAT"), None]]
    day2_tiles = [[_tile("PLANT", crop="WHEAT"), _tile("PLANT", crop="MELON")]]
    day3_tiles = [[_tile("PLANT", crop="WHEAT"), _tile("PASTURE", animal="COW")]]
    return [
        _step(0, _farm(100.0, [[None]], 1, ["NW"]), _DUMMY_OPP),  # step 0, never read (steps[1:])
        _step(1, _farm(120.0, day1_tiles, 1, ["NW"]), _DUMMY_OPP, market=[["SELL", "WHEAT", 3]]),
        _step(1, _farm(130.0, day1_tiles, 2, ["NW"]), _DUMMY_OPP),
        _step(2, _farm(200.0, day2_tiles, 2, ["NW", "NE"]), _DUMMY_OPP, market=[["SELL", "WHEAT", 5]]),
        _step(3, _farm(300.0, day3_tiles, 3, ["NW", "NE"]), _DUMMY_OPP, market=[["SELL", "MELON", 2]]),
    ]


def test_day_snapshots_take_end_of_day_state():
    steps = _fake_steps()
    snaps = prof._day_snapshots(steps, 0)
    assert snaps[1]["money"] == 130.0  # second step-1 snapshot overwrote the first
    assert snaps[1]["hands"] == 2
    assert snaps[2]["quadrants"] == 2
    assert snaps[3]["crop_tiles"] == {"WHEAT": 1}
    assert snaps[3]["animals"] == {"COW": 1}


def test_profile_seat_money_tiles_hands_at_checkpoints():
    steps = _fake_steps()
    p = prof.profile_seat({"steps": steps}, 0)
    # day 5 has no snapshot -> carries forward the last one on/before it (day 3)
    assert p["money_at"]["5"] == 300.0
    assert p["money_at"]["end"] == 300.0
    assert p["tiles_at"]["5"] == 1
    assert p["hands_at"]["5"] == 3
    assert p["quadrants_final"] == 2


def test_profile_seat_first_quadrant_and_animal_day():
    steps = _fake_steps()
    p = prof.profile_seat({"steps": steps}, 0)
    assert p["first_quadrant_day"]["2"] == 2
    assert "3" not in p["first_quadrant_day"]  # never unlocked
    assert p["first_animal_day"]["COW"] == 3
    assert p["animals_peak"]["COW"] == 1


def test_profile_seat_tile_days_sums_across_days():
    steps = _fake_steps()
    p = prof.profile_seat({"steps": steps}, 0)
    # WHEAT planted on days 1,2,3 -> 3 tile-days; MELON only day 2 -> 1
    assert p["tile_days"]["WHEAT"] == 3
    assert p["tile_days"]["MELON"] == 1


def test_profile_seat_sell_calendar_first_day_and_batch():
    steps = _fake_steps()
    p = prof.profile_seat({"steps": steps}, 0)
    assert p["first_sell_day"]["WHEAT"] == 1
    assert p["batch_median"]["WHEAT"] == 4  # median of orders 3 and 5
    assert p["sell_orders"]["WHEAT"] == 2
    assert p["first_sell_day"]["MELON"] == 3


# --------------------------------------------------------------------------- aggregation

def test_agg_team_medians_scalar_and_dict_fields():
    profiles = [
        {"final_money": 100.0, "money_at": {"5": 20.0, "end": 100.0}},
        {"final_money": 200.0, "money_at": {"5": 40.0, "end": 200.0}},
        {"final_money": 300.0, "money_at": {"5": 60.0, "end": 300.0}},
    ]
    assert prof._agg_team(profiles, "final_money") == 200.0
    assert prof._agg_team(profiles, "money_at") == {"5": 40.0, "end": 200.0}


def test_range_across_teams_is_never_pooled():
    team_aggs = {
        "A": {"final_money": 100.0, "tile_days": {"WHEAT": 50}},
        "B": {"final_money": 300.0, "tile_days": {"WHEAT": 150, "MELON": 10}},
    }
    assert prof._range_across_teams(team_aggs, "final_money") == [100.0, 300.0]
    assert prof._range_across_teams(team_aggs, "tile_days") == {
        "WHEAT": [50, 150], "MELON": [10, 10],
    }


# --------------------------------------------------------------------------- end to end

def test_build_profile_end_to_end_uses_real_ledger(tmp_path):
    sub_dir = tmp_path / "live_TOP"
    sub_dir.mkdir()
    sell_melon = lambda _i: {"farmer": ["PASS"], "hands": [], "market": [["SELL", "MELON", 4]]}
    p1 = write_synthetic_replay(sub_dir, 501, teams=("STRAF", "TopTeam"), seed=1,
                                episode_steps=40, seat1_action=sell_melon, gzip_it=False)
    selection = {"TopTeam": [{"episode_id": 501, "seat": 1, "path": str(p1)}]}

    profile = prof.build_profile(selection)
    assert "TopTeam" in profile["teams"]
    assert profile["teams"]["TopTeam"]["episodes"] == 1
    assert "range_across_teams" in profile
    assert "generated" in profile["verdict"] or "traces" in profile["verdict"]


def test_main_writes_expected_json(tmp_path, monkeypatch, capsys):
    sub_dir = tmp_path / "live_TOP"
    sub_dir.mkdir()
    p1 = write_synthetic_replay(sub_dir, 601, teams=("STRAF", "TopTeam"), seed=2, episode_steps=20)
    sel_path = tmp_path / "manifest.json"
    sel_path.write_text(json.dumps({
        "selection": {"TopTeam": [{"episode_id": 601, "seat": 1, "path": str(p1)}]},
    }))
    out_path = tmp_path / "out.json"

    monkeypatch.setattr(sys, "argv", ["b1_top_profile.py", "--selection", str(sel_path),
                                       "--out", str(out_path)])
    rc = prof.main()
    assert rc == 0
    written = json.loads(out_path.read_text())
    assert written["teams"]["TopTeam"]["episodes"] == 1
    assert "verdict" in written and "range_across_teams" in written
