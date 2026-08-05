"""Layer 2 deterministic task scheduler."""
from dataclasses import dataclass, field

from .config import CONFIG
from .constants import ANIMALS, SHED_ACCESS
from .planner import DayPlan
from .state import Snapshot, animals_needing

# review.md L8: was a bare hardcoded 719; derive it from the same config every call site
# already uses, so a runtime.episode_steps change can't silently leave this stale. Every
# production call site sets deadline_step explicitly — this only backs ad-hoc/test Tasks.
_DEFAULT_DEADLINE_STEP = CONFIG["runtime"]["episode_steps"] - 1


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
    unit_inventory: list[dict]
    shed_free: int
    money: float
    market_slots: int = 10


def build_tasks(snapshot: Snapshot, plan: DayPlan, config: dict) -> list[Task]:
    """Build deadline-aware v1a carrot tasks."""
    if not config["scheduler"].get("enabled", False):
        return []

    ablation = config["ablation"]
    tasks = []
    turns_per_day = config["runtime"]["turns_per_day"]
    day_deadline = (snapshot.day + 1) * turns_per_day - 1
    target_tiles_by_crop = config["scheduler"]["target_tiles"]
    target_specs = [
        (crop, target_index, pos)
        for crop in ("CARROT", "STRAWBERRY")
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
    max_new_plants = int(config["planner"]["max_new_plants_per_day"])
    # review.md H1/M6: cap PLANT task *creation* to what today's plant budget and the
    # currently-observed seed count can actually support, so assign() can never commit more
    # PLANT actions in one turn than the cap allows, and never sends a unit walking toward a
    # PLANT tile whose only seed was already claimed by an earlier task in this same build.
    plant_budget_remaining = max(0, max_new_plants - planted_today)
    seeds_budget = dict(snapshot.seeds)
    # v1b behavior when plant_task_cap is off: a single build-time threshold check, not a
    # per-task-decremented budget.
    plant_cap_ok_v1b = planted_today < max_new_plants

    for crop, target_index, (x, y) in target_specs:
        plant_limit = plan.plant_targets.get(crop, 0)
        tile = snapshot.my_tiles[y][x]
        if isinstance(tile, dict) and tile.get("kind") == "PLANT":
            if tile.get("crop") != crop:
                continue
            age = snapshot.day - tile["planted_day"]
            # review.md L7: v1b watered CARROT on `age >= 2` unconditionally, including past
            # the engine's yield window (ages 2-3) — a rare, small unit-turn waste, not
            # present in plan.md's ablation table but needed for the all-off self-test to
            # reproduce v1b exactly (criterion #1).
            carrot_water_age_ok = (2 <= age <= 3) if ablation["carrot_water_window"] else age >= 2
            needs_water = (
                not tile.get("watered_today")
                and (
                    tile.get("consecutive_unwatered", 0) >= 1
                    or (crop == "CARROT" and carrot_water_age_ok)
                )
            )
            if needs_water:
                tasks.append(Task(
                    id=f"water:{x}:{y}",
                    kind="WATER",
                    pos=(x, y),
                    priority=0,
                    deadline_step=day_deadline,
                ))
            harvest_due = (
                crop == "CARROT" and age >= 3
                or crop == "STRAWBERRY" and age >= 16
            )
            if harvest_due and tile.get("yield_units", 0) > 0:
                tasks.append(Task(
                    id=f"harvest:{x}:{y}",
                    kind="HARVEST",
                    pos=(x, y),
                    priority=(
                        0
                        if crop == "STRAWBERRY" or tile.get("watered_today") or age > 3
                        else 1
                    ),
                    deadline_step=min(day_deadline, tile.get("max_lifespan_step", day_deadline)),
                ))
            continue

        # review.md H5: feasibility used to be judged from the farmer's position only, even
        # though assign() may hand the task to a hand standing somewhere else entirely. Use
        # the closest unit's distance instead, so a hand near a far tile isn't blocked by
        # (and a hand far from a near tile doesn't wrongly greenlight) a farmer-only estimate.
        if config["ablation"]["per_unit_plant_feasibility"]:
            min_distance = min(abs(ux - x) + abs(uy - y) for ux, uy in unit_positions)
        else:
            farmer_x, farmer_y = unit_positions[0]
            min_distance = abs(farmer_x - x) + abs(farmer_y - y)
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

        plant_cap_ok = (
            (plant_budget_remaining > 0 and seeds_budget.get(crop, 0) > 0)
            if ablation["plant_task_cap"] else plant_cap_ok_v1b
        )
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
            if ablation["plant_task_cap"]:
                plant_budget_remaining -= 1
                seeds_budget[crop] -= 1

    if plan.force_liquidation:
        # review.md M1: one DROP task per loaded unit, restricted to that unit, instead of a
        # single global task an empty-inventory unit can monopolize with silent no-ops.
        access = (4, 4)  # the only initially unlocked shed-access tile
        if ablation["drop_task_per_unit"]:
            for unit_index, unit_pos in enumerate(unit_positions):
                del unit_pos
                inventory = snapshot.inventories[unit_index] if unit_index < len(snapshot.inventories) else {}
                if sum(inventory.values()) > 0:
                    tasks.append(Task(
                        id=f"drop:liquidation:{unit_index}",
                        kind="DROP",
                        pos=access,
                        priority=0,
                        deadline_step=config["runtime"]["episode_steps"] - 2,
                        allowed_unit=unit_index,
                    ))
        else:
            any_inventory = any(
                sum((snapshot.inventories[i] if i < len(snapshot.inventories) else {}).values()) > 0
                for i in range(len(unit_positions))
            )
            if any_inventory:
                tasks.append(Task(
                    id="drop:liquidation",
                    kind="DROP",
                    pos=access,
                    priority=0,
                    deadline_step=config["runtime"]["episode_steps"] - 2,
                ))

    tasks.extend(_build_animal_tasks(snapshot, plan, config, unit_positions, day_deadline))

    # review.md L8: truncation used to follow construction order (CARROT tiles first), not
    # priority — a footgun if the task pool ever actually reaches max_tasks (currently
    # unreachable at 400, but not something the code should rely on staying true).
    if ablation["priority_sort_before_truncate"]:
        tasks.sort(key=lambda task: task.priority)
    return tasks[:config["scheduler"]["max_tasks"]]


def animal_placed(snapshot: Snapshot, name: str) -> bool:
    for row in snapshot.my_tiles:
        for tile in row:
            if isinstance(tile, dict) and tile.get("animal") == name:
                return True
    return False


def animal_structure_ready(snapshot: Snapshot, config: dict, name: str) -> tuple[int, int] | None:
    """Position of `name`'s reserved structure tile if it's built, empty, and waiting — the
    home a just-bought animal can be carried to. None if the slot isn't built yet (or `name`
    has no reserved slot at all)."""
    structure_kind = ANIMALS[name]["structure"]
    tiles = config["scheduler"].get("animal_structure_tiles", {}).get(structure_kind, ())
    targets = config.get("animals", {}).get("targets", ())
    kind_targets = [n for n in targets if ANIMALS[n]["structure"] == structure_kind]
    if name not in kind_targets:
        return None
    slot_index = kind_targets.index(name)
    if slot_index >= len(tiles):
        return None
    x, y = tiles[slot_index]
    tile = snapshot.my_tiles[y][x]
    if isinstance(tile, dict) and tile.get("kind") == structure_kind and "animal" not in tile:
        return (x, y)
    return None


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

    # 2. Pickup/place: one animal at a time per target, in plan.animal_purchases order —
    # a placed animal needs nothing further here (its ongoing care is step 3), a carried one
    # just needs routing to its slot, and one still in the shed needs a PICKUP first.
    for name in plan.animal_purchases:
        if animal_placed(snapshot, name):
            continue
        target_pos = animal_structure_ready(snapshot, config, name)
        if target_pos is None:
            continue
        carried = sum(inv.get(name, 0) for inv in snapshot.inventories)
        if carried > 0:
            tasks.append(Task(
                id=f"place:{name}", kind="PLACE", pos=target_pos,
                priority=1, item=name, deadline_step=episode_deadline,
            ))
        elif snapshot.shed.get(name, 0) > 0:
            tasks.append(Task(
                id=f"pickup:{name}", kind="PICKUP", pos=spawn,
                priority=1, item=name, count=1, deadline_step=episode_deadline,
            ))

    # 3. Daily upkeep for whatever's already placed. FEED carries review.md C1's exact
    # zero-slack death mechanism (`consecutive_unfed >= 2`, engine :795) that WATER has, but
    # worse (escape = $300-500 lost capital, not a replantable tile) — fed every single day,
    # unconditionally, no every-other-day economy like carrot watering. Wheat must already be
    # in a unit's own inventory before FEED can be assigned to it (G5: reserved before use,
    # enforced in assign()'s eligibility filter, not here).
    animal_needs = animals_needing(snapshot)
    unfed_positions = [pos for pos, needed in animal_needs.items() if "FEED" in needed]
    if unfed_positions:
        carried_wheat = sum(inv.get("WHEAT", 0) for inv in snapshot.inventories)
        wheat_needed = len(unfed_positions) - carried_wheat
        wheat_available = int(snapshot.shed.get("WHEAT", 0))
        if wheat_needed > 0 and wheat_available > 0:
            tasks.append(Task(
                id="pickup:WHEAT", kind="PICKUP", pos=spawn,
                priority=0, item="WHEAT", count=min(wheat_needed, wheat_available),
                deadline_step=day_deadline,
            ))
        for (x, y) in unfed_positions:
            tasks.append(Task(
                id=f"feed:{x}:{y}", kind="FEED", pos=(x, y),
                priority=0, deadline_step=day_deadline,
            ))

    for (x, y), needed in animal_needs.items():
        if "CARE" in needed:
            tasks.append(Task(
                id=f"care:{x}:{y}", kind="CARE", pos=(x, y),
                priority=1, deadline_step=day_deadline,
            ))
        if "HARVEST" in needed:
            tasks.append(Task(
                id=f"harvest_animal:{x}:{y}", kind="HARVEST", pos=(x, y),
                priority=1, deadline_step=day_deadline,
            ))
        if "COLLECT_FERTILIZER" in needed:
            tasks.append(Task(
                id=f"fertilizer:{x}:{y}", kind="COLLECT_FERTILIZER", pos=(x, y),
                priority=3, deadline_step=day_deadline,
            ))
    return tasks


def make_ledger(snapshot: Snapshot) -> ResourceLedger:
    shed_used = sum(snapshot.shed.values())
    return ResourceLedger(
        seeds=dict(snapshot.seeds),
        unit_inventory=[dict(inv) for inv in snapshot.inventories],
        shed_free=max(0, 100 - shed_used),
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

    review.md C1/§1.2: each task's `slack` (deadline_step - step - the nearest currently
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
    ablation = config["ablation"]
    unit_positions = [snapshot.farmer_pos, *snapshot.hand_positions]
    actions = [["PASS"] for _ in unit_positions]
    remaining_tasks = list(tasks)
    unassigned_units = set(range(len(unit_positions)))
    seeds_remaining = dict(snapshot.seeds)
    new_commitments: dict[int, str] = {}

    def _carries_cargo(unit_index: int) -> bool:
        # plan.md §5.1 v1d / review.md G5: unlike PLANT's seeds (a shared private-state pool
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

    while remaining_tasks and unassigned_units:
        candidates = []
        for task in remaining_tasks:
            eligible_units = [
                unit_index
                for unit_index in unassigned_units
                if (task.allowed_unit is None or task.allowed_unit == unit_index)
                and _carries_cargo(unit_index)
            ]
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
            if ablation["slack_assign"]:
                slack = task.deadline_step - snapshot.step - (best_distance + 1)
                urgent = slack <= config["scheduler"]["urgency_slack_margin"]
                urgency_tier = 0 if urgent else 1
                task_slack = slack if urgent else 0
            else:
                urgency_tier = 0
                task_slack = task.deadline_step
            for unit_index in eligible_units:
                unit_pos = unit_positions[unit_index]
                if (
                    task.kind == "PLANT"
                    and unit_pos == task.pos
                    and seeds_remaining.get(task.item, 0) <= 0
                ):
                    continue
                distance = abs(unit_pos[0] - task.pos[0]) + abs(unit_pos[1] - task.pos[1])
                switching = (
                    (0 if committed.get(unit_index) == task.id else 1)
                    if ablation["task_stickiness"] else 0
                )
                candidates.append((
                    task.priority,
                    switching,
                    urgency_tier,
                    task_slack,
                    distance,
                    task.pos[1],
                    task.pos[0],
                    unit_index,
                    task.id,
                    task,
                ))
        if not candidates:
            break

        *_sort_key, task = min(candidates)
        unit_index = _sort_key[-2]
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
        remaining_tasks = [candidate for candidate in remaining_tasks if candidate.pos != task.pos]

    return actions[0], actions[1:], new_commitments
