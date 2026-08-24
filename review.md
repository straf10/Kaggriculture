# Kaggriculture — deep-clean & optimization audit

*Audit-only. Nothing outside this file was modified. Test suite run, no Kaggle API touched.*
*Repo state: branch `main`, 247 tracked files, 8 untracked, `git status` snapshot at session start.*

---

## 1. Verdict

- **The live code is genuinely good.** `pytest tests/` → **390 passed in 144 s** (0 fail/skip). The agent hot path (`agent/`, 15 modules, all imported and tested) has **no bare excepts, no mutable-default args, no file I/O per turn, no TODO/FIXME**. This is a mature, well-guarded codebase.
- **The headline problem is portfolio honesty, not code quality.** `README.md` presents the `planner → scheduler → executor` heuristic as "the submission" and claims "Currently Top 18%", but the tracked `main.py` heuristic agent is **not what is on the ladder**. Every shipped submission (`55726984`, `55675634`) is a self-contained `main.py` that **replays a decoded action tape of another team's agent (ReCurSiON)** with a thin overlay — built by `analysis/build_tape_overlay_submission.py`, inlining `agent/tape_overlay.py`. A cold reviewer is told a different story than the one the git history and memory tell.
- **The repo is buried under its own process exhaust.** `memory.md` (477 KB / 5 276 lines, Greek+English session diary), `ROADMAP.md` (651 lines — the user's own memory says it was cut to 544 and has regrown), a root-level `prompt.md` pass-brief, `docs/INDEX.md` (Greek), and 12 one-off "pass brief" docs in `docs/plans/` dominate the top level over ~2 000 lines of actual agent code.
- **8 uncommitted files** sit in the tree (3 analysis scripts + 5 plan docs from S7/S8 desk passes) — they must be committed or discarded before this is shown to anyone.
- **Portfolio-ready? Not yet — but the gap is a doc-layer cleanup, not a rewrite.** A day of curation (fix the README framing, demote the diaries, resolve the untracked files, add an English entry-point) gets it there.

---

## 2. Bugs & omissions

No severe defects were found in the shipped path; the findings below are low-severity omissions and one documentation contradiction. Ranked by severity.

| # | Sev | Location | Finding | Failure scenario | Evidence |
|---|-----|----------|---------|------------------|----------|
| B1 | **Med (doc-correctness)** | `README.md:29`, `:12-27` | README describes the heuristic `plan→schedule→execute` agent as the submission and states "Currently Top 18%", but the ladder result is produced by the tape-overlay path, which the README never mentions. A reviewer attributes the result to the wrong code. | Reviewer reads README, runs `python -m harness.cli play main.py …`, sees a ~700-rating heuristic, and cannot reconcile it with "Top 18%". | `main.py:9` imports `agent.policy.agent` (heuristic); shipped `main.py` is written by `analysis/build_tape_overlay_submission.py:590-668` and inlines `agent/tape_overlay.py` (no `agent/` import at runtime). Memory `s7-ship-b-tile-recovery`, `s9-phase2-gate`. |
| B2 | Low | `agent/receipts.py:22` | `expected_transition` reads `snapshot.my_tiles[y][x]` guarding only `y` (`0 <= y < len(...)`), not `x`. `reconcile._tile_at` (`:51-55`) and `tape_overlay._recover_tile_actions` (`:172`) both guard *both* axes — inconsistent defensiveness. | An `x` past the row length raises `IndexError` instead of degrading to `None`. Unreachable in practice (unit positions are always on the 10×10 board) and debug-only (`guards.debug`), so latent. | `agent/receipts.py:22` vs `agent/tape_overlay.py:172`. |
| B3 | Low | `agent/tape_overlay.py:311-315` | `act()` (augment/replace) returns `"market": combined` **without** a `[:10]` cap, relying on the engine to truncate; `_liquidate_act` (`:266`) caps explicitly with `out[:10]` and pre-checks `len(out) <= 9`. The design (purchases first, so only strawberry sells get dropped) makes this safe against the *real* engine, but a harness/engine that did not silently truncate would see divergent behaviour between the two modes. | A future engine bump that rejects >10-order turns instead of clipping would break augment mode but not liquidate mode. Documented as intentional (`:19-21`). | `agent/tape_overlay.py:300` vs `:266`; docstring `:19-21`. |
| B4 | Low (omission) | `agent/state.py:24`, `:48-68` | `Snapshot.opponent_tiles` is parsed on **every** turn but has **no reader** anywhere in the live path (documented "reserved for a Phase 2 opponent-aware policy"). Cost is a per-turn list copy that nothing consumes. | No functional failure; wasted work per turn and a field that reads as live but is inert. | `git grep opponent_tiles` → only `state.py`. Comment `state.py:14-24`. |
| B5 | **Med (doc-correctness)** | repo-wide code comments | Tracked source cites the section numbers of design docs that **no longer exist or are rolling**: `plan.md §…` in **19** files, `current_phase.md §…` in **26** files — and **`plan.md`, `current_phase.md`, `docs/MASTERPLAN.md` were deleted** (retired 2026-08-11, per `README.md:72`). Plus `prompt.md §…` in 11 files (rolling, B-above). A reviewer following any of these citations hits a missing/overwritten target. | A maintainer reads `agent/policy.py:49` "review… M4: plan.md §3.1 calls for a replan" and `agent/receipts.py:20` "config…", follows `plan.md §3.1`, and finds no `plan.md`. Dozens of such dead provenance links. | `git grep -l 'plan\.md'` → 19; `'current_phase\.md'` → 26; `ls plan.md current_phase.md` → "No such file". |

**Omission — the shipped artifact has no runtime manifest.** `requirements-dev.txt` is the only manifest and is dev-scoped (`pandas`, `pyarrow`, `pytest`, `kaggle` CLI). That is *correct* for the self-contained submission (it imports only `kaggle_environments`, provided by Kaggle), but a cold reviewer has no one-line statement of "the submission needs nothing but the engine." Worth a README sentence, not a code change.

---

## 3. Delete list *(authoritative — the section to act on)*

Two ground rules shaped this list. (a) The repo has an **explicit, documented archival policy**: `README.md:37` ("`analysis/` … kept for reproducibility, not re-run on a schedule") and the `.gitignore` header comments deliberately keep every checkpoint `manifest.json` and gate `results.json`. Under the audit's own rule ("distinguish *dead* from *archival*; archival is kept"), the tracked `analysis/`, `checkpoints/*/manifest.json`, and `gates/*/results.json` are **archival, not dead** — see the note after the table. (b) I only hard-list items I can defend as removable. The larger "should the archival policy itself change?" question is Open Question Q1.

| Path | Reason | Evidence | Verdict | Risk if wrong |
|---|---|---|---|---|
| `prompt.md` (root) | **Rolling working file** overwritten each pass; current content is the "Ship B component (i)" brief (pass **shipped** as `55675634`). A stray, always-stale note at repo root. | Content is a single shipped-pass brief. ⚠️ **Corrected in Pass 2:** `prompt.md §X` is cited in **11 tracked `.py` files + tests** (e.g. `harness/compare.py:306`, `tests/test_harness.py:796`, `analysis/v1r_feed_reserve.py`), but those cite *earlier overwritten versions* (08-14/08-15), so the citations are **already dangling** against the current content. See finding B5. | **DELETE** the file; fix the citations as part of B5 (they resolve to nothing today regardless) | Low — the citations are already broken; deletion makes that explicit rather than silently-wrong. |
| `docs/plans/item4_step1_prompt.md`, `item4_step2_prompt.md`, `item4_min_cost_assignment.md` | "Min-cost assignment" investigation briefs. The investigation ran (via `analysis/v1u_oracle.py`, `v1u_travel_ratio.py`) and was **not** implemented — `grep -niE "min.?cost\|hungarian\|assignment" agent/scheduler.py` → 0 hits. Superseded process docs. | `git grep item4` → the plan docs + `v1u_oracle.py:5` / `v1u_travel_ratio.py` (which **cite the brief in docstrings**) + `memory.md`. Not in `ROADMAP.md`/`docs/INDEX.md`. | **ARCHIVE, don't delete piecemeal** — the `v1u_*` scripts cite these docs, so deleting them adds to the B5 dangling-citation problem. Move as a set or leave until the B5 sweep. | Low, but coupled to B5. |
| `docs/plans/s8_submission_analysis_tasks.md`, `s9_liquidation_heuristics.md`, `s9_phase1_implementation_prompt.md`, `s9_phase2_gate_prompt.md` | Pass briefs for passes that are **done/shipped** (S8 analysis complete; S9 H2 shipped as `55726984`). Same class as `prompt.md`. | Memory `s8-*`, `s9-phase1-h2-liquidation`, `s9-phase2-gate` record the outcomes; the shipped logic is in `agent/tape_overlay.py` + the build script. ⚠️ `s8_submission_analysis_tasks.md` is cited by `analysis/s8_replay_io.py` (B5 coupling). | **ARCHIVE** (consolidate briefs out of the top-level doc tree) as part of the B5 sweep | Low — outcomes are in memory + code. |
| `analysis/s7_conditional_agreement.py`, `s7_glut_bound.py`, `s7_glut_leg0_absorb.py` (**untracked**) | Uncommitted S7 desk-STOP scripts. Both approaches were **STOPPED** (memory `s7-conditional-agreement-k3`, `s7-glut-phase0-desk`). Not imported by any tracked test. | `git status` → `??`; `git grep` in `tests/` → 0. | **COMMIT or DISCARD** (user's call — see Q2). If committed, they are archival like their siblings; if the STOP is final, discard. | Medium — discarding loses the desk work permanently (never committed). Confirm with user. |
| `docs/plans/conditional_agreement_top4.md`, `glut_metering_premium.md`, `live_read_55675634_prompt.md`, `now_leg1_phase3_downloads.md`, `state_aligned_policy_extraction.md` (**untracked**) | Uncommitted plan/brief docs from the same S7/S8 desk passes. | `git status` → `??`. `conditional_agreement_top4.md` and `glut_metering_premium.md` are referenced by their (also-untracked) memory entries. | **COMMIT or DISCARD** with the scripts above | Low. |

### Archival — deliberately **NOT** on the delete list

- **`analysis/` (78 tracked scripts).** Per `README.md:37` these are kept for reproducibility. 14 are load-bearing (imported by `tests/`: `s6_step2b_phase05`, `s7_ladder_census`, `v1v_shop_demand`, `s6_step2e`, `v1u_travel_ratio`, `v1u_oracle`, `s6_step2d`, `s6_step2c`, `s6_step1_reconstruct`, `s6_step1_phase0`, `s6_step0_leg3`, `s6_step0_leg2`, `replay_profile`, `donor_streams`); 3 are shipped-submission reproducibility (`build_tape_overlay_submission.py`, `build_reconstruction_submission.py`, `build_tape_submission.py`). The rest are one-off diagnostics whose conclusions live in memory — **the audit's B-criterion would delete these, but the repo's stated policy keeps them.** That tension is Q1; I am not unilaterally deleting provenance.
- **`checkpoints/*/manifest.json` (42)** and **`gates/*/results.json` (15).** `.gitignore` keeps *only* these fingerprint files by explicit, dated, user-approved decision (R34/R14 comments in `.gitignore`). Archival. KEEP.
- **`engine_reference/` (4 files).** README claims "never imported by tests or the agent." **Verified:** `git grep engine_reference -- '*.py'` returns only *comment* line-refs (e.g. `agent/demand.py:4`), never an `import`. Load-bearing as the citation target for the agent's engine-fact comments. KEEP.
- **`docs/source/notebooks/` (18) + `docs/source/*`.** Verbatim RAW copies (competition page, forum, top notebooks); `docs/INDEX.md` marks `source/` "Ποτέ edit / Never edit" and line-refs point into them. Archival reference. KEEP.

---

## 4. Code-level dead weight *(non-file removals)*

- **`Snapshot.opponent_tiles`** (`agent/state.py:24`) — parsed, zero readers (B4). Either wire the Phase-2 reader or drop the field + its parse line. **BEHAVIOUR-RISK: none** (no reader ⇒ removing it cannot change output), but it is a `frozen` dataclass field, so removal touches the constructor call at `state.py:55`. Low effort.
- **No unused third-party deps.** `pandas`/`pyarrow`/`kagglehub` are used only in `analysis/` + `tests/test_replay_profile.py` (correct for a `-dev` manifest); `kaggle` is a CLI (0 imports, by design); `kaggle_environments` is core. Manifest is clean.
- **No tracked caches / no tracked `__pycache__` / no `.pyc`.** `git ls-files | grep -E 'pycache|\.pyc'` → empty. Good hygiene.
- **`agent/config.py` (738 lines).** Heavily commented config; the `dead`/`no longer`/`unused` grep hits are all inside *explanatory comments*, not dead config keys. A per-key "is this read?" sweep would need a runtime trace to be conclusive — **unverified**; flagged as a possible follow-up, not a finding.

---

## 5. Performance

**Measured baseline:** the shipped agent is not the perf concern — it does zero file I/O per turn, no copies beyond the `Snapshot` parse, and the profiler path exists (`harness/cli profile`, memory `s9-phase1` records "timing 0.02 ms/turn"). The heavy compute is the **dev harness** (`harness/compare.py`, 75 KB), which is already parallelised (`ProcessPoolExecutor`, per-future try/except at `compare.py:1017`) and gitignores its outputs. 

| Item | Current cost | Change | Gain | Effort | Risk |
|---|---|---|---|---|---|
| `Snapshot.opponent_tiles` parse | 1 unused list-copy/turn (~720/episode) | Drop the field (see §4) | Negligible CPU; removes a misleading "live" field | Low | **BEHAVIOUR-RISK: none** — no reader. |
| Full-file memory/diary loads by tooling | `memory.md` 477 KB, `ROADMAP.md` 60 KB read into context each session | Out of scope for the agent; a *human/agent-context* cost, not a runtime one | Large context savings | — | N/A (docs) |

**Honest statement:** I did **not** find a measured hot-path perf defect (no accidental O(n²), no per-row `apply`, no whole-dataset load in the agent). The workload is CPU-bound episode simulation inside `kaggle_environments`; the agent's own per-turn cost is already ~0.02 ms. **No `BEHAVIOUR-RISK` perf change is recommended** beyond the inert-field removal. Any claim of a bigger perf win here would be unbacked.

---

## 6. Portfolio gaps *(ordered — do these to make it reviewer-ready)*

1. **Fix the README's central claim (B1).** State plainly that the repo contains *two* agents: (a) the original heuristic `plan→schedule→execute` agent (the readable, fully-tested reference, ~700 rating), and (b) the **tape-overlay** strategy that is actually on the ladder (a decoded-tape replay of a top team's policy + a live market/tile overlay). Attribute "Top 18%" to (b). Hiding (b) is the single biggest credibility risk for a reviewer who reads the git log.
2. **Resolve the 8 untracked files** (§3) — commit or discard. An uncommitted working tree is the first thing a reviewer's `git status` shows.
3. **Demote the process exhaust.** `memory.md` (477 KB Greek/English diary), root `prompt.md`, and the `docs/plans/*` briefs are working artifacts, not portfolio surface. Move them under a clearly-labelled `docs/journal/` (or gitignore `memory.md` and keep it local) so the top level reads as *code + README + ROADMAP + docs/reference*.
4. **Add an English entry point.** `README.md` is English but `docs/INDEX.md`, `ROADMAP.md` prose, and `memory.md` are Greek/mixed. A reviewer who doesn't read Greek stalls at `docs/INDEX.md`. At minimum, an English one-paragraph "how the pieces fit" at the top of INDEX.
5. **Re-cut `ROADMAP.md`** — 651 lines vs the user's own 544-line target (memory `roadmap-is-the-plan-not-the-diary`); it has regrown with narrative again.
6. **Tests: strong, keep as-is.** 22 test files, 390 tests, green in 144 s; they cover the agent guards, engine-fact tripwires, harness, and every S6/S7 analysis instrument. Note in the README that the suite passes and how long it takes — reproducibility signal.
7. **Fix dangling design-doc citations (B5).** Either restore the retired docs as an archive or sweep the `plan.md §…` / `current_phase.md §…` / `prompt.md §…` references out of the tracked source comments. 45+ code comments currently point at documents a reviewer cannot open.
8. **Add CI.** There is **no `.github/` and no CI config** — a repo with a 390-test green suite should run it on push. A visible passing CI badge is the single cheapest credibility signal for a portfolio piece.
9. **Delete the stale `s9-h2-liquidation` branch.** ⚠️ *Corrected in Pass 2:* it is **fully merged** — `main` is 3 commits ahead, the branch has **0 unique commits** (`git log main..s9-h2-liquidation` empty; `git branch --merged main` lists it). Its work shipped as `55726984` on `main`. Both local and `origin/s9-h2-liquidation` are safe to delete.
10. **Secrets: clean.** `.env` is gitignored (`git check-ignore .env` ✓); no token/key value is committed — only variable-*name* references to `KAGGLE_API_TOKEN` in docs. `memory.md:444` records the public Kaggle username `nikosstraf` (not a credential; the user's own handle). LICENSE (MIT) present.

---

## 7. Memory compaction

**Scope:** the persistent `~/.claude/.../memory/` store — **21 content files + `MEMORY.md` index**. All 21 were read. The store is high-quality and densely `[[linked]]`; the compaction win is folding the **6-file S6 chain into 1** and the **2-file S9 chain into 1** (early-phase narrative → one per-phase memory), preserving every load-bearing number. Target: **21 → 15 content files.**

### 7a. Per-file disposition

| File | Verdict | Reason |
|---|---|---|
| `harness-metric-gate-on-tape-arms.md` | **KEEP** | Standing rule (GO=False is by-design on tape arms); load-bearing, referenced by `s9-phase2-gate`. |
| `kaggle-api-auth.md` | **KEEP** | Reference mechanics (OAuth token, CLI recipe). Durable. |
| `kaggle-ladder-rating-mechanics.md` | **KEEP** | Reference mechanics (burst/deflation/judge-at-100). Durable. |
| `kaggriculture-active-pair-mechanics.md` | **KEEP** | Reference mechanics (latest-2-by-date, eviction). Durable. |
| `kaggriculture-town-shop-mechanics.md` | **KEEP** | Reference mechanics (8 shops, per-product absorption, strawberry-draw variable). Durable, the richest engine-fact memory. |
| `roadmap-is-the-plan-not-the-diary.md` | **KEEP** | User feedback (type: feedback) — must be preserved verbatim per the rules. |
| `s7-leg0-ladder-currency.md` | **KEEP** | Load-bearing: acceptance order (wins→BT→bank), rank-not-score, 43,4 % converged win-rate correction. |
| `s7-leg-a-killed-by-fidelity.md` | **KEEP** | Killed approach + *why* (top-4 re-donor state-adaptive) + the reusable fidelity-replay rule. |
| `s7-conditional-agreement-k3.md` | **KEEP** | Killed approach + the reusable cross-match control instrument (Leg 3). |
| `s7-glut-phase0-desk.md` | **KEEP** | STOPPED approach + *why* (common-mode/K5 risk); has the 2026-08-23 differential update. |
| `s7-ship-b-tile-recovery.md` | **KEEP** | Provenance of active submission `55675634` (still live). |
| `s8-two-submission-analysis.md` | **KEEP** | Load-bearing standing-kill: the neighbourhood bench inverts live order — "don't tune on it" (§7.4). |
| `s8-wins-analysis-liquidation-lever.md` | **KEEP** | The lever lineage into the shipped H2; kills WHEAT/MELON readings with numbers. |
| `s9-phase2-gate.md` | **KEEP + absorb S9-phase1** | Current live state (`55726984` shipped, active pair, first live read). |
| `s9-phase1-h2-liquidation.md` | **MERGE → `s9-phase2-gate`** | Self-labelled "SUPERSEDED — shipped as 55726984". Its build detail (frozen params, 412/412 bit-exact) folds into the phase-2 entry as a one-line "how it was built". |
| `s6-step1b-shipped.md` | **MERGE → `s6-erased-conditioning-closed`** | `55586926` is now *evicted* (per `s9-phase2-gate`); its historical role folds into the S6 summary. |
| `s6-step2b-phase0-go.md` | **DELETE (fold nothing new)** | Explicitly "SUPERSEDED ON INTERPRETATION" by `phase05-refuted`; its only durable numbers ($117→$90/u, ratio 1,339 vs 1,010) already live in the refutation entry. |
| `s6-step2b-phase05-refuted.md` | **MERGE → `s6-erased-conditioning-closed`** | The decisive refutation (fixed hour-0 calendar, 290 units 46/50, corr(units,shop)=+0,02). Keep the numbers. |
| `s6-step2c-branch-i.md` | **MERGE → `s6-erased-conditioning-closed`** | Market layer town-invariant channel-wide (WOOL/MILK/FERTILIZER). Keep the numbers. |
| `s6-step2d-branch-iv.md` | **MERGE → `s6-erased-conditioning-closed`** | Production channel town-reactive but bounded ($597/ep, +2,4 pts). Keep the bound. |
| `s6-step2e-loss-tail.md` | **MERGE → `s6-erased-conditioning-closed`** | Loss tail = shop composition (r=0,605) not desync (r=−0,029); 11/178 flippable (+6,2 pts). Keep the numbers + the re-validation corrections. |

**Net:** 6 S6 files → 1; 2 S9 files → 1. **21 → 15.** No load-bearing fact, mechanic, active-submission id, killed-approach rationale, or user-feedback entry is dropped — only the blow-by-blow narrative and the now-stale "§-numbers predate the restructure" footers.

### 7b. Proposed consolidated memory — `s6-erased-conditioning-closed.md`

```markdown
---
name: s6-erased-conditioning-closed
description: "S6 (2026-08-17→20) — the 'what did the vote erase' programme is CLOSED across every channel and currency. The ReCurSiON majority-vote reconstruction is a faithful OPEN-LOOP copy; the donor gap is strength/opponent-pool + the clock, not a lossy copy."
metadata:
  type: project
---

Six passes (2a, 2b, 2b-0.5, 2c, 2d, 2e) exhaustively bounded every channel by which the
majority-vote reconstruction of ReCurSiON (`55586926`, shipped 2026-08-17, **now evicted** by
[[s9-phase2-gate]]) could differ from the donor. Verdict: **the vote is a faithful open-loop copy;
the ~1.036–1.100-pt live gap to the donor is real strength + opponent-pool + the §4.4 clock (BT over
post-deadline episodes, deadline 2026-09-30), NOT a per-episode bank phenomenon and NOT a lossy copy.**
Do not reopen the "erased conditioning" family.

**Market layer — town-INVARIANT channel-wide (2b-0.5, 2c).** Strawberry sell-rule is a fixed hour-0
calendar, not town-conditioning: 46/50 traces sell an identical 290 units; at step 336 all 50 sell 6
units while price spans $151–230 and strawberry-shop count spans 0–4; corr(units, shop identity)=+0,02,
corr(units, own shed)=+0,92; ~80% sold at hour 0 (townCenterSellInterval=24). WOOL: 20/50 towns never
draw a YARN_STORE yet the modal action is identical across the split at all 20 contested steps
(corr(units,wool-shops)=+0,09). MILK never presents a zero-drain population. FERTILIZER is in no SHOPS
entry ⇒ zero absorption, analytically eliminated. The vote reproduces every product's modal volume
(WOOL 200 / MILK 296 / WHEAT 457 / MELON 114 / STRAWBERRY 290). The $117→$90/u strawberry gap the GO
pass measured is the **zero-sum contest** (our live opponents also concentrate at hour 0), reachable ≈ $0
— NOT a restorable lever. (`s6-step2b-phase0-go`'s causal claim was refuted; its numbers reproduce.)

**Production layer — town-REACTIVE but bounded small (2d).** The 88 production-disagreement steps are
real closed-loop hand tile-control (per-town weedSpawnChance → DIG the weed, re-PLANT, WATER by actual
dry state) that a fixed-index 50-town vote cannot carry (farmer-op differs 0/88; it's the hands, 87/88;
75/122 hand disagreements on a disjoint tile content). But the recoverable surface = own-farm weed/decay
loss = 14,89 decay + 4,99 weeds = **$597/ep, 100% WHEAT**, ⇒ full recovery **+2,4 rating pts / 0,09% of
the gap**. This is what `s7-ship-b-tile-recovery` (55675634) later shipped as the tile-recovery overlay.

**Loss tail — shop composition, not desync (2e, re-validated on 178 eps).** r(premium drain, bank)=
**+0,605** (R²=0,336, ~$7,116/tick); desync r=−0,006 raw and partial r(desync|drain)=**−0,029** ⇒ desync
adds nothing. Decay does not track bank. **11/178 episodes flippable = +6,2 pts.** Converged win-rate
43,4% (the 65% in early briefs was the placement burst — see [[s7-leg0-ladder-currency]]).

**Reusable instrument:** the same-town seat-vs-seat realised-premium-ratio test (donor 1,339 vs our
1,010 on STRAWBERRY) is the clean way to detect a real market-conditioning edge vs a mirror-match
baseline. Artefacts (gitignored reports under `baselines/2026-08-18..20/`, scripts `analysis/s6_step2c.py`
/ `s6_step2d.py` / `s6_step2e.py`, guards `tests/test_s6_step2*.py`) remain for reproducibility.

Related: [[s7-leg-a-killed-by-fidelity]], [[s7-conditional-agreement-k3]], [[kaggriculture-town-shop-mechanics]], [[kaggle-ladder-rating-mechanics]].
```

### 7c. Proposed replacement `MEMORY.md`

```markdown
# Memory index

## Current state (live)
- [S9 Phase 2 — SHIPPED 55726984](s9-phase2-gate.md) — 2026-08-23/24: H2 tail-liquidation package (55586926+H2) gated (Instrument B b=0: dev 43-0-5, holdout 39-0-9; all counters Δ=0; pytest 390/390) → **uploaded, evicted 55586926**. Active pair **55726984 + 55675634**. Built bit-exact from the frozen H2 rule (params F=25/first_day=22/h_max=12/d_days=4/force_step=686), 412/412 bit-exact vs reference. First live read 2026-08-24: score 1669,2, rank 1234/6128, sub-100 eps → **not judgeable; judge nothing before ~100 episodes**.
- [S7 Ship B — tile recovery SHIPPED 55675634](s7-ship-b-tile-recovery.md) — 2026-08-21: 6-rule tile-recovery overlay on the ReCurSiON tape; SMOKE 336-0-0; the cheaper active slot (next eviction by date).

## Reference — mechanics (durable)
- [Town & shop mechanics](kaggriculture-town-shop-mechanics.md) — 8 shops on fixed days 3/6/…/24, identity uniform iid; #draws feeding STRAWBERRY is the dominant town variable ($24→$237, wr 0,52→0,77); MELON 0 shops, FERTILIZER 0 absorption; wheat tiles are animal feed (don't convert them).
- [Ladder rating mechanics](kaggle-ladder-rating-mechanics.md) — placement burst then 1-2 eps/h; judge past ~100 eps; score deflates pool-wide (read RANK); a re-submission costs ~1.000 pts; optimise wins, not coins.
- [Active-pair mechanics](kaggriculture-active-pair-mechanics.md) — only the latest 2 by DATE play; eviction is by date not score; deadline 2026-09-30.
- [Harness metric gate can't pass a tape arm — by design](harness-metric-gate-on-tape-arms.md) — GO=False is expected on every tape/reconstruction submission; read the structural leg differentially.
- [Kaggle API auth](kaggle-api-auth.md) — OAuth token in gitignored `.env` as KAGGLE_API_TOKEN, introspected by kagglesdk; `source .env` before `kaggle` CLI calls.

## User feedback
- [ROADMAP is the plan, not the diary](roadmap-is-the-plan-not-the-diary.md) — keep ROADMAP a forward technical plan (~544 lines); narrative → memory.md; **price the programme not the increment**, and **every pass ends in an upload**.

## Closed phases (consolidated)
- [S6 — erased-conditioning programme CLOSED](s6-erased-conditioning-closed.md) — the vote is a faithful open-loop copy of ReCurSiON; market layer town-invariant, production town-reactive but $597/ep (+2,4 pts), loss tail = shop composition (r=0,605) not desync; donor gap is strength+clock. Reusable: same-town seat-vs-seat premium-ratio test.
- [S7 leg 0 — the ladder's currency](s7-leg0-ladder-currency.md) — win rate 43,4% converged (65% was the burst); acceptance order wins→BT→bank→diff; rank is the invariant; donor gap is real strength.
- [S7 Leg A — top-4 re-donor KILLED by fidelity](s7-leg-a-killed-by-fidelity.md) — every top-4 candidate is state-adaptive (cross-trace agreement 0,25-0,37 vs ReCurSiON 0,993); fidelity replay now required before any recon upload.
- [S7 conditional agreement — STOPPED](s7-conditional-agreement-k3.md) — no single variable explains top-4 disagreement; two top-4 policies in the SAME town disagree 99,93% → no shared core to extract. Reusable: the same-seed cross-match control.
- [S7 glut-metering — STOPPED at gate](s7-glut-phase0-desk.md) — desk gates pass but the lever is largely COMMON-MODE (K5 risk); revisit only via a differential measure (now exists in s8-wins).
- [S8 two-submission analysis — DONE](s8-two-submission-analysis.md) — diagnostics not levers; the neighbourhood bench inverts live order → **standing kill, do not tune on it**.
- [S8 wins analysis → the liquidation lever](s8-wins-analysis-liquidation-lever.md) — no volume variable; the only lever is when/into-what-inventory we liquidate → became the shipped H2 (s9-phase2-gate).
```

---

## 8. Open questions *(only the user can decide)*

- **Q1 — Archival policy vs portfolio cleanliness.** The repo's documented policy keeps ~60 one-off `analysis/` diagnostics "for reproducibility"; the audit's own dead-weight criterion would delete most of them (conclusions already in memory). Which wins for the *portfolio* cut — keep the full provenance trail, or prune to the ~17 load-bearing + build scripts and let git history hold the rest?
- **Q2 — The 8 untracked files.** Commit them (they become archival like their siblings) or discard (the S7 STOPs are final)? They were never committed, so discarding is irreversible.
- **Q3 — `memory.md` (477 KB diary).** Keep tracked as provenance, gitignore it (local-only), or move to a `docs/journal/` branch? It is the largest single file in the repo and is Greek/English prose a cold reviewer can't use.
- **Q4 — The README framing (B1).** Are you comfortable stating openly that the ladder result comes from replaying a decoded tape of another team's agent? That is the honest description, but it changes how the "Top 18%" reads. This is a positioning call, not a technical one.

---

## Pass 2 corrections

Re-read as a hostile reviewer; re-ran repo-wide reference searches on every delete-list entry and swept for skipped categories. Changes made to the sections above:

1. **FALSE CLAIM FIXED — "no dead local branches (single `main`)".** Wrong. `git branch -a` shows `s9-h2-liquidation` (local **and** `origin/s9-h2-liquidation`). I first misread `git rev-list --left-right --count` and nearly reported the branch as *ahead*; re-checking, `git log main..s9-h2-liquidation` is **empty** and `git branch --merged main` lists it — the branch is **fully merged, 0 unique commits**, `main` is 3 ahead. Added as portfolio item #9 (safe to delete). This is exactly the kind of miss Pass 2 exists for.

2. **FALSE EVIDENCE FIXED — `prompt.md` "referenced by no code/test/config".** Wrong. `git grep "prompt\.md" -- '*.py'` → **11 files** (incl. `harness/compare.py`, `tests/test_harness.py`, `tests/test_v1s_herd.py`, five `analysis/v1*` scripts). The verdict (DELETE) survives because those citations point at *earlier, overwritten* versions of the rolling file and are already unresolvable — but the evidence line was simply false and is corrected, and the deeper problem was promoted to a real finding (next).

3. **MISS ADDED — B5, dangling design-doc citations.** The `prompt.md` grep led me to check the sibling rolling/retired docs. Tracked source cites `plan.md §…` (**19 files**) and `current_phase.md §…` (**26 files**), and **both files were deleted** on 2026-08-11 (`ls` → "No such file"; `README.md:72` confirms the retirement). 45+ code/test comments point at documents a reviewer cannot open. Added as bug **B5 (Med)** and portfolio item #7. This is a more significant portfolio defect than any single stray plan doc, and I had under-weighted it in Pass 1.

4. **MISS ADDED — no CI.** Confirmed `no .github` and no `*.yml`/`*.yaml` config anywhere outside `.venv`. A 390-test suite with no CI is a portfolio gap; added as item #8.

5. **Delete-list coupling tightened.** Verified the `item4_*` and `s8_submission_analysis_tasks.md` plan docs are **cited in docstrings** by `analysis/v1u_oracle.py`, `v1u_travel_ratio.py`, `s8_replay_io.py`. Deleting them piecemeal would *add* to B5, so their verdict was changed from a clean ARCHIVE to "archive as a set, coupled to the B5 sweep." No plan doc should be removed in isolation.

6. **Categories I had skipped, now checked (no new deletions, recorded for completeness):** `harness/bench_agents/` — 4 tracked files (`meta_route.py`, `meta_route_sheep.py`, `reference_ladder.py`, `__init__.py`), live harness baselines, KEEP. `.claude/` — empty. `data/derived/` — 12 tracked files, all on the `.gitignore` allowlist, archival KEEP. `engine_reference/` — re-confirmed never `import`ed (only comment line-refs). No tracked `__pycache__`/`.pyc`.

7. **Unbacked figure flagged.** The "~700 rating" for the heuristic agent (referenced in B1 and §6.1) comes from the **project history / audit brief**, not a measurement taken this pass — I did not run the heuristic on the ladder. Treat it as provenance, not a measured result. Every other number in this review is backed by a command output, a `path:line`, or the test run.

8. **Perf section held to measurement.** I re-checked that I made no unmeasured perf claim. The only concrete perf note (the inert `opponent_tiles` copy) is backed by `git grep`; I explicitly declined to assert any hot-path win because none was measured. No downgrade needed.

**Net effect of Pass 2:** 1 false claim removed, 1 false evidence line corrected, 2 findings added (B5, CI), 1 delete-list verdict tightened, 4 categories confirmed clean. Bug count 4 → 5; portfolio items 7 → 10.
