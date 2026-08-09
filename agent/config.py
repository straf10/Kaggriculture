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
        # v1h': the crew size once SW is actually owned. v1f's h6-beats-h8 result is not
        # contradicted, it is *conditioned*: it measured 6/8/10/12 hands against a fixed 41-tile
        # crop ceiling and 3 animals, and its own conclusion was "no further crew scaling
        # without first growing the real workload" (current_phase.md §0 ⚠️β). SW is that
        # workload. The capacity gate below is already binding at 6 hands with NE unlocked —
        # _capacity_limited_targets trims STRAWBERRY from 24 to 21 — so buying a third quadrant
        # without also raising the crew buys tiles nobody can water, which is the same dead
        # -capital mistake MASTERPLAN §3.2#7 warns about for land bought before hands exist.
        # Hands are re-hired every morning (the engine wipes farm["hands"] at end of day), so
        # this is a recurring fib(n) cost, not a one-off: 6 hands cost 1+1+2+3+5+8 = $20/day,
        # 10 cost $143/day. That ~$123/day is what the extra ~77 unit-turns/day has to pay for.
        #
        # Screened on DEV_SEEDS against checkpoints/v1g_1 with pinned towns. 8 hands is not
        # enough at any tile count that pays: at 12 WHEAT tiles it still lost 1 animal per
        # episode to feed contention. 10 is the first size where the herd stays whole while SW
        # is being worked, and 12 measured identical to 10 (the 11th and 12th hire cost fib(10)
        # =89 / fib(11)=144 at an hour when the bank rarely has it, so they are mostly never
        # actually hired). See memory.md 2026-08-08 for the full sweep.
        "sw_hands_target": 10,
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
        # v1h' (current_phase.md §v1h'): SW is planted with WHEAT and nothing else.
        #
        # Why WHEAT and not a mirror of NW/NE: (a) it is the only product we cannot saturate —
        # 5 of the 8 shops buy it (P(no buyer) = 0.04%) and its cliff is >2000 units against
        # WOOL's 59 and MILK's 76; (b) we are its biggest *customer*, not its seller — 10
        # animals eat 1 WHEAT/day each, ~280 units/season, and buying that many pushes the
        # market price from $25 to ~$42 (below-I0 scarcity side), so a home-grown unit is worth
        # its avoided purchase, not its sale price; (c) STRAWBERRY cannot go here at all —
        # strawberry_last_plant_day is 5 and SW is not affordable until well after that; (d) no
        # PASTURE/COOP goes here, deliberately: BUY_LAND's gate requires every planned animal
        # already placed, so a structure on not-yet-bought land deadlocks it (the trap that
        # already kept COOP in v1e and PASTURE in v1g on NW).
        #
        # Not fertilized, on purpose: one FERTILIZE covers day..day+2, i.e. all three of
        # WHEAT's yield-bearing waterings, doubling the tile's 3 units to 6. But the marginal
        # FERTILIZER unit still sells for ~$88-100 on a curve 493 units deep, against +3 WHEAT
        # worth ~$75-125. That is a coin-flip, not a win, and it would need its own gate.
        #
        # 12, screened on DEV_SEEDS against checkpoints/v1g_1 under pinned towns: 8 tiles is
        # too little to pay for the land and the crew (+$796/ep on a 4-seed smoke), 16 earns
        # slightly more per episode (+$3,190 vs +$2,942) but pushes the 100-slot shed into
        # overflow — 3,100 units burnt across 96 episodes against 12's 40 — and still lost an
        # animal. 12 is the size that clears every hard metric with 48/48 seed wins.
        "sw_wheat_tiles": 12,
        "sw_max_new_plants_per_day": 3,
        # WHEAT is one-shot (HARVEST empties the tile), so a tile is a repeating ~5-day cycle
        # and a seed planted too late never matures (yield peaks at max_yield_day = age 4).
        #
        # 20, not 22, and the reason is measured rather than arithmetic. At 22 a tile is still
        # alive and still generating priority-0 WATER tasks *during liquidation* (day >= 26),
        # where they compete directly with FEED for the same units — a seed-0 smoke run lost
        # both far SHEEP ((0,2) and (0,3), distance 5-6) to consecutive_unfed on day 27 with
        # $35k in the bank, i.e. purely to unit contention, not to money. Cutting off at 20
        # means the last tile is harvest-ready on day 24 and the whole quadrant is empty before
        # liquidation starts, so the endgame keeps the undivided crew v1g's feed logistics
        # were sized around. The cost is the tail of one cycle; the alternative was an
        # animals_escaped gate failure.
        "wheat_last_plant_day": 20,
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
            # v1h': the SW quadrant (x < 5, y >= 5), ordered nearest-shed-spawn-first — WHEAT
            # is watered on 4 of every 5 days (ages 1-4: age 1 to survive consecutive_unwatered
            # >= 2, ages 2-4 inside the engine's yield window) plus a PLANT and a HARVEST visit
            # per cycle, so the commute is paid ~6 times per 5 days per tile and tile distance
            # dominates the cost. Same unlock-gated growth story as the NE mirrors above: SW
            # tiles read "LOCKED" (a string, not None) until BUY_LAND lands, so build_tasks'
            # `tile is None` check makes every entry past the unlock a harmless no-op.
            # (4, 5) is deliberately absent even though it is the nearest SW tile of all: it is
            # one of the four shed-access tiles every PICKUP/DROP in the feed pipeline stands
            # on, and the 10-animal feed loop is not worth risking for one tile.
            "WHEAT": (
                (3, 5), (4, 6),
                (2, 5), (3, 6), (4, 7),
                (1, 5), (2, 6), (3, 7), (4, 8),
                (0, 5), (1, 6), (2, 7), (3, 8), (4, 9),
                (0, 6), (1, 7), (2, 8), (3, 9),
            ),
        },
        # plan.md §5.1 v1d / v1g: reserved structure tiles for animal placement, carved up
        # per-name by agent.animal_slots.animal_slot_ranges in config["animals"]["targets"]
        # dict order — the first `targets["COW"]` PASTURE tiles below are COW's, the next
        # `targets["SHEEP"]` are SHEEP's. v1h.2 D2 therefore uses the first 4 for COW and the
        # next 6 for SHEEP; the 3 trailing v1g-era reserve positions are currently unused.
        # All PASTURE candidates are NW (owned from day 0):
        # current_phase.md v1g deliberately never places a structure on not-yet-purchased
        # land — BUY_LAND's gate (executor.py) requires every planned animal already placed,
        # so a structure sitting on NE-locked land would deadlock it (the same reasoning that
        # already put GOOSE's COOP on NW in v1e — see its comment below). Ordered nearest-
        # shed-first because FEED/CARE is a recurring daily commute.
        "animal_structure_tiles": {
            "PASTURE": (
                # Active 4C/6S carve consumes the first ten positions in this order.
                (4, 2), (3, 3), (2, 4), (3, 2), (2, 3), (4, 0), (0, 4), (0, 3),
                (0, 2), (2, 0), (0, 1), (1, 0), (0, 0),
            ),
            # plan.md §5 v1e: GOOSE's COOP, placed on the reclaimed NW STRAWBERRY tile (3, 0)
            # rather than NE — see strawberry_tiles comment in config["planner"] for why NE
            # would deadlock BUY_LAND's full-herd gate.
            "COOP": ((3, 0),),
        },
    },
    "executor": {
        "enabled": True,
        "max_market_orders": 10,
        "seed_buffer": 6,
        # v1g.2: these stay the hard lower bound. planner._dynamic_sell_floors may only RAISE a
        # product's floor above the value here (and only for products with non-zero NPC demand),
        # never lower it — so turning dynamic_sell_floor off restores the pre-v1g.2 behaviour
        # exactly, which is what makes the two sides of the $-gate a clean A/B.
        "sell_floor_price": {
            "CARROT": 5,
            "STRAWBERRY": 8,
            "EGG": 5,
            "MILK": 15,
            "WOOL": 20,
            "FERTILIZER": 10,
        },
        # v1h.2 D3: endgame used to bypass every floor and sell the whole shed, including
        # 2,035 DEV units at <=$5 after the 1.32.6 demand cut. Keeping the normal product
        # floors during liquidation stranded too much stock (shed overflow 1,809 -> 2,036),
        # so liquidation gets the weakest floor that still protects the hard metric.
        "liquidation_floor_price": 5,
        # v1g.2 (γ): size each floor against the glut the town can actually work off, read from
        # the shops that actually unlocked this episode. See planner._dynamic_sell_floors for
        # why a floor and a rate cap are the same object here.
        #
        # ⚠️ OFF — MEASURED NEGATIVE, HYPOTHESIS FALSIFIED (2026-08-07, DEV_SEEDS 0-7 vs
        # checkpoints/v1g_1). The premise of current_phase.md §v1g.2 (γ) — "near-zero NPC demand
        # makes aggressive selling self-destructive" — does not hold in this engine, because the
        # agent is production-constrained, never glut-constrained: our ~2 wool/day sell rate is
        # below NPC absorption even with town-centre demand alone, so market inventory stays
        # BELOW I0 and every sale realizes the scarcity side of the price curve. The glut side
        # the floor protects against is never reached. Measured consequence: throttling bought
        # no price at all (WOOL $241.46/u -> $241.37/u) and only removed volume (348u -> 328u),
        # for -$1,103/ep in a full town, -$1,909/ep with no YARN_STORE — i.e. it lost hardest in
        # the exact town it was designed for — and -$24,762/ep with no shops at all. Gating it on
        # shop_evidence_min_unlocks removes the loss but yields exactly $0 upside, because once
        # the early season is left alone the floor never binds: with min_unlocks=5 the delta is
        # -$16 in a full town and +$0 in a no-YARN_STORE town, 0/8 wins everywhere.
        #
        # Left in place, disabled, as the artifact those numbers refer to. Turning it on is a
        # measured regression, not a tuning opportunity — the missing-shop risk is production-
        # side (a wool-less town costs $12,077/ep by itself) and sell-side adaptation cannot
        # reach it. See memory.md 2026-08-07 and current_phase.md §v1g.2.
        "dynamic_sell_floor": False,
        # How many days' worth of NPC demand of glut to tolerate before refusing to sell. Higher
        # = weaker throttle (3.0 already leaves STRAWBERRY's floor below its static 8 with a full
        # town, i.e. inactive, while binding on CARROT/MILK/WOOL). A BBO sweep knob
        # (current_phase.md §BBO); 3.0 is the value the v1g.2 gate was run at.
        "sell_headroom_days": 3.0,
        # How many shops must have unlocked before "no shop buys this" is evidence about the
        # town rather than about the calendar. Shops appear one per townShopUnlockInterval (3)
        # days in both the current and the announced regime, so day 4 always looks shop-poor;
        # throttling on that taxes the early season, where revenue still compounds into
        # hands/animals/land. Measured: without this gate the layer cost $1,103/ep on
        # DEV_SEEDS 0-7 against checkpoints/v1g_1 at every headroom that bound at all.
        "shop_evidence_min_unlocks": 5,
        "opponent_price_safety_units": 4,
    },
    "land": {
        # plan.md §5 v1c / MASTERPLAN §3.2#7: buy NE as soon as money allows AND a workforce
        # actually exists to work it (buying land before hands_target hands are hired would
        # be dead capital).
        "enabled": True,
        # v1h': how many quadrants past NW to buy, in the engine's own fixed LAND_ORDER
        # (NE $1000 -> SW $2000 -> SE $4000 — BUY_LAND takes no argument, the engine picks the
        # next one). SE is deliberately excluded, not merely unreached: nobody in the elite
        # buys it (topfarms-19, which has the #3 quadrant landing around day 11 and the #4
        # never), and at $4000 it would be a fourth quadrant we already cannot staff.
        # Listing the names rather than a count keeps this checkable against LAND_ORDER
        # instead of being a bare "2" that silently means something else after an engine bump.
        "quadrants": ("NE", "SW"),
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
        # v1h.2 D2 (engine 1.32.6): the town centre now absorbs 30 rather than 140 units
        # per product/season. In mirror, 6 COW per side collapsed MILK to $31-37 while WOOL
        # stayed healthy at $197-243. DEV pinned-basket screen vs v1h_2b:
        # 4C/6S +$2,644/ep with 0 water weeds and 54 escapes; 5C/4S +$2,191 but 52/122;
        # 4C/4S -$1,055 with 66/0. Keep ten animals but diversify production toward WOOL.
        "targets": {"COW": 4, "SHEEP": 6, "GOOSE": 0},
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
        "shed_capacity": 100,
    },
}
