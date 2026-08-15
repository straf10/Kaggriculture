"""v1t — engine 1.32.7 `hinge` price curve, pinned as facts.

The 1.32.7 balance change is market-only: CARROT, TOMATO and EGG move their **below-I0** curve
to a new `hinge` shape so those three products stay cheap under ordinary demand and spike once
the town has genuinely drained them. Nothing else in the engine moved — no turn order, no RNG,
no yields, no glut branch.

These tests exist so the next bump cannot quietly undo it, and so the two properties the change
*claims* stay claims we actually check: hinge is `target`-compatible (f(T) == 1), and the switch
is a strict no-op for TOMATO/EGG everywhere at or above the knee-adjacent inventories where the
old linear curve already agreed.
"""
import math

import pytest

from kaggle_environments.envs.kaggriculture import kaggriculture as k

I0 = k.MARKET_I0
HINGE_ITEMS = ("CARROT", "TOMATO", "EGG")


def _pre_1327_price(item, inventory):
    """The 1.32.6 curve for the three changed products, restated from the old MARKET_PARAMS.

    Deliberately a literal transcription rather than a call into the engine — the point is to
    have the *old* behaviour available to diff against, independent of anything 1.32.7 ships.
    """
    old = {
        "CARROT": {"base": 35, "T": 450, "below_func": "log", "below_target": 0.20},
        "TOMATO": {"base": 60, "T": 200, "below_func": "linear", "below_target": 0.40},
        "EGG": {"base": 50, "T": 332, "below_func": "linear", "below_target": 0.40},
    }[item]

    def shape(func, x):
        x = max(0.0, x)
        return {"linear": x, "log": math.log(1.0 + x)}[func]

    base, capacity = old["base"], old["T"]
    amp = old["below_target"] * base / shape(old["below_func"], capacity)
    raw = base + amp * shape(old["below_func"], I0 - inventory)
    return max(k.PRICE_FLOOR, int(round(raw)))


# --------------------------------------------------------------------------- the shape itself


def test_hinge_is_target_compatible():
    """f(T) == 1 by construction, which is what lets `below_target` keep the meaning it has for
    every other shape. Without this, switching a product to hinge would silently rescale it."""
    for capacity in (100, 200, 332, 450, 1000):
        assert k._shape("hinge", capacity, capacity) == pytest.approx(1.0)


def test_hinge_degenerates_to_linear_without_capacity():
    """The engine passes T positionally everywhere it matters, but the fallback branch is what
    makes `_shape` safe to call with the old two-argument signature."""
    for x in (0, 1, 37, 450):
        assert k._shape("hinge", x) == k._shape("linear", x)
        assert k._shape("hinge", x, 0) == k._shape("linear", x)
        assert k._shape("hinge", x, None) == k._shape("linear", x)


def test_hinge_is_flat_below_the_knee_and_convex_above():
    """Below the knee hinge is exactly u = x/T; above it the quadratic term takes over."""
    capacity = 200
    for x in range(0, capacity + 1):
        assert k._shape("hinge", x, capacity) == pytest.approx(x / capacity)
    assert k._shape("hinge", 2 * capacity, capacity) == pytest.approx(1.0 + 8.0 * 1.0 + 1.0)


def test_only_the_three_intended_products_use_hinge():
    for item, params in k.MARKET_PARAMS.items():
        expected = item in HINGE_ITEMS
        assert (params["below_func"] == "hinge") is expected, item
        # The glut branch was explicitly left alone for every product.
        assert params["above_func"] != "hinge", item


# --------------------------------------------------------------------------- the price effect


@pytest.mark.parametrize(
    "item,depletions,expected",
    [
        ("CARROT", [0, 225, 450, 600, 900, 1200], [35, 52, 70, 113, 385, 906]),
        ("TOMATO", [0, 100, 200, 250, 300, 390, 534], [60, 72, 84, 102, 144, 280, 660]),
        ("EGG", [0, 83, 166, 249, 332, 415, 498, 664], [50, 55, 60, 65, 70, 85, 120, 250]),
    ],
)
def test_hinge_price_tables(item, depletions, expected):
    """The tables quoted in the 1.32.7 PR, pinned verbatim."""
    assert [k.market_price(item, I0 - d) for d in depletions] == expected


@pytest.mark.parametrize("item", ["TOMATO", "EGG"])
def test_tomato_and_egg_are_a_strict_noop_below_the_knee(item):
    """Both kept `below_target` at 0.40, and linear's amp normalises to x/T — exactly hinge's
    below-knee branch. So the ordinary-season price path is unchanged to the dollar."""
    capacity = k.MARKET_PARAMS[item]["T"]
    for depletion in range(0, capacity + 1):
        assert k.market_price(item, I0 - depletion) == _pre_1327_price(item, I0 - depletion), depletion


def test_carrot_changes_everywhere_not_only_past_the_knee():
    """CARROT is the exception, and the PR's own framing understates it: it changed shape *and*
    target (log/0.20 -> hinge/1.00), so its below-curve moves from depletion 1 upward, not just
    past the knee. Anything in `agent/` that priced carrot off the old near-flat curve is stale."""
    capacity = k.MARKET_PARAMS["CARROT"]["T"]
    changed = [
        d
        for d in range(0, capacity + 1)
        if k.market_price("CARROT", I0 - d) != _pre_1327_price("CARROT", I0 - d)
    ]
    assert len(changed) == 433
    assert changed[0] == 1
    # The old curve was flat to the point of being inert: $35 -> $42 across the whole range.
    assert _pre_1327_price("CARROT", I0 - capacity) == 42
    assert k.market_price("CARROT", I0 - capacity) == 70


@pytest.mark.parametrize("item", HINGE_ITEMS)
def test_glut_branch_untouched(item):
    """Dumping any of the three still craters the price exactly as before — the change is
    one-sided, so no sell-side model built on the glut curve needs revisiting."""
    params = k.MARKET_PARAMS[item]
    above_func, above_target = params["above_func"], params["above_target"]
    old_above = {
        "CARROT": ("sqrt", 0.70),
        "TOMATO": ("sqrt", 0.60),
        "EGG": ("log", 0.20),
    }[item]
    assert (above_func, above_target) == old_above


def test_untouched_products_are_bit_identical():
    """The five products our agent actually earns on today must not have moved at all."""
    for item in ("WHEAT", "STRAWBERRY", "MELON", "MILK", "WOOL", "FERTILIZER"):
        params = k.MARKET_PARAMS[item]
        capacity = params["T"]
        assert params["below_func"] != "hinge", item
        # Spot-check the scarcity side stayed on its documented shape.
        for depletion in (0, capacity, 2 * capacity):
            assert k.market_price(item, I0 - depletion) >= params["base"], (item, depletion)
