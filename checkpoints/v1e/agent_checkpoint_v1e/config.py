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
        # plan.md §5 v1e: reduced from 16 to 15 to free tile (3, 0) for GOOSE's COOP structure
        # — all 25 NW tiles were already fully allocated (7 CARROT + 16 STRAWBERRY + 2 PASTURE),
        # so adding a third animal kind requires reclaiming one. (3, 0) was the lowest-priority
        # NW STRAWBERRY tile (last in target_tiles' tuple order, so the capacity gate already
        # trims it first under any pressure). COOP is placed on NW (not NE) specifically to
        # avoid a circular dependency: BUY_LAND's gate (executor.py) requires every planned
        # animal already placed, but GOOSE can't be placed before COOP exists — if COOP sat on
        # NE-locked land, GOOSE could never be placed, and land could never be bought.
        "strawberry_tiles": 15,
        "strawberry_last_plant_day": 5,
        "max_new_plants_per_day": 5,
        "hands_target": 3,
        "capacity_safety_factor": 0.8,
        # plan.md §5 v1c: added to carrot_tiles/strawberry_tiles once "NE" is in
        # snapshot.my_quadrants (the NE-mirrored tiles appended to target_tiles below). NOT a
        # 1:1 mirror of NW counts, unlike ne_strawberry_tiles: a holdout-confirm gate against
        # checkpoints/v1d with the naive 1:1 mirror (7) landed INCONCLUSIVE, narrowly missing
        # NON_INFERIOR — CARROT's own base price already crashes fast under real (not "pass")
        # opponent competition, and doubling its supply into that same shared market crashed it
        # further (observed avg sell price ~$24-34 vs STRAWBERRY's ~$130-230), eating most of
        # NE's net value. STRAWBERRY's higher, more volume-resilient price meant its full 1:1
        # mirror was still worth it. 3 was the smallest bump that cleared holdout-confirm as
        # NON_INFERIOR — a properly volume-aware seller belongs in v1e, not here.
        "ne_carrot_tiles": 3,
        "ne_strawberry_tiles": 16,
        # plan.md §5 v1c: without this, CARROT and STRAWBERRY compete for the SAME shared
        # max_new_plants_per_day budget (scheduler.py build_tasks) in CARROT-first order —
        # doubling carrot_target's tile count alone let CARROT's many newly-empty NE tiles
        # eat the whole day's planting budget every day, starving STRAWBERRY of any planting
        # slots at all (observed in a v1c smoke test: 8 STRAWBERRY sold over 30 days vs 64
        # pre-v1c). Doubling the daily budget alongside the tile counts keeps both crops
        # actually plantable.
        "ne_max_new_plants_per_day": 5,
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
                # plan.md §5 v1c: NE mirror (x' = 9 - x) of the 7 NW tiles above, appended so
                # target_index 7-13 only ever produce PLANT tasks once plan.plant_targets
                # grows past 7 — which planner.py only does once "NE" is actually unlocked
                # (still LOCKED tiles fall through build_tasks' `tile is None` check as a
                # harmless no-op until then).
                (5, 4), (6, 4), (6, 3),
                (5, 3), (7, 4), (7, 3),
                (5, 0),
            ),
            # plan.md §5.1: (4, 2) and (3, 2) were reassigned from STRAWBERRY targets to
            # animal_structure_tiles below to make room for the two PASTURE slots (COW +
            # SHEEP) without expanding onto not-yet-owned land (v1d runs before v1c's land
            # purchase). 16 tiles remain (was 18) — see strawberry_tiles below.
            "STRAWBERRY": (
                (2, 2),
                (1, 4), (1, 3), (1, 2),
                (1, 1), (2, 1), (3, 1),
                (4, 1), (0, 4), (0, 3),
                (0, 2), (0, 1), (0, 0),
                (1, 0), (2, 0),
                # (3, 0) reassigned to animal_structure_tiles["COOP"] in v1e (see
                # strawberry_tiles comment above).
                # plan.md §5 v1c: NE mirror (x' = 9 - x) of the 16 NW tiles above, same
                # unlock-gated growth story as CARROT above.
                (7, 2),
                (8, 4), (8, 3), (8, 2),
                (8, 1), (7, 1), (6, 1),
                (5, 1), (9, 4), (9, 3),
                (9, 2), (9, 1), (9, 0),
                (8, 0), (7, 0), (6, 0),
            ),
        },
        # plan.md §5.1 v1d: fixed PASTURE slots for the two top-decile animals (COW day-0,
        # SHEEP day-5 median adoption per data/derived/top_agent_profiles.md), ordered to
        # match CONFIG["animals"]["targets"] — slot index i within a structure kind's tuple
        # is reserved for the i-th target animal using that structure. Chosen close to the
        # shed spawn (distance 2-3) since FEED/CARE is a recurring daily commute cost exactly
        # like WATER (review.md C1 §1.3).
        "animal_structure_tiles": {
            "PASTURE": ((4, 2), (3, 2)),
            # plan.md §5 v1e: GOOSE's COOP, placed on the reclaimed NW STRAWBERRY tile (3, 0)
            # rather than NE — see strawberry_tiles comment in config["planner"] for why NE
            # would deadlock BUY_LAND's animal_placed gate.
            "COOP": ((3, 0),),
        },
    },
    "executor": {
        "enabled": True,
        "max_market_orders": 10,
        "seed_buffer": 6,
        "sell_floor_price": {
            "CARROT": 5,
            "STRAWBERRY": 8,
            "EGG": 5,
            "MILK": 15,
            "WOOL": 20,
            "FERTILIZER": 10,
        },
        "opponent_price_safety_units": 4,
    },
    "land": {
        # plan.md §5 v1c / MASTERPLAN §3.2#7: buy NE as soon as money allows AND a workforce
        # actually exists to work it (buying land before hands_target hands are hired would
        # be dead capital). Scoped to NE only for v1c; SW/SE are a later-phase roadmap item
        # (MASTERPLAN §3.2#7), not needed to clear Phase 1's acceptance criteria.
        "enabled": True,
        # A dev-screen run (main.py vs checkpoints/v1d, a REAL competing seller — unlike the
        # earlier "pass"-opponent smoke tests, which gave main.py the entire market to itself
        # and hid this) showed land's $1000 landing on day 0 (as soon as hands_target + both
        # animals were affordable) left the bank near $0 for days afterward, with no buffer to
        # absorb a real opponent crashing crop prices via shared market competition — starving
        # hires and cascading into G1/G5 capacity failures (weeds, decay, animal escapes) that
        # never showed up against a passive opponent. plan.md's own top-decile data targets
        # 2nd-quadrant unlock around day ~9, not day 0 — this reserve requirement (rather than
        # a hardcoded day) makes the trigger self-regulating: land waits until the shed has
        # genuine surplus cash beyond survival needs, however many days that actually takes.
        "min_reserve": 1000,
    },
    "animals": {
        # plan.md §5.1: v1d shipped COW (85% top-team adoption, median day 0) and SHEEP (56%,
        # median day 5). GOOSE (15% adoption) added in v1e, now that COOP has a home (see
        # scheduler.animal_structure_tiles). Order matters: it fixes which animal claims which
        # slot in animal_structure_tiles per structure kind.
        "enabled": True,
        "targets": ("COW", "SHEEP", "GOOSE"),
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
