"""All tunable agent settings, grouped for later sweeps."""
import os

CONFIG = {
    "planner": {
        "enabled": True,
        # v1g: reduced from 7 to 3 (kept the 3 nearest-to-shed NW CARROT tiles: (4,4)/(3,4)/
        # (4,3)) to free the 4 farthest ((3,3)/(2,4)/(2,3)/(4,0)) for PASTURE — NW was already
        # fully allocated (see strawberry_tiles comment below), and CARROT was the cheaper give
        # -up: its price crashes fastest under real opponent competition (ne_carrot_tiles
        # comment below), so it was the first place cut when 11 more PASTURE tiles were needed
        # for the v1g animal-mass increment (current_phase.md v1g). NE's carrot mirror tiles
        # (ne_carrot_tiles) are untouched.
        "carrot_tiles": 3,
        # plan.md §5 v1e: reduced from 16 to 15 to free tile (3, 0) for GOOSE's COOP structure
        # — all 25 NW tiles were already fully allocated (7 CARROT + 16 STRAWBERRY + 2 PASTURE),
        # so adding a third animal kind requires reclaiming one. (3, 0) was the lowest-priority
        # NW STRAWBERRY tile (last in target_tiles' tuple order, so the capacity gate already
        # trims it first under any pressure). COOP is placed on NW (not NE) specifically to
        # avoid a circular dependency: BUY_LAND's gate (executor.py) requires every planned
        # animal already placed, but GOOSE can't be placed before COOP exists — if COOP sat on
        # NE-locked land, GOOSE could never be placed, and land could never be bought.
        # v1g: reduced from 15 to 8 — the 7 lowest-priority NW STRAWBERRY tiles (already last
        # in target_tiles' tuple order, i.e. already first to be trimmed under any capacity
        # pressure) were reclaimed for PASTURE alongside the 4 CARROT tiles above, together
        # freeing the 11 new PASTURE slots current_phase.md's v1g asks for (2 existing + 11 new
        # = 13, matching the elite ceiling of 8 COW + 5 SHEEP). NW is fully allocated either way
        # (3 CARROT + 8 STRAWBERRY + 13 PASTURE + 1 COOP = 25); this is a targeted reclaim to
        # fit the new structures, not the full crop/animal portfolio rebalance MASTERPLAN
        # reserves for v1h.
        "strawberry_tiles": 8,
        "strawberry_last_plant_day": 5,
        "max_new_plants_per_day": 5,
        # v1f: screened hands_target in {6, 8, 10, 12} on DEV_SEEDS vs checkpoints/v1e (all vs
        # the fixed 41-tile crop-target ceiling + 3 fixed animals). 6 and 8 IMPROVED, 10 and 12
        # REGRESSED (hiring cost outweighs benefit once real workload — sized by
        # _animal_daily_demand() + the crop capacity gate below — runs out around ~7-8 hands'
        # worth of unit-turns; extra hands sit idle). h6 confirmed decisively best on
        # HOLDOUT_SEEDS: +$2241.72/ep (se=48.97) vs h8's +$1107.15/ep (se=48.45), non-overlapping
        # 95% CIs, both 96/96 episode wins vs v1e, 0 errors.
        "hands_target": 6,
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
            # v1g: (3, 3)/(2, 4)/(2, 3)/(4, 0) — the 4 farthest-from-shed of the original 7 —
            # reclaimed for PASTURE (see carrot_tiles comment above). The 3 nearest NW tiles
            # stay CARROT so late-game planting (after STRAWBERRY's window closes, before NE
            # unlock) still has a target.
            "CARROT": (
                (4, 4), (3, 4), (4, 3),
                # plan.md §5 v1c: NE mirror (x' = 9 - x) of the original 7 NW tiles, appended
                # so target_index 3+ only ever produce PLANT tasks once plan.plant_targets
                # grows past 3 — which planner.py only does once "NE" is actually unlocked
                # (still LOCKED tiles fall through build_tasks' `tile is None` check as a
                # harmless no-op until then). Left at its original 7 positions/count — only
                # NW's own tile count shrank, not NE's.
                (5, 4), (6, 4), (6, 3),
                (5, 3), (7, 4), (7, 3),
                (5, 0),
            ),
            # plan.md §5.1: (4, 2) and (3, 2) were reassigned from STRAWBERRY targets to
            # animal_structure_tiles below to make room for the two PASTURE slots (COW +
            # SHEEP) without expanding onto not-yet-owned land (v1d runs before v1c's land
            # purchase). v1g: the 7 lowest-priority (last-in-tuple, already-first-trimmed)
            # NW tiles below — (0, 4) through (2, 0) — were further reclaimed for PASTURE
            # (see strawberry_tiles comment above); 8 NW tiles remain.
            "STRAWBERRY": (
                (2, 2),
                (1, 4), (1, 3), (1, 2),
                (1, 1), (2, 1), (3, 1),
                (4, 1),
                # (3, 0) reassigned to animal_structure_tiles["COOP"] in v1e (see
                # strawberry_tiles comment above).
                # plan.md §5 v1c: NE mirror (x' = 9 - x) of the original 16 NW tiles, same
                # unlock-gated growth story as CARROT above. Left at its original 16
                # positions/count — only NW's own tile count shrank, not NE's.
                (7, 2),
                (8, 4), (8, 3), (8, 2),
                (8, 1), (7, 1), (6, 1),
                (5, 1), (9, 4), (9, 3),
                (9, 2), (9, 1), (9, 0),
                (8, 0), (7, 0), (6, 0),
            ),
        },
        # plan.md §5.1 v1d / v1g: reserved structure tiles for animal placement, carved up
        # per-name by agent.animal_slots.animal_slot_ranges in config["animals"]["targets"]
        # dict order — the first `targets["COW"]` PASTURE tiles below are COW's, the next
        # `targets["SHEEP"]` are SHEEP's. All 13 PASTURE tiles are NW (owned from day 0):
        # current_phase.md v1g deliberately never places a structure on not-yet-purchased
        # land — BUY_LAND's gate (executor.py) requires every planned animal already placed,
        # so a structure sitting on NE-locked land would deadlock it (the same reasoning that
        # already put GOOSE's COOP on NW in v1e — see its comment below). Ordered nearest-
        # shed-first within each animal's own block (FEED/CARE is a recurring daily commute
        # cost ×13 now, review_89d99f0_2026-08-05.md C1 §1.3) — COW (8, more numerous) gets
        # the nearer half, SHEEP (5) the farther half.
        "animal_structure_tiles": {
            "PASTURE": (
                # COW block (8): distances 2,2,2,3,3,4,4,5 from the (4,4) shed spawn.
                (4, 2), (3, 3), (2, 4), (3, 2), (2, 3), (4, 0), (0, 4), (0, 3),
                # SHEEP block (5): distances 6,6,7,7,8.
                (0, 2), (2, 0), (0, 1), (1, 0), (0, 0),
            ),
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
        # scheduler.animal_structure_tiles).
        #
        # v1g: targets is now name -> count (was one slot per unique name) — see
        # agent/animal_slots.py. Dict order still fixes which tiles within a shared structure
        # kind (COW/SHEEP both PASTURE) each name claims first. current_phase.md's elite
        # ceiling (topfarms-19, 8 COW + 5 SHEEP) does NOT clear the metric gate at this
        # hands_target: feed logistics (one WHEAT-carrying trip per animal per day, spread
        # across up to 13 tiles at distance <=8) breaks down at that mass regardless of the
        # scheduling fixes below, producing 660-885 animals_escaped across 96 dev-screen
        # episodes. Screened 7/10/11/12/13/14-animal sizes on DEV_SEEDS; mean_diff peaks at
        # 10 (6 COW + 4 SHEEP, GOOSE dropped): +$25384/ep dev-screen, +$25343/ep
        # HOLDOUT_SEEDS confirm (se=594.65, 96/96 episode wins vs checkpoints/v1f, 0 errors),
        # all four hard-gate metrics at 0. 11 animals still clears the gate but is worse
        # economically (+$18940/ep — feed-logistics overhead outweighs the extra animal's
        # yield); 12+ starts failing the gate again (water_weeds_lost>0). GOOSE's 15%
        # adoption and low yield made it a measured drop here, not a carry-over — see
        # memory.md v1g entry for the full screen history.
        "enabled": True,
        "targets": {"COW": 6, "SHEEP": 4, "GOOSE": 0},
    },
    "endgame": {
        "enabled": True,
        "liquidation_day": 26,
    },
    "guards": {
        # plan.md §1.5.4: the agent runs in a separate, freshly-imported process from
        # whatever invoked it (harness CLI, a ProcessPoolExecutor worker), so this must be
        # steered by an env var read once at import, never by mutating CONFIG after the fact.
        "debug": os.environ.get("KAGGRI_DEBUG", "0") == "1",
    },
    "runtime": {
        "turns_per_day": 24,
        "episode_steps": 720,
    },
}
