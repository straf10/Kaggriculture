# 44-46-strict-future-top-30-v22-price-impact

> Extracted by `analysis/nb_extract.py` from `notebooks/44-46-strict-future-top-30-v22-price-impact.ipynb`.
> Cell numbers below are the anchors cited elsewhere in the repo (e.g. MASTERPLAN's `viz cell 19` = cell 19 of the *visualized* notebook).

## cell [0] — markdown

# 44/46 Strict-Future Top-30 | v22 Price Impact

**A current complete route plus an order-only estimate of real nonlinear price damage.**

The public v21 route did not gradually lose because its mirror threshold became
slightly wrong. On episodes created after this candidate was frozen, that old
artifact won only **1/46**.
Refreshing the complete route reached
**36/46**; ranking
the route's already-planned SELLs by official price impact reached
**44/46**.

| Chronological gate | v22 | Seat 0 | Seat 1 |
|---|---:|---:|---:|
| development | **30/30** | 20/20 | 10/10 |
| untouched newest-two outer | **42/44** | 19/20 | 23/24 |
| episodes created after freeze | **44/46** | 20/20 | 24/26 |
| frozen `main.py`, exact game-level replay | **44/46** | 20/20 | 24/26 |

`44/46` is a local strict-future counterfactual replay result, **not an official
Public-LB score**. Replay opponents execute their recorded public trajectories
and do not react to our counterfactual policy.

```text
719-step current route
  + actor-local WEED transaction repair
  + official 1.32.4 price curve
  + SELL ranking inside existing SELL slots
  = no new SELL, no resized SELL, no moved BUY/HIRE slot
```

## cell [1] — markdown

## Machine-readable contribution card

```yaml
upstream_agent: Kaito v21.1 Conditional Memory
public_route_provenance: roma / submission 55299523 / episode 90473746 / seat 0
direct_public_inspiration: Rayk Kretzschmar, Findings from Zero to Top Meta
new_contribution:
  - refresh route on a 2026-08-07 Top-30 snapshot
  - independently transcribe the official 1.32.4 market curve
  - rank only existing SELL slots by quantity times self-induced quote drop
  - verify the frozen artifact game-by-game on episodes created after freeze
explicitly_rejected:
  - unconditional preemption
  - late state-incompatible route takeover
  - fertilizer dumping
runtime_identity_fields: []
runtime_opponent_private_fields: []
```

This card is intentionally easy for humans, forks, and retrieval agents to
parse. A downstream copy should preserve the upstream route and mechanism
citations, then state its own changed lines and independent evaluation window.

## cell [2] — markdown

## 1. Diagnosis: the route was stale, but route refresh was not enough

At the 2026-08-07 snapshot, the Top-30 boundary was **2910.4**. We downloaded
102 public episodes from the current scoring submissions under
`kaggle-environments==1.32.4` and kept time order.

Thirty real, complete fit-only routes were screened on the next trajectory for
each current team. The strongest unchanged routes were:

| Fit-only complete route | Development wins |
|---|---:|
| DECEM | **28/30** |
| roma | **28/30** |
| Mohit Rao | 25/30 |
| old public v21 | 2/30 |

DECEM and roma differ at only 18 of 719 turns. The DECEM source replay contains
a stochastic WEED detour around steps 663–671; roma preserves the clean shared
route at that point. The market-aware pair `roma-impact-slots` was therefore
frozen before the outer and later strict-future downloads.

The important decomposition on the later 46 cases is:

```text
old route + old market memory       1/46
current route, market unchanged    36/46
current route + price impact       44/46
```

Route refresh repaired the basin. The order controller supplied another eight
wins without changing production or inventory decisions.

## cell [3] — code

**output:**

```text
policy | wins | games | mean margin | win rate
0 | old public v21 | 1 | 46 | -7839.760870 | 0.021739
1 | current route only | 36 | 46 | 1838.173913 | 0.782609
2 | v22 price impact | 44 | 46 | 3508.934783 | 0.956522
```

**output:**

*[image omitted — see the notebook]*

## cell [4] — markdown

## 2. What the public forks taught us

Attribution and validation are separate questions. These are the public works
most relevant to this release:

| Notebook | What is strong | How v22 uses it |
|---|---|---|
| [Kaito v21.1 Conditional Memory](https://www.kaggle.com/code/kaitofukami/177-180-fresh-top-30-v21-1-conditional-memory) | exact public artifact and the route/memory baseline | upstream agent; now tested as a stale control |
| [Rayk — Findings from Zero to Top Meta](https://www.kaggle.com/code/raykkretzschmar/kaggriculture-findings-from-zero-to-top-meta) | unusually precise upstream byte/hash boundary; isolates one SELL-ranking substitution | direct inspiration for price-impact ranking; independently reimplemented here |
| [boatlee — Order-Safe Premium Control](https://www.kaggle.com/code/boatlee/v13-r3-top-meta-order-safe-premium-control) | quantity-conserving preemption and the warning not to move BUY/HIRE slots | v22 preserves every non-SELL slot, but rejects preemption without fresh gain |
| [fle3n — v21.1 No Preemption](https://www.kaggle.com/code/fleongg/kaggriculture-public-2830-4-v21-1-no-preemption) | narrow ablation showing repeated early SELL can decay | ordinary v22 turns create no SELL |
| [Desyat — 93% WR vs Kaito v21.1](https://www.kaggle.com/code/desyatio/93-wr-vs-kaito-s-v21-1-local-tuning-experiment) | clear terminal-only contribution boundary | retained as an adversarial idea, not promoted from version-specific evidence |
| [webcainiao — v21 Tactical Memory](https://www.kaggle.com/code/web3cainiao/kaggriculture-v21-tactical-memory) | explicit Kaito attribution | evidence that v21 became a population prior; not treated as independent validation |
| [Furina — What the Top Farms Do](https://www.kaggle.com/code/cjlcjlcjl/kaggriculture-what-the-top-farms-do-a-live-meta) | daily population drift and exact 1.32.x price-cliff warning | engine pin and a post-freeze time slice |
| [prvsiyan — The Moon Counts Melons](https://www.kaggle.com/code/prvsiyan/kaggriculture-frontier-the-moon-counts-melons) | market timing inside a converged production basin | market and route are ablated separately |

The public route embedded here is a real replay from team **roma**, submission
`55299523`, episode `90473746`, source seat `0`, action hash
`cd4380d55c4a13c2ed4fd0c9463268c5764599f7e3f58b91e960b49d7dfd5d77`.
That provenance is credited; it is not claimed as a newly invented production
plan. The contribution of this Notebook is the refreshed selection protocol,
the safe price-impact controller, rejected-branch evidence, and exact artifact
verification.

## cell [5] — markdown

## 3. Chronological protocol

```text
initial current-submission download (4 episodes per Top-30 team)
  oldest 1  -> route donor
  next 1    -> development / route + market selection
  newest 2  -> outer, unopened until roma-impact-slots was fixed

after the method was frozen
  download current episodes again
  retain EpisodeId > 90476046 only
  -> 46 team/seat cases from 33 newly arrived unique episodes
```

Top-vs-Top episodes can contribute one case for each public opponent, which is
why case counts exceed unique-episode counts. No team is selected by identity
at runtime. Both seats are scored separately; the strict-future split contains
20 candidate-seat-0 and 26 candidate-seat-1 games.

The later download was not used to tune a threshold or choose a new route. It
was used once to compare the already selected v22, the same route without the
market layer, and the old public artifact.

## cell [6] — markdown

## 4. Price impact, not unit price and not guessed identity

For an existing order `SELL item quantity`, define:

\[
I = q\,\max\left(0,\;p(s)-p(s+q)\right)
\]

where `s` is current shared market inventory and `p` is the official 1.32.4
quote function. This estimates how much quote damage our own order causes. A
large low-unit-price order can outrank a small expensive order when its
nonlinear market impact is larger.

The exact default price-floor distances from equilibrium are:

| product | units to the $1 floor |
|---|---:|
| WOOL | 59 |
| STRAWBERRY | 62 |
| MILK | 76 |
| MELON | 158 |

The score does **not** claim to know the opponent's current order. It is a
state-based risk ranking for the actions our route has already decided to take.

## cell [7] — code

**output:**

*[image omitted — see the notebook]*

## cell [8] — markdown

## 5. The order-slot safety contract

Suppose the complete route requests:

```python
[
    ["BUY_PRODUCT", "WHEAT", 2],
    ["SELL", "WHEAT", 20],
    ["HIRE"],
    ["SELL", "STRAWBERRY", 12],
]
```

If strawberry has larger self-impact, v22 returns:

```python
[
    ["BUY_PRODUCT", "WHEAT", 2],
    ["SELL", "STRAWBERRY", 12],
    ["HIRE"],
    ["SELL", "WHEAT", 20],
]
```

Only the contents of indices 1 and 3 changed. This matters because moving a
SELL ahead of a BUY/HIRE can change cash availability and create a different
production trajectory. v22 deliberately refuses that larger intervention.

Runtime invariants:

- same farmer and hand actions;
- same number of market orders;
- same SELL products and quantities;
- same non-SELL orders and positions;
- no ordinary-turn preemption;
- no opponent name, team id, submission id, episode id, or private shed.

## cell [9] — markdown

## 6. Failure audit and rejected local optima

The strict-future losses are intentionally not hidden:

```text
episode 90477635 | Seb (allegedly) | seat 1 | margin -2855
episode 90483794 | Seb (allegedly) | seat 1 | margin -5668
```

Both belong to the same six-hand opening family. It is a real
rock-paper-scissors signal:

- old v18 closed loop won only **2/49** current outer cases, and both wins were
  against that family;
- the current v22 route won **44/46**, and both losses were against it;
- changing to v18 at step 96 kept the same win count but broke accumulated
  state, dropping mean margin from `+3,524` to `-3,092`;
- five fixed alternate routes that beat one older episode went **0/2** on later
  episodes;
- targeted strawberry/wool/milk dumping did not improve unknown-seed wins;
- fertilizer dumping went **0/16** because fertilizer is production input.

These are examples of exactly the local optimization this release is trying to
avoid. None is in `main.py`. A future counter should learn a coherent opening
policy before step 0 or a true state-value bridge—not splice a complete route
after its inventory and labor assumptions are already false.

## cell [10] — markdown

## 7. Frozen artifact and reproducibility boundary

The final agent is **18,609 bytes**, contains 719 actions, uses
only the Python standard library, and has SHA-256:

`62fb5a5f66f0011092a2b51e3192879ba583d5d815d761f176091c615657147a`

The same bytes were imported and rerun on all 46 strict-future cases. Every
candidate reward, opponent reward, and win flag matched the selected research
policy exactly (`46/46` game rows).

The public Notebook embeds the production artifact and reproduces its byte
hash, compilation, archive membership, official price cliffs, and action-schema
smoke test. The Notebook image's installed game package is printed explicitly;
the reported replay research uses the official 1.32.4 schema rather than
treating a potentially lagged Notebook image as a score benchmark. The
multi-gigabyte replay download and route screen are summarized rather than
embedded. Episode boundaries, source artifact, rejected variants, and
fixed-vs-future result are reported so the scientific claim is narrower than
the submission claim.

Limitations remain:

- replay opponents do not react;
- an exact deterministic copy has symmetric logic;
- field/labor behavior is still mostly a complete route;
- public meta decay can occur within hours;
- `44/46` is not a promise of an official LB score.

## cell [11] — code

**output:**

```text
[92m18:00:10 - LiteLLM:WARNING[0m: get_model_cost_map.py:271 - LiteLLM: Failed to fetch remote model cost map from https://raw.githubusercontent.com/BerriAI/litellm/main/model_prices_and_context_window.json: [Errno -3] Temporary failure in name resolution. Falling back to local backup.
```

**output:**

```text
[kaggle_environments.envs.open_spiel_env.open_spiel_env] INFO: Successfully loaded OpenSpiel environments: 24.
[kaggle_environments.envs.open_spiel_env.open_spiel_env] INFO:    open_spiel_amazons
[kaggle_environments.envs.open_spiel_env.open_spiel_env] INFO:    open_spiel_backgammon
[kaggle_environments.envs.open_spiel_env.open_spiel_env] INFO:    open_spiel_checkers
[kaggle_environments.envs.open_spiel_env.open_spiel_env] INFO:    open_spiel_chess
[kaggle_environments.envs.open_spiel_env.open_spiel_env] INFO:    open_spiel_clobber
[kaggle_environments.envs.open_spiel_env.open_spiel_env] INFO:    open_spiel_coin_game
[kaggle_environments.envs.open_spiel_env.open_spiel_env] INFO:    open_spiel_coin_game_arena
[kaggle_environments.envs.open_spiel_env.open_spiel_env] INFO:    open_spiel_connect_four
[kaggle_environments.envs.open_spiel_env.open_spiel_env] INFO:    open_spiel_dark_hex
[kaggle_environments.envs.open_spiel_env.open_spiel_env] INFO:    open_spiel_gin_rummy
[kaggle_environments.envs.open_spiel_env.open_spiel_env] INFO:    open_spiel_go
[kaggle_environments.envs.open_spiel_env.open_spiel_env] INFO:    open_spiel_goofspiel
[kaggle_environments.envs.open_spiel_env.open_spiel_env] INFO:    open_spiel_hearts
[kaggle_environments.envs.open_spiel_env.open_spiel_env] INFO:    open_spiel_hex
[kaggle_environments.envs.open_spiel_env.open_spiel_env] INFO:    open_spiel_lines_of_action
[kaggle_environments.envs.open_spiel_env.open_spiel_env] INFO:    open_spiel_matching_pennies_3p
[kaggle_environments.envs.open_spiel_env.open_spiel_env] INFO:    open_spiel_oshi_zumo
[kaggle_environments.envs.open_spiel_env.open_spiel_env] INFO:    open_spiel_othello
[kaggle_environments.envs.open_spiel_env.open_spiel_env] INFO:    open_spiel_repeated_game
[kaggle_environments.envs.open_spiel_env.open_spiel_env] INFO:    open_spiel_tic_tac_toe
[kaggle_environments.envs.open_spiel_env.open_spiel_env] INFO:    open_spiel_y
[kaggle_environments.envs.open_spiel_env.open_spiel_env] INFO:    open_spiel_universal_poker
[kaggle_environments.envs.open_spiel_env.open_spiel_env] INFO:    open_spiel_repeated_poker
[kaggle_environments.envs.open_spiel_env.open_spiel_env] INFO:    open_spiel_python_repeated_pokerkit
[kaggle_environments.envs.open_spiel_env.open_spiel_env] INFO: OpenSpiel games skipped: 1.
[kaggle_environments.envs.open_spiel_env.open_spiel_env] INFO:    snake
{'policy': 'v22_price_impact_slots', 'title_metric': '44/46 strict-future Top-30 replay cases; not an official LB score', 'main_py': '/kaggle/working/main.py', 'main_bytes': 18609, 'main_sha256': '62fb5a5f66f0011092a2b51e3192879ba583d5d815d761f176091c615657147a', 'submission': '/kaggle/working/submission.tar.gz', 'archive_members': ['main.py'], 'research_engine_version': '1.32.4', 'notebook_engine_version': '1.29.3', 'smoke_scope': 'artifact/hash/archive/action-schema; score evidence is the frozen 1.32.4 replay audit', 'action_schema_smoke': [{'seat': 0, 'farmer': ['PASS'], 'hands': 0, 'market_orders': 9}, {'seat': 1, 'farmer': ['PASS'], 'hands': 0, 'market_orders': 9}], 'ready': True}
```
