"""T2 — the closed-loop market overlay on an open-loop donor tape (ROADMAP §4.3 S3 step 3).

Keeps the donor tape's `farmer`/`hands` verbatim (T1 proved these run byte-identically against
every opponent) and its `market` BUY/HIRE orders verbatim (they fund production; Phase 0 showed
the cash floor is ≈$6 and several turns depend on same-turn non-strawberry sell revenue). The
overlay replaces ONLY the tape's STRAWBERRY sells with our own live sell logic
(`_sell_batch_size` + the v1i `OpponentSupplyTracker`), because Phase 0 established that
STRAWBERRY — the −61% realised-price loss T1 measured — is *never* a cash-funding dependency on
any turn, which makes a strawberry-only overlay UNCONDITIONALLY cash-safe: every BUY is funded
entirely by the non-strawberry sells we keep verbatim, so no BUY can silently fail whatever we do
with strawberry timing.

Two residual risks a strawberry-only overlay must still guard (Phase 0 §3):
  * shed overflow — the tape's shed peaks at 95–100 against a cap of 100; if we hold strawberry
    too long it burns. Guard: liquidate strawberry once the shed is near full.
  * end-of-season stranding — unsold strawberry at step 718 is lost. Guard: liquidate late.

Order discipline: kept BUY/HIRE/other-sell orders keep their ORIGINAL relative positions (so the
within-turn buy-after-sell dependencies Phase 0 found at steps 48/72/120/168/252 are preserved
byte-for-byte) and always precede our appended strawberry sells, so the engine's 10-order cap
(`q[:10]`, silently drops the rest) can only ever drop a strawberry sell, never a purchase.

This module is import-based for the gate harness. The shipped self-contained `main.py` inlines
the same logic (build_tape_overlay_submission.py) — no `agent/` import at runtime (§2.12).
"""
from __future__ import annotations

from .config import CONFIG
from .constants import market_price
from .executor import _safety_units, _sell_batch_size
from .sell_ahead import OpponentSupplyTracker
from .state import parse

_PRODUCT = "STRAWBERRY"

_TILE_OPS = {"WATER", "PLANT", "DIG", "HARVEST", "FERTILIZE",
             "BUILD_COOP", "BUILD_PASTURE", "FEED", "CARE", "COLLECT_FERTILIZER"}


def _tile_valid(op, tile):
    """True if a tile-level action is effective (not a silent no-op) given the tile."""
    if op == "WATER":
        return isinstance(tile, dict) and tile.get("kind") == "PLANT" and not tile.get("watered_today")
    if op == "PLANT":
        return tile is None
    if op == "DIG":
        return tile is not None and not (isinstance(tile, dict) and "animal" in tile)
    if op == "HARVEST":
        return isinstance(tile, dict) and tile.get("yield_units", 0) > 0
    if op == "FERTILIZE":
        return isinstance(tile, dict) and tile.get("kind") == "PLANT"
    if op in ("BUILD_COOP", "BUILD_PASTURE"):
        return tile is None
    if op == "FEED":
        return isinstance(tile, dict) and "animal" in tile and not tile.get("fed_today")
    if op == "CARE":
        return isinstance(tile, dict) and "animal" in tile and not tile.get("cared_today")
    if op == "COLLECT_FERTILIZER":
        return isinstance(tile, dict) and "animal" in tile and tile.get("fertilizer_available")
    return True


def _tile_recovery(op, tile):
    """Return the recovery action list when `op` is invalid on `tile`."""
    if op == "WATER":
        if isinstance(tile, dict) and tile.get("kind") == "WEED":
            return ["DIG"]
        return ["PASS"]
    if op == "PLANT":
        if isinstance(tile, dict) and tile.get("kind") == "PLANT":
            if not tile.get("watered_today"):
                return ["WATER"]
            return ["PASS"]
        if isinstance(tile, dict) and tile.get("kind") == "WEED":
            return ["DIG"]
        return ["PASS"]
    if op == "DIG":
        return ["PASS"]
    if op == "HARVEST":
        if isinstance(tile, dict) and tile.get("kind") == "PLANT" and not tile.get("watered_today"):
            return ["WATER"]
        return ["PASS"]
    return ["PASS"]


class TapeOverlay:
    """Seat-local, per-episode. One instance per running agent process/seat."""

    def __init__(self, stream, *,
                 shed_guard: int = 90,
                 liquidate_step: int = 690,
                 overlay_products=(_PRODUCT,),
                 floor_override: dict | None = None,
                 mode: str = "augment",
                 pull_forward_before_step: int = 336,
                 liq_floor_price: int = 25,
                 liq_first_day: int = 22,
                 liq_h_max: int = 12,
                 liq_d_days: int = 4,
                 liq_force_step: int = 686):
        self.stream = stream
        self.n = len(stream)
        self.shed_guard = shed_guard
        self.liquidate_step = liquidate_step
        self.overlay_products = tuple(overlay_products)
        # mode="liquidate" (S9 Phase 1, H2): a FROZEN transfer of the tail-liquidation rule
        # validated in analysis/s9_h2_k10.py::make_h2_agent(variant="tail"). It is NOT the market
        # augment/replace channel — it keeps every tape order verbatim (farmer/hands/BUY/HIRE/other
        # sells) and only DEFERS the sub-$25 tail of a STRAWBERRY batch on day >= liq_first_day,
        # re-selling at the first later step whose price is back >= liq_floor_price, or when forced.
        # No tile recovery (the arm is market-only, ROADMAP §3.1(2)). Every parameter is frozen;
        # none is tuned in this pass. Any change to this path must also land in the inlined copy in
        # analysis/build_tape_overlay_submission.py (bit-equivalent, part of G13).
        self.liq_floor_price = int(liq_floor_price)
        self.liq_first_day = int(liq_first_day)
        self.liq_h_max = int(liq_h_max)
        self.liq_d_days = int(liq_d_days)
        self.liq_force_step = int(liq_force_step)
        # Held-tail state. Seat-local and per-episode; reset in _reset_if_new_episode at the exact
        # point the tracker resets (a mid-episode carry-over would open episode 2 holding phantom
        # units).
        self._held_units = 0
        self._held_since_day = None
        # mode="replace": strip the tape's overlay-product sells, substitute ours (can DEFER →
        #   overflows the shed; Phase 0 forbade this).
        # mode="augment": keep ALL of the tape's orders verbatim and only ADD early sells before
        #   `pull_forward_before_step` (the tape's own strawberry window opens ~day 14 = step
        #   336). Shed occupancy is then monotonically ≤ the tape's — no new overflow, no feed
        #   starvation — and the added sells capture the pre-flood price. This is the pull-
        #   forward-only design Phase 0 §3 prescribed.
        self.mode = mode
        self.pull_forward_before_step = pull_forward_before_step
        exec_cfg = CONFIG["executor"]
        self.exec_cfg = exec_cfg
        self.liq_floor = int(exec_cfg["liquidation_floor_price"])
        # sell_floor_price is calibrated for our own LOW strawberry volume, where dumping barely
        # moves the market; at the tape's ~300-unit volume the floor must throttle price impact.
        # floor_override lets the viability probe engage the sell-ahead controller (a floor near
        # the ~$120 equilibrium price is what makes safety_units and average_rule actually bind).
        self.static_floor = dict(exec_cfg["sell_floor_price"])
        if floor_override:
            self.static_floor.update(floor_override)
        self.average_rule = bool(exec_cfg.get("sell_ahead", {}).get("average_rule", False))
        horizon = exec_cfg.get("sell_ahead", {}).get("predict_horizon_turns", 6)
        self.tracker = OpponentSupplyTracker(horizon)
        self._last_step = None

    def _reset_if_new_episode(self, step: int) -> None:
        # The Kaggle server reuses the process across episodes; a step that did not advance by
        # one from the last means a new episode (seat-local tracker must reset, G13/policy.py).
        if self._last_step is None or step <= self._last_step:
            horizon = self.exec_cfg.get("sell_ahead", {}).get("predict_horizon_turns", 6)
            self.tracker = OpponentSupplyTracker(horizon)
            self._held_units = 0
            self._held_since_day = None
        self._last_step = step

    @staticmethod
    def _recover_tile_actions(snapshot, farmer_a, hands_a):
        tiles = snapshot.my_tiles
        all_actions = [farmer_a] + list(hands_a)
        positions = [snapshot.farmer_pos] + list(snapshot.hand_positions)
        for i, action in enumerate(all_actions):
            if i >= len(positions):
                break
            if not (isinstance(action, list) and action):
                continue
            op = action[0]
            if op not in _TILE_OPS:
                continue
            x, y = positions[i]
            if y < len(tiles) and x < len(tiles[y]):
                tile = tiles[y][x]
            else:
                tile = None
            if not _tile_valid(op, tile):
                recovery = _tile_recovery(op, tile)
                if i == 0:
                    farmer_a = recovery
                else:
                    hands_a[i - 1] = recovery
        return farmer_a, hands_a

    def _decide_sells(self, snapshot, configuration) -> list[list]:
        orders = []
        shed_total = sum(int(v) for v in snapshot.shed.values())
        for product in self.overlay_products:
            stock = int(snapshot.shed.get(product, 0))
            if stock <= 0:
                continue
            inventory = int(snapshot.market_inventory.get(product, 0))
            liquidate = (snapshot.step >= self.liquidate_step) or (shed_total >= self.shed_guard)
            if liquidate:
                floor = self.liq_floor
                safety = 0
            else:
                floor = int(self.static_floor.get(product, 5))
                safety = _safety_units(snapshot, self.exec_cfg, product, self.tracker)
            n = _sell_batch_size(product, stock, inventory, safety, floor,
                                 self.liq_floor, self.average_rule)
            if n > 0:
                orders.append(["SELL", product, int(n)])
        return orders

    def _sellable_above_floor(self, inv: int, q: int) -> int:
        """How many of q units still price at or above the floor, walking the engine's own
        (monotone non-increasing) price curve one unit at a time. Reading market_price(inv) once
        is not enough: a batch can start at $120 and end at $1, and the sub-floor units are exactly
        the tail we defer (analysis/s9_h2_k10.py::_sellable_above_floor)."""
        n = 0
        for j in range(q):
            if market_price(_PRODUCT, inv + j) < self.liq_floor_price:
                break
            n += 1
        return n

    def _liquidate_act(self, obs):
        """H2 tail-liquidation, frozen. Byte-for-byte the tail variant of
        analysis/s9_h2_k10.py::make_h2_agent — no tile recovery, farmer/hands verbatim."""
        step = obs.get("step", 0) if hasattr(obs, "get") else int(getattr(obs, "step", 0))
        self._reset_if_new_episode(step)
        snapshot = parse(obs)
        t = step
        day = t // 24
        base = self.stream[t] if 0 <= t < self.n else {"farmer": ["PASS"], "hands": [], "market": []}
        inv = int(snapshot.market_inventory.get(_PRODUCT, 0))
        shed = int(snapshot.shed.get(_PRODUCT, 0))

        out = []
        for od in list(base.get("market") or []):
            is_target = (isinstance(od, list) and len(od) >= 3 and od[0] == "SELL"
                         and od[1] == _PRODUCT and day >= self.liq_first_day
                         and t < self.liq_force_step)
            if not is_target:
                out.append(od)
                continue
            q = int(od[2])
            keep = self._sellable_above_floor(inv, q)
            room = max(0, self.liq_h_max - self._held_units)
            defer = min(q - keep, room)
            if defer > 0:
                if self._held_units == 0:
                    self._held_since_day = day
                self._held_units += defer
            if q - defer > 0:
                out.append([od[0], od[1], q - defer])

        if self._held_units > 0:
            forced = (t >= self.liq_force_step) or (day - self._held_since_day > self.liq_d_days)
            above = market_price(_PRODUCT, inv) >= self.liq_floor_price
            if forced or above:
                qty = min(self._held_units, shed)
                if qty > 0 and len(out) <= 9:
                    out.append(["SELL", _PRODUCT, qty])
                    self._held_units = 0
                    self._held_since_day = None
                elif qty <= 0:
                    # the tape already sold the shed out from under us; nothing to re-sell.
                    self._held_units = 0
                    self._held_since_day = None
                # elif forced: blocked by the 10-order cap this step — carry to the next step.

        return {
            "farmer": base.get("farmer", ["PASS"]),
            "hands": base.get("hands", []),
            "market": out[:10],
        }

    def act(self, obs, configuration=None):
        if self.mode == "liquidate":
            return self._liquidate_act(obs)
        step = obs.get("step", 0) if hasattr(obs, "get") else int(getattr(obs, "step", 0))
        self._reset_if_new_episode(step)
        snapshot = parse(obs)
        self.tracker.observe(snapshot, configuration)

        if 0 <= step < self.n:
            tape_action = self.stream[step]
        else:
            tape_action = {"farmer": ["PASS"], "hands": [], "market": []}

        tape_market = tape_action.get("market", []) or []
        overlay_set = set(self.overlay_products)

        if self.mode == "augment":
            # Keep every tape order verbatim; only ADD early sells (before the tape opens its own
            # window) so shed occupancy is monotonically ≤ the tape's. After the window opens the
            # tape's own sells carry the product, so we add nothing (avoids double-selling).
            kept = list(tape_market)
            if step < self.pull_forward_before_step:
                our_sells = self._decide_sells(snapshot, configuration)
            else:
                our_sells = []
        else:  # replace
            kept = [o for o in tape_market
                    if not (isinstance(o, list) and len(o) >= 2
                            and o[0] == "SELL" and o[1] in overlay_set)]
            our_sells = self._decide_sells(snapshot, configuration)

        combined = kept + our_sells  # kept (incl. purchases) first → 10-cap can only drop a straw sell

        self.tracker.record_our_orders(
            [o for o in combined if isinstance(o, list) and o and o[0] == "SELL"])

        farmer_a = list(tape_action.get("farmer", ["PASS"]))
        hands_a = [list(h) for h in tape_action.get("hands", [])]

        farmer_a, hands_a = self._recover_tile_actions(
            snapshot, farmer_a, hands_a)

        return {
            "farmer": farmer_a,
            "hands": hands_a,
            "market": combined,
        }


def make_overlay_agent(stream, **kwargs):
    """Return a fresh callable(obs, configuration) with its own seat-local overlay state."""
    overlay = TapeOverlay(stream, **kwargs)
    return overlay.act
