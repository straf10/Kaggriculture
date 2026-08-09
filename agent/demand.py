"""Derived metric: how many units per day the town actually absorbs, per product.

current_phase.md §v1g.2 (β). This is a *reimplementation of the engine's own consumption
rule*, not an estimate: `_town_consume` (engine_reference/kaggriculture.py:714-736) is fully
deterministic given `town["unlocked_shops"]`, the day, and three configuration intervals — all
three of which the agent can observe. The only thing that is genuinely random is *which* shops
unlock (MASTERPLAN §2 Αμφισημία #7), and that we read straight off the observation.

Why the agent needs it: price is a monotone function of market inventory, NPC demand is the
only thing that pulls inventory back down, and the glut side of the price curve is brutally
convex for exactly the products animals produce (WOOL `sq`/3.20, MILK `linear`/1.60). Selling
into a product whose buyer never unlocked is therefore not merely low-yield, it permanently
depresses every later sale of that product — and in 34.4% of post-balance-change episodes some
product's shop simply will not exist (current_phase.md §0bis.1).
"""
from .constants import SHOPS, TOWN_CENTER_DEMAND_SCHEDULE, TOWN_CENTER_PRODUCTS

#: Engine defaults, used only when the agent is called without a configuration (unit tests,
#: direct `agent(obs)` calls). Sourced from engine_reference/kaggriculture.py:719-721 — the
#: same literals the engine itself falls back to, so "no configuration" reproduces a default
#: episode rather than inventing a regime.
_DEFAULT_INTERVALS = {
    "townShopSellInterval": 4,
    "townCenterSellInterval": 12,
    "turnsPerDay": 24,
}


def _config_value(env_config, key: str) -> int:
    """Read an engine configuration key that may arrive as a dict or as an attribute bag.

    kaggle_environments hands the agent a Struct (attribute access) in some paths and a plain
    dict in others; the engine's own `get()` helper (kaggriculture.py:107) handles both for the
    same reason. Mirrors the engine's `max(1, int(...))` clamp so a pathological configuration
    can't make this divide by zero where the engine would not.
    """
    default = _DEFAULT_INTERVALS[key]
    if env_config is None:
        value = default
    elif isinstance(env_config, dict):
        value = env_config.get(key, default)
    else:
        value = getattr(env_config, key, default)
    try:
        return max(1, int(value))
    except (TypeError, ValueError):
        return default


def _ticks_in_day(day: int, turns_per_day: int, interval: int) -> int:
    """How many times `step % interval == 0` fires during `day`.

    The engine tests the **global** step, not the hour, so this is only `turns_per_day //
    interval` when the interval happens to divide the day. Counting it exactly matters for the
    announced balance change, which moves `townCenterSellInterval` to 24: with turnsPerDay=24
    that is 1 tick/day, and any "hours // interval" shortcut that assumed divisibility would
    still be right there but wrong for any other value a future config sweep might use.
    """
    last_step = (day + 1) * turns_per_day - 1
    first_step = day * turns_per_day - 1
    return last_step // interval - first_step // interval


def npc_daily_demand(unlocked_shops, day: int, env_config=None) -> dict[str, int]:
    """Units of each product the town removes from the market during `day`.

    Args:
        unlocked_shops: the observation's shop list, **in engine order and with duplicates
            kept**. After the balance change the engine draws with replacement, so a repeated
            name is a second, independently-buying shop instance — de-duplicating would
            under-count it by exactly the amount that matters.
        day: the day whose demand is wanted (the town-centre multiplier is day-stepped).
        env_config: the `configuration` object kaggle_environments passes as the agent's second
            argument. Optional; omitting it falls back to the engine's own defaults.

    Returns:
        product -> units/day, for every product with non-zero demand. Products absent from the
        mapping have **exactly** zero demand, which is a materially different state from "a
        little" — with no buyer the price never recovers, so a zero-demand product must not be
        throttled (see planner._dynamic_sell_floors). FERTILIZER is always in this category: no
        shop lists it and the town centre excludes it.
    """
    shop_interval = _config_value(env_config, "townShopSellInterval")
    center_interval = _config_value(env_config, "townCenterSellInterval")
    turns_per_day = _config_value(env_config, "turnsPerDay")

    demand: dict[str, int] = {}

    shop_ticks = _ticks_in_day(day, turns_per_day, shop_interval)
    if shop_ticks:
        for shop_name in unlocked_shops:
            products = SHOPS.get(shop_name)
            if not products:
                continue
            # engine_reference/kaggriculture.py:727 — a single-product shop buys double.
            multiplier = 2 if len(products) == 1 else 1
            for item in products:
                demand[item] = demand.get(item, 0) + multiplier * shop_ticks

    center_ticks = _ticks_in_day(day, turns_per_day, center_interval)
    # NB. the town centre buys every product except FERTILIZER, so total demand is never zero
    # for anything else — "does a *shop* buy this?" is a strictly different question and has its
    # own reader below.
    if center_ticks:
        center_mult = next(m for threshold, m in TOWN_CENTER_DEMAND_SCHEDULE if day >= threshold)
        for item in TOWN_CENTER_PRODUCTS:
            demand[item] = demand.get(item, 0) + center_mult * center_ticks

    return demand


def shop_buyer_counts(unlocked_shops) -> dict[str, int]:
    """How many unlocked **shop instances** buy each product (town centre excluded).

    The town centre buys everything but FERTILIZER at a low, fixed rate, so total demand alone
    can never answer "does this product have a real buyer in this town?" — which is the actual
    shop-adaptive question (current_phase.md §v1g.2). A product with at least one shop gets
    6 ticks/day of shop demand on top of the centre's 2, and that is enough for the market to
    work off anything a 5x5 farm can produce; a product with none is living on the centre alone.

    Counts instances, not distinct names: after the balance change two YARN_STOREs is twice the
    wool demand of one.
    """
    counts: dict[str, int] = {}
    for shop_name in unlocked_shops:
        for item in SHOPS.get(shop_name, ()):
            counts[item] = counts.get(item, 0) + 1
    return counts
