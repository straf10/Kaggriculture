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
        # for the v1g animal-mass increment. NE's carrot mirror tiles
        # (ne_carrot_tiles) are untouched.
        #
        # ⛔ v1p.1 (ROADMAP §4.3 S3 step 1c, herd compaction — arm A) STOPPED at SMOKE, kept at 3.
        # Tried: reassign (3, 4) and (4, 3) — the two remaining NW CARROT tiles here besides
        # (4, 4), distance 1 from the (4,4) shed spawn and otherwise idle land (CARROT is
        # $34,9/tile-day, the worst crop in the game — §3.2(6) — and §4.3 already wants it at
        # zero) — from CARROT to PASTURE's two farthest SHEEP slots ((0, 2)/(2, 0), distance 6
        # each: the same tail that lost animals in v1h', v1o.2 and v1o.3). carrot_tiles would
        # drop 3 -> 1 and the herd's summed shed distance 39 -> 27 across all 10 claimed slots.
        #
        # SMOKE 0-11, both seats, `--town-pin basket`, mirror vs `checkpoints/v1o_2`:
        # `animals_escaped_a` **48 vs 2** (100% reproducible — every single one of the 24
        # orientations, `mean_diff` -$875,4 INCONCLUSIVE, `metric_gate_passed` False,
        # `crop_tile_days`/ep 494,0 vs 616,2. `worker_turns_moving` DID fall (61,7% -> 53,6%,
        # confirming the geometry change itself works as intended) but the animal side broke
        # completely differently from every prior escape STOP: the loss is not the measured tail
        # ((0,3) etc., §3.3) but two **COW** at (3, 2)/(3, 3) — tiles this change never touched —
        # escaping at exactly step 48 (day 2) in every single seed and both seat orientations
        # (analysis dump: escapes/analysis_v1p1_armA_escape_diag, local). Root cause, traced
        # directly against the replay: `assign()`'s greedy loop has no notion of animal type, only
        # priority + distance (scheduler.py's sort key) — PLACE is priority 1 for every animal
        # name, so on day 0 the two new distance-1 SHEEP slots out-race COW's own distance-2/3
        # slots for every unit as they free up, and COW's PLACE (and the FEED cycle that only
        # starts once an animal is actually placed) is pushed back far enough to cross the
        # `consecutive_unfed >= 2` escape threshold — a structural side effect of making some
        # PASTURE slots closer to spawn than *any* of COW's own slots, not a `strawberry_last
        # _plant_day`/`sw_hands_target`-style economic trade. It is intrinsic to reassigning
        # distance-1 tiles to SHEEP specifically (arms B and C in the original screen share the
        # same two tiles and would hit the identical race), not a bookkeeping detail of this one
        # arm, so no further variant of "give SHEEP the freed CARROT tiles" was screened. See
        # ROADMAP §3.3 and memory.md 2026-08-13.
        #
        # ⛔ v1p.1b (ROADMAP §4.3 S3 step 1c) STOPPED at SMOKE, kept at 3 — this closes the
        # "convert a CARROT tile to compact the herd" family for good. Two untested controls
        # v1p.1's own root cause implied, both run: arm A1 (same tile set as arm A, COW instead
        # of SHEEP gets the two distance-1 tiles — see animal_structure_tiles["PASTURE"] below)
        # and arm B (carrot_tiles 3 -> 1 alone, PASTURE completely untouched — the confound
        # control arm A never ran). Both fail. Arm A1: `animals_escaped_a` **48** (vs its own
        # paired `v1o_2` mirror at 0), the same magnitude as arm A's original 48 — but now a
        # *mixed* pair, (4,2) COW and (3,2) SHEEP, not the pure-COW pair arm A hit, at the same
        # day 2 / step ~48 timing (`worker_turns_moving` did fall, 60,3% -> 46,0%, confirming the
        # geometry itself still works). **This refutes v1p.1's own root cause**: giving COW the
        # close tiles instead of SHEEP does not fix the race, so it was never a type-blind
        # SHEEP-vs-COW contest specifically. Arm B: `animals_escaped_a` **12** (vs its own paired
        # baseline 2), seed/orientation-dependent (6 of 24) rather than deterministic, with **zero
        # PASTURE change at all** — dropping carrot_tiles below 3 is *itself* destabilizing to the
        # feed pipeline, independent of what the freed land becomes. Excess-over-own-baseline
        # decomposition (§2.1.1: paired baselines legitimately differ seed-to-seed under RNG
        # coupling, so this is approximate): arm A1 excess ~48, arm B excess ~10, geometry-only
        # ~38. Analytically confirmed separately: NW is fully allocated (3 CARROT + 8 STRAWBERRY
        # + 13 PASTURE + 1 COOP = 25) and the 13 PASTURE tiles sorted by distance are
        # 2,2,2,3,3,4,4,5,6,6,7,7,8 — the ten currently-claimed slots are already the ten
        # nearest, so there is no free reorder left inside the existing PASTURE pool; proximity
        # can only be bought by converting a crop tile, and that purchase does not pay for
        # itself. Checkpoints `checkpoints/v1p1b_armA1` / `checkpoints/v1p1b_armB`. See ROADMAP
        # §3.3 and memory.md 2026-08-13.
        "carrot_tiles": 3,
        # v1e: reduced from 16 to 15 to free tile (3, 0) for GOOSE's COOP structure
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
        # freeing the 11 new PASTURE slots v1g asks for (2 existing + 11 new
        # = 13, matching the elite ceiling of 8 COW + 5 SHEEP). NW is fully allocated either way
        # (3 CARROT + 8 STRAWBERRY + 13 PASTURE + 1 COOP = 25); this is a targeted reclaim to
        # fit the new structures, not the full crop/animal portfolio rebalance MASTERPLAN
        # reserves for v1h.
        "strawberry_tiles": 8,
        # v1o.1 (ROADMAP §4.3 S3 step 1): the single gate that shut the farm down. E0
        # (analysis/e0_s3_blockers.py, 4 seeds x both seats vs meta_route) traced the planner's
        # own raw targets per day and found STRAWBERRY's raw target drops to 0 on **day 6** and
        # never returns: the 8 tiles planted on days 0-5 reach their 4th and last yield tick
        # (first_yield_day 10 + interval 2 * 3 = age 16) around days 17-21, decay to WEED, and
        # nothing is ever planted behind them. Measured consequence at the old value of 5:
        # planted tiles peak at **26** on d14-17 and fall to 18 (d20) / 11,5 (d24) / 0 (d28),
        # against the current-engine top-30 profile's 62 / 60 / 59 / 1
        # (data/derived/b3_target_profile.json). That is ROADMAP §3.2's "our farm shuts down on
        # day 17", and it is a config constant, not an emergent capacity limit: the capacity
        # gate (_capacity_limited_targets) trims nothing at all on days 14-24, and the crew hits
        # its hands_target on every single day of all 8 E0 runs.
        #
        # Why 12 and not later. STRAWBERRY is `ongoing` with first_yield_day 10 and interval 2,
        # so a seed planted on day P first pays on P+10 and reaches its full 4 ticks on P+16 —
        # arithmetic alone would say 19. The value is screened, and the screen says the opposite
        # of the arithmetic. SMOKE 0-11, both seats, `--town-pin basket`, mirror vs
        # `checkpoints/v1i`:
        #
        #   value | mean_diff | verdict      | crop tile-days | idle  | clipped_production_ticks
        #      12 |   +$603   | INCONCLUSIVE |          515,3 | 20,2% | 0
        #      16 | -$4.071   | REGRESSED    |          567,7 | 15,8% | 1  <- structural, hard STOP
        #      20 | -$7.913   | REGRESSED    |          615,3 | 14,3% | 1  <- structural, hard STOP
        #
        # Tile-days and idle keep improving monotonically past 12 and the bank keeps falling,
        # because the extra watering is paid for out of the animals: analysis/
        # v1o1_product_split.py (vs the non-mirror `meta_route` bench) measured STRAWBERRY going
        # 32 -> 80 units at a *higher* realized price ($232,9 -> $259,0, i.e. no saturation at
        # all) while WOOL lost 41% of its units and FERTILIZER 27% — HARVEST on an animal tile
        # is priority 1 and COLLECT_FERTILIZER is priority 3, both below WATER's 0, so new
        # priority-0 crop work crushes them first. 16 and 20 additionally break a *structural*
        # counter (an animal's yield left uncollected past its cap), which is a STOP under
        # ROADMAP §2.1.5 regardless of the dollar verdict.
        #
        # So 12 is not "the best window" — it is the largest window that today's task priorities
        # can actually staff. Raising it again is gated on protecting animal upkeep from crop
        # watering first; see ROADMAP §3.3.
        "strawberry_last_plant_day": 12,
        # v1o.1: WHEAT's start used to be spelled `snapshot.day > strawberry_last_plant_day`
        # (planner.make_day_plan), which silently coupled the two windows — extending
        # STRAWBERRY's window by itself would have pushed WHEAT's first plant to day 17 and
        # deleted the SW quadrant's whole season. Split out as its own knob, set to the day the
        # old expression produced at strawberry_last_plant_day=5, so the decoupling is
        # behaviour-preserving at the old value and the two windows can now be screened apart.
        # The ordering reason the old expression encoded is still real and is preserved by the
        # comment on sw_wheat_tiles: STRAWBERRY has a hard planting deadline and WHEAT does not,
        # so where the capacity gate has to choose, WHEAT is the one that can wait.
        "wheat_first_plant_day": 6,
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
        # without first growing the real workload". SW is that
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
        # v1o.2 (ROADMAP §4.3 S3 step 1, crew shape): screened again on top of v1o.1's refilled
        # farm, because every number above was measured against a farm that emptied after day 17
        # and therefore against a workload that no longer exists. The top-30 profile
        # (data/derived/b3_target_profile.json) runs 14 hands at d10 and d20; E0 established
        # that our crew is capped by this constant alone and never by the fib() hire budget
        # (`days_hands_below_target` was empty in all 8 runs at 10 hands) — so whether a larger
        # crew is affordable is a real question this screen had to answer rather than assume.
        #
        # It took two screens. The first raised this constant alone and measured 10 -> 12 -> 14
        # as **byte-identical** (mean_diff exactly $0,00, CI [0, 0]) — the ceiling was the
        # engine's 10-orders-per-turn limit, not this number (see executor.hire_last_hour). With
        # that unblocked, SMOKE 0-11 both seats `--town-pin basket` vs `checkpoints/v1o_1`:
        #
        #   (sw, endgame, hire_last_hour) | mean_diff | verdict      | tile-days | idle
        #   (10, 6, 0)  slot-cap only     |  -$9.704  | REGRESSED    |       415 | 15,9%
        #   (12, 6, 2)                    |  +$4.316  | IMPROVED     |       595 | 25,2%
        #   (14, 6, 2)                    |  -$1.516  | INCONCLUSIVE |       599 | 31,8%
        #   (14, 10, 2)                   |    -$591  | INCONCLUSIVE |       603 | 32,8%
        #
        # 14 buys 4 more tile-days than 12 and pays fib(12)+fib(13) = $610/day extra for them,
        # with idle unit-turns going the wrong way (25,2% -> 31,8%) — the crew overshoots the
        # work again, which is the same shape v1f measured at its own scale.
        #
        # ⛔ **12 then went to DEV and STOPPED on the acceptance arm**, and the number is left
        # at 10. DEV 0-47 both seats, pinned, vs `meta_route`: the dollars were the best this
        # session has produced (`mean_diff` **+$4.144,7**, IMPROVED, episodes **82-14**,
        # `median_bank` **$59.409**) — and `priced_loss_delta` came in at **$477,6/ep against a
        # budget of $414,5** (10% of mean_diff; it is inside the $500 absolute leg but the rule
        # is AND, not OR), driven by `animals_escaped` **87 vs 32**. That is ROADMAP §2.1.5, and
        # it is not a tuning opportunity: the mechanism is that 12 hands on ~594 crop tile-days
        # generate more priority-0 WATER than the same tier's FEED can survive, which is the
        # *same* displacement analysis/v1o1_product_split.py measured taking 41% of WOOL and 27%
        # of FERTILIZER. The crew is not the fix for that and cannot be raised past it; feed
        # priority has to be protected first. See ROADMAP §3.3 and memory.md 2026-08-11.
        "sw_hands_target": 10,
        # v1o.2: what the crew drops back to once SW's last WHEAT is harvestable
        # (wheat_last_plant_day + max_yield_day = day 24). Was hard-wired to the pre-SW
        # `hands_target` of 6; split out so the endgame crew can be screened apart from the
        # mid-season crew. It is not cosmetic: v1o.1's unpinned holdout carries 240
        # water_weeds_lost, and the mechanism is this step-down — the capacity gate's floor
        # holds every already-planted tile, so the tiles stay but a third of the crew that was
        # watering them does not. The counter-argument is measured too and is why 6 was chosen
        # in v1h': carrying the big crew into liquidation lost 2 far SHEEP per episode to unit
        # contention on days 25-27 (see planner.make_day_plan).
        #
        # Screened and **left at 6**: raising it to 10 alongside a 14-hand mid-season crew moved
        # nothing worth having (-$591 vs -$1.516, both INCONCLUSIVE, water-weeds 44 vs 52 on 24
        # smoke episodes). The step-down is therefore not the water-weed mechanism it looked
        # like; the tiles that die are dying of priority, not of headcount. Kept as a separate
        # knob because that is now a *measured* answer rather than an assumption.
        "endgame_hands_target": 6,
        "capacity_safety_factor": 0.8,
        # v1c: added to carrot_tiles/strawberry_tiles once "NE" is in
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
        # v1c: without this, CARROT and STRAWBERRY compete for the SAME shared
        # max_new_plants_per_day budget (scheduler.py build_tasks) in CARROT-first order —
        # doubling carrot_target's tile count alone let CARROT's many newly-empty NE tiles
        # eat the whole day's planting budget every day, starving STRAWBERRY of any planting
        # slots at all (observed in a v1c smoke test: 8 STRAWBERRY sold over 30 days vs 64
        # pre-v1c). Doubling the daily budget alongside the tile counts keeps both crops
        # actually plantable.
        "ne_max_new_plants_per_day": 5,
        # v1h': SW is planted with WHEAT and nothing else.
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
        # ⛔ v1p.2 (ROADMAP §4.3 S3 step 1c, zone assignment) STOPPED at SMOKE, kept at False.
        # `assign()`'s global argmin takes no account of *where* a unit already is relative to
        # where the rest of the day's work is — a hand standing in one owned quadrant can be
        # pulled to a task in another, a commute of up to ~12 turns to perform one 1-turn action.
        # `worker_turns_moving` measured 57-62% of every unit-turn
        # (analysis/v1o3_visit_efficiency.py, ROADMAP §3.3), and v1o.3 already showed that
        # nothing *inside* a saturated priority tier can be reordered profitably — this instead
        # narrowed *which units* a task is even offered, via scheduler._zone_partition (kept, see
        # its docstring for the full mechanism: proportional to that turn's real task counts per
        # quadrant, a filter on eligible units never on tasks, explicit fallback to the global
        # pool, WHEAT-carriers zone-exempt).
        #
        # SMOKE 0-11, both seats, `--town-pin basket`, mirror vs `checkpoints/v1o_2`:
        # `mean_diff` **-$6.966,0, REGRESSED, p=4,9e-4**, episodes 0-24. The roadmap's own kill
        # criterion (§4.3 S3 step 1c: "if the best arm does not move worker_turns_moving below
        # ~55%, zoning is not binding") fired at the very first screen — `worker_turns_moving`
        # barely moved (60,0% -> 58,7%, B vs A), nowhere near the target, so the commute share
        # this increment exists to cut was essentially untouched. Worse, it broke a *structural*
        # hard-zero counter: `plant_decay_units_lost` **17** (0 at baseline; ROADMAP §2.1.5, a
        # STOP on its own regardless of the dollar verdict), alongside `animals_escaped` 20 vs 6
        # and `shed_overflow_burnt` 12 vs 0.
        #
        # WHY, most likely (not re-tuned against, only documented — ROADMAP §2's STOP protocol):
        # the zone partition is a pure function of the *current* snapshot, recomputed fresh every
        # `assign()` call, with no memory of which zone a unit was in the turn before. A unit
        # mid-walk toward a task it is already `committed` to (the C1 stickiness mechanism this
        # module's docstring describes at length, built to stop exactly this class of thrash) can
        # be re-zoned OUT of eligibility for that same task the very next turn, as soon as the
        # day's task-count mix shifts by one WATER or FEED task finishing elsewhere — silently
        # discarding progress on a walk already paid for. `committed`'s switching bonus lives
        # *inside* the eligible set; a hard exclusion from that set bypasses it entirely. This is
        # consistent with the observed pattern: the counters that broke are exactly the ones with
        # a hard multi-turn deadline (WATER's decay clock, FEED's `consecutive_unfed`), and the
        # damage is sparse and seed/day-dependent (occurs on 4 of 12 SMOKE seeds) rather than the
        # 100%-reproducible mechanism v1p.1 found — consistent with a timing-dependent
        # re-zoning race, not a fixed geometric flaw. A zone-aware stickiness extension (folding
        # `committed` into `_zone_partition` so a unit already walking toward a task keeps its
        # eligibility) is a plausible fix but was not built or screened — that would be tuning
        # against this specific measured failure, not the next independently-motivated
        # increment. Hands off to ROADMAP §4.3's deferred item ③ (min-cost matching inside
        # `assign()` itself) per the kill criterion's own instruction.
        #
        # ⛔ v1p.2b (ROADMAP §4.3 S3 step 1c) STOPPED at SMOKE, kept at False — the untested
        # control v1p.2's own root cause implied, now run. `scheduler._zone_partition` threads
        # `committed` through and pins a unit with a live commitment to its own task's zone
        # before any quota is computed (see that function's docstring), closing exactly the
        # thrash class v1p.2's STOP diagnosed. It worked at the structural level: the hard-zero
        # break is gone (`plant_decay_units_lost` 0, was 17) and `animals_escaped` is back to
        # parity with baseline (5 vs 5, was 20 vs 6). But the number the whole increment is
        # judged on did not move: SMOKE 0-11, both seats, `--town-pin basket`, mirror vs
        # `checkpoints/v1o_2`: `worker_turns_moving` **58,9% -> 60,3%** (candidate vs baseline),
        # essentially the same ~1,4pp non-movement as v1p.2's own original screen (58,7% vs
        # 60,0%), nowhere near the roadmap's ~55% target. `mean_diff` -$2.688,6, REGRESSED
        # (CI [-3.832,5, -1.544,8]), driven by `water_weeds_lost`/`unexpected_weeds_lost` 226 vs
        # 61 and new `shed_overflow_burnt` 18 vs 0 — the fix removed the thrash-driven structural
        # break but not the underlying commute cost, and traded it for a different, smaller loss
        # pattern. Per this increment's own restated kill criterion (ROADMAP §4.3 S3 step 1c):
        # stickiness in place and `worker_turns_moving` still does not fall means the constraint
        # genuinely is not *which* tasks a unit is offered — zoning was never the lever.
        # **Refuted, not just under-delivering**: hands off to the deferred travel-ratio
        # diagnostic (ROADMAP §4.3 item ③), not directly to min-cost matching (item ④), per the
        # kill criterion's own instruction — that diagnostic decides whether ④ is even
        # justified. Checkpoint `checkpoints/v1p2b`. See ROADMAP §3.3 and memory.md 2026-08-13.
        "zone_assignment_enabled": False,
        # ======================================================================================
        # ⛔ v1o.3 (ROADMAP §4.3 S3 step 1b) — "protect the animal-upkeep pipeline". **STOPPED on
        # the acceptance arm.** Every value below is at its pre-v1o.3 default, so this whole block
        # is behaviourally inert and live `main.py` remains behaviour-identical to
        # `checkpoints/v1o_2` (verified: mirror compare, mean_diff exactly $0,00, all ties). The
        # code is kept, disabled, as the artefact these numbers refer to — the same treatment
        # `dynamic_sell_floor` gets, and for the same reason. `checkpoints/v1o_3` is retained as
        # the *stopped* variant E that `gates/v1o3_dev_*` keys to; it is not the shipped agent.
        #
        # WHAT IT WAS FOR. assign()'s sort key leads with task.priority, so a tier-1 task never
        # beats a tier-0 one at any distance. With v1o.1/v1o.2's ~60 planted tiles the tier-0
        # WATER pool no longer empties inside a day, and everything at tier >= 1 starves
        # deterministically: analysis/v1o1_product_split.py measured WOOL losing 41% of its units
        # and FERTILIZER 27% while STRAWBERRY volume rose 2,5x at a *higher* realised price, and
        # the sw_hands_target=12 STOP measured escapes 87 vs 32 on the same mechanism.
        #
        # ⚠️ The measurement that shaped the design, and that no earlier screen had made: **the
        # feed round is open 100% of the hours of a median day from day 9 onward** (>=70% every
        # day from day 7; 8 runs vs meta_route, per-hour count of animals with fed_today false).
        # There is no moment in the season when the crew is free of tier-0 work — so "wait for a
        # quiet moment" is not an available strategy, and any reordering inside that tier is
        # strictly zero-sum.
        #
        # THE LADDER — SMOKE 0-11, both seats, `--town-pin basket`, mirror vs `checkpoints/v1o_2`:
        #
        #  variant                              | mean_diff | verdict      | esc A/B | underfed | decay
        #  A  bundle only                       |   +$3.198 | IMPROVED     |  15 / 6 | 51,6/36,1|  0
        #  B  A + fertilizer 3->2               |     +$644 | INCONCLUSIVE |  23 / 6 | 52,2/36,6|  6
        #  C  A + FEED/PICKUP -1/-2             |   -$1.036 | INCONCLUSIVE |   1 / 2 | 36,1/35,0|  4
        #  D  B + C                             |   +$3.121 | IMPROVED     |   1 / 8 | 36,6/35,4| 14
        #  A2 A + bundle yields to feed round   |      +$26 | INCONCLUSIVE |   5 / 4 | 35,4/34,9|  0
        #  E  A + C + crop-harvest decay guard  |   +$4.445 | IMPROVED     |   1 / 2 | 35,2/34,7|  0
        #  F  E + fertilizer 3->2               |   +$3.548 | IMPROVED     |   0 / 3 | 36,2/34,4|  7
        #
        # ⛔ AND THEN THE ACCEPTANCE ARM SAID NO, TWICE. DEV 0-47, both seats, pinned, vs the
        # non-mirror `meta_route` bench, `--arm-role acceptance`, against `v1o_2`'s own numbers on
        # the identical arm ($59.875,5 median_bank / +$4.839,9 mean_diff / 84-12 episodes):
        #
        #   E  (the SMOKE winner)  | median_bank $59.469,5 | mean_diff   +$61,6 | 50-46 | decay 14
        #   A3 (bundle alone)      | median_bank $58.258,5 | mean_diff -$3.793,4| 34-62 | escapes 77
        #
        # E worked *exactly as designed* and that is what makes the result decisive:
        # `animals_escaped` went 13 -> **0**, the pipeline was fully protected — and it was paid
        # for out of production (`crop_tile_days` 58.749 -> 55.099, `crop_revenue` -$2.361/ep),
        # while `animals_underfed_days` still got *worse* (2.942 -> 3.198). Thirteen prevented
        # escapes are worth ~$271/ep. The watering they cost is worth ~$2.361/ep. The exchange
        # rate inside the saturated tier is simply bad, because ROADMAP §3.2(5) still holds: the
        # whole gap to the top-30 is in plants, and we are at 573 crop tile-days against 1.316.
        #
        # ⚠️ AND THE MIRROR ARM SAID YES: +$4.877,5, IMPROVED, 40-8 seeds, p=3,3e-6, 79-17
        # episodes. This is the sharpest demonstration this repo has produced of ROADMAP §3.4's
        # "the mirror loop optimises inside a ceiling it cannot see" — a change that beats its own
        # predecessor decisively and buys nothing at all against a stronger opponent. Had the
        # acceptance arm not existed, v1o.3 would have shipped.
        # ======================================================================================
        "animal_task_priority": {"CARE": 1, "HARVEST": 1, "COLLECT_FERTILIZER": 3},
        # FEED and its mandatory PICKUP WHEAT predecessor. They move together or not at all —
        # _carries_cargo makes a FEED task eligible only for a unit that already holds WHEAT, so
        # promoting FEED alone does nothing on the turns where nobody has any. (0, -1) is the
        # v1h' ladder: FEED merely *shares* tier 0 with WATER and only an already-missed animal
        # jumps ahead. Screened at (-1, -2): variant C alone -$1.036 with water_weeds 46 -> 120,
        # and inside variant E it drove escapes to 0 at the cost of production. Left at v1h'.
        "feed_priority": 0,
        "feed_at_risk_priority": -1,
        # The tier a crop HARVEST claims once its own tile is actually losing yield today (engine
        # _decay_plants, :738-752, strips one yield_unit every second step past max_lifespan_step
        # — a strawberry at its 4-unit cap is bare in eight steps). None is a strict no-op. It
        # only has a job when FEED is promoted above tier 0, because -1 would then outrank the
        # only *other* task in the game with a hard yield deadline: variants C and D broke
        # `plant_decay_units_lost` (4 and 14 on 24 episodes) on exactly that. Setting it to -1
        # took SMOKE decay to 0 but only made it rarer, not absent — DEV measured 14 (acceptance)
        # and 22 (mirror) on 96 episodes, still a structural failure under ROADMAP §2.1.5.
        "crop_harvest_at_risk_priority": None,
        # Animal-visit bundling: promote this tile's remaining CARE/HARVEST/COLLECT_FERTILIZER to
        # `bundle_priority` for the unit ALREADY STANDING on it, so a visit is finished in place
        # (1 turn) instead of re-commuted (2*distance + 1). The mechanism is real and was measured
        # working against the non-mirror bench: `worker_turns_moving` 62,0% -> 57,5%,
        # COLLECT_FERTILIZER ops 123 -> 193/ep, FERTILIZER units 123 -> 191/ep.
        #
        # ⛔ Off, because it has nowhere safe to sit. At tier 0 it out-competes the tier-0 feed
        # round itself — PICKUP WHEAT and FEED are always at distance >= 1, a bundle is always at
        # distance 0 — and DEV acceptance measured that as **-$3.793,4, REGRESSED, 34-62, escapes
        # 77 vs 5, animals_underfed_days 57,6 vs 31,5** (variant A3). Below the feed round it needs
        # the feed round promoted above WATER, which is variant E and its own STOP above.
        "bundle_animal_visits": False,
        "bundle_priority": 0,
        # The third option: suppress the bundle entirely while any animal is still unfed.
        # Measured and rejected (variant A2): +$26/ep, INCONCLUSIVE, every counter back at
        # baseline. It does not under-perform — it does *nothing*, because the feed round is open
        # 100% of the hours of a median day, so a bundle that waits for it never fires at all.
        "bundle_yields_to_feed_round": False,
        "target_tiles": {
            # v1g: (3, 3)/(2, 4)/(2, 3)/(4, 0) — the 4 farthest-from-shed of the original 7 —
            # reclaimed for PASTURE (see carrot_tiles comment above). The 3 nearest NW tiles
            # stay CARROT so late-game planting (after STRAWBERRY's window closes, before NE
            # unlock) still has a target.
            #
            # ⛔ v1p.1 tried reassigning (3, 4)/(4, 3) to PASTURE — STOPPED, see the carrot_tiles
            # comment above. Left at their original 3 NW positions.
            "CARROT": (
                (4, 4), (3, 4), (4, 3),
                # v1c: NE mirror (x' = 9 - x) of the original 7 NW tiles, appended
                # so target_index 3+ only ever produce PLANT tasks once plan.plant_targets
                # grows past 3 — which planner.py only does once "NE" is actually unlocked
                # (still LOCKED tiles fall through build_tasks' `tile is None` check as a
                # harmless no-op until then). Left at its original 7 positions/count — only
                # NW's own tile count shrank, not NE's.
                (5, 4), (6, 4), (6, 3),
                (5, 3), (7, 4), (7, 3),
                (5, 0),
            ),
            # v1d: (4, 2) and (3, 2) were reassigned from STRAWBERRY targets to
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
                # v1c: NE mirror (x' = 9 - x) of the original 16 NW tiles, same
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
        # v1d / v1g: reserved structure tiles for animal placement, carved up
        # per-name by agent.animal_slots.animal_slot_ranges in config["animals"]["targets"]
        # dict order — the first `targets["COW"]` PASTURE tiles below are COW's, the next
        # `targets["SHEEP"]` are SHEEP's. Current targets are COW=4, SHEEP=6, GOOSE=0:
        # only the first 10 of 13 PASTURE slots are claimed; the final 3 stay unused, as does
        # the COOP slot below. All structure slots are NW (owned from day 0):
        # v1g deliberately never places a structure on not-yet-purchased
        # land — BUY_LAND's gate (executor.py) requires every planned animal already placed,
        # so a structure sitting on NE-locked land would deadlock it (the same reasoning that
        # already put GOOSE's COOP on NW in v1e — see its comment below). Ordered nearest-
        # shed-first across the claimed slots (FEED/CARE is a recurring daily commute cost
        # ×10 now, review_89d99f0_2026-08-05.md C1 §1.3).
        "animal_structure_tiles": {
            # ⛔ v1p.1 (ROADMAP §4.3 S3 step 1c) tried swapping (0, 2)/(2, 0) — the two farthest
            # SHEEP slots, distance 6 each — for (3, 4)/(4, 3), the two NW CARROT tiles freed by
            # the carrot_tiles comment above (distance 1 each), cutting the herd's summed shed
            # distance 39 -> 27. STOPPED at SMOKE: `animals_escaped_a` 48 vs 2 over 24
            # orientations, 100% reproducible — not the (0,2)/(0,3)/(2,0) tail these two tiles
            # were meant to fix, but two **COW** at (3, 2)/(3, 3) (untouched by this change)
            # escaping at day 2 every single episode. Root cause: `assign()`'s greedy PLACE
            # competition (scheduler.py) has no notion of animal type, only priority + distance —
            # making two SHEEP slots closer than *any* COW slot lets SHEEP win every early PLACE
            # race, pushing COW's first placement/feed cycle back far enough to cross
            # `consecutive_unfed >= 2`. Full mechanism in the carrot_tiles comment above; kept at
            # the original geometry.
            #
            # ⛔ v1p.1b arm A1 tried the untested control — COW instead of SHEEP on the same two
            # distance-1 tiles — and STOPPED too: `animals_escaped_a` 48, same magnitude, now a
            # mixed COW/SHEEP pair. Refutes v1p.1's own type-blind-race root cause; see the
            # carrot_tiles comment above. Kept at the original geometry.
            "PASTURE": (
                # COW block (4): distances 2,2,2,3 from the (4,4) shed spawn.
                (4, 2), (3, 3), (2, 4), (3, 2),
                # SHEEP block (6): distances 3,4,4,5,6,6.
                (2, 3), (4, 0), (0, 4), (0, 3), (0, 2), (2, 0),
                # Unclaimed PASTURE capacity (3): distances 7,7,8.
                (0, 1), (1, 0), (0, 0),
            ),
            # v1e: GOOSE's COOP, placed on the reclaimed NW STRAWBERRY tile (3, 0)
            # rather than NE — see strawberry_tiles comment in config["planner"] for why NE
            # would deadlock BUY_LAND's animal_placed gate.
            "COOP": ((3, 0),),  # GOOSE=0: listed capacity, never built.
        },
    },
    "executor": {
        "enabled": True,
        "max_market_orders": 10,
        # v1o.2: last hour of the day in which a HIRE order may still be emitted. 0 is the
        # pre-v1o.2 behaviour (hire the whole crew in hour 0), and 0 is also a hard ceiling of
        # exactly 10 hands, because one HIRE is one market order and the engine drops everything
        # past `maxMarketOrdersPerTurn` = 10 silently — see the long note in
        # executor.market_orders. Anything above 0 lets the crew finish assembling on later
        # turns at the same fib() price. Kept small: a hand hired at hour h works 24-h turns, so
        # the marginal value of a late hire falls while its fib cost does not.
        #
        # ⚠️ The two halves of v1o.2 are **not separable** and the screen proves it. Applying the
        # order-slot cap while leaving this at 0 measured **-$9.704/ep, REGRESSED, 0-24** with
        # crop tile-days collapsing 513 -> 415: with hires confined to hour 0, capping them at
        # the leftover slots simply means the day's SELLs starve the crew. review.md H8 was
        # right that HIRE must not lose to SELL — it is only safe to let it yield the slot
        # *because* the hire now happens one turn later instead of not at all.
        #
        # Gated on its own, at the unchanged crew of 10. The crew *size* increase that this
        # unblocked (sw_hands_target 12) is a separate, STOPPED question — see that knob. What
        # is kept here is only the hiring mechanism: at 10 hands it does not add a single hand,
        # it stops the morning's 10 HIREs from pushing that day's SELL orders off the end of the
        # engine's 10-order budget.
        "hire_last_hour": 2,
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
        # checkpoints/v1g_1). The premise of v1g.2 (γ) — "near-zero NPC demand
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
        # reach it. See memory.md 2026-08-07.
        "dynamic_sell_floor": False,
        # How many days' worth of NPC demand of glut to tolerate before refusing to sell. Higher
        # = weaker throttle (3.0 already leaves STRAWBERRY's floor below its static 8 with a full
        # town, i.e. inactive, while binding on CARROT/MILK/WOOL). A BBO sweep knob
        # 3.0 is the value the v1g.2 gate was run at.
        "sell_headroom_days": 3.0,
        # How many shops must have unlocked before "no shop buys this" is evidence about the
        # town rather than about the calendar. Shops appear one per townShopUnlockInterval (3)
        # days in both the current and the announced regime, so day 4 always looks shop-poor;
        # throttling on that taxes the early season, where revenue still compounds into
        # hands/animals/land. Measured: without this gate the layer cost $1,103/ep on
        # DEV_SEEDS 0-7 against checkpoints/v1g_1 at every headroom that bound at all.
        "shop_evidence_min_unlocks": 5,
        "opponent_price_safety_units": 4,
        # ROADMAP §4.3 S3 step 1e (v1r): the day-0 feed-cash reserve. The v1g reserve (see the
        # long note in executor.market_orders) sets aside FEED_RESERVE_DAYS' worth of WHEAT cash
        # for the herd before spending on new animals, so a whole batch bought in one hour can't
        # starve. Its liability count was `total_placed + buy_target` — animals already on tiles
        # plus the ones a single BUY order adds — which SILENTLY OMITS animals already bought on
        # earlier turns and still carried/in the shed (each of which eats one WHEAT/day the moment
        # it is placed). Spreading purchases across turns (arm A1's geometry does exactly this)
        # then bypasses the guard: with 5 animals in flight and 0 placed, the reserve was
        # (0+1)*25*2 = $50 against a $260 real liability, and never bound. Three config-gated
        # variants, ALL inert by default so `main.py` behaviour is unchanged until one is chosen:
        #   feed_reserve_counts_in_flight (arm C1): add the in-flight herd to the reserved count.
        #   feed_reserve_horizon="target" (arm C2): reserve for the full intended herd
        #     (sum of animal_purchases targets) — the variant that keeps binding when the target
        #     grows past what has been bought yet (e.g. the §4.0 herd-13 profile).
        #   feed_reserve_days (arm X): the discriminating control — raise the horizon alone,
        #     leaving the undercount in place, to tell "reserve too small" from "liability
        #     undercounted". 2 is the shipped value.
        "feed_reserve_days": 2,
        # arm C1: count in-flight animals in the reserved liability (6f208cd located defect)
        "feed_reserve_counts_in_flight": True,
        "feed_reserve_horizon": "in_flight",  # "in_flight" | "target"
        # v1i — the two remaining sell-ahead levers, each independently
        # switchable so the KILL clause ("try the other one alone before dropping both")
        # costs a config edit, not a patch.
        "sell_ahead": {
            # Η1: judge a SELL batch by the average it will realize (Σ p(s+i) / n) instead of
            # by its marginal unit, with `liquidation_floor_price` as an un-overridable
            # per-unit veto. Identical to the pre-v1i rule whenever floor <= that veto, i.e.
            # for CARROT/EGG always and for every product during liquidation.
            "average_rule": True,
            # Η2: replace the `opponent_price_safety_units` constant in the main sell loop
            # with the c68 controller's one-turn-ahead estimate of the opponent's supply
            # (agent/sell_ahead.py). Off => the constant, which is also what every product
            # with no observed history gets.
            "predict_safety_units": True,
            "predict_horizon_turns": 6,
            # Clamp on the controller's output. The low end is 1, not 0: even a silent
            # opponent can open a SELL on the turn we do, and one unit of headroom is the
            # cheapest insurance against quoting at exactly the pre-commit index.
            "min_safety_units": 1,
            "max_safety_units": 8,
        },
    },
    "land": {
        # v1c / MASTERPLAN §3.2#7: buy NE as soon as money allows AND a workforce
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
        # never showed up against a passive opponent. The top-decile data targets
        # 2nd-quadrant unlock around day ~9, not day 0 — this reserve requirement (rather than
        # a hardcoded day) makes the trigger self-regulating: land waits until the shed has
        # genuine surplus cash beyond survival needs, however many days that actually takes.
        "min_reserve": 1000,
    },
    "animals": {
        # v1d shipped COW (85% top-team adoption, median day 0) and SHEEP (56%,
        # median day 5). GOOSE (15% adoption) added in v1e, now that COOP has a home (see
        # scheduler.animal_structure_tiles).
        #
        # v1g: targets is now name -> count (was one slot per unique name) — see
        # agent/animal_slots.py. Dict order still fixes which tiles within a shared structure
        # kind (COW/SHEEP both PASTURE) each name claims first. The elite
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
        # ROADMAP §4.3 S3 step 2 (v1s): optional day-gated herd ramp. None = shipped behaviour
        # (buy toward the full `targets` from day 0, a step purchase). A list of [day, cap] rungs
        # sorted ascending caps the total herd per day, spending the cap across names in `targets`
        # dict order; past the last rung the herd is uncapped. §4.0's profile is [[5, 6], [10, 12]]
        # (6 by d5, 12 by d10, 13 thereafter). See planner._herd_ramp_cap.
        "ramp": None,
    },
    "endgame": {
        "enabled": True,
        "liquidation_day": 26,
    },
    "guards": {
        # The agent runs in a separate, freshly-imported process from
        # whatever invoked it (harness CLI, a ProcessPoolExecutor worker), so this must be
        # steered by an env var read once at import, never by mutating CONFIG after the fact.
        "debug": os.environ.get("KAGGRI_DEBUG", "0") == "1",
    },
    "runtime": {
        "turns_per_day": 24,
        "episode_steps": 720,
    },
}
