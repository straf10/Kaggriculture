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
- **(β)** νικά τον built-in `"starter"` (engine_reference/kaggriculture.py:1031-1060) σε **24/24 orientation episodes** (12 seeds × 2 seats) τοπικά,
- **(γ)** υποβάλλεται στο competition `kaggriculture` και το αρχικό rating trajectory καταγράφεται ως baseline στο `baselines/`.

**Μετρήσιμα κριτήρια αποδοχής ανά βήμα** (αναλυτικά στην κάθε ενότητα):

| Βήμα | Κριτήριο αποδοχής |
|---|---|
| 0.1 Tests | `pytest tests/test_engine_facts.py` πράσινο στο `.venv` — όλα τα §7/§2 ευρήματα καλυμμένα |
| 0.2 Harness | `compare("starter", "pass", seeds=range(12))` τρέχει end-to-end, παράγει πίνακα diffs + αποθηκευμένα replays + timing report, αναπαραγώγιμο (ίδια νούμερα σε δεύτερο run) |
| 0.3 CLI auth | `kaggle competitions list -s kaggriculture` επιστρέφει το competition χωρίς auth error |
| 1.v0 | Walking skeleton: ένα mirror episode 720 steps, `clean=True`, τελικά statuses DONE, ακριβώς $3.000 bank σε **κάθε** seat |
| 1.v0.5 | Ο harness αποδεικνύει ότι φορτώνει δύο διαφορετικά version checkpoints, το directional/non-inferiority verdict είναι σωστό και τα guard metrics έχουν executable tests |
| 1.v1a-v1e | Κάθε increment περνά directional non-inferiority έναντι immutable checkpoint του προηγούμενου· αρνητικό practical diff δεν μπορεί ποτέ να είναι GO· οριακό αποτέλεσμα κλιμακώνεται από 12 σε 24-48 seeds |
| 1 τελικό | 24/24 orientation-level wins (12 seeds × 2 seats) **vs `starter`**· median bank ≥ **$40k** στα ίδια 24 episodes (relative μετρική — η κοινή αγορά με έναν αδύναμο αντίπαλο φουσκώνει το απόλυτο bank σε σχέση με το ladder median $44.8k, review.md M11· απόλυτο καλιμπράρισμα μόνο από πραγματικά episodes, §4.3)· cold-process profile και στα δύο seats με `clean=True`, steady-state `max_turn × 3 < 1s` |
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

**Υπογραφές:** το Step-0 API παραμένει η βάση· τα πεδία με σχόλιο `v0.5` είναι pending
επεκτάσεις που πρέπει να υλοποιηθούν πριν από το v1a.

```python
# harness/play.py
@dataclass
class PlayResult:
    seed: int
    agents: tuple[str, str]          # ονόματα/paths, index = seat
    rewards: tuple[float, float]     # τελικό bank ανά seat (engine :937-940)
    winner: int | None               # None = tie
    statuses: tuple[str, str]        # "DONE" ή error status ανά agent
    episode_steps: int
    replay_path: Path | None
    turn_times: list[float] | None   # από env.logs, περιλαμβάνει lazy import στο turn 1
    metrics: dict                    # βλ. metrics.py
    health: dict
    agent_errors: list[dict]
    clean: bool

def play(agent_a, agent_b, seed: int, *,
         steps: int | None = None,
         record: bool = True, run_dir: Path | None = None,
         profile_seat: int | None = None,
         debug: bool = False, strict: bool = True,
         metrics: bool = True) -> PlayResult:
    """Ένα episode: steps=None χρησιμοποιεί το engine default.
    env.run([agent_a, agent_b]). agent_* = callable | "main.py" path | built-in name
    ("pass"/"random"/"starter"). record=True → env.toJSON() στο run_dir.
    strict=True απορρίπτει οποιοδήποτε per-step ERROR/TIMEOUT/INVALID/stderr.
    profile_seat → timings από το ίδιο το framework/env.logs."""
```

```python
# harness/compare.py
@dataclass
class CompareResult:
    per_seed: list[dict]      # v0.5: κρατά ΚΑΙ τα 2 raw orientation αποτελέσματα
    errors: list[dict]
    mean_diff: float
    se_diff: float
    n_effective: int
    wins_a: int; wins_b: int; ties: int       # paired-seed verdicts
    episode_wins_a: int; episode_wins_b: int  # v0.5
    median_bank_a: float                       # v0.5
    ci95: tuple[float, float]
    verdict: str              # v0.5 directional semantics

def compare(agent_a, agent_b, seeds: Sequence[int], *,
            both_seats: bool = True,      # A παίζει seat 0 ΚΑΙ seat 1 ανά seed (weed RNG asymmetry, MASTERPLAN §2#6)
            steps: int | None = None,
            run_dir: Path | None = None, record: bool = False,
            strict: bool = True, min_effect: float | None = None,
            non_inferiority_margin: float | None = None,  # v0.5
            resume: bool = False) -> CompareResult:
    """Paired-seed πρωτόκολλο (MASTERPLAN §6, μεθοδολογία viz cells 46-50).
    Με both_seats=True: 12 seeds → 24 episodes. Το per-seed diff για το κριτήριο
    υπολογίζεται στο μέσο των δύο seats του ίδιου seed, αλλά τα raw orientation
    αποτελέσματα διατηρούνται για τα acceptance gates.

    Directional semantics:
    - IMPROVED: mean_diff > 0, lower CI > 0 και mean_diff > practical margin
    - NON_INFERIOR: lower CI >= -non_inferiority_margin
    - REGRESSED: upper CI < -non_inferiority_margin
    - αλλιώς INCONCLUSIVE → περισσότερα seeds· ποτέ GO από abs(mean_diff)."""
```

```python
# harness/metrics.py
def extract_metrics(env_json: dict, seat: int) -> dict:
    """Από replay JSON (env.toJSON()). Βήμα 0 minimum:
       - final_bank, bank_curve (ανά turn — εντοπισμός stalls, MASTERPLAN §6 πίνακας #2)
       - opponent_final_bank, outcome
       Βήμα 1 επέκταση (προαπαιτούμενο v0.5, πριν χρησιμοποιηθούν οι guards):
       - weeds_lost (φυτά που έγιναν weed), animals_escaped
       - shed_overflow_burnt, units_sold_at_or_below(5), avg_sell_price ανά προϊόν vs base
       - worker_turns_moving vs working"""
```

Τα operational metrics δεν θεωρούνται διαθέσιμα επειδή απλώς δηλώνονται εδώ. Στο v0.5
ορίζεται και τεστάρεται ο ακριβής transition extractor για κάθε event. Για actual SELL prices,
όπου το απλό state diff δεν αρκεί λόγω lockstep interleaving, χρησιμοποιείται deterministic
market-trace reconstruction από τα δύο action queues και τα pre-turn states. Τα debug receipts
του G11 συλλέγονται χωριστά από `env.logs` στο `PlayResult` — δεν υπάρχουν στο `env.toJSON()`.

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
                             #   sys.path insert("/kaggle_simulations/agent/") (competition_info.md:524)
                             #   — literal path, ΟΧΙ dirname(__file__): ο loader κάνει exec() σε
                             #   ένα namespace χωρίς __file__ (review.md C3, επαληθεύτηκε: σκάει με
                             #   NameError και στο harness ΚΑΙ στον server), μετά top-level:
                             #   from agent.policy import agent   # ΟΧΙ μέσα σε def agent(obs) — lazy
                             #   imports σκάνε αφού ο loader κάνει sys.path.pop() μετά το exec
agent/
├── __init__.py
├── constants.py             # Layer-ανεξάρτητο: engine σταθερές
├── _vendored.py             # fallback constants/market_price, parity-tested με engine 1.32.4
├── state.py                 # View: parse του obs dict → δομημένο snapshot
├── planner.py               # Layer 1: economic planner (ανά μέρα / on-event)
├── scheduler.py             # Layer 2: task scheduler (ανά turn)
├── executor.py              # Layer 3: market executor (ανά turn)
├── config.py                # nested CONFIG — planner/scheduler/executor/endgame/guards
└── policy.py                # agent(obs) glue: state → planner (αν νέα μέρα) → scheduler → executor
```

Το `CONFIG` schema ορίζεται πλήρως από το v0 (ακόμη κι αν τα μεταγενέστερα sections είναι
αρχικά inactive), ώστε animals/endgame/market tuning να μη χρειαστούν αλλαγή interface:
`planner`, `scheduler`, `executor`, `animals`, `endgame`, `guards`, `runtime`. Όλα τα iteration
orders που επηρεάζουν actions είναι ρητά tuples/lists — όχι set iteration.

**`constants.py`** (Υ6): 

```python
try:
    from kaggle_environments.envs.kaggriculture.kaggriculture import (
        CROPS, ANIMALS, MARKET_PARAMS, market_price)   # engine_reference/kaggriculture.py:11-51, :178-192
except ImportError:
    from ._vendored import CROPS, ANIMALS, MARKET_PARAMS, market_price  # verbatim αντίγραφο
```

Συν παράγωγες σταθερές: `SHED_ACCESS = [(4,4),(5,4),(4,5),(5,5)]` (:118-121), `LAND_ORDER/LAND_PRICES` (:83-84), `SHOPS` (:90-99), town demand schedule (:104).
Το `_vendored.py` είναι μέρος του v0 deliverable και έχει parity test για constants και
`market_price()` έναντι του installed engine — δεν αναβάλλεται μέχρι το submission.

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

**`planner.py`** — Layer 1, τρέχει στο hour 0 κάθε μέρας ή όταν observed state αποκλίνει
από το plan (νέο quadrant, αποτυχημένη αγορά/reservation, αλλαγή season phase):

```python
@dataclass
class DayPlan:
    plant_targets: dict[str, int]        # crop -> πόσα νέα tiles σήμερα
    hands_target: int                    # πόσα HIRE σήμερα
    buy_land: bool                       # trigger για BUY_LAND
    animal_purchases: dict[str, int]     # Φάση v1d
    structures_to_build: dict[str, int]  # COOP/PASTURE prerequisites
    sell_floor_price: dict[str, int]     # ανά προϊόν: ελάχιστη αποδεκτή marginal τιμή
    seed_orders: dict[str, int]
    season_phase: str                    # OPEN/GROW/LIQUIDATE
    force_liquidation: bool

def make_day_plan(snap: Snapshot, cfg: CONFIG) -> DayPlan
```

Χρησιμοποιεί το ακριβές `market_price()` για την **own-queue** marginal εκτίμηση και τα
ντετερμινιστικά town intervals (MASTERPLAN §4.1). Η actual execution quote μπορεί να διαφέρει
λόγω άγνωστων same-turn orders του αντιπάλου· opponent-aware λογική = Φάση 2. Κάθε επένδυση
(crop/animal/land) περνά horizon check ώστε η παραγωγή να προλαβαίνει HARVEST→DROP→SELL πριν
το τέλος. Στο `LIQUIDATE` σταματούν οι μη αποσβέσιμες αγορές/φυτεύσεις και υπερισχύει το
τελικό cash-out.

**`scheduler.py`** — Layer 2, κάθε turn:

```python
@dataclass
class Task:
    id: str
    kind: str            # + BUILD_COOP/BUILD_PASTURE/PLACE, εκτός των υπαρχόντων ops
    pos: tuple[int, int]
    priority: int        # χαμηλότερο = πιο επείγον
    item: str | None     # crop/animal/product
    count: int
    deadline_step: int
    prerequisites: tuple[str, ...]
    required_inventory: dict[str, int]
    reservation_key: str | None

@dataclass
class ResourceLedger:
    seeds: dict[str, int]       # μόνο observed seeds, ποτέ queued BUY_SEED
    unit_inventory: list[dict]
    shed_free: int
    money: float
    market_slots: int

def build_tasks(snap, plan) -> list[Task]
    # Βασική ιεραρχία (πάντα με deadline/slack ως tie-break):
    # 1 WATER (consecutive_unwatered==1: water σήμερα ή weed απόψε)
    # 2 FEED (ζώα με consecutive_unfed==1 πρώτα)
    # 3 HARVEST πριν από production clipping / plant decay
    # 4 CARE, 5 HARVEST λοιπά, 6 PLANT, 7 COLLECT_FERTILIZER/FERTILIZE, 8 DROP στο shed
    # Workflows:
    #   seed observed → PLANT → WATER πριν EOD
    #   BUILD_* → BUY_ANIMAL → PICKUP → MOVE → PLACE
    #   PICKUP WHEAT → MOVE → FEED; COLLECT → carry/drop/FERTILIZE
    #   HARVEST → carry → DROP → SELL

def assign(tasks, units: list[UnitPos], snap) -> list[list[str]]
    # Greedy nearest-unit-first (Manhattan)· Hungarian ΜΟΝΟ αν το greedy αποδειχθεί
    # μετρήσιμα χειρότερο στο harness (όχι προκαταβολική πολυπλοκότητα).
    # Deterministic order: (priority, deadline_step, slack, distance, y, x, unit_index).
    # Task/resource reservation αποτρέπει duplicate assignment και atomic-PLANT failure.
    # Engine execution order = farmer πρώτα, μετά hands κατά index (:912-916). Για το ίδιο
    # tile ανατίθεται το πολύ ένα tile-op ανά turn, αλλιώς τα επόμενα units κάνουν silent no-op.
    # Επιστρέφει action ανά unit: [farmer_action, *hand_actions] — index-aligned με
    # farm["hands"] (MASTERPLAN §2#1, engine :264-268). Unit χωρίς task → κίνηση προς
    # το επόμενο task ή PASS.
```

Το board είναι 10×10 και τα planned hands 2-4, άρα scan O(100) και greedy O(units×tasks)
είναι αμελητέα ως προς το 1s budget. Το performance guard είναι task deduplication και
ρητά caps — όχι Hungarian. Manhattan είναι πραγματικό shortest-path metric εδώ επειδή οι
μονάδες συνυπάρχουν και τα LOCKED tiles είναι passable.

**`executor.py`** — Layer 3, κάθε turn, ≤ 10 orders (engine :537):

```python
def market_orders(snap, plan, ledger, scheduled_unit_actions, cfg) -> list[list]:
    # allocate_market_slots() συνθέτει ΟΛΗ τη λίστα εντός cap — δεν φτιάχνουμε
    # >10 orders για να τα κόψουμε μετά.
    # Mandatory survival/procurement, price-sensitive SELL, HIRE/LAND και discretionary
    # orders ανταγωνίζονται με ρητό slot+money+shed budget.
    # SELL quantity: own-queue marginal model + configurable opponent safety margin.
    # Το market βλέπει το post-unit state. Πριν από SELL γίνεται deterministic projection
    # των scheduled HARVEST/DROP/PICKUP/consumption effects· δεν χρησιμοποιείται μόνο το
    # pre-action snap, αλλιώς same-turn harvest/drop inventory μένει αδικαιολόγητα απούλητο.
    # HIRE/BUY_LAND δεν δεσμεύονται μηχανικά στα index 0-1: αυτό θα χάριζε στον
    # αντίπαλο προγενέστερα SELL quotes. Η index policy είναι μέρος του CONFIG.
    # LIQUIDATE: πούλησε κάθε monetizable unit ακόμη και στο $1 floor — unsold = $0 reward.
    # Hard postcondition: len(orders) <= 10.
```

Κρίσιμη engine σειρά: τα unit actions εκτελούνται πριν το market (`:912-923`). Άρα αγορές
και HIRE του τρέχοντος turn είναι διαθέσιμα από το επόμενο turn. HIRE στο hour 0 δίνει 23
action turns· HIRE στο hour 23 απαγορεύεται γιατί το hand διαγράφεται στο ίδιο EOD. Ο
scheduler δεν επιτρέπεται να καταναλώσει queued seed/wheat/animal σαν να υπήρχε ήδη.
Στο EOD γίνεται υποχρεωτικό auto-drop όλων των unit inventories στο shed (`:821-835`,
overflow καίγεται), μετά hands/hires_today/inventories μηδενίζονται και ο farmer respawnάρει
στο shed (`:857-860`). Οι seeds είναι ξεχωριστό `private["seeds"]` resource: δεν περνούν από
shed ή unit inventory και το atomic PLANT ελέγχει μόνο το observed seed dict (`:897-910`).

**`policy.py`**:

```python
_RUNTIME_BY_PLAYER = {}  # context ανά player· reset όταν step==0 ή step μειωθεί.
                         # Κανένα correctness-critical resource δεν ζει μόνο εδώ.

def agent(obs):
    snap = parse(obs)
    runtime = reset_or_get_runtime(snap)
    plan = get_or_make_day_plan(snap, runtime)
    tasks, ledger = build_tasks_and_ledger(snap, plan, runtime)
    farmer, hands = assign(tasks, units(snap), snap)
    market = market_orders(snap, plan, ledger, [farmer, *hands], CONFIG)
    record_expected_transitions(runtime, snap, farmer, hands, market)  # debug-only receipts
    return {"farmer": farmer, "hands": hands, "market": market}
```

Στο mirror match τα δύο seats μοιράζονται το ίδιο imported `agent.policy` module, άρα κάθε
runtime/cache key περιλαμβάνει `player`. Δύο διαδοχικά episodes στο ίδιο process είναι επίσης
υποχρεωτικό test: step reset δεν πρέπει να κληρονομεί plan ή intended-action receipt.

### 3.2 Guard κανόνες — testable requirements (`tests/test_agent_guards.py`)

Κάθε guard έχει το σωστό επίπεδο test: contract/unit test για action construction και
reservations, transition test για συγκεκριμένο engine pipeline, full-episode metric μόνο όπου
το replay πράγματι παρατηρεί το event. Δεν βαφτίζουμε κάθε guard «replay test».

| # | Guard | Testable απαίτηση |
|---|---|---|
| G1 | Πότισμα ημέρας φύτευσης (§7#4) | 0 plant→weed losses από missed water· PLANT επιτρέπεται μόνο με reserved observed seed και εφικτό WATER πριν το τρέχον EOD |
| G2 | Ατομικό PLANT (§2#4) | Ποτέ 2 units με PLANT ίδιου crop σε turn με ανεπαρκείς σπόρους — ο scheduler κάνει reserve σπόρων ανά turn |
| G3 | Shed cap 100 (:821-835) | `shed_overflow_burnt == 0`· ledger μετρά shed + όλα τα carried inventories + scheduled DROP/BUY πριν το EOD |
| G4 | Price discipline (:629-637) | Σε OPEN/GROW: 0 actual units sold ≤ configurable threshold, με trace reconstruction· σε LIQUIDATE επιτρέπεται πώληση έως και στο $1 γιατί unsold inventory αξίζει $0 |
| G5 | Feed logistics, κανένα ζώο άταιστο | `animals_escaped == 0`· wheat πρέπει να είναι reserved στο inventory του worker πριν το FEED, όχι απλώς queued/στο shed· BUY_PRODUCT έχει ≥1-turn lead. FEED αποτρέπει escape· CARE είναι οικονομικό yield bonus, όχι survival precondition |
| G6 | Hand σε locked spawn (engine :309-317, :510-518) | Hands από (5,4) και (5,5) περνούν από LOCKED tiles προς unlocked εργασία· κανένα δεν χαρακτηρίζεται trapped μόνο λόγω quadrant lock |
| G7 | 10-order/resource budget (§2#2) | `len(market) <= 10` σε κάθε turn και κάθε order καλύπτεται από predicted money/shed/slot ledger· η θέση HIRE/LAND ακολουθεί explicit index policy, όχι hardcoded 0-1 |
| G8 | Ζώα max_held (MASTERPLAN §3.2#1) | 0 clipped production ticks· HARVEST πριν το production EOD όταν `yield_units + expected_output > max_held` |
| G9 | Harvest πριν το decay (§2#5) | 0 μονάδες χαμένες σε `_decay_plants` για δικά μας ώριμα one-shots· deadline σε `max_lifespan_step` και decay ανά 2 steps, όχι day-only heuristic (`:730-744`) |
| G10 | Horizon-aware strawberry deadline | Η μέρα 13 είναι μόνο production bound· PLANT επιτρέπεται αν όλες οι αναμενόμενες παραγωγές προλαβαίνουν HARVEST→DROP→SELL με βάση απόσταση/remaining turns, αλλιώς μειωμένο-value plan ή αποκλεισμός |
| G11 | Silent no-op detector (Ρίσκο #6, MASTERPLAN §7) | Debug-only: precondition validation + action-specific expected transition receipts + boundary-aware reconciliation στο επόμενο obs· expected no-ops κατηγοριοποιούνται, unexplained = 0 |
| G12 | Loader contract (review C2/C3) | `main.py` φορτώνει lazy όπως ο server, το exported `agent` είναι το τελευταίο callable, imports top-level, κανένα callable import μετά από αυτό |
| G13 | Runtime isolation & determinism | Mirror seats και διαδοχικά episodes δεν μοιράζονται plan/receipts· ίδιο seed σε fresh processes και διαφορετικό `PYTHONHASHSEED` δίνει ίδιο trajectory |
| G14 | Endgame liquidation | 0 avoidable unsold value στο τέλος· κανένα late crop/animal purchase χωρίς θετικό cashable payoff πριν το τελευταίο market turn |
| G15 | Version identity | Κάθε `compare(new, prev)` καταγράφει διαφορετικά immutable code fingerprints/package namespaces· collision ή stale import αποτυγχάνει πριν το πρώτο seed |

Το G11 δεν είναι ένα generic `state_before != state_after`. WATER/FEED/CARE στο hour 23,
farmer reset, hand deletion, production, auto-drop, weeds και market interleaving έχουν
action-specific postconditions. Τα receipts γράφονται structured στο local stdout και
συλλέγονται από `env.logs`; debug είναι off στο submission.

### 3.3 Σειρά υλοποίησης — μικρά, συγκρίσιμα increments

Κάθε strategic increment: υλοποίηση → contract/guard tests → immutable checkpoint με μοναδικό
package namespace → `compare(new, prev, seeds=range(12), both_seats=True)`. Για να προχωρήσει:
directional `IMPROVED` ή αποδεδειγμένο `NON_INFERIOR` εντός του δηλωμένου margin. Αρνητικό
practical diff = `REGRESSED`, ποτέ GO. `INCONCLUSIVE` κλιμακώνεται σε 24-48 seeds και, αν
παραμένει οριακό, σταματά για απόφαση — δεν βαφτίζεται μη-χειροτέρευση. Τα checkpoints στο
`runs/checkpoints/` αντικαθιστούν την ανάγκη commit· commit/push μόνο με ρητή οδηγία χρήστη.
Η τελική απόφαση v1e θέλει 24-48 seeds. Το v1a′ έχει ανεβασμένη προτεραιότητα λόγω του
strawberry ladder evidence (MASTERPLAN §3.2.2).

- [x] **v0 — walking skeleton**: `main.py` + `agent/` skeleton + `_vendored.py`· parse του obs, PASS παντού, 0 market orders. Το `main.py` τελειώνει με top-level import του exported `agent`. *Αποδοχή:* `play("main.py","main.py",seed=0,steps=720)` με `clean=True`, DONE, ακριβώς $3.000 και στα 2 seats· G12/G13 loader, mirror, sequential-episode, vendored-parity και cross-process determinism tests πράσινα.
- [x] **v0.5 — measurement/checkpoint foundation**: directional/non-inferiority `compare`, raw orientation metrics + median bank, unique-namespace immutable checkpoints/G15, operational metric extractors και G11 receipt plumbing. *Αποδοχή:* synthetic negative diff = REGRESSED (ποτέ GO), A/B fingerprints διαφορετικά, crafted replays με γνωστά weeds/overflow/sales/no-ops μετρώνται ακριβώς.
- [x] **v1a — carrot loop, multi-tile**: planner με στόχο N carrot tiles στο NW, observed-seed reservation, scheduler με deadline/slack για PLANT→WATER και harvest/replant, executor με market slot ledger και G4. *Αποδοχή:* ≥10/12 paired-seed wins και ≥20/24 orientation wins vs `starter`, median bank >$8k στα 24 episodes, G1/G2/G4/G7/G9 πράσινα.
- [x] **v1a′ — strawberry loop** (νέο, MASTERPLAN §3.2.2): φύτευση strawberries νωρίς μόνο αν περνά G10 horizon check· πότισμα κάθε δεύτερη μέρα αρκεί μετά το υποχρεωτικό planting-day water (η παραγωγή στο `_daily_refresh_plants` :767-780 δεν εξαρτάται από WATER — μόνο η επιβίωση), carrots ως cash-flow. *Αποδοχή:* directional IMPROVED ή NON_INFERIOR vs v1a, G10 πράσινο.
- [x] **v1b — hands**: HIRE 2-4 hands στο hour 0 (23 usable turns, fib κόστη :667-676), deterministic assign(), resource reservations και locked-tile routing από όλα τα shed spawns. *Αποδοχή:* directional gate vs v1a′, G6/G13 πράσινα, 0 unexplained idle/oscillation.
- [ ] **v1c — land**: BUY_LAND NE on-trigger (χρήματα ≥ $1k + υπάρχει εργατικό δυναμικό να το δουλέψει — MASTERPLAN §3.2#7: γη χωρίς hands = νεκρό κεφάλαιο), επέκταση φυτέματος στο NE. *Αποδοχή:* directional gate vs v1b και επιβεβαίωση ότι observed BUY_LAND success/failure προκαλεί σωστό replan.
  *STOP 2026-08-05:* τρεις capacity variants απέτυχαν ήδη στο smoke gate ($13k-$18k έναντι ~$21k του v1b, με 5-9 watering losses). Το working agent επανήλθε byte-for-byte στο checkpoint v1b· απαιτείται νέο routing/capacity design πριν από άλλη δοκιμή.
- [ ] **v1d — animals**: εσωτερικά δύο guard-gated sub-builds χωρίς benchmark του μισού feature: (A) BUILD_PASTURE/COOP (`:437-447`) → BUY_ANIMAL (μπαίνει στο shed) → PICKUP → PLACE από unit inventory (`:449-461`), (B) inventory-aware FEED+CARE, COLLECT_FERTILIZER, HARVEST, wheat procurement ≥1 turn νωρίτερα. 2-4 sheep/cow· CARE απαιτείται για το οικονομικό bonus μόνο όταν συνδυάζεται με FEED, όχι για survival. *Αποδοχή:* directional gate vs v1c, G3/G5/G8/G11 πράσινα και 0 clipped animal production.
- [ ] **v1e — full market + liquidation**: slot/money/shed allocator, post-unit inventory projection, actual-price trace metrics, marginal-price thresholds ανά προϊόν, hour-aware town demand (market πριν από town consume· center ramp + shop pulls, 2× στα single-product shops) και endgame LIQUIDATE που cash-άρει inventory ακόμη και κάτω από το normal G4 threshold. *Αποδοχή:* directional gate vs v1d σε 24-48 seeds **και** συνολικά κριτήρια Φάσης 1 (§1: 24/24 orientation wins vs starter, median ≥$40k, steady-state max×3<1s και στα 2 seats).
- [ ] `tests/test_agent_guards.py` και loader/runtime tests πράσινα για G1-G15 στο τελικό v1e· κάθε guard έχει γίνει πράσινο από το πρώτο increment όπου είναι σχετικό, όχι μαζικά στο τέλος.

---

## 4. ΒΗΜΑ 2 — Πρώτο Submission & Baseline

### 4.1 Checklist προ-υποβολής

- [ ] **Format** (Υ5): tar.gz με `main.py` στο **root** (competition_info.md:421-429):
  ```powershell
  tar -czf submission.tar.gz main.py agent/
  ```
- [ ] **Imports/loader**: το shim του `main.py` καλύπτει `/kaggle_simulations/agent/` (competition_info.md:524), ο exported `agent` είναι το τελευταίο callable/top-level import και ο relative vendored fallback έχει parity test. Προσοχή στο notebook pitfall — υποβολή από CLI.
- [ ] **Timing σε «αργό CPU»**: cold-process profile και στα δύο seats. Canonical steady-state gate `max_turn × 3 < 1s` (άρα <333ms local με τον συντηρητικό multiplier), cold import/turn-1 και cumulative overage αναφέρονται χωριστά, episode `clean=True`.
- [ ] **Deterministic check**: ίδιο seed σε 2 fresh processes και διαφορετικό `PYTHONHASHSEED` → ταυτόσημο action/state trajectory· δύο sequential episodes στο ίδιο process επίσης ταυτόσημα με fresh-process equivalents.
- [ ] **Mirror smoke**: `play("main.py", "main.py", seed=0)` — 720 steps, `clean=True`, κανένα cache cross-talk και καμία αυτοκαταστροφή αγοράς.
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

- [ ] `local_bench.json` — output του `compare(v1e, "starter", seeds=range(24), both_seats=True)` με raw orientation rows, paired rows, code fingerprints, median bank, CI/non-inferiority verdict και bank distribution (και vs `"pass"`, `"random"`), **και** mirror bank (`play("main.py","main.py")`)
- [ ] `validation.md` — αποτέλεσμα validation episode (pass/fail, χρόνος)
- [ ] `rating_trajectory.csv` — rating ανά episode για τα πρώτα ~20 episodes (από `kaggle competitions episodes`, χειροκίνητο ή scripted pull 1-2 φορές/μέρα)
- [ ] `leaderboard_snapshot.md` — θέση + rating την ημέρα 1 και ημέρα 3
- [ ] `replays/` — **2-3 ηττημένα** episodes + τα logs τους, για την πρώτη post-mortem ανάλυση της Φάσης 2
- [ ] Σημείωση κλίμακας: τα scores στο `data/archive/manifest.csv` είναι πιθανόν rating, ΟΧΙ $ (MASTERPLAN §3.2bis) — μην συγκριθούν με bank values.

### 4.4 Διαχείριση submission slots

Όρια: 5/μέρα, **μόνο τα 2 τελευταία active** και αυτά μπαίνουν στο final (competition_info.md:40, 523). Κάθε upload καίει 1 από τα 2 active slots. Πρωτόκολλο Φάσης 1-2:

- 1ο upload = v1e baseline (σκόπιμα νωρίς — δωρεάν πληροφορία από την πραγματική ladder, MASTERPLAN §5).
- 2ο upload **μόνο** όταν μια νέα έκδοση έχει directional `IMPROVED` verdict έναντι της τρέχουσας σε 24-48 seeds — όχι από `abs(diff)`, όχι απλή απουσία significance και όχι «δοκιμαστικά» uploads.

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
| 1 v0 → v1e | 5-8 μέρες (προστέθηκε v0.5 measurement/checkpoint foundation· v1d βαρύτερο) | 08-08 → 08-17 |
| 2 submission + baseline | 0.5 μέρα + 2-3 μέρες παθητικής παρακολούθησης | **πρώτο submission ~08-14/15** |

Συνολικά ~7-11 εργάσιμες → πρώτο submission εντός Αυγούστου, με buffer πριν την ενδεικτική μετάβαση σε Φάση 2 αρχές Σεπτεμβρίου.

### 5.2 Top-5 κίνδυνοι αυτών των 2 φάσεων & fallbacks

| # | Κίνδυνος | Πιθανό σύμπτωμα | Fallback |
|---|---|---|---|
| 1 | **Silent no-ops** (το engine δεν πετά semantic error): bug σε precondition/resource ownership χαμηλώνει το σκορ αθόρυβα | intended action χωρίς το action-specific expected effect | G11 preconditions + boundary-aware receipts από v0.5, structured `unexplained_noops`, contract/transition tests ανά action family |
| 2 | **Legacy kaggle CLI δεν δέχεται το KAGGLE_API_TOKEN** | `401/403` στο §2.5 | Αλυσίδα fallback ήδη γραμμένη στο §2.5 (access_token file → OAuth → kaggle.json)· ελέγχεται στο Βήμα 0, ημέρες πριν χρειαστεί |
| 3 | **Engine version bump στη ladder** πριν το submission (2 bumps την πρώτη εβδομάδα — MASTERPLAN §7 Ρίσκο #1) | Νέο kaggle-environments στο PyPI / ανακοίνωση | `pip install -U` + `pytest tests/` = ο detector (§2.2)· ό,τι κοκκινίσει διορθώνεται στοχευμένα· το pinned 1.32.4 μένει η τοπική βάση μέχρι να περάσει το suite στη νέα |
| 4 | **Server runtime διαφορές**: αργό 1.6 vCPU, import paths, validation fail | Submission Error / timeout | v0 walking skeleton δοκιμάζει το format νωρίς· ×3 timing margin (§2.4)· vendored constants fallback (Υ6)· σε Error: `kaggle competitions logs` για το validation episode και fix-forward — τα 5 submissions/μέρα επιτρέπουν 2-3 προσπάθειες την ίδια μέρα |
| 5 | **Λάθος/θορυβώδες increment verdict ή stale package import** | αρνητικό diff ως GO, ασταθές CI ή ίδια fingerprints για A/B | directional non-inferiority semantics, unique-namespace immutable checkpoints/G15, 12 seeds μόνο για coarse screen και 24-48 σε INCONCLUSIVE/final· πάντα both_seats |

---

## Εκκρεμότητες προς χρήστη

1. ~~**Αποδοχή κανόνων competition στο site**~~ **ΛΥΘΗΚΕ 2026-08-05** — `kaggle competitions list --group entered` επιστρέφει `userHasEntered: True`. Το submit δεν μπλοκάρεται πλέον.
2. ~~**Kaggle CLI auth**~~ **ΛΥΘΗΚΕ 2026-08-05** — το `KAGGLE_API_TOKEN` από το `.env` δούλεψε με το legacy CLI χωρίς κανένα fallback.

*(Το Kaggle API access για datasets μέσω kagglehub είναι ήδη λυμένο — καμία ενέργεια.)*
