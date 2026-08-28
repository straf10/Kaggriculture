"""ROADMAP §3.1 rule 1, corrected 2026-08-28 (S16 task 4, docs/plans/s16_slot_comparison.md).

The old wording — "a one-tile difference on either farm re-rolls the whole remaining shop
sequence" — overclaims. `_spawn_weeds` (kaggriculture.py:836-840) calls `rng.random()` once
per tile **only when that tile is `None`**:

    if farm["tiles"][y][x] is None and rng.random() < weed_chance: ...

So the number of draws consumed by one farm's weed pass equals the count of `None` tiles on
that farm, not a function of tile CONTENT. A change that mutates a tile dict in place without
touching its `None`-ness (WATER, FERTILIZE, a `PLANT` tile decaying into a `WEED` — both
dicts) is RNG-neutral for that night; a change that flips a tile to/from `None` (DIG, PLANT,
BUY_LAND, HARVEST of a non-`ongoing` crop) re-rolls every draw after it, cascading into the
shared per-day rng's shop-unlock draw (`_end_of_day`, kaggriculture.py:860-891).

These two tests pin that distinction directly against the installed engine (not
engine_reference/, so a future engine bump that changes `_spawn_weeds`'s draw semantics fails
here loudly — same convention as `test_engine_facts.py`). Confirmed to redden under the old
("any tile difference re-rolls") reading: `test_water_on_a_plant_tile_is_occupancy_neutral`
asserts equality where that reading would predict a difference.
"""
from __future__ import annotations

import copy
import random

from kaggle_environments.envs.kaggriculture import kaggriculture as k

BOARD_SIZE = 10


class _CountingRandom(random.Random):
    """Spy on `.random()` call count without altering the sequence it returns."""

    def __init__(self, seed):
        super().__init__(seed)
        self.n_calls = 0

    def random(self):
        self.n_calls += 1
        return super().random()


def _empty_board():
    return [[None] * BOARD_SIZE for _ in range(BOARD_SIZE)]


def _n_none(tiles):
    return sum(1 for row in tiles for t in row if t is None)


def _draws_consumed(tiles):
    """`_spawn_weeds` mutates `tiles` in place (a None tile can become a WEED mid-pass), so
    it must run on a throwaway copy — otherwise the act of measuring changes what the next
    measurement sees."""
    rng = _CountingRandom(0)
    k._spawn_weeds({"tiles": copy.deepcopy(tiles)}, BOARD_SIZE, 0.5, rng)
    return rng.n_calls


def test_draws_equal_the_count_of_none_tiles():
    tiles = _empty_board()
    tiles[2][2] = k._new_plant("WHEAT", 0, 24)
    tiles[5][5] = {"kind": "WEED"}
    tiles[7][1] = k._new_animal("SHEEP", 0)
    assert _draws_consumed(tiles) == _n_none(tiles) == BOARD_SIZE * BOARD_SIZE - 3


def test_water_on_a_plant_tile_is_occupancy_neutral():
    """WATER (kaggriculture.py:431-444) mutates the tile dict in place; it never touches
    `None`-ness. The old rule-1 wording predicts this changes the draw count — it does not."""
    tiles = _empty_board()
    tiles[0][0] = k._new_plant("WHEAT", 0, 24)
    before = _draws_consumed(tiles)

    tiles[0][0]["watered_today"] = True  # WATER's actual mutation on an unwatered PLANT tile
    after = _draws_consumed(tiles)

    assert after == before  # reddens under "any one-tile difference re-rolls the sequence"


def test_dig_on_a_weed_tile_adds_exactly_one_draw():
    """DIG (kaggriculture.py:484-491) sets the tile to `None` — one fewer occupied tile, one
    more draw the next `_spawn_weeds` pass consumes."""
    tiles = _empty_board()
    tiles[3][3] = {"kind": "WEED"}
    before = _draws_consumed(tiles)

    tiles[3][3] = None  # DIG's actual effect
    after = _draws_consumed(tiles)

    assert after == before + 1


def test_plant_to_weed_decay_is_also_occupancy_neutral():
    """A `PLANT` tile that decays into a `WEED` (kaggriculture.py:766,784) stays a dict — the
    tile is never `None` at either end, so this transition is RNG-neutral too."""
    tiles = _empty_board()
    tiles[4][4] = k._new_plant("WHEAT", 0, 24)
    before = _draws_consumed(tiles)

    tiles[4][4] = {"kind": "WEED"}  # the decay's actual effect
    after = _draws_consumed(tiles)

    assert after == before
