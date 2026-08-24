#!/usr/bin/env python3
"""S7 — Conditional agreement on the top-4 (docs/plans/conditional_agreement_top4.md).

§7.1 KILLED the top-4 *tape* extraction: a majority-vote reconstruction of any top-4 candidate is a
chimera (market_agr 0.64-0.86, and the tetsuya recon replayed at 59% median bank error). This pass
does NOT reopen tape extraction. It runs the plan's Phase 0 — a purely DESCRIPTIVE desk measurement
of whether the top-4's *rule* is extractable: at the many steps where a candidate's own traces
disagree with themselves, is the action **random**, or **predictable from a single visible state
variable**? No `agent/` change, no episode, no upload. Four legs, desk-only:

  leg0  reproduction tripwire — recompute cross-trace prod/market agreement per candidate; MUST match
        the 8 §7.1 numbers within +-0.01, else the pipeline has a bug (K1, STOP).
  leg1  channel decomposition — of the production disagreements, how many are in the main-farmer op,
        the worker count (len(hands)), or the hand-slot content? (s6_step2d instrument 2, per team.)
  leg2  conditional agreement (the core) — for each of 10 pre-declared, obs-visible state variables
        V1..V10, stratify traces by V at each step, measure modal share within stratum, aggregate.
        Three mandatory guards: (a) permutation null — report only the lift over shuffled labels;
        (b) minimum stratum size 3, report the excluded-step fraction; (c) split confirm — fit on
        {Ryo, tetsuya}, confirm on {Arman, Crop Dusta}.
  leg3  cross-match control (DECISIVE) — group traces by seed (same town). If two DIFFERENT top-4
        policies in the SAME town disagree about as much as ONE team with itself across DIFFERENT
        towns, there is no single town-reactive policy to extract, with any method (K3, STOP).

The pre-declared GO rule (§4) and the kill table (§8) are applied by `_verdict`. GO requires ALL of:
  1. some V gives lift >= +0.25 over the permutation null in one channel; and
  2. the conditional agreement reaches >= 0.80 absolute; and
  3. it repeats on the confirm pair with >= 60% of the fit lift; and
  4. V is obs-visible at decision time (true by construction for V1..V10); and
  5. the rule is legible (threshold/lookup on 1-2 variables — true by construction, single V).
Anything else is a useful STOP: it closes risk #2 (state-aliasing) with OUR OWN number.

Alignment (identical to s6_step1 / s6_step2d): stream index i <-> action steps[i+1][seat].action,
produced by the observation steps[i][seat].observation. Both farms are visible in `farms`.

Everything derived from competition action streams is gitignored (§2.4b / R11).

Usage:
    python analysis/s7_conditional_agreement.py leg0        # tripwire only
    python analysis/s7_conditional_agreement.py all          # legs 0-3 + verdict (default perms=200)
    python analysis/s7_conditional_agreement.py all --perms 50   # quick check
    python analysis/s7_conditional_agreement.py report       # reprint saved JSON
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

os.environ.setdefault("S6_ARCHIVE_DATE", "2026-08-21")
from analysis.s6_step1_phase0 import (  # noqa: E402
    ARCHIVE, DERIVED, LIVE_ENGINE, _agreement_for_traces, _canon, _reload_streams,
)

SELECTION = DERIVED / "s7_leg_a_selection.json"
OUT = DERIVED / "s7_conditional_agreement.json"

# §Leg0 tripwire — the 8 numbers §7.1 measured; the pipeline MUST reproduce these within +-0.01.
LEG0_TARGETS = {
    "Ryo Hasegawa":     {"prod": 0.331, "market": 0.692},
    "tetsuya":          {"prod": 0.374, "market": 0.856},
    "Arman Tuganbaev":  {"prod": 0.247, "market": 0.777},
    "Crop Dusta":       {"prod": 0.269, "market": 0.636},
}
LEG0_TOL = 0.01

# §Leg2(γ) pre-declared split — fit on these two, confirm on the other two, before any number is seen.
FIT_PAIR = ("Ryo Hasegawa", "tetsuya")
CONFIRM_PAIR = ("Arman Tuganbaev", "Crop Dusta")

# §4 GO thresholds
MIN_LIFT = 0.25          # (1) lift over permutation null, in one channel
MIN_ABS_AGREEMENT = 0.80  # (2) absolute conditional agreement
CONFIRM_FRAC = 0.60      # (3) fraction of the fit lift the confirm pair must reproduce
MIN_STRATUM = 3          # §Leg2(β) minimum stratum size

# The 10 pre-declared variables (§Leg2). Each must be visible from OUR obs at decision time; the
# `source` documents where. All are computed from steps[i][seat].observation (the board that produced
# the action at steps[i+1]).
V_DECL = {
    "V1_tile_at_farmer":   "farms[me].tiles at the farmer's own position",
    "V2_weed_count":       "count of WEED tiles on farms[me]",
    "V3_unwatered_plants": "count of un-watered PLANT tiles on farms[me] (binned)",
    "V4_day":              "step->day (0-29): a TIME control — identical across index-aligned traces",
    "V4_hour":             "step->hour (0-23): a TIME control — identical across index-aligned traces",
    "V5_money":            "farms[me].money (binned)",
    "V6_shed_fill":        "sum(private.shed)/shedCapacity (binned)",
    "V7_str_price":        "market.prices.STRAWBERRY (binned)",
    "V8_shops":            "town.unlocked_shops (sorted tuple — presence/absence per type)",
    "V9_opp_exposure":     "farms[1-me]: (planted binned, animals binned)",
    "V10_hands":           "len(farms[me].hands) — worker count",
}


# --------------------------------------------------------------------------------------------------
# stream + feature extraction
# --------------------------------------------------------------------------------------------------
def _bin(x: float, edges: tuple) -> int:
    """Right-open bucket index for x given ascending edges; -1 below the first edge is impossible
    (edges start at 0). Returns len(edges) for the open top bucket."""
    i = 0
    for e in edges:
        if x < e:
            return i
        i += 1
    return i


MONEY_EDGES = (100, 300, 600, 1000, 2000, 4000, 8000)
UNWAT_EDGES = (1, 3, 6, 10, 20, 40)          # 0, 1-2, 3-5, 6-9, 10-19, 20-39, 40+
SHED_FRAC_EDGES = (0.1, 0.25, 0.5, 0.75, 0.9, 1.0)
STRPRICE_EDGES = (80, 120, 140, 160, 180, 220)
OPP_PLANT_EDGES = (10, 25, 40, 55, 70)
OPP_ANIM_EDGES = (3, 6, 10, 15)


def _tile_code(tile) -> str:
    """Compact content bucket of one board tile (V1's alphabet)."""
    if not isinstance(tile, dict):
        return "EMPTY"
    k = tile.get("kind")
    if k == "PLANT":
        return "PLANT_WATERED" if tile.get("watered_today") else "PLANT_DRY"
    if k == "PASTURE":
        return "ANIMAL"
    if k == "WEED":
        return "WEED"
    return k or "EMPTY"


def _farm_scan(f: dict) -> tuple[int, int]:
    """(#PLANT, #WEED, #un-watered PLANT, #PASTURE) in one pass — returns (weeds, unwatered)."""
    weeds = unwat = 0
    for row in f["tiles"]:
        for tl in row:
            if isinstance(tl, dict):
                k = tl.get("kind")
                if k == "WEED":
                    weeds += 1
                elif k == "PLANT" and not tl.get("watered_today"):
                    unwat += 1
    return weeds, unwat


def _opp_scan(f: dict) -> tuple[int, int]:
    """(#PLANT, #PASTURE) on the opponent farm — V9 exposure."""
    npl = nan = 0
    for row in f["tiles"]:
        for tl in row:
            if isinstance(tl, dict):
                k = tl.get("kind")
                if k == "PLANT":
                    npl += 1
                elif k == "PASTURE":
                    nan += 1
    return npl, nan


def _features_at(o: dict, shed_cap: float) -> dict:
    """The 10 pre-declared V codes for one observation (a step's board for one seat)."""
    me = o["player"]
    f = o["farms"][me]
    opp = o["farms"][1 - me]
    fx, fy = f["farmer"]
    weeds, unwat = _farm_scan(f)
    shed = o.get("private", {}).get("shed", {}) or {}
    shed_fill = (sum(shed.values()) / shed_cap) if shed_cap else 0.0
    opp_pl, opp_an = _opp_scan(opp)
    prices = (o.get("market", {}) or {}).get("prices", {}) or {}
    return {
        "V1_tile_at_farmer": _tile_code(f["tiles"][fy][fx]),
        "V2_weed_count": weeds,
        "V3_unwatered_plants": _bin(unwat, UNWAT_EDGES),
        "V4_day": o.get("day"),
        "V4_hour": o.get("hour"),
        "V5_money": _bin(f.get("money", 0), MONEY_EDGES),
        "V6_shed_fill": _bin(shed_fill, SHED_FRAC_EDGES),
        "V7_str_price": _bin(prices.get("STRAWBERRY", 0), STRPRICE_EDGES),
        "V8_shops": tuple(sorted(o.get("town", {}).get("unlocked_shops", []) or [])),
        "V9_opp_exposure": (_bin(opp_pl, OPP_PLANT_EDGES), _bin(opp_an, OPP_ANIM_EDGES)),
        "V10_hands": len(f.get("hands", [])),
    }


def _load_trace(eid: int, seat: int) -> dict:
    """Per-trace: prod/market action tokens (index i = steps[i+1] action) and V codes (obs steps[i]).
    Length T = len(steps)-1 to match _seat_streams / _agreement_for_traces exactly."""
    d = json.loads((ARCHIVE / f"{eid}.json").read_text())
    steps = d["steps"]
    shed_cap = float(d.get("configuration", {}).get("shedCapacity") or 100.0)
    T = len(steps) - 1
    prod, market = [], []
    feats = {k: [] for k in V_DECL}
    farmer, hands = [], []
    for i in range(T):
        act = steps[i + 1][seat].get("action") or {}
        fa = act.get("farmer", ["PASS"])
        ha = act.get("hands", [])
        farmer.append(fa)
        hands.append(ha)
        prod.append(_canon([fa, ha]))
        market.append(_canon(act.get("market", [])))
        fv = _features_at(steps[i][seat]["observation"], shed_cap)
        for k in V_DECL:
            feats[k].append(fv[k])
    return {"eid": eid, "seat": seat, "T": T,
            "prod": prod, "market": market, "farmer": farmer, "hands": hands, "feats": feats}


# --------------------------------------------------------------------------------------------------
# candidate loading (drives off §7.1's saved per-submission trace sets)
# --------------------------------------------------------------------------------------------------
def _load_selection() -> dict:
    if not SELECTION.exists():
        raise SystemExit(f"{SELECTION} missing — run analysis/s7_leg_a_donor_select.py select first")
    return json.loads(SELECTION.read_text())


def _candidates() -> dict[str, dict]:
    """{team: {submission_id, episodes:[(eid,seat)...]}} from §7.1's selection (one submission each,
    already deduped to 15 distinct (episode_id, seat) traces)."""
    sel = _load_selection()
    out = {}
    for _key, rec in sel["per_candidate"].items():
        eps = [tuple(e) for e in rec["episodes_used"]]
        assert len(eps) == len(set(eps)), f"{rec['team']}: episodes_used has duplicate (eid,seat)"
        out[rec["team"]] = {"submission_id": rec["submission_id"], "episodes": eps}
    return out


# --------------------------------------------------------------------------------------------------
# leg 0 — reproduction tripwire
# --------------------------------------------------------------------------------------------------
def leg0(cands: dict) -> dict:
    rows = {}
    ok = True
    for team, c in cands.items():
        traces = []
        for eid, seat in c["episodes"]:
            p, m, _ = _reload_streams(eid, seat)
            traces.append((p, m))
        a = _agreement_for_traces(traces)
        tgt = LEG0_TARGETS[team]
        dp = abs(a["prod_agreement"] - tgt["prod"])
        dm = abs(a["market_agreement"] - tgt["market"])
        passed = dp <= LEG0_TOL and dm <= LEG0_TOL
        ok = ok and passed
        rows[team] = {
            "n_traces": a["n_traces"], "n_steps": a["n_steps"],
            "prod": round(a["prod_agreement"], 4), "market": round(a["market_agreement"], 4),
            "target_prod": tgt["prod"], "target_market": tgt["market"],
            "delta_prod": round(dp, 4), "delta_market": round(dm, 4), "pass": passed,
        }
    return {"pass": ok, "tolerance": LEG0_TOL, "candidates": rows}


# --------------------------------------------------------------------------------------------------
# leg 1 — channel decomposition of the production disagreements
# --------------------------------------------------------------------------------------------------
def leg1(traces_by_team: dict) -> dict:
    out = {}
    for team, traces in traces_by_team.items():
        n = len(traces)
        T = min(t["T"] for t in traces)
        disagree = farmer_op = hands_len = hands_content = 0
        for i in range(T):
            toks = {t["prod"][i] for t in traces}
            if len(toks) <= 1:
                continue
            disagree += 1
            if len({(t["farmer"][i][0] if t["farmer"][i] else "PASS") for t in traces}) > 1:
                farmer_op += 1
            if len({len(t["hands"][i]) for t in traces}) > 1:
                hands_len += 1
            if len({_canon(t["hands"][i]) for t in traces}) > 1:
                hands_content += 1
        frac = (lambda x: round(x / disagree, 3) if disagree else None)
        out[team] = {
            "n_traces": n, "n_steps": T, "n_disagree_prod": disagree,
            "farmer_op_differs": farmer_op, "farmer_op_frac": frac(farmer_op),
            "worker_count_differs": hands_len, "worker_count_frac": frac(hands_len),
            "hands_content_differs": hands_content, "hands_content_frac": frac(hands_content),
        }
    return out


# --------------------------------------------------------------------------------------------------
# leg 2 — conditional agreement (the core), with permutation null + min-stratum + split confirm
# --------------------------------------------------------------------------------------------------
def _codes(values: list) -> np.ndarray:
    """Factorize an arbitrary list of hashables to a small int array (order-stable)."""
    idx: dict = {}
    out = np.empty(len(values), dtype=np.int32)
    for i, v in enumerate(values):
        c = idx.get(v)
        if c is None:
            c = idx[v] = len(idx)
        out[i] = c
    return out


def _conditional_agreement(V: np.ndarray, A: np.ndarray, min_size: int = MIN_STRATUM):
    """V, A are int arrays of shape (n_traces, T). Per step: stratify traces by V value, drop strata
    with < min_size, and average (over kept strata, size-weighted) the modal share of A within a
    stratum. Aggregate = mean over steps that keep >= 1 valid stratum. Returns (agreement, incl_frac).
    """
    n, T = V.shape
    total = 0.0
    included = 0
    for t in range(T):
        vt = V[:, t]
        at = A[:, t]
        groups: dict = defaultdict(list)
        for tr in range(n):
            groups[int(vt[tr])].append(int(at[tr]))
        valid = 0
        ssum = 0
        for acts in groups.values():
            if len(acts) >= min_size:
                valid += len(acts)
                ssum += max(Counter(acts).values())
        if valid >= min_size:
            total += ssum / valid
            included += 1
    return (total / included if included else None), (included / T if T else 0.0)


def _null_agreement(V: np.ndarray, A: np.ndarray, perms: int, rng, min_size: int = MIN_STRATUM):
    """Mean conditional agreement under `perms` independent per-step shuffles of the V labels — the
    same stratification with the V<->trace link broken, so the size-inflation is preserved but any
    real V->action signal is destroyed. Returns (null_mean, null_std)."""
    n, T = V.shape
    vals = np.empty(perms, dtype=np.float64)
    for r in range(perms):
        order = np.argsort(rng.random((n, T)), axis=0)      # independent column permutations
        Vsh = np.take_along_axis(V, order, axis=0)
        a, _ = _conditional_agreement(Vsh, A, min_size)
        vals[r] = a if a is not None else np.nan
    finite = vals[np.isfinite(vals)]
    return (float(finite.mean()) if finite.size else None,
            float(finite.std()) if finite.size else None)


def _leg2_for_team(traces: list, perms: int, seed: int) -> dict:
    """Per-team, per-variable, per-channel: raw conditional agreement, permutation-null mean, lift,
    excluded-step fraction. Actions and V codes are index-aligned across traces at the min length."""
    n = len(traces)
    T = min(t["T"] for t in traces)
    rng = np.random.default_rng(seed)
    A_prod = np.stack([_codes(t["prod"][:T]) for t in traces])
    A_mkt = np.stack([_codes(t["market"][:T]) for t in traces])
    channels = {"prod": A_prod, "market": A_mkt}
    res = {}
    for vname in V_DECL:
        Vcode = np.stack([_codes(t["feats"][vname][:T]) for t in traces])
        n_strata_mean = float(np.mean([len(set(Vcode[:, t])) for t in range(T)]))
        per_ch = {}
        for cname, A in channels.items():
            raw, incl = _conditional_agreement(Vcode, A)
            null_mean, null_std = _null_agreement(Vcode, A, perms, rng)
            lift = (raw - null_mean) if (raw is not None and null_mean is not None) else None
            per_ch[cname] = {
                "agreement": round(raw, 4) if raw is not None else None,
                "null_mean": round(null_mean, 4) if null_mean is not None else None,
                "null_std": round(null_std, 4) if null_std is not None else None,
                "lift": round(lift, 4) if lift is not None else None,
                "included_frac": round(incl, 3),
                "excluded_frac": round(1 - incl, 3),
            }
        res[vname] = {"mean_strata_per_step": round(n_strata_mean, 2), "channels": per_ch}
    return {"n_traces": n, "n_steps": T, "perms": perms, "variables": res}


def leg2(traces_by_team: dict, perms: int) -> dict:
    out = {}
    for si, (team, traces) in enumerate(traces_by_team.items()):
        print(f"  leg2: {team} ({len(traces)} traces, perms={perms}) ...", flush=True)
        out[team] = _leg2_for_team(traces, perms, seed=1000 + si)
    out["_split_confirm"] = _split_confirm(out)
    return out


def _split_confirm(per_team: dict) -> dict:
    """(§Leg2γ / §4.3) For each (variable, channel): mean lift and mean absolute agreement on the FIT
    pair {Ryo, tetsuya} vs the CONFIRM pair {Arman, Crop Dusta}, and whether the confirm pair
    reproduces >= CONFIRM_FRAC of the fit lift. The best fit-pair cell is highlighted."""
    def mean_over(pair, vname, cname, field):
        xs = [per_team[t]["variables"][vname]["channels"][cname][field]
              for t in pair if t in per_team]
        xs = [x for x in xs if x is not None]
        return statistics.fmean(xs) if xs else None

    cells = []
    for vname in V_DECL:
        for cname in ("prod", "market"):
            fit_lift = mean_over(FIT_PAIR, vname, cname, "lift")
            conf_lift = mean_over(CONFIRM_PAIR, vname, cname, "lift")
            fit_agr = mean_over(FIT_PAIR, vname, cname, "agreement")
            conf_agr = mean_over(CONFIRM_PAIR, vname, cname, "agreement")
            reproduces = (fit_lift is not None and conf_lift is not None and fit_lift > 0
                          and (conf_lift / fit_lift) >= CONFIRM_FRAC)
            cells.append({
                "variable": vname, "channel": cname,
                "fit_lift": round(fit_lift, 4) if fit_lift is not None else None,
                "confirm_lift": round(conf_lift, 4) if conf_lift is not None else None,
                "fit_agreement": round(fit_agr, 4) if fit_agr is not None else None,
                "confirm_agreement": round(conf_agr, 4) if conf_agr is not None else None,
                "confirm_frac_of_fit": (round(conf_lift / fit_lift, 3)
                                        if (fit_lift and conf_lift is not None and fit_lift > 0)
                                        else None),
                "confirm_reproduces": reproduces,
            })
    cells.sort(key=lambda c: (c["fit_lift"] is None, -(c["fit_lift"] or -1)))
    return {"fit_pair": list(FIT_PAIR), "confirm_pair": list(CONFIRM_PAIR),
            "ranked_by_fit_lift": cells}


# --------------------------------------------------------------------------------------------------
# leg 3 — cross-match control (DECISIVE)
# --------------------------------------------------------------------------------------------------
def _pair_disagree(ta: dict, tb: dict, channel: str) -> float:
    T = min(ta["T"], tb["T"])
    a, b = ta[channel], tb[channel]
    return sum(1 for i in range(T) if a[i] != b[i]) / T


def leg3(cands: dict, trace_cache: dict) -> dict:
    """Group every candidate trace by seed (same town). Compare BETWEEN-TEAM same-town disagreement
    (two different top-4 policies, one town) with WITHIN-TEAM different-town disagreement (one team,
    different towns). If they are ~equal, there is no single town-reactive policy to extract (K3)."""
    from analysis.s6_step1_phase0 import _load_inventory
    inv = {(r["episode_id"], r["seat"]): r for r in _load_inventory()}

    # union of the 4 candidates' (eid, seat), deduped, with team + seed attached
    entries = []
    seen = set()
    for team, c in cands.items():
        for eid, seat in c["episodes"]:
            if (eid, seat) in seen:
                continue
            seen.add((eid, seat))
            info = inv.get((eid, seat))
            entries.append({"eid": eid, "seat": seat, "team": team,
                            "seed": info["seed"] if info else None})

    by_seed: dict = defaultdict(list)
    for e in entries:
        by_seed[e["seed"]].append(e)
    seeds_multi_team = [s for s, es in by_seed.items() if len({e["team"] for e in es}) >= 2]

    def dis(ea, eb, ch):
        return _pair_disagree(trace_cache[(ea["eid"], ea["seat"])],
                              trace_cache[(eb["eid"], eb["seat"])], ch)

    between_prod, between_mkt = [], []          # same seed (town), different team
    within_prod, within_mkt = [], []            # same team, different seed (town)

    for seed, es in by_seed.items():
        for ea, eb in combinations(es, 2):
            if ea["team"] != eb["team"]:
                between_prod.append(dis(ea, eb, "prod"))
                between_mkt.append(dis(ea, eb, "market"))

    # a true cross-match episode = one episode file whose two seats are both top-4 candidates
    eid_seats: dict = defaultdict(set)
    eid_teams: dict = defaultdict(set)
    for e in entries:
        eid_seats[e["eid"]].add(e["seat"])
        eid_teams[e["eid"]].add(e["team"])
    n_cross_match_episodes = sum(1 for eid, ss in eid_seats.items()
                                 if len(ss) >= 2 and len(eid_teams[eid]) >= 2)

    # within-team, different-town pairs
    by_team_seed: dict = defaultdict(list)
    for e in entries:
        by_team_seed[e["team"]].append(e)
    for team, es in by_team_seed.items():
        for ea, eb in combinations(es, 2):
            if ea["seed"] != eb["seed"]:
                within_prod.append(dis(ea, eb, "prod"))
                within_mkt.append(dis(ea, eb, "market"))

    def summ(xs):
        return {"n_pairs": len(xs),
                "median": round(statistics.median(xs), 4) if xs else None,
                "mean": round(statistics.fmean(xs), 4) if xs else None}

    return {
        "n_candidate_traces": len(entries),
        "n_distinct_seeds": len(by_seed),
        "n_seeds_with_multiple_teams": len(seeds_multi_team),
        "n_cross_match_episodes": n_cross_match_episodes,
        "between_team_same_town": {"prod": summ(between_prod), "market": summ(between_mkt)},
        "within_team_diff_town": {"prod": summ(within_prod), "market": summ(within_mkt)},
    }


# --------------------------------------------------------------------------------------------------
# verdict (§4 GO rule + §8 kill table)
# --------------------------------------------------------------------------------------------------
def _verdict(rec: dict) -> dict:
    l0 = rec["leg0"]
    if not l0["pass"]:
        return {"gate": "K1", "go": False,
                "text": "K1 — Leg 0 did NOT reproduce the 8 §7.1 numbers within +-0.01. The pipeline "
                        "has a bug; every leg-1..3 number is unreliable. STOP and fix first."}

    l2 = rec.get("leg2")
    l3 = rec.get("leg3")
    if l2 is None or l3 is None:
        return {"gate": None, "go": None, "text": "legs 2/3 not run — run `all`."}

    # §4 GO: need a single (variable, channel) that clears lift, absolute agreement, AND confirm.
    cells = l2["_split_confirm"]["ranked_by_fit_lift"]
    winners = [c for c in cells
               if c["fit_lift"] is not None and c["fit_lift"] >= MIN_LIFT
               and c["fit_agreement"] is not None and c["fit_agreement"] >= MIN_ABS_AGREEMENT
               and c["confirm_reproduces"]]
    best = cells[0] if cells else None

    # §Leg3 / K3: is there any same-town shared core?
    bt = l3["between_team_same_town"]["prod"]["median"]
    wt = l3["within_team_diff_town"]["prod"]["median"]
    k3_fires = (bt is not None and wt is not None and bt >= 0.95 * wt)

    if winners:
        w = winners[0]
        go_text = (f"GO — {w['variable']} / {w['channel']} clears all §4 gates: fit lift "
                   f"{w['fit_lift']:+.3f} (>= {MIN_LIFT}), absolute agreement {w['fit_agreement']:.3f} "
                   f"(>= {MIN_ABS_AGREEMENT}), and the confirm pair reproduces "
                   f"{w['confirm_frac_of_fit']:.0%} of the lift (>= {CONFIRM_FRAC:.0%}). "
                   f"Proceed to Phase 1 (policy reconstruction) THEN the fidelity gate (<= 5% median "
                   f"bank error) — no upload without both.")
        if k3_fires:
            go_text += (f" NOTE: Leg 3 K3 is borderline (between-team same-town prod disagreement "
                        f"{bt} vs within-team diff-town {wt}); confirm the shared core before Phase 1.")
        return {"gate": "GO", "go": True, "winner": w, "text": go_text}

    # No winner → which STOP?
    if k3_fires:
        return {"gate": "K3", "go": False, "winner": best,
                "text": (f"K3 — Leg 3 decisive: between-team SAME-town production disagreement "
                         f"({bt}) is not meaningfully below within-team DIFFERENT-town disagreement "
                         f"({wt}). Two different top-4 policies in one town diverge about as much as "
                         f"one policy across towns — this is four different strategies, NOT a shared "
                         f"town-reactive policy. There is no single policy to extract by any method. "
                         f"STOP; this also voids Phase 1 and any future top-4 re-donor.")}
    return {"gate": "K2", "go": False, "winner": best,
            "text": (f"K2 — no pre-declared variable cleared §4 (best fit-pair cell: "
                     f"{best['variable']}/{best['channel']} lift {best['fit_lift']}, agreement "
                     f"{best['fit_agreement']}, confirm reproduces={best['confirm_reproduces']}). "
                     f"State-aliasing is confirmed with OUR OWN number: the top-4 residual is not a "
                     f"legible one-variable rule. This closes risk #2 properly. STOP.")}


# --------------------------------------------------------------------------------------------------
# driver + printing
# --------------------------------------------------------------------------------------------------
def _load_all_traces(cands: dict) -> tuple[dict, dict]:
    """trace_cache[(eid,seat)] = full trace dict; traces_by_team[team] = [trace, ...]."""
    trace_cache: dict = {}
    traces_by_team: dict = {}
    for team, c in cands.items():
        lst = []
        for eid, seat in c["episodes"]:
            key = (eid, seat)
            if key not in trace_cache:
                trace_cache[key] = _load_trace(eid, seat)
            lst.append(trace_cache[key])
        traces_by_team[team] = lst
    return trace_cache, traces_by_team


def _print(rec: dict):
    print("\n" + "=" * 90)
    print("S7 — CONDITIONAL AGREEMENT ON THE TOP-4 (Phase 0, desk-only)")
    print("=" * 90)

    l0 = rec["leg0"]
    print(f"\n[leg 0] reproduction tripwire (tol +-{l0['tolerance']}) — pass={l0['pass']}")
    print(f"  {'team':<18}{'prod':>8}{'(tgt)':>8}{'market':>8}{'(tgt)':>8}  ok")
    for team, r in l0["candidates"].items():
        print(f"  {team:<18}{r['prod']:>8.3f}{r['target_prod']:>8.3f}"
              f"{r['market']:>8.3f}{r['target_market']:>8.3f}  {'OK' if r['pass'] else 'FAIL'}")

    if rec.get("leg1"):
        print(f"\n[leg 1] production-disagreement channel decomposition")
        print(f"  {'team':<18}{'disagree':>9}{'farmerOp':>9}{'workerN':>9}{'handContent':>12}")
        for team, r in rec["leg1"].items():
            print(f"  {team:<18}{r['n_disagree_prod']:>9}"
                  f"{(r['farmer_op_frac'] or 0):>9.2f}{(r['worker_count_frac'] or 0):>9.2f}"
                  f"{(r['hands_content_frac'] or 0):>12.2f}")
        print("  (fractions are of production-disagreement steps)")

    if rec.get("leg2"):
        sc = rec["leg2"]["_split_confirm"]
        print(f"\n[leg 2] conditional agreement — top cells by FIT-pair lift "
              f"(fit={sc['fit_pair']}, confirm={sc['confirm_pair']})")
        print(f"  {'variable':<20}{'ch':>7}{'fitLift':>9}{'fitAgr':>8}{'confLift':>9}"
              f"{'confAgr':>8}{'repro':>7}")
        for c in sc["ranked_by_fit_lift"][:12]:
            print(f"  {c['variable']:<20}{c['channel']:>7}"
                  f"{(c['fit_lift'] if c['fit_lift'] is not None else 0):>9.3f}"
                  f"{(c['fit_agreement'] if c['fit_agreement'] is not None else 0):>8.3f}"
                  f"{(c['confirm_lift'] if c['confirm_lift'] is not None else 0):>9.3f}"
                  f"{(c['confirm_agreement'] if c['confirm_agreement'] is not None else 0):>8.3f}"
                  f"{('Y' if c['confirm_reproduces'] else 'n'):>7}")
        # excluded-step fractions for the top variable per team
        anyteam = next(t for t in rec["leg2"] if t != "_split_confirm")
        print(f"  guard (β) min-stratum={MIN_STRATUM}; example excluded-step fracs ({anyteam}):")
        for v in list(V_DECL)[:11]:
            ex = rec["leg2"][anyteam]["variables"][v]["channels"]["prod"]["excluded_frac"]
            ms = rec["leg2"][anyteam]["variables"][v]["mean_strata_per_step"]
            print(f"      {v:<20} excluded={ex:.2f}  mean_strata/step={ms}")

    if rec.get("leg3"):
        l3 = rec["leg3"]
        print(f"\n[leg 3] cross-match control (DECISIVE)")
        print(f"  {l3['n_candidate_traces']} candidate traces, {l3['n_distinct_seeds']} distinct "
              f"seeds, {l3['n_seeds_with_multiple_teams']} seeds w/ >=2 teams, "
              f"{l3['n_cross_match_episodes']} true cross-match episodes")
        for ch in ("prod", "market"):
            bt = l3["between_team_same_town"][ch]
            wt = l3["within_team_diff_town"][ch]
            print(f"  {ch:<7} between-team SAME-town: median {bt['median']} ({bt['n_pairs']} pairs)"
                  f"  |  within-team DIFF-town: median {wt['median']} ({wt['n_pairs']} pairs)")

    v = rec["verdict"]
    print("\n" + "-" * 90)
    print(f"VERDICT [{v['gate']}] go={v['go']}")
    print(v["text"])
    print("-" * 90)


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("leg0")
    for name in ("leg1", "leg2", "leg3", "all"):
        p = sub.add_parser(name)
        if name in ("leg2", "all"):
            p.add_argument("--perms", type=int, default=200, help="permutation-null iterations (>=200)")
    sub.add_parser("report")
    args = ap.parse_args()

    if args.cmd == "report":
        if not OUT.exists():
            raise SystemExit(f"{OUT} missing — run `all` first")
        _print(json.loads(OUT.read_text()))
        return 0

    cands = _candidates()

    if args.cmd == "leg0":
        rec = {"leg0": leg0(cands)}
        rec["verdict"] = _verdict(rec)
        _print(rec)
        return 0 if rec["leg0"]["pass"] else 1

    # leg1/leg2/leg3/all all need the full traces
    print("loading traces ...", flush=True)
    trace_cache, traces_by_team = _load_all_traces(cands)

    rec = {"archive": ARCHIVE.name, "leg0": leg0(cands)}
    if not rec["leg0"]["pass"]:
        rec["verdict"] = _verdict(rec)
        _print(rec)
        DERIVED.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(rec, indent=1))
        return 1  # K1 — do not trust downstream numbers

    if args.cmd in ("leg1", "all"):
        rec["leg1"] = leg1(traces_by_team)
    if args.cmd in ("leg3", "all"):
        rec["leg3"] = leg3(cands, trace_cache)
    if args.cmd in ("leg2", "all"):
        rec["leg2"] = leg2(traces_by_team, perms=args.perms)

    rec["verdict"] = _verdict(rec)
    DERIVED.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rec, indent=1))
    _print(rec)
    print(f"\nwrote {OUT} (gitignored)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
