# Kaggriculture Agent

A competition-analysis-and-engineering project for [Kaggriculture](https://www.kaggle.com/competitions/kaggriculture),
a Kaggle simulation where two players compete on a shared farm board to maximize their end-of-season
bank — planting and harvesting crops, raising livestock, and trading in a dynamic shared market.

Hand-written heuristics plateaued early (around a ~700 rating), so I stopped tuning them and built
something more general instead: **a system that reconstructs strong policies from public episode
replays, measures them rigorously against a local ladder, and improves them with my own closed-loop
overlays.** That system reached roughly the **top ~18%** of the leaderboard.

The engineering in this repo — the reconstruction pipeline, the evaluation harness, the acceptance
gates, and the overlays — is the substance of the project. (The *base* policy a submission replays is
reconstructed from a top-ranked team's public replays via majority-vote decoding, with replay
**fidelity validated** before use; see [Two agents](#two-agents) and `ROADMAP.md`. The original
contribution is the system around that base, not the base farming strategy itself.)

## What's actually here

- **A reconstruction pipeline** (`analysis/build_*_submission.py`, `analysis/s6_step1_reconstruct.py`)
  — decode a strong policy's action stream from many public replays by majority vote, validate it by
  replaying against the donor's *own* recorded opponents in their *own* recorded towns (a fidelity
  check that catches state-adaptive policies a fixed tape can't carry), and package it as a
  self-contained `main.py` with no runtime dependency on `agent/`.
- **Closed-loop overlays** (`agent/tape_overlay.py`) — my own micro-strategies layered on top of the
  replayed base: *tile recovery* (when the tape's action would be a silent no-op on the live board —
  a weed where it expected a plant, an already-watered tile — substitute the cheapest legal action)
  and *tail liquidation* (defer the sub-floor tail of a strawberry batch and re-sell once the market
  price recovers). Both are proven **bit-exact** against a reference implementation and gated on
  win/loss before shipping.
- **A local evaluation harness** (`harness/`) — a `play / compare / profile / report` CLI that runs
  head-to-head episodes over seed ranges, builds opponent benches from downloaded replays, and
  applies structural + priced-loss acceptance gates with deterministic, reproducible replay.
- **A measurement discipline** — every change is priced in rating points, gated on wins first, and
  checked for bit-exactness; dead ends are recorded with the number that killed them (`ROADMAP.md`).

## Two agents

The repo contains two distinct agents, kept separate on purpose:

1. **The heuristic reference agent** (`agent/policy.py` → `main.py`). A readable, fully-tested
   `plan → schedule → execute` farming agent. This is the code the tests and the harness baseline
   exercise, and the easiest place to read how the game works. It is the ~700-rating lineage — kept
   as the legible reference, not as the competitive entry.
   - **`agent/planner.py`** reads the `Snapshot` and produces a `DayPlan`;
   - **`agent/scheduler.py`** turns the plan into a task ledger and assigns it to hands;
   - **`agent/executor.py`** converts assigned tasks into the engine's per-turn action/order format;
   - **`agent/receipts.py`** reconciles expected vs. actual post-action state so silent execution
     failures surface immediately.
2. **The shipped tape-overlay agent** (`agent/tape_overlay.py`, packaged by
   `analysis/build_tape_overlay_submission.py`). The reconstructed base policy plus the closed-loop
   overlays above, inlined into a self-contained `main.py`. This is what actually placed on the
   ladder.

## Repository layout

| Path | Contents |
|---|---|
| `agent/` | Both agents — the heuristic `plan→schedule→execute` reference and the shipped tape overlay, plus shared state parsing, config, and constants |
| `harness/` | Local evaluation CLI — play single episodes, compare agents over many seeds, profile timing, render reports, build opponent benches |
| `analysis/` | Reproducibility scripts — submission builders and the load-bearing diagnostics the tests exercise (superseded per-pass one-offs were pruned; they remain in git history, narrated in `docs/journal/`) |
| `tests/` | Guard tests for both agents, engine-fact tripwires, and harness unit tests (`pytest tests/` → 390 passing) |
| `engine_reference/` | Read-only mirror of the installed `kaggle-environments` engine, cited for line-accurate references in comments (never imported by tests or the agent) |
| `docs/` | Curated engine/market reference and dated meta/ladder snapshots — see [`docs/INDEX.md`](docs/INDEX.md); session narrative lives in [`docs/journal/`](docs/journal) |
| `ROADMAP.md` | Strategy, measurement protocol, and the current hypothesis list |
| `main.py` | The heuristic-agent submission entrypoint (`tar -czf submission.tar.gz main.py agent/`); the tape-overlay submission is a separate self-contained `main.py` emitted by the builder |

Generated artifacts — episode replays, gate/comparison results, versioned agent checkpoints, scraped
datasets, and packaged submissions — are produced locally by the harness and analysis scripts and are
intentionally not tracked (see `.gitignore`); they're large, regenerable, and not needed to read or
run the code.

## Getting started

The submission itself needs nothing but the competition engine (`kaggle_environments`), which Kaggle
provides at runtime. To run the harness and tests locally:

```bash
pip install -r requirements-dev.txt

# Run one episode between two agents (a file path, or "starter" for the built-in baseline)
python -m harness.cli play main.py main.py --seed 0

# Compare two agents over a range of seeds
python -m harness.cli compare main.py main.py --seeds 0-23 --out runs/demo

# Profile per-turn timing
python -m harness.cli profile main.py --seed 0

python -m pytest tests/     # 390 tests, ~2.5 min
```

## Status

An active competition entry. Strategy, measurement protocol, carried-forward findings, and the
current hypothesis list all live in [`ROADMAP.md`](ROADMAP.md). Start at [`docs/INDEX.md`](docs/INDEX.md)
to find anything else.

## License

[MIT](LICENSE)
