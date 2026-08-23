#!/usr/bin/env python3
"""S9 K10 — the foresight-free, shed-respecting test of H2, run as a REAL replay.

Not a stream transform against a frozen inventory path: our seat gets an ONLINE agent that
carries the recorded tape and applies the H2 floor guard against the live market it actually
faces; the opponent seat gets its own recorded stream; the seed is the recorded seed. That is
Instrument A with one side swapped (`docs/plans/s9_liquidation_heuristics.md` §5).

Nothing here imports `agent/` — the overlay lives in this file, exactly like `tape_agent.py`.

Two rule variants, because the plan's wording and the mechanism disagree:

  `naive`  — the plan as written: skip the tape's SELL while `market_price(p, inv) < F`.
             Reads the price BEFORE the tape's own order walks it down, so it cannot see a
             batch that starts at $120 and ends at $1.
  `tail`   — sell the head of the batch that prices at or above F, defer only the tail, and
             re-sell at the FIRST later step where the price is back at or above F.
             Same information, no foresight; `market_price` is a pure function of inventory.
  `patient`— identical deferral, but re-sells ONLY when forced (hold age > D days, or
             step >= FORCE_STEP). This is the "let the town absorb" mechanism at full
             strength: it spends the entire recovery window instead of taking the first
             price that clears the floor. Still zero foresight.

Baseline = the recorded rewards (the alpha control replays them at 0,0000%).

Output: data/derived/s9_h2_k10_<variant>.json
"""
from __future__ import annotations

import json
import sys
from concurrent.futures import ProcessPoolExecutor
from hashlib import sha256
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "engine_reference"))

import kaggriculture as K  # noqa: E402
from analysis.s8_replay_io import SUBMISSIONS, ladder_episodes, our_seat  # noqa: E402
from analysis.tape_agent import make_tape_agent  # noqa: E402
from harness.play import play  # noqa: E402

PASS = {"farmer": ["PASS"], "hands": [], "market": []}
TPD = 24

# H2 parameters as corrected in the plan (§3)
F = 25                 # STRAWBERRY floor
D_DAYS = 4             # max hold age
H_MAX = 12             # shed-safe hold cap (min over 253 of free boundary capacity is 16)
FORCE_STEP = 686       # NOT 690: our queue is at the 10-order cap at step 696 in every episode
FIRST_DAY = 22         # P2 protects early strawberry liquidation
PRODUCT = "STRAWBERRY"


def dev_split(team: str) -> bool:
    """Team-disjoint 60/40 split (plan §5). True = dev."""
    return int(sha256(team.encode()).hexdigest(), 16) % 100 < 60


def _sellable_above_floor(inv: int, q: int) -> int:
    """How many of q units price at or above F, walking the engine's own curve (:652 — a $1
    sale adds no inventory, but that only happens far below F)."""
    n = 0
    for j in range(q):
        if K.market_price(PRODUCT, inv + j) < F:
            break
        n += 1
    return n


def make_h2_agent(stream, variant: str, stats: dict):
    held = {"units": 0, "since_day": None}

    def agent(obs, configuration=None):
        t = obs["step"]
        base = stream[t] if t < len(stream) else PASS
        day = t // TPD
        inv = obs["market"]["inventory"][PRODUCT]
        shed = obs["private"]["shed"].get(PRODUCT, 0)
        out = []
        for od in list(base.get("market") or []):
            is_target = (isinstance(od, list) and len(od) >= 3 and od[0] == "SELL"
                         and od[1] == PRODUCT and day >= FIRST_DAY and t < FORCE_STEP)
            if not is_target:
                out.append(od)
                continue
            q = int(od[2])
            keep = q if variant == "naive" else _sellable_above_floor(inv, q)
            if variant == "naive":
                keep = 0 if K.market_price(PRODUCT, inv) < F else q
            room = max(0, H_MAX - held["units"])
            defer = min(q - keep, room)
            if defer > 0:
                if held["units"] == 0:
                    held["since_day"] = day
                held["units"] += defer
                stats["deferred"] += defer
                stats["defer_events"] += 1
            if q - defer > 0:
                out.append([od[0], od[1], q - defer])

        if held["units"] > 0:
            forced = (t >= FORCE_STEP) or (day - held["since_day"] > D_DAYS)
            above = K.market_price(PRODUCT, inv) >= F
            if forced or (above and variant != "patient"):
                qty = min(held["units"], shed)
                if qty > 0 and len(out) <= 9:
                    out.append(["SELL", PRODUCT, qty])
                    stats["resold"] += qty
                    stats["resell_events"] += 1
                    held["units"] = 0
                    held["since_day"] = None
                elif qty <= 0:
                    stats["lost_to_shed"] += held["units"]
                    held["units"] = 0
                    held["since_day"] = None
                elif forced:
                    stats["blocked_by_cap"] += 1
        stats["held_final"] = held["units"]
        return {"farmer": base.get("farmer", ["PASS"]),
                "hands": base.get("hands", []),
                "market": out[:10]}

    return agent


def _streams(steps):
    return [[(steps[i + 1][seat].get("action") or dict(PASS)) for i in range(len(steps) - 1)]
            for seat in (0, 1)]


def run_one(args):
    sub, eid, teams, rewards, seed, steps, variant = args
    seat = our_seat(teams)
    st = _streams(steps)
    stats = dict(deferred=0, resold=0, defer_events=0, resell_events=0,
                 lost_to_shed=0, blocked_by_cap=0, held_final=0)
    cand = make_h2_agent(st[seat], variant, stats)
    a, b = (cand, make_tape_agent(st[1])) if seat == 0 else (make_tape_agent(st[0]), cand)
    r = play(a, b, seed=seed, record=False, metrics=False, strict=False)
    us, opp = r.rewards[seat], r.rewards[1 - seat]
    base_us, base_opp = rewards[seat], rewards[1 - seat]
    return dict(submission=sub, episode_id=eid, opponent=teams[1 - seat], seat=seat,
                base_us=base_us, base_opp=base_opp, new_us=us, new_opp=opp,
                base_win=base_us > base_opp, new_win=us > opp,
                d_bank=us - base_us, clean=r.clean, stats=stats)


def main(variant="tail", limit=None, split="dev"):
    jobs = []
    for sub in SUBMISSIONS:
        for eid, m in ladder_episodes(sub):
            seat = our_seat(m["teams"])
            if seat is None:
                continue
            opp = m["teams"][1 - seat]
            in_dev = dev_split(opp)
            if (split == "dev") != in_dev and split != "all":
                continue
            jobs.append((sub, eid, m["teams"], m["rewards"], m["seed"], m["steps"], variant))
            if limit and len(jobs) >= limit:
                break
        if limit and len(jobs) >= limit:
            break
    print(f"{variant}/{split}: {len(jobs)} episodes", flush=True)
    rows = []
    with ProcessPoolExecutor() as ex:
        for i, row in enumerate(ex.map(run_one, jobs), 1):
            rows.append(row)
            if i % 20 == 0:
                print(f"  {i}/{len(jobs)}", flush=True)
    out = ROOT / "data" / "derived" / f"s9_h2_k10_{variant}_{split}.json"
    out.write_text(json.dumps(rows))
    print("wrote", out)


if __name__ == "__main__":
    v = sys.argv[1] if len(sys.argv) > 1 else "tail"
    lim = int(sys.argv[2]) if len(sys.argv) > 2 and sys.argv[2] not in ("", "0", "none") else None
    sp = sys.argv[3] if len(sys.argv) > 3 else "dev"
    main(v, lim, sp)
