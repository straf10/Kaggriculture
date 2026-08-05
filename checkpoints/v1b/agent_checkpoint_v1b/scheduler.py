"""Layer 2 deterministic task scheduler."""
from dataclasses import dataclass, field

from .planner import DayPlan
from .state import Snapshot


@dataclass(frozen=True)
class Task:
    id: str
    kind: str
    pos: tuple[int, int]
    priority: int
    item: str | None = None
    count: int = 1
    deadline_step: int = 719
    prerequisites: tuple[str, ...] = ()
    required_inventory: dict[str, int] = field(default_factory=dict)
    reservation_key: str | None = None


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

    tasks = []
    day_deadline = (snapshot.day + 1) * config["runtime"]["turns_per_day"] - 1
    target_tiles_by_crop = config["scheduler"]["target_tiles"]
    target_specs = [
        (crop, target_index, pos)
        for crop in ("CARROT", "STRAWBERRY")
        for target_index, pos in enumerate(target_tiles_by_crop.get(crop, ()))
    ]
    farmer_x, farmer_y = snapshot.farmer_pos
    turns_left_today = config["runtime"]["turns_per_day"] - snapshot.hour
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

    for crop, target_index, (x, y) in target_specs:
        plant_limit = plan.plant_targets.get(crop, 0)
        tile = snapshot.my_tiles[y][x]
        if isinstance(tile, dict) and tile.get("kind") == "PLANT":
            if tile.get("crop") != crop:
                continue
            age = snapshot.day - tile["planted_day"]
            needs_water = (
                not tile.get("watered_today")
                and (
                    tile.get("consecutive_unwatered", 0) >= 1
                    or (crop == "CARROT" and age >= 2)
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

        distance = abs(farmer_x - x) + abs(farmer_y - y)
        if isinstance(tile, dict) and tile.get("kind") == "WEED":
            if target_index < plant_limit and distance + 3 <= turns_left_today:
                tasks.append(Task(
                    id=f"dig:{x}:{y}",
                    kind="DIG",
                    pos=(x, y),
                    priority=2,
                    deadline_step=day_deadline - 2,
                ))
            continue

        if (
            target_index < plant_limit
            and tile is None
            and snapshot.seeds.get(crop, 0) > 0
            and planted_today < max_new_plants
            and distance + 2 <= turns_left_today
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

    if any(snapshot.inventories) and plan.force_liquidation:
        access = (4, 4)  # the only initially unlocked shed-access tile
        tasks.append(Task(
            id="drop:liquidation",
            kind="DROP",
            pos=access,
            priority=0,
            deadline_step=config["runtime"]["episode_steps"] - 2,
        ))

    return tasks[:config["scheduler"]["max_tasks"]]


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


def assign(tasks: list[Task], snapshot: Snapshot) -> tuple[list[str], list[list[str]]]:
    """Greedily assign unique tasks to farmer and hands with seed reservations."""
    unit_positions = [snapshot.farmer_pos, *snapshot.hand_positions]
    actions = [["PASS"] for _ in unit_positions]
    remaining_tasks = list(tasks)
    unassigned_units = set(range(len(unit_positions)))
    seeds_remaining = dict(snapshot.seeds)

    while remaining_tasks and unassigned_units:
        candidates = []
        for unit_index in sorted(unassigned_units):
            unit_pos = unit_positions[unit_index]
            for task in remaining_tasks:
                if (
                    task.kind == "PLANT"
                    and unit_pos == task.pos
                    and seeds_remaining.get(task.item, 0) <= 0
                ):
                    continue
                distance = abs(unit_pos[0] - task.pos[0]) + abs(unit_pos[1] - task.pos[1])
                candidates.append((
                    task.priority,
                    task.deadline_step,
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
        elif task.kind in {"PLANT", "PLACE"}:
            actions[unit_index] = [task.kind, task.item]
            if task.kind == "PLANT":
                seeds_remaining[task.item] -= 1
        else:
            actions[unit_index] = [task.kind]

        unassigned_units.remove(unit_index)
        remaining_tasks = [candidate for candidate in remaining_tasks if candidate.pos != task.pos]

    return actions[0], actions[1:]
