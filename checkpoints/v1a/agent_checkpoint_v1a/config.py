"""All tunable agent settings, grouped for later sweeps."""

CONFIG = {
    "planner": {
        "enabled": True,
        "carrot_tiles": 9,
        "max_new_plants_per_day": 3,
    },
    "scheduler": {
        "enabled": True,
        "max_tasks": 400,
        "target_tiles": (
            (4, 4), (3, 4), (3, 3),
            (4, 3), (2, 4), (2, 3),
            (2, 2), (3, 2), (4, 2),
        ),
    },
    "executor": {
        "enabled": True,
        "max_market_orders": 10,
        "seed_buffer": 3,
        "sell_floor_price": {
            "CARROT": 5,
        },
        "opponent_price_safety_units": 4,
    },
    "animals": {
        "enabled": False,
    },
    "endgame": {
        "enabled": False,
        "liquidation_day": 26,
    },
    "guards": {
        "debug": False,
    },
    "runtime": {
        "turns_per_day": 24,
        "episode_steps": 720,
    },
}
