#!/usr/bin/env python3
"""S9 K10 companion — the A8 bias check for the H2 counterfactual, plus the alpha control at scale.

The K10 result is carried by the OPPONENT's bank, not ours (dev, `tail`: our bank +$62 median,
theirs -$392, margin +$464). That makes the declared limit of Instrument A decisive rather than
cosmetic: the opponent's stream is open-loop, so if our change starves them of cash their own
`BUY_*` orders start failing and the measured margin is inflated in our favour.

So this runs BOTH sides of every dev episode twice - baseline (both recorded tapes) and candidate
(our seat overlaid) - at the recorded seed, with `_commit_unit` instrumented per seat, and reports

  * alpha control: does the baseline replay reproduce the recorded rewards? (must be exact)
  * A8: median(opp BUY_* refused units | candidate) - median(... | baseline)

Seat attribution is exact: `_process_market` is wrapped to register `id(farm) -> seat` for the
turn before delegating, so every `_commit_unit` call is attributed by identity, not inferred.

Output: data/derived/s9_h2_a8_<variant>.json
"""
from __future__ import annotations

import json
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import kaggle_environments.envs.kaggriculture.kaggriculture as ENG  # noqa: E402
from analysis.s8_replay_io import SUBMISSIONS, ladder_episodes, our_seat  # noqa: E402
from analysis.s9_h2_k10 import PASS, _streams, dev_split, make_h2_agent  # noqa: E402
from analysis.tape_agent import make_tape_agent  # noqa: E402
from harness.play import play  # noqa: E402

SEAT_OF_FARM: dict[int, int] = {}
TALLY = {"committed": [{}, {}], "refused": [{}, {}]}
_patched = False


def _install():
    """Idempotent, per-worker-process. Patches the INSTALLED engine (byte-identical to
    engine_reference, sha256 bc8a5487...), which is the module `kaggle_environments.make` uses."""
    global _patched
    if _patched:
        return
    real_pm, real_cu = ENG._process_market, ENG._commit_unit

    def pm(state, env):
        SEAT_OF_FARM.clear()
        for i, f in enumerate(state[0].observation.farms):
            SEAT_OF_FARM[id(f)] = i
        return real_pm(state, env)

    def cu(op, item, price, farm, private, market, shed_capacity=100):
        ok = real_cu(op, item, price, farm, private, market, shed_capacity)
        seat = SEAT_OF_FARM.get(id(farm))
        if seat is not None:
            d = TALLY["committed" if ok else "refused"][seat]
            k = f"{op}:{item}"
            d[k] = d.get(k, 0) + 1
        return ok

    ENG._process_market, ENG._commit_unit = pm, cu
    _patched = True


def _reset():
    for k in TALLY:
        TALLY[k][0].clear()
        TALLY[k][1].clear()


def _snapshot(seat):
    return {"committed": dict(TALLY["committed"][seat]), "refused": dict(TALLY["refused"][seat])}


def run_one(args):
    sub, eid, teams, rewards, seed, steps, variant = args
    _install()
    seat = our_seat(teams)
    opp = 1 - seat
    st = _streams(steps)

    _reset()
    rb = play(make_tape_agent(st[0]), make_tape_agent(st[1]), seed=seed,
              record=False, metrics=False, strict=False)
    base_opp_orders = _snapshot(opp)

    _reset()
    stats = dict(deferred=0, resold=0, defer_events=0, resell_events=0,
                 lost_to_shed=0, blocked_by_cap=0, held_final=0)
    cand = make_h2_agent(st[seat], variant, stats)
    a, b = (cand, make_tape_agent(st[1])) if seat == 0 else (make_tape_agent(st[0]), cand)
    rc = play(a, b, seed=seed, record=False, metrics=False, strict=False)
    cand_opp_orders = _snapshot(opp)

    def buys_refused(snap):
        return sum(v for k, v in snap["refused"].items() if k.startswith("BUY"))

    return dict(
        submission=sub, episode_id=eid, opponent=teams[1 - seat], seat=seat,
        recorded=[rewards[0], rewards[1]], base_replay=list(rb.rewards),
        alpha_exact=(list(rb.rewards) == [rewards[0], rewards[1]]),
        base_us=rb.rewards[seat], base_opp=rb.rewards[opp],
        new_us=rc.rewards[seat], new_opp=rc.rewards[opp],
        base_buy_refused=buys_refused(base_opp_orders),
        cand_buy_refused=buys_refused(cand_opp_orders),
        base_opp_committed=sum(base_opp_orders["committed"].values()),
        cand_opp_committed=sum(cand_opp_orders["committed"].values()),
        clean=(rb.clean and rc.clean), stats=stats,
    )


def main(variant="tail", split="dev", limit=None):
    jobs = []
    for sub in SUBMISSIONS:
        for eid, m in ladder_episodes(sub):
            seat = our_seat(m["teams"])
            if seat is None:
                continue
            if split != "all" and dev_split(m["teams"][1 - seat]) != (split == "dev"):
                continue
            jobs.append((sub, eid, m["teams"], m["rewards"], m["seed"], m["steps"], variant))
            if limit and len(jobs) >= limit:
                break
        if limit and len(jobs) >= limit:
            break
    print(f"A8 {variant}/{split}: {len(jobs)} episodes x 2 replays", flush=True)
    rows = []
    with ProcessPoolExecutor() as ex:
        for i, row in enumerate(ex.map(run_one, jobs), 1):
            rows.append(row)
            if i % 20 == 0:
                print(f"  {i}/{len(jobs)}", flush=True)
    out = ROOT / "data" / "derived" / f"s9_h2_a8_{variant}_{split}.json"
    out.write_text(json.dumps(rows))
    print("wrote", out)


if __name__ == "__main__":
    v = sys.argv[1] if len(sys.argv) > 1 else "tail"
    sp = sys.argv[2] if len(sys.argv) > 2 else "dev"
    lim = int(sys.argv[3]) if len(sys.argv) > 3 and sys.argv[3] not in ("", "0", "none") else None
    main(v, sp, lim)
