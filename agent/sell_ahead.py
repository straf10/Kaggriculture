"""current_phase.md §v1i (Η2) — the c68 opponent-supply controller, prediction only.

What it predicts, and why that is the *only* actionable prediction here
---------------------------------------------------------------------
The Η0 diagnostic (`analysis/v1i_h0_sell_diagnostic.py`, `gates/v1i_h0_diagnostic/`) measured
that the executor already sells, every turn, everything its floor lets it sell: on 24 mirror
episodes only 5.5 unit-turns/ep of non-floor-bound stock ever sat unsold. So there is no
"wait, then front-run" decision to make — the agent is never waiting. What the executor does
have is a **threshold** it applies against an assumed opponent, and that assumption is a
hardcoded constant: `opponent_price_safety_units = 4` in agent/config.py, added to the quoted
index to model the opponent selling into the same per-unit lockstep index we are
(engine_reference/kaggriculture.py:599-608 — both players are quoted against the same
pre-commit inventory, so a *simultaneous* sale is the only opponent sale that costs us
anything within a turn).

So the controller replaces that constant with a measurement. It is two-sided by construction:
a quiet opponent lowers it and we realize units the constant refused, a selling opponent
raises it above 4 and we are protected better than the constant ever was.

Three sources, none of them a hardcoded calendar (current_phase.md §v1i)
-----------------------------------------------------------------------
(i)   The meta sell calendar is **deliberately absent**. §v1i's own warning — the calendar
      moved milk 8->10 and strawberry 16->18 inside a single ladder day — makes an empty
      prior the design requirement, not a fallback: this controller has no prior at all and
      degrades to the configured constant before it has seen two turns.
(ii)  Live market inventory. Between two observations the inventory moved by our own sales,
      the town's deterministic drain, and the opponent's sales — and the first two are known
      exactly, so the third is recoverable:

          opponent_batch = inventory_now - inventory_before + town_drain - our_units_sold

      `agent.demand.npc_step_demand` supplies the drain term, engine-pinned. This is the c68
      controller: recover the opponent's batches, fit over a short horizon, project one turn.
(iii) Visible ripe opponent tiles. The opponent's farm is public, so stock that is *about to*
      reach the market is observable before any of it shows up in (ii). Used only to raise a
      prediction the observed rate has not caught up with yet — a wave's first turn.

The prediction is a **median** over the horizon, not a mean or a max: one truncation-driven
spike in an opponent's emission must not move our threshold for six turns.
"""
from .constants import ANIMALS, CROPS
from .demand import npc_step_demand

#: Which tile output feeds which market product. Animals list their own product; crops are
#: sold under their own name.
_ANIMAL_PRODUCT = {name: data["product"] for name, data in ANIMALS.items()
                   if isinstance(data, dict) and "product" in data}


def _median(values: list[int]) -> float:
    ordered = sorted(values)
    count = len(ordered)
    if not count:
        return 0.0
    middle = count // 2
    if count % 2:
        return float(ordered[middle])
    return 0.5 * (ordered[middle - 1] + ordered[middle])


class OpponentSupplyTracker:
    """Seat-local, per-episode. Owned by `policy.RuntimeContext`, never module-global.

    Determinism (G13): every reader iterates an explicit product list or a sorted key order,
    and the only stored state is integer counts, so two processes with different
    `PYTHONHASHSEED` produce identical predictions.
    """

    def __init__(self, horizon_turns: int = 6):
        self.horizon_turns = max(1, int(horizon_turns))
        self._previous_inventory: dict[str, int] | None = None
        self._previous_step: int | None = None
        self._our_pending_sales: dict[str, int] = {}
        self._batches: dict[str, list[int]] = {}

    # -- (ii) live market inventory ------------------------------------------------------
    def observe(self, snapshot, env_config=None) -> None:
        """Fold one turn's inventory move into the per-product batch history."""
        inventory = {
            product: int(units) for product, units in snapshot.market_inventory.items()
        }
        if self._previous_inventory is not None and self._previous_step is not None:
            drain = npc_step_demand(
                snapshot.unlocked_shops, self._previous_step, env_config
            )
            for product in sorted(inventory):
                moved = inventory[product] - self._previous_inventory.get(product, 0)
                opponent = (
                    moved
                    + drain.get(product, 0)
                    - self._our_pending_sales.get(product, 0)
                )
                history = self._batches.setdefault(product, [])
                history.append(max(0, opponent))
                if len(history) > self.horizon_turns:
                    del history[:-self.horizon_turns]
        self._previous_inventory = inventory
        self._previous_step = snapshot.step
        self._our_pending_sales = {}

    def record_our_orders(self, orders) -> None:
        """Remember what we asked to sell this turn so the next `observe` can subtract it.

        Requested, not committed: the engine can refuse a unit (empty shed, $1 sales do not
        raise inventory at all), which makes this an over-subtraction and therefore biases
        the recovered opponent batch *down*. That is the safe direction — it can only make
        the controller predict less pressure than there is, i.e. behave more like today.
        """
        pending: dict[str, int] = {}
        for order in orders:
            if isinstance(order, list) and len(order) >= 3 and order[0] == "SELL":
                try:
                    pending[order[1]] = pending.get(order[1], 0) + int(order[2])
                except (TypeError, ValueError):
                    continue
        self._our_pending_sales = pending

    # -- (iii) visible ripe opponent tiles -----------------------------------------------
    @staticmethod
    def visible_opponent_supply(snapshot, day: int) -> dict[str, int]:
        """Units sitting harvest-ready on the opponent's public tiles, by market product."""
        supply: dict[str, int] = {}
        for row in snapshot.opponent_tiles:
            for tile in row:
                if not isinstance(tile, dict):
                    continue
                units = int(tile.get("yield_units", 0) or 0)
                if units <= 0:
                    continue
                if "animal" in tile:
                    product = _ANIMAL_PRODUCT.get(tile.get("animal"))
                elif tile.get("kind") == "PLANT":
                    crop = tile.get("crop")
                    crop_data = CROPS.get(crop)
                    if crop_data is None:
                        continue
                    if day - int(tile.get("planted_day", day)) < crop_data["first_yield_day"]:
                        continue
                    product = crop
                else:
                    continue
                if product:
                    supply[product] = supply.get(product, 0) + units
        return supply

    # -- the prediction -------------------------------------------------------------------
    def predicted_units(self, snapshot, product: str) -> int | None:
        """Opponent units expected in the next turn's lockstep, or None with no evidence."""
        history = self._batches.get(product)
        if not history:
            return None
        rate = _median(history)
        visible = self.visible_opponent_supply(snapshot, snapshot.day).get(product, 0)
        if visible > 0 and rate <= 0:
            # Their stock is ripe but has not reached the market yet — a wave's first turn is
            # exactly the turn the observed rate cannot see. One unit is enough of a signal;
            # the caller clamps the magnitude.
            return 1
        return int(round(rate))
