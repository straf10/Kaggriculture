# Kaggriculture Episodes

Full episode replays and results from the [Kaggriculture](https://www.kaggle.com/competitions/kaggriculture)
simulation competition, collected from Kaggle's public episode API. One episode is one 720-turn
farming game (a turn is an in-game hour; a game is a 30-day season). Refreshed daily by a
scheduled notebook.

## Files

- `episodes.csv` — one row per episode: `episode_id`, `create_time`/`end_time`, `state`,
  `type` (`EPISODE_TYPE_PUBLIC` = ladder game, `EPISODE_TYPE_VALIDATION` = self-play check;
  filter those out for strength analysis), and per seat: `sub_N`, `team_N`, `bank_N`
  (final coins — the game score), `rating_N` (skill rating right after the game).
- `agents.csv` — the per-agent view: `episode_id`, `agent_index`, `submission_id`, `team_id`,
  `final_bank`, `rating_after`.
- `replays.parquet` — every full replay in one table: `episode_id` plus `replay_json`,
  the replay exactly as the episode CDN serves it (`steps` — 720 turns, `rewards`,
  engine `configuration`). Each `steps[t][seat]` holds that seat's `observation` and
  `action`. Zstd-compressed, so ~20 MB stands in for gigabytes of raw JSON.
- `teams.csv` — `team_id`, `team_name`, `ladder_score`, `last_submission`: the join that puts
  readable names on every chart (episode rows carry ids only).
- `episode_features.csv` — one row per (episode, seat), parsed out of every replay so you don't
  have to: `final_money`, `peak_crew`, `total_hires`, `first_land_day`, `elbow_day` (first day
  the bank crosses 10% of its final value), `tiles_planted`, `plants_<crop>` per crop, and
  `price_<product>_min`/`_max` for the episode's shared market. Hires are read from farm state
  (`hires_today`), not submitted orders — the engine rejects orders once money runs short.
- `state.json` — crawler state; makes updates incremental.
- `scrape.py`, `repack.py`, `teams.py`, `features.py` — the collector chain. Everything here
  reproduces from public endpoints.

Not every episode has its replay downloaded yet (the crawl is politely rate-limited), and a
brand-new submission can lag one update behind. Current counts live in the version notes.

## Rights

The games belong to their players and to Kaggle — this dataset only collects and reshapes
public episode data (the same tables Kaggle publishes in Meta Kaggle). Environment:
[kaggle-environments](https://github.com/Kaggle/kaggle-environments).
