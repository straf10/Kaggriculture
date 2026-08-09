"""Engine constants with a submission-safe vendored fallback."""
try:
    from kaggle_environments.envs.kaggriculture.kaggriculture import (
        ANIMALS,
        CROPS,
        LAND_ORDER,
        LAND_PRICES,
        MARKET_PARAMS,
        SHOPS,
        TOWN_CENTER_DEMAND_SCHEDULE,
        market_price,
    )
except ImportError:
    from ._vendored import (
        ANIMALS,
        CROPS,
        LAND_ORDER,
        LAND_PRICES,
        MARKET_PARAMS,
        SHOPS,
        TOWN_CENTER_DEMAND_SCHEDULE,
        market_price,
    )

SHED_ACCESS = ((4, 4), (5, 4), (4, 5), (5, 5))
