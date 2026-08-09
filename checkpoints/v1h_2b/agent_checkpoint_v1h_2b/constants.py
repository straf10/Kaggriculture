"""Engine constants with a submission-safe vendored fallback.

**Per-symbol fallback, deliberately.** The previous version imported every name inside a single
`try:` block, which meant that one deleted engine symbol dropped *all* of them to the vendored
copy — silently, because `ImportError` on a from-import gives no clue which name was missing.
That is exactly what the 1.32.6 bump produced: the engine removed `TOWN_CENTER_DEMAND_SCHEDULE`,
so `MARKET_PARAMS`, `market_price` and everything else quietly stopped tracking the installed
engine (v1h.1, `current_phase.md`). Resolving each name on its own keeps a future deletion
confined to the one constant it actually affects.

`_vendored` remains the source of truth **only** when the engine is unavailable — the submission
runner always has it, so in practice this file reads the live engine.
"""
from . import _vendored

try:
    from kaggle_environments.envs.kaggriculture import kaggriculture as _engine
except ImportError:  # pragma: no cover - exercised by the vendored-fallback guard test
    _engine = None


def _const(name):
    """The installed engine's value for `name`, falling back to the vendored copy.

    Falls back on a *missing attribute* as well as a missing engine, so a symbol the engine
    drops in a future bump degrades to the pinned value instead of taking the rest of the
    module down with it. Every name resolved here is covered by the `_vendored` parity test.
    """
    if _engine is not None:
        try:
            return getattr(_engine, name)
        except AttributeError:
            pass
    return getattr(_vendored, name)


ANIMALS = _const("ANIMALS")
CROPS = _const("CROPS")
LAND_ORDER = _const("LAND_ORDER")
LAND_PRICES = _const("LAND_PRICES")
MARKET_PARAMS = _const("MARKET_PARAMS")
SHOPS = _const("SHOPS")
TOWN_CENTER_PRODUCTS = _const("TOWN_CENTER_PRODUCTS")
market_price = _const("market_price")

SHED_ACCESS = ((4, 4), (5, 4), (4, 5), (5, 5))
