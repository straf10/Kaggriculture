"""All tunable agent settings, grouped for later sweeps."""

CONFIG = {
    "planner": {
        "enabled": True,
        "carrot_tiles": 7,
        "strawberry_tiles": 18,
        "strawberry_last_plant_day": 5,
        "max_new_plants_per_day": 5,
        "hands_target": 3,
    },
    "scheduler": {
        "enabled": True,
        "max_tasks": 400,
        "target_tiles": {
            "CARROT": (
                (4, 4), (3, 4), (3, 3),
                (4, 3), (2, 4), (2, 3),
                (4, 0),
            ),
            "STRAWBERRY": (
                (2, 2), (3, 2), (4, 2),
                (1, 4), (1, 3), (1, 2),
                (1, 1), (2, 1), (3, 1),
                (4, 1), (0, 4), (0, 3),
                (0, 2), (0, 1), (0, 0),
                (1, 0), (2, 0), (3, 0),
            ),
        },
    },
    "executor": {
        "enabled": True,
        "max_market_orders": 10,
        "seed_buffer": 6,
        "sell_floor_price": {
            "CARROT": 5,
            "STRAWBERRY": 8,
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
