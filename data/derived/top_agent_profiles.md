# Top-decile replay profile vs v1b (plan.md §1.5.5)

Top-decile teams: **21** (winrate n>=8, Wilson lower bound, top 10%). Extracted from **662** (episode, seat) rows.

> Replays used strictly as target curve / diagnostic (MASTERPLAN §3.4, Open #11). No trajectory copying, no BC/IL prior — only aggregate per-day state.

## (i) Quadrant acquisition day (median across top-decile episodes)

| Quadrant # | median day | n episodes |
|---|---|---|
| 1 | 0.0 | 662 |
| 2 | 9 | 649 |
| 3 | 11 | 473 |
| 4 | 12 | 211 |

## (ii) Animal species acquired + median day

| Species | median first day | n episodes (out of total) |
|---|---|---|
| COW | 0.0 | 566 / 662 |
| GOOSE | 12 | 97 / 662 |
| SHEEP | 5.0 | 368 / 662 |

## plan.md §5.1 decision: land vs animals first

Median day of 1st animal (any species): **0** (n=593). Median day of 1st extra quadrant (beyond starting NW): **9** (n=649).

**Decision (v1d -> v1c, animals before land)**: top-decile teams get their first animal at day 0, before their first extra quadrant at day 9 — per the §5.1 criterion, the order reverses to v1d then v1c.

## (iii) Bank at day 10/20/30 — top-decile median vs v1b

| Day | top-decile median bank | v1b bank | gap |
|---|---|---|---|
| 10 | 735.5 | 1069.0 | -333.5 |
| 20 | 25912.5 | 20054.0 | 5858.5 |
| 30 | 86073.0 | 22311.0 | 63762.0 |

## Full per-day median target curve

See [top_agent_profiles.csv](top_agent_profiles.csv) (30 day rows, 15 columns: money/hands/tiles per crop/animals per species/unlocked_quadrants, median across all top-decile (episode, seat) rows for that day).

Each column is an **independent per-day median** across all 662 (episode, seat) rows — the row at a given day is not a single coherent episode's trajectory (e.g. `animals_total` need not equal the sum of the per-species columns for that same row). Use it as a target curve/diagnostic per column, not as a literal reference playthrough.