# plan.md — Φάσεις 0-1: Ground Truth, Harness, Agent v1, Πρώτο Submission

> **Working plan, προσωρινό** — θα αντικατασταθεί όταν κλείσει η Φάση 1.
> Πηγή στρατηγικής: [docs/MASTERPLAN.md](docs/MASTERPLAN.md) (source of truth — ΔΕΝ επαναδιαπραγματεύεται εδώ).
> Engine ground truth: [engine_reference/kaggriculture.py](engine_reference/kaggriculture.py) (αντίγραφο του
> εγκατεστημένου `kaggle-environments==1.32.4`). Όπου docs και engine διαφωνούν, υπερισχύει το engine.
> Config παντού: defaults (720 steps, 10×10, $3.000 — competition_info.md:346-360).
>
> Ημερομηνία σύνταξης: 2026-08-05. Scope: **μόνο Φάση 0 + Φάση 1 + πρώτο submission** (MASTERPLAN §5).

---

## Τι υποθέτω

Τα τεχνικά ερωτήματα engine συμπεριφοράς είναι ήδη απαντημένα (MASTERPLAN §2 Αμφισημίες #1-6, §7 πίνακας) — **δεν επαναλαμβάνονται εδώ**. Μένουν μόνο νέες υποθέσεις *υλοποίησης*:

| # | Υπόθεση | Βάση | Επαλήθευση |
|---|---|---|---|
| Υ1 | **pytest** ως testing framework (νέο dependency στο `.venv`) | Standard, μηδενικό ρίσκο | `pip install pytest` στο Βήμα 0.1 |
| Υ2 | Τα interpreter-level tests στήνονται με `env = make(...)` + **`env.step([action0, action1])`** (scripted actions ανά turn, χωρίς agent callables) | Το `env.step()` είναι δημόσιο API του kaggle-environments | [ΕΠΑΛΗΘΕΥΣΗ ΣΤΟ ΒΗΜΑ 0] στο πρώτο test· fallback: closure-agents με προκαθορισμένη λίστα actions ανά step |
| Υ3 | Determinism ανά seed μέσω `configuration={"seed": N}` → `resolve_episode_seed` → `env.info["seed"]` (engine_reference/kaggriculture.py:235, :848) | Το config field `seed` τεκμηριώνεται (competition_info.md:360) | [ΕΠΑΛΗΘΕΥΣΗ ΣΤΟ ΒΗΜΑ 0]: ίδιο seed δύο φορές σε fresh process → ταυτόσημο `env.toJSON()` |
| Υ4 | Δομή φακέλων: `agent/` + `harness/` + `tests/` + `runs/` (gitignored) + `baselines/` — βλ. §2.4 | Δική μας απόφαση | — |
| Υ5 | Submission format: **tar.gz με `main.py` στο root + πακέτο `agent/`** από την αρχή (όχι single file), ώστε το validation episode να τεστάρει το πραγματικό τελικό format | competition_info.md:426-429 | Validation episode στο Βήμα 2 |
| Υ6 | `from kaggle_environments.envs.kaggriculture.kaggriculture import CROPS, ANIMALS, MARKET_PARAMS, market_price` δουλεύει **και στο server** (το πακέτο τρέχει το episode) | Επιβεβαιωμένα importable τοπικά (MASTERPLAN §4.1) | Guard: try/except fallback σε vendored αντίγραφο σταθερών μέσα στο `agent/constants.py` — βλ. §3.2 |
| Υ7 | **Δεν** δημιουργείται ξεχωριστό `engine_facts.md` — βλ. απόφαση §2.3 | Αποφυγή τρίτου αντιγράφου που θα ξεκλειδώσει drift | Κλείνει με την αποδοχή αυτού του plan |

---

## 1. Στόχος & Definition of Done

**Τελικό deliverable των Φάσεων 0-1:** ένα `main.py` (+ πακέτο `agent/`) που:

- **(α)** περνά το validation episode στο Kaggle (παίζει εναντίον αντιγράφου του εαυτού του χωρίς Error — competition_info.md:44),
- **(β)** νικά τον built-in `"starter"` (engine_reference/kaggriculture.py:1031-1060) σε **12/12 paired seeds** τοπικά, και στα δύο seats,
- **(γ)** υποβάλλεται στο competition `kaggriculture` και το αρχικό rating trajectory καταγράφεται ως baseline στο `baselines/`.

**Μετρήσιμα κριτήρια αποδοχής ανά βήμα** (αναλυτικά στην κάθε ενότητα):

| Βήμα | Κριτήριο αποδοχής |
|---|---|
| 0.1 Tests | `pytest tests/test_engine_facts.py` πράσινο στο `.venv` — όλα τα §7/§2 ευρήματα καλυμμένα |
| 0.2 Harness | `compare("starter", "pass", seeds=range(12))` τρέχει end-to-end, παράγει πίνακα diffs + αποθηκευμένα replays + timing report, αναπαραγώγιμο (ίδια νούμερα σε δεύτερο run) |
| 0.3 CLI auth | `kaggle competitions list -s kaggriculture` επιστρέφει το competition χωρίς auth error |
| 1.v0 | Walking skeleton: 720 steps χωρίς exception, και στα δύο seats, status DONE, bank ≥ $3.000 άθικτο |
| 1.v1a-v1e | Κάθε increment ≥ το προηγούμενο σε 12 paired seeds (κριτήριο §6 MASTERPLAN: \|mean diff\| > 2×SE ή τουλάχιστον μη-χειροτέρευση) |
| 1 τελικό | 12/12 wins vs `starter` και στα δύο seats· τοπικό bank ≥ **$40k** median (στόχος MASTERPLAN §5 Φάση 1 ≈ ladder median $44.8k)· max turn time < 500ms |
| 2 | Submission δεκτό, validation Complete, ≥ 20 episodes καταγεγραμμένα, baseline folder γεμάτο |

---

## 2. ΒΗΜΑ 0 — Engine Ground Truth Formalization & Harness

### 2.0 Ήδη ολοκληρωμένο setup (καταγραφή για αναπαραγωγιμότητα — ΟΧΙ pending work)

Όλα τα παρακάτω έγιναν 2026-08-05 και **δεν επαναλαμβάνονται**:

```powershell
# venv με Python 3.11.9 (ΟΧΙ system 3.14 — δεν έχει Windows wheels για pygame)
py -3.11 -m venv .venv
.venv\Scripts\Activate.ps1
pip install kaggle-environments==1.32.4    # pinned, ίδιο version με το viz notebook
# Reference copy του engine στο repo (read-only):
#   engine_reference/{kaggriculture.py, kaggriculture.json, README.md, AGENTS.md}
# .gitignore: .venv/, __pycache__/, *.pyc, .env
# .env (gitignored): KAGGLE_API_TOKEN — επιβεβαιωμένο με kagglehub.whoami() → nikosstraf
```

Τα engine ground-truth ερωτήματα (πρώην MASTERPLAN §2 Αμφισημίες #1-6) **απαντήθηκαν** με ανάγνωση πηγαίου κώδικα + ad-hoc smoke test· τα ευρήματα ζουν στο MASTERPLAN §2 με αναφορές σε συναρτήσεις. Ό,τι ΔΕΝ υπάρχει: formal test suite, harness, agent code — αυτά είναι το παρόν βήμα και το επόμενο.

### 2.1 Κύριο παραδοτέο #1: `tests/test_engine_facts.py`

- [x] `pip install pytest` (καταγραφή version σε `requirements-dev.txt` μαζί με το pinned engine) — pytest 9.1.1, 2026-08-05
- [x] Δημιουργία `tests/test_engine_facts.py` με τα παρακάτω tests — 32 tests, όλα empirically verified πριν γραφτούν

**Αρχή:** όλα τα tests κάνουν import από το **εγκατεστημένο** πακέτο (`kaggle_environments.envs.kaggriculture.kaggriculture`), ΟΧΙ από το `engine_reference/` — έτσι ένα μελλοντικό `pip install -U` που αλλάζει συμπεριφορά σκάει αμέσως στο suite (Ρίσκο #1, MASTERPLAN §7). Τα line references παρακάτω δείχνουν στο reference copy μόνο για ανάγνωση.

**Δύο επίπεδα tests** (και τα δύο πάνω στο πραγματικό engine):

- **Tier A — unit-level**: απευθείας κλήση των engine functions πάνω σε χειροποίητα farm/tile dicts. Για ευρήματα που είναι συμπεριφορά μίας συνάρτησης.
- **Tier B — interpreter-level**: `env = make("kaggriculture", configuration={"seed": N, ...})` + `env.step([action_p0, action_p1])` ανά turn (Υ2). Για ευρήματα που εξαρτώνται από το pipeline/σειρά επεξεργασίας του `interpreter()` (engine_reference/kaggriculture.py:871-942).

Πλήρης λίστα tests — **τα αναμενόμενα είναι ήδη γνωστά** (MASTERPLAN §2/§7), εδώ μόνο το στήσιμο:

| Test | Tier | Στήσιμο | Αναμένουμε (γνωστό) | Engine ref |
|---|---|---|---|---|
| `test_market_price_table` | A | `market_price(item, I0±T)`, `I0+2T` για τα 9 προϊόντα | Πίνακας README (P(I0−T)/P(I0+T)/P(I0+2T), π.χ. WHEAT $45/$20/$19, MELON $300/$1/$1) | :178-192, :41-51 |
| `test_hire_cost_fib` | A | `_hire_cost(n)` για n=0..7 | 1,1,2,3,5,8,13,21 | :667-676 |
| `test_care_bonus_plus_one` (§7#1) | A | Χειροποίητο animal tile `fed_today=cared_today=True` → `_daily_refresh_animals` | `pending_care_bonus` +1 (όχι +2)· καταβολή ολόκληρου του bank σε fed production day, μηδενισμός σε unfed | :804-808 |
| `test_fertilizer_sell_accepted` (§7#2) | B | Shed με 1 FERTILIZER, order `["SELL","FERTILIZER",1]` | Πώληση εκτελείται, μπαίνει χρήμα, inventory +1 | :573, :629-637 |
| `test_dig_semantics` (§7#3) | A | `_apply_unit_action` DIG σε: plant, weed, άδειο coop, κατειλημμένο coop | Πρώτα 3 καθαρίζουν· κατειλημμένο = no-op | :428-435 |
| `test_planting_day_counts_unwatered` (§7#4) | A+B | `_new_plant` → `consecutive_unwatered == 1`· B: PLANT χωρίς WATER ίδια μέρα → end of day | Weed το ίδιο βράδυ | :208, :755-762 |
| `test_melon_cap_day10` (§7#5) | A | Loop: WATER κάθε «μέρα» σε melon tile μέσω `_apply_unit_action` με αυξανόμενο `day` | `yield_units` φτάνει 6 στην ηλικία 10· μέρες 11-12 δεν προσθέτουν | :383-387, :16 |
| `test_strawberry_exactly_4_yields` (§7#6, #7) | A | `_daily_refresh_plants` σε strawberry tile, ποτισμένο, μέρες 0-20 | Παραγωγές μόνο στις ηλικίες 10/12/14/16 (×1), μετά `max_lifespan_step = (next_day+1)*24` και decay | :767-780 |
| `test_fertilizer_available_no_care` (§7#8) | A | Animal tile `fed_today=False, cared_today=False` → `_daily_refresh_animals`· COLLECT ×2 συνεχόμενα | `fertilizer_available=True` για κάθε επιζών ζώο· δεν συσσωρεύεται (2ο COLLECT no-op) | :809, :492-499 |
| `test_shed_access_tiles` (§7#9) | A | `_shed_access_tiles(10)`· DROP από μη-κεντρικό tile | Ακριβώς (4,4),(5,4),(4,5),(5,5)· DROP no-op αλλού | :118-121, :327-329 |
| `test_market_order_cap_10` (πρώην #3) | B | 12 orders σε ένα turn (10 SELL + HIRE + BUY_LAND στο τέλος) | Μόνο τα 10 πρώτα εκτελούνται — HIRE/BUY_LAND μετράνε στο cap, 11ο+ σιωπηλά dropped | :537 |
| `test_market_interleaving_lockstep` (πρώην #3) | B | Και οι δύο παίκτες SELL ίδιο προϊόν στο ίδιο index· έπειτα σενάριο index 0 vs index 5 | Ίδιο index: ίδια τιμή ανά unit και για τους δύο· προγενέστερο index εξαντλείται πρώτο σε καλύτερες τιμές | :539-603 |
| `test_hands_action_mapping` (πρώην #4) | B | HIRE 2 hands· δώσε 1 action για 2 hands, μετά 3 actions για 2 hands | Λιγότερα actions → extra hands αδρανή· περισσότερα → πλεονάζοντα σιωπηλά no-op (`pos=None`) | :264-268, :914-916 |
| `test_hand_spawn_ignores_locked` (πρώην #4) | B | HIRE με farmer στο (4,4), κανένα quadrant αγορασμένο | 1ο hand spawn στο (5,4) (LOCKED)· μπορεί να κινηθεί δυτικά | :510-518, :309-317 |
| `test_decay_per_2_steps` (πρώην #5) | A | `_decay_plants` σε plant με γνωστό `max_lifespan_step`, διαδοχικά steps | −1 yield ανά 2 **steps** (όχι μέρες) από το mls· στο 0 → WEED· one-shot mls = `(planted_day+max_yield_day+1)*24` | :730-744, :210 |
| `test_weed_rng_seat_coupling` (πρώην #6) | B | Ίδιο seed, 2 runs: στο run 2 ο player 0 έχει διαφορετικό πλήθος κενών tiles (π.χ. έχει φυτέψει 5 tiles) | Το weed pattern του **player 1** διαφέρει μεταξύ των runs (κοινό rng instance, σειριακή κατανάλωση draws) — seed επιλέγεται/hardcoded ώστε η διαφορά να εκδηλώνεται ντετερμινιστικά | :848-855, :814-818 |
| `test_plant_atomic_block` (§2#4) | B | 1 melon seed, farmer+hand και οι δύο `PLANT MELON` ίδιο turn | Κανείς δεν φυτεύει (όλα → PASS) | :897-910 |
| `test_floor_sales_no_inventory` | B | Ρίξε τιμή στο floor $1 με μαζικό SELL, συνέχισε SELL | Units στο floor πληρώνονται $1 αλλά ΔΕΝ αυξάνουν το market inventory | :636-637 |
| `test_determinism_same_seed` (Υ3) | B | Ίδιο seed + scripted actions, 2 φορές (fresh env) | Ταυτόσημο τελικό state / `env.toJSON()` (πλην timing πεδίων) | :235, :848 |

- [x] **Κριτήριο αποδοχής 0.1:** όλα πράσινα με `kaggle-environments==1.32.4`· το suite τρέχει < 2 λεπτά — 32 passed σε 1.81s.

### 2.2 Πρόσθετος ρόλος του suite: version-bump detector

Κάθε φορά που η ladder αλλάζει engine version (Ρίσκο #1, MASTERPLAN §7), το μόνο απαιτούμενο βήμα είναι `pip install -U kaggle-environments && pytest tests/` — ό,τι κοκκινίσει είναι η αλλαγή συμπεριφοράς. Δεν χρειάζεται ξανά χειροκίνητη ανάγνωση diff.

### 2.3 Απόφαση: engine_facts.md ή παραπομπή στο MASTERPLAN;

**Απόφαση: ΟΧΙ ξεχωριστό `engine_facts.md`.** Το ζεύγος τεκμηρίωσης είναι:

1. **MASTERPLAN §2 + §7** — το πεζό «τι κάνει το engine και γιατί μας νοιάζει» (ήδη γραμμένο, με line refs).
2. **`tests/test_engine_facts.py`** — η εκτελέσιμη μορφή του ίδιου περιεχομένου· κάθε test φέρει docstring της μορφής `"MASTERPLAN §7#5 — melon cap 6 στην ημέρα 10. Engine: kaggriculture.py:383-387."`

*Αιτιολόγηση:* ένα τρίτο αρχείο θα ήταν αντίγραφο του MASTERPLAN §2/§7 χωρίς νέο περιεχόμενο, με βέβαιο drift μόλις κάτι αλλάξει σε ένα από τα τρία μέρη. Tests + MASTERPLAN καλύπτουν και τις δύο ανάγκες (εκτελέσιμη επαλήθευση, ανθρώπινη ανάγνωση) χωρίς τρίτη πηγή αλήθειας. Αν στη Φάση 2+ συσσωρευτούν *νέα* ευρήματα, γράφονται πρώτα ως tests και περιληπτικά στο MASTERPLAN §2 — ίδιο πρωτόκολλο.

### 2.4 Κύριο παραδοτέο #2: Harness (`harness/`) — 100% νέο έργο

Δομή φακέλων (Υ4):

```
Kaggriculture/
├── main.py                  # (Βήμα 1) submission entrypoint
├── agent/                   # (Βήμα 1) το πακέτο του agent
├── harness/
│   ├── __init__.py
│   ├── play.py              # play(): ένα episode, με recording & timing
│   ├── compare.py           # compare(): paired seeds A vs B
│   ├── metrics.py           # εξαγωγή μετρικών από env/replay
│   ├── profile.py           # timing profiler wrapper
│   └── cli.py               # python -m harness.cli play|compare|profile
├── tests/
│   ├── test_engine_facts.py # (2.1)
│   └── test_agent_guards.py # (Βήμα 1)
├── runs/                    # gitignored — replays + αποτελέσματα ανά run
│   └── 2026-08-07_v1a-vs-starter/
│       ├── results.json
│       └── replays/seed17_seatA0.json
└── baselines/               # (Βήμα 2) committed — submission baselines
```

- [x] Προσθήκη `runs/` στο `.gitignore`.

**Υπογραφές (προδιαγραφή — υλοποίηση στο Βήμα 0, όχι σε αυτό το έγγραφο):**

```python
# harness/play.py
@dataclass
class PlayResult:
    seed: int
    agents: tuple[str, str]          # ονόματα/paths, index = seat
    rewards: tuple[float, float]     # τελικό bank ανά seat (engine :937-940)
    winner: int | None               # None = tie
    statuses: tuple[str, str]        # "DONE" ή error status ανά agent
    replay_path: Path | None
    turn_times: list[float] | None   # sec ανά κλήση του υπό μέτρηση agent
    metrics: dict                    # βλ. metrics.py

def play(agent_a, agent_b, seed: int, *,
         steps: int = 720,
         record: bool = True, run_dir: Path | None = None,
         profile_seat: int | None = None,
         debug: bool = False) -> PlayResult:
    """Ένα episode: make("kaggriculture", configuration={"episodeSteps": steps, "seed": seed}),
    env.run([agent_a, agent_b]). agent_* = callable | "main.py" path | built-in name
    ("pass"/"random"/"starter"). record=True → env.toJSON() στο run_dir.
    profile_seat → τύλιγμα του agent με harness.profile.timed()."""
```

```python
# harness/compare.py
@dataclass
class CompareResult:
    per_seed: list[dict]      # {seed, seat_layout, bank_a, bank_b, diff, winner}
    mean_diff: float
    se_diff: float
    wins_a: int; wins_b: int; ties: int
    significant: bool         # |mean_diff| > 2*se_diff  (MASTERPLAN §6)

def compare(agent_a, agent_b, seeds: Sequence[int], *,
            both_seats: bool = True,      # A παίζει seat 0 ΚΑΙ seat 1 ανά seed (weed RNG asymmetry, MASTERPLAN §2#6)
            steps: int = 720,
            run_dir: Path | None = None) -> CompareResult:
    """Paired-seed πρωτόκολλο (MASTERPLAN §6, μεθοδολογία viz cells 46-50).
    Με both_seats=True: 12 seeds → 24 episodes. Το per-seed diff για το κριτήριο
    2×SE υπολογίζεται στο άθροισμα/μέσο των δύο seats του ίδιου seed."""
```

```python
# harness/metrics.py
def extract_metrics(env_json: dict, seat: int) -> dict:
    """Από replay JSON (env.toJSON()). Βήμα 0 minimum:
       - final_bank, bank_curve (ανά turn — εντοπισμός stalls, MASTERPLAN §6 πίνακας #2)
       - opponent_final_bank, outcome
       Βήμα 1 επέκταση (μαζί με τους guards, §3.3):
       - weeds_lost (φυτά που έγιναν weed), animals_escaped
       - shed_overflow_burnt, units_sold_at_or_below(5), avg_sell_price ανά προϊόν vs base
       - worker_turns_moving vs working"""
```

```python
# harness/profile.py
def timed(agent) -> tuple[Callable, list[float]]:
    """Τυλίγει agent callable με time.perf_counter ανά κλήση· επιστρέφει (wrapped, times).
    Report: max, median, p99, σύνολο. Budget: actTimeout 1s/turn + 60s overage (MASTERPLAN §1).
    Server margin: το submission runtime είναι 1.6 vCPU (competition_info.md:528) — κανόνας
    αποδοχής τοπικά: max_turn × 3 < 1s (συντηρητικός πολλαπλασιαστής μέχρι το ανοιχτό #7
    του MASTERPLAN να μετρηθεί από πραγματικά server logs — ΕΚΤΟΣ scope Φάσης 0/1)."""
```

CLI (λεπτό wrapper, χωρίς φιλοδοξίες):

```
python -m harness.cli play main.py starter --seed 17 --record
python -m harness.cli compare main.py starter --seeds 0-11 --out runs/<name>
python -m harness.cli profile main.py --seed 17
```

- [x] Υλοποίηση `play.py` + smoke: `play("starter", "pass", seed=0)` → starter κερδίζει, replay γράφεται
- [x] Υλοποίηση `compare.py` + smoke: `compare("starter", "pass", range(12))` → **12/12 wins, mean_diff≈499, significant=True**, 720 steps/episode σε 73s· αναπαραγώγιμα νούμερα σε 2ο run (επαληθεύτηκε σε 200-step smoke)
- [x] Υλοποίηση `metrics.py` (Βήμα-0 minimum) + `profile.py` + `cli.py`
- [x] **Κριτήριο αποδοχής 0.2:** το κριτήριο του πίνακα §1 — end-to-end compare με replays (`runs/step0_acceptance/`, 24 αρχεία), timing, αναπαραγωγιμότητα. Επαληθεύτηκε 2026-08-05.

### 2.5 [ΕΠΑΛΗΘΕΥΣΗ] Kaggle CLI auth — νωρίς, για να μην μπλοκάρει το Βήμα 2

Το kagglehub auth δουλεύει (`KAGGLE_API_TOKEN` σε `.env`)· το **legacy kaggle CLI** (αυτό που κάνει `submit/submissions/episodes/replay/logs`) είναι **ανεπιβεβαίωτο** — παραδοσιακά θέλει `~/.kaggle/kaggle.json` ή `KAGGLE_USERNAME`+`KAGGLE_KEY`, αν και το competition_info.md:404 τεκμηριώνει και `KAGGLE_API_TOKEN` ως env-var εναλλακτική.

- [x] `pip install kaggle` στο `.venv` — ήδη παρόν (kaggle 2.2.4)
- [x] Δοκιμή με το token από το `.env` — **επιτυχής**, το legacy CLI δέχεται το `KAGGLE_API_TOKEN` χωρίς fallback
- [x] ~~Αν αποτύχει → fallback~~ — δεν χρειάστηκε, το token δούλεψε με την πρώτη
- [x] **Κριτήριο αποδοχής 0.3:** `kaggle competitions list -s kaggriculture` επιστρέφει το competition. `kaggle competitions list --group entered` → `userHasEntered: True` (rank 0) — ο χρήστης έχει κάνει ήδη Join. Επαληθεύτηκε 2026-08-05, βλ. [[kaggriculture-competition-joined]].

---

## 3. ΒΗΜΑ 1 — Agent v1 (rule-based) — μηδενικός υπάρχων κώδικας

Αρχιτεκτονική: τα 3 επίπεδα του MASTERPLAN §4 (κλειδωμένη απόφαση — heuristic scheduler, όχι RL).

### 3.1 Modules & αρχεία

```
main.py                      # entrypoint υποβολής — ΜΟΝΟ shim:
                             #   sys.path insert για /kaggle_simulations/agent/ (competition_info.md:524)
                             #   + local fallback στο dirname(__file__), μετά:
                             #   from agent.policy import agent
agent/
├── __init__.py
├── constants.py             # Layer-ανεξάρτητο: engine σταθερές
├── state.py                 # View: parse του obs dict → δομημένο snapshot
├── planner.py               # Layer 1: economic planner (ανά μέρα / on-event)
├── scheduler.py             # Layer 2: task scheduler (ανά turn)
├── executor.py              # Layer 3: market executor (ανά turn)
├── config.py                # CONFIG dict — ΟΛΑ τα thresholds εδώ (έτοιμο για Φάση-2 sweeps)
└── policy.py                # agent(obs) glue: state → planner (αν νέα μέρα) → scheduler → executor
```

**`constants.py`** (Υ6): 

```python
try:
    from kaggle_environments.envs.kaggriculture.kaggriculture import (
        CROPS, ANIMALS, MARKET_PARAMS, market_price)   # engine_reference/kaggriculture.py:11-51, :178-192
except ImportError:
    from agent._vendored import CROPS, ANIMALS, MARKET_PARAMS, market_price  # verbatim αντίγραφο
```

Συν παράγωγες σταθερές: `SHED_ACCESS = [(4,4),(5,4),(4,5),(5,5)]` (:118-121), `LAND_ORDER/LAND_PRICES` (:83-84), `SHOPS` (:90-99), town demand schedule (:104).

**`state.py`** — καμία απόφαση, μόνο ανάγνωση:

```python
@dataclass
class Snapshot:
    step: int; day: int; hour: int; player: int
    money: float
    my_tiles: list[list]; opp_tiles: list[list]     # ωμά dicts + helpers
    farmer_pos: tuple; hand_positions: list[tuple]
    shed: dict; seeds: dict; inventories: list[dict]
    market_inv: dict; market_prices: dict
    unlocked_shops: list[str]; my_quadrants: list[str]
    hires_today: int; opp_money: float

def parse(obs: dict) -> Snapshot
def plants_needing_water(snap) -> list[TilePos]      # watered_today=False, kind=PLANT
def harvestable(snap) -> list[TilePos]               # yield_units>0 (plants ώριμα + animals)
def animals_needing(snap) -> dict[TilePos, set]      # {"FEED","CARE","COLLECT_FERTILIZER","HARVEST"}
```

**`planner.py`** — Layer 1, τρέχει στο hour 0 κάθε μέρας (ή on-event π.χ. νέο quadrant):

```python
@dataclass
class DayPlan:
    plant_targets: dict[str, int]        # crop -> πόσα νέα tiles σήμερα
    hands_target: int                    # πόσα HIRE σήμερα
    buy_land: bool                       # trigger για BUY_LAND
    animal_purchases: dict[str, int]     # Φάση v1d
    sell_floor_price: dict[str, int]     # ανά προϊόν: ελάχιστη αποδεκτή marginal τιμή
    seed_orders: dict[str, int]

def make_day_plan(snap: Snapshot, cfg: CONFIG) -> DayPlan
```

Χρησιμοποιεί το **ακριβές** `market_price()` για marginal revenue (όχι εκτίμηση) και τα ντετερμινιστικά town intervals (MASTERPLAN §4.1). Opponent-aware λογική = Φάση 2, ΟΧΙ εδώ.

**`scheduler.py`** — Layer 2, κάθε turn:

```python
@dataclass
class Task:
    kind: str            # WATER/FEED/CARE/HARVEST/PLANT/FERTILIZE/COLLECT_FERTILIZER/DROP/PICKUP/DIG
    pos: tuple[int, int]
    priority: int        # χαμηλότερο = πιο επείγον
    arg: str | None      # π.χ. crop για PLANT

def build_tasks(snap, plan) -> list[Task]
    # Σταθερή ιεραρχία προτεραιότητας (MASTERPLAN §5 Φάση 1):
    # 1 WATER (φυτά με consecutive_unwatered==1 πρώτα — αύριο πεθαίνουν)
    # 2 FEED (ζώα με consecutive_unfed==1 πρώτα)
    # 3 HARVEST ζώων στο max_held / φυτών κοντά σε decay
    # 4 CARE, 5 HARVEST λοιπά, 6 PLANT, 7 COLLECT_FERTILIZER/FERTILIZE, 8 DROP στο shed

def assign(tasks, units: list[UnitPos], snap) -> list[list[str]]
    # Greedy nearest-unit-first (Manhattan)· Hungarian ΜΟΝΟ αν το greedy αποδειχθεί
    # μετρήσιμα χειρότερο στο harness (όχι προκαταβολική πολυπλοκότητα).
    # Επιστρέφει action ανά unit: [farmer_action, *hand_actions] — index-aligned με
    # farm["hands"] (MASTERPLAN §2#1, engine :264-268). Unit χωρίς task → κίνηση προς
    # το επόμενο task ή PASS.
```

**`executor.py`** — Layer 3, κάθε turn, ≤ 10 orders (engine :537):

```python
def market_orders(snap, plan, cfg) -> list[list]:
    # Σειρά μέσα στη λίστα (τα πρώτα index εκτελούνται σε καλύτερη τιμή — MASTERPLAN §2#3):
    # 1. HIRE ×k (hour 0, ώστε τα hands να δουλέψουν όλη τη μέρα)
    # 2. BUY_LAND (on-trigger)
    # 3. SELL trickles: για κάθε προϊόν, πούλα μονάδες όσο
    #    market_price(item, inv + already_queued) >= plan.sell_floor_price[item]
    # 4. BUY_SEED / BUY_ANIMAL / BUY_PRODUCT(WHEAT για feed, μόνο αν χρειάζεται)
    # Hard cap: len(orders) <= 10 — ποτέ σιωπηλή απόρριψη.
```

**`policy.py`**:

```python
_STATE_CACHE = {}   # per-process: DayPlan της τρέχουσας μέρας (ΟΧΙ κρίσιμο state —
                    # αν χαθεί, ξαναϋπολογίζεται από το obs· ο agent μένει stateless-safe)

def agent(obs):
    snap = parse(obs)
    plan = get_or_make_day_plan(snap)
    farmer, hands = assign(build_tasks(snap, plan), units(snap), snap)
    return {"farmer": farmer, "hands": hands, "market": market_orders(snap, plan, CONFIG)}
```

### 3.2 Guard κανόνες — testable requirements (`tests/test_agent_guards.py`)

Κάθε guard = ένα test πάνω σε replay/metrics του harness (τα G αντιστοιχούν στο checklist MASTERPLAN §6 + §5 Φάση 1):

| # | Guard | Testable απαίτηση |
|---|---|---|
| G1 | Πότισμα ημέρας φύτευσης (§7#4) | Σε πλήρες episode: **0 φυτά** χάνονται με `planted_day == weed day`· ο scheduler δεν προγραμματίζει PLANT που δεν προλαβαίνει WATER την ίδια μέρα |
| G2 | Ατομικό PLANT (§2#4) | Ποτέ 2 units με PLANT ίδιου crop σε turn με ανεπαρκείς σπόρους — ο scheduler κάνει reserve σπόρων ανά turn |
| G3 | Shed cap 100 (:821-835) | `shed_overflow_burnt == 0` σε κάθε bench run· ο planner πουλά/κρατά αποθέματα ώστε προβλεπόμενο end-of-day drop ≤ 100 |
| G4 | Όχι πώληση στο floor (:636-637) | `units_sold_at_or_below($5) == 0` (configurable κατώφλι στο CONFIG)· ο executor κόβει το trickle πριν το floor |
| G5 | FEED πριν CARE, κανένα ζώο άταιστο | `animals_escaped == 0`· wheat reserve: ο executor εξασφαλίζει `wheat διαθέσιμο ≥ #ζώα` πριν από κάθε μέρα (καλλιέργεια ή BUY_PRODUCT) |
| G6 | Hand σε locked spawn (§7 πίνακας, discussion.md:34) | Hand στο (5,4) κινείται δυτικά το ίδιο turn· hand στο (5,5) χωρίς αγορασμένα NE/SW = εγκλωβισμένο → ο scheduler το μαρκάρει idle, δεν crash-άρει, δεν του αναθέτει tasks |
| G7 | 10-order cap (§2#2) | `len(market) <= 10` σε **κάθε** turn (assert στο executor)· HIRE/BUY_LAND πάντα στα index 0-1 |
| G8 | Ζώα max_held (MASTERPLAN §3.2#1) | Κανένα ζώο δεν μένει στο `max_held` για > 1 μέρα με προγραμματισμένη παραγωγή (χαμένη παραγωγή = 0) |
| G9 | Harvest πριν το decay (§2#5) | 0 μονάδες χαμένες σε `_decay_plants` για δικά μας ώριμα one-shots |
| G10 | Strawberry deadline | Κανένα strawberry PLANT μετά τη μέρα **13** (πλήρεις 4 παραγωγές θέλουν ηλικία 16 ≤ μέρα 29 — engine :15, :767-780)· μετά τη μέρα 13 ο planner υπολογίζει μειωμένες παραγωγές ή αποκλείει το crop |
| G11 | Silent no-op detector (Ρίσκο #6, MASTERPLAN §7) | **Μόνο τοπικά** (debug flag στο CONFIG, off στο submission): κάθε intended action συγκρίνεται με το state του επόμενου turn· απόκλιση → log. Στο bench: 0 unexplained no-ops |

### 3.3 Σειρά υλοποίησης — μικρά, συγκρίσιμα increments

Κάθε increment: υλοποίηση → `compare(new, prev, seeds=range(12), both_seats=True)` → commit μόνο αν μη-χειρότερο (κριτήριο §1). Το v1a′ έχει **ανεβασμένη προτεραιότητα** έναντι της αρχικής εκδοχής του masterplan (MASTERPLAN §3.2.2: strawberry 70% win rate, n=441, real-ladder evidence).

- [ ] **v0 — walking skeleton**: `main.py` + `agent/` skeleton· parse του obs, PASS παντού, 0 market orders. *Αποδοχή:* 720 steps χωρίς exception και στα 2 seats, DONE, bank $3.000. Ελέγχει το πακέτο/imports/format πριν μπει λογική.
- [ ] **v1a — carrot loop, multi-tile**: planner με στόχο N carrot tiles στο NW, scheduler για water/harvest/replant κύκλο 3 ημερών (engine :13), executor: BUY_SEED + απλό SELL με G4. *Αποδοχή:* νικά `starter` (που δουλεύει 1 tile) σε ≥ 10/12 seeds· bank > $8k.
- [ ] **v1a′ — strawberry loop** (νέο, MASTERPLAN §3.2.2): φύτευση strawberries νωρίς (μέρες 0-5, G10), πότισμα **κάθε δεύτερη μέρα** αρκεί (η παραγωγή στο `_daily_refresh_plants` :767-780 δεν εξαρτάται από το WATER — μόνο η επιβίωση), carrots ως cash-flow για τα $100/σπόρο. *Αποδοχή:* > v1a στο paired bench.
- [ ] **v1b — hands**: HIRE 2-4 hands στο hour 0 (fib κόστη :667-676), assign() σε πλήρη λειτουργία, G6. *Αποδοχή:* > v1a′, μηδέν idle-crash με hands.
- [ ] **v1c — land**: BUY_LAND NE on-trigger (χρήματα ≥ $1k + υπάρχει εργατικό δυναμικό να το δουλέψει — MASTERPLAN §3.2#7: γη χωρίς hands = νεκρό κεφάλαιο), επέκταση φυτέματος στο NE. *Αποδοχή:* > v1b.
- [ ] **v1d — animals**: 2-4 sheep/cow (pasture :443-447, PLACE :449-461), καθημερινό FEED+CARE, COLLECT_FERTILIZER, wheat για feed (G5), pickup προϊόντων στο max_held ρυθμό (G8). Το CARE είναι υποχρεωτικό, όχι extra (MASTERPLAN §1: cared sheep +$5.575 vs +$375 fed-only). *Αποδοχή:* > v1c.
- [ ] **v1e — trickle selling πλήρες**: executor με marginal-price κατώφλια ανά προϊόν από CONFIG, αξιοποίηση town ramp (πώληση premium αργότερα — ×2 ζήτηση από μέρα 10, ×4 από μέρα 20, engine :104, :722-725) εντός ορίων G3. *Αποδοχή:* > v1d **και** συνολικά κριτήρια Φάσης 1 (πίνακας §1: 12/12 vs starter, ≥ $40k, < 500ms/turn).
- [ ] `tests/test_agent_guards.py` πράσινο για G1-G11 στο τελικό v1e.

---

## 4. ΒΗΜΑ 2 — Πρώτο Submission & Baseline

### 4.1 Checklist προ-υποβολής

- [ ] **Format** (Υ5): tar.gz με `main.py` στο **root** (competition_info.md:421-429):
  ```powershell
  tar -czf submission.tar.gz main.py agent/
  ```
- [ ] **Imports**: το shim του `main.py` καλύπτει `/kaggle_simulations/agent/` (competition_info.md:524)· ο vendored fallback του `constants.py` (Υ6) υπάρχει και έχει test. Προσοχή στο notebook pitfall — εμείς υποβάλλουμε από CLI, όχι notebook (discussion.md:37).
- [ ] **Timing σε «αργό CPU»**: `python -m harness.cli profile main.py --seed 17` → `max_turn × 3 < 1s` (κανόνας §2.4· ο server έχει 1.6 vCPU — competition_info.md:526-528). Επίσης import time < 5s (μετριέται στο πρώτο turn).
- [ ] **Deterministic check**: ίδιο seed, 2 fresh processes → ταυτόσημο αποτέλεσμα (κανένα unseeded random/clock/set-iteration — MASTERPLAN §6).
- [ ] **Mirror smoke** (προσομοίωση του validation episode): `play("main.py", "main.py", seed=0)` — τρέχει 720 steps, κανένα error, καμία αυτοκαταστροφή αγοράς.
- [ ] **Μέγεθος** < 100 MiB (θα είναι KB — απλός έλεγχος).
- [ ] `pytest tests/` πλήρως πράσινο (regression πριν από κάθε submission — MASTERPLAN §5 «Συνεχώς»).

### 4.2 CLI εντολές (competition_info.md:425-483)

> **Εξάρτηση:** το [ΕΠΑΛΗΘΕΥΣΗ] item §2.5. Αν το `KAGGLE_API_TOKEN` δεν αναγνωρίζεται από το legacy CLI, πρώτα το fallback auth setup — αλλιώς το Βήμα 2 μπλοκάρει εδώ.

```powershell
kaggle competitions submit kaggriculture -f submission.tar.gz -m "v1e rule-based baseline"
kaggle competitions submissions kaggriculture          # status + SUBMISSION_ID
kaggle competitions episodes <SUBMISSION_ID>           # -v για CSV
kaggle competitions replay <EPISODE_ID> -p ./baselines/<date>/replays
kaggle competitions logs <EPISODE_ID> 0 -p ./baselines/<date>/logs   # index 0/1 = seat
kaggle competitions leaderboard kaggriculture -s
```

### 4.3 Τι καταγράφουμε ως baseline — `baselines/2026-08-XX/`

- [ ] `local_bench.json` — output του `compare(v1e, "starter", seeds=range(12), both_seats=True)` + bank distribution (και vs `"pass"`, `"random"` — MASTERPLAN §6 checklist)
- [ ] `validation.md` — αποτέλεσμα validation episode (pass/fail, χρόνος)
- [ ] `rating_trajectory.csv` — rating ανά episode για τα πρώτα ~20 episodes (από `kaggle competitions episodes`, χειροκίνητο ή scripted pull 1-2 φορές/μέρα)
- [ ] `leaderboard_snapshot.md` — θέση + rating την ημέρα 1 και ημέρα 3
- [ ] `replays/` — **2-3 ηττημένα** episodes + τα logs τους, για την πρώτη post-mortem ανάλυση της Φάσης 2
- [ ] Σημείωση κλίμακας: τα scores στο `data/archive/manifest.csv` είναι πιθανόν rating, ΟΧΙ $ (MASTERPLAN §3.2bis) — μην συγκριθούν με bank values.

### 4.4 Διαχείριση submission slots

Όρια: 5/μέρα, **μόνο τα 2 τελευταία active** και αυτά μπαίνουν στο final (competition_info.md:40, 523). Κάθε upload καίει 1 από τα 2 active slots. Πρωτόκολλο Φάσης 1-2:

- 1ο upload = v1e baseline (σκόπιμα νωρίς — δωρεάν πληροφορία από την πραγματική ladder, MASTERPLAN §5).
- 2ο upload **μόνο** όταν μια νέα έκδοση νικά την τρέχουσα στο τοπικό bench με στατιστική σημαντικότητα (κριτήριο 2×SE) — όχι «δοκιμαστικά» uploads· το mid-competition rating είναι θορυβώδες (Ρίσκο #4, MASTERPLAN §7) και οι αποφάσεις μας βασίζονται στο local bench.

*Προαιρετική σημείωση (όχι task):* για γρήγορο sanity-check αντιπάλων πέρα από pass/random/starter, το `data/kaggriculture-episodes/` έχει ήδη πραγματικό tier list με ονόματα (MASTERPLAN §3.2bis) — μόνο ως reference ανάγνωσης, εκτός deliverable.

---

## 5. Χρονοδιάγραμμα & Κίνδυνοι

### 5.1 Εκτίμηση (εργάσιμες μέρες)

Σήμερα 2026-08-05 (~1 εβδομάδα μετά το start 07-29). Το setup + engine ground-truth της αρχικής εκτίμησης «1-2 μέρες» για τη Φάση 0 έχει ήδη καλυφθεί — αλλά harness και ολόκληρο το Βήμα 1 είναι ανέπαφο έργο.

| Βήμα | Εκτίμηση | Ημερολογιακά (στόχος) |
|---|---|---|
| 0.1 test_engine_facts.py | 0.5-1 μέρα | 08-06 |
| 0.2 harness | 1-1.5 μέρες | 08-07 |
| 0.3 CLI auth check | 0.5 ώρα (μέσα στο 0.1) | 08-06 |
| 1 v0 → v1e | 4-6 μέρες (το v1d/animals το βαρύτερο) | 08-08 → 08-14 |
| 2 submission + baseline | 0.5 μέρα + 2-3 μέρες παθητικής παρακολούθησης | **πρώτο submission ~08-14/15** |

Συνολικά ~6-9 εργάσιμες → πρώτο submission άνετα εντός Αυγούστου (στόχος MASTERPLAN §5: Φάσεις 0-1 μέσα στον Αύγουστο), με ~2 εβδομάδες buffer πριν την ενδεικτική μετάβαση σε Φάση 2 αρχές Σεπτεμβρίου.

### 5.2 Top-5 κίνδυνοι αυτών των 2 φάσεων & fallbacks

| # | Κίνδυνος | Πιθανό σύμπτωμα | Fallback |
|---|---|---|---|
| 1 | **Silent no-ops** (το engine δεν πετά ποτέ σφάλμα — MASTERPLAN §7 Ρίσκο #6): bug στο action format χαμηλώνει το σκορ αθόρυβα | v1x χειρότερο από v1(x-1) χωρίς προφανή αιτία | G11 assertion layer από το v0 κιόλας· metrics `unexplained_noops`· τα B-tier tests του 2.1 είναι ήδη εκτελέσιμα παραδείγματα σωστού format |
| 2 | **Legacy kaggle CLI δεν δέχεται το KAGGLE_API_TOKEN** | `401/403` στο §2.5 | Αλυσίδα fallback ήδη γραμμένη στο §2.5 (access_token file → OAuth → kaggle.json)· ελέγχεται στο Βήμα 0, ημέρες πριν χρειαστεί |
| 3 | **Engine version bump στη ladder** πριν το submission (2 bumps την πρώτη εβδομάδα — MASTERPLAN §7 Ρίσκο #1) | Νέο kaggle-environments στο PyPI / ανακοίνωση | `pip install -U` + `pytest tests/` = ο detector (§2.2)· ό,τι κοκκινίσει διορθώνεται στοχευμένα· το pinned 1.32.4 μένει η τοπική βάση μέχρι να περάσει το suite στη νέα |
| 4 | **Server runtime διαφορές**: αργό 1.6 vCPU, import paths, validation fail | Submission Error / timeout | v0 walking skeleton δοκιμάζει το format νωρίς· ×3 timing margin (§2.4)· vendored constants fallback (Υ6)· σε Error: `kaggle competitions logs` για το validation episode και fix-forward — τα 5 submissions/μέρα επιτρέπουν 2-3 προσπάθειες την ίδια μέρα |
| 5 | **Θόρυβος 12-seed bench** σε κοντινές συγκρίσεις (game variance ~19% του median bank — MASTERPLAN §6): λάθος go/no-go σε increment | Ασταθές πρόσημο diff μεταξύ επαναλήψεων | Τα 12 seeds αρκούν μόνο για τα χοντρά gaps του Βήματος 1· σε οριακό αποτέλεσμα (μη significant στο 2×SE) → κλιμάκωση σε 24-48 seeds πριν την απόφαση· πάντα both_seats (weed RNG asymmetry §2#6) |

---

## Εκκρεμότητες προς χρήστη

1. ~~**Αποδοχή κανόνων competition στο site**~~ **ΛΥΘΗΚΕ 2026-08-05** — `kaggle competitions list --group entered` επιστρέφει `userHasEntered: True`. Το submit δεν μπλοκάρεται πλέον.
2. ~~**Kaggle CLI auth**~~ **ΛΥΘΗΚΕ 2026-08-05** — το `KAGGLE_API_TOKEN` από το `.env` δούλεψε με το legacy CLI χωρίς κανένα fallback.

*(Το Kaggle API access για datasets μέσω kagglehub είναι ήδη λυμένο — καμία ενέργεια.)*
