# Kaggriculture Agent

An autonomous agent for [Kaggriculture](https://www.kaggle.com/competitions/kaggriculture), a Kaggle
simulation competition where two players compete on a shared farm board to maximize their bank
at the end of a season — planting and harvesting crops, raising livestock, and trading in a
dynamic, shared market.

This repo holds the submission agent, a local evaluation harness for measuring it head-to-head
against baselines, and the analysis tooling used to close the gap between local results and the
live ladder.

## Architecture

Each in-game day the agent runs a **plan → schedule → execute** loop:

- **`agent/planner.py`** — reads the current `Snapshot` (crops, animals, market, hands) and
  produces a `DayPlan`: what to plant, water, harvest, buy, and sell.
- **`agent/scheduler.py`** — turns the plan into a task ledger and assigns tasks to available
  hands (`agent/animal_slots.py` handles livestock-specific slotting).
- **`agent/executor.py`** — converts assigned tasks into the engine's per-turn action/order
  format, including market orders.
- **`agent/receipts.py`** — reconciles the *expected* post-action state against what the engine
  actually returns, so silent execution failures surface immediately instead of being measured
  as strategy loss.

`agent/policy.py` wires this together into the single `agent(obs, configuration)` callable the
Kaggle loader expects; `main.py` is the packaged submission entrypoint.

Currently Top 18%

## Repository layout

| Path | Contents |
|---|---|
| `agent/` | The submission itself — planner, scheduler, executor, state parsing, config/constants |
| `harness/` | Local evaluation CLI — play single episodes, compare agents over many seeds, profile timing, render reports |
| `analysis/` | One-off scripts that turn replays / ladder downloads into diagnostics (kept for reproducibility, not re-run on a schedule) |
| `tests/` | Guard tests for the agent, engine-fact tripwires, and harness unit tests |
| `engine_reference/` | Read-only mirror of the installed `kaggle-environments` engine, used for line-accurate references in docs (never imported by tests or the agent) |
| `docs/` | Curated engine/market reference and dated meta/ladder snapshots — see [`docs/INDEX.md`](docs/INDEX.md) |
| `ROADMAP.md` | Strategy, measurement protocol, and the current hypothesis list |
| `main.py` | Kaggle submission entrypoint (`tar -czf submission.tar.gz main.py agent/`) |

Generated artifacts — episode replays, gate/comparison results, versioned agent checkpoints,
scraped datasets, and Kaggle notebook exports — are produced locally by the harness and analysis
scripts and are intentionally not tracked in this repo (see `.gitignore`); they're large,
regenerable, and not needed to read or run the code.

## Getting started

```bash
pip install -r requirements-dev.txt

# Run one episode between two agents (a file path, or "starter" for the built-in baseline)
python -m harness.cli play main.py main.py --seed 0

# Compare two agents over a range of seeds
python -m harness.cli compare main.py main.py --seeds 0-23 --out runs/demo

# Profile per-turn timing
python -m harness.cli profile main.py --seed 0

python -m pytest tests/
```

## Status

This is an active competition entry. Strategy, measurement protocol, carried-forward findings, and
the current hypothesis list all live in one place: [`ROADMAP.md`](ROADMAP.md). Start at
[`docs/INDEX.md`](docs/INDEX.md) to find anything else.

*(`docs/MASTERPLAN.md` and `current_phase.md` were retired on 2026-08-11 in favour of that single
roadmap; their history is in git.)*

## License

[MIT](LICENSE)
