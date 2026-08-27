#!/usr/bin/env python3
"""S13 Phase 1 — is the seat asymmetry real? (docs/plans/s13_seat_asymmetry.md §2)

Screen was `55726984` (97 eps): seat 0 30W-16L (WR 0,652), seat 1 24W-27L (WR 0,471),
p ~ 0,07 at n=46/51 — "a question, not a finding" (plan §1). This module answers three
pre-registered questions on the full 509-episode corpus (`55586926` + `55675634` +
`55726984`), thresholds declared in the plan BEFORE running:

  1a — replicate the raw seat W/L split, per submission and pooled (never pooled alone).
  1b — the opponent-strength control: is there a confound, and does the gap survive a
       Cochran-Mantel-Haenszel test stratified by rating zone (THE headline number).
  1c — the temporal/burst control: gap excluding each submission's first 70 episodes,
       and a logistic regression of outcome on (seat, episode position) pooled with
       submission fixed effects.
  1d — the town control: realised shop-draw distribution by seat; add it as a CMH
       stratum if it differs materially.

Reused, not rewritten: `analysis.board_join` (board_at/rating_zone/episode_times, S11 B1)
and `analysis.s8_replay_io` (ladder_episodes/our_seat/SUBMISSIONS, S8). No `agent/`
change, no episode played, no submission (plan §5 rule 1).

Decision rule (plan §2, pre-registered):
    CMH p < 0,01 and same raw-gap sign in all three submissions  -> real, Phase 2 opens
    CMH p >= 0,05, or sign disagrees across submissions          -> dead
    0,01 <= p < 0,05                                             -> underpowered, stop

CLI:
    python analysis/s13_seat_asymmetry.py run
    python analysis/s13_seat_asymmetry.py report
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from collections import Counter, defaultdict
from math import sqrt
from pathlib import Path

import numpy as np
from scipy.stats import chi2, chi2_contingency, fisher_exact, mannwhitneyu

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from analysis.board_join import board_at, episode_times, rating_zone  # noqa: E402
from analysis.s8_replay_io import SUBMISSIONS, ladder_episodes, our_seat  # noqa: E402

DERIVED = ROOT / "data" / "derived"
OUT = DERIVED / "s13_seat_phase1.json"

Z95 = 1.959963985  # two-sided 95%
BURST_EXCLUDE = 70  # plan §2 1c — pre-registered, not tuned

# --------------------------------------------------------------------------------------
# statistics primitives — pure functions, unit-tested in tests/test_s13_seat_asymmetry.py
# --------------------------------------------------------------------------------------


def wilson_ci(x: int, n: int, z: float = Z95) -> tuple[float, float] | tuple[None, None]:
    """Wilson score interval for a single proportion x/n."""
    if n == 0:
        return None, None
    phat = x / n
    denom = 1 + z * z / n
    center = (phat + z * z / (2 * n)) / denom
    half = (z * sqrt(phat * (1 - phat) / n + z * z / (4 * n * n))) / denom
    return center - half, center + half


def newcombe_diff_ci(x1: int, n1: int, x2: int, n2: int,
                      z: float = Z95) -> tuple[float, float] | tuple[None, None]:
    """Newcombe (1998) hybrid-Wilson CI for p1 - p2. Standard for two independent
    proportions — robust at the small-to-medium n this corpus carries."""
    if n1 == 0 or n2 == 0:
        return None, None
    l1, u1 = wilson_ci(x1, n1, z)
    l2, u2 = wilson_ci(x2, n2, z)
    p1, p2 = x1 / n1, x2 / n2
    diff = p1 - p2
    lower = diff - sqrt((p1 - l1) ** 2 + (u2 - p2) ** 2)
    upper = diff + sqrt((u1 - p1) ** 2 + (p2 - l2) ** 2)
    return lower, upper


def fisher_p(a: int, b: int, c: int, d: int) -> float:
    """Two-sided Fisher exact on [[a,b],[c,d]] (row0=seat0 win/loss, row1=seat1 win/loss)."""
    _, p = fisher_exact([[a, b], [c, d]])
    return float(p)


def cmh_test(strata: list[tuple[int, int, int, int]]) -> dict:
    """Cochran-Mantel-Haenszel test over 2x2 strata (a,b,c,d) = (seat0 W, seat0 L,
    seat1 W, seat1 L). Reports both the continuity-corrected statistic (R's
    `mantelhaen.test` default) and the uncorrected one; the corrected figure is the
    headline (more conservative). Also returns the Mantel-Haenszel common odds ratio."""
    num = 0.0
    var = 0.0
    or_num = 0.0
    or_den = 0.0
    used = 0
    for a, b, c, d in strata:
        n = a + b + c + d
        if n < 2:
            continue
        used += 1
        num += a - (a + b) * (a + c) / n
        v = (a + b) * (c + d) * (a + c) * (b + d) / (n * n * (n - 1))
        var += v
        or_num += a * d / n
        or_den += b * c / n
    if var == 0 or used == 0:
        return {"n_strata_used": used, "chi2_corrected": None, "p_corrected": None,
                "chi2_uncorrected": None, "p_uncorrected": None, "or_mh": None}
    chi2_unc = (num * num) / var
    chi2_cor = (max(0.0, abs(num) - 0.5)) ** 2 / var
    return {
        "n_strata_used": used,
        "chi2_corrected": chi2_cor,
        "p_corrected": float(chi2.sf(chi2_cor, df=1)),
        "chi2_uncorrected": chi2_unc,
        "p_uncorrected": float(chi2.sf(chi2_unc, df=1)),
        "or_mh": (or_num / or_den) if or_den else None,
    }


def mannwhitney(x: list[float], y: list[float]) -> dict:
    if not x or not y:
        return {"u": None, "p": None, "median_x": None, "median_y": None}
    u, p = mannwhitneyu(x, y, alternative="two-sided")
    return {"u": float(u), "p": float(p),
            "median_x": float(np.median(x)), "median_y": float(np.median(y))}


def logistic_fit(X: np.ndarray, y: np.ndarray, max_iter: int = 100,
                  tol: float = 1e-10) -> dict:
    """IRLS logistic regression (IRLS == Fisher scoring for this family) — no
    statsmodels in the environment. Returns coefficients, Wald SEs, and the
    log-likelihood at convergence so callers can build LR tests by hand."""
    n, p = X.shape
    beta = np.zeros(p)
    for _ in range(max_iter):
        eta = X @ beta
        mu = 1.0 / (1.0 + np.exp(-eta))
        w = np.clip(mu * (1 - mu), 1e-10, None)
        z = eta + (y - mu) / w
        xtw = X.T * w
        xtwx = xtw @ X
        xtwz = xtw @ z
        beta_new = np.linalg.solve(xtwx, xtwz)
        if np.max(np.abs(beta_new - beta)) < tol:
            beta = beta_new
            break
        beta = beta_new
    eta = X @ beta
    mu = 1.0 / (1.0 + np.exp(-eta))
    mu = np.clip(mu, 1e-12, 1 - 1e-12)
    ll = float(np.sum(y * np.log(mu) + (1 - y) * np.log(1 - mu)))
    w = mu * (1 - mu)
    cov = np.linalg.inv((X.T * w) @ X)
    se = np.sqrt(np.diag(cov))
    return {"beta": beta.tolist(), "se": se.tolist(), "ll": ll, "n": n, "p_params": p}


def lr_test(ll_full: float, ll_reduced: float, df: int = 1) -> float:
    stat = max(0.0, 2.0 * (ll_full - ll_reduced))
    return float(chi2.sf(stat, df=df))


# --------------------------------------------------------------------------------------
# data extraction — one row per ladder episode, all three submissions
# --------------------------------------------------------------------------------------


def load_all_episodes() -> list[dict]:
    rows = []
    for sub in SUBMISSIONS:
        times = episode_times(sub)
        idx = 0
        for eid, m in ladder_episodes(sub):
            idx += 1  # ladder_episodes yields id-ascending -> chronological proxy
            seat = our_seat(m["teams"])
            if seat is None:
                continue
            opp = m["teams"][1 - seat]
            rewards = m.get("rewards")
            bank = float(rewards[seat]) if rewards and rewards[seat] is not None else None
            opp_bank = float(rewards[1 - seat]) if rewards and rewards[1 - seat] is not None else None
            if bank is None or opp_bank is None:
                continue
            t = times.get(eid)
            opp_score = opp_rank = zone = None
            if t is not None:
                board = board_at(t)
                info = board.get(opp)
                if info is not None:
                    opp_rank, opp_score, _last_sub = info
                    zone = rating_zone(opp_score)
            last_step = m["steps"][-1]
            shops = list((last_step[seat]["observation"].get("town") or {}).get("unlocked_shops") or [])
            rows.append({
                "submission": sub, "episode_id": eid, "seat": seat, "opponent": opp,
                "win": bank > opp_bank, "bank": bank, "opp_bank": opp_bank,
                "ep_index": idx, "ep_time": t.isoformat() if t else None,
                "opp_score": opp_score, "opp_rank": opp_rank, "zone": zone,
                "shops": shops,
            })
        # stamp n_sub once idx is final
        n_sub = idx
        for r in rows:
            if r["submission"] == sub:
                r["n_sub"] = n_sub
    return rows


# --------------------------------------------------------------------------------------
# Phase 1a — replication
# --------------------------------------------------------------------------------------


def _wl_table(rows: list[dict]) -> tuple[int, int, int, int]:
    """(seat0_w, seat0_l, seat1_w, seat1_l)."""
    a = sum(1 for r in rows if r["seat"] == 0 and r["win"])
    b = sum(1 for r in rows if r["seat"] == 0 and not r["win"])
    c = sum(1 for r in rows if r["seat"] == 1 and r["win"])
    d = sum(1 for r in rows if r["seat"] == 1 and not r["win"])
    return a, b, c, d


def _seat_summary(rows: list[dict]) -> dict:
    a, b, c, d = _wl_table(rows)
    n0, n1 = a + b, c + d
    wr0 = a / n0 if n0 else None
    wr1 = c / n1 if n1 else None
    gap = (wr0 - wr1) if (wr0 is not None and wr1 is not None) else None
    return {
        "n": len(rows), "seat0_w": a, "seat0_l": b, "seat1_w": c, "seat1_l": d,
        "seat0_wr": wr0, "seat1_wr": wr1, "gap": gap,
        "fisher_p": fisher_p(a, b, c, d) if n0 and n1 else None,
        "gap_ci95_newcombe": newcombe_diff_ci(a, n0, c, n1) if n0 and n1 else (None, None),
    }


def phase1a(rows: list[dict]) -> dict:
    per_sub = {sub: _seat_summary([r for r in rows if r["submission"] == sub])
               for sub in SUBMISSIONS}
    pooled = _seat_summary(rows)
    gaps = [v["gap"] for v in per_sub.values() if v["gap"] is not None]
    signs = [1 if g > 0 else (-1 if g < 0 else 0) for g in gaps]
    same_sign = len(signs) == 3 and all(s == signs[0] and s != 0 for s in signs)
    return {"per_submission": per_sub, "pooled": pooled,
            "signs": signs, "same_sign_all_three": same_sign}


# --------------------------------------------------------------------------------------
# Phase 1b — the opponent-strength control
# --------------------------------------------------------------------------------------


def phase1b(rows: list[dict]) -> dict:
    matched = [r for r in rows if r["zone"] is not None]
    unmatched = [r for r in rows if r["zone"] is None]

    # 1. confound check
    s0_scores = [r["opp_score"] for r in matched if r["seat"] == 0]
    s1_scores = [r["opp_score"] for r in matched if r["seat"] == 1]
    confound = mannwhitney(s0_scores, s1_scores)

    # 2. controlled comparison — CMH stratified by rating zone
    zones = sorted({r["zone"] for r in matched})
    headline_strata = []
    zone_rows = {}
    for z in zones:
        zrows = [r for r in matched if r["zone"] == z]
        a, b, c, d = _wl_table(zrows)
        headline_strata.append((a, b, c, d))
        zone_rows[z] = {"n": len(zrows), "seat0_w": a, "seat0_l": b, "seat1_w": c, "seat1_l": d,
                         "seat0_wr": (a / (a + b)) if (a + b) else None,
                         "seat1_wr": (c / (c + d)) if (c + d) else None}
    headline_cmh = cmh_test(headline_strata)

    per_sub_cmh = {}
    for sub in SUBMISSIONS:
        sub_matched = [r for r in matched if r["submission"] == sub]
        strata = []
        for z in zones:
            zrows = [r for r in sub_matched if r["zone"] == z]
            if not zrows:
                continue
            strata.append(_wl_table(zrows))
        per_sub_cmh[sub] = {"n": len(sub_matched), **cmh_test(strata)}

    # 3. unmatched row — never silently dropped
    a_m, b_m, c_m, d_m = _wl_table(matched)
    a_u, b_u, c_u, d_u = _wl_table(unmatched)
    n0_m, n1_m = a_m + b_m, c_m + d_m
    n0_u, n1_u = a_u + b_u, c_u + d_u
    unmatched_seat_split_p = (
        fisher_p(n0_m, n1_m, n0_u, n1_u) if (n0_m + n1_m) and (n0_u + n1_u) else None
    )

    return {
        "n_matched": len(matched), "n_unmatched": len(unmatched),
        "match_rate": len(matched) / len(rows) if rows else None,
        "confound_check": confound,
        "by_zone": zone_rows,
        "headline_cmh": headline_cmh,
        "per_submission_cmh": per_sub_cmh,
        "unmatched": {
            "n": len(unmatched), "seat0": n0_u, "seat1": n1_u,
            "seat_split_vs_matched_fisher_p": unmatched_seat_split_p,
            "seat0_wr": (a_u / n0_u) if n0_u else None,
            "seat1_wr": (c_u / n1_u) if n1_u else None,
        },
    }


# --------------------------------------------------------------------------------------
# Phase 1c — temporal / burst control
# --------------------------------------------------------------------------------------


def phase1c(rows: list[dict]) -> dict:
    post_burst = []
    per_sub_excl = {}
    for sub in SUBMISSIONS:
        sub_rows = sorted([r for r in rows if r["submission"] == sub], key=lambda r: r["ep_index"])
        n = len(sub_rows)
        kept = sub_rows[BURST_EXCLUDE:] if n > BURST_EXCLUDE else []
        per_sub_excl[sub] = {"n_total": n, "n_excluded": min(BURST_EXCLUDE, n),
                              "n_kept": len(kept), **_seat_summary(kept)}
        post_burst.extend(kept)
    pooled_post_burst = _seat_summary(post_burst)

    # logistic regression: outcome ~ seat + ep_frac (+ submission dummies), pooled
    subs = list(SUBMISSIONS)
    y = np.array([1.0 if r["win"] else 0.0 for r in rows])
    seat = np.array([float(r["seat"]) for r in rows])
    ep_frac = np.array([r["ep_index"] / r["n_sub"] for r in rows])
    dummies = [np.array([1.0 if r["submission"] == s else 0.0 for r in rows]) for s in subs[1:]]
    intercept = np.ones(len(rows))

    X_full = np.column_stack([intercept, *dummies, ep_frac, seat])
    X_reduced = np.column_stack([intercept, *dummies, ep_frac])
    full = logistic_fit(X_full, y)
    reduced = logistic_fit(X_reduced, y)
    p_lr = lr_test(full["ll"], reduced["ll"], df=1)
    seat_idx = X_full.shape[1] - 1
    seat_beta = full["beta"][seat_idx]
    seat_se = full["se"][seat_idx]
    pooled_logistic = {
        "feature_order": ["intercept", *[f"sub_{s}" for s in subs[1:]], "ep_frac", "seat"],
        "beta": full["beta"], "se": full["se"], "ll_full": full["ll"], "ll_reduced": reduced["ll"],
        "seat_coef": seat_beta, "seat_se": seat_se,
        "seat_wald_p": float(2 * chi2.sf((seat_beta / seat_se) ** 2, df=1)) if seat_se else None,
        "seat_lr_p": p_lr,
        "seat_survives_time_term_p<0.01": p_lr < 0.01,
    }

    per_sub_logistic = {}
    for sub in subs:
        sub_rows = [r for r in rows if r["submission"] == sub]
        y_s = np.array([1.0 if r["win"] else 0.0 for r in sub_rows])
        seat_s = np.array([float(r["seat"]) for r in sub_rows])
        ep_frac_s = np.array([r["ep_index"] / r["n_sub"] for r in sub_rows])
        intercept_s = np.ones(len(sub_rows))
        Xf = np.column_stack([intercept_s, ep_frac_s, seat_s])
        Xr = np.column_stack([intercept_s, ep_frac_s])
        try:
            ff = logistic_fit(Xf, y_s)
            rr = logistic_fit(Xr, y_s)
            p = lr_test(ff["ll"], rr["ll"], df=1)
            per_sub_logistic[sub] = {"seat_coef": ff["beta"][-1], "seat_se": ff["se"][-1],
                                      "seat_lr_p": p}
        except np.linalg.LinAlgError:
            per_sub_logistic[sub] = {"seat_coef": None, "seat_se": None, "seat_lr_p": None,
                                      "note": "singular design (n too small)"}

    return {
        "burst_exclude_n": BURST_EXCLUDE,
        "per_submission_excl_burst": per_sub_excl,
        "pooled_excl_burst": pooled_post_burst,
        "logistic_pooled": pooled_logistic,
        "logistic_per_submission": per_sub_logistic,
    }


# --------------------------------------------------------------------------------------
# Phase 1d — the town control
# --------------------------------------------------------------------------------------


def phase1d(rows: list[dict], zone_strata_1b: list[tuple[int, int, int, int]] | None,
            zones: list[str]) -> dict:
    seat0_shops = Counter()
    seat1_shops = Counter()
    for r in rows:
        c = seat0_shops if r["seat"] == 0 else seat1_shops
        c.update(r["shops"])
    shop_types = sorted(set(seat0_shops) | set(seat1_shops))
    if len(shop_types) < 2:
        return {"shop_types": shop_types, "note": "too few distinct shop types for a chi2 test"}
    table = np.array([[seat0_shops[s], seat1_shops[s]] for s in shop_types])
    chi2_stat, p, dof, expected = chi2_contingency(table)
    residuals = (table - expected) / np.sqrt(expected)
    worst_idx = int(np.argmax(np.abs(residuals[:, 0]) + np.abs(residuals[:, 1])))
    worst_shop = shop_types[worst_idx]
    material = bool(p < 0.05)

    result = {
        "shop_types": shop_types,
        "seat0_counts": {s: seat0_shops[s] for s in shop_types},
        "seat1_counts": {s: seat1_shops[s] for s in shop_types},
        "chi2": float(chi2_stat), "p": float(p), "dof": int(dof),
        "material_difference": material,
        "largest_residual_shop": worst_shop,
    }

    if material and zone_strata_1b:
        median_count = float(np.median([r["shops"].count(worst_shop) for r in rows]))
        strata = defaultdict(list)
        for r in rows:
            if r["zone"] is None:
                continue
            bucket = "high" if r["shops"].count(worst_shop) > median_count else "low"
            strata[(r["zone"], bucket)].append(r)
        tables = [_wl_table(v) for v in strata.values()]
        extended = cmh_test(tables)
        result["extended_cmh_with_town_stratum"] = {
            "stratum_variable": f"count({worst_shop}) > median({median_count})",
            "n_strata": len(tables), **extended,
        }
    return result


# --------------------------------------------------------------------------------------
# decision + driver
# --------------------------------------------------------------------------------------


def decide(a: dict, b: dict) -> dict:
    p = (b["headline_cmh"] or {}).get("p_corrected")
    same_sign = a["same_sign_all_three"]
    if p is None:
        verdict = "dead"
        reason = "CMH degenerate (no usable strata) — treated as no evidence of an effect"
    elif p < 0.01 and same_sign:
        verdict = "real"
        reason = f"CMH p_corrected={p:.4g} < 0.01 and same sign in all three submissions"
    elif p >= 0.05 or not same_sign:
        verdict = "dead"
        reason = f"CMH p_corrected={p:.4g}, same_sign={same_sign}"
    else:
        verdict = "underpowered"
        reason = f"CMH p_corrected={p:.4g} in [0.01, 0.05) — not established, do not build"
    return {"verdict": verdict, "reason": reason, "cmh_p_corrected": p, "same_sign": same_sign}


def run() -> dict:
    rows = load_all_episodes()
    a = phase1a(rows)
    b = phase1b(rows)
    c = phase1c(rows)
    zones = sorted({r["zone"] for r in rows if r["zone"] is not None})
    zone_strata = [(v["seat0_w"], v["seat0_l"], v["seat1_w"], v["seat1_l"])
                   for v in b["by_zone"].values()]
    d = phase1d(rows, zone_strata, zones)
    decision = decide(a, b)

    out = {
        "pass": "S13 Phase 1 — seat asymmetry, is it real?",
        "generated": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "verdict": f"{decision['verdict']}: {decision['reason']}",
        "n_total_episodes": len(rows),
        "submissions": list(SUBMISSIONS),
        "decision": decision,
        "phase1a_replication": a,
        "phase1b_opponent_strength": b,
        "phase1c_temporal_burst": c,
        "phase1d_town": d,
    }
    DERIVED.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=2, ensure_ascii=False, default=str))
    print(f"wrote {OUT}  ({len(rows)} ladder episodes)  verdict: {out['verdict']}")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["run", "report"])
    args = ap.parse_args()
    if args.cmd == "run":
        run()
    else:
        print(json.dumps(json.loads(OUT.read_text()), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
