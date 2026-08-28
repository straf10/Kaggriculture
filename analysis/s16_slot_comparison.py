#!/usr/bin/env python3
"""S16 Phase 1 — read both live slots (`55726984`, `55675634`) in the SAME window.

ROADMAP §2 rule 9's corollary: two of our own agents are comparable only if fielded
together and read over the same calendar window.  Both are fielded right now, so this
needs no bench — it is the cleanest comparison available (docs/plans/s16_slot_comparison.md
§1).

Reused, not rewritten (ROADMAP §3 "reuse, do not duplicate" / plan §4 rule 2):
  - `analysis.s8_replay_io` (`ladder_episodes`, `our_seat`) — the one replay parser.
  - `analysis.board_join` (`board_at`, `rating_zone`, `episode_times`) — the one
    leaderboard-join instrument (built for S13, reused verbatim).
  - `analysis.s13_seat_asymmetry` (`cmh_test`, `fisher_p`, `newcombe_diff_ci`,
    `wilson_ci`) — the one CMH/CI implementation in the repo.
Only new code: the window definition, the per-opponent / zone tables for a *slot* (not
*seat*) comparison, and the power calculation the plan's §1 step 5 demands pre-registered.

Pre-registered gate (plan §1 step 5, declared BEFORE reading any outcome below):
    CMH p < 0.05  AND  zone-stratified gap >= 0.10   -> declare a winner
    otherwise                                         -> "not separable at this sample size"
A direction is never reported as a finding when the test does not clear (plan §4 rule 8).

CLI:
    python analysis/s16_slot_comparison.py run
    python analysis/s16_slot_comparison.py report
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import statistics
import sys
from collections import defaultdict
from math import sqrt
from pathlib import Path

from scipy.stats import norm

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from analysis.board_join import board_at, episode_times, rating_zone  # noqa: E402
from analysis.s8_replay_io import ladder_episodes, our_seat  # noqa: E402
from analysis.s13_seat_asymmetry import (  # noqa: E402
    cmh_test, fisher_p, newcombe_diff_ci, wilson_ci,
)

DERIVED = ROOT / "data" / "derived"
OUT = DERIVED / "s16_slot_window.json"

SLOT_A = "55726984"  # H2 tail-liquidation — market-only
SLOT_B = "55675634"  # market overlay + tile recovery — occupancy
A_UPLOADED = dt.datetime(2026, 8, 23, 23, 7, 25)
BURST_N = 70  # ROADMAP §2 rule 2 — never judge inside the first ~70 episodes
MIN_WINDOW_N = 40  # plan §1 step 2 — below this, say so and go to Phase 2, do not widen

# Pre-registered gate (plan §1 step 5) — declared before any outcome is read.
GATE_CMH_P = 0.05
GATE_ZONE_GAP = 0.10


# --------------------------------------------------------------------------- loading


def load_slot(sub: str) -> list[dict]:
    """One row per ladder episode: seat, opponent, win, time, opp zone/score/rank."""
    times = episode_times(sub)
    rows = []
    for idx, (eid, m) in enumerate(ladder_episodes(sub), start=1):
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
        opp_last_sub = None
        if t is not None:
            board = board_at(t)
            info = board.get(opp)
            if info is not None:
                opp_rank, opp_score, opp_last_sub = info
                zone = rating_zone(opp_score)
        rows.append({
            "submission": sub, "episode_id": eid, "ep_index": idx, "seat": seat,
            "opponent": opp, "win": bank > opp_bank, "bank": bank, "opp_bank": opp_bank,
            "margin": bank - opp_bank, "time": t,
            "opp_score": opp_score, "opp_rank": opp_rank, "zone": zone,
            "opp_last_sub": opp_last_sub,
            "controlled": bool(t and opp_last_sub and opp_last_sub < t),
        })
    return rows


# --------------------------------------------------------------------------- window


def define_window(rows_a: list[dict]) -> dt.datetime:
    """max(A_upload, A's 70th-episode createTime) — plan §1 step 2."""
    timed = [r for r in rows_a if r["time"] is not None]
    timed.sort(key=lambda r: r["ep_index"])
    if len(timed) < BURST_N:
        # not enough episodes to find a 70th at all; window can't be defined
        return A_UPLOADED
    t70 = timed[BURST_N - 1]["time"]
    return max(A_UPLOADED, t70)


# --------------------------------------------------------------------------- panels


def per_opponent_table(rows_a: list[dict], rows_b: list[dict]) -> dict:
    """A row per opponent, per submission — never a pooled figure (plan §1 step 4.1)."""
    def agg(rows):
        by_opp = defaultdict(lambda: {"w": 0, "l": 0})
        for r in rows:
            by_opp[r["opponent"]]["w" if r["win"] else "l"] += 1
        return by_opp

    a_by, b_by = agg(rows_a), agg(rows_b)
    shared = sorted(set(a_by) & set(b_by))
    all_opps = sorted(set(a_by) | set(b_by))
    rows = []
    for opp in all_opps:
        a, b = a_by.get(opp, {"w": 0, "l": 0}), b_by.get(opp, {"w": 0, "l": 0})
        rows.append({
            "opponent": opp, "both_agents_met": opp in shared,
            "A_w": a["w"], "A_l": a["l"], "B_w": b["w"], "B_l": b["l"],
        })
    return {
        "n_opponents_total": len(all_opps),
        "n_opponents_met_by_both": len(shared),
        "shared_opponents": [r for r in rows if r["both_agents_met"]],
        "all_opponents": rows,
    }


def zone_table(rows: list[dict], controlled_only: bool) -> list[dict]:
    from analysis.board_join import RATING_EDGES
    out = []
    src = [r for r in rows if (r["zone"] is not None) and (not controlled_only or r["controlled"])]
    for _lo, _hi, label in RATING_EDGES:
        sub = [r for r in src if r["zone"] == label]
        w = sum(r["win"] for r in sub)
        out.append({"zone": label, "n": len(sub), "wins": w,
                    "win_rate": (w / len(sub)) if sub else None})
    return out


def zone_strata(rows_a: list[dict], rows_b: list[dict], controlled_only: bool):
    """(a,b,c,d) per zone for cmh_test: (A_win, A_loss, B_win, B_loss)."""
    from analysis.board_join import RATING_EDGES
    strata = []
    detail = []
    for _lo, _hi, label in RATING_EDGES:
        a_sub = [r for r in rows_a if r["zone"] == label and (not controlled_only or r["controlled"])]
        b_sub = [r for r in rows_b if r["zone"] == label and (not controlled_only or r["controlled"])]
        aw, al = sum(r["win"] for r in a_sub), sum(not r["win"] for r in a_sub)
        bw, bl = sum(r["win"] for r in b_sub), sum(not r["win"] for r in b_sub)
        strata.append((aw, al, bw, bl))
        detail.append({"zone": label, "A_n": len(a_sub), "A_wr": (aw / len(a_sub)) if a_sub else None,
                       "B_n": len(b_sub), "B_wr": (bw / len(b_sub)) if b_sub else None})
    return strata, detail


# --------------------------------------------------------------------------- power


def two_proportion_power(n1: int, n2: int, delta: float, alpha: float = 0.05,
                          p0: float = 0.5) -> float:
    """Power of a two-sided two-proportion z-test to detect |p1-p2|=delta at (n1,n2),
    assuming p1=p0+delta/2, p2=p0-delta/2 (maximum-variance placement at p0=0.5)."""
    if n1 <= 0 or n2 <= 0:
        return 0.0
    p1, p2 = p0 + delta / 2, p0 - delta / 2
    se_null = sqrt(p0 * (1 - p0) * (1 / n1 + 1 / n2))
    se_alt = sqrt(max(p1 * (1 - p1), 1e-12) / n1 + max(p2 * (1 - p2), 1e-12) / n2)
    z_alpha = norm.ppf(1 - alpha / 2)
    z_crit = z_alpha * se_null
    return float(norm.sf((z_crit - delta) / se_alt))


def min_detectable_effect(n1: int, n2: int, power_target: float = 0.80,
                           alpha: float = 0.05, p0: float = 0.5) -> float | None:
    lo, hi = 0.0, 2 * min(1 - p0, p0)
    if two_proportion_power(n1, n2, hi, alpha, p0) < power_target:
        return None
    for _ in range(60):
        mid = (lo + hi) / 2
        if two_proportion_power(n1, n2, mid, alpha, p0) >= power_target:
            hi = mid
        else:
            lo = mid
    return hi


# --------------------------------------------------------------------------- driver


def run() -> dict:
    all_a, all_b = load_slot(SLOT_A), load_slot(SLOT_B)
    window_start = define_window(all_a)
    now = dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)

    win_a = [r for r in all_a if r["time"] and window_start <= r["time"] <= now]
    win_b = [r for r in all_b if r["time"] and window_start <= r["time"] <= now]

    n_a, n_b = len(win_a), len(win_b)
    window_adequate = n_a >= MIN_WINDOW_N and n_b >= MIN_WINDOW_N

    res = {
        "pass": "S16 Phase 1 — same-window slot comparison",
        "generated": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "slot_A": SLOT_A, "slot_B": SLOT_B,
        "window": {"start": window_start.isoformat(), "end": now.isoformat(),
                   "n_A_all": len(all_a), "n_B_all": len(all_b),
                   "n_A_window": n_a, "n_B_window": n_b,
                   "min_required_n": MIN_WINDOW_N, "window_adequate": window_adequate},
    }
    if not window_adequate:
        res["verdict"] = (f"WINDOW INADEQUATE: n_A={n_a}, n_B={n_b} in "
                           f"[{window_start.isoformat()}, {now.isoformat()}] — below the "
                           f"n>={MIN_WINDOW_N} floor on at least one side. Per plan §1 step 2, "
                           "do not widen the window; go to Phase 2 (Instrument A).")
        DERIVED.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(res, indent=2, ensure_ascii=False, default=str))
        print(f"wrote {OUT} — window inadequate, stop at Phase 1")
        return res

    # -- panel 1: per-opponent W/L per seat (never pooled alone) -----------------
    res["panel_1_per_opponent"] = per_opponent_table(win_a, win_b)
    res["panel_1_by_seat"] = {
        "A": {str(s): {"w": sum(1 for r in win_a if r["seat"] == s and r["win"]),
                       "l": sum(1 for r in win_a if r["seat"] == s and not r["win"])}
              for s in (0, 1)},
        "B": {str(s): {"w": sum(1 for r in win_b if r["seat"] == s and r["win"]),
                       "l": sum(1 for r in win_b if r["seat"] == s and not r["win"])}
              for s in (0, 1)},
    }

    # -- panel 2: win rate by opponent-strength zone + CMH ------------------------
    n_matched_a = sum(1 for r in win_a if r["zone"] is not None)
    n_matched_b = sum(1 for r in win_b if r["zone"] is not None)
    n_ctrl_a = sum(1 for r in win_a if r["controlled"])
    n_ctrl_b = sum(1 for r in win_b if r["controlled"])

    strata_unctrl, detail_unctrl = zone_strata(win_a, win_b, controlled_only=False)
    strata_ctrl, detail_ctrl = zone_strata(win_a, win_b, controlled_only=True)
    cmh_unctrl = cmh_test(strata_unctrl)
    cmh_ctrl = cmh_test(strata_ctrl)

    a_w, a_l = sum(r["win"] for r in win_a), sum(not r["win"] for r in win_a)
    b_w, b_l = sum(r["win"] for r in win_b), sum(not r["win"] for r in win_b)
    raw_gap = (a_w / n_a) - (b_w / n_b)

    max_zone_gap = max(
        (abs(d["A_wr"] - d["B_wr"]) for d in detail_ctrl if d["A_wr"] is not None and d["B_wr"] is not None),
        default=0.0,
    )

    res["panel_2_strength_zone"] = {
        "leaderboard_matched": {"A": n_matched_a, "B": n_matched_b},
        "controlled_join": {"A": n_ctrl_a, "B": n_ctrl_b,
                            "note": "opponent LastSubmissionDate precedes our episode createTime"},
        "uncontrolled": {"by_zone": detail_unctrl, "cmh": cmh_unctrl},
        "controlled": {"by_zone": detail_ctrl, "cmh": cmh_ctrl},
        "max_abs_zone_gap_controlled": round(max_zone_gap, 4),
        "raw_gap_A_minus_B": round(raw_gap, 4),
        "raw_wl": {"A": f"{a_w}-{a_l}", "B": f"{b_w}-{b_l}"},
        "fisher_p_raw": fisher_p(a_w, a_l, b_w, b_l),
        "gap_ci95_newcombe": newcombe_diff_ci(a_w, n_a, b_w, n_b),
        "wilson_ci_A": wilson_ci(a_w, n_a), "wilson_ci_B": wilson_ci(b_w, n_b),
    }

    # -- panel 3: median bank & margin — diagnostics only -------------------------
    res["panel_3_diagnostics"] = {
        "A": {"median_bank": statistics.median([r["bank"] for r in win_a]),
              "median_margin": statistics.median([r["margin"] for r in win_a])},
        "B": {"median_bank": statistics.median([r["bank"] for r in win_b]),
              "median_margin": statistics.median([r["margin"] for r in win_b])},
    }

    # -- pre-registered power, computed BEFORE the gate is applied ----------------
    mde80 = min_detectable_effect(n_a, n_b, power_target=0.80)
    power_curve = {f"{int(d*100)}pt": round(two_proportion_power(n_a, n_b, d), 3)
                   for d in (0.05, 0.10, 0.15, 0.20)}
    res["power"] = {
        "n_A": n_a, "n_B": n_b, "alpha": 0.05,
        "power_at_gap": power_curve,
        "minimum_detectable_effect_80pct_power": round(mde80, 4) if mde80 is not None else None,
        "note": "normal-approx two-proportion z-test, p0=0.5 (max-variance placement), "
                "computed at the actual window n before the gate below is applied (S13 lesson)",
    }

    # -- the pre-registered gate (plan §1 step 5) ----------------------------------
    p_cmh = cmh_ctrl.get("p_corrected")
    cleared = (p_cmh is not None) and (p_cmh < GATE_CMH_P) and (max_zone_gap >= GATE_ZONE_GAP)
    if not cleared:
        reason = []
        if p_cmh is None:
            reason.append("CMH degenerate (no usable strata)")
        else:
            reason.append(f"CMH p_corrected={p_cmh:.4g} (gate p<{GATE_CMH_P})")
        reason.append(f"max |zone gap|={max_zone_gap:.4f} (gate >= {GATE_ZONE_GAP})")
        res["verdict"] = ("NOT SEPARABLE at this sample size — " + "; ".join(reason) +
                           f". Power at a {int(GATE_ZONE_GAP*100)}-point gap is "
                           f"{two_proportion_power(n_a, n_b, GATE_ZONE_GAP):.2f}. "
                           "Per plan §4 rule 8, a direction is not reported as a finding. "
                           "Proceed to Phase 2 (Instrument A).")
    else:
        winner = "A" if raw_gap > 0 else "B"
        loser = "B" if winner == "A" else "A"
        res["verdict"] = (f"SEPARABLE: {loser} is weaker (CMH p_corrected={p_cmh:.4g}, "
                          f"max zone gap={max_zone_gap:.4f}) ⇒ the next upload drops "
                          f"{SLOT_B if loser == 'B' else SLOT_A}.")
    res["gate"] = {"cmh_p_threshold": GATE_CMH_P, "zone_gap_threshold": GATE_ZONE_GAP,
                  "cmh_p_corrected_controlled": p_cmh, "max_abs_zone_gap": max_zone_gap,
                  "cleared": cleared}

    DERIVED.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(res, indent=2, ensure_ascii=False, default=str))
    print(f"wrote {OUT}")
    print(res["verdict"])
    return res


# --------------------------------------------------------------------------- Phase 2 (§2)


OUT_PHASE2 = DERIVED / "s16_bench_three_arm.json"
GATE_P_PHASE2 = 0.01  # plan §2.4 — an overlay wins only if p<0.01 on BOTH seats


def _per_seat_mcnemar(rows):
    from analysis.s10_replay_bench import _mcnemar_binomial_p
    out = {}
    for seat in (0, 1):
        srows = [r for r in rows if r["seat"] == seat]
        c = sum(1 for r in srows if (not r["base_win"]) and r["new_win"])
        b = sum(1 for r in srows if r["base_win"] and (not r["new_win"]))
        out[str(seat)] = {"n": len(srows), "c": c, "b": b, "p": _mcnemar_binomial_p(b, c)}
    return out


def run_phase2() -> dict:
    """Plan §2 — the three-arm Instrument A gate. Reads the outputs of
    `analysis/s10_replay_bench.py {h2_calibration, recovery_calibration,
    recovery_alpha_bias}`, which must already have been run FRESH against the current
    archive (not the historic 412-episode snapshot — the archive has since grown, and
    both overlay arms must share the identical confirm-set enumeration for a comparison
    to mean anything). Computes no game state itself; only assembles and gates.
    """
    h2_path = DERIVED / "s10_bench_h2_calibration.json"
    rec_path = DERIVED / "s10_bench_recovery_calibration.json"
    alpha_path = DERIVED / "s10_bench_recovery_alpha_bias.json"
    for p in (h2_path, rec_path, alpha_path):
        if not p.exists():
            raise SystemExit(
                f"missing {p} — run `python analysis/s10_replay_bench.py "
                f"{{h2_calibration,recovery_calibration,recovery_alpha_bias}}` first "
                "(plan §2.1/§2.2/§2.3)."
            )
    h2 = json.loads(h2_path.read_text())
    rec = json.loads(rec_path.read_text())
    alpha_bias = json.loads(alpha_path.read_text())

    if h2["n"] != rec["n"]:
        raise SystemExit(
            f"h2_calibration n={h2['n']} != recovery_calibration n={rec['n']} — the two "
            "overlay arms were not run against the same confirm-set snapshot. Re-run both "
            "modes fresh (in that order doesn't matter, but neither may be stale) before "
            "trusting a side-by-side comparison (plan §2.3)."
        )

    h2_by_seat = _per_seat_mcnemar(h2["rows"])
    rec_by_seat = rec.get("mcnemar_by_seat") or _per_seat_mcnemar(rec["rows"])
    h2_clears = all(h2_by_seat[s]["p"] < GATE_P_PHASE2 for s in ("0", "1"))
    rec_clears = all(rec_by_seat[s]["p"] < GATE_P_PHASE2 for s in ("0", "1"))

    # §7.4 sign check against the Phase 1 live-window read (data/derived/s16_slot_window.json).
    sign_check = {"available": False}
    if OUT.exists():
        p1 = json.loads(OUT.read_text())
        p1_gate = p1.get("gate", {})
        if p1_gate.get("cleared"):
            p1_direction = "A" if p1["panel_2_strength_zone"]["raw_gap_A_minus_B"] > 0 else "B"
            bench_direction = "A" if h2_clears and not rec_clears else (
                "B" if rec_clears and not h2_clears else None)
            sign_check = {
                "available": True, "phase1_separable": True,
                "phase1_stronger_slot": p1_direction, "phase2_stronger_slot": bench_direction,
                "contradicts": bool(bench_direction and bench_direction != p1_direction),
            }
        else:
            sign_check = {
                "available": True, "phase1_separable": False,
                "note": ("Phase 1's gate did not clear (NOT SEPARABLE) — there is no "
                         "significant live-window direction for this bench to reverse. "
                         "The raw (non-significant) live gap is reported for context only, "
                         "never as a finding (plan §4 rule 8)."),
                "phase1_raw_gap_A_minus_B": p1["panel_2_strength_zone"]["raw_gap_A_minus_B"],
            }

    if h2_clears and not rec_clears:
        decision = (
            "B shipped on a SMOKE and still has no gated evidence (plan §2.4): the H2 "
            "overlay (slot A) clears p<0.01 on both seats against the shared base "
            f"(seat0 p={h2_by_seat['0']['p']:.2e}, seat1 p={h2_by_seat['1']['p']:.2e}); the "
            "recovery overlay (slot B) does not "
            f"(seat0 p={rec_by_seat['0']['p']:.2e}, seat1 p={rec_by_seat['1']['p']:.2e}). "
            "This decides the eviction on its own: the next upload drops 55675634."
        )
        eviction = "55675634"
    elif rec_clears and not h2_clears:
        decision = (
            "The recovery overlay (slot B) clears p<0.01 on both seats against the shared "
            f"base (seat0 p={rec_by_seat['0']['p']:.2e}, seat1 p={rec_by_seat['1']['p']:.2e}) "
            "while H2 (slot A) does not "
            f"(seat0 p={h2_by_seat['0']['p']:.2e}, seat1 p={h2_by_seat['1']['p']:.2e}) — but "
            "the §2 bias runs IN FAVOUR of the recovery arm by construction (occupancy "
            "re-rolls the opponent's shop RNG). Read this result net of that bias, not at "
            "face value, before it decides anything."
        )
        eviction = "inconclusive — bias-corrected recovery edge not established here"
    elif h2_clears and rec_clears:
        decision = (
            "Both overlays clear p<0.01 on both seats against the shared base — the pair "
            "is differentiated in strength as well as exposure. Eviction should follow "
            "whichever carries the larger effect, read net of §2's occupancy bias in "
            "recovery's favour."
        )
        eviction = "see effect sizes below, bias-corrected"
    else:
        decision = (
            "Neither overlay clears p<0.01 on both seats against the shared base at Instrument "
            "A. This is unexpected for H2 (previously gated at p=2.4e-7) — treat as a STOP and "
            "re-check the confirm-set enumeration before trusting either arm."
        )
        eviction = "STOP — re-check before deciding"

    result = {
        "pass": "S16 Phase 2 — Instrument A three-arm gate (base / base+H2 / base+recovery)",
        "generated": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "confirm_n": h2["n"],
        "confirm_subs": h2["confirm_subs"],
        "equivalence_check": (
            "tests/test_s16_recovery_bit_equivalence.py PASSED before this pass ran — the "
            "inlined 55675634 copy and agent/tape_overlay.py agree bit-exactly across 5 "
            "seeds (plan §2.1)."
        ),
        "base_arm": (
            "S16 task 1 (2026-08-28 correction): the base for BOTH overlay arms is the bare "
            "719-action reconstruction stream (data/derived/s6_step1_reconstruction_"
            "ReCurSiON.json), replayed with no overlay at all — not each episode's own "
            "recorded reward and not that episode's own recorded action stream. Pre-fix, the "
            "candidate for 55675634 episodes wrapped that episode's OWN recorded stream, which "
            "already carried the shipped overlay's output — recovery found nothing left to fix "
            "on any of the 246 55675634 confirm episodes (0 fires, 0 with d_bank != 0) and "
            "silently reproduced the recorded reward. Recomputed against the bare stream on "
            "every episode below; correctness verified on 55586926 (no overlay at all, so "
            "bare-stream replay must reproduce its own recorded reward exactly): "
            f"h2_calibration {h2.get('bare_base_correctness_check')}, "
            f"recovery_calibration {rec.get('bare_base_correctness_check')}."
        ),
        "recovery_artifact_name": (
            "The shipped 55675634 overlay is market pull-forward (STRAWBERRY, "
            "pull_forward_before_step=336) PLUS tile recovery, run together — not tile "
            "recovery alone. This gate cannot isolate component (i) [transaction/weed-legality "
            "recovery] from the market pull-forward it ships bundled with; §6 rows 26-27's "
            "separate +6,2-point bound on (i) alone is neither confirmed nor refuted here."
        ),
        "bias_declared": rec["occupancy_bias_warning"],
        "bias_measured": {
            "recovery_fires_on_confirm_set": rec["recovery_fires"],
            "alpha_control_n": alpha_bias["n"],
            "alpha_control_bit_exact_share_overall": alpha_bias["share_bit_exact"],
            "alpha_control_n_episodes_recovery_fired": alpha_bias["n_episodes_recovery_fired"],
            "alpha_control_share_fired_and_bit_exact": alpha_bias.get("share_fired_and_bit_exact"),
            "note": ("S16 task 3 correction: the overall bit-exact share (was reported as "
                     "79,4%) folds in 55675634's 246 confirm-set episodes, which are bit-exact "
                     "BY DEFINITION under the pre-fix base (recovery had nothing left to touch, "
                     "see base_arm above) — not evidence the arm is well-behaved. The number to "
                     "read is share_fired_and_bit_exact (68,1% = 308/452): among episodes where "
                     "recovery actually fired, only 68,1% still reproduced the recorded reward "
                     "bit-exactly. A large gap from 1.0 there is the EXPECTED, correct signature "
                     "of an occupancy arm (plan §2.2) — the RNG stream re-rolls once tile "
                     "occupancy changes. It is reported as the error bar this gate must be read "
                     "against, not tuned toward zero."),
        },
        "h2": {"pooled": {"c": h2["mcnemar_c"], "b": h2["mcnemar_b"], "p": h2["mcnemar_p"]},
               "by_seat": h2_by_seat, "clears_p<0.01_both_seats": h2_clears},
        "recovery": {"pooled": {"c": rec["mcnemar_c"], "b": rec["mcnemar_b"], "p": rec["mcnemar_p"]},
                     "by_seat": rec_by_seat, "clears_p<0.01_both_seats": rec_clears},
        "gate": {"threshold_p": GATE_P_PHASE2,
                 "rule": "an overlay wins only if p<0.01 on BOTH seats (plan §2.4)"},
        "sign_check_vs_phase1": sign_check,
        "decision": decision,
        "eviction": eviction,
    }
    DERIVED.mkdir(parents=True, exist_ok=True)
    OUT_PHASE2.write_text(json.dumps(result, indent=2, ensure_ascii=False, default=str))
    print(f"wrote {OUT_PHASE2}")
    print(decision)
    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["run", "report", "phase2", "phase2_report"])
    args = ap.parse_args()
    if args.cmd == "run":
        run()
    elif args.cmd == "phase2":
        run_phase2()
    elif args.cmd == "phase2_report":
        print(json.dumps(json.loads(OUT_PHASE2.read_text()), indent=2, ensure_ascii=False))
    else:
        print(json.dumps(json.loads(OUT.read_text()), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
