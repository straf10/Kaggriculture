"""v1v — pin the shop-drain constants the realised-price finding rests on.

`analysis/v1v_shop_demand.py` mirrors the engine's `SHOPS` table and re-derives the
per-tick consumption rule so the analysis is dependency-free. That mirror is exactly the
kind of vendored constant §6bis's loader contract requires to be parity-tested against the
**installed** engine — a balance change to `SHOPS` or to the single-product multiplier
would silently invalidate every number in `data/derived/v1v_shop_demand.json`.
"""
import math

import pytest
from kaggle_environments import make
from kaggle_environments.envs.kaggriculture import kaggriculture as k

from analysis.v1v_shop_demand import (
    SHOPS,
    absent_probability,
    expected_units_per_tick,
    units_per_tick,
)

PASS = {"farmer": ["PASS"], "hands": [], "market": []}


def test_shops_table_matches_installed_engine():
    assert SHOPS == k.SHOPS


def test_max_shop_instances_is_eight():
    # The absent-probability arithmetic is (types_without / types) ** MAX_SHOP_INSTANCES.
    assert k.MAX_SHOP_INSTANCES == 8


def test_single_product_shops_consume_double():
    """The multiplier=2 branch is what makes WOOL's one YARN_STORE worth 2 units/tick."""
    singles = {n for n, p in k.SHOPS.items() if len(p) == 1}
    assert singles == {"YARN_STORE", "PET_CAFE"}
    assert units_per_tick(["YARN_STORE"]) == {"WOOL": 2}
    assert units_per_tick(["PET_CAFE"]) == {"CARROT": 2}
    assert units_per_tick(["SMOOTHIE_SHOP"]) == {"STRAWBERRY": 1, "MILK": 1}


def test_melon_and_fertilizer_have_no_shop_buyer():
    """The two flat products in the measurement — neither appears in any shop."""
    assert absent_probability()["MELON"] == 1.0
    assert absent_probability()["FERTILIZER"] == 1.0
    for products in k.SHOPS.values():
        assert "MELON" not in products
        assert "FERTILIZER" not in products
    # FERTILIZER is additionally excluded from the town centre; MELON is not.
    assert "FERTILIZER" not in k.TOWN_CENTER_PRODUCTS
    assert "MELON" in k.TOWN_CENTER_PRODUCTS


def test_wool_is_absent_from_a_third_of_towns():
    """The single most consequential draw: 34,4% of towns never unlock a YARN_STORE."""
    assert absent_probability()["WOOL"] == pytest.approx((7 / 8) ** 8)
    assert absent_probability()["WOOL"] == pytest.approx(0.3436, abs=5e-5)
    # STRAWBERRY sits in 4 of the 8 types, so it is effectively always drained.
    assert absent_probability()["STRAWBERRY"] < 0.005


def test_expected_units_per_tick_sums_to_the_full_draw():
    exp = expected_units_per_tick()
    # Eight instances, each consuming (len(products) or 2 for singles) units.
    total = sum(2 if len(p) == 1 else len(p) for p in k.SHOPS.values()) * 8 / len(k.SHOPS)
    assert math.isclose(sum(exp.values()), total)
    assert exp["WHEAT"] == pytest.approx(5.0)
    assert exp["STRAWBERRY"] == pytest.approx(4.0)
    assert exp["MILK"] == pytest.approx(3.0)
    assert exp["WOOL"] == pytest.approx(2.0)


def test_town_consume_drains_inventory_at_the_mirrored_rate():
    """Tier B: drive the real interpreter and read the drain off market inventory.

    Two indexing facts this pins, both of which cost a wrong first draft:
    `_town_consume` is called with the *pre-increment* step, so the drain that lands in
    `obs.step == N` was computed on `N - 1`; and interpreter step 0 satisfies **both**
    `step % townShopSellInterval` and `step % townCenterSellInterval`, so the very first
    tick carries an extra town-centre unit on every non-FERTILIZER product.
    """
    env = make("kaggriculture",
               configuration={"seed": 3, "episodeSteps": 30, "turnsPerDay": 24})
    env.reset(2)
    obs = env.state[0].observation
    obs.town["unlocked_shops"] = ["YARN_STORE", "SMOOTHIE_SHOP"]
    expected = units_per_tick(["YARN_STORE", "SMOOTHIE_SHOP"])

    # First tick (interpreter step 0) — shops *and* town centre.
    before = dict(obs.market["inventory"])
    env.step([PASS, PASS])
    after = dict(env.state[0].observation.market["inventory"])
    assert env.state[0].observation.step == 1
    for item, units in expected.items():
        centre = 1 if item in k.TOWN_CENTER_PRODUCTS else 0
        assert before[item] - after[item] == units + centre, item

    # Next tick (interpreter step 4, landing in obs.step 5) — shops only.
    before = after
    while env.state[0].observation.step < 5:
        env.step([PASS, PASS])
    after = dict(env.state[0].observation.market["inventory"])
    for item, units in expected.items():
        assert before[item] - after[item] == units, item
