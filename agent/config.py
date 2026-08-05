"""All tunable agent settings, grouped for later sweeps."""
import os

_ABLATION_DEFAULTS = {
    # plan.md §1.5.2: every flag defaults True (= today's behavior, one per review.md fix
    # from the 2026-08-05 session). Flipping a flag False must reproduce EXACTLY the v1b
    # behavior at that point, so ablate.py can attribute the -$2.195 regression vs v1b to a
    # specific flag (or pair of flags) instead of reverting the whole session blind.
    "slack_assign": True,
    "task_stickiness": True,
    "per_unit_plant_feasibility": True,
    "plant_task_cap": True,
    "capacity_gate": True,
    "drop_task_per_unit": True,
    "on_event_replan": True,
    "seed_cap_by_remaining_targets": True,
    "priority_sort_before_truncate": True,
    "endgame_enabled": True,
    # review.md L7 — not in plan.md's §1.5.2 table, but a real v1b-vs-main behavior delta
    # found while validating the ablation self-test (criterion #1): without this flag, an
    # all-off run still showed nonzero per-seed diffs.
    "carrot_water_window": True,
}


def _load_ablation_overrides() -> dict:
    """Parse KAGGRI_ABLATION="flag1=0,flag2=1" once at import time (plan.md §1.5.2). The
    ablation runner and the agent run in separate processes (harness.compare spawns workers),
    so an env var read once at import is the only way to inject a combo without either
    rewriting config.py per run or mutating CONFIG at runtime — the latter would break G13
    determinism by making behavior depend on call order within a process."""
    raw = os.environ.get("KAGGRI_ABLATION", "")
    overrides = {}
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        name, _, value = part.partition("=")
        name = name.strip()
        if name not in _ABLATION_DEFAULTS:
            raise ValueError(f"KAGGRI_ABLATION: unknown flag {name!r}")
        overrides[name] = bool(int(value.strip()))
    return overrides


CONFIG = {
    "planner": {
        "enabled": True,
        "carrot_tiles": 7,
        "strawberry_tiles": 18,
        "strawberry_last_plant_day": 5,
        "max_new_plants_per_day": 5,
        "hands_target": 3,
        "capacity_safety_factor": 0.8,
    },
    "scheduler": {
        "enabled": True,
        "max_tasks": 400,
        # ablation §1.5.2 root-cause fix: tasks sharing priority+deadline_step (the common
        # case — every same-day WATER task) had slack differing only by -best_distance, so
        # "sort by min slack" always picked the FARTHEST task, all day, not just when a task
        # was actually about to miss its deadline. Gate slack's queue-jump to tasks within
        # this many turns of infeasibility; comfortable tasks fall back to plain
        # nearest-first, preserving both C1/§1.2's far-but-urgent fix and v1b's efficient
        # default ordering.
        "urgency_slack_margin": 2,
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
        "enabled": True,
        "liquidation_day": 26,
    },
    "guards": {
        # plan.md §1.5.4: same env-mechanism as KAGGRI_ABLATION (agent/config.py's module
        # docstring) — the agent runs in a separate, freshly-imported process from whatever
        # invoked it (harness CLI, a ProcessPoolExecutor worker), so this must be steered by
        # an env var read once at import, never by mutating CONFIG after the fact.
        "debug": os.environ.get("KAGGRI_DEBUG", "0") == "1",
    },
    "runtime": {
        "turns_per_day": 24,
        "episode_steps": 720,
    },
    "ablation": {**_ABLATION_DEFAULTS, **_load_ablation_overrides()},
}
