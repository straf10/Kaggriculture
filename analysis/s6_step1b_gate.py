#!/usr/bin/env python3
"""S6 step 1b, item 4 — bank sweep WITH its realised shop draw printed (R21), per seed set.

The Phase 0 report's 24-0-0 headline (§2.1.4) never printed the shop draw it actually sampled
(correction 3 / R21), and that is the number the ship decision rests on: realised premium price
moves 5-18x with the town's draw (§4.1b), so a bank margin is only interpretable against the draw
that produced it. This runs the reconstruction vs the raw Valmorlee tape (the incumbent, per the
brief) over a seed set, both seats (§2.1.1), and reports the bank record, the per-seat split, AND
`shop_draw_summary` (R21) for that exact seed set.

The formal GO/metric decision is the separate `harness.cli compare --metrics` run; this is the
R21 companion the brief requires for *every* seed set including the bank sweep.

Usage:
    python analysis/s6_step1b_gate.py --seeds 0-11      # SMOKE control
    python analysis/s6_step1b_gate.py --seed-set dev
    python analysis/s6_step1b_gate.py --seed-set holdout
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from harness.ladder import duel, shop_draw_summary  # noqa: E402
from harness.seeds import DEV_SEEDS, HOLDOUT_SEEDS, SMOKE_SEEDS  # noqa: E402

RECON = "baselines/2026-08-17/tape_submissions/reconstruction_ReCurSiON/main.py"
VALMORLEE = "baselines/2026-08-16/tape_submissions/91456307_seat0/main.py"
DERIVED = ROOT / "data" / "derived"

SEED_SETS = {"smoke": SMOKE_SEEDS, "dev": DEV_SEEDS, "holdout": HOLDOUT_SEEDS}


def _parse_seeds(spec: str) -> list[int]:
    out: list[int] = []
    for part in spec.split(","):
        if "-" in part:
            lo, hi = part.split("-")
            out.extend(range(int(lo), int(hi) + 1))
        else:
            out.append(int(part))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds")
    ap.add_argument("--seed-set", choices=list(SEED_SETS))
    ap.add_argument("--label", default=None)
    args = ap.parse_args()
    if args.seed_set:
        seeds = list(SEED_SETS[args.seed_set])
        label = args.label or args.seed_set
    elif args.seeds:
        seeds = _parse_seeds(args.seeds)
        label = args.label or args.seeds
    else:
        raise SystemExit("give --seeds or --seed-set")

    run_dir = DERIVED / f"s6_step1b_gate_{label}"
    towns: list = []
    d = duel("ReCurSiON_recon", RECON, "Valmorlee_tape", VALMORLEE, seeds,
             shop_draw=True, run_dir=run_dir, towns=towns)

    print(f"=== bank sweep [{label}]  recon vs raw Valmorlee tape  "
          f"({len(seeds)} seeds x 2 seats = {d.games} games) ===")
    print(f"record (recon W-L-T): {d.wins_a}-{d.wins_b}-{d.ties}   errors: {d.errors}")
    print(f"mean margin (recon - tape): ${statistics.fmean(d.margins):,.0f}   "
          f"median margin: ${statistics.median(d.margins):,.0f}")
    print(f"per-seat: recon wins from seat0 {d.wins_a_by_seat[0]}/{d.games_by_seat[0]}, "
          f"seat1 {d.wins_a_by_seat[1]}/{d.games_by_seat[1]}")

    draw = shop_draw_summary(towns)
    print(f"\n--- R21 realised shop draw for [{label}] ({draw['episodes']} towns) ---")
    for product, s in draw["products"].items():
        print(f"  {product:<11} drain median {s['median']:>4.0f}  "
              f"[min {s['min']}, max {s['max']}]  "
              f"zero-drain towns {s['zero_drain_episodes']}/{draw['episodes']} "
              f"({s['zero_drain_episodes']/draw['episodes']:.0%})")

    out = {
        "label": label, "seeds": seeds, "games": d.games,
        "record": f"{d.wins_a}-{d.wins_b}-{d.ties}", "errors": d.errors,
        "mean_margin": statistics.fmean(d.margins), "median_margin": statistics.median(d.margins),
        "per_seat_wins": {"seat0": [d.wins_a_by_seat[0], d.games_by_seat[0]],
                          "seat1": [d.wins_a_by_seat[1], d.games_by_seat[1]]},
        "shop_draw": draw,
    }
    (DERIVED / f"s6_step1b_gate_draw_{label}.json").write_text(json.dumps(out, indent=1))
    print(f"\nwrote {DERIVED / f's6_step1b_gate_draw_{label}.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
