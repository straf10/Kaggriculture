"""Shared animal-slot bookkeeping.

v1g: config["animals"]["targets"] moved from "one slot per unique animal name" (the v1d/v1e
model, where COW/SHEEP/GOOSE each owned exactly one reserved structure tile) to "N instances
of a named type sharing a structure kind's tile pool" (8 COW + 5 SHEEP both drawing from
PASTURE). Both planner.py and scheduler.py need to answer "which tile positions belong to
this animal name" — this lives in its own module, not either of theirs, because scheduler.py
already does `from .planner import DayPlan`, and planner.py importing back from scheduler.py
would be a cycle.
"""
from .constants import ANIMALS


def animal_slot_ranges(config: dict) -> dict[str, tuple[tuple[int, int], ...]]:
    """Reserved structure-tile positions per animal name.

    Carved contiguously out of each structure kind's `animal_structure_tiles` pool, in
    `config["animals"]["targets"]` dict order: the first COW-count PASTURE tiles are COW's,
    the next SHEEP-count are SHEEP's, and so on. Two animal names sharing a structure kind
    (COW/SHEEP both PASTURE) never overlap as long as their combined counts fit the pool —
    a name whose count runs past the end of its structure's tile pool silently gets fewer
    slots than requested (build_tasks' structures_to_build sizes the pool to match, so this
    is a config-consistency invariant, not a runtime condition to guard against here).
    """
    targets = config.get("animals", {}).get("targets", {})
    structure_tiles = config["scheduler"].get("animal_structure_tiles", {})
    offsets: dict[str, int] = {}
    ranges: dict[str, tuple[tuple[int, int], ...]] = {}
    for name, count in targets.items():
        structure = ANIMALS[name]["structure"]
        start = offsets.get(structure, 0)
        tiles = structure_tiles.get(structure, ())
        ranges[name] = tuple(tiles[start:start + int(count)])
        offsets[structure] = start + int(count)
    return ranges
