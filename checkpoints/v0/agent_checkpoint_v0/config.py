"""All tunable agent settings, grouped for later sweeps."""

CONFIG = {
    "planner": {
        "enabled": False,
    },
    "scheduler": {
        "enabled": False,
        "max_tasks": 400,
    },
    "executor": {
        "enabled": False,
        "max_market_orders": 10,
    },
    "animals": {
        "enabled": False,
    },
    "endgame": {
        "enabled": False,
        "liquidation_day": 29,
    },
    "guards": {
        "debug": False,
    },
    "runtime": {
        "turns_per_day": 24,
        "episode_steps": 720,
    },
}
