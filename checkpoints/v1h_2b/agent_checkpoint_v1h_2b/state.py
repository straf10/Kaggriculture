"""Observation parsing with no policy decisions."""
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Snapshot:
    step: int
    day: int
    hour: int
    player: int
    money: float
    my_tiles: list
    # review.md L9: opponent_money/unlocked_shops had zero real readers and were removed;
    # opponent_tiles is kept despite also having no current reader — it's reserved for a
    # Phase 2 opponent-aware selling policy (undercutting/matching the opponent's own sell
    # behavior), not dead in the same sense.
    # v1g.2 (current_phase.md §v1g.2 α): `unlocked_shops` is back, and now has a real reader —
    # agent.demand.npc_daily_demand, which turns it into the exact per-day NPC absorption rate
    # the sell floors are sized against. Kept as a tuple (not a list) so the frozen dataclass
    # stays hashable-by-value and, more importantly, so no downstream reader can mutate the
    # observation's own list in place. Order is the engine's unlock order and is preserved —
    # never iterate a set of it (G13 determinism).
    opponent_tiles: list
    farmer_pos: tuple[int, int]
    hand_positions: tuple[tuple[int, int], ...]
    shed: dict
    seeds: dict
    inventories: tuple[dict, ...]
    market_inventory: dict
    market_prices: dict
    my_quadrants: tuple[str, ...]
    hires_today: int
    unlocked_shops: tuple[str, ...] = ()


def parse(obs: Any) -> Snapshot:
    """Convert the framework observation mapping into a stable view."""
    player = int(obs.get("player", 0))
    farms = obs.get("farms", [])
    mine = farms[player] if player < len(farms) else {}
    opponent_index = 1 - player
    opponent = farms[opponent_index] if opponent_index < len(farms) else {}
    private = obs.get("private", {}) or {}
    market = obs.get("market", {}) or {}
    town = obs.get("town", {}) or {}

    return Snapshot(
        step=int(obs.get("step", 0)),
        day=int(obs.get("day", 0)),
        hour=int(obs.get("hour", 0)),
        player=player,
        money=float(mine.get("money", 0.0)),
        my_tiles=mine.get("tiles", []),
        opponent_tiles=opponent.get("tiles", []),
        farmer_pos=tuple(mine.get("farmer", (0, 0))),
        hand_positions=tuple(tuple(pos) for pos in mine.get("hands", [])),
        shed=dict(private.get("shed", {})),
        seeds=dict(private.get("seeds", {})),
        inventories=tuple(dict(inv) for inv in private.get("inventories", [])),
        market_inventory=dict(market.get("inventory", {})),
        market_prices=dict(market.get("prices", {})),
        my_quadrants=tuple(mine.get("unlocked_quadrants", [])),
        hires_today=int(mine.get("hires_today", 0)),
        # v1g.2: the engine appends duplicates here once shops are drawn WITH replacement
        # (§0bis balance change) — do NOT de-duplicate, every instance is its own buyer.
        unlocked_shops=tuple(town.get("unlocked_shops", ()) or ()),
    )


def animals_needing(snapshot: Snapshot) -> dict[tuple[int, int], set[str]]:
    needs = {}
    for y, row in enumerate(snapshot.my_tiles):
        for x, tile in enumerate(row):
            if not (isinstance(tile, dict) and "animal" in tile):
                continue
            actions = set()
            if not tile.get("fed_today"):
                actions.add("FEED")
            if not tile.get("cared_today"):
                actions.add("CARE")
            if tile.get("fertilizer_available"):
                actions.add("COLLECT_FERTILIZER")
            if tile.get("yield_units", 0) > 0:
                actions.add("HARVEST")
            needs[(x, y)] = actions
    return needs
