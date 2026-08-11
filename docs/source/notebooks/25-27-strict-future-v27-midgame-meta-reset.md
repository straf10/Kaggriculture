# 25-27-strict-future-v27-midgame-meta-reset

> Extracted by `analysis/nb_extract.py` from `notebooks/25-27-strict-future-v27-midgame-meta-reset.ipynb`.
> Cell numbers below are the anchors cited elsewhere in the repo (e.g. MASTERPLAN's `viz cell 19` = cell 19 of the *visualized* notebook).

## cell [0] — markdown

# 25/27 Strict-Future | v27 Midgame Meta Reset

**The dominant opening did not fail. Its stale continuation did.**

| Frozen evaluation | v27 | previous v26 | Seat 0 | Seat 1 |
|---|---:|---:|---:|---:|
| current inner | **28/30** | 16/30 | 12/13 | 16/17 |
| development outer | **29/30** | 14/30 | **16/16** | 13/14 |
| captured after policy freeze | **25/27** | 14/27 | 16/17 | 9/10 |
| actual three v26 losses, counterfactual | **3/3** | 0/3 observed | **3/3** | — |

`25/27` is a local strict-future counterfactual result, **not an
official Public-LB score**. Recorded opponents replay their public
actions and cannot react to our changed policy.

```text
same low-entropy HIRE4 opening
    ↓
replace the stale continuation from step 161 onward
    ↓
one coherent 719-step route in both seats
    + actor-local WEED repair
    + existing-SELL-slot price-impact ordering
```

## cell [1] — markdown

## Machine-readable attribution and contribution card

```yaml
notebook_history: Kaito v22 → v26 (this same public Notebook)
observable_route_source:
  team: Ezzzzzekki
  submission: 55390428
  episode: 91493566
  seat: 0
  action_sha256: 9080682756f5b9fc0f2cae25efdffa69474d40883f693b49f58be2c1893ae5d2
new_contribution:
  - separate rating warm-up from strategic decay
  - audit all three real v26 losses at action level
  - measure the current six-family Top-30 opening distribution
  - reject a higher-inner-score seat router that failed 2/3 real losses
  - freeze one coherent midgame reset before a globally later gate
runtime_route: same complete route in both seats
runtime_identity_fields: []
runtime_opponent_private_fields: []
mid_game_route_splice: false
ordinary_sell_create_delete_resize: false
```

The 719-action backbone is credited as Ezzzzzekki's observable
public replay behavior. It is not claimed as hidden-source recovery
or as a newly invented production schedule. The contribution here is
the diagnosis, time-separated selection, rejected-branch evidence,
sparse controller, and exact production artifact.

## cell [2] — markdown

## 1. Was v26 actually losing more?

Not in its observed public record. At the frozen audit:

| Submission | Wins | Latest 20 | Mean margin | Close-loss share |
|---|---:|---:|---:|---:|
| v26 | **87/90** | **20/20** | +18,415 | 100% |
| v25 | 66/93 | 4/20 | +6,598 | 15% |

All three v26 losses were seat 0 and close:

```text
episode 91375701 | Arda Ceylan   | -3,868
episode 91397548 | lemon13418    | -3,465
episode 91412066 | Hajime Tamura |   -747
```

So a lower displayed rating did not mean v26 had a worse win rate.
Each new submission started from the competition's low initial rating,
and rating gains depend on the two ratings rather than coin margin.
The [official evaluation](https://www.kaggle.com/competitions/kaggriculture/overview/evaluation)
explains rating-aware matchmaking and win/loss/tie scoring.

But the user's concern still exposed a real issue: against the **new
current opponent distribution**, frozen v26 won only
14/27. Live history and current
counterfactual robustness answer different questions.

## cell [3] — markdown

## 2. The Top-30 opening has almost collapsed to one prior

Modal Day-0 public signatures across the frozen Top-30 were:

| Opening signature | Teams | Interpretation |
|---|---:|---|
| 1 COW, 4 SHEEP, 5/5 seed, WHEAT 5, **HIRE4** | **14** | post-v26 basin |
| same assets, **HIRE5** | **12** | v25 basin |
| HealthStone HIRE3 | 1 | private continuation |
| Seb 2 COW / wheat-heavy HIRE7 | 1 | counter family |
| five-sheep carrot branch | 1 | rare alternative |
| old v23 opening | 1 | nearly displaced |

**26/30 teams now share the same 1-COW/4-SHEEP core.** An opening
classifier therefore has little information value. The next edge has
moved into continuation timing, labor paths, production mix, and
market execution after the common opening.

This is consistent with population-level observations in
[Two Private Bots Beating Kaggriculture Meta](https://www.kaggle.com/code/revanthtambisetty/two-private-bots-beating-kaggriculture-meta)
and [What the Top Farms Do — a Live Meta](https://www.kaggle.com/code/cjlcjlcjl/kaggriculture-what-the-top-farms-do-a-live-meta):
a public opening can become a prior while different continuations
retain the real rating edge.

## cell [4] — code

**output:**

```text
policy / split | wins | games | win rate
0 | v26 current inner | 16 | 30 | 0.533333
1 | v27 current inner | 28 | 30 | 0.933333
2 | v26 development outer | 14 | 30 | 0.466667
3 | v27 development outer | 29 | 30 | 0.966667
4 | v26 strict future | 14 | 27 | 0.518519
5 | v27 strict future | 25 | 27 | 0.925926
```

**output:**

*[image omitted — see the notebook]*

## cell [5] — markdown

## 3. Same opening, different continuation

The old v26 seat-0 route and the selected v27 route have the same
HIRE4 Day-0 queue. Their first market difference appears only at
**step 161** and their first
farmer/hands difference at **step 170**.
Across all 719 steps their actor-plus-market distance is
**634**.

Planned route totals illustrate the shift without pretending they
are a causal decomposition:

| Planned quantity | v26 seat 0 | v27 |
|---|---:|---:|
| purchased WHEAT | 380 | 360 |
| sold MILK | 218 | 241 |
| sold FERTILIZER | 245 | 235 |
| SELL orders | 171 | 168 |

The selected route purchases less wheat, schedules more milk sale,
and changes hundreds of labor/market turns after the shared prefix.
This is a **coherent continuation reset**, not a late splice into a
farm whose inventory assumptions came from another policy.

## cell [6] — markdown

## 4. Why the tempting seat portfolio was rejected

The first inner screen favored a seat router:

| Candidate | Inner | Outer | Actual v26 losses | Outer mean margin |
|---|---:|---:|---:|---:|
| fixed Ezz route | 28/30 | **29/30** | **3/3** | **+9,591** |
| Nikita fixed route | 28/30 | 28/30 | 1/3 | +8,804 |
| Nikita seat 0 + Ezz seat 1 | 29/30 | 29/30 | 1/3 | +9,212 |

The router gained one inner win but solved only one of the three real
failures. Fixed Ezz solved all three, tied the router on outer wins,
and had the higher outer margin. v27 therefore removes the seat
branch instead of adding another expert.

This directly corrects v26's local optimum: **seat-specific validation
performance was mistaken for a generally useful seat mechanism**.

## cell [7] — markdown

## 5. The sparse controller still earns its place

Route-only control versus official price-impact SELL-slot ordering:

| Split | route only | + sparse SELL ordering | Mean-margin gain |
|---|---:|---:|---:|
| inner | 28/30 | 28/30 | +1,115 |
| outer | 28/30 | **29/30** | +819 |

Most gain comes from the current route, but the market layer adds
one outer win and improves margin without changing production:

- ordinary turns create, delete, or resize no SELL;
- SELLs move only among already existing SELL indices;
- BUY, HIRE, seed, animal, land, farmer, and hand plans stay fixed;
- observed actor-local WEED is repaired with bounded replay;
- no opponent name, team ID, submission ID, Notebook, or private
  opponent inventory enters runtime.

[Structured Economic Policy](https://www.kaggle.com/code/pilkwang/kaggriculture-structured-economic-policy)
remains useful context for reserve-aware control. Here the promoted
intervention is narrower because larger market-maker branches did not
survive previous fresh panels.

## cell [8] — markdown

## 6. Chronological protocol

```text
snapshot A at 2026-08-10 01:28 UTC
  70 unique public episodes, then-current Top-30
  oldest listed trace → route donor
  next trace          → 30-case inner screen
  newest trace        → 30-case development outer

freeze at 2026-08-10T01:53:37Z
  route episode 91493566
  route hash 9080682756f5b9fc...
  global cutoff EpisodeId 91496460

snapshot B after freeze
  33 globally later physical episodes available
  maximum unique team/seat matching → 27 cases
  frozen v27: 25/27
  unchanged v26 control: 14/27
```

The outer split helped choose the architecture, so it is explicitly
called **development outer**. Only the later `EpisodeId >
91496460` slice is the one-time
strict-future promotion gate.

This follows the panel warning in
[Beating Your Own Best Agent Is The Wrong Test](https://www.kaggle.com/code/dariushafshar/beating-your-own-best-agent-is-the-wrong-test)
and the paired-seat framing in
[Kaggriculture Rank Your Agent](https://www.kaggle.com/code/raykkretzschmar/kaggriculture-rank-your-agent).

## cell [9] — markdown

## 7. Two strict-future losses remain

```text
episode 91498290 | Nikita Lugovoy |
candidate seat 1 | -312

episode 91500868 | Jince |
candidate seat 0 | -834
```

Both are sub-1,000-coin losses, but they still count as full losses.
The sample also contains only one wheat-heavy counter case. Therefore
`25/27` is not evidence that every private adaptive branch is solved.

[Breaking the Tie](https://www.kaggle.com/code/andrewsokolovsky/kaggriculture-breaking-the-tie)
and [Adaptive Queue](https://www.kaggle.com/code/blacklions/kaggriculture-v20-adaptive-queue-public-experiment)
motivate queue-level responses to convergent agents. This release
does not promote a micro-seed permutation: only the complete route
and conservative order layer cleared the multi-team chronology.

## cell [10] — markdown

## 8. Exact artifact and citation boundary

The production file is **20,813 bytes**, contains one
719-action route used in both seats, and depends only on the Python
standard library.

SHA-256: `f48c21166eac68d1b05a401f04f94a2eb6154e65415af64893672365ff33c7b8`

Research and generated artifact matched on **5,760
/ 5,760 actions** from four full public
observation streams.

If you fork this work, please retain:

- Ezzzzzekki as the observable complete-route source;
- this Notebook for the current-meta audit, fixed-vs-seat-router
  ablation, chronological protocol, WEED repair, and SELL-slot layer;
- your changed mechanism and independent future window separately.

[Source replay episode 91493566](https://www.kaggle.com/competitions/kaggriculture/episodes/91493566)

The cell below reconstructs the exact submitted bytes, verifies the
hash and archive, imports the artifact, and smoke-tests both seats.

## cell [11] — code

**output:**

```text
[92m02:08:19 - LiteLLM:WARNING[0m: get_model_cost_map.py:271 - LiteLLM: Failed to fetch remote model cost map from https://raw.githubusercontent.com/BerriAI/litellm/main/model_prices_and_context_window.json: [Errno -3] Temporary failure in name resolution. Falling back to local backup.
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
{'policy': 'v27_midgame_meta_reset', 'title_metric': '25/27 strict-future Top-30 replay cases; not an official LB score', 'main_py': '/kaggle/working/main.py', 'main_bytes': 20813, 'main_sha256': 'f48c21166eac68d1b05a401f04f94a2eb6154e65415af64893672365ff33c7b8', 'submission': '/kaggle/working/submission.tar.gz', 'archive_members': ['main.py'], 'research_engine_version': '1.32.6', 'notebook_engine_version': '1.29.3', 'research_exact_action_comparisons': 5760, 'action_schema_smoke': [{'seat': 0, 'farmer': ['PASS'], 'hands': 0, 'market_orders': 9}, {'seat': 1, 'farmer': ['PASS'], 'hands': 0, 'market_orders': 9}], 'ready': True}
```
