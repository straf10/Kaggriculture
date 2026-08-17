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


class TapeOverlay:
    """Seat-local, per-episode. One instance per running agent process/seat."""

    def __init__(self, stream, *,
                 shed_guard: int = 90,
                 liquidate_step: int = 690,
                 overlay_products=(_PRODUCT,),
                 floor_override: dict | None = None,
                 mode: str = "replace",
                 pull_forward_before_step: int = 336):
        self.stream = stream
        self.n = len(stream)
        self.shed_guard = shed_guard
        self.liquidate_step = liquidate_step
        self.overlay_products = tuple(overlay_products)
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
        self._last_step = step

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

    def act(self, obs, configuration=None):
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

        return {
            "farmer": tape_action.get("farmer", ["PASS"]),
            "hands": tape_action.get("hands", []),
            "market": combined,
        }


def make_overlay_agent(stream, **kwargs):
    """Return a fresh callable(obs, configuration) with its own seat-local overlay state."""
    overlay = TapeOverlay(stream, **kwargs)
    return overlay.act
