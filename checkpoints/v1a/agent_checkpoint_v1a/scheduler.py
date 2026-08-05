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
    target_tiles = tuple(config["scheduler"]["target_tiles"])
    plant_limit = plan.plant_targets.get("CARROT", 0)
    farmer_x, farmer_y = snapshot.farmer_pos
    turns_left_today = config["runtime"]["turns_per_day"] - snapshot.hour
    planted_today = sum(
        1
        for x, y in target_tiles
        if (
            isinstance(snapshot.my_tiles[y][x], dict)
            and snapshot.my_tiles[y][x].get("kind") == "PLANT"
            and snapshot.my_tiles[y][x].get("crop") == "CARROT"
            and snapshot.my_tiles[y][x].get("planted_day") == snapshot.day
        )
    )
    max_new_plants = int(config["planner"]["max_new_plants_per_day"])

    for target_index, (x, y) in enumerate(target_tiles):
        tile = snapshot.my_tiles[y][x]
        if isinstance(tile, dict) and tile.get("kind") == "PLANT":
            if tile.get("crop") != "CARROT":
                continue
            age = snapshot.day - tile["planted_day"]
            if not tile.get("watered_today") and (
                tile.get("consecutive_unwatered", 0) >= 1 or age >= 2
            ):
                tasks.append(Task(
                    id=f"water:{x}:{y}",
                    kind="WATER",
                    pos=(x, y),
                    priority=0,
                    deadline_step=day_deadline,
                ))
            if age >= 3 and tile.get("yield_units", 0) > 0:
                tasks.append(Task(
                    id=f"harvest:{x}:{y}",
                    kind="HARVEST",
                    pos=(x, y),
                    priority=0 if tile.get("watered_today") or age > 3 else 1,
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
            and snapshot.seeds.get("CARROT", 0) > 0
            and planted_today < max_new_plants
            and distance + 2 <= turns_left_today
        ):
            tasks.append(Task(
                id=f"plant:{x}:{y}",
                kind="PLANT",
                pos=(x, y),
                priority=3,
                item="CARROT",
                deadline_step=day_deadline - 1,
                required_inventory={"CARROT_SEED": 1},
                reservation_key="seed:CARROT",
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
    """Assign the nearest highest-urgency task to the v1a farmer."""
    if not tasks:
        return ["PASS"], [["PASS"] for _ in snapshot.hand_positions]

    farmer_x, farmer_y = snapshot.farmer_pos
    task = min(
        tasks,
        key=lambda candidate: (
            candidate.priority,
            candidate.deadline_step,
            abs(farmer_x - candidate.pos[0]) + abs(farmer_y - candidate.pos[1]),
            candidate.pos[1],
            candidate.pos[0],
            candidate.id,
        ),
    )
    if snapshot.farmer_pos != task.pos:
        farmer_action = _move_toward(snapshot.farmer_pos, task.pos)
    elif task.kind in {"PLANT", "PLACE"}:
        farmer_action = [task.kind, task.item]
    else:
        farmer_action = [task.kind]
    return farmer_action, [["PASS"] for _ in snapshot.hand_positions]
