#!/usr/bin/env python3
"""Package a self-contained overlay submission: reconstruction + market overlay + tile recovery.

Inlines the full TapeOverlay logic (agent/tape_overlay.py) with all dependencies so the
shipped main.py has no `agent/` import at runtime (§2.12). The overlay has two channels:

  1. Market overlay (augment mode) — adds early STRAWBERRY sells before the tape's own window
     opens (~step 336), using the sell-ahead controller. Shed occupancy is monotonically ≤ the
     tape's (the reconstruction peaks at 72/100, so there is headroom).

  2. Tile recovery (§7.2 component (i)) — when the tape issues a tile action that is a no-op
     on the actual board state (e.g. WATERing a WEED), substitutes the cheapest legal recovery.

Usage:
    python analysis/build_tape_overlay_submission.py --team ReCurSiON --package
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import tarfile
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

DERIVED = ROOT / "data" / "derived"


def _sha256(stream: list) -> str:
    return hashlib.sha256(json.dumps(stream, separators=(",", ":")).encode("utf-8")).hexdigest()


def _assert_gitignored(path: Path) -> None:
    rel = path.resolve().relative_to(ROOT)
    res = subprocess.run(["git", "check-ignore", "-q", str(rel)], cwd=ROOT)
    if res.returncode != 0:
        raise SystemExit(
            f"REFUSING to write to {rel}: not gitignored. The route is derived from "
            f"competition data and must stay out of this public repo (§2.4b)."
        )


# The self-contained main.py template. All overlay logic is inlined.
MAIN_TEMPLATE = '''\
"""Kaggriculture submission — reconstruction + market overlay + tile recovery (§7.2).

COMPETITION DATA — this file embeds a route reconstructed from another participant's episode
traces plus two closed-loop overlays. Gitignored (§2.4b). Provenance in provenance.json.

    donor team      : {team}
    reconstruction  : per-decision majority vote across {n_traces} of {team}'s own traces
    agreement       : production {prod_agr:.4f}, market {market_agr:.4f}
    stream sha256   : {sha256}
    n_steps         : {n_steps}
    overlays        : (1) market — augment-mode strawberry sell-ahead
                      (2) tile recovery — §7.2 component (i), {n_recovery_rules} recovery rules
"""
import json
import math

# ── embedded stream ──────────────────────────────────────────────────────────
_STREAM = json.loads(r"""{stream_json}""")
_N = len(_STREAM)

# ── vendored engine constants (1.32.7) ───────────────────────────────────────
_MARKET_I0 = 10000
_PRICE_FLOOR = 1
_HINGE_GAIN = 8.0

_MARKET_PARAMS = {{
    "WHEAT": {{"base": 25, "I0": _MARKET_I0, "T": 400, "below_func": "sqrt", "below_target": 0.80, "above_func": "log", "above_target": 0.20}},
    "CARROT": {{"base": 35, "I0": _MARKET_I0, "T": 450, "below_func": "hinge", "below_target": 1.00, "above_func": "sqrt", "above_target": 0.70}},
    "TOMATO": {{"base": 60, "I0": _MARKET_I0, "T": 200, "below_func": "hinge", "below_target": 0.40, "above_func": "sqrt", "above_target": 0.60}},
    "STRAWBERRY": {{"base": 120, "I0": _MARKET_I0, "T": 100, "below_func": "sqrt", "below_target": 0.70, "above_func": "linear", "above_target": 1.60}},
    "MELON": {{"base": 250, "I0": _MARKET_I0, "T": 300, "below_func": "log", "below_target": 0.20, "above_func": "sq", "above_target": 3.60}},
    "EGG": {{"base": 50, "I0": _MARKET_I0, "T": 332, "below_func": "hinge", "below_target": 0.40, "above_func": "log", "above_target": 0.20}},
    "MILK": {{"base": 160, "I0": _MARKET_I0, "T": 122, "below_func": "sqrt", "below_target": 0.60, "above_func": "linear", "above_target": 1.60}},
    "WOOL": {{"base": 200, "I0": _MARKET_I0, "T": 105, "below_func": "log", "below_target": 0.20, "above_func": "sq", "above_target": 3.20}},
    "FERTILIZER": {{"base": 100, "I0": _MARKET_I0, "T": 200, "below_func": "linear", "below_target": 0.40, "above_func": "linear", "above_target": 0.40}},
}}

_SHOPS = {{
    "BAKERY": ["EGG", "WHEAT"],
    "PIZZA_SHOP": ["MILK", "TOMATO", "WHEAT"],
    "BRUNCH_SPOT": ["EGG", "WHEAT", "STRAWBERRY"],
    "YARN_STORE": ["WOOL"],
    "ICE_CREAM_SHOP": ["STRAWBERRY", "MILK", "WHEAT"],
    "PET_CAFE": ["CARROT"],
    "SMOOTHIE_SHOP": ["STRAWBERRY", "MILK"],
    "FARMERS_MARKET": ["WHEAT", "CARROT", "TOMATO", "STRAWBERRY"],
}}

_TC_PRODUCTS = [p for p in _MARKET_PARAMS if p != "FERTILIZER"]


def _shape(func, x, capacity=None):
    x = max(0.0, x)
    if func == "linear":
        return x
    if func == "sq":
        return x * x
    if func == "sqrt":
        return math.sqrt(x)
    if func == "log":
        return math.log(1.0 + x)
    if func == "hinge":
        if not capacity or capacity <= 0:
            return x
        u = x / capacity
        return u + _HINGE_GAIN * max(0.0, u - 1.0) ** 2
    return x


def _market_price(item, inventory):
    p = _MARKET_PARAMS[item]
    base, equilibrium, capacity = p["base"], p["I0"], p["T"]
    if inventory < equilibrium:
        func = p["below_func"]
        amplitude = p["below_target"] * base / _shape(func, capacity, capacity)
        price = base + amplitude * _shape(func, equilibrium - inventory, capacity)
    else:
        func = p["above_func"]
        amplitude = p["above_target"] * base / _shape(func, capacity, capacity)
        price = base - amplitude * _shape(func, inventory - equilibrium, capacity)
    return max(_PRICE_FLOOR, int(round(price)))


# ── NPC demand (per-step) ────────────────────────────────────────────────────
_SHOP_INTERVAL = 4
_CENTER_INTERVAL = 24


def _npc_step_demand(unlocked_shops, step):
    demand = {{}}
    if step % _SHOP_INTERVAL == 0:
        for shop_name in unlocked_shops:
            products = _SHOPS.get(shop_name)
            if not products:
                continue
            mult = 2 if len(products) == 1 else 1
            for item in products:
                demand[item] = demand.get(item, 0) + mult
    if step % _CENTER_INTERVAL == 0:
        for item in _TC_PRODUCTS:
            demand[item] = demand.get(item, 0) + 1
    return demand


# ── opponent supply tracker ──────────────────────────────────────────────────
def _median(values):
    ordered = sorted(values)
    count = len(ordered)
    if not count:
        return 0.0
    middle = count // 2
    if count % 2:
        return float(ordered[middle])
    return 0.5 * (ordered[middle - 1] + ordered[middle])


class _SupplyTracker:
    def __init__(self, horizon=6):
        self.horizon = max(1, int(horizon))
        self._prev_inv = None
        self._prev_step = None
        self._our_pending = {{}}
        self._batches = {{}}

    def observe(self, obs_data):
        inventory = obs_data["market_inventory"]
        step = obs_data["step"]
        unlocked_shops = obs_data["unlocked_shops"]
        if self._prev_inv is not None and self._prev_step is not None:
            drain = _npc_step_demand(unlocked_shops, self._prev_step)
            for product in sorted(inventory):
                moved = inventory[product] - self._prev_inv.get(product, 0)
                opponent = moved + drain.get(product, 0) - self._our_pending.get(product, 0)
                history = self._batches.setdefault(product, [])
                history.append(max(0, opponent))
                if len(history) > self.horizon:
                    del history[:-self.horizon]
        self._prev_inv = dict(inventory)
        self._prev_step = step
        self._our_pending = {{}}

    def record_our_orders(self, orders):
        pending = {{}}
        for order in orders:
            if isinstance(order, list) and len(order) >= 3 and order[0] == "SELL":
                try:
                    pending[order[1]] = pending.get(order[1], 0) + int(order[2])
                except (TypeError, ValueError):
                    continue
        self._our_pending = pending

    def predicted_units(self, product):
        history = self._batches.get(product)
        if not history:
            return None
        return int(round(_median(history)))


# ── sell logic ───────────────────────────────────────────────────────────────
_SELL_FLOOR = {{"CARROT": 5, "STRAWBERRY": 8, "EGG": 5, "MILK": 15, "WOOL": 20, "FERTILIZER": 10}}
_LIQ_FLOOR = 5
_AVERAGE_RULE = True
_SAFETY_CONST = 4
_SAFETY_MIN = 1
_SAFETY_MAX = 8
_SHED_GUARD = 90
_LIQ_STEP = 690
_PULL_FORWARD_BEFORE = 336
_OVERLAY_PRODUCTS = ("STRAWBERRY",)


def _safety_units(product, tracker):
    if tracker is None:
        return _SAFETY_CONST
    predicted = tracker.predicted_units(product)
    if predicted is None:
        return _SAFETY_CONST
    return max(_SAFETY_MIN, min(_SAFETY_MAX, int(predicted)))


def _sell_batch_size(product, stock, inventory, safety, floor, hard_floor):
    sell_units = 0
    batch_total = 0
    while sell_units < stock:
        unit_price = _market_price(product, inventory + sell_units + safety)
        if unit_price <= hard_floor:
            break
        if unit_price <= floor:
            if not _AVERAGE_RULE:
                break
            if (batch_total + unit_price) / (sell_units + 1) < floor:
                break
        sell_units += 1
        batch_total += unit_price
    return sell_units


# ── tile recovery ────────────────────────────────────────────────────────────
_TILE_OPS = {{"WATER", "PLANT", "DIG", "HARVEST", "FERTILIZE",
             "BUILD_COOP", "BUILD_PASTURE", "FEED", "CARE", "COLLECT_FERTILIZER"}}


def _tile_valid(op, tile):
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


def _recover_tile_actions(farm, farmer_a, hands_a):
    tiles = farm["tiles"]
    farmer_pos = farm.get("farmer", [0, 0])
    hand_positions = farm.get("hands", [])
    all_actions = [farmer_a] + list(hands_a)
    positions = [farmer_pos] + list(hand_positions)
    for i, action in enumerate(all_actions):
        if i >= len(positions):
            break
        if not (isinstance(action, list) and action):
            continue
        op = action[0]
        if op not in _TILE_OPS:
            continue
        x, y = positions[i][0], positions[i][1]
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


# ── overlay agent ────────────────────────────────────────────────────────────
_tracker = None
_last_step = None


def _parse_obs(obs):
    player = int(obs.get("player", 0))
    farms = obs.get("farms", [])
    mine = farms[player] if player < len(farms) else {{}}
    private = obs.get("private", {{}}) or {{}}
    market = obs.get("market", {{}}) or {{}}
    town = obs.get("town", {{}}) or {{}}
    return {{
        "step": int(obs.get("step", 0)),
        "player": player,
        "farm": mine,
        "shed": dict(private.get("shed", {{}})),
        "market_inventory": {{k: int(v) for k, v in (market.get("inventory", {{}}) or {{}}).items()}},
        "unlocked_shops": list(town.get("unlocked_shops", ()) or ()),
    }}


def agent(obs, configuration=None):
    global _tracker, _last_step

    step = obs.get("step", 0) if hasattr(obs, "get") else int(getattr(obs, "step", 0))

    if _last_step is None or step <= _last_step:
        _tracker = _SupplyTracker(6)
    _last_step = step

    parsed = _parse_obs(obs)
    _tracker.observe(parsed)

    if 0 <= step < _N:
        tape_action = _STREAM[step]
    else:
        tape_action = {{"farmer": ["PASS"], "hands": [], "market": []}}

    tape_market = tape_action.get("market", []) or []
    kept = list(tape_market)

    if step < _PULL_FORWARD_BEFORE:
        our_sells = []
        shed = parsed["shed"]
        shed_total = sum(int(v) for v in shed.values())
        for product in _OVERLAY_PRODUCTS:
            stock = int(shed.get(product, 0))
            if stock <= 0:
                continue
            inventory = int(parsed["market_inventory"].get(product, 0))
            liquidate = (step >= _LIQ_STEP) or (shed_total >= _SHED_GUARD)
            if liquidate:
                floor = _LIQ_FLOOR
                safety = 0
            else:
                floor = int(_SELL_FLOOR.get(product, 5))
                safety = _safety_units(product, _tracker)
            n = _sell_batch_size(product, stock, inventory, safety, floor, _LIQ_FLOOR)
            if n > 0:
                our_sells.append(["SELL", product, int(n)])
    else:
        our_sells = []

    combined = kept + our_sells

    _tracker.record_our_orders(
        [o for o in combined if isinstance(o, list) and o and o[0] == "SELL"])

    farmer_a = list(tape_action.get("farmer", ["PASS"]))
    hands_a = [list(h) for h in tape_action.get("hands", [])]

    farm = parsed["farm"]
    farmer_a, hands_a = _recover_tile_actions(farm, farmer_a, hands_a)

    return {{
        "farmer": farmer_a,
        "hands": hands_a,
        "market": combined,
    }}
'''


def build(team: str, package: bool) -> Path:
    rec_path = DERIVED / f"s6_step1_reconstruction_{team}.json"
    if not rec_path.exists():
        raise SystemExit(f"reconstruction not found: {rec_path}")
    rec = json.loads(rec_path.read_text())
    stream = rec["stream"]
    sha = _sha256(stream)
    n_steps = len(stream)
    prod_agr = rec["prod_modal_share_mean"]
    market_agr = rec["market_modal_share_mean"]

    stream_json = json.dumps(stream, separators=(",", ":"))
    if '"""' in stream_json or stream_json.endswith("\\"):
        raise SystemExit("stream JSON contains a triple-quote or ends with backslash")

    out_dir = (ROOT / "baselines" / date.today().isoformat() / "tape_submissions"
               / f"overlay_{team}")
    out_dir.mkdir(parents=True, exist_ok=True)
    _assert_gitignored(out_dir)

    main_path = out_dir / "main.py"
    main_path.write_text(MAIN_TEMPLATE.format(
        team=team, n_traces=rec["n_traces"], prod_agr=prod_agr, market_agr=market_agr,
        n_steps=n_steps, sha256=sha, stream_json=stream_json, n_recovery_rules=6,
    ), encoding="utf-8")

    provenance = {
        "artifact": "reconstruction + market overlay + tile recovery (§7.2 component (i))",
        "donor_team": team,
        "reconstruction_stream_sha256": sha,
        "n_steps": n_steps,
        "cross_trace_agreement": {"production": prod_agr, "market": market_agr},
        "overlays": {
            "market": "augment mode, STRAWBERRY only, sell-ahead controller, "
                      f"pull_forward_before_step=336",
            "tile_recovery": "§7.2 component (i): 6 recovery rules for desync tile actions",
        },
    }
    (out_dir / "provenance.json").write_text(
        json.dumps(provenance, indent=2), encoding="utf-8")

    from harness.checkpoint import agent_fingerprint
    fingerprint = agent_fingerprint(str(main_path))
    manifest = {
        "version": f"overlay_{team}",
        "artifact": "reconstruction + overlays",
        "fingerprint": fingerprint,
        "reconstruction_stream_sha256": sha,
    }
    (out_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")

    print(f"wrote {main_path} ({main_path.stat().st_size:,} bytes)")
    print(f"  team={team}  n_steps={n_steps}  sha256={sha}")

    if package:
        def _make_tar():
            import gzip as _gzip
            import io
            tar_buf = io.BytesIO()
            with tarfile.open(fileobj=tar_buf, mode="w") as tf:
                info = tarfile.TarInfo(name="main.py")
                data = main_path.read_bytes()
                info.size = len(data)
                info.mtime = 0
                info.uid = info.gid = 0
                info.uname = info.gname = ""
                tf.addfile(info, io.BytesIO(data))
            tar_bytes = tar_buf.getvalue()
            out = io.BytesIO()
            with _gzip.GzipFile(fileobj=out, mode="wb", mtime=0) as gz:
                gz.write(tar_bytes)
            return out.getvalue()

        tar_bytes_1 = _make_tar()
        tar_bytes_2 = _make_tar()
        sha_1 = hashlib.sha256(tar_bytes_1).hexdigest()
        sha_2 = hashlib.sha256(tar_bytes_2).hexdigest()
        tar_path = out_dir / "submission.tar.gz"
        tar_path.write_bytes(tar_bytes_1)
        print(f"packaged {tar_path} ({tar_path.stat().st_size:,} bytes)")
        _assert_gitignored(tar_path)
        if sha_1 != sha_2:
            print(f"  ⚠️ archive sha256 mismatch: {sha_1} vs {sha_2}")
        else:
            print(f"  archive sha256 (two-filename check): {sha_1}")

    return main_path


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--team", default="ReCurSiON")
    ap.add_argument("--package", action="store_true")
    args = ap.parse_args()
    build(args.team, args.package)


if __name__ == "__main__":
    main()
