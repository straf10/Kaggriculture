"""Engine constants fallback for the pinned kaggle-environments **1.32.6**.

Parity with the installed engine is asserted by `tests/test_agent_guards.py`. Every value in
this file was re-verified equal under 1.32.6 during the v1h.1 bump: the balance change touched
only the town-demand *rule*, never a constant this file carries.
"""
import math

CROPS = {
    "WHEAT": {"seed": 10, "first_yield_day": 2, "max_yield_day": 4, "interval": 0, "max_yield": 6, "ongoing": False},
    "CARROT": {"seed": 20, "first_yield_day": 2, "max_yield_day": 3, "interval": 0, "max_yield": 4, "ongoing": False},
    "TOMATO": {"seed": 50, "first_yield_day": 8, "max_yield_day": 8, "interval": 1, "max_yield": 4, "ongoing": True},
    "STRAWBERRY": {"seed": 100, "first_yield_day": 10, "max_yield_day": 10, "interval": 2, "max_yield": 4, "ongoing": True},
    "MELON": {"seed": 80, "first_yield_day": 10, "max_yield_day": 12, "interval": 0, "max_yield": 6, "ongoing": False},
}

ANIMALS = {
    "GOOSE": {"cost": 300, "structure": "COOP", "first_yield_day": 4, "interval": 1, "max_held": 4, "product": "EGG"},
    "COW": {"cost": 400, "structure": "PASTURE", "first_yield_day": 8, "interval": 2, "max_held": 6, "product": "MILK"},
    "SHEEP": {"cost": 500, "structure": "PASTURE", "first_yield_day": 6, "interval": 3, "max_held": 6, "product": "WOOL"},
}

MARKET_I0 = 10000
PRICE_FLOOR = 1

MARKET_PARAMS = {
    "WHEAT": {"base": 25, "I0": MARKET_I0, "T": 400, "below_func": "sqrt", "below_target": 0.80, "above_func": "log", "above_target": 0.20},
    "CARROT": {"base": 35, "I0": MARKET_I0, "T": 450, "below_func": "log", "below_target": 0.20, "above_func": "sqrt", "above_target": 0.70},
    "TOMATO": {"base": 60, "I0": MARKET_I0, "T": 200, "below_func": "linear", "below_target": 0.40, "above_func": "sqrt", "above_target": 0.60},
    "STRAWBERRY": {"base": 120, "I0": MARKET_I0, "T": 100, "below_func": "sqrt", "below_target": 0.70, "above_func": "linear", "above_target": 1.60},
    "MELON": {"base": 250, "I0": MARKET_I0, "T": 300, "below_func": "log", "below_target": 0.20, "above_func": "sq", "above_target": 3.60},
    "EGG": {"base": 50, "I0": MARKET_I0, "T": 332, "below_func": "linear", "below_target": 0.40, "above_func": "log", "above_target": 0.20},
    "MILK": {"base": 160, "I0": MARKET_I0, "T": 122, "below_func": "sqrt", "below_target": 0.60, "above_func": "linear", "above_target": 1.60},
    "WOOL": {"base": 200, "I0": MARKET_I0, "T": 105, "below_func": "log", "below_target": 0.20, "above_func": "sq", "above_target": 3.20},
    "FERTILIZER": {"base": 100, "I0": MARKET_I0, "T": 200, "below_func": "linear", "below_target": 0.40, "above_func": "linear", "above_target": 0.40},
}

LAND_ORDER = ["NE", "SW", "SE"]
LAND_PRICES = [1000, 2000, 4000]

SHOPS = {
    "BAKERY": ["EGG", "WHEAT"],
    "PIZZA_SHOP": ["MILK", "TOMATO", "WHEAT"],
    "BRUNCH_SPOT": ["EGG", "WHEAT", "STRAWBERRY"],
    "YARN_STORE": ["WOOL"],
    "ICE_CREAM_SHOP": ["STRAWBERRY", "MILK", "WHEAT"],
    "PET_CAFE": ["CARROT"],
    "SMOOTHIE_SHOP": ["STRAWBERRY", "MILK"],
    "FARMERS_MARKET": ["WHEAT", "CARROT", "TOMATO", "STRAWBERRY"],
}

# v1g.2: mirrors the engine's own derivation (`PRODUCTS = list(MARKET_PARAMS)`, then
# `TOWN_CENTER_PRODUCTS = [p for p in PRODUCTS if p != "FERTILIZER"]`) rather than restating
# the list, so a future engine bump that adds a product can only ever go out of sync here via
# MARKET_PARAMS — which is already pinned by a parity test. FERTILIZER's exclusion is the one
# fact this file has to carry: it is the only product with literally zero NPC demand (no shop
# buys it either), which is what makes its price monotonically decreasing in cumulative sales.
PRODUCTS = list(MARKET_PARAMS)
TOWN_CENTER_PRODUCTS = [p for p in PRODUCTS if p != "FERTILIZER"]

# v1h.1 (1.32.6): `TOWN_CENTER_DEMAND_SCHEDULE = [(20, 4), (10, 2), (0, 1)]` used to live here.
# The engine deleted it — the town centre now consumes a flat 1 of each non-fertilizer product
# per tick, with no day-stepped ramp anywhere in the engine. It is NOT re-vendored as `[(0, 1)]`:
# a constant with no reader is the dead code review L9 flagged, and keeping the name alive would
# invite a future reader to assume a ramp still exists somewhere. `MAX_SHOP_INSTANCES` is
# likewise absent by design — no `agent/` code reads it; the harness reads it straight off the
# engine, and `tests/test_engine_facts.py` pins both facts against the engine directly.


def _shape(func, x):
    x = max(0.0, x)
    if func == "linear":
        return x
    if func == "sq":
        return x * x
    if func == "sqrt":
        return math.sqrt(x)
    if func == "log":
        return math.log(1.0 + x)
    if func == "log10":
        return math.log10(1.0 + x)
    return x


def market_price(item, inventory, params=None):
    """Return the pinned engine's rounded, floored market price."""
    p = (params or MARKET_PARAMS)[item]
    base, equilibrium, capacity = p["base"], p["I0"], p["T"]
    if inventory < equilibrium:
        func = p["below_func"]
        amplitude = p["below_target"] * base / _shape(func, capacity)
        price = base + amplitude * _shape(func, equilibrium - inventory)
    else:
        func = p["above_func"]
        amplitude = p["above_target"] * base / _shape(func, capacity)
        price = base - amplitude * _shape(func, inventory - equilibrium)
    return max(PRICE_FLOOR, int(round(price)))
