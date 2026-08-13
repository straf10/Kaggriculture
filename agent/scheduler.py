"""Layer 2 deterministic task scheduler."""
from dataclasses import dataclass, field

from .animal_slots import animal_slot_ranges
from .config import CONFIG
from .constants import ANIMALS, CROPS, SHED_ACCESS
from .planner import DayPlan
from .state import Snapshot, animals_needing

# review.md L8: was a bare hardcoded 719; derive it from the same config every call site
# already uses, so a runtime.episode_steps change can't silently leave this stale. Every
# production call site sets deadline_step explicitly — this only backs ad-hoc/test Tasks.
_DEFAULT_DEADLINE_STEP = CONFIG["runtime"]["episode_steps"] - 1


def _harvest_ready_age(crop: str) -> int:
    """review.md M12: age (days since planted) at which `crop` first reaches its peak
    yield_units, derived from CROPS instead of a hardcoded magic number. Ongoing crops
    (STRAWBERRY) keep accumulating yield via the engine's daily refresh at
    first_yield_day + interval*k; the last production tick (k = max_yield-1) is the day
    yield peaks (engine kaggriculture.py _daily_refresh_plants, ~L764-780). Non-ongoing
    crops (CARROT) only gain yield_units through the WATER op inside
    [(max_yield_day+1)//2, max_yield_day] (engine _apply_op WATER, ~L381-387), so they
    peak at max_yield_day itself."""
    data = CROPS[crop]
    if data["ongoing"]:
        return data["first_yield_day"] + data["interval"] * (data["max_yield"] - 1)
    return data["max_yield_day"]


def _water_window(crop: str) -> tuple[int, int]:
    """review.md M12: [start, end] age range in which watering a non-ongoing crop still
    grows yield_units, mirroring the engine's own `window_start = (max_yield_day+1)//2`
    (engine kaggriculture.py L384)."""
    max_yield_day = CROPS[crop]["max_yield_day"]
    return (max_yield_day + 1) // 2, max_yield_day


# v1h': WHEAT joins as SW's crop (config.scheduler.target_tiles["WHEAT"]). Order matters —
# it is the order build_tasks spends the shared daily planting budget in, so WHEAT (which has
# no planting deadline) comes after STRAWBERRY (which does).
_GROWN_CROPS = ("CARROT", "STRAWBERRY", "WHEAT")
_HARVEST_READY_AGE = {crop: _harvest_ready_age(crop) for crop in _GROWN_CROPS}
# v1h': non-ongoing crops only gain yield_units from a WATER inside their own engine window,
# so watering them purely on the every-other-day survival rule (consecutive_unwatered >= 1)
# would land outside it and grow almost nothing. This was CARROT-only until WHEAT arrived;
# derived per crop from CROPS, so CARROT's behaviour is byte-identical to before.
_WATER_WINDOWS = {crop: _water_window(crop) for crop in _GROWN_CROPS if not CROPS[crop]["ongoing"]}


@dataclass(frozen=True)
class Task:
    id: str
    kind: str
    pos: tuple[int, int]
    priority: int
    item: str | None = None
    count: int = 1
    deadline_step: int = _DEFAULT_DEADLINE_STEP
    prerequisites: tuple[str, ...] = ()
    required_inventory: dict[str, int] = field(default_factory=dict)
    reservation_key: str | None = None
    allowed_unit: int | None = None


@dataclass
class ResourceLedger:
    seeds: dict[str, int]
    money: float


def build_tasks(snapshot: Snapshot, plan: DayPlan, config: dict) -> list[Task]:
    """Build deadline-aware v1a carrot tasks."""
    if not config["scheduler"].get("enabled", False):
        return []

    tasks = []
    crop_harvest_at_risk_priority = config["scheduler"].get("crop_harvest_at_risk_priority")
    turns_per_day = config["runtime"]["turns_per_day"]
    day_deadline = (snapshot.day + 1) * turns_per_day - 1
    target_tiles_by_crop = config["scheduler"]["target_tiles"]
    target_specs = [
        (crop, target_index, pos)
        for crop in _GROWN_CROPS
        for target_index, pos in enumerate(target_tiles_by_crop.get(crop, ()))
    ]
    unit_positions = (snapshot.farmer_pos, *snapshot.hand_positions)
    turns_left_today = turns_per_day - snapshot.hour
    planted_today = sum(
        1
        for _crop, _target_index, (x, y) in target_specs
        if (
            isinstance(snapshot.my_tiles[y][x], dict)
            and snapshot.my_tiles[y][x].get("kind") == "PLANT"
            and snapshot.my_tiles[y][x].get("planted_day") == snapshot.day
        )
    )
    # plan.md §5 v1c: read from plan (not config directly) — planner.py grows this alongside
    # plant_targets once NE is unlocked, so CARROT's newly-doubled tile count can't starve
    # STRAWBERRY of its share of a budget that never grew to match.
    max_new_plants = int(plan.max_new_plants)
    # review_89d99f0_2026-08-05.md H1/M6: cap PLANT task *creation* to what today's plant budget and the
    # currently-observed seed count can actually support, so assign() can never commit more
    # PLANT actions in one turn than the cap allows, and never sends a unit walking toward a
    # PLANT tile whose only seed was already claimed by an earlier task in this same build.
    plant_budget_remaining = max(0, max_new_plants - planted_today)
    seeds_budget = dict(snapshot.seeds)

    for crop, target_index, (x, y) in target_specs:
        plant_limit = plan.plant_targets.get(crop, 0)
        tile = snapshot.my_tiles[y][x]
        if isinstance(tile, dict) and tile.get("kind") == "PLANT":
            if tile.get("crop") != crop:
                continue
            age = snapshot.day - tile["planted_day"]
            # review_89d99f0_2026-08-05.md L7: v1b watered CARROT on `age >= 2` unconditionally, including past
            # the engine's yield window (ages 2-3) — a rare, small unit-turn waste, not
            # present in plan.md's ablation table but needed for the all-off self-test to
            # reproduce v1b exactly (criterion #1).
            water_window = _WATER_WINDOWS.get(crop)
            in_yield_window = water_window is not None and water_window[0] <= age <= water_window[1]
            needs_water = (
                not tile.get("watered_today")
                and (tile.get("consecutive_unwatered", 0) >= 1 or in_yield_window)
            )
            if needs_water:
                tasks.append(Task(
                    id=f"water:{x}:{y}",
                    kind="WATER",
                    pos=(x, y),
                    priority=0,
                    deadline_step=day_deadline,
                ))
            harvest_ready_age = _HARVEST_READY_AGE[crop]
            harvest_due = age >= harvest_ready_age
            if harvest_due and tile.get("yield_units", 0) > 0:
                harvest_priority = (
                    0
                    if crop == "STRAWBERRY" or tile.get("watered_today") or age > harvest_ready_age
                    else 1
                )
                # v1o.3: crop HARVEST is the one priority-0 task with a hard *yield* deadline —
                # engine _decay_plants (:738-752) takes one yield_unit every second step from
                # max_lifespan_step onward, so a strawberry at its 4-unit cap is stripped bare in
                # eight steps. FEED's at-risk tier (-1) therefore outranks it, and the v1o.3
                # screen measured exactly that: promoting FEED/PICKUP above WATER broke
                # `plant_decay_units_lost` (4 in variant C, 14 in D) — a structural counter, hard
                # zero under ROADMAP §2.1.5 — while fixing the animals. Give a tile that is
                # actually losing yield today the same at-risk standing, so the two hard
                # deadlines compete with each other on urgency and distance instead of one
                # silently always winning. None (the default) is a strict no-op.
                lifespan_step = tile.get("max_lifespan_step", -1)
                decaying_today = isinstance(lifespan_step, int) and 0 <= lifespan_step <= day_deadline
                if crop_harvest_at_risk_priority is not None and decaying_today:
                    harvest_priority = min(harvest_priority, int(crop_harvest_at_risk_priority))
                tasks.append(Task(
                    id=f"harvest:{x}:{y}",
                    kind="HARVEST",
                    pos=(x, y),
                    priority=harvest_priority,
                    deadline_step=min(day_deadline, tile.get("max_lifespan_step", day_deadline)),
                ))
            continue

        # review_89d99f0_2026-08-05.md H5: feasibility used to be judged from the farmer's position only, even
        # though assign() may hand the task to a hand standing somewhere else entirely. Use
        # the closest unit's distance instead, so a hand near a far tile isn't blocked by
        # (and a hand far from a near tile doesn't wrongly greenlight) a farmer-only estimate.
        min_distance = min(abs(ux - x) + abs(uy - y) for ux, uy in unit_positions)
        if isinstance(tile, dict) and tile.get("kind") == "WEED":
            if target_index < plant_limit and min_distance + 3 <= turns_left_today:
                tasks.append(Task(
                    id=f"dig:{x}:{y}",
                    kind="DIG",
                    pos=(x, y),
                    priority=2,
                    deadline_step=day_deadline - 2,
                ))
            continue

        plant_cap_ok = plant_budget_remaining > 0 and seeds_budget.get(crop, 0) > 0
        if (
            target_index < plant_limit
            and tile is None
            and plant_cap_ok
            and min_distance + 2 <= turns_left_today
        ):
            tasks.append(Task(
                id=f"plant:{crop}:{x}:{y}",
                kind="PLANT",
                pos=(x, y),
                priority=2 if crop == "STRAWBERRY" and snapshot.day <= 5 else 3,
                item=crop,
                deadline_step=day_deadline - 1,
                required_inventory={f"{crop}_SEED": 1},
                reservation_key=f"seed:{crop}",
            ))
            plant_budget_remaining -= 1
            seeds_budget[crop] -= 1

    if plan.force_liquidation:
        # review_89d99f0_2026-08-05.md M1: one DROP task per loaded unit, restricted to that unit, instead of a
        # single global task an empty-inventory unit can monopolize with silent no-ops.
        access = (4, 4)  # the only initially unlocked shed-access tile
        # plan.md §5 v1e: WHEAT excluded from "cargo to dump" — it's productive input a unit
        # just PICKUP'd to carry to a FEED task, not sellable crop yield. Counting it here (as
        # v1d did) meant a unit carrying WHEAT toward an animal got handed a same-position DROP
        # task before it could walk away, dumping the wheat straight back into the shed; next
        # turn it PICKUP'd again, repeating forever. Found via a v1e smoke test once GOOSE's
        # extra daily upkeep pushed the farmer into the WHEAT-fetch role during liquidation
        # (day >= endgame.liquidation_day) — COW and SHEEP starved to consecutive_unfed>=2 and
        # escaped while the farmer oscillated PICKUP/DROP at the shed, never reaching them.
        def _liquidatable(inventory: dict) -> int:
            return sum(v for k, v in inventory.items() if k != "WHEAT")

        for unit_index, unit_pos in enumerate(unit_positions):
            del unit_pos
            inventory = snapshot.inventories[unit_index] if unit_index < len(snapshot.inventories) else {}
            if _liquidatable(inventory) > 0:
                tasks.append(Task(
                    id=f"drop:liquidation:{unit_index}",
                    kind="DROP",
                    pos=access,
                    priority=0,
                    deadline_step=config["runtime"]["episode_steps"] - 2,
                    allowed_unit=unit_index,
                ))

    tasks.extend(_build_animal_tasks(snapshot, plan, config, unit_positions, day_deadline))

    # review_89d99f0_2026-08-05.md L8: truncation used to follow construction order (CARROT tiles first), not
    # priority — a footgun if the task pool ever actually reaches max_tasks (currently
    # unreachable at 400, but not something the code should rely on staying true).
    tasks.sort(key=lambda task: task.priority)
    return tasks[:config["scheduler"]["max_tasks"]]


def placed_count(snapshot: Snapshot, name: str) -> int:
    """How many `name` animals are currently placed anywhere on the farm."""
    return sum(
        1 for row in snapshot.my_tiles for tile in row
        if isinstance(tile, dict) and tile.get("animal") == name
    )


def animal_placed(snapshot: Snapshot, name: str) -> bool:
    """True once at least one `name` animal is placed — used where "some investment in this
    animal type already exists" is the question (e.g. the BUY_LAND gate), not "the full herd
    is placed" (v1g: a name can now have more than one reserved slot; see placed_count for an
    exact count and open_animal_slots for which slots still need filling)."""
    return placed_count(snapshot, name) > 0


def open_animal_slots(snapshot: Snapshot, config: dict, name: str) -> list[tuple[int, int]]:
    """Every reserved structure tile for `name` that's built, empty, and waiting — the homes
    a just-bought/carried animal of this name can still be routed to, in tile order. v1g:
    generalizes the old single-slot animal_structure_ready to N slots per name."""
    structure_kind = ANIMALS[name]["structure"]
    tiles = animal_slot_ranges(config).get(name, ())
    open_slots = []
    for x, y in tiles:
        tile = snapshot.my_tiles[y][x]
        if isinstance(tile, dict) and tile.get("kind") == structure_kind and "animal" not in tile:
            open_slots.append((x, y))
    return open_slots


def _build_animal_tasks(
    snapshot: Snapshot, plan: DayPlan, config: dict,
    unit_positions: tuple, day_deadline: int,
) -> list["Task"]:
    """plan.md §5.1 v1d: structures (BUILD_PASTURE) → BUY_ANIMAL (executor, lands in shed) →
    PICKUP → PLACE, then the daily FEED/CARE/COLLECT_FERTILIZER/HARVEST loop for whatever's
    already placed. Gated entirely by config["animals"]["enabled"] — no ablation flag, unlike
    §1.5.2's closed regression-debug flags, since this is new feature surface, not a
    reproduction of a past behavior."""
    if not config.get("animals", {}).get("enabled", False):
        return []
    tasks = []
    scheduler_config = config["scheduler"]
    # v1o.3: the priority ladder for animal upkeep is config, not literals, so a variant is one
    # edit and every arm is reversible. Defaults reproduce the pre-v1o.3 numbers exactly.
    animal_priority = scheduler_config.get("animal_task_priority", {})
    feed_priority = int(scheduler_config.get("feed_priority", 0))
    feed_at_risk_priority = int(scheduler_config.get("feed_at_risk_priority", -1))
    bundle_enabled = bool(scheduler_config.get("bundle_animal_visits", False))
    bundle_priority = int(scheduler_config.get("bundle_priority", 0))
    bundle_yields_to_feed_round = bool(
        scheduler_config.get("bundle_yields_to_feed_round", True)
    )
    spawn = SHED_ACCESS[0]
    structure_tiles = config["scheduler"].get("animal_structure_tiles", {})
    # Structures/animal-onboarding are one-time, episode-scoped setup, not a daily-reset
    # obligation like WATER/FEED — using day_deadline here would make the slack/urgency-tier
    # machinery (tuned for genuine same-day deadlines) treat "not yet built by hour 23" as an
    # emergency and yank a unit off real daily work near every day's end for no real reason
    # (there's no engine penalty for a pasture built on day 1 instead of day 0).
    episode_deadline = config["runtime"]["episode_steps"] - 1

    # 1. Structures: build each reserved slot (clearing a weed first if one spawned there)
    # up to plan.structures_to_build, independent of whether an animal is ready to fill it —
    # BUILD_* is free, so there's no reason to wait for the purchase.
    for structure_kind, tiles in structure_tiles.items():
        target = plan.structures_to_build.get(structure_kind, 0)
        for slot_index, (x, y) in enumerate(tiles):
            if slot_index >= target:
                break
            tile = snapshot.my_tiles[y][x]
            if isinstance(tile, dict) and tile.get("kind") == "WEED":
                tasks.append(Task(
                    id=f"dig_structure:{x}:{y}", kind="DIG", pos=(x, y),
                    priority=1, deadline_step=episode_deadline,
                ))
            elif tile is None:
                tasks.append(Task(
                    id=f"build:{structure_kind}:{x}:{y}", kind=f"BUILD_{structure_kind}",
                    pos=(x, y), priority=2, deadline_step=episode_deadline,
                ))

    # 2. Pickup/place: v1g generalizes this from "one animal per target" to N per name — a
    # PLACE task per still-open slot (harmless if nothing is actually carried yet: assign()'s
    # _carries_cargo filters ineligible units out, it doesn't mis-route them) lets multiple
    # units place different same-named animals into different slots in the same turn, instead
    # of serializing one slot per turn. One aggregated PICKUP per name (not per slot) mirrors
    # the WHEAT bulk-pickup pattern below — a single unit can carry several of the same animal
    # at once and walk between their slots placing one per turn.
    for name, target in plan.animal_purchases.items():
        have_placed = placed_count(snapshot, name)
        if have_placed >= target:
            continue
        open_slots = open_animal_slots(snapshot, config, name)
        if not open_slots:
            continue
        for target_pos in open_slots:
            tasks.append(Task(
                id=f"place:{name}:{target_pos[0]}:{target_pos[1]}", kind="PLACE", pos=target_pos,
                priority=1, item=name, deadline_step=episode_deadline,
            ))
        carried = sum(inv.get(name, 0) for inv in snapshot.inventories)
        shed_have = int(snapshot.shed.get(name, 0))
        remaining_need = max(0, target - have_placed - carried)
        pickup_amount = min(remaining_need, shed_have)
        if pickup_amount > 0:
            tasks.append(Task(
                id=f"pickup:{name}", kind="PICKUP", pos=spawn,
                priority=1, item=name, count=pickup_amount, deadline_step=episode_deadline,
            ))

    # 3. Daily upkeep for whatever's already placed. FEED carries review_89d99f0_2026-08-05.md C1's exact
    # zero-slack death mechanism (`consecutive_unfed >= 2`, engine :795) that WATER has, but
    # worse (escape = $300-500 lost capital, not a replantable tile) — fed every single day,
    # unconditionally, no every-other-day economy like carrot watering. Wheat must already be
    # in a unit's own inventory before FEED can be assigned to it (G5: reserved before use,
    # enforced in assign()'s eligibility filter, not here).
    animal_needs = animals_needing(snapshot)
    unfed_positions = [pos for pos, needed in animal_needs.items() if "FEED" in needed]
    if unfed_positions:
        at_risk_positions = {
            (x, y)
            for x, y in unfed_positions
            if (
                isinstance(snapshot.my_tiles[y][x], dict)
                and snapshot.my_tiles[y][x].get("consecutive_unfed", 0) >= 1
            )
        }
        carried_wheat = sum(inv.get("WHEAT", 0) for inv in snapshot.inventories)
        wheat_needed = len(unfed_positions) - carried_wheat
        wheat_available = int(snapshot.shed.get("WHEAT", 0))
        if wheat_needed > 0 and wheat_available > 0:
            # v1g: a single aggregated PICKUP task hands the WHOLE day's wheat to one unit,
            # which must then serially walk to every unfed tile itself. That was fine when
            # there were 2-3 animals in one corner; at 13 PASTURE slots spanning the whole
            # NW quadrant (up to distance 8 apart) one carrier cannot complete the round
            # inside a day's 24 turns, so animals hit consecutive_unfed>=2 and escape — a
            # dev-screen run confirmed thousands of escapes/rebuy-death cycles at full mass.
            # Split the fetch into one allowed_unit-restricted task per unit (mirroring the
            # liquidation DROP pattern above) so several units can each carry a share and
            # feed a different cluster in parallel; allowed_unit exempts these from assign()'s
            # same-position mutual-exclusion dedup, which would otherwise collapse them all
            # back into a single winner.
            #
            # An earlier version of this fix divided the pickup count evenly across
            # range(num_units) by index (`base + 1 if unit_index < extra else 0`) — but as
            # unfed_positions shrinks over the day (animals get fed one by one), `extra`
            # shrinks with it, so higher-index hands get `count=0` on most hours and the loop
            # skips creating a task for them entirely (`if count <= 0: continue`). A hand that
            # is never even OFFERED a pickup task defaults to whatever lower-priority chore is
            # under its feet (CARE/HARVEST, priority 1) instead of fetching wheat — a replay
            # trace found exactly this: a hand standing directly on an unfed SHEEP tile with
            # 0 WHEAT, doing CARE there every hour, all day, because it was never given the
            # chance to go fetch feed. Offering every unit the FULL remaining need (capped by
            # shed stock, not divided) fixes this: PICKUP sits at priority 0, the same tier as
            # FEED/WATER and above CARE/HARVEST(1), so whichever unit has nothing better at
            # that tier will now actually go fetch it. The engine clamps PICKUP to available
            # stock per unit (kaggriculture.py's PICKUP op), so multiple units "requesting"
            # more than what's left is a harmless no-op once the shed empties, not a bug.
            pickup_count = min(wheat_needed, wheat_available)
            # v1h.2d: PICKUP is FEED's mandatory predecessor. Its old day_deadline ignored
            # the post-pickup trip from the shed to the farthest unfed animal, so it could
            # remain "comfortable" until there was no delivery slack left. Reserve that
            # mechanical trip now; if any animal is already one miss from escape, promote
            # the predecessor with the same priority as its at-risk FEED task.
            delivery_distance = max(
                abs(spawn[0] - x) + abs(spawn[1] - y)
                for x, y in unfed_positions
            )
            pickup_deadline = day_deadline - delivery_distance - 1
            for unit_index in range(len(unit_positions)):
                tasks.append(Task(
                    id=f"pickup:WHEAT:{unit_index}", kind="PICKUP", pos=spawn,
                    # v1o.3: PICKUP moves with FEED, always. `_carries_cargo` makes a FEED task
                    # eligible only for a unit that already holds WHEAT, so promoting FEED alone
                    # does nothing on the turns where nobody has any — the two are one knob.
                    priority=feed_at_risk_priority if at_risk_positions else feed_priority,
                    item="WHEAT", count=pickup_count,
                    deadline_step=pickup_deadline, allowed_unit=unit_index,
                ))
        for (x, y) in unfed_positions:
            # v1g: FEED tasks all shared day_deadline regardless of history, so assign()'s
            # slack-based urgency tier (C1/§1.2) never kicked in until the day's final hours —
            # until then, ties between same-priority FEED tasks fall back to raw tile position
            # (task.pos[1] then task.pos[0]), which a replay trace showed systematically
            # favoring one far tile over another every time capacity was tight, starving the
            # loser on a reproducible ~3-day cycle regardless of seed. An animal with
            # consecutive_unfed >= 1 is one more miss from actually escaping (engine
            # kaggriculture.py:795) — that is categorically more urgent than a tile that
            # hasn't missed a day yet, so pull its deadline in well before day's end to force
            # it into the urgent tier and win ties on real risk instead of position.
            tile = snapshot.my_tiles[y][x]
            at_risk = isinstance(tile, dict) and tile.get("consecutive_unfed", 0) >= 1
            feed_deadline = (
                snapshot.step + config["scheduler"]["urgency_slack_margin"] + 1
                if at_risk else day_deadline
            )
            tasks.append(Task(
                id=f"feed:{x}:{y}", kind="FEED", pos=(x, y),
                # v1h': an animal that has already missed a day outranks *everything*, not just
                # everything at its own priority. v1g pulled its deadline in, which wins ties
                # inside priority 0 — but FEED shares priority 0 with WATER, and once SW's
                # WHEAT and NE's 24 STRAWBERRY tiles are both live there are more urgent-looking
                # WATER tasks in a day than units to serve them, so the pulled-in deadline was
                # competing rather than deciding. Measured: 2 animals per episode in all four
                # smoke seeds, always the farthest PASTURE tiles, always on consecutive misses
                # around days 25-27, with 30+ WHEAT sitting in the shed — never a supply
                # problem, always a contention one. The asymmetry justifies the jump: a missed
                # WATER costs a replantable tile, a second missed FEED costs $400-500 of placed
                # capital and its remaining production. Only the at-risk tier is promoted; a
                # normally-fed animal stays at 0 and keeps competing on the merits.
                priority=feed_at_risk_priority if at_risk else feed_priority,
                deadline_step=min(day_deadline, feed_deadline),
            ))

    # v1o.3: which unit (if any) may bundle the rest of a tile's visit. `unfed_positions` is the
    # day's still-open feed round; see the note in the loop for why it is a veto and not a
    # tiebreak. `allowed_unit` is what makes a bundled task safe on top of that — assign() dedups
    # allowed_unit tasks by id instead of by position, so a bundled CARE can never take the same
    # tile's FEED (or anything else there) out of the turn's pool the way an unrestricted one does.
    feed_round_open = bool(unfed_positions)
    bundle_unit_by_position: dict[tuple[int, int], int] = {}
    if bundle_enabled and not (feed_round_open and bundle_yields_to_feed_round):
        for unit_index, unit_pos in enumerate(unit_positions):
            bundle_unit_by_position.setdefault(unit_pos, unit_index)

    for (x, y), needed in animal_needs.items():
        # v1o.3 (ROADMAP §4.3 S3 step 1b) — **animal-visit bundling**. An animal tile needs up to
        # four ops a day (FEED/CARE/HARVEST/COLLECT_FERTILIZER), but assign() drops *every*
        # unrestricted task at an assigned position once one of them is taken, and its `committed`
        # stickiness is only set when a unit MOVES — so a unit standing on an animal tile performs
        # exactly one op, then re-competes from scratch next turn and is pulled away by the nearest
        # priority-0 WATER. With ~60 planted tiles the tier-0 pool no longer empties inside a day
        # (`sw_hands_target=12` STOP, ROADMAP §3.3), so tier-1 CARE/HARVEST and tier-3
        # COLLECT_FERTILIZER starve deterministically: analysis/v1o1_product_split.py measured WOOL
        # losing 41% of its units and FERTILIZER 27% purely from added WATER work.
        #
        # Promoting those tasks globally would be **zero-sum** — every unit-turn they win above
        # WATER is one WATER loses, trading $300 weed tiles for $1.000 escapes and nothing else.
        # Promoting them only where a unit is ALREADY STANDING is not: the marginal cost of the
        # next op is 1 turn instead of `2*distance + 1`, so the bundle can never induce a commute,
        # only finish one. At distance 2-6 from the shed that is ~80 unit-turns/day for ten animals
        # instead of ~160.
        #
        # ⚠️ WHY THE BUNDLE IS NOT ENOUGH ON ITS OWN, MEASURED. The first screen (variant A) put
        # the bundle at tier 0 on top of the unchanged ladder. It was demonstrably taken —
        # `worker_turns_moving` 62,0% -> 57,5%, COLLECT_FERTILIZER ops 123 -> 193/ep, FERTILIZER
        # units 123 -> 191/ep, bank +$8.806 against the non-mirror bench — and it still made the
        # animal side *worse*: `animals_escaped` 15 vs 6, `animals_underfed_days` 51,6 vs 36,1.
        #
        # The reason is not this tile. Both halves of the feed round — the aggregated
        # `PICKUP WHEAT` and every `FEED` — sat at priority 0 with a distance of at least 1, while
        # a bundled task at the unit's own feet has distance 0 and the same priority. So a unit
        # standing on ANY already-fed animal tile out-competed the whole round, for as many turns
        # as that tile had work left. The fix that ships is therefore not to weaken the bundle but
        # to give the feed round a tier of its own (config `feed_priority` -1) so the bundle has
        # something to sit under — with the crop-HARVEST decay guard in build_tasks closing the
        # hole that opens up when -1 also starts outranking the only other hard yield deadline.
        #
        # The obvious alternative — suppress the bundle while any animal is unfed
        # (`bundle_yields_to_feed_round`) — was measured and does *nothing*: the feed round is open
        # 100% of the hours of a median day from day 9 onward, so the bundle simply never fires.
        bundle_unit = None if "FEED" in needed else bundle_unit_by_position.get((x, y))
        bundled = bundle_unit is not None

        for kind, default_priority, task_id in (
            ("CARE", 1, f"care:{x}:{y}"),
            ("HARVEST", 1, f"harvest_animal:{x}:{y}"),
            ("COLLECT_FERTILIZER", 3, f"fertilizer:{x}:{y}"),
        ):
            if kind not in needed:
                continue
            priority = int(animal_priority.get(kind, default_priority))
            if bundled:
                # min(), not assignment: a bundle may only ever promote a task, never demote one.
                priority = min(priority, bundle_priority)
            tasks.append(Task(
                id=task_id, kind=kind, pos=(x, y),
                priority=priority, deadline_step=day_deadline,
                allowed_unit=bundle_unit,
            ))
    return tasks


# v1p.2 (ROADMAP §4.3 S3 step 1c, zone assignment). Quadrant boundaries mirror the engine's own
# `_quadrant_of` (engine_reference/kaggriculture.py:114-116) at boardSize=10 — the same hardcoded
# geometry every other constant in this module already assumes (SHED_ACCESS, target_tiles, ...).
_QUADRANT_ORDER = ("NW", "NE", "SW", "SE")
# SHED_ACCESS is documented as "four inner-corner tiles around the shed, in NWSE order"
# (engine_reference/kaggriculture.py:119-122) — reused directly as each quadrant's near-shed
# anchor point instead of inventing separate constants that could drift out of sync with it.
_QUADRANT_ANCHOR = dict(zip(_QUADRANT_ORDER, SHED_ACCESS))


def _tile_quadrant(pos: tuple[int, int]) -> str:
    x, y = pos
    return ("N" if y < 5 else "S") + ("W" if x < 5 else "E")


def _zone_partition(
    tasks: list[Task],
    snapshot: Snapshot,
    config: dict,
    committed: dict[int, str] | None = None,
) -> dict[int, str]:
    """Which quadrant each unit is zoned to this turn, or `{}` if zoning has no effect.

    ROADMAP §4.3 S3 step 1c: `assign()`'s global argmin can pull a unit standing in one
    quadrant to a task in another, a commute of up to ~12 turns to perform one 1-turn action.
    This computes a proportional split of units across the quadrants we currently own, sized by
    that turn's actual task count per quadrant (not a fixed ratio, which would re-break the
    moment a tile-count knob moves) — a pure function of `tasks`/`snapshot`/`config`/`committed`
    alone, so two processes with different PYTHONHASHSEED produce identical zones (G13). The
    caller (`assign()`) turns this into a *filter on eligible_units*, never on tasks themselves,
    with an explicit fallback to the full unit pool when a task's own zone has nobody in it — a
    task must never become unservable just because its zone is momentarily empty.

    v1p.2b (ROADMAP §4.3 S3 step 1c): v1p.2's own SMOKE STOP diagnosed why the plain version of
    this function above was never safe to ship — it recomputed zones fresh every turn from the
    *current* snapshot alone, so a unit already `committed` to a task (the C1 stickiness fix
    `assign()`'s own docstring describes at length) could be re-zoned OUT of eligibility for that
    exact task the moment the day's task-count mix shifted by one — silently discarding a walk
    already paid for, reproducing the class of oscillation `committed` exists to prevent, one
    layer up from where `committed` can see it. **Pin first**: a unit whose `committed` task still
    exists in `tasks` keeps the zone that task lives in, unconditionally, before any quota is
    computed — a pinned unit is never displaced by quota exhaustion, because quotas are a soft
    target for the *remaining*, uncommitted units only. This is what lets `committed`'s stickiness
    survive zoning instead of being bypassed by a hard eligibility exclusion.

    Only tasks assign() will actually apply the filter to are counted toward a quadrant's
    workload: `allowed_unit` tasks (PICKUP WHEAT, liquidation DROP — one per unit by
    construction) already go to one named unit regardless of zone, so counting them would scale
    a quadrant's quota with total unit count instead of real contested workload.
    """
    if not config["scheduler"].get("zone_assignment_enabled", False):
        return {}
    owned = tuple(q for q in _QUADRANT_ORDER if q in snapshot.my_quadrants)
    if len(owned) <= 1:
        return {}

    committed = committed or {}
    unit_positions = (snapshot.farmer_pos, *snapshot.hand_positions)
    num_units = len(unit_positions)
    if num_units == 0:
        return {}

    # Pin first (v1p.2b): a unit with a live commitment whose task still exists this turn keeps
    # the zone that task lives in, unconditionally — this is the guard that would have caught
    # v1p.2's STOP. Iterate `committed` in sorted unit-index order, never dict order (G13).
    tasks_by_id = {task.id: task for task in tasks}
    zones: dict[int, str] = {}
    pinned_units: set[int] = set()
    for unit_index in sorted(committed):
        if unit_index >= num_units:
            continue
        committed_task = tasks_by_id.get(committed[unit_index])
        if committed_task is None:
            continue
        zones[unit_index] = _tile_quadrant(committed_task.pos)
        pinned_units.add(unit_index)

    counts: dict[str, int] = {q: 0 for q in owned}
    for task in tasks:
        if task.allowed_unit is not None:
            continue
        quadrant = _tile_quadrant(task.pos)
        if quadrant in counts:
            counts[quadrant] += 1
    total = sum(counts.values())

    remaining_units = [unit_index for unit_index in range(num_units) if unit_index not in pinned_units]
    if total == 0 or not remaining_units:
        return zones

    # Largest-remainder apportionment (Hamilton's method), over the remaining (unpinned) units
    # only — quotas are a soft target for units without a live commitment. Floor each quadrant's
    # exact share, then hand the leftover units to the quadrants with the largest fractional
    # remainder, ties broken by _QUADRANT_ORDER position — deterministic regardless of dict
    # iteration.
    num_remaining = len(remaining_units)
    exact = {q: num_remaining * counts[q] / total for q in owned}
    quota = {q: int(exact[q]) for q in owned}
    leftover = num_remaining - sum(quota.values())
    by_remainder = sorted(owned, key=lambda q: (-(exact[q] - quota[q]), _QUADRANT_ORDER.index(q)))
    for q in by_remainder[:leftover]:
        quota[q] += 1

    # Assign each remaining unit (in fixed unit_index order) to its nearest quadrant that still
    # has quota left, so a unit already working near a quadrant tends to stay zoned there instead
    # of thrashing turn to turn. Ties (equal distance, equal quota availability) break on
    # _QUADRANT_ORDER, never on set iteration.
    remaining_quota = dict(quota)
    for unit_index in remaining_units:
        pos = unit_positions[unit_index]
        ranked = sorted(
            owned,
            key=lambda q: (
                0 if remaining_quota.get(q, 0) > 0 else 1,
                abs(pos[0] - _QUADRANT_ANCHOR[q][0]) + abs(pos[1] - _QUADRANT_ANCHOR[q][1]),
                _QUADRANT_ORDER.index(q),
            ),
        )
        zone = ranked[0]
        remaining_quota[zone] = remaining_quota.get(zone, 0) - 1
        zones[unit_index] = zone
    return zones


def make_ledger(snapshot: Snapshot) -> ResourceLedger:
    return ResourceLedger(
        seeds=dict(snapshot.seeds),
        money=snapshot.money,
    )


def _move_toward(start: tuple[int, int], destination: tuple[int, int]) -> list[str]:
    start_x, start_y = start
    destination_x, destination_y = destination
    if start_x < destination_x:
        return ["EAST"]
    if start_x > destination_x:
        return ["WEST"]
    if start_y < destination_y:
        return ["SOUTH"]
    if start_y > destination_y:
        return ["NORTH"]
    return ["PASS"]


def assign(
    tasks: list[Task],
    snapshot: Snapshot,
    committed: dict[int, str] | None = None,
    config: dict = CONFIG,
) -> tuple[list[str], list[list[str]], dict[int, str]]:
    """Greedily assign unique tasks to farmer and hands with seed reservations.

    review_89d99f0_2026-08-05.md C1/§1.2: each task's `slack` (deadline_step - step - the nearest currently
    -unassigned unit's travel-and-act turns) leads the sort key ahead of raw distance. A
    task's own urgency is now judged by its *best available* unit, not by whichever unit
    happens to be asking — so a distant task that is about to run out of time is picked for
    service before a near task that still has time to spare. Distance only breaks ties
    between equally-urgent tasks, at which point it correctly prefers the nearest unit for
    the winning task. Plain nearest-pair-first (no slack) let far-but-urgent tiles starve
    behind a steady stream of near-but-unhurried ones.

    `committed` (unit_index -> task.id from the *previous* turn's returned commitments) is
    C1's task-stickiness resolution (§2 C1 step 4), and it is not optional polish: without
    it, this was reproduced to oscillate — a unit walking toward task A raises A's own slack
    turn by turn (distance shrinking offsets the clock), while every task it ISN'T walking
    toward keeps draining, so an untouched task B can cross below A's slack mid-walk and steal
    the unit next turn; A then drains while B is approached, flipping back the turn after.
    Two units were observed stepping back and forth between the same pair of tiles
    indefinitely, watering almost nothing, before this was added. Continuing a still-valid
    commitment is preferred over switching, ahead of slack, so a unit that starts toward a
    task finishes reaching it instead of re-litigating the choice every turn. (A softer,
    coarse-urgency-tier version of this tiebreak was tried and measured to still oscillate,
    just on a ~3-turn period instead of every turn — unconditional stickiness is what's
    stable; a commitment only breaks when the task itself vanishes from the fresh task list.)
    """
    committed = committed or {}
    unit_positions = [snapshot.farmer_pos, *snapshot.hand_positions]
    actions = [["PASS"] for _ in unit_positions]
    remaining_tasks = list(tasks)
    unassigned_units = set(range(len(unit_positions)))
    seeds_remaining = dict(snapshot.seeds)
    new_commitments: dict[int, str] = {}
    # v1p.2: computed once from the original (pre-loop) task list, not `remaining_tasks` — the
    # day's zoning is a single decision, not something that reshapes itself as tasks get
    # assigned away turn-by-turn within this same call. v1p.2b: `committed` (this same turn's
    # incoming stickiness map) is threaded through so a unit already walking toward a task keeps
    # its zone pinned to that task, surviving this call's own zoning decision.
    zones = _zone_partition(tasks, snapshot, config, committed)

    def _carries_cargo(unit_index: int) -> bool:
        # plan.md §5.1 v1d / plan.md G5: unlike PLANT's seeds (a shared private-state pool
        # any co-located unit can draw from), FEED's wheat and PLACE's animal are cargo a
        # specific unit already carried there via an earlier PICKUP — a unit with none of it
        # can never complete the action regardless of distance, so it must not be eligible at
        # all (not just blocked once it arrives, which would waste a walk).
        inventory = snapshot.inventories[unit_index] if unit_index < len(snapshot.inventories) else {}
        if task.kind == "FEED":
            return inventory.get("WHEAT", 0) > 0
        if task.kind == "PLACE":
            return inventory.get(task.item, 0) > 0
        return True

    def _carries_wheat(unit_index: int) -> bool:
        # v1p.2: a unit already holding WHEAT is zone-exempt regardless of task kind. The feed
        # round's PICKUP is itself allowed_unit-restricted (already zone-exempt, one task per
        # unit), so this only ever matters for the FEED/CARE/HARVEST/COLLECT_FERTILIZER tasks
        # downstream of it — decided explicitly rather than left implicit, per ROADMAP §4.3 S3
        # step 1c: "decide explicitly whether carriers are zone-exempt while holding WHEAT."
        inventory = snapshot.inventories[unit_index] if unit_index < len(snapshot.inventories) else {}
        return inventory.get("WHEAT", 0) > 0

    while remaining_tasks and unassigned_units:
        candidates = []
        for task in remaining_tasks:
            eligible_units = [
                unit_index
                for unit_index in unassigned_units
                if (task.allowed_unit is None or task.allowed_unit == unit_index)
                and _carries_cargo(unit_index)
            ]
            # v1p.2: a zone is a filter on eligible_units, never on tasks — allowed_unit tasks
            # are already exempt (their eligible_units is at most one unit, unaffected below),
            # and a task whose own zone has nobody in it falls back to the full pool rather than
            # going unservable (a task quietly starving forever is a bug, not an outcome).
            if zones and task.allowed_unit is None:
                task_zone = _tile_quadrant(task.pos)
                zoned_units = [
                    unit_index for unit_index in eligible_units
                    if zones.get(unit_index) == task_zone or _carries_wheat(unit_index)
                ]
                if zoned_units:
                    eligible_units = zoned_units
            if not eligible_units:
                continue
            best_distance = min(
                abs(unit_positions[unit_index][0] - task.pos[0])
                + abs(unit_positions[unit_index][1] - task.pos[1])
                for unit_index in eligible_units
            )
            # v1b's pre-C1 sort key used raw task.deadline_step (not slack, and not 0) as its
            # second field — "pure nearest-pair-first" in plan.md's table means no *slack*
            # term, but v1b still broke ties by absolute deadline before distance.
            #
            # ablation §1.5.2 fix: among tasks sharing priority+deadline_step (the common
            # case), raw slack differs from every other such task only by -best_distance, so
            # unconditionally sorting by min(slack) always picked the FARTHEST task, all day
            # — not just when a task was actually about to miss its deadline. Gate the
            # queue-jump: only tasks within urgency_slack_margin turns of infeasibility sort
            # by slack ahead of distance (tier 0, C1/§1.2's far-but-urgent fix); every other
            # ("comfortable") task falls back to plain nearest-first (tier 1), matching v1b's
            # efficient default the rest of the time.
            slack = task.deadline_step - snapshot.step - (best_distance + 1)
            urgent = slack <= config["scheduler"]["urgency_slack_margin"]
            urgency_tier = 0 if urgent else 1
            task_slack = slack if urgent else 0
            for unit_index in eligible_units:
                unit_pos = unit_positions[unit_index]
                if (
                    task.kind == "PLANT"
                    and unit_pos == task.pos
                    and seeds_remaining.get(task.item, 0) <= 0
                ):
                    continue
                distance = abs(unit_pos[0] - task.pos[0]) + abs(unit_pos[1] - task.pos[1])
                switching = 0 if committed.get(unit_index) == task.id else 1
                candidates.append((
                    (
                        task.priority,
                        switching,
                        urgency_tier,
                        task_slack,
                        distance,
                        task.pos[1],
                        task.pos[0],
                        unit_index,
                        task.id,
                    ),
                    task,
                ))
        if not candidates:
            break

        # review.md L2: Task is a frozen dataclass without order=True, so it can't be compared
        # — sorting on (*, task) tuples only worked because (unit_index, task.id) is always
        # unique, making the tuple comparison stop one element early. Sort on the key tuple
        # explicitly so a future duplicate key fails loudly in the key, not by TypeError deep
        # inside tuple comparison.
        sort_key, task = min(candidates, key=lambda candidate: candidate[0])
        unit_index = sort_key[-2]
        unit_pos = unit_positions[unit_index]
        if unit_pos != task.pos:
            actions[unit_index] = _move_toward(unit_pos, task.pos)
            new_commitments[unit_index] = task.id
        elif task.kind in {"PLANT", "PLACE"}:
            actions[unit_index] = [task.kind, task.item]
            if task.kind == "PLANT":
                seeds_remaining[task.item] -= 1
        elif task.kind == "PICKUP":
            actions[unit_index] = [task.kind, task.item, task.count]
        else:
            actions[unit_index] = [task.kind]

        unassigned_units.remove(unit_index)
        # review.md M2: only tasks that actually compete for this pos should be dropped.
        # allowed_unit-restricted tasks (e.g. per-unit liquidation DROPs, all sharing the
        # shed's access tile) are non-competing by construction — dedup those by task.id so
        # only the just-assigned one is dropped, not every other unit's own DROP task at the
        # same pos. Unrestricted tasks keep the old pos-based mutual exclusion.
        remaining_tasks = [
            candidate for candidate in remaining_tasks
            if (
                candidate.id != task.id
                if candidate.allowed_unit is not None
                else candidate.pos != task.pos
            )
        ]

    return actions[0], actions[1:], new_commitments
