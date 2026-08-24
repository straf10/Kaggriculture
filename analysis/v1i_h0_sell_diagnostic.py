#!/usr/bin/env python3
"""v1i (Η0) — measure-before-code diagnostic for the two remaining
sell-ahead levers, in the L1/L2/§v1n-Ρ1 pattern: aggregate-only, **no `agent/` changes**.

Two questions, both answered from replays rather than from a hypothesis:

Η1 ("exact per-unit sum instead of the endpoint check")
    agent/executor.py:209-213 stops at the first unit whose *quoted* price
    ``market_price(p, inventory + sell_units + safety_units)`` falls to the floor. The engine
    actually pays ``Σ p(inventory + i)`` per unit, so the batch's realized *average* is
    strictly above the marginal unit the loop tests. Measured here: how many units the
    marginal rule withholds that a batch-average rule (with a hard per-unit sub-floor at
    ``liquidation_floor_price``, so it can never manufacture <=$5 sales) would release, and
    what those units fetch.

Η2 (prediction controller / one-turn front-run)
    Only worth building if the opponent's sell wave moves the price of a product **we hold
    stock in**, inside a window we could react to. ⚠️ Engine fact that bounds this
    (kaggriculture.py:599-608): within one turn both players are quoted against the *same*
    pre-commit inventory, so a same-turn opponent sale costs us nothing. Only units the
    opponent committed on an EARLIER turn are front-runnable, so that is exactly what is
    priced here — at the previous turn, and across the whole day so far.

Both Η2 numbers are **perfect-oracle upper bounds**: they price the counterfactual on the
observed inventory path, with no controller-accuracy discount and no opponent response.

The market itself is replayed through `harness.metrics`' engine-faithful simulator (which
applies the turn's unit actions first — the engine does the same at kaggriculture.py:900-928,
and skipping it made 59 of 705 requested sell units commit in a first draft of this script).

Usage:
    python analysis/v1i_h0_sell_diagnostic.py --seeds 0-3 --out gates/v1i_h0_diagnostic
"""
import argparse
import copy
import gzip
import json
import statistics
import sys
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from kaggle_environments.envs.kaggriculture import kaggriculture as engine  # noqa: E402

from harness.metrics import _action, _apply_unit_actions  # noqa: E402

# Mirrors agent/config.py CONFIG["executor"]; restated as data so the diagnostic never
# imports the policy decision it is measuring.
SELL_FLOOR_PRICE = {
    "CARROT": 5, "STRAWBERRY": 8, "EGG": 5, "MILK": 15, "WOOL": 20, "FERTILIZER": 10,
}
LIQUIDATION_FLOOR = 5
SAFETY_UNITS = 4


def simulate_market(farms, privates, market, actions, configuration):
    """`harness.metrics._simulate_market`, plus the market inventory at each committed sale.

    Same loop and the same engine helpers; the only addition is recording
    ``inventory_at_sale`` per unit, which is what the Η2 counterfactual has to shift.
    """
    max_orders = max(1, int(configuration.get("maxMarketOrdersPerTurn", 10)))
    board_size = int(configuration.get("boardSize", 10))
    hire_mult = int(configuration.get("farmHandCostMult", 1))
    shed_capacity = int(configuration.get("shedCapacity", 100))
    queues = [
        list(action.get("market", []))[:max_orders]
        if isinstance(action.get("market", []), list)
        else []
        for action in actions
    ]
    sales = [[], []]

    for order_index in range(max((len(queue) for queue in queues), default=0)):
        order_states = [
            engine._parse_order(queue[order_index]) if order_index < len(queue) else None
            for queue in queues
        ]
        for seat, order_state in enumerate(order_states):
            if order_state is None:
                continue
            if order_state["type"] == "HIRE":
                engine._do_hire(farms[seat], privates[seat], board_size, hire_mult)
                order_states[seat] = None
            elif order_state["type"] == "BUY_LAND":
                engine._do_buy_land(farms[seat], board_size)
                order_states[seat] = None

        guard = 0
        while True:
            guard += 1
            if guard >= 100_000:
                break
            quoted = [None, None]
            for seat, order_state in enumerate(order_states):
                if order_state is None or order_state["remaining"] <= 0:
                    continue
                op, item = order_state["type"], order_state["item"]
                if op == "SELL" and item in engine.PRODUCTS:
                    price = engine.market_price(
                        item, market["inventory"][item], market.get("params")
                    )
                elif op == "BUY_PRODUCT" and item in ("WHEAT", "FERTILIZER"):
                    price = engine.market_price(
                        item, market["inventory"][item] - 1, market.get("params")
                    )
                elif op == "BUY_SEED" and item in engine.CROPS:
                    price = engine.CROPS[item]["seed"]
                elif op == "BUY_ANIMAL" and item in engine.ANIMALS:
                    price = engine.ANIMALS[item]["cost"]
                else:
                    order_states[seat] = None
                    continue
                quoted[seat] = (op, item, price, order_state)

            if all(quote is None for quote in quoted):
                break

            committed_any = False
            for seat, quote in enumerate(quoted):
                if quote is None:
                    continue
                op, item, price, order_state = quote
                inventory_at_sale = market["inventory"].get(item, 0)
                committed = engine._commit_unit(
                    op, item, price, farms[seat], privates[seat], market, shed_capacity,
                )
                if committed:
                    order_state["remaining"] -= 1
                    committed_any = True
                    if op == "SELL":
                        sales[seat].append(
                            {"item": item, "price": price,
                             "inventory_at_sale": inventory_at_sale}
                        )
                else:
                    order_states[seat] = None
            if not committed_any:
                break
        engine._refresh_prices(market)
    return sales


def analyse_replay(env_json, seat: int) -> dict:
    steps = env_json["steps"]
    configuration = env_json["configuration"]
    out = {
        "realized": defaultdict(lambda: {"units": 0, "revenue": 0}),
        # Η1
        "withheld_floor_bound": defaultdict(lambda: {"unit_turns": 0, "turns": 0}),
        "withheld_other": defaultdict(lambda: {"unit_turns": 0, "turns": 0}),
        "average_rule_extra": defaultdict(lambda: {"units": 0, "revenue": 0, "turns": 0}),
        "turns_with_sells": 0,
        # Η2
        "frontrun_prev_turn_gain": defaultdict(int),
        "frontrun_same_day_gain": defaultdict(int),
        "opponent_units": defaultdict(int),
        "opponent_units_by_day": defaultdict(int),
        "own_units_by_day": defaultdict(int),
        # closing state — is anything stranded that the floor could have released?
        "final_shed": {},
    }
    opponent_prev_turn = defaultdict(int)
    opponent_today = defaultdict(int)
    current_day = None

    for index in range(len(steps) - 1):
        previous_step, current_step = steps[index], steps[index + 1]
        observation = previous_step[0]["observation"]
        day = int(observation.get("day", 0))
        if day != current_day:
            current_day = day
            opponent_today = defaultdict(int)

        farms = copy.deepcopy(observation["farms"])
        market = copy.deepcopy(observation["market"])
        privates = [
            copy.deepcopy(previous_step[s]["observation"]["private"]) for s in (0, 1)
        ]
        shed_seen_by_executor = dict(privates[seat].get("shed") or {})
        inventory_pre = dict(market["inventory"])
        actions = [_action(current_step, s) for s in (0, 1)]
        _apply_unit_actions(farms, privates, actions, configuration, day)
        sales = simulate_market(farms, privates, market, actions, configuration)

        our_units = defaultdict(int)
        for sale in sales[seat]:
            product, price = sale["item"], sale["price"]
            out["realized"][product]["units"] += 1
            out["realized"][product]["revenue"] += price
            our_units[product] += 1
            out["own_units_by_day"][day] += 1
            for key, ahead in (("frontrun_prev_turn_gain", opponent_prev_turn[product]),
                               ("frontrun_same_day_gain", opponent_today[product])):
                if ahead:
                    shifted = engine.market_price(
                        product, sale["inventory_at_sale"] - ahead, market.get("params")
                    )
                    out[key][product] += max(0, shifted - price)

        opponent_this_turn = defaultdict(int)
        for sale in sales[1 - seat]:
            out["opponent_units"][sale["item"]] += 1
            out["opponent_units_by_day"][day] += 1
            opponent_this_turn[sale["item"]] += 1

        if our_units:
            out["turns_with_sells"] += 1

        # Η1. Iterating over every sellable product with stock (not only those that sold) is
        # load-bearing: a product the floor blocks *entirely* sells 0 units and would
        # otherwise be invisible. `unit_turns` is stock-days, not distinct units — the same
        # held unit is counted on every turn it sits — so it is a pressure indicator only.
        for product, floor in SELL_FLOOR_PRICE.items():
            sold = our_units.get(product, 0)
            left = int(shed_seen_by_executor.get(product, 0)) - sold
            if left <= 0:
                continue
            start = int(inventory_pre.get(product, 0))
            quote = engine.market_price(product, start + sold + SAFETY_UNITS,
                                        market.get("params"))
            bucket = "withheld_floor_bound" if quote <= floor else "withheld_other"
            out[bucket][product]["unit_turns"] += left
            out[bucket][product]["turns"] += 1
            if bucket != "withheld_floor_bound":
                continue
            # The batch-average rule Η1 asks for: keep taking units while the running mean of
            # Σ p(inventory + safety + i) stays >= floor, with a hard per-unit sub-floor at
            # liquidation_floor_price. Revenue is priced on the *live* post-turn inventory,
            # which is what those units would actually have fetched.
            total = sum(
                engine.market_price(product, start + SAFETY_UNITS + i, market.get("params"))
                for i in range(sold)
            )
            count = sold
            extra_units = 0
            extra_revenue = 0
            live = market["inventory"].get(product, 0)
            for i in range(sold, sold + left):
                unit = engine.market_price(
                    product, start + SAFETY_UNITS + i, market.get("params")
                )
                if unit <= LIQUIDATION_FLOOR or (total + unit) / (count + 1) < floor:
                    break
                total += unit
                count += 1
                realized = engine.market_price(
                    product, live + extra_units, market.get("params")
                )
                if realized <= LIQUIDATION_FLOOR:
                    break
                extra_units += 1
                extra_revenue += realized
            if extra_units:
                out["average_rule_extra"][product]["units"] += extra_units
                out["average_rule_extra"][product]["revenue"] += extra_revenue
                out["average_rule_extra"][product]["turns"] += 1

        opponent_prev_turn = opponent_this_turn
        for product, count in opponent_this_turn.items():
            opponent_today[product] += count

    final_private = steps[-1][seat]["observation"].get("private") or {}
    out["final_shed"] = {
        product: units for product, units in (final_private.get("shed") or {}).items()
        if units
    }
    return {
        key: (dict(value) if isinstance(value, defaultdict) else value)
        for key, value in out.items()
    }


def aggregate(episodes: list[dict]) -> dict:
    n = len(episodes)
    agg = {"episodes": n}
    for key in ("realized", "withheld_floor_bound", "withheld_other", "average_rule_extra"):
        merged = defaultdict(lambda: defaultdict(int))
        for episode in episodes:
            for product, values in episode[key].items():
                for field, value in values.items():
                    merged[product][field] += value
        agg[key] = {
            product: {field: round(value / n, 2) for field, value in fields.items()}
            for product, fields in merged.items()
        }
    for key in ("frontrun_prev_turn_gain", "frontrun_same_day_gain", "opponent_units",
                "final_shed"):
        merged = defaultdict(int)
        for episode in episodes:
            for product, value in episode[key].items():
                merged[product] += value
        agg[key] = {product: round(value / n, 2) for product, value in merged.items()}
        agg[key + "_total"] = round(sum(merged.values()) / n, 2)
    agg["turns_with_sells"] = statistics.mean(e["turns_with_sells"] for e in episodes)
    return agg


def parse_seeds(text: str) -> list[int]:
    seeds = []
    for chunk in text.split(","):
        if "-" in chunk:
            low, high = chunk.split("-")
            seeds.extend(range(int(low), int(high) + 1))
        else:
            seeds.append(int(chunk))
    return seeds


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--seeds", default="0-3")
    parser.add_argument("--opponents", default="main.py,harness/bench_agents/meta_route.py")
    parser.add_argument("--out", default="gates/v1i_h0_diagnostic")
    parser.add_argument("--replay-dir", default=None)
    args = parser.parse_args()

    out_dir = REPO / args.out
    out_dir.mkdir(parents=True, exist_ok=True)
    replay_dir = Path(args.replay_dir) if args.replay_dir else (out_dir / "replays")
    replay_dir.mkdir(parents=True, exist_ok=True)

    from harness.play import play

    report = {}
    for opponent in args.opponents.split(","):
        label = Path(opponent).stem
        per_episode = []
        for seed in parse_seeds(args.seeds):
            for seat in (0, 1):
                agent_a = "main.py" if seat == 0 else opponent
                agent_b = opponent if seat == 0 else "main.py"
                path = replay_dir / f"{label}_seed{seed}_seat{seat}.json.gz"
                if not path.exists():
                    result = play(agent_a, agent_b, seed=seed, record=True,
                                  run_dir=replay_dir, metrics=False)
                    result.replay_path.replace(path)
                with gzip.open(path, "rt", encoding="utf-8") as handle:
                    per_episode.append(analyse_replay(json.load(handle), seat))
        report[label] = aggregate(per_episode)

    (out_dir / "diagnosis.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
