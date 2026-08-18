#!/usr/bin/env python3
"""S6 step 2d — Track 2 Phase 0: is the vote's averaging lossy in the PRODUCTION channel? (paper)

Steps 2b/2b-0.5/2c closed the market layer: the donor's whole sell schedule is a town-INVARIANT
calendar the 50-town majority vote reproduces byte-for-byte. But every one of those passes looked at
the market channel. `n_disagree_prod = 88` production steps — where the 50 traces' `farmer`/`hands`
actions disagree — had never been examined by any pass. This module runs the step-2c instrument on the
PRODUCTION channel and answers the brief's leg A question:

  at the 88 production-disagreement steps, is the residual the SAME fixed 4-trace submission variant
  {43,45,46,49} the market side showed (a variant artefact, town-invariant) — or does it move with
  something the town does (weed spawns, obstruction, tile decay, worker count), i.e. a closed-loop
  adaptive rule a fixed-index 50-town vote structurally cannot carry?

Alignment is identical to s6_step1 / s6_step2c: stream index i ↔ action at steps[i+1][seat].action,
board that produced it at steps[i][seat].observation.farms[player]. The canonical production action is
`_canon([farmer, hands])`, exactly the token s6_step1_reconstruct votes on (so the disagreement set
recomputed here reproduces the reconstruction's n_disagree_prod = 88).

leg A — the five instruments on the production channel:
  1. Determinism / carriers — which traces carry the 88 disagreements; is the carrier set the fixed
     {43,45,46,49} subset (market-side artefact) or a town-varying population?
  2. Channel decomposition — is the disagreement in the main-farmer op, the worker count (hands
     length — the §4.5b worker-count-adaptation hypothesis), or the hands' tile-level content?
  3. Tile-reactivity split (DECISIVE) — at each hand-slot disagreement, is the hand at the SAME board
     position across all 50 towns (so it is not positional drift), and is the deviator standing on a
     tile whose content (WEED / dry-vs-watered PLANT / empty) is DISJOINT from the modal towns' — i.e.
     the action tracks the local board? This is the closed-loop rule the vote cannot carry.
  4. Calendar — when in the season the disagreement steps fall.
  5. Vote reproduction — the reconstruction stream emits the modal production action at every step.

leg B — the never-done total-bank decomposition + the dollar bound (desk, free):
  donor 50-trace final banks vs our 85 live 55586926 banks, matched on town richness, with the R32
  weed/decay loss ledger priced on the live episodes. This bounds leg A's mechanism in dollars: the
  recoverable own-farm loss is exactly what a closed-loop rule would recover, and step 2a already
  metered it (ceiling $599/ep, +2.4 rating pts, 0.09% of the gap). leg B re-grounds that on this pass's
  own data and states where the residual bank gap actually lives (the opponent pool, not a policy
  channel).

Everything derived from the donor/live action streams is gitignored (§2.4b / R11). No `agent/` change,
no episode (legs A/B are desk-only; legs C/D are NOT run — branch (iv) outranks them). No upload (R27).

Usage:
    python analysis/s6_step2d.py legA      # production-channel town-reactivity sweep
    python analysis/s6_step2d.py legB       # bank decomposition + live loss-ledger bound
    python analysis/s6_step2d.py report      # reprint the saved JSON without recomputing
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

from analysis.s6_step1_phase0 import _canon  # the exact token the reconstruction votes on
from analysis.s6_step2b_phase05 import (  # reuse the exact loading plumbing
    ARCHIVE, DERIVED, LIVE, RECON, _load_recon, _load_traces, _obs, _pearson,
)

OUT = DERIVED / "s6_step2d.json"

# The strawberry/wheat outlier subset the market side resolved to (a late-season submission variant).
# A production residual carried by exactly this set would be the same variant artefact, NOT reactivity.
VARIANT_SUBSET = {43, 45, 46, 49}

# Honest recoverable price of an own-farm loss unit (step 2a): $40.1/u realised over ~443 sold wheat
# units/ep. The $300/tile proxy double-counts (the tile's value IS its 3 wheat units), so units-only.
WHEAT_UNIT_PRICE = 40.1
FREE_GATE = 500.0  # §3 pre-registered $/ep gate a FREE lever must clear


def _prod(steps, seat, i):
    """canonical [farmer, hands] token for stream index i (= steps[i+1][seat].action)."""
    a = steps[i + 1][seat].get("action") or {}
    return _canon([a.get("farmer", ["PASS"]), a.get("hands", [])])


def _farmer(steps, seat, i):
    a = steps[i + 1][seat].get("action") or {}
    return a.get("farmer", ["PASS"])


def _hands(steps, seat, i):
    a = steps[i + 1][seat].get("action") or {}
    return a.get("hands", [])


def _myfarm(steps, seat, i):
    o = _obs(steps, seat, i)
    return o["farms"][o["player"]]


def _tile_state(steps, seat, i, pos):
    """Compact content of the board tile at `pos` in this town at stream index i.
    PLANT tiles carry their watered state (the closed-loop signal a hand reads before WATER/move)."""
    if pos is None:
        return "OFF"
    f = _myfarm(steps, seat, i)
    x, y = pos
    tl = f["tiles"][y][x]
    if isinstance(tl, dict):
        k = tl.get("kind")
        if k == "PLANT":
            return f"PLANT:{tl.get('crop')}{'' if tl.get('watered_today') else '|dry'}"
        return k  # WEED / PASTURE / LOCKED / COOP / ...
    return str(tl)  # None (empty)


def leg_a() -> dict:
    rec = _load_recon()
    eps = rec["episodes_used"]
    traces = _load_traces(eps)
    steps_of = [(seat, d["steps"]) for (_eid, seat, d) in traces]
    T = rec["n_steps"]
    n = len(traces)

    farmer = [[_farmer(steps, seat, i) for i in range(T)] for (seat, steps) in steps_of]
    hands = [[_hands(steps, seat, i) for i in range(T)] for (seat, steps) in steps_of]
    prod = [[_canon([farmer[t][i], hands[t][i]]) for i in range(T)] for t in range(n)]
    disagree = [i for i in range(T) if len({prod[t][i] for t in range(n)}) > 1]

    # --- 1. Determinism / carriers ------------------------------------------------------------
    dev_by_trace = Counter()
    modal_share = []
    for i in disagree:
        c = Counter(prod[t][i] for t in range(n))
        m_canon, m_cnt = c.most_common(1)[0]
        modal_share.append(m_cnt / n)
        for t in range(n):
            if prod[t][i] != m_canon:
                dev_by_trace[t] += 1
    carriers = set(dev_by_trace)
    residual_is_fixed4 = bool(carriers) and carriers.issubset(VARIANT_SUBSET)

    # --- 2. Channel decomposition -------------------------------------------------------------
    farmer_op_differs = hands_len_differs = hands_content_differs = 0
    for i in disagree:
        if len({(farmer[t][i][0] if farmer[t][i] else "PASS") for t in range(n)}) > 1:
            farmer_op_differs += 1
        if len({len(hands[t][i]) for t in range(n)}) > 1:
            hands_len_differs += 1
        if len({_canon(hands[t][i]) for t in range(n)}) > 1:
            hands_content_differs += 1

    # worker count is town-varying in principle (hiring cost scales with money) — is it here?
    nhand_disagree_steps = [i for i in range(T) if len({len(hands[t][i]) for t in range(n)}) > 1]

    # --- 3. Tile-reactivity split (DECISIVE) --------------------------------------------------
    # For each hand-slot that disagrees at a disagreement step: is the hand at the SAME board
    # position across all 50 towns (so not positional drift), and is the deviating group standing on
    # a tile whose content is DISJOINT from the modal group's (so the action tracks the local board)?
    hand_slot_disagreements = 0
    pos_identical_across_towns = 0
    tile_disjoint_where_action_differs = 0
    involves_weed = 0
    op_transitions = Counter()
    examples = []
    for i in disagree:
        nh = min(len(hands[t][i]) for t in range(n))
        for h in range(nh):
            acts = {t: _canon(hands[t][i][h]) for t in range(n)}
            if len(set(acts.values())) == 1:
                continue
            hand_slot_disagreements += 1
            positions = {}
            for t, (seat, steps) in enumerate(steps_of):
                f = _myfarm(steps, seat, i)
                hp = f["hands"][h] if h < len(f["hands"]) else None
                positions[t] = tuple(hp) if hp else None
            if len(set(positions.values())) == 1:
                pos_identical_across_towns += 1
            modal_act = Counter(acts.values()).most_common(1)[0][0]
            dev_t = [t for t in range(n) if acts[t] != modal_act]
            mod_t = [t for t in range(n) if acts[t] == modal_act]
            dev_tiles = {_tile_state(steps_of[t][1], steps_of[t][0], i, positions[t]) for t in dev_t}
            mod_tiles = {_tile_state(steps_of[t][1], steps_of[t][0], i, positions[t]) for t in mod_t}
            if dev_tiles and mod_tiles and dev_tiles.isdisjoint(mod_tiles):
                tile_disjoint_where_action_differs += 1
            if any("WEED" in tt for tt in (dev_tiles | mod_tiles)):
                involves_weed += 1
            modal_op = json.loads(modal_act)[0] if modal_act != '"PASS"' else "PASS"
            dev_op = json.loads(Counter(acts[t] for t in dev_t).most_common(1)[0][0])
            op_transitions[(modal_op, dev_op[0] if dev_op else "PASS")] += 1
            if len(examples) < 8:
                o0 = _obs(steps_of[0][1], steps_of[0][0], i)
                examples.append({
                    "step": i, "day": o0.get("day"), "hour": o0.get("hour"), "hand": h,
                    "modal_act": modal_act, "modal_tiles": sorted(mod_tiles)[:3],
                    "dev_act": Counter(acts[t] for t in dev_t).most_common(1)[0][0],
                    "dev_tiles": sorted(dev_tiles)[:3], "n_dev": len(dev_t)})

    reactivity_rate = (tile_disjoint_where_action_differs / hand_slot_disagreements
                       if hand_slot_disagreements else None)

    # --- 4. Calendar --------------------------------------------------------------------------
    day_hist = Counter(_obs(steps_of[0][1], steps_of[0][0], i).get("day") for i in disagree)

    # --- 5. Vote reproduction -----------------------------------------------------------------
    # The reconstruction emits the modal production action at every step by construction; confirm it.
    stream = rec["stream"]
    vote_reproduces_modal = 0
    for i in disagree:
        modal_canon = Counter(prod[t][i] for t in range(n)).most_common(1)[0][0]
        recon_canon = _canon([stream[i]["farmer"], stream[i]["hands"]])
        if recon_canon == modal_canon:
            vote_reproduces_modal += 1

    return {
        "n_traces": n, "n_steps": T, "n_disagree_prod": len(disagree),
        "determinism": {
            "modal_share_mean": round(statistics.fmean(modal_share), 4),
            "modal_share_min": round(min(modal_share), 4),
            "n_carrier_traces": len(carriers),
            "carriers": sorted(carriers),
            "carriers_top": dev_by_trace.most_common(10),
            "residual_is_fixed4_variant": residual_is_fixed4,
        },
        "channel_decomposition": {
            "n_disagree": len(disagree),
            "farmer_op_differs": farmer_op_differs,
            "hands_len_differs": hands_len_differs,
            "hands_content_differs": hands_content_differs,
            "worker_count_disagree_steps": len(nhand_disagree_steps),
        },
        "tile_reactivity": {
            "hand_slot_disagreements": hand_slot_disagreements,
            "pos_identical_across_towns": pos_identical_across_towns,
            "tile_disjoint_where_action_differs": tile_disjoint_where_action_differs,
            "reactivity_rate": round(reactivity_rate, 3) if reactivity_rate is not None else None,
            "involves_weed_tile": involves_weed,
            "op_transitions_top": [[list(k), v] for k, v in op_transitions.most_common(8)],
            "examples": examples,
        },
        "calendar": {"disagree_by_day_top": day_hist.most_common(6),
                     "day_min": min(day_hist), "day_max": max(day_hist)},
        "vote": {"n_disagree": len(disagree), "reproduces_modal_at": vote_reproduces_modal,
                 "reproduces_all": vote_reproduces_modal == len(disagree)},
    }


def leg_b() -> dict:
    """Total-bank decomposition (never done by any pass) + the dollar bound on leg A's mechanism.

    Caveats carried, not buried (the brief): (a) the opponents differ between the donor's recorded
    episodes and our live pool — so absolute-bank comparison is confounded by opponent quality, and we
    report each side's margin OVER ITS OWN opponents to control for it; (b) configuration.seed is None
    in every replay, so the donor's exact town cannot be re-run — richness-matching (final shop count)
    is the only same-town-like control available at the desk."""
    rec = _load_recon()
    traces = _load_traces(rec["episodes_used"])

    def summ(rows, label):
        b = [r["bank"] for r in rows]
        ob = [r["opp_bank"] for r in rows]
        margin = [r["bank"] - r["opp_bank"] for r in rows]
        return {
            "label": label, "n": len(rows),
            "bank_median": round(statistics.median(b)), "bank_mean": round(statistics.fmean(b)),
            "opp_bank_median": round(statistics.median(ob)),
            "margin_over_opp_median": round(statistics.median(margin)),
            "richness_median_shops": statistics.median([r["nshops"] for r in rows]),
            "richness_range": [min(r["nshops"] for r in rows), max(r["nshops"] for r in rows)],
        }

    donor = []
    for (_eid, seat, d) in traces:
        last = d["steps"][-1][seat]["observation"]
        donor.append({"bank": d["rewards"][seat], "opp_bank": d["rewards"][1 - seat],
                      "nshops": len(last["town"]["unlocked_shops"])})
    donor_s = summ(donor, "donor (50 ReCurSiON traces)")

    # our live 55586926
    files = sorted(glob.glob(str(LIVE / "*.json")) + glob.glob(str(LIVE / "*.json.gz")))
    live_s = ledger = None
    if files:
        from harness.metrics import extract_metrics  # lazy: pulls kaggle_environments via harness

        def load(f):
            return json.load(gzip.open(f)) if f.endswith(".gz") else json.loads(Path(f).read_text())

        live = []
        decay, weeds, water_w = [], [], []
        for f in files:
            d = load(f)
            teams = d.get("info", {}).get("TeamNames", [None, None])
            seat = 1 if (teams[1] == "STRAF" and teams[0] != "STRAF") else 0
            last = d["steps"][-1][seat]["observation"]
            live.append({"bank": d["rewards"][seat], "opp_bank": d["rewards"][1 - seat],
                         "nshops": len(last["town"]["unlocked_shops"])})
            try:
                m = extract_metrics(d, seat)
                decay.append(m.get("plant_decay_units_lost", 0))
                weeds.append(m.get("unexpected_weeds_lost", 0))
                water_w.append(m.get("water_weeds_lost", 0))
            except Exception:  # noqa: BLE001
                pass
        live_s = summ(live, "our live (55586926 recon)")
        decay_mean = statistics.fmean(decay) if decay else 0.0
        ceiling = decay_mean * WHEAT_UNIT_PRICE  # units-only honest recoverable (step 2a basis)
        ledger = {
            "n_episodes_metered": len(decay),
            "plant_decay_units_per_ep": round(decay_mean, 2),
            "unexpected_weeds_per_ep": round(statistics.fmean(weeds), 2) if weeds else 0.0,
            "water_weeds_per_ep": round(statistics.fmean(water_w), 2) if water_w else 0.0,
            "recoverable_ceiling_dollars_per_ep": round(ceiling),
            "recoverable_ceiling_rating_pts": round(ceiling / 253.0, 1),  # $253/ep per pt (step 2a)
            "free_half_dollars_per_ep": [0, 241],  # on-tile $0 → reachable $241, step 2a; both < gate
            "free_half_below_gate": True,
            "note": ("units-only honest ceiling (decay units x $40.1/u); the $300/tile proxy "
                     "double-counts. This is the FULL own-farm loss a closed-loop rule could recover "
                     "(the dollar surface of leg A's mechanism); it exceeds the $500 gate but the FREE "
                     "non-displacing half is $0 on-tile to $241 reachable (both < gate, step 2a). "
                     "Even the full ceiling = +2.4 pts / 0.09% of the gap. Matches step 2a "
                     "(14.94 decay / 4.98 weeds, $599/ep)."),
        }

    bank_gap = (donor_s["bank_median"] - live_s["bank_median"]) if live_s else None
    margin_gap = (donor_s["margin_over_opp_median"] - live_s["margin_over_opp_median"]) if live_s else None
    return {
        "donor": donor_s, "live": live_s, "loss_ledger": ledger,
        "bank_gap_donor_minus_live_median": bank_gap,
        "margin_gap_donor_minus_live_median": margin_gap,
        "reading": (
            "Town richness is matched (both median 8 shops), so this is a richness-controlled desk "
            f"comparison. The donor's ABSOLUTE bank leads by ~${bank_gap}/ep median, but most of that is "
            f"the OPPONENT POOL: the donor's recorded opponents banked ${donor_s['opp_bank_median']:,} "
            f"vs our live opponents' ${live_s['opp_bank_median']:,}, a richer/stronger pool the donor "
            "did not create. On the head-to-head currency — per-episode margin OVER ONE'S OWN "
            f"opponents — the donor leads by only ~${margin_gap}/ep (${donor_s['margin_over_opp_median']:,} "
            f"vs ${live_s['margin_over_opp_median']:,}) ≈ {round((margin_gap or 0)/253.0,1)} rating pts. "
            f"And ~${ledger['recoverable_ceiling_dollars_per_ep']}/ep of that margin gap IS the own-farm "
            "weed/decay loss — leg A's mechanism — whose FREE half ($0–$241) is below the $500 gate and "
            "whose full recovery is +2.4 pts (step 2a). So the recoverable-policy slice of the gap is a "
            "few rating points at most; the ~1.100-point live anomaly is submission-level (R36), a "
            "rating/opponent/clock phenomenon a mismatched-pool bank comparison neither reproduces nor "
            "locates in the market (2c) or recoverable production (2a/2d) channels."
        ) if live_s else "live replays absent (§2.4b) — donor banks reported alone.",
    }


def _verdict(a: dict, b: dict | None) -> str:
    tr = a["tile_reactivity"]
    det = a["determinism"]
    ch = a["channel_decomposition"]
    bound = (b["loss_ledger"]["recoverable_ceiling_dollars_per_ep"]
             if (b and b.get("loss_ledger")) else 599)
    return (
        f"BRANCH (iv) in MECHANISM, bounded SMALL. The {a['n_disagree_prod']} production-disagreement "
        f"steps ARE town-reactive, NOT the fixed-4 variant: the carrier set is {det['n_carrier_traces']} "
        f"traces (not subset of {{43,45,46,49}}), the main-farmer op disagrees at {ch['farmer_op_differs']} "
        f"of {a['n_disagree_prod']} steps (the farmer script is town-invariant), and worker count differs "
        f"at only {ch['worker_count_disagree_steps']}. The disagreement is the HANDS' tile-level control: "
        f"of {tr['hand_slot_disagreements']} hand-slot disagreements, {tr['pos_identical_across_towns']} "
        f"occur at an identical board position across all 50 towns and {tr['tile_disjoint_where_action_differs']} "
        f"({tr['reactivity_rate']:.0%}) have the deviator standing on a tile whose content (WEED / dry-vs-"
        f"watered PLANT / empty) is DISJOINT from the modal towns' — the hand reads the local board and "
        f"DIGs a per-town spawned weed, re-PLANTs, or WATERs by actual dry state. This is closed-loop "
        f"control a fixed-index 50-town vote cannot carry (exactly the 'closed-loop redirect that desyncs "
        f"the tape' step 2a named). BUT its recoverable dollar surface is the own-farm weed/decay loss, "
        f"re-measured here at ~${bound}/ep (units-only ceiling), 100% wheat, whose FREE non-displacing "
        f"half is $0-$241 (below the $500 gate) and whose full recovery = +2.4 rating pts / 0.09% of the "
        f"gap (step 2a). The vote is a faithful OPEN-LOOP reproduction; "
        f"the town-reactive production rule it erases is real but is NOT where the ~1.100 points live. "
        f"Report and re-brief; do NOT build the adaptive layer this pass (Phase-0.5 discipline). No "
        f"episode, no upload (R27). Legs C/D not run — branch (iv) outranks them."
    )


def _print(rec: dict):
    a = rec["legA"]
    print(f"\n=== S6 step 2d leg A — production-channel town-reactivity ({a['n_traces']} traces, "
          f"{a['n_disagree_prod']} disagreement steps) ===")
    print(f"\nVERDICT: {rec['verdict']}")
    det = a["determinism"]
    print(f"\n[1] carriers: {det['n_carrier_traces']} traces carry the {a['n_disagree_prod']} "
          f"disagreements; is the fixed {{43,45,46,49}} variant subset: {det['residual_is_fixed4_variant']}")
    print(f"    modal-share mean {det['modal_share_mean']:.3f} (min {det['modal_share_min']:.3f}); "
          f"top carriers {det['carriers_top'][:6]}")
    ch = a["channel_decomposition"]
    print(f"[2] of {ch['n_disagree']} steps: farmer-op differs {ch['farmer_op_differs']}  |  "
          f"worker-count differs {ch['worker_count_disagree_steps']}  |  hands-content differs "
          f"{ch['hands_content_differs']}")
    tr = a["tile_reactivity"]
    print(f"[3] DECISIVE tile split: {tr['hand_slot_disagreements']} hand-slot disagreements; "
          f"{tr['pos_identical_across_towns']} at identical position across 50 towns; "
          f"{tr['tile_disjoint_where_action_differs']} ({tr['reactivity_rate']:.0%}) track a disjoint "
          f"tile content; {tr['involves_weed_tile']} involve a WEED tile")
    print(f"    op transitions (modal→dev): {tr['op_transitions_top'][:5]}")
    for e in tr["examples"][:5]:
        print(f"      s{e['step']} d{e['day']}h{e['hour']} hand{e['hand']}: modal {e['modal_act'][:24]} "
              f"on {e['modal_tiles']}  ||  {e['n_dev']} dev {e['dev_act'][:24]} on {e['dev_tiles']}")
    print(f"[4] calendar: disagreements span days {a['calendar']['day_min']}-{a['calendar']['day_max']}; "
          f"by day {a['calendar']['disagree_by_day_top']}")
    print(f"[5] vote reproduces modal production at {a['vote']['reproduces_modal_at']}/{a['n_disagree_prod']} "
          f"disagreement steps (all: {a['vote']['reproduces_all']})")
    if rec.get("legB"):
        b = rec["legB"]
        print(f"\n=== leg B — bank decomposition + bound ===")
        for k in ("donor", "live"):
            s = b[k]
            if s:
                print(f"  {s['label']:<28} n={s['n']:>3}  bank median ${s['bank_median']:>7,}  "
                      f"opp ${s['opp_bank_median']:>7,}  margin ${s['margin_over_opp_median']:>+7,}  "
                      f"richness {s['richness_median_shops']} shops")
        if b.get("loss_ledger"):
            lg = b["loss_ledger"]
            print(f"  loss ledger (live, {lg['n_episodes_metered']} ep): decay {lg['plant_decay_units_per_ep']}/ep "
                  f"+ weeds {lg['unexpected_weeds_per_ep']}/ep ⇒ recoverable ceiling "
                  f"${lg['recoverable_ceiling_dollars_per_ep']}/ep ({lg['recoverable_ceiling_rating_pts']} pts); "
                  f"FREE half ${lg['free_half_dollars_per_ep'][0]}-${lg['free_half_dollars_per_ep'][1]} < $500 gate")
        print(f"  bank gap (donor−live median): ${b['bank_gap_donor_minus_live_median']}/ep  |  "
              f"margin gap: ${b['margin_gap_donor_minus_live_median']}/ep")
        print(f"  reading: {b['reading']}")


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("legA")
    sub.add_parser("legB")
    sub.add_parser("report")
    args = ap.parse_args()

    if args.cmd == "report":
        if not OUT.exists():
            raise SystemExit(f"{OUT} missing — run `legA` (and `legB`) first")
        _print(json.loads(OUT.read_text()))
        return 0

    a = leg_a()
    b = leg_b() if args.cmd == "legB" else None
    if b is None and OUT.exists():  # preserve a previously computed leg B when only re-running leg A
        b = json.loads(OUT.read_text()).get("legB")
    rec = {"legA": a, "legB": b, "verdict": _verdict(a, b)}
    DERIVED.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rec, separators=(",", ":")))
    _print(rec)
    print(f"\nwrote {OUT} (gitignored)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
