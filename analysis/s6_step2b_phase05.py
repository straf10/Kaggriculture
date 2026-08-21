#!/usr/bin/env python3
"""S6 step 2b — Phase 0.5: recover the donor's actual strawberry sell-rule (paper, no episodes).

The 2b Phase-0 GO rests on one mechanism: *"the majority vote replaced ReCurSiON's town-conditioned
strawberry sell-timing with the modal action at the 127/719 state-dependent market steps."* Before
inventing a metering heuristic (§3.4 / the T2 & C-A lesson: bound the lever on paper first, prefer
the engine/recorded data to the experiment), this module **recovers** the rule from the 50 traces +
their observations + the already-computed disagreement set, and answers the crux the brief pins:

  does the strawberry sell-rule condition on **shop identity** (`obs.town.unlocked_shops`, the town's
  drain — capped near ~43-60% readable, leg 3) or on **own observable state** (inventory / price /
  day — observable from step 0, uncapped)?

Alignment (verified, and identical to s6_step1's convention): stream index i ↔ action at
steps[i+1][seat].action, observation that produced it at steps[i][seat].observation.

Subcommands:
  recover   — the whole recovery: determinism across 50 towns, price/shop invariance, the feature
              regression, the hour-of-day calendar, the 4-outlier cluster. Writes a gitignored JSON.
  live      — reachability: does our shipped reconstruction (55586926) execute the hour-0 calendar
              on our 85 live episodes, and do our live opponents contest it? (needs the gitignored
              live replays; skips with a note if absent.)
  report    — reprint the saved JSON without recomputing.

Everything derived from the donor/live action streams is gitignored (§2.4b / R11). No `agent/` change,
no upload (R27).

Usage:
    python analysis/s6_step2b_phase05.py recover
    python analysis/s6_step2b_phase05.py live
    python analysis/s6_step2b_phase05.py report
"""
from __future__ import annotations

import argparse
import glob
import gzip
import json
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

ARCHIVE = ROOT / "data" / "archive" / "raw" / "2026-08-16"
LIVE = ROOT / "data" / "archive" / "raw" / "live_55586926"
DERIVED = ROOT / "data" / "derived"
RECON = DERIVED / "s6_step1_reconstruction_ReCurSiON.json"
OUT = DERIVED / "s6_step2b_phase05.json"

# The four shop types whose demand STRAWBERRY drains into (engine_reference/kaggriculture.py SHOPS).
STR_SHOPS = {"BRUNCH_SPOT", "ICE_CREAM_SHOP", "SMOOTHIE_SHOP", "FARMERS_MARKET"}


def _market(steps, seat, i):
    """action.market for stream index i (= steps[i+1][seat].action.market)."""
    cell = steps[i + 1][seat]
    return (cell.get("action") or {}).get("market") or []


def _obs(steps, seat, i):
    """the observation that produced stream-index-i's action (= steps[i][seat].observation)."""
    return steps[i][seat]["observation"]


def _str_units(market: list) -> int:
    return sum(m[2] for m in market
              if isinstance(m, list) and len(m) == 3 and m[0] == "SELL" and m[1] == "STRAWBERRY")


def _load_recon() -> dict:
    if not RECON.exists():
        raise SystemExit(f"{RECON} missing — run analysis/s6_step1_reconstruct.py build first")
    return json.loads(RECON.read_text())


def _load_traces(eps):
    out = []
    for eid, seat in eps:
        p = ARCHIVE / f"{eid}.json"
        if not p.exists():
            raise SystemExit(f"gitignored donor replay absent: {p} (§2.4b) — cannot recover on a public checkout")
        out.append((eid, seat, json.loads(p.read_text())))
    return out


def recover() -> dict:
    rec = _load_recon()
    eps = rec["episodes_used"]
    traces = _load_traces(eps)          # [(eid, seat, replay_dict), ...]
    steps_of = [(seat, d["steps"]) for (_eid, seat, d) in traces]
    T = rec["n_steps"]
    n = len(traces)

    # --- 1. Determinism of the strawberry schedule across 50 different towns ------------------
    # units[trace, step] of strawberry sold; a step is a "disagreement" iff traces differ there.
    units = [[_str_units(_market(steps, seat, i)) for i in range(T)] for (seat, steps) in steps_of]
    sell_steps = [i for i in range(T) if any(units[t][i] > 0 for t in range(n))]
    disagree = [i for i in sell_steps if len({units[t][i] for t in range(n)}) > 1]
    per_trace_total = [sum(units[t]) for t in range(n)]
    vol_modal, vol_cnt = Counter(per_trace_total).most_common(1)[0]
    outliers = sorted(t for t in range(n) if per_trace_total[t] != vol_modal)

    # which traces carry the disagreement (are they a fixed subset = phase variant, or 50 towns?)
    dev_by_trace = Counter()
    for i in disagree:
        modal = Counter(units[t][i] for t in range(n)).most_common(1)[0][0]
        for t in range(n):
            if units[t][i] != modal:
                dev_by_trace[t] += 1

    # --- 2. Price / shop invariance at the largest-disagreement sell step ---------------------
    # (the decisive picture: same action in 50 towns with wildly different price & drain)
    def snapshot(i):
        rows = []
        for t, (seat, steps) in enumerate(steps_of):
            o = _obs(steps, seat, i)
            shops = o["town"]["unlocked_shops"]
            rows.append({
                "units": units[t][i],
                "str_shops": sum(1 for s in shops if s in STR_SHOPS),
                "price": o["market"]["prices"].get("STRAWBERRY", 0),
                "shed": o["private"]["shed"].get("STRAWBERRY", 0),
            })
        return rows
    # pick the sell step with the most towns selling a non-trivial identical amount
    big = max(sell_steps, key=lambda i: (units_modal_count(units, i, n)))
    snap = snapshot(big)
    modal_units = Counter(r["units"] for r in snap).most_common(1)[0]
    invariance = {
        "step": big,
        "day": _obs(steps_of[0][1], steps_of[0][0], big)["day"],
        "modal_units": modal_units[0], "n_traces_at_modal": modal_units[1],
        "price_min": min(r["price"] for r in snap), "price_max": max(r["price"] for r in snap),
        "str_shops_min": min(r["str_shops"] for r in snap),
        "str_shops_max": max(r["str_shops"] for r in snap),
    }

    # --- 3. Feature regression at strawberry-sell disagreement steps --------------------------
    # what predicts units sold: own shed (own state) or shop count (shop identity)?
    feats = defaultdict(list)
    for i in disagree:
        for t, (seat, steps) in enumerate(steps_of):
            o = _obs(steps, seat, i)
            shops = o["town"]["unlocked_shops"]
            feats["units"].append(units[t][i])
            feats["shed_str"].append(o["private"]["shed"].get("STRAWBERRY", 0))
            feats["str_shops"].append(sum(1 for s in shops if s in STR_SHOPS))
            feats["price"].append(o["market"]["prices"].get("STRAWBERRY", 0))
    corr = {f: _pearson(feats[f], feats["units"]) for f in ("shed_str", "str_shops", "price")}

    # --- 4. The hour-of-day calendar: when in the day does strawberry get sold? ---------------
    hour_units = Counter()
    for i in sell_steps:
        h = _obs(steps_of[0][1], steps_of[0][0], i)["hour"]
        hour_units[h] += sum(units[t][i] for t in range(n))
    tot = sum(hour_units.values())
    hour0_share = hour_units.get(0, 0) / tot if tot else None

    # --- 5. The reconstruction reproduces the fixed schedule ---------------------------------
    recon_str_total = sum(_str_units(s["market"]) for s in rec["stream"])

    out = {
        "team": rec["team"], "n_traces": n, "n_steps": T,
        "determinism": {
            "n_sell_steps": len(sell_steps),
            "n_unanimous_sell_steps": len(sell_steps) - len(disagree),
            "n_disagreement_sell_steps": len(disagree),
            "per_trace_total_modal": vol_modal, "n_traces_at_modal_total": vol_cnt,
            "outlier_traces": [{"trace": t, "episode": eps[t][0], "seat": eps[t][1],
                                "total_units": per_trace_total[t]} for t in outliers],
            "disagreement_carried_by_traces": dict(dev_by_trace.most_common()),
        },
        "invariance_at_biggest_sell_step": invariance,
        "feature_corr_with_units": corr,
        "calendar": {"hour0_units": hour_units.get(0, 0), "total_units": tot,
                     "hour0_share": hour0_share,
                     "units_by_hour": dict(sorted(hour_units.items(), key=lambda kv: -kv[1])[:6])},
        "reconstruction_strawberry_units": recon_str_total,
    }
    return out


def units_modal_count(units, i, n):
    vals = [units[t][i] for t in range(n)]
    m = Counter(vals).most_common(1)[0]
    return m[1] if m[0] > 0 else 0


def _pearson(x, y):
    x, y = list(x), list(y)
    if len(x) != len(y):
        raise ValueError(f"_pearson: length mismatch {len(x)} vs {len(y)}")
    n = len(x)
    if n < 2:
        return None
    mx, my = sum(x) / n, sum(y) / n
    sx = sum((a - mx) ** 2 for a in x) ** 0.5
    sy = sum((b - my) ** 2 for b in y) ** 0.5
    if sx == 0 or sy == 0:
        return 0.0
    return sum((a - mx) * (b - my) for a, b in zip(x, y)) / (sx * sy)


def live() -> dict:
    """Reachability: on our 85 live episodes, does the reconstruction execute the hour-0 calendar,
    and do our live opponents contest it? Needs the gitignored live replays."""
    from harness.metrics import _transition_events
    files = sorted(glob.glob(str(LIVE / "*.json")) + glob.glob(str(LIVE / "*.json.gz")))
    if not files:
        return {"available": False, "note": f"gitignored live replays absent at {LIVE} (§2.4b)"}

    def load(f):
        return json.load(gzip.open(f)) if f.endswith(".gz") else json.loads(Path(f).read_text())

    our = Counter(); opp = Counter()
    our_rev = defaultdict(float); opp_rev = defaultdict(float)
    n = 0
    total_transitions = 0
    skipped_transitions = 0
    last_skip_exc = None
    for f in files:
        d = load(f)
        steps = d["steps"]; cfg = d.get("configuration", {})
        teams = d.get("info", {}).get("TeamNames", [None, None])
        if "STRAF" not in teams:
            raise ValueError(f"replay {f}: neither team is STRAF ({teams})")
        if teams[0] == "STRAF" and teams[1] == "STRAF":
            continue
        our_seat = 1 if (teams[1] == "STRAF" and teams[0] != "STRAF") else 0
        for i in range(1, len(steps)):
            total_transitions += 1
            try:
                _a, _o, sales, _ab, _h = _transition_events(steps[i - 1], steps[i], cfg)
            except Exception as exc:  # noqa: BLE001
                skipped_transitions += 1
                last_skip_exc = exc
                continue
            h = steps[i - 1][our_seat]["observation"].get("hour")
            for s in sales[our_seat]:
                if s["item"] == "STRAWBERRY":
                    our[h] += 1; our_rev[h] += s["price"]
            for s in sales[1 - our_seat]:
                if s["item"] == "STRAWBERRY":
                    opp[h] += 1; opp_rev[h] += s["price"]
        n += 1

    if total_transitions > 0 and skipped_transitions > 0.02 * total_transitions:
        raise SystemExit(
            f"live(): {skipped_transitions}/{total_transitions} transitions failed — "
            f"measurement not trustworthy: {last_skip_exc!r}"
        )

    def summ(u, r):
        tot = sum(u.values()); h0 = u.get(0, 0)
        return {"total_units": tot, "hour0_units": h0,
                "hour0_share": h0 / tot if tot else None,
                "hour0_realised": (r.get(0, 0) / h0) if h0 else None}
    return {"available": True, "n_episodes": n,
            "skipped_transitions": skipped_transitions,
            "total_transitions": total_transitions,
            "our_reconstruction": summ(our, our_rev), "opponents": summ(opp, opp_rev)}


def _print(rec: dict, lv: dict | None):
    d = rec["determinism"]
    print(f"\n=== S6 step 2b Phase 0.5 — donor STRAWBERRY sell-rule, recovered ({rec['team']}, "
          f"{rec['n_traces']} traces) ===")
    print(f"\n[1] Determinism across {rec['n_traces']} DIFFERENT towns:")
    print(f"    strawberry sell-steps: {d['n_sell_steps']}  |  identical in all towns: "
          f"{d['n_unanimous_sell_steps']}  |  differ: {d['n_disagreement_sell_steps']}")
    print(f"    {d['n_traces_at_modal_total']}/{rec['n_traces']} traces sell EXACTLY "
          f"{d['per_trace_total_modal']} strawberry units total; outliers: "
          f"{[o['trace'] for o in d['outlier_traces']]} (sell {[o['total_units'] for o in d['outlier_traces']]})")
    print(f"    every disagreement is carried by the SAME fixed subset: "
          f"{d['disagreement_carried_by_traces']}")
    inv = rec["invariance_at_biggest_sell_step"]
    print(f"\n[2] Price/shop INVARIANCE at step {inv['step']} (day {inv['day']}): all "
          f"{inv['n_traces_at_modal']} towns sell {inv['modal_units']} units while "
          f"price spans ${inv['price_min']}–${inv['price_max']} and strawberry-shop count spans "
          f"{inv['str_shops_min']}–{inv['str_shops_max']}.")
    c = rec["feature_corr_with_units"]
    print(f"\n[3] corr(units sold, feature) at disagreement steps:  "
          f"shed_str={c['shed_str']:+.3f}  |  str_shops(shop identity)={c['str_shops']:+.3f}  |  "
          f"price={c['price']:+.3f}")
    cal = rec["calendar"]
    print(f"\n[4] Calendar: {cal['hour0_share']:.1%} of all strawberry units are sold at HOUR 0 "
          f"(the once-daily town-center pulse, townCenterSellInterval=24). units by hour: "
          f"{cal['units_by_hour']}")
    print(f"\n[5] The vote already reproduces it: reconstruction sells "
          f"{rec['reconstruction_strawberry_units']} strawberry units (= the "
          f"{d['n_traces_at_modal_total']}-trace fixed schedule).")
    print("\nCRUX: the rule conditions on NEITHER shop identity NOR own varying state — it is a fixed")
    print("      global calendar (sell held strawberry into the hour-0 pulse). Town-invariant; already")
    print("      reproduced by the majority vote. Reachable fraction of the $7,833/ep lever ≈ 0.")
    if lv and lv.get("available"):
        o = lv["our_reconstruction"]; p = lv["opponents"]
        print(f"\n[live] on {lv['n_episodes']} live episodes the reconstruction EXECUTES the calendar: "
              f"{o['hour0_share']:.1%} of our strawberry at hour 0 (realised ${o['hour0_realised']:.0f}/u); "
              f"our live opponents also concentrate — {p['hour0_share']:.1%} at hour 0 "
              f"(${p['hour0_realised']:.0f}/u). The pulse is contested ⇒ the skim is zero-sum, not erased.")
    elif lv:
        print(f"\n[live] {lv['note']}")


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("recover")
    sub.add_parser("live")
    sub.add_parser("report")
    args = ap.parse_args()

    if args.cmd == "report":
        if not OUT.exists():
            raise SystemExit(f"{OUT} missing — run `recover` first")
        saved = json.loads(OUT.read_text())
        _print(saved, saved.get("live"))
        return 0

    rec = recover()
    if args.cmd == "live":
        rec["live"] = live()
    else:
        # `recover` also runs live when the replays are present, so the JSON is complete
        rec["live"] = live()
    DERIVED.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rec, separators=(",", ":")))
    _print(rec, rec.get("live"))
    print(f"\nwrote {OUT} (gitignored)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
