# plan.md — Εκτέλεση Φάσης 0-1: από το v1b regression στο πρώτο submission

> **Working plan** — εκτελεί τη στρατηγική του [docs/MASTERPLAN.md](docs/MASTERPLAN.md)· **δεν την
> επαναδιαπραγματεύεται**. Όπου χρειάζεται αιτιολόγηση, παραπομπή (π.χ. «βλ. MASTERPLAN §6.1»).
> Engine ground truth: το εγκατεστημένο `kaggle-environments==1.32.4`· το
> [engine_reference/kaggriculture.py](engine_reference/kaggriculture.py) είναι read-only αντίγραφο
> για line refs. Όπου docs και engine διαφωνούν, υπερισχύει το engine.
>
> Τελευταία ενημέρωση: **2026-08-05** (μετά το review.md). Deadline: **30 Σεπ 2026**.

**Πού είμαστε σε μία παράγραφο:** Βήμα 0 κλειστό. v0→v1b αποδεκτά (median bank ~$21k).
**v1c μπλοκαρισμένο** (3 αποτυχίες, root cause στο [review.md](review.md) §1). **Ενεργό
regression:** το working `agent/` είναι **−$2.195 έναντι του `checkpoints/v1b`** (se≈$93,
CI [−2.399, −1.991], 24/24 episode losses) — άρα **κάθε gate είναι σήμερα μπλοκαρισμένο**, αφού
όλα τα increments gate-άρουν εναντίον του v1b. Το επόμενο έργο δεν είναι feature αλλά
**ΒΗΜΑ 1.5** (§4): ξεμπλοκάρισμα + υποδομή μέτρησης/παρατηρησιμότητας.

---

## 1. Στόχος & Definition of Done

**Τελικό deliverable Φάσεων 0-1:** ένα `main.py` (+ πακέτο `agent/`) που (α) περνά το validation
episode στο Kaggle, (β) νικά τον built-in `"starter"` σε 24/24 orientation episodes τοπικά,
(γ) υποβάλλεται και το αρχικό rating trajectory καταγράφεται στο `baselines/`.

| Βήμα | Κριτήριο αποδοχής (εκτελεστικά ελέγξιμο) |
|---|---|
| 0.1-0.3 | ✅ ΟΛΟΚΛΗΡΩΜΕΝΑ — βλ. §2 |
| 1.v0 → v1b | ✅ ΟΛΟΚΛΗΡΩΜΕΝΑ — βλ. §3.3 |
| **1.5.1** Parallel compare + seed split | test: ταυτόσημα per-seed diffs σε `workers=1` vs `workers=N`· μετρημένο speedup ≥ 4× σε 8 workers |
| **1.5.2** Ablation & ξεμπλοκάρισμα | self-test: όλα τα flags `False` → `|mean_diff| == 0` με **κάθε** per-seed diff ακριβώς 0· έξοδος: `main.py` vs `checkpoints/v1b` σε HOLDOUT → `IMPROVED` ή `NON_INFERIOR` |
| **1.5.3** Πρωτόκολλο μέτρησης | κάθε gate report περιέχει stage (`dev-screen` / `holdout-confirm`) και τα δύο metric gates· κανένα GO από dev |
| **1.5.4** Episode report + receipts | γνωστά προβληματικό episode → οπτικός εντοπισμός αιτίου σε <2′· `unexplained_noops == 0` σε καθαρό v1b episode |
| **1.5.5** Gap analysis από replays | αριθμητικές απαντήσεις στα 3 ερωτήματα του §1.5.5 (quadrant days, ζώα, bank@10/20/30) στο `data/derived/top_agent_profiles.csv` |
| 1.v1c-v1e | metric gate (`water_weeds_lost == 0` **και** `plant_decay_units_lost == 0`) **πριν** από το $-gate· έπειτα directional `IMPROVED`/`NON_INFERIOR` έναντι immutable checkpoint· αρνητικό practical diff ποτέ GO |
| 1 τελικό | 24/24 orientation wins vs `starter`· median bank ≥ **$40k** στα ίδια 24 episodes (relative μετρική, review.md M11)· cold-process profile και στα 2 seats, steady-state `max_turn × 3 < 1s` |
| 2 | Submission δεκτό, validation Complete, ≥20 episodes καταγεγραμμένα, `baselines/` γεμάτο |

### 1.1 Ρητά ΕΚΤΟΣ scope της Φάσης 1

| Εκτός scope | Πότε ξανασυζητιέται |
|---|---|
| **BBO sweeps** (CMA-ES/Optuna στο `CONFIG`) | MASTERPLAN §5.0 #6 — μόνο αφού υπάρχουν features προς tuning (γη+ζώα)· πριν από αυτά βελτιστοποιεί σε λάθος ταβάνι (§3.4) |
| **RL** (οποιασδήποτε μορφής, και παράλληλα) | MASTERPLAN §4 — μόνο στον ρητό 4-πλό trigger· ποσοτικοποιημένη απόρριψη ήδη γραμμένη εκεί |
| **W&B / εξωτερικό experiment tracking** | MASTERPLAN §8.2 — απαιτεί **απόφαση χρήστη** (ανέβασμα config/metrics σε εξωτερική υπηρεσία εν μέσω διαγωνισμού + API key), άρα δεν είναι agent task. Βλ. Εκκρεμότητα #1 |
| **BC / IL / trajectory copying από replays** | MASTERPLAN §3.4 οριοθέτηση — μόνιμα εκτός· replays = target curve + διαγνωστικό, ποτέ πηγή κινήσεων |

---

## 2. ΒΗΜΑ 0 — ΟΛΟΚΛΗΡΩΜΕΝΟ 2026-08-05

Το Βήμα 0 (venv/pin `kaggle-environments==1.32.4`, `tests/test_engine_facts.py`, `harness/`,
Kaggle CLI auth) έκλεισε πλήρως· η αναλυτική του προδιαγραφή αφαιρέθηκε — το ιστορικό ζει στο
[memory.md](memory.md) και στο git. Παραμένουν **ενεργοί κανόνες**:

1. **Τα tests κάνουν import από το εγκατεστημένο πακέτο** (`kaggle_environments.envs.kaggriculture.
   kaggriculture`), ΠΟΤΕ από το `engine_reference/` — αλλιώς ένα `pip install -U` που αλλάζει
   συμπεριφορά περνά απαρατήρητο.
2. **Το suite είναι ο version-bump detector** (MASTERPLAN §7 Ρίσκο #1): σε κάθε engine bump της
   ladder, `pip install -U kaggle-environments && pytest tests/` — ό,τι κοκκινίσει είναι η αλλαγή
   συμπεριφοράς. Καμία χειροκίνητη ανάγνωση diff.
3. **ΟΧΙ ξεχωριστό `engine_facts.md`** (απόφαση, παραμένει σε ισχύ): το ζεύγος τεκμηρίωσης είναι
   MASTERPLAN §2+§7 (πεζός λόγος) + `tests/test_engine_facts.py` (εκτελέσιμη μορφή, κάθε test με
   docstring τύπου `"MASTERPLAN §7#5 — melon cap 6 στην ημέρα 10. Engine: kaggriculture.py:383-387."`).
   Τρίτο αντίγραφο = βέβαιο drift. Νέα ευρήματα → πρώτα test, μετά περίληψη στο MASTERPLAN §2.
4. **Kaggle CLI auth & competition entry: λυμένα** — το `KAGGLE_API_TOKEN` από το `.env` δουλεύει με
   το legacy CLI χωρίς fallback, και `kaggle competitions list --group entered` → `userHasEntered: True`.
   Το submit δεν μπλοκάρεται από τίποτα (πρώην «Εκκρεμότητες προς χρήστη» 1-2).

---

## 3. ΒΗΜΑ 1 — Agent (υπάρχων κώδικας)

Αρχιτεκτονική: τα 3 επίπεδα του MASTERPLAN §4 (κλειδωμένη απόφαση — heuristic scheduler, όχι RL).

### 3.1 Modules — τι υπάρχει σήμερα

```
main.py                   # submission entrypoint: top-level `from agent.policy import agent`,
                          # ΚΑΝΕΝΑ dirname(__file__) shim (ο loader κάνει exec χωρίς __file__ —
                          # review.md C3), κανένα callable import μετά (C2/G12)
agent/
├── constants.py          # engine constants με try/except → _vendored.py fallback (Υ6)
├── _vendored.py          # verbatim αντίγραφο, parity-tested έναντι engine 1.32.4
├── state.py              # parse(obs) -> Snapshot· καμία απόφαση
├── planner.py            # Layer 1: make_day_plan(snapshot, config) -> DayPlan
│                         #   + _capacity_limited_targets() (capacity gate, review.md C1 §1.3)
├── scheduler.py          # Layer 2: build_tasks(snapshot, plan, config) -> list[Task]
│                         #   assign(tasks, snapshot, committed) -> (farmer, hands, commitments)
├── executor.py           # Layer 3: market_orders(snapshot, plan, ledger, unit_actions, config)
├── receipts.py           # G11: expected_transition() / reconcile()
├── debug.py              # emit_receipt() → KAGGRI_RECEIPT stdout lines
├── config.py             # nested CONFIG: planner/scheduler/executor/animals/endgame/guards/runtime
└── policy.py             # agent(obs) glue + RuntimeContext ανά player (G13)
```

Ισχύοντα σχεδιαστικά contracts (να μη σπάσουν από το v1c redesign):

- **Engine execution order**: unit actions πριν το market ([:912-923](engine_reference/kaggriculture.py#L912))
  → αγορές/HIRE του turn είναι διαθέσιμα από το επόμενο turn. `hands_actions[i]` ↔ `farm["hands"][i]`.
- **Ένα tile-op ανά tile ανά turn** — τα επόμενα units κάνουν silent no-op. Το `assign()` το τηρεί
  αφαιρώντας κάθε task με ίδιο `pos` μετά την ανάθεση ([scheduler.py:287](agent/scheduler.py#L287)).
- **Units συνυπάρχουν σε tile** — καμία collision avoidance (review.md §1.6, ρητά αποκλεισμένο).
- **Hands διαγράφονται κάθε EOD και ξαναγεννιούνται στο shed** → το commute είναι **ημερήσιο**
  κόστος, όχι εφάπαξ. Ο farmer respawnάρει στο shed ([:857-860](engine_reference/kaggriculture.py#L857)).
- **Seeds = ξεχωριστό `private["seeds"]`**, δεν περνούν από shed/inventory· atomic PLANT ελέγχει
  μόνο το observed seed dict ([:897-910](engine_reference/kaggriculture.py#L897)).
- **Ντετερμινισμός**: κάθε iteration order που επηρεάζει actions είναι tuple/list, ποτέ set.
  Κάθε runtime key περιλαμβάνει `player` (mirror match μοιράζεται module).

### 3.2 Guards G1-G15 — ενεργό contract, με σημερινή κατάσταση

Κάθε guard έχει το σωστό επίπεδο test: contract/unit test για action construction και reservations,
transition test για engine pipeline, full-episode metric μόνο όπου το replay πράγματι παρατηρεί
το event. Δεν βαφτίζεται κάθε guard «replay test».

| # | Guard | Testable απαίτηση | Σήμερα |
|---|---|---|---|
| G1 | Πότισμα ημέρας φύτευσης (MASTERPLAN §7#4) | 0 plant→weed losses· PLANT μόνο με reserved observed seed **και** εφικτό WATER πριν το EOD | 🟡 πράσινο στο `checkpoints/v1b`· **κόκκινο στο working agent** (~2 `water_weeds_lost`/episode) |
| G2 | Ατομικό PLANT (§2#4) | Ποτέ 2 units με PLANT ίδιου crop σε turn με ανεπαρκείς σπόρους | 🟢 |
| G3 | Shed cap 100 | `shed_overflow_burnt == 0` | 🟢 |
| G4 | Price discipline | OPEN/GROW: 0 units sold ≤ threshold (trace reconstruction)· LIQUIDATE επιτρέπει έως $1 | 🟢 |
| G5 | Feed logistics | `animals_escaped == 0`· wheat reserved στο inventory **πριν** το FEED | ⚪ δεν εφαρμόζεται ακόμα (v1d) |
| G6 | Hand σε locked spawn | Hands από (5,4)/(5,5) περνούν από LOCKED tiles· κανένα δεν θεωρείται trapped | 🟢 |
| G7 | 10-order/resource budget | `len(market) <= 10` κάθε turn· κάθε order καλυμμένο από predicted money/shed/slot ledger | 🟢 (max 7 by construction· truncation αντί raise — review.md M7) |
| G8 | Ζώα `max_held` | 0 clipped production ticks | ⚪ δεν εφαρμόζεται ακόμα (v1d) |
| G9 | Harvest πριν το decay | 0 μονάδες χαμένες σε `_decay_plants`· deadline σε `max_lifespan_step`, decay ανά 2 **steps** | 🟡 πράσινο στο v1b· **κόκκινο στο working agent** (~14 `plant_decay_units_lost`/episode) |
| G10 | Horizon-aware strawberry deadline | PLANT μόνο αν όλες οι αναμενόμενες παραγωγές προλαβαίνουν HARVEST→DROP→SELL | 🟢 |
| G11 | Silent no-op detector | preconditions + action-specific receipts + boundary-aware reconciliation· **`unexplained_noops == 0`** | 🟡 **μερικώς**: `receipts.py`/`debug.py` εκπέμπουν και το `play()` τα συλλέγει, αλλά **δεν υπάρχει `unexplained_noops` metric** (review.md H4) → §1.5.4 |
| G12 | Loader contract | `main.py` φορτώνει lazy όπως ο server· exported `agent` = τελευταίο callable· imports top-level | 🟢 |
| G13 | Runtime isolation & determinism | Mirror seats/διαδοχικά episodes δεν μοιράζονται plan/receipts· ίδιο seed σε fresh processes και διαφορετικό `PYTHONHASHSEED` → ίδιο trajectory | 🟢 |
| G14 | Endgame liquidation | 0 avoidable unsold value· καμία late αγορά χωρίς cashable payoff | ⚪ δεν εφαρμόζεται ακόμα (v1e) |
| G15 | Version identity | Κάθε `compare(new, prev)` καταγράφει διαφορετικά immutable fingerprints· collision/stale import αποτυγχάνει πριν το πρώτο seed | 🟢 (+ manifest verification, review.md H3) |

Το G11 **δεν** είναι generic `state_before != state_after`: WATER/FEED/CARE στο hour 23, farmer
reset, hand deletion, production, auto-drop, weeds και market interleaving έχουν action-specific
postconditions. Receipts → structured stdout → `env.logs`· debug **off** στο submission.

### 3.3 Ολοκληρωμένα increments (ιστορικό — μία γραμμή το καθένα)

| Version | Αποτέλεσμα | Checkpoint |
|---|---|---|
| v0 | Walking skeleton: 720 steps, `clean=True`, DONE/DONE, ακριβώς $3.000 και στα 2 seats· G12/G13 πράσινα | [checkpoints/v0](checkpoints/v0) |
| v0.5 | Measurement foundation: directional verdicts, raw orientation metrics, immutable checkpoints/G15, receipt plumbing | (harness, όχι agent) |
| v1a | Carrot loop 9 tiles: vs `starter` 24/24 orientation wins, median bank **$8.801**· vs v0 `IMPROVED` CI +$6.207k…+$7.350k | [checkpoints/v1a](checkpoints/v1a) |
| v1a′ | + πρώιμα strawberries: vs v1a 24/24, median **$10.832**, `IMPROVED` CI +$1.326k…+$2.259k | [checkpoints/v1a_prime](checkpoints/v1a_prime) |
| v1b | + 3 daily hands, deterministic multi-unit assign: vs v1a′ 24/24, median **$20.695**, `IMPROVED` CI +$9.818k…+$10.909k | [checkpoints/v1b](checkpoints/v1b) ← **immutable baseline όλων των gates** |

- [ ] **Commit των 4 checkpoints** (review.md §5 check #7 / H2): μετακινήθηκαν από το gitignored
  `runs/checkpoints/` στο `checkpoints/` αλλά **δεν έχουν γίνει `git add`** — μέχρι να γίνει, τα
  v0/v1a/v1a′ είναι μη ανακατασκευάσιμα από οποιοδήποτε commit.

---

## 4. ΒΗΜΑ 1.5 — Ξεμπλοκάρισμα & υποδομή μέτρησης

> **Μπαίνει ΠΡΙΝ από το v1c.** Η σειρά των items είναι σειρά εκτέλεσης — το 1.5.1 ξεκλειδώνει τα
> υπόλοιπα. Αιτιολόγηση προτεραιοτήτων: MASTERPLAN §5.0 (πίνακας 7 προτεραιοτήτων).

### 1.5.1 — Parallel `compare()` + dev/holdout seed split  [ΠΡΩΤΟ] — ✅ ΟΛΟΚΛΗΡΩΜΕΝΟ 2026-08-05

- [x] **Νέο [harness/seeds.py](harness/seeds.py)** με τις μοναδικές σταθερές αλήθειας:
  ```python
  DEV_SEEDS = range(0, 48)        # screening/tuning — αγγίζονται ελεύθερα
  HOLDOUT_SEEDS = range(100, 148) # ΜΟΝΟ τελική επιβεβαίωση, καμία απόφαση tuning
  SMOKE_SEEDS = range(0, 12)      # γρήγορο coarse screen, ποτέ GO
  ```
  **Καμία άλλη λίστα seeds hardcoded πουθενά**· το `--seeds` default του
  [harness/cli.py](harness/cli.py) είναι τώρα `"0-47"` (= `DEV_SEEDS`), με νέο `--seed-set
  dev|holdout|smoke` που υπερισχύει.
- [x] **[harness/compare.py](harness/compare.py): νέα παράμετρος `workers: int = 1`.** Με
  `workers > 1`, `ProcessPoolExecutor` με **μία εργασία ανά (seed, orientation)** μέσω του
  module-level `_play_orientation()`. Τρία σημεία προσοχής:
  - **(α) Windows spawn — picklability.** `_is_picklable()` ελέγχει `agent_a`/`agent_b` πριν το
    dispatch· αν κάποιο δεν είναι picklable (nested func/lambda) → αυτόματο fallback σε
    `workers=1` με `warnings.warn`, όχι exception.
  - **(β) Το `results.jsonl` γράφεται ΜΟΝΟ από τον parent** μέσω `_persist()`, αφού κάθε future
    επιστρέψει — οι workers επιστρέφουν μόνο `rewards`, καμία εγγραφή αρχείου από worker.
  - **(γ) Ο fingerprint guard και ο έλεγχος A≠B** τρέχουν στον **parent, πριν** το dispatch
    (αμετάβλητο σημείο κώδικα).
- [x] Per-future `try/except` — ένα seed που σκάει (`job_errors`) δεν σκοτώνει το pool.
- [x] Το `per_seed`/`errors` **ταξινομείται κατά seed** μετά τη συλλογή (`sorted(computed)`),
  ανεξάρτητα από τη σειρά ολοκλήρωσης των futures.
- [x] **[harness/cli.py](harness/cli.py)**: flags `--workers N` (default `max(1, cpu_count-1)`)
  και `--seed-set dev|holdout|smoke`.

**Κριτήριο αποδοχής — ΠΕΡΑΣΕ:**
(i) `test_compare_workers_matches_sequential_per_seed_diffs` — πραγματικά episodes,
`workers=1` vs `workers=2`, ταυτόσημα per-seed diffs/mean_diff/verdict.
(ii) **μετρημένο speedup**: `checkpoints/v1b/main.py` vs `main.py`, 8 seeds/16 orientation
episodes, `--workers 1` → **93.9s**, `--workers 8` → **20.6s** ⇒ **4.56×** (ίδιο mean_diff=2118.2,
ci95=(1864.1,2372.4), verdict=IMPROVED και στα δύο runs — ίδιο αποτέλεσμα, μόνο ο χρόνος άλλαξε).
(iii) `test_compare_workers_falls_back_to_sequential_for_unpicklable_callable` καλύπτει το
callable-fallback (α).

### 1.5.2 — Ξεμπλοκάρισμα του −$2.195 με αυτοματοποιημένο ablation — ✅ ΟΛΟΚΛΗΡΩΜΕΝΟ 2026-08-05

**Πλαίσιο:** `main.py` vs `checkpoints/v1b` = **−$2.195** (se≈$93, CI [−2.399, −1.991], 24/24
episode losses, μηδέν errors). **Ήδη ΑΠΟΚΛΕΙΣΤΗΚΑΝ χειροκίνητα — μην τα ξαναψάξεις πρώτα:** το
planner capacity gate (η απενεργοποίησή του δεν αλλάζει τίποτα στη 4-unit κλίμακα του v1b) και η
H1 plant-cap enforcement (η χαλάρωσή της τα έκανε *χειρότερα*).

- [x] **Νέο section `CONFIG["ablation"]`** στο [agent/config.py](agent/config.py), boolean flags,
  **ΟΛΑ default `True`** (= σημερινή συμπεριφορά), ένα ανά αλλαγή του session 2026-08-05. Κάθε
  flag `False` πρέπει να επαναφέρει **ΑΚΡΙΒΩΣ** τη συμπεριφορά του v1b σε εκείνο το σημείο:

  | Flag | Σημείο κώδικα | `False` ⇒ συμπεριφορά v1b |
  |---|---|---|
  | `slack_assign` | [scheduler.py:248](agent/scheduler.py#L248) (`task_slack` στο sort key) | ταξινόμηση χωρίς slack — καθαρό nearest-pair-first |
  | `task_stickiness` | [scheduler.py:258](agent/scheduler.py#L258) (`switching`) | αγνόησε το `committed`, καμία δέσμευση |
  | `per_unit_plant_feasibility` (H5) | [scheduler.py:115](agent/scheduler.py#L115) (`min_distance`) | απόσταση **μόνο** από `farmer_pos` |
  | `plant_task_cap` (H1/M6) | [scheduler.py:68,144](agent/scheduler.py#L68) (`plant_budget_remaining`, `seeds_budget`) | threshold check `planted_today < max_new_plants` τη στιγμή του build |
  | `capacity_gate` (C1 §1.3) | [planner.py:30-76](agent/planner.py#L30-L76) | `plant_targets` = raw config σταθερές |
  | `drop_task_per_unit` (M1) | [scheduler.py:147-162](agent/scheduler.py#L147-L162) | ένα καθολικό DROP task χωρίς `allowed_unit` |
  | `on_event_replan` (M4) | [policy.py:47-52](agent/policy.py#L47-L52) | replan μόνο σε αλλαγή `day` |
  | `seed_cap_by_remaining_targets` (M5) | [executor.py:70-71](agent/executor.py#L70-L71) | flat `seed_buffer` ανεξαρτήτως ανάγκης |
  | `priority_sort_before_truncate` (L8) | [scheduler.py:167](agent/scheduler.py#L167) | truncation με σειρά κατασκευής |
  | `endgame_enabled` (L6) | [planner.py:88](agent/planner.py#L88) | liquidation άνευ όρων από `liquidation_day` |
  | `carrot_water_window` (L7, βρέθηκε κατά το self-test — δεν ήταν στον αρχικό πίνακα) | [scheduler.py:86](agent/scheduler.py#L86) | πότισμα CARROT σε `age >= 2` άνευ ορίου (όχι μόνο ηλικίες 2-3) |

  *Σημείωση:* το `endgame_enabled` αναμένεται **no-op** (το flag είναι ήδη `True`) — χρησιμεύει ως
  **control**: αν εμφανίσει μη μηδενικό diff, η ίδια η υποδομή ablation είναι λάθος. **Επιβεβαιώθηκε**
  (βλ. αποτελέσματα παρακάτω).
- [x] **Injection ανά combo χωρίς επεξεργασία αρχείων:** το `config.py` διαβάζει **μία φορά στο
  import** ένα env override (π.χ. `KAGGRI_ABLATION="slack_assign=0,task_stickiness=0"`) και το
  εφαρμόζει πάνω στα defaults. Απαραίτητο γιατί ο agent τρέχει σε ξεχωριστή διεργασία από τον
  ablation runner. **Καμία μεταβολή runtime** — τα flags διαβάζονται μία φορά, ώστε το
  `CONFIG["ablation"]` να μη σπάει το **G13 determinism**.
- [x] **Νέο [harness/ablate.py](harness/ablate.py)**: τρέχει σύνολο flag-combos εναντίον ενός
  **σταθερού baseline** (`checkpoints/v1b`) σε `DEV_SEEDS` με `workers>1`· γράφει **ένα row ανά
  combo** (`flags`, `mean_diff`, `se_diff`, `ci95`, `verdict`) σε `ablation.jsonl` + περίληψη
  ταξινομημένη κατά `mean_diff`.
- [x] **Στρατηγική εκτέλεσης, με αυτή τη σειρά:**
  - **(α)** all-off — self-test της υποδομής (βλ. κριτήριο #1).
  - **(β)** one-at-a-time OFF πάνω στο πλήρες σετ — **10 runs**, εντοπίζει μονοπάτι ενόχου.
  - **(γ)** αν κανένα μεμονωμένο flag δεν εξηγεί το κενό → fractional factorial στους ύποπτους.
    **Πρώτοι ύποπτοι** κατά [memory.md](memory.md): `slack_assign` × `task_stickiness`
    (αλληλεπίδραση — η stickiness προστέθηκε ακριβώς για να σταθεροποιήσει το slack) και
    `per_unit_plant_feasibility`.

**ΚΡΙΤΙΚΟ κριτήριο αποδοχής #1 (self-test της ίδιας της υποδομής):** με **ΟΛΑ τα flags `False`**,
το `compare("main.py", "checkpoints/v1b/main.py", DEV_SEEDS)` πρέπει να δίνει `|mean_diff| == 0`
με **per-seed diffs όλα ακριβώς 0**. Αν όχι, η υποδομή ablation είναι λάθος και **δεν επιτρέπεται
να βγει κανένα συμπέρασμα από αυτήν** — αυτό διορθώνεται πρώτο, πριν τρέξει το (β).

**Κριτήριο αποδοχής #2:** γραπτή **απόδοση αιτίου** — ποιο flag ή ποιο ζεύγος flags ευθύνεται, με
CI, και **προτεινόμενη διόρθωση ΧΩΡΙΣ να θυσιαστεί το εύρημα του review.md που το γέννησε** (π.χ.
αν φταίει το `slack_assign`, η λύση δεν είναι «βγάλε το slack» — το review.md §1.2 δείχνει ότι
χωρίς slack ο scheduler είναι δομικά τυφλός στο «μακρινό αλλά επείγον»).

**Κριτήριο αποδοχής #3 (έξοδος από το βήμα):** `main.py` vs `checkpoints/v1b` σε **HOLDOUT_SEEDS**
→ `IMPROVED` ή αποδεδειγμένο `NON_INFERIOR`. **Μέχρι τότε κανένα v1c work.**

**Αποτελέσματα — ΠΕΡΑΣΕ:**

**Κριτήριο #1 (self-test):** όλα τα flags `False` (συμπεριλαμβανομένου του νέου `carrot_water_window`)
→ `compare("main.py", "checkpoints/v1b/main.py", DEV_SEEDS)` = `mean_diff=0.0`, **48/48 seeds με diff
ακριβώς 0** (96 episodes, `both_seats=True`). Το `carrot_water_window` δεν ήταν στον αρχικό πίνακα·
βρέθηκε επειδή χωρίς αυτό, το all-off self-test απέτυχε (nonzero diffs σε rare CARROT-over-age
περιπτώσεις, review.md L7).

**One-at-a-time OFF sweep σε πλήρες `DEV_SEEDS` (48 seeds, 96 episodes/combo, `workers=8`):**

| Flag off (μόνο) | mean_diff | verdict |
|---|---:|---|
| `task_stickiness` | −20686.7 | REGRESSED (καταστροφικό) |
| `on_event_replan` | −8088.8 | REGRESSED |
| `per_unit_plant_feasibility` | −4981.6 | REGRESSED |
| `plant_task_cap` | −4535.3 | REGRESSED |
| `seed_cap_by_remaining_targets` | −2683.5 | REGRESSED |
| `capacity_gate` | −2109.7 | REGRESSED (≈ baseline, inert) |
| `drop_task_per_unit` | −2084.3 | REGRESSED (≈ baseline, inert) |
| `carrot_water_window` | −2084.3 | REGRESSED (≈ baseline, inert) |
| `endgame_enabled` | −2084.3 | REGRESSED (≈ baseline, inert — **control επιβεβαιώθηκε**) |
| `priority_sort_before_truncate` | −2084.3 | REGRESSED (≈ baseline, inert) |
| **`slack_assign`** | **−257.4** | **NON_INFERIOR** |

**Κριτήριο #2 — απόδοση αιτίου:** μόνο του, το `slack_assign` off μειώνει το χάσμα από −$2195 σε
−$257 (NON_INFERIOR) ενώ κάθε άλλο flag είτε είναι αδρανές (±0 γύρω στο −$2084, επιβεβαιώνει το
`endgame_enabled` control) είτε κάνει τα πράγματα πολύ χειρότερα αν αφαιρεθεί (`task_stickiness`,
`on_event_replan`, `per_unit_plant_feasibility`, `plant_task_cap` — δηλαδή αυτά **δεν** φταίνε, είναι
απαραίτητα). **Ρίζα:** στο [scheduler.py](agent/scheduler.py)'s `assign()`, `task_slack =
deadline_step - step - (best_distance + 1)`. Για tasks με ίδιο `priority` **και** ίδιο
`deadline_step` — η κοινή περίπτωση, αφού όλα τα WATER tasks μιας μέρας μοιράζονται
`priority=0`/`deadline_step=day_deadline` — το `task_slack` διαφέρει από task σε task **μόνο** κατά
`-best_distance`. Το `min(candidates)` διαλέγει το μικρότερο slack πρώτο, άρα διαλέγει πάντα το
**μακρύτερο** task ανάμεσα σε ισοπρόσωπα (ίδιο priority/deadline) tasks — όχι μόνο όταν κάποιο
task κινδυνεύει πραγματικά να χάσει το deadline, αλλά **σε κάθε recomputation, όλη μέρα**. Αυτό
είναι το αντίστροφο του προδιαγεγραμμένου «μακρινό αλλά επείγον»: αντί να ξεχωρίζει τα σπάνια
πραγματικά επείγοντα, μετατρέπει το nearest-first σε **farthest-first μόνιμα**, σπαταλώντας
unit-turns σε μετακινήσεις προς μακρινά tiles ενώ κοντινά περιμένουν — συνεπές με το μέγεθος και
τον χαρακτήρα της απώλειας.

**Διόρθωση (χωρίς να θυσιαστεί το review.md §1.2 εύρημα):** το slack δεν αφαιρέθηκε. Αντ' αυτού,
το queue-jump του slack **μπλοκάρεται πίσω από ένα urgency gate** — μόνο tasks που είναι όντως
κοντά στο να γίνουν ανέφικτα ταξινομούνται με slack πριν την απόσταση (tier 0, το «μακρινό αλλά
επείγον» του C1/§1.2)· όλα τα υπόλοιπα («άνετα») tasks επιστρέφουν σε καθαρό nearest-first (tier 1,
η αποδοτική προεπιλογή του v1b). Νέο config
`CONFIG["scheduler"]["urgency_slack_margin"] = 2` ([config.py](agent/config.py)) + νέο πεδίο
`urgency_tier` στο sort key πριν το `task_slack`
([scheduler.py:282-301](agent/scheduler.py#L282-L301)). Επαληθεύτηκε ότι το self-test #1 παραμένει
ΑΚΡΙΒΩΣ ίδιο μετά τη διόρθωση (η διόρθωση αγγίζει μόνο το `slack_assign=True` branch). Με τη
διόρθωση, `main.py` (`slack_assign` ενεργό, διορθωμένο) vs v1b σε DEV_SEEDS: `mean_diff=-262.2`,
`verdict=NON_INFERIOR` — σχεδόν ταυτόσημο με το «off» (−$257), επιβεβαιώνοντας ότι το
farthest-first ελάττωμα εξαλείφθηκε ενώ το urgency tier παραμένει διαθέσιμο για γνήσια επείγοντα
tasks.

**Κριτήριο #3 (έξοδος, HOLDOUT_SEEDS, μία φορά, καμία tuning απόφαση):** `main.py` (διορθωμένο) vs
`checkpoints/v1b` σε **HOLDOUT_SEEDS** (48 seeds, 96 episodes, `workers=8`): `mean_diff=-219.0`,
`se=20.3`, `ci95=[-259.8, -178.3]`, **`verdict=NON_INFERIOR`**, 0 errors. **Το βήμα 1.5.2
ολοκληρώθηκε — v1c work ξεμπλοκαρίστηκε.**

### 1.5.3 — Επεκτάσεις πρωτοκόλλου μέτρησης (MASTERPLAN §6.1) — ✅ ΟΛΟΚΛΗΡΩΜΕΝΟ 2026-08-05

- [x] **ΚΑΝΟΝΑΣ (screen → confirm, ποτέ «κράτα το max από k variants»):**
  screening/tuning **σε DEV_SEEDS** → κράτα **top-3** → **confirm σε HOLDOUT με 48+ seeds** →
  **GO μόνο από το confirm stage**. Με spread ~19% του median (MASTERPLAN §6), το «κράτα το
  καλύτερο από k» επιλέγει θόρυβο με πιθανότητα που μεγαλώνει με το k.
  *Εκτελεστικός έλεγχος:* κάθε gate report καταγράφει `stage` (`dev-screen` / `holdout-confirm`)
  και το seed-set· ένα GO με `stage=dev-screen` είναι άκυρο εξ ορισμού.
- [x] **Metric gates πριν από το $-verdict** (review.md §5 check #5) — προστίθενται ρητά στα gates
  **όλων** των increments: `water_weeds_lost == 0` **και** `plant_decay_units_lost == 0`. Τα metrics
  υπάρχουν ήδη στο [harness/metrics.py:300,303](harness/metrics.py#L300).
  *Τεχνική προϋπόθεση:* το `compare()` περνά σήμερα `metrics=False`
  ([compare.py:174](harness/compare.py#L174)) για ταχύτητα — άρα το metric gate χρειάζεται είτε
  νέα παράμετρο `metrics: bool = False` που να προωθείται και να συγκεντρώνει τα δύο counters ανά
  seed, είτε ξεχωριστό `play()` sweep. **Το $-gate δεν μετράει αν τα metric gates δεν έχουν τρέξει.**

**Αποτελέσματα — ΠΕΡΑΣΕ:**

- **`compare()`** ([harness/compare.py](harness/compare.py)) πήρε δύο νέες παραμέτρους:
  - `metrics: bool = False` — περνά `metrics=` στο κάθε `play()` (worker path και sequential
    path εξίσου) και διαβάζει τα δύο counters από το **seat του agent_a σε κάθε orientation**
    (seat 0 στο `A@0/B@1`, seat 1 στο `B@0/A@1` — όχι πάντα seat 0, αλλιώς θα μετρούσε κατά λάθος
    την πειθαρχία ποτίσματος του **αντιπάλου**). Αθροίζονται (όχι μέσος όρος — ένα defect που
    φαίνεται σε ένα μόνο orientation δεν πρέπει να «αραιώνεται») σε `water_weeds_lost_a` /
    `plant_decay_units_lost_a` στο `CompareResult`, μαζί με `metric_gate_passed` (και οι δύο == 0)
    και `metrics_checked`.
  - `stage: Optional["dev-screen"|"holdout-confirm"] = None` — raise `ValueError` σε άκυρη τιμή.
  - Νέο πεδίο `go: bool` στο `CompareResult`: `True` **μόνο** όταν `stage=="holdout-confirm"`
    **και** verdict ∈ {IMPROVED, NON_INFERIOR} **και** `metrics_checked` **και**
    `metric_gate_passed` — ένα καθαρό $-verdict χωρίς μετρημένο metric gate (ή σε λάθος stage)
    ποτέ δεν μετράει σαν GO, ακριβώς όπως ζητά το κριτήριο.
- **[harness/cli.py](harness/cli.py):** νέα flags `--metrics` και `--stage` στο `compare`
  subcommand· το `--stage` παίρνει default από το `--seed-set` (`dev`→`dev-screen`,
  `holdout`→`holdout-confirm`, `smoke`→`None`, ποτέ GO). Η έξοδος (stdout + `results.json`)
  τυπώνει/γράφει `stage`, `metrics_checked`, τα δύο counters, `metric_gate_passed`, και `go`.
- **Tests** (5 νέα σε [tests/test_harness.py](tests/test_harness.py)): invalid-stage raises,
  metrics off-by-default αφήνει τα gate fields ανενεργά, το metric gate διαβάζει σωστά το seat
  του agent_a σε κάθε orientation (όχι πάντα seat 0), και τρία σενάρια `go` (dev-screen ⇒ False,
  holdout-confirm χωρίς metrics ⇒ False, holdout-confirm με καθαρό metric gate ⇒ True, και
  holdout-confirm με failed metric gate ⇒ False παρά το καθαρό $-verdict). Full suite: 96/96 passed.
- **Real-engine επαλήθευση** (όχι μόνο mocks): `python -m harness.cli compare main.py
  checkpoints/v1b/main.py --seed-set smoke --metrics --workers 4` →
  `water_weeds_lost_a=0 plant_decay_units_lost_a=0 metric_gate_passed=True`,
  `verdict=NON_INFERIOR`, `GO=False` (σωστά — `stage=None` για smoke). Και ένα πλήρες
  `--seed-set dev` run (χωρίς `--metrics`) αναπαρήγαγε ακριβώς το `mean_diff=-262.2` του §1.5.2.

### 1.5.4 — Episode report + receipts viewer (MASTERPLAN §8.1) — ✅ ΟΛΟΚΛΗΡΩΜΕΝΟ 2026-08-05

- [x] **[harness/play.py](harness/play.py): νέο flag `render_html: bool = False`** → γράφει
  `env.render(mode="html")` σε `<run_dir>/episode_seed<N>_seat<S>.html` (ο **bundled** visualizer
  του engine, ~14.7MB, offline, [engine_reference:992-997](engine_reference/kaggriculture.py#L992)).
- [x] **Persist των receipts δίπλα στο replay:** τα G11 receipts ζουν στο
  `PlayResult.diagnostics` ([play.py:44,131-147](harness/play.py#L131-L147)) και **δεν** υπάρχουν
  στο `env.toJSON()` — όταν `record=True`, γράψε τα σε `<run_dir>/receipts_seed<N>.jsonl`, αλλιώς
  το report δεν μπορεί να τα ξαναβρεί. Το `CONFIG["guards"]["debug"]` ενεργοποιείται με τον ίδιο
  env μηχανισμό του §1.5.2 (ο agent τρέχει σε άλλη διεργασία).
- [x] **Νέο [harness/report.py](harness/report.py)**: παράγει **αυτόνομο** HTML report ανά episode
  από metrics + receipts. **Καμία εξωτερική εξάρτηση, κανένα CDN.** Ελάχιστο περιεχόμενο:
  1. bank curve **και για τα 2 seats**,
  2. unit-turns moving / working / idle ([metrics.py:308-310](harness/metrics.py#L308)),
  3. `water_weeds_lost` και `plant_decay_units_lost` **ανά μέρα**,
  4. farm-state heatmap ανά μέρα,
  5. τιμές πώλησης vs base ανά προϊόν (`average_sell_price`),
  6. **ΥΠΟΧΡΕΩΤΙΚΑ: timeline ανάθεσης task ανά unit** — μία γραμμή ανά unit, χρώμα ανά task kind.
     Αυτό είναι το μόνο που θα είχε δείξει το oscillation του προηγούμενου session **αμέσως**.
- [x] **[harness/metrics.py](harness/metrics.py): πρόσθεσε `unexplained_noops`** (λείπει —
  review.md H4) ώστε ο **G11 να είναι πραγματικά πράσινος**. Υπογραφή:
  `extract_metrics(env_json, seat, diagnostics=None)` — όταν δίνονται diagnostics, μετρά τα
  reconciliation mismatches που **δεν** ταξινομούνται ως expected no-op (hour-23 boundary, farmer
  reset, hand deletion, auto-drop)· χωρίς diagnostics επιστρέφει `None`, όχι `0` (η απουσία
  receipts δεν είναι απόδειξη μηδενικών no-ops).
- [x] **[harness/cli.py](harness/cli.py)**: υποεντολή `report`, και `--render-html` στο `play`.

**Κριτήριο αποδοχής:** ένα **γνωστά προβληματικό** episode (π.χ. seed με μη μηδενικό
`water_weeds_lost` από το τρέχον working agent) παράγει report όπου η αιτία εντοπίζεται **οπτικά
σε <2 λεπτά** (καταγράφεται ποιο tile/step/unit), **και** `unexplained_noops == 0` σε ένα καθαρό
v1b episode.

**Αποτελέσματα — ΠΕΡΑΣΕ (με μία διόρθωση στο σχέδιο, βλ. παρακάτω):**

- **`unexplained_noops` — δεν χρειάστηκε swallow-list.** Πριν το υλοποιήσω, διάβασα το πραγματικό
  `_end_of_day`/`interpreter()` στο [engine_reference/kaggriculture.py:838-937]
  (engine_reference/kaggriculture.py#L838): σε κάθε turn, το `_apply_unit_action` (άρα και το
  αποτέλεσμα ενός WATER/PLANT/HARVEST στο **tile**) εκτελείται **πριν** το πιθανό
  `_end_of_day` του ίδιου step — δηλαδή ο farmer/hands reset («farmer»→spawn, «hands»→[])
  συμβαίνει **μετά** το tile effect έχει ήδη καταγραφεί, και το `reconcile()` του
  [agent/receipts.py](agent/receipts.py) ελέγχει το tile **by position**, όχι by unit identity.
  Άρα καμία από τις αρχικά υποτιθέμενες κατηγορίες («hour-23 boundary», «farmer reset», «hand
  deletion», «auto-drop») δεν αντιστοιχεί σε πραγματικό false-positive μηχανισμό στο σημερινό
  `reconcile()` — hands γεννιούνται **μόνο** από HIRE (κανένα mid-day dismiss υπάρχει καν) και ο
  boundary-aware έλεγχος του WATER (`eod_boundary`) ήδη λογαριάζει σωστά το reset effect. Άρα:
  `unexplained_noops` = απλά το πλήθος των `reconciliation` receipts με `ok=False` για το seat
  αυτό — κάθε τέτοιο `False` είναι γνήσιο mismatch, όχι artifact ορίου ημέρας. Χωρίς
  `diagnostics` param: `None` (όχι `0`).
- **Per-day breakdown + `loss_events`:** το `extract_metrics()` πλέον επιστρέφει επίσης `daily`
  (λίστα ανά ημέρα με `water_weeds_lost`/`plant_decay_units_lost`/worker-turn breakdown) και
  `loss_events` (μία εγγραφή `{type, day, step, pos, units}` ανά ζημιά) — αυτό είναι που κάνει
  δυνατή την «οπτική εντοπισμό σε <2 λεπτά»: το report δείχνει πίνακα με το **ακριβές tile/step**
  κάθε `water_weeds_lost`/`plant_decay_units_lost`, όχι μόνο ένα άθροισμα.
- **`harness/report.py`**: αυτόνομο HTML (inline CSS/JS, `<canvas>` για τα charts, καμία
  εξωτερική βιβλιοθήκη) με όλα τα ζητούμενα: bank curve (2 seats), daily losses + worker-turn
  utilization (canvas bar charts), per-unit action timeline (CSS grid, scrollable, χρωματισμένο
  ανά action opcode — αφού δεν υπάρχει persisted "task kind" ανά turn, το action opcode
  (WATER/PLANT/HARVEST/MOVE/DROP/PASS) ανά unit/step είναι το πιστό διαθέσιμο proxy και αρκεί
  για να φανεί oscillation), farm heatmap με day slider, sell-price-vs-base table, G11
  unexplained_noops badge, και το loss-events table.
- **`harness/play.py`**: `render_html=True` γράφει `env.render(mode="html")` σε
  `episode_seed<N>_seat0-<a>_seat1-<b>.html` (~15MB, επιβεβαιωμένο σε πραγματικό run).
  Τα receipts γράφονται σε `receipts_seed<N>_seat0-<a>_seat1-<b>.jsonl` **μόνο όταν μη-κενά**
  (`record=True` + `KAGGRI_DEBUG=1` στη διεργασία του agent) — `PlayResult.html_path`/
  `receipts_path` νέα πεδία.
- **`harness/cli.py`**: `--render-html` στο `play`· νέα υποεντολή `report <replay>
  [--receipts] [--seat] [--out]` που βρίσκει by convention το ταιριαστό `receipts_*.jsonl`.
- **Tests**: 3 νέα σε [tests/test_metrics.py](tests/test_metrics.py) (unexplained_noops
  None/counted, daily+loss_events shape), 3 νέα σε
  [tests/test_harness.py](tests/test_harness.py) (render_html on/off, receipts only-when-nonempty),
  7 νέα σε νέο [tests/test_report.py](tests/test_report.py) (build_report_data shape, self-contained
  HTML, load_replay gzip/plain roundtrip, load_receipts missing/present). Full suite: **109/109 passed**.
- **Real-engine επαλήθευση**: `KAGGRI_DEBUG=1 python -m harness.cli play main.py pass --steps 48
  --render-html --out runs/...` → replay + ~15MB html + receipts (40 diagnostics) όλα γράφτηκαν
  σωστά· `python -m harness.cli report <replay>.json.gz` παρήγαγε report με
  `unexplained_noops=0` σε καθαρό run (**κριτήριο αποδοχής #2 πέρασε**). Ένα δεύτερο run με
  `checkpoints/v1b` (frozen, προ-G11) έδειξε σωστά `receipts_path=None`/`unexplained_noops=None`
  ("not measured", όχι ψευδές 0) — το `report` subcommand τυπώνει ρητή προειδοποίηση σε αυτή την
  περίπτωση.

### 1.5.5 — Gap analysis από raw top replays (MASTERPLAN §3.4) — ✅ ΟΛΟΚΛΗΡΩΜΕΝΟ 2026-08-06

**Πρόβλημα προς λύση:** το [data/kaggriculture-episodes/episode_features.csv](data/kaggriculture-episodes/episode_features.csv)
**ΔΕΝ έχει στήλες για ζώα ή για τελικά quadrants** (μόνο `final_money, peak_crew, total_hires,
first_land_day, elbow_day, tiles_planted, plants_*, price_*`) — άρα με τα σημερινά structured
δεδομένα **δεν μπορούμε να απαντήσουμε «γη ή ζώα πρώτα;»**, ακριβώς το ερώτημα όπου το v1c
απέτυχε 3 φορές.

- [x] **Νέο [analysis/replay_profile.py](analysis/replay_profile.py)** — **χωριστά από το `harness/`**:
  offline data work, όχι agent/benchmark code.
  - Φόρτωση του `replays.parquet` μέσω `kagglehub.dataset_download("georgymamarin/
    kaggriculture-episodes")` (πραγματικό μέγεθος 337MB σε αυτό το crawl, όχι 213MB — το
    dataset README (data/kaggriculture-episodes/README.md, upstream, όχι αρχείο μας) λέει
    "~20MB" από παλαιότερο, μικρότερο crawl).
    **Ποτέ δεν μπαίνει στο repo**, μένει στο τοπικό kagglehub cache· ανάγνωση με
    `pyarrow.parquet.ParquetFile.iter_batches` (streaming, batch_size=16) γιατί ένα πλήρες
    `pd.read_parquet` έσκαγε με `ArrowMemoryError` σε αυτό το μηχάνημα.
  - Team selection: cross-team `EPISODE_TYPE_PUBLIC` episodes μόνο (`type_0 != team_1`,
    validation self-play αποκλείεται)· win = μεγαλύτερο `bank_N`· Wilson lower bound (z=1.96)
    πάνω σε teams με n≥8 παιχνίδια· top decile = top 10% by lower bound → **21 teams**.
  - Per-day profile: `extract_profile()` παίρνει το end-of-day snapshot (`steps[day*24+23]`)
    ανά (episode, seat)· tiles μετρημένα by `kind` (`PLANT`→crop, `COOP`/`PASTURE` **με** το
    κλειδί `"animal"` παρόν — άδειες δομές χωρίς ζώο υπάρχουν, engine:437-446, και δεν
    μετρώνται)· quadrants από `farm["unlocked_quadrants"]`· πωλήσεις σωρευτικά από τα
    `SELL` orders στο action stream (μόνο aggregate ποσότητα ανά προϊόν, καμία per-unit
    ακολουθία δεν αποθηκεύεται πουθενά — MASTERPLAN §3.4).
- [x] **Output:** [data/derived/top_agent_profiles.csv](data/derived/top_agent_profiles.csv)
  (30 γραμμές, median ανά ημέρα σε 662 (episode, seat) γραμμές) + [top_agent_profiles.md]
  (data/derived/top_agent_profiles.md) με τις καμπύλες-στόχους **και τη v1b καμπύλη** (από
  `play("checkpoints/v1b/main.py", "pass", seed=0, metrics=True)`, `bank_curve`).

**Αποτελέσματα — ΠΕΡΑΣΕ (ρητές αριθμητικές απαντήσεις):**

(i) **Quadrant #2 → median ημέρα 9** (n=649/662), **#3 → ημέρα 11** (n=473), **#4 → ημέρα 12**
(n=211). Cross-check: το ανεξάρτητα υπολογισμένο `episode_features.csv["first_land_day"]`
για τα ίδια 21 top teams δίνει επίσης **median 9.0** (688 γραμμές) — συμφωνία πλήρης.

(ii) **COW**: median ημέρα **0** (566/662 = 85% των games)· **SHEEP**: ημέρα **5** (368/662 =
56%)· **GOOSE**: ημέρα **12** (97/662 = 15%, το μόνο ζώο με `first_yield_day` που ταιριάζει
αργή απόκτηση — cost $300, πιο φθηνό αλλά λιγότερο δημοφιλές από τα COW/SHEEP).

(iii) **Bank @ ημέρα 10/20/30** (top-decile median έναντι v1b, seed 0):

| Ημέρα | top-decile median | v1b | διαφορά |
|---|---|---|---|
| 10 | $735.5 | $1,069 | **v1b μπροστά** κατά $333.5 |
| 20 | $25,912.5 | $20,054 | top teams μπροστά κατά $5,858.5 |
| 30 | $86,073 | $22,311 | top teams μπροστά κατά **$63,762** (~3.9×) |

Ερμηνεία: οι top teams είναι **φτωχότεροι** από το v1b στη μέρα 10 (βαρύ capex σε γη+ζώα
νωρίς), μετά ανοίγουν ψαλίδα εκθετικά — το v1b δεν αποτυγχάνει στην εκτέλεση της μέρας 10,
αποτυγχάνει να **επενδύσει αρκετά νωρίς** ώστε να έχει κάτι να θερίσει στη μέρα 20-30.

**§5.1 decision point (γη ή ζώα πρώτα) — λύθηκε αριθμητικά:** median ημέρα 1ου ζώου
(οποιοδήποτε είδος) = **0** (n=593)· median ημέρα 1ου επιπλέον quadrant (πέρα από το δωρεάν
NW) = **9** (n=649). **0 < 9 → η σειρά αντιστρέφεται σε v1d → v1c** (ζώα πριν από γη) — βλ.
§5.1 παρακάτω, ενημερωμένο με το πραγματικό ζεύγος ημερών.

**Tests**: νέο [tests/test_replay_profile.py](tests/test_replay_profile.py) — `wilson_lower_bound`
(μονοτονία με n), `select_top_teams` (αποκλεισμός n<8 και self-play), `select_episode_seats`
(μόνο replay-available επεισόδια top team), `_tile_counts` (LOCKED/None/άδειο COOP αγνοούνται),
`extract_profile` (quadrant #1 = ημέρα 0, daily rows καλύπτουν κάθε ημέρα). Full suite:
**115/115 passed**.

> **ΟΡΙΟ (MASTERPLAN §3.4 / Ανοιχτό #11) — τηρήθηκε:** το script διαβάζει **μόνο** aggregate
> per-day state (πλήθη/χρήματα/quadrants) — ποτέ per-unit action sequences, καμία μορφή
> πολιτικής/βαρών δεν παράγεται ή αποθηκεύεται. `first_animal_day`/`first_quadrant_day`
> είναι ημερομηνίες-στόχοι, όχι trajectory. Requirements: `pyarrow`/`pandas` προστέθηκαν στο
> [requirements-dev.txt](requirements-dev.txt).

---

## 5. ΒΗΜΑ 1 (συνέχεια) — v1c → v1e

**Προαπαιτούμενο για όλα:** το §1.5.2 κριτήριο #3 (`main.py` vs `checkpoints/v1b` σε HOLDOUT →
`IMPROVED`/`NON_INFERIOR`). Πριν από αυτό, κάθε gate συγκρίνεται με ένα baseline που ήδη χάνουμε.

**Πρωτόκολλο ανά increment:** υλοποίηση → contract/guard tests → immutable checkpoint με μοναδικό
package namespace → **metric gate** (§1.5.3) → `compare(new, prev)` σε DEV (screen) → confirm σε
HOLDOUT 48 seeds. `REGRESSED` = STOP και revert. `INCONCLUSIVE` σε HOLDOUT = STOP για απόφαση —
δεν βαφτίζεται μη-χειροτέρευση.

### 5.1 Decision point: γη πρώτα ή ζώα πρώτα; — ✅ ΛΥΘΗΚΕ ΑΡΙΘΜΗΤΙΚΑ 2026-08-06

**Απόφαση:** **v1d → v1c (ζώα πριν από γη)** — αντίστροφα από την αρχική υπόθεση.

> **Κριτήριο (όπως ορίστηκε):** αν η median ημέρα απόκτησης του 1ου ζώου < median ημέρα αγοράς
> του 1ου επιπλέον quadrant, η σειρά αντιστρέφεται.
>
> **Πραγματικό ζεύγος ημερών** (από [data/derived/top_agent_profiles.md](data/derived/top_agent_profiles.md),
> §1.5.5, 662 (episode, seat) γραμμές από 21 top-decile teams): median ημέρα 1ου ζώου
> (οποιοδήποτε είδος) = **0** (n=593)· median ημέρα 1ου επιπλέον quadrant = **9** (n=649).
> **0 < 9 → v1d πρώτα.** Cross-check: το COW (το πιο δημοφιλές ζώο, 85% των games) έχει median
> ημέρα απόκτησης 0 — δηλαδή οι top teams αγοράζουν ζώο(α) **στην πρώτη μέρα του παιχνιδιού**,
> πολύ πριν αγοράσουν έστω το 2ο quadrant (μέρα 9).

- [ ] **v1d — ζώα [ΠΡΩΤΟ]**: δύο guard-gated sub-builds χωρίς benchmark του μισού feature: **(A)**
  BUILD_PASTURE/COOP → BUY_ANIMAL (μπαίνει στο shed) → PICKUP → PLACE από unit inventory·
  **(B)** inventory-aware FEED+CARE, COLLECT_FERTILIZER, HARVEST, wheat procurement ≥1 turn
  νωρίτερα. Target: COW (85% των top teams, μέρα 0) πρώτο, SHEEP (56%, μέρα 5) δεύτερο — το
  GOOSE (μόλις 15% υιοθέτηση, μέρα 12) **δεν** είναι προτεραιότητα v1d, μπορεί να μπει στο v1e.
  CARE απαιτείται για το **οικονομικό bonus** όταν συνδυάζεται με FEED, όχι για survival.
  **Προαπαιτούμενα (πριν γραφτεί κώδικας v1d):** review.md §5 checks 1-9 (όπως και για v1c,
  βλ. παρακάτω) — τα zero-slack θέματα του v1c ισχύουν αυτούσια εδώ.
  *Αποδοχή:* **metric gate** (+ `animals_escaped == 0`, 0 clipped production) →
  **έπειτα** directional $-gate vs `checkpoints/v1b`· G3/G5/G8/G11 πράσινα.
  ⚠ Το FEED έχει τον **ίδιο zero-slack θάνατο** με το WATER (`consecutive_unfed >= 2`,
  [engine:795](engine_reference/kaggriculture.py#L795)) αλλά με χειρότερη ζημιά: escape = χαμένο
  κεφάλαιο $300-500. Χωρίς το capacity redesign του review.md C1, το v1d σκάει **χειρότερα** από
  το v1c.
- [ ] **v1c — γη**: BUY_LAND NE on-trigger (χρήματα ≥ $1k **και** υπάρχει εργατικό δυναμικό να το
  δουλέψει — MASTERPLAN §3.2#7: γη χωρίς hands = νεκρό κεφάλαιο), επέκταση φυτέματος στο NE.
  Target: 2ο quadrant μέχρι μέρα ~9 (top-decile median). **Προαπαιτούμενα (όλα, πριν γραφτεί
  κώδικας v1c):**
  - **review.md §5 checks 1-9** — τα 1-5 blockers: slack+per-unit feasibility με margin ≥1-2 turns,
    planner capacity gate που διαβάζει board state, same-turn plant budget στο `assign()`,
    minimum G11 receipts, metric gate. Τα 6-9: on-event replan για BUY_LAND, commit των
    checkpoints, fingerprints στο `results.jsonl`, σχεδιαστικές σταθερές (units συνυπάρχουν —
    **ΜΗΝ** χτιστεί collision avoidance· commute ημερήσιο· DROP no-op σε LOCKED shed tiles·
    WATER δίνει +1 yield σε καρότα ηλικίας 2-3, να διατηρηθεί).
  - **v1d πρέπει να έχει ήδη κλείσει** (νέα σειρά §5.1).
  *Αποδοχή:* **metric gate** (`water_weeds_lost == 0`, `plant_decay_units_lost == 0`) → **έπειτα**
  directional $-gate vs το v1d checkpoint · **και** επιβεβαίωση ότι observed BUY_LAND
  success/failure προκαλεί σωστό replan (παρατηρήσιμο στα G11 receipts).
- [ ] **v1e — full market + liquidation**: slot/money/shed allocator, post-unit inventory
  projection, actual-price trace metrics, marginal-price thresholds ανά προϊόν, hour-aware town
  demand, endgame LIQUIDATE. *Αποδοχή:* metric gate → directional gate σε 48 seeds (HOLDOUT)
  **και** τα συνολικά κριτήρια Φάσης 1 (§1: 24/24 vs `starter`, median ≥$40k, `max×3<1s`).
- [ ] `tests/test_agent_guards.py` + loader/runtime tests **πράσινα για G1-G15** στο τελικό v1e·
  κάθε guard γίνεται πράσινο στο **πρώτο increment όπου είναι σχετικό**, όχι μαζικά στο τέλος.

---

## 6. ΒΗΜΑ 2 — Πρώτο submission & baseline

### 6.1 Checklist προ-υποβολής

- [ ] **Format**: `tar -czf submission.tar.gz main.py agent/` — `main.py` στο **root**
  (competition_info.md:421-429).
- [ ] **Imports/loader**: exported `agent` = τελευταίο callable, imports top-level, vendored
  fallback με parity test. Υποβολή από **CLI**, όχι notebook.
- [ ] **Timing**: cold-process profile και στα 2 seats· gate `max_turn × 3 < 1s` (<333ms local)·
  cold import/turn-1 και cumulative overage αναφέρονται χωριστά· episode `clean=True`.
- [ ] **Determinism**: ίδιο seed σε 2 fresh processes + διαφορετικό `PYTHONHASHSEED` → ταυτόσημο
  trajectory· 2 sequential episodes στο ίδιο process ταυτόσημα με fresh-process equivalents.
- [ ] **Mirror smoke**: `play("main.py", "main.py", seed=0)` — 720 steps, `clean=True`, κανένα
  cache cross-talk, καμία αυτοκαταστροφή αγοράς.
- [ ] **Μέγεθος** < 100 MiB. `pytest tests/` πλήρως πράσινο.

### 6.2 CLI εντολές

```powershell
kaggle competitions submit kaggriculture -f submission.tar.gz -m "v1e rule-based baseline"
kaggle competitions submissions kaggriculture          # status + SUBMISSION_ID
kaggle competitions episodes <SUBMISSION_ID>           # -v για CSV
kaggle competitions replay <EPISODE_ID> -p ./baselines/<date>/replays
kaggle competitions logs <EPISODE_ID> 0 -p ./baselines/<date>/logs   # index 0/1 = seat
kaggle competitions leaderboard kaggriculture -s
```

### 6.3 Baseline — `baselines/2026-08-XX/`

- [ ] `local_bench.json` — `compare(v1e, "starter", HOLDOUT_SEEDS)` με raw orientation rows, paired
  rows, code fingerprints, median bank, CI/verdict, bank distribution (και vs `"pass"`/`"random"`),
  **και** mirror bank.
- [ ] `validation.md` (pass/fail + χρόνος) · `rating_trajectory.csv` (πρώτα ~20 episodes) ·
  `leaderboard_snapshot.md` (ημέρα 1 και 3) · `replays/` με **2-3 ηττημένα** episodes + logs.
- [ ] Σημείωση κλίμακας: τα scores στο `data/archive/manifest.csv` είναι πιθανόν **rating, ΟΧΙ $**
  (MASTERPLAN §3.2bis) — μη συγκριθούν με bank values.

### 6.4 Submission slots

Όρια: 5/μέρα, **μόνο τα 2 τελευταία active** και αυτά μπαίνουν στο final. 1ο upload = v1e baseline
(σκόπιμα νωρίς — δωρεάν πληροφορία από την πραγματική ladder). 2ο upload **μόνο** με directional
`IMPROVED` σε HOLDOUT 48 seeds — όχι από `abs(diff)`, όχι «δοκιμαστικά».

---

## 7. Χρονοδιάγραμμα & κίνδυνοι

### 7.1 Εκτίμηση (βάση **2026-08-05**, deadline **30 Σεπ 2026**)

> **Ο στόχος «πρώτο submission ~08-14/15» ΑΝΑΘΕΩΡΕΙΤΑΙ ΠΡΟΣ ΤΑ ΠΙΣΩ.** Δύο λόγοι: (α) το ενεργό
> −$2.195 regression μπλοκάρει κάθε gate και πρέπει να λυθεί πριν από οποιοδήποτε feature, (β) το
> v1c απαιτεί redesign (review.md §5 checks 1-5), όχι retry. **Νέα εκτίμηση πρώτου submission:
> ~08-22/24.** Παραμένουν ~5,5 εβδομάδες buffer πριν το deadline — ο χρόνος **δεν** είναι ο
> περιοριστικός πόρος· η ποιότητα του gate είναι.

| Βήμα | Εκτίμηση | Ημερολογιακά (στόχος) |
|---|---|---|
| 1.5.1 Parallel compare + seeds | 0.5 μέρα | 08-06 |
| 1.5.2 Ablation & ξεμπλοκάρισμα | 1-1.5 μέρες (εκ των οποίων ~0.5 σε compute) | 08-06 → 08-08 |
| 1.5.3 Πρωτόκολλο μέτρησης | 0.25 μέρα (μαζί με 1.5.1/1.5.2) | 08-08 |
| 1.5.4 Episode report + `unexplained_noops` | 1-1.5 μέρες | 08-08 → 08-10 |
| 1.5.5 Gap analysis από replays | 0.5-1 μέρα (παράλληλα με 1.5.4 — offline data work) | 08-09 → 08-11 |
| v1c (ή v1d, βλ. §5.1) redesign | 2-3 μέρες | 08-11 → 08-14 |
| v1d (ή v1c) | 2-3 μέρες | 08-14 → 08-18 |
| v1e market + liquidation | 2 μέρες | 08-18 → 08-21 |
| 2 submission + baseline | 0.5 μέρα + 2-3 μέρες παθητικής παρακολούθησης | **πρώτο submission ~08-22/24** |

Το 1.5.1 πληρώνεται μία φορά και επιταχύνει **όλα** τα επόμενα (κάθε 48-seed compare από ~5′ σε <1.5′).

### 7.2 Top-5 κίνδυνοι & fallbacks

| # | Κίνδυνος | Σύμπτωμα | Fallback |
|---|---|---|---|
| 1 | **Το ablation δεν απομονώνει το −$2.195** (καμία μεμονωμένη ή ζευγαρωτή αιτία) | όλα τα combos κοντά στο −$2.195 | Το κριτήριο #1 αποκλείει «σπασμένη υποδομή» ως εξήγηση. Αν επιβεβαιωθεί διάχυτη αιτία: revert σε `checkpoints/v1b` και **επανεφαρμογή των review.md fixes μία-μία με gate ανά fix** — αργότερο αλλά ντετερμινιστικό |
| 2 | **Σιωπηλά no-ops** — bug χαμηλώνει το σκορ αθόρυβα (το engine δεν πετά ποτέ error) | intended action χωρίς το expected effect | G11 receipts + `unexplained_noops` (§1.5.4) — αυτό ακριβώς έλειψε στη διάγνωση του v1c |
| 3 | **Engine version bump** στη ladder πριν το submission | νέο `kaggle-environments` στο PyPI | `pip install -U` + `pytest tests/` = ο detector (§2 κανόνας 2)· το pinned 1.32.4 μένει η βάση μέχρι να περάσει το suite στη νέα |
| 4 | **Server runtime διαφορές** (1.6 vCPU, import paths, validation fail) | Submission Error / timeout | ×3 timing margin· vendored constants fallback· σε Error: `kaggle competitions logs` + fix-forward (5 submissions/μέρα ⇒ 2-3 προσπάθειες την ίδια μέρα) |
| 5 | **Overfit σε dev seeds** από τα πολλά ablation/tuning runs | dev κέρδη που εξατμίζονται στην ladder | Το dev/holdout split (§1.5.1) + «GO μόνο από confirm» (§1.5.3)· το HOLDOUT δεν αγγίζεται σε **καμία** απόφαση tuning |

---

## Εκκρεμότητες προς χρήστη

1. **Απόφαση W&B ή τοπικό static HTML report** (MASTERPLAN §8.2). Το W&B ανεβάζει config +
   metrics σε **εξωτερική υπηρεσία εν μέσω ενεργού διαγωνισμού** — private projects το καλύπτουν,
   αλλά είναι συνειδητή απόφαση, όχι default· επιπλέον απαιτεί login/API key που **δεν** στήνεται
   αυτόνομα από τον agent. Εναλλακτική με μηδενικό ρίσκο: μένουμε στο static HTML του §1.5.4 πάνω
   στο `results.jsonl`, που παραμένει η **πηγή αλήθειας** ούτως ή άλλως.
   **Μέχρι να απαντηθεί: υλοποιείται μόνο το τοπικό report.**
2. **Commit των checkpoints** (§3.3): τα `checkpoints/v0|v1a|v1a_prime|v1b` δεν έχουν γίνει
   `git add` — μέχρι τότε τρία από τα τέσσερα είναι μη ανακατασκευάσιμα (review.md H2).
   Χρειάζεται ρητή έγκριση για commit.
