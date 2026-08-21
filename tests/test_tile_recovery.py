"""Tests for the tile-validity checker and the desync recovery overlay (§7.2 component (i))."""
import pytest
from agent.tape_overlay import _tile_valid, _tile_recovery, TapeOverlay


# --- _tile_valid ---

class TestTileValid:
    def test_water_unwatered_plant(self):
        tile = {"kind": "PLANT", "watered_today": False}
        assert _tile_valid("WATER", tile) is True

    def test_water_watered_plant(self):
        tile = {"kind": "PLANT", "watered_today": True}
        assert _tile_valid("WATER", tile) is False

    def test_water_weed(self):
        tile = {"kind": "WEED"}
        assert _tile_valid("WATER", tile) is False

    def test_water_empty(self):
        assert _tile_valid("WATER", None) is False

    def test_plant_empty(self):
        assert _tile_valid("PLANT", None) is True

    def test_plant_on_plant(self):
        tile = {"kind": "PLANT", "watered_today": False}
        assert _tile_valid("PLANT", tile) is False

    def test_plant_on_weed(self):
        tile = {"kind": "WEED"}
        assert _tile_valid("PLANT", tile) is False

    def test_dig_plant(self):
        tile = {"kind": "PLANT"}
        assert _tile_valid("DIG", tile) is True

    def test_dig_weed(self):
        tile = {"kind": "WEED"}
        assert _tile_valid("DIG", tile) is True

    def test_dig_empty(self):
        assert _tile_valid("DIG", None) is False

    def test_dig_animal(self):
        tile = {"kind": "PASTURE", "animal": "COW"}
        assert _tile_valid("DIG", tile) is False

    def test_harvest_with_yield(self):
        tile = {"kind": "PLANT", "yield_units": 3}
        assert _tile_valid("HARVEST", tile) is True

    def test_harvest_no_yield(self):
        tile = {"kind": "PLANT", "yield_units": 0}
        assert _tile_valid("HARVEST", tile) is False

    def test_non_tile_op_always_valid(self):
        assert _tile_valid("NORTH", None) is True
        assert _tile_valid("PASS", None) is True


# --- _tile_recovery ---

class TestTileRecovery:
    def test_water_weed_digs(self):
        tile = {"kind": "WEED"}
        assert _tile_recovery("WATER", tile) == ["DIG"]

    def test_water_watered_plant_passes(self):
        tile = {"kind": "PLANT", "watered_today": True}
        assert _tile_recovery("WATER", tile) == ["PASS"]

    def test_water_empty_passes(self):
        assert _tile_recovery("WATER", None) == ["PASS"]

    def test_plant_on_dry_plant_waters(self):
        tile = {"kind": "PLANT", "watered_today": False}
        assert _tile_recovery("PLANT", tile) == ["WATER"]

    def test_plant_on_watered_plant_passes(self):
        tile = {"kind": "PLANT", "watered_today": True}
        assert _tile_recovery("PLANT", tile) == ["PASS"]

    def test_plant_on_weed_digs(self):
        tile = {"kind": "WEED"}
        assert _tile_recovery("PLANT", tile) == ["DIG"]

    def test_dig_empty_passes(self):
        assert _tile_recovery("DIG", None) == ["PASS"]

    def test_harvest_dry_plant_waters(self):
        tile = {"kind": "PLANT", "yield_units": 0, "watered_today": False}
        assert _tile_recovery("HARVEST", tile) == ["WATER"]

    def test_harvest_watered_plant_passes(self):
        tile = {"kind": "PLANT", "yield_units": 0, "watered_today": True}
        assert _tile_recovery("HARVEST", tile) == ["PASS"]

    def test_harvest_empty_passes(self):
        assert _tile_recovery("HARVEST", None) == ["PASS"]


# --- _recover_tile_actions (integration) ---

class TestRecoverTileActions:
    @staticmethod
    def _make_snapshot(tiles, farmer_pos=(0, 0), hand_positions=()):
        class FakeSnapshot:
            pass
        s = FakeSnapshot()
        s.my_tiles = tiles
        s.farmer_pos = farmer_pos
        s.hand_positions = hand_positions
        return s

    def test_valid_actions_unchanged(self):
        tiles = [[None, {"kind": "PLANT", "watered_today": False}]]
        snap = self._make_snapshot(tiles, farmer_pos=(0, 0), hand_positions=((1, 0),))
        farmer, hands = TapeOverlay._recover_tile_actions(
            snap, ["PLANT", "WHEAT"], [["WATER"]])
        assert farmer == ["PLANT", "WHEAT"]
        assert hands == [["WATER"]]

    def test_farmer_water_weed_becomes_dig(self):
        tiles = [[{"kind": "WEED"}]]
        snap = self._make_snapshot(tiles, farmer_pos=(0, 0))
        farmer, hands = TapeOverlay._recover_tile_actions(
            snap, ["WATER"], [])
        assert farmer == ["DIG"]

    def test_hand_plant_on_plant_becomes_water(self):
        tiles = [[None, {"kind": "PLANT", "watered_today": False}]]
        snap = self._make_snapshot(tiles, farmer_pos=(0, 0),
                                   hand_positions=((1, 0),))
        farmer, hands = TapeOverlay._recover_tile_actions(
            snap, ["PASS"], [["PLANT", "MELON"]])
        assert farmer == ["PASS"]
        assert hands == [["WATER"]]

    def test_non_tile_op_untouched(self):
        tiles = [[None]]
        snap = self._make_snapshot(tiles, farmer_pos=(0, 0))
        farmer, hands = TapeOverlay._recover_tile_actions(
            snap, ["NORTH"], [])
        assert farmer == ["NORTH"]

    def test_multiple_hands_mixed(self):
        tiles = [[{"kind": "WEED"}, {"kind": "PLANT", "watered_today": True}, None]]
        snap = self._make_snapshot(
            tiles, farmer_pos=(2, 0),
            hand_positions=((0, 0), (1, 0)))
        farmer, hands = TapeOverlay._recover_tile_actions(
            snap, ["PLANT", "WHEAT"],
            [["WATER"], ["PLANT", "MELON"]])
        assert farmer == ["PLANT", "WHEAT"]
        assert hands[0] == ["DIG"]
        assert hands[1] == ["PASS"]
