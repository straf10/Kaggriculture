"""review_89d99f0_2026-08-05.md H4/G11: the scheduler commits WATER/PLANT/HARVEST expecting a specific tile
transition, but nothing ever checked whether the engine actually produced it — on an engine
that never raises, this was the only tool that could have turned "we lost $8k" into "the
WATER at (7,2) on step 341 didn't do what we expected", and it was missing. This module
builds the expected-transition record when an action is committed and reconciles it against
the following observation of the same seat.
"""
from .debug import emit_receipt
from .state import Snapshot


def expected_transition(unit_index: int, action: list, pos: tuple[int, int],
                         snapshot: Snapshot, config: dict) -> dict | None:
    """Record of what a just-committed WATER/PLANT/HARVEST at `pos` should look like next
    time this seat is observed. Returns None for actions with nothing worth reconciling
    (moves, PASS, market-only turns)."""
    if not action:
        return None
    kind = action[0]
    turns_per_day = config["runtime"]["turns_per_day"]
    x, y = pos
    tile = snapshot.my_tiles[y][x] if 0 <= y < len(snapshot.my_tiles) else None

    if kind == "WATER":
        # A WATER committed on the day's last hour is only visible as `watered_today` for the
        # instant before end-of-day resets it; by the time this seat is observed again the
        # day has rolled over, so check the *effect* of that reset (consecutive_unwatered
        # dropping to 0) instead of the flag itself (review_89d99f0_2026-08-05.md H4 "boundary-aware").
        if snapshot.hour == turns_per_day - 1:
            return {"kind": "expected_transition", "step": snapshot.step, "unit": unit_index,
                    "action": "WATER", "pos": list(pos), "field": "consecutive_unwatered",
                    "expected": 0, "eod_boundary": True}
        return {"kind": "expected_transition", "step": snapshot.step, "unit": unit_index,
                "action": "WATER", "pos": list(pos), "field": "watered_today",
                "expected": True, "eod_boundary": False}

    if kind == "PLANT":
        return {"kind": "expected_transition", "step": snapshot.step, "unit": unit_index,
                "action": "PLANT", "pos": list(pos), "field": "kind", "expected": "PLANT",
                "crop": action[1] if len(action) > 1 else None, "eod_boundary": False}

    if kind == "HARVEST":
        before = tile.get("yield_units", 0) if isinstance(tile, dict) else 0
        return {"kind": "expected_transition", "step": snapshot.step, "unit": unit_index,
                "action": "HARVEST", "pos": list(pos), "field": "yield_units",
                "before": before, "eod_boundary": False}

    return None


def _tile_at(snapshot: Snapshot, pos) -> object:
    x, y = pos
    if 0 <= y < len(snapshot.my_tiles) and 0 <= x < len(snapshot.my_tiles[y]):
        return snapshot.my_tiles[y][x]
    return None


def reconcile(pending: list[dict], snapshot: Snapshot) -> None:
    """Compare each pending expected-transition receipt to the current observation and emit
    a `reconciliation` receipt reporting whether the engine did what the scheduler expected."""
    for receipt in pending:
        tile = _tile_at(snapshot, receipt["pos"])
        action = receipt["action"]
        if action == "PLANT":
            ok = (
                isinstance(tile, dict)
                and tile.get("kind") == "PLANT"
                and tile.get("crop") == receipt.get("crop")
            )
            actual = tile.get("kind") if isinstance(tile, dict) else tile
        elif action == "WATER":
            ok = isinstance(tile, dict) and tile.get(receipt["field"]) == receipt["expected"]
            actual = tile.get(receipt["field"]) if isinstance(tile, dict) else tile
        elif action == "HARVEST":
            after = tile.get("yield_units", 0) if isinstance(tile, dict) else 0
            ok = tile is None or after < receipt["before"]
            actual = after
        else:
            continue
        emit_receipt({
            "kind": "reconciliation",
            "issued_step": receipt["step"],
            "checked_step": snapshot.step,
            "unit": receipt["unit"],
            "action": action,
            "pos": receipt["pos"],
            "ok": bool(ok),
            "actual": actual,
        })
