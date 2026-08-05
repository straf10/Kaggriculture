# review.md — Code & Logic Review του commit `89d99f0` (agent v0–v1b + harness checkpoint/guard foundation)

> Ημερομηνία: 2026-08-05. Scope: **μόνο** οι αλλαγές του `89d99f0` (agent/ πλήρες, main.py,
> harness/checkpoint.py, επεκτάσεις compare/metrics/play/cli, νέα tests). Το Βήμα 0 (`5ccb60a`)
> ΔΕΝ επανελέγχθηκε. Μόνο ανάλυση — καμία αλλαγή κώδικα.
>
> Κάθε εύρημα φέρει ετικέτα επαλήθευσης:
> **[CONFIRMED-EXEC]** = αναπαράχθηκε εκτελεστικά στο `.venv` με repro script,
> **[CONFIRMED-READ]** = επιβεβαιωμένο με side-by-side ανάγνωση agent + engine source,
> **[PLAUSIBLE]** = συνεπής μηχανισμός, δεν παράχθηκε episode-level trace.
>
> Baseline κατάστασης: `pytest tests -q` → **80 passed σε 8.6s**. Fingerprint του working
> `agent/` == manifest του `runs/checkpoints/v1b` (`f0295e90…`) — το "byte-for-byte revert στο
> v1b" του memory.md **επιβεβαιώθηκε εκτελεστικά**.

---

## 0. Σύνοψη ευρημάτων

| # | Severity | Εύρημα | Αρχείο | Status |
|---|---|---|---|---|
| C1 | **Critical** | Ο scheduler δεν έχει κανένα capacity/feasibility μοντέλο· το slack λείπει από το sort key (απόκλιση από plan.md §3.1)· zero-slack watering cadence· nearest-first starvation μακρινών tiles → **αυτό είναι το πραγματικό αίτιο του v1c STOP, όχι "tuning capacity variants"** | `agent/scheduler.py` | CONFIRMED-READ + μηχανισμός |
| H1 | High | Same-turn multi-unit PLANT σπάει το `max_new_plants_per_day` (7 φυτά με cap 5) | `agent/scheduler.py:46-55,109-125` | **CONFIRMED-EXEC** |
| H2 | High | Όλα τα regression checkpoints (v0/v1a/v1a′/v1b) ζουν ΜΟΝΟ στο gitignored `runs/checkpoints/` — μηδενικό ίχνος στο git history· μόνο το v1b ανακτήσιμο (== committed `agent/`) | `.gitignore:5`, `harness/checkpoint.py` | **CONFIRMED-EXEC** |
| H3 | High | Η "immutability" των checkpoints είναι μόνο σύμβαση: κανείς δεν επαληθεύει το manifest fingerprint όταν το checkpoint χρησιμοποιείται σε `compare()` | `harness/checkpoint.py`, `harness/compare.py:103-108` | CONFIRMED-READ |
| H4 | High | G11: υπάρχει μόνο το harness-side plumbing (`KAGGRI_RECEIPT` parsing)· ο agent δεν εκπέμπει ποτέ receipts, δεν υπάρχει `unexplained_noops` — το βασικό αμυντικό εργαλείο του Ρίσκου #1/#6 δεν λειτουργεί· το v1c διαγνώστηκε "στα τυφλά" | `agent/policy.py`, `harness/play.py:131-147` | CONFIRMED-READ |
| H5 | High | Τα feasibility checks DIG/PLANT μετρούν απόσταση **μόνο από τον farmer**, αλλά το task μπορεί να το εκτελέσει hand με άλλη απόσταση → PLANT που δεν προλαβαίνει water πριν το EOD = weed το ίδιο βράδυ | `agent/scheduler.py:44,97,99,114` | CONFIRMED-READ |
| M1 | Medium | Liquidation DROP task: inventory-blind assignment — άδειος farmer πάνω στο (4,4) το μονοπωλεί με αέναα silent no-op DROP, ενώ το φορτωμένο hand κάνει PASS | `agent/scheduler.py:127-135`, `assign()` | **CONFIRMED-EXEC** |
| M2 | Medium | `compare(resume=True)`: τα rows του `results.jsonl` δεν φέρουν fingerprints/agent identity → resume μετά από αλλαγή κώδικα αναμειγνύει σιωπηλά αποτελέσματα δύο εκδόσεων | `harness/compare.py:119-144` | CONFIRMED-READ |
| M3 | Medium | `NON_INFERIOR` επιτεύξιμο με n=1 ή εκφυλισμένο CI (se=0 → ci=(mean,mean)) — gate περνάει χωρίς καμία στατιστική βάση | `harness/compare.py:213,230-231` | CONFIRMED-READ (+adjacent EXEC) |
| M4 | Medium | Planner: μόνο per-day replan· λείπει το on-event replan του plan.md §3.1 — προαπαιτούμενο του v1c acceptance ("observed BUY_LAND success/failure → σωστό replan") | `agent/policy.py:35-37`, `agent/planner.py` | CONFIRMED-READ |
| M5 | Medium | Executor: top-up σπόρων στο `seed_buffer=6` αγνοώντας πόσα target tiles απομένουν άφυτα → έως ~$600 νεκρό κεφάλαιο σε strawberry seeds (χωρίς resale) | `agent/executor.py:49-60` | CONFIRMED-READ |
| M6 | Medium | Units στέλνονται να περπατούν προς PLANT tasks των οποίων ο σπόρος μόλις δεσμεύτηκε/καταναλώθηκε από άλλο unit· `build_tasks` φτιάχνει PLANT task ανά tile ακόμα κι αν υπάρχει 1 σπόρος συνολικά | `agent/scheduler.py:176-181` | **CONFIRMED-EXEC** |
| M7 | Medium | `market_orders` κάνει `raise AssertionError` σε υπέρβαση cap — σε submission ένα raise = agent ERROR = χαμένο episode (σήμερα unreachable, max 7 orders, αλλά λάθος production συμπεριφορά για guard) | `agent/executor.py:72-74` | CONFIRMED-READ |
| M8 | Medium | metrics: PICKUP τοποθετημένου ζώου θα μετρηθεί ως `animals_escaped`· HARVEST στο/μετά το mls με σωστό parity μπορεί να μετρηθεί ως decay loss — θα διαφθείρει G5/G8 metrics στο v1d | `harness/metrics.py:236-242,220-235` | CONFIRMED-READ |
| L1-L10 | Low | Βλ. §4 | διάφορα | READ |

**Στατιστική εγκυρότητα `compare()` γενικά: ΚΑΘΑΡΗ** (t-table σωστό, paired CI σωστό, median από
raw orientations σωστό, INCOMPLETE σε errors σωστό) — εκτός των M2/M3. **Security: ΚΑΘΑΡΟ**
(το `version` regex του checkpoint.py μπλοκάρει path traversal). **Performance: ΚΑΘΑΡΟ**
(`extract_metrics` μετρήθηκε 0.5s/episode· `assign()` O(units²×tasks) αμελητέο έως ~10 units).

---

## 1. Το κεντρικό ερώτημα: τι πραγματικά σκότωσε το v1c

**Απάντηση: ΟΧΙ, δεν είναι "καθαρά capacity θέμα" με την έννοια που υπονοεί η σημείωση του
plan.md** ("τρία capacity variants απέτυχαν"). Τα "5-9 watering losses" είναι το αναμενόμενο
αποτέλεσμα **τεσσάρων προϋπαρχόντων δομικών κενών του v1b scheduler**, που η συμπαγής NW
γεωμετρία απλώς κάλυπτε. Κανένα tuning "capacity variant" δεν τα διορθώνει — γι' αυτό απέτυχαν
και οι 3 προσπάθειες με παρόμοιο τρόπο. Το v1c agent code δεν υπάρχει πια στο repo (σωστά,
revert), οπότε η απόδοση αιτίου γίνεται μέσω δομικής ανάλυσης του v1b κώδικα που ΘΑ εκτελούσε
το v1c workload· τα επιμέρους μηχανιστικά κομμάτια είναι επιβεβαιωμένα ξεχωριστά.

### 1.1 Zero-slack watering cadence [CONFIRMED-READ]

Το engine σκοτώνει φυτό στο EOD όταν `consecutive_unwatered >= 2` (engine :755-762). Ο
scheduler ποτίζει strawberry **μόνο** όταν `consecutive_unwatered >= 1` ([scheduler.py:64-70](agent/scheduler.py#L64-L70))
— δηλαδή πάντα την τελευταία δυνατή μέρα. Οικονομικά σωστό (μισό watering labor), αλλά:
**μία και μόνη μέρα αποτυχίας = θάνατος το ίδιο βράδυ**. Δεν υπάρχει fallback, δεν υπάρχει
"πότισε νωρίς αν έχεις πλεονάζον capacity".

### 1.2 Το slack ΛΕΙΠΕΙ από το sort key του assign() — απόκλιση από το ίδιο το plan.md [CONFIRMED-READ]

Το plan.md §3.1 προδιαγράφει: `(priority, deadline_step, slack, distance, y, x, unit_index)`.
Το υλοποιημένο key ([scheduler.py:184-193](agent/scheduler.py#L184-L193)) είναι
`(priority, deadline_step, distance, y, x, unit_index, task.id)` — **χωρίς slack**. Όλα τα
WATER tasks της μέρας μοιράζονται priority=0 και **ταυτόσημο** `deadline_step` (το `day_deadline`),
άρα η ανάθεση εκφυλίζεται σε **καθαρό nearest-pair-first**: το κοντινό tile κερδίζει πάντα, το
μακρινό tile — που χρειάζεται να ξεκινήσει ΤΩΡΑ για να προλάβει — παίρνει unit τελευταίο ή ποτέ.
Χωρίς slack, ο scheduler είναι δομικά τυφλός στο "μακρινό αλλά επείγον".

### 1.3 Κανένα capacity/feasibility μοντέλο πουθενά [CONFIRMED-READ]

- `build_tasks` παράγει WATER task για κάθε διψασμένο φυτό χωρίς κανέναν έλεγχο ότι το συνολικό
  (travel + action) unit-turn demand χωράει στα διαθέσιμα unit-turns της μέρας.
- `assign()` αναθέτει 1 task/unit/turn greedy· task που δεν προλαβαίνεται απλώς… δεν γίνεται,
  σιωπηλά. Το `deadline_step` είναι **μόνο sort key** — δεν φιλτράρει τίποτα, δεν κλιμακώνει
  τίποτα, δεν ενημερώνει τον planner ότι το πλάνο είναι ανέφικτο.
- Ο planner ([planner.py:20-40](agent/planner.py#L20-L40)) διαβάζει **μόνο config σταθερές**
  (`carrot_tiles`, `strawberry_tiles`, `hands_target`) — ούτε πόσα φυτά υπάρχουν, ούτε πού, ούτε
  πόσα hands/αποστάσεις. Plant targets και watering capacity δεν συνδέονται πουθενά.
- Κρίσιμο engine fact για το μοντέλο: **όλα τα units επιστρέφουν στο shed κάθε EOD** (farmer
  respawn :857, hands διαγράφονται :858 και ξαναπροσλαμβάνονται hour 0) — το πρωινό commute
  προς NE (απόσταση 5-13 από το (4,4)) καίει 20-50% της ημερήσιας χωρητικότητας ενός hand και
  ΔΕΝ αποτυπώνεται πουθενά.

### 1.4 Ο πολλαπλασιαστής ζημιάς: strawberry yield accrual [CONFIRMED-READ]

Ο scheduler θερίζει strawberries μόνο σε `age >= 16` ([scheduler.py:79-82](agent/scheduler.py#L79-L82)),
αφήνοντας έως 4 units να συσσωρεύονται πάνω στο φυτό (engine :767-780). Σωστό ως labor-saving,
αλλά σημαίνει ότι **ένα missed watering σε ηλικία 10-15 χάνει το φυτό ΜΑΖΙ με 1-3 δεδουλευμένα
units** (~$120 base/unit). 5-9 τέτοιοι θάνατοι + χαμένο μελλοντικό yield + το κόστος του σπόρου
εξηγούν άνετα τη διαφορά $13k-$18k έναντι ~$21k.

### 1.5 Συνεισφέροντες (δευτερεύοντες) μηχανισμοί

- **H1** [CONFIRMED-EXEC]: το same-turn multi-PLANT σπάει το ημερήσιο cap (βλ. §2.H1) → 
  περισσότερα φυτά από όσα αντέχει το watering capacity της επόμενης μέρας. Στο v1c, με
  περισσότερα άδεια tiles και units, ο μηχανισμός πυροδοτείται συχνότερα.
- **H5** [CONFIRMED-READ]: PLANT feasibility με απόσταση farmer αλλά εκτέλεση από μακρινό hand
  → φύτεμα χωρίς εφικτό same-day water = weed το ίδιο βράδυ (το `_new_plant` ξεκινά με
  `consecutive_unwatered=1`, engine :208).
- **Oscillation** [PLAUSIBLE]: τα tasks ξαναχτίζονται και η ανάθεση ξαναποφασίζεται από το μηδέν
  κάθε turn χωρίς καμία δέσμευση (stickiness)· ένα unit καθ' οδόν προς μακρινό tile μπορεί να
  ανακατευθυνθεί όταν εμφανιστεί νέο κοντινό priority-0 task, μηδενίζοντας την επένδυση
  διαδρομής. Συνεπές με τον κώδικα, δεν παράχθηκε trace που να το δείχνει σε episode.

### 1.6 Τι ΔΕΝ φταίει (αποκλείστηκε ρητά)

- **Δεν υπάρχει movement collision/blocking**: το engine ΔΕΝ έχει occupancy check στην κίνηση
  (`_apply_unit_action` MOVE, engine :309-317 — μόνο bounds check, units μπορούν να συνυπάρχουν
  στο ίδιο tile). Η "one-unit-per-tile" σημείωση αφορά tile-ops (2ο WATER στο ίδιο tile = no-op),
  όχι κίνηση. Άρα deadlock από αμοιβαίο μπλοκάρισμα διαδρομών **δεν** συνέβη στο v1c — μην
  σπαταληθεί redesign effort σε collision avoidance.
- **Το reservation logic seeds (G2) είναι σωστό** για units που στέκονται στο tile τους
  (atomic-PLANT ασφαλές), και ο executor δεν υπερβαίνει ποτέ το 10-order cap (max 7 by
  construction).
- **Ο executor/market δεν εμπλέκεται**: SELL μόνο από shed με συντηρητικό marginal pricing —
  κανένας μηχανισμός του να προκαλέσει watering losses.

**Συμπέρασμα για το retry:** το "explicit per-quadrant worker capacity + deadline-feasible
routes" που προτείνει το memory.md είναι σωστή κατεύθυνση αλλά **ανεπαρκής** αν δεν διορθωθούν
ταυτόχρονα: το slack στο sort key (1.2), το same-turn plant cap (H1), το per-unit feasibility
(H5), και η σύνδεση planner↔capacity (1.3). Βλ. §5.

---

## 2. Critical / High ευρήματα — αναλυτικά

### C1 — Scheduler χωρίς capacity/feasibility μοντέλο (root cause v1c)

Η πλήρης τεκμηρίωση είναι το §1. **Impact:** κάθε μελλοντική επέκταση (v1c land, v1d animals —
που προσθέτει FEED με δικό του zero-slack θάνατο `consecutive_unfed>=2`, engine :795) θα
ξανασκάσει στον ίδιο τοίχο· τα animals μάλιστα χειρότερα, γιατί escape = χαμένο κεφάλαιο $300-500.

**Επίλυση (σειρά εργασιών):**
1. **Slack στο sort key** όπως το προδιαγράφει ήδη το plan.md: `slack = deadline_step - step -
   distance(unit, task)`. Ταξινόμηση `(priority, slack, distance, …)` ή τουλάχιστον προσθήκη
   slack πριν το distance. Μόνο του, αυτό κάνει τα μακρινά WATER να κερδίζουν units νωρίς.
2. **Ημερήσιος capacity έλεγχος στον planner**: στο hour 0, υπολόγισε `demand = Σ(travel από
   spawn + 1) ανά υποχρεωτικό task` και `supply = units × 24 − commute`. Αν demand > supply·k
   (π.χ. k=0.8 safety), **μείωσε τα plant_targets / μην αγοράσεις γη** — η γη χωρίς εφικτό
   watering είναι το "νεκρό κεφάλαιο" του MASTERPLAN §3.2#7 με χειρότερους όρους (σκοτώνει και
   τα υπάρχοντα φυτά).
3. **Watering slack option**: όταν υπάρχει πλεονάζον capacity, πότισε και tiles με
   `consecutive_unwatered == 0` που είναι μακριά (προαγορά ασφάλειας)· εναλλακτικά χαμήλωσε το
   trigger σε "πότισε το πρωί, όχι όποτε τύχει" δίνοντας priority boost όσο πέφτει το
   `turns_left_today - distance`.
4. **Task stickiness**: κράτα στο `RuntimeContext` την ανάθεση unit→task του προηγούμενου turn
   και σπάσε ισοπαλίες υπέρ της συνέχισης, ώστε επενδυμένη διαδρομή να μην πετιέται.
5. Πρόσθεσε **scheduler-level guard test** που κατασκευάζει ευρύ farm (π.χ. 10 tiles σε
   αποστάσεις 5-13, 2 units, hour 0) και βεβαιώνει είτε όλα τα υποχρεωτικά WATER εφικτά είτε ότι
   ο planner έκοψε στόχους — ΟΧΙ μόνο happy-path με farmer πάνω στο tile.

### H1 — Same-turn multi-PLANT σπάει το `max_new_plants_per_day` [CONFIRMED-EXEC]

Το `planted_today < max_new_plants` ([scheduler.py:113](agent/scheduler.py#L113)) είναι
**threshold check τη στιγμή του build**, όχι budget: με `planted_today=4` και cap 5
δημιουργούνται PLANT tasks για ΟΛΑ τα υπόλοιπα άδεια tiles, και το `assign()` μπορεί να βάλει
πολλά units να φυτέψουν στο ίδιο turn. **Αναπαράχθηκε: 3 ταυτόχρονα PLANT με planted_today=4 →
7 φυτά τη μέρα με cap 5.** Impact: το cap υπάρχει ακριβώς για να φράξει το αυριανό watering
demand· η παραβίαση τροφοδοτεί το C1. **Επίλυση:** πέρασε budget
`remaining = max_new_plants - planted_today` μέσα στο `assign()` (μαζί με το seeds_remaining
pattern που ήδη υπάρχει) και μείωσέ το σε κάθε PLANT ανάθεση — και για τα moving units,
ώστε να μετρά η πρόθεση, όχι μόνο η στιγμιαία εκτέλεση.

### H2 — Το regression-baseline ιστορικό ζει μόνο σε gitignored φάκελο [CONFIRMED-EXEC]

Επιβεβαιώθηκε: `runs/` στο [.gitignore:5](.gitignore#L5), `git log --all -- runs/` κενό — **κανένα
ίχνος των checkpoints σε ολόκληρο το git history**. Τα v0/v1a/v1a_prime/v1b υπάρχουν μόνο ως
working-tree αρχεία. Το plan.md περιγράφει το `runs/` ως αναλώσιμο (replays 105MB+) και
ταυτόχρονα λέει "τα checkpoints αντικαθιστούν την ανάγκη commit" — αντίφαση με πραγματικό ρίσκο:
ένα `rm -r runs/` για χώρο διαγράφει **όλη** την αλυσίδα των accepted baselines. Σήμερα μόνο το
v1b είναι ανακτήσιμο (fingerprint match με το committed `agent/`, επιβεβαιωμένο)· τα v0/v1a/v1a′
είναι **μη ανακατασκευάσιμα** από κανένα commit. Χωρίς αυτά: αδύνατο το bisect μελλοντικής
παλινδρόμησης, αδύνατη η επανεπαλήθευση των gates v1a→v1a′→v1b.

**Επίλυση (πρόταση):** μετακίνηση των checkpoints εκτός `runs/` σε committed path — π.χ.
`checkpoints/` στο root (ΚΒ-επίπεδο μέγεθος, όχι MB) — ή negation `!runs/checkpoints/` στο
.gitignore· commit ΤΩΡΑ των τεσσάρων υπαρχόντων ώστε να μπουν στο history, και στο εξής commit
(ή τουλάχιστον `git tag`) ανά accepted increment. Το tag-only ΔΕΝ αρκεί αναδρομικά: tags δείχνουν
commits, και v0/v1a/v1a′ δεν υπάρχουν σε κανένα commit. Σημείωση: το default
`checkpoint_root="runs/checkpoints"` στο [checkpoint.py:50](harness/checkpoint.py#L50) και στο
CLI `--out` πρέπει να αλλάξουν μαζί.

### H3 — Η immutability των checkpoints δεν επιβάλλεται πουθενά [CONFIRMED-READ]

Το `manifest.json` γράφεται στο create αλλά **δεν διαβάζεται ποτέ ξανά**: το
`agent_fingerprint()` χασάρει ό,τι υπάρχει στον δίσκο τη στιγμή του compare, και το
`compare()` ελέγχει μόνο A≠B ([compare.py:103-108](harness/compare.py#L103-L108)). Ένα checkpoint
που τροποποιήθηκε (κατά λάθος edit, εργαλείο, merge) περνάει ως "το immutable v1b" ενώ δεν
είναι — όλα τα increment gates χάνουν το νόημά τους σιωπηλά. **Επίλυση:** στο
`agent_fingerprint()` (ή σε νέο `load_checkpoint()`), όταν το spec είναι main.py με διπλανό
manifest.json: επαλήθευσε `manifest["fingerprint"] == _hash_package(dir)` και raise σε mismatch·
προαιρετικά κάνε τα αρχεία read-only στο create. Δευτερεύον [PLAUSIBLE-edge]: εντός ίδιου
process, το `sys.modules` cache μπορεί να εκτελεί stale module ενώ το fingerprint διαβάζεται
από τον δίσκο — αμελητέο για CLI (fresh process), αξίζει σχόλιο.

### H4 — G11 receipts: μόνο ο "δέκτης" υπάρχει, ο "πομπός" όχι [CONFIRMED-READ]

Το `play()` συλλέγει `KAGGRI_RECEIPT` lines από stdout ([play.py:131-147](harness/play.py#L131-L147))
και υπάρχει test γι' αυτό — αλλά **κανένα σημείο του agent δεν τυπώνει receipt**: το
`record_expected_transitions` του plan.md §3.1 δεν υλοποιήθηκε, το `CONFIG["guards"]["debug"]`
δεν διαβάζεται πουθενά, και το metrics.py δεν έχει `unexplained_noops`. Το plan.md §5.2 Ρίσκο #1
υπόσχεται "G11 preconditions + receipts από v0.5". Impact: σε ένα engine που ποτέ δεν πετάει
exception, ο G11 είναι το ΜΟΝΟ εργαλείο που μετατρέπει "χάσαμε $8k" σε "το WATER στο (7,2) στο
step 341 δεν είχε το αναμενόμενο αποτέλεσμα" — ακριβώς ό,τι έλειψε στη διάγνωση του v1c.
**Επίλυση:** πριν το v1c retry, υλοποίησε το minimum: για κάθε scheduled WATER/PLANT/HARVEST,
receipt `{step, unit, kind, pos, expected}` όταν `guards.debug=True`, και reconciliation στο
επόμενο obs (boundary-aware: hour-23 actions κρίνονται μετά το EOD). Off στο submission.

### H5 — Feasibility με απόσταση farmer για tasks που εκτελούν hands [CONFIRMED-READ]

Στο `build_tasks`, το `distance` για τα DIG/PLANT feasibility checks
([scheduler.py:97,99,114](agent/scheduler.py#L97)) υπολογίζεται **πάντα από το
`snapshot.farmer_pos`**, αλλά το `assign()` δίνει το task σε όποιο unit είναι βέλτιστο συνολικά.
Δύο modes αποτυχίας: (α) hand μακρύτερα από τον farmer φυτεύει τόσο αργά που το same-day WATER
δεν προλαβαίνει → weed το ίδιο βράδυ (το `distance+2 <= turns_left` είναι ήδη zero-slack ακόμα
και για τον farmer)· (β) υπερ-συντηρητικά, task που φαίνεται ανέφικτο από τον farmer δεν
δημιουργείται καν ενώ ένα κοντινό hand θα το προλάβαινε. Το (α) μεγαλώνει με την ακτίνα του
farm — v1c amplifier. **Επίλυση:** είτε υπολόγισε τη feasibility στο `assign()` με την απόσταση
του υποψήφιου unit (φίλτρο υποψηφίων: `distance + action_turns <= deadline_step - step`), είτε
στο `build_tasks` με `min` απόσταση όλων των units — και βάλε ρητό slack margin (≥1-2 turns),
όχι ακριβώς οριακό.

---

## 3. Medium ευρήματα

### M1 — Liquidation DROP: inventory-blind, single-instance, starved [CONFIRMED-EXEC]

Αναπαράχθηκε: day 26, farmer με άδειο inventory στο (4,4), hand με 4 CARROT στο (2,2) →
farmer παίρνει το DROP (distance 0), κάνει αέναα silent no-op, hand κάνει PASS. Σήμερα το
σώζει το EOD auto-drop (engine :821-835) και η ζημιά περιορίζεται στο να πωλούνται τα harvests
με 1 μέρα καθυστέρηση και το day-29 harvest να μένει απούλητο — αλλά ο κώδικας **δεν κάνει αυτό
που ισχυρίζεται** και το v1e (intra-day DROP→SELL pipeline, G14) θα χτιστεί πάνω του.
**Επίλυση:** eligible για DROP μόνο units με μη κενό inventory (και προσοχή: inventory dict με
zero-count keys είναι truthy — καθάρισε με `sum(inv.values()) > 0`)· ένα DROP task **ανά
φορτωμένο unit** (π.χ. `id=f"drop:{unit_index}"` με πεδίο επιτρεπτού unit), όχι ένα καθολικό.
Το `(4,4)`-only είναι σωστό όσο τα άλλα shed tiles είναι LOCKED (tile-ops no-op σε LOCKED,
engine :323-325) — μετά το BUY_LAND γίνε position-aware.

### M2 — `resume` χωρίς ταυτότητα έκδοσης στο results.jsonl [CONFIRMED-READ]

Τα cached rows ([compare.py:119-144](harness/compare.py#L119-L144)) κρίνονται μόνο από το
`seed`. Σενάριο: τρέχεις compare στο ίδιο `run_dir`, αλλάζεις τον agent, ξανατρέχεις με
`--resume` → τα μισά seeds είναι από την παλιά έκδοση, το verdict είναι σαλάτα δύο εκδόσεων και
**φαίνεται** έγκυρο. **Επίλυση:** γράψε header row (ή πεδίο ανά row) με τα
`code_fingerprints`· στο resume, σύγκρινε με τα τρέχοντα και raise σε mismatch (με σαφές μήνυμα
"σβήσε το jsonl ή άλλαξε run_dir").

### M3 — NON_INFERIOR χωρίς στατιστική βάση σε εκφυλισμένα n/CI [CONFIRMED-READ]

Με n=1: `ci95=(mean,mean)` ([compare.py:213](harness/compare.py#L213)) και το
`ci95[0] >= -margin` ([:230](harness/compare.py#L230)) περνάει με ένα και μόνο seed. Με se=0 και
n>1 το ίδιο. Το gate protocol του plan.md δέχεται "αποδεδειγμένο NON_INFERIOR" ως GO — άρα
τυπικά ένα 1-seed run μπορεί να περάσει gate. (Συγγενές, [CONFIRMED-EXEC]: σταθερό **θετικό**
diff n=12 → verdict NON_INFERIOR αντί IMPROVED, επειδή το IMPROVED απαιτεί se>0 — συντηρητικό,
αποδεκτό, αλλά ας τεκμηριωθεί στο docstring.) **Επίλυση:** `NON_INFERIOR` μόνο όταν
`n >= <όριο, π.χ. 12>` **και** `se_diff > 0`· αλλιώς INCONCLUSIVE. Πρόσθεσε test.

### M4 — Λείπει το on-event replan του planner [CONFIRMED-READ]

Το plan.md §3.1: ο planner τρέχει "στο hour 0 **ή όταν observed state αποκλίνει από το plan**".
Υλοποιήθηκε μόνο το per-day ([policy.py:35-37](agent/policy.py#L35-L37)), και το `DayPlan`
χτίζεται από config σταθερές χωρίς καμία ανάγνωση board state. Για το v1b αδιάφορο· για το v1c
είναι **μέρος του acceptance** ("observed BUY_LAND success/failure προκαλεί σωστό replan").
**Επίλυση:** πριν το v1c retry, πρόσθεσε trigger conditions στο `agent()`: αλλαγή
`my_quadrants`, αποτυχημένη αναμενόμενη αγορά (receipt από H4), σημαντική απόκλιση
plant-count — recompute `DayPlan` intra-day.

### M5 — Seed over-procurement: νεκρό κεφάλαιο [CONFIRMED-READ]

Ο executor ([executor.py:49-60](agent/executor.py#L49-L60)) αγοράζει έως `seed_buffer=6` ανά
crop όσο `plant_targets > 0` — αλλά το `plant_targets` είναι η config σταθερά (18), όχι τα
απομένοντα άφυτα tiles. Όταν και τα 18 strawberry tiles φυτευτούν πριν το day-5 όριο, τυχόν
αποθεματικό σπόρων (έως 6 × $100) μένει για πάντα αχρησιμοποίητο — σπόροι δεν πωλούνται.
**Επίλυση:** `seeds_to_buy = min(seed_buffer, remaining_unplanted_targets + in_flight) -
seed_count`, όπου remaining υπολογίζεται από το snapshot (κενά target tiles με target_index <
plant_limit).

### M6 — Ανέφικτα PLANT walks / πλεόνασμα PLANT tasks [CONFIRMED-EXEC]

Με 1 σπόρο και 2 άδεια targets: farmer φυτεύει, hand στέλνεται να περπατά προς task που θα
εξαφανιστεί στο επόμενο build (seeds=0). Το φίλτρο του `assign()`
([scheduler.py:176-181](agent/scheduler.py#L176-L181)) ελέγχει `seeds_remaining` **μόνο όταν
`unit_pos == task.pos`**. Σπατάλη κινήσεων — σε φάσεις στενότητας σπόρων, συστηματική.
**Επίλυση:** δέσμευε το seed budget και για αναθέσεις κίνησης (decrement όταν το task
ανατίθεται, όχι όταν εκτελείται)· και κόψε τα δημιουργούμενα PLANT tasks σε
`min(#eligible tiles, seeds διαθέσιμα, remaining plant budget)` ήδη στο `build_tasks`.

### M7 — `raise AssertionError` σε production path [CONFIRMED-READ]

Το postcondition του executor ([executor.py:72-74](agent/executor.py#L72-L74)) σκάει το agent
αν ποτέ ξεπεραστεί το cap. Σήμερα unreachable (2 SELL + 2 BUY_SEED + 3 HIRE = 7 max), αλλά ένα
raise στον server = ERROR = χαμένο episode — ενώ ένα truncation στα 10 θα ήταν ακίνδυνο. Το
fail-fast ανήκει στα tests, όχι στο submission runtime. **Επίλυση:** `orders = orders[:max]` +
debug receipt (H4) όταν κόβει· κράτα το αυστηρό assert ως pytest guard (G7 test υπάρχει ήδη).

### M8 — Metrics false positives για v1d [CONFIRMED-READ]

(α) `animals_escaped` ([metrics.py:236-242](harness/metrics.py#L236-L242)): PICKUP τοποθετημένου
ζώου αφήνει tile με ίδιο kind χωρίς "animal" → θα μετρηθεί escape. (β) decay counter
([:220-235](harness/metrics.py#L220-L235)): HARVEST σε step ≥ mls με `(step-mls)%2==0` μηδενίζει
το yield και θα καταγραφεί ως decay loss. Σήμερα αθέατα (δεν υπάρχουν ζώα· τα harvests γίνονται
προ-mls), αλλά τα G5/G8 acceptance του v1d θα μετρούν λάθος. **Επίλυση:** στο
`_transition_events` τα actions είναι ήδη διαθέσιμα — εξαίρεσε pos όπου το transition περιέχει
PICKUP/HARVEST από τον ίδιο seat.

---

## 4. Low ευρήματα

- **L1** [metrics.py:154-157] Το `_transition_events` κάνει mutate το `env_json` του καλούντος
  (προσθέτει `"_day"` στο action dict του replay). Πέρνα το day ως όρισμα.
- **L2** [metrics.py:98-142] Το `_simulate_market` δεν έχει το 100k escape hatch του engine
  (:562-566) — παθολογικό replay μπορεί θεωρητικά να κολλήσει τα metrics σε άπειρο loop.
- **L3** [executor.py:8-12] Το `_hire_cost` είναι χειρόγραφο αντίγραφο του engine `_fib` χωρίς
  parity test (τα υπόλοιπα vendored έχουν). Πρόσθεσέ το στο vendored parity test.
- **L4** [checkpoint.py:67] Το `copytree` αντιγράφει και `__pycache__/` μέσα στα checkpoints
  (το fingerprint σωστά τα αγνοεί — μόνο θόρυβος). `ignore=shutil.ignore_patterns("__pycache__")`.
- **L5** [checkpoint.py:27-43] Το fingerprint ενός main.py spec χασάρει ΜΟΝΟ το package — όχι το
  ίδιο το main.py (π.χ. extra code μετά το import, το ακριβές C2 hazard) ούτε non-`.py` αρχεία
  του package. Συμπερίλαβε το main.py source στο digest.
- **L6** [config.py:44-47, planner.py:27] Το `endgame.enabled=False` είναι νεκρό — το
  liquidation ενεργοποιείται από το `liquidation_day` άνευ όρων. Τίμησε το flag ή αφαίρεσέ το
  πριν μπερδέψει το v1e tuning.
- **L7** [scheduler.py:64-69] Καρότο με `age > 3` (αθέριστο) συνεχίζει να ποτίζεται λόγω
  `age >= 2` ενώ είναι εκτός yield window (engine window: ηλικίες 2-3) — σπάνιο, λίγα χαμένα
  unit-turns.
- **L8** [scheduler.py:137, :16] Το `tasks[:max_tasks]` κόβει με σειρά κατασκευής (CARROT πρώτα),
  όχι priority — footgun αν ποτέ πιαστεί το 400· και το `deadline_step=719` default του Task
  είναι hardcoded αντί από `config["runtime"]["episode_steps"]-1`.
- **L9** [test_agent_guards.py:78-88] Το vendored parity test ΔΕΝ καλύπτει το
  `TOWN_CENTER_DEMAND_SCHEDULE` (επιβεβαιώθηκε ίσο με το engine σήμερα — αλλά χωρίς test το
  version-bump detector του §2.2 έχει τυφλό σημείο εκεί).
- **L10** [checkpoint/compare] Εντός ίδιου process, ήδη-imported checkpoint package
  (`sys.modules`) μπορεί να αποκλίνει από ό,τι fingerprint-άρεται στον δίσκο (βλ. H3).

---

## 5. Pre-v1c-retry Checks

Με σειρά προτεραιότητας — τα 1-5 είναι **μπλόκερ** για το retry, τα 6-9 ισχυρά συνιστώμενα:

1. **[C1.1+H5]** Slack στο assignment sort key + per-unit deadline feasibility φίλτρο με ρητό
   margin ≥1-2 turns. Χωρίς αυτό, κάθε "capacity variant" ξαναχάνει τα μακρινά WATER.
2. **[C1.2]** Planner capacity gate: μην αυξάνεις plant targets και μην αγοράζεις NE αν
   `watering demand (με commute από shed spawn) > 0.8 × supply`. Ο planner πρέπει να διαβάζει
   board state (λύνει μαζί και M5).
3. **[H1]** Same-turn plant budget στο `assign()` — αλλιώς το capacity gate του (2) υπονομεύεται
   από την ίδια τη μηχανή εκτέλεσης.
4. **[H4]** Minimum G11 receipts (WATER/PLANT/HARVEST expected transitions + reconciliation),
   ώστε αν το retry ξαναχάσει φυτά, να υπάρχει ονομαστική λίστα «ποιο tile, ποιο step, τι
   περίμενες, τι έγινε» αντί για νέο guessing game.
5. **[Gate hygiene]** Στο smoke gate του v1c retry, πρόσθεσε **ρητό κριτήριο
   `water_weeds_lost == 0` και `plant_decay_units_lost == 0`** (τα metrics υπάρχουν ήδη στο
   metrics.py) — όχι μόνο σύγκριση $. Το $-gate είδε το σύμπτωμα 3 φορές· το metric-gate δείχνει
   το αίτιο στο 1ο run.
6. **[M4]** On-event replan για BUY_LAND success/failure — είναι μέρος του v1c acceptance όπως
   ήδη γράφεται στο plan.md §3.3.
7. **[H2+H3]** Πριν γραφτεί οτιδήποτε νέο: commit τα 4 checkpoints σε μη-gitignored path και
   manifest-verification στο load — το retry θα κάνει gate ενάντια στο v1b· βεβαιώσου ότι αυτό
   το v1b είναι αποδεδειγμένα το αποδεκτό.
8. **[M2]** Fingerprints στο results.jsonl πριν τρέξουν τα (πολλά) v1c retry benches με resume.
9. **[Σχεδιαστικές σταθερές για το redesign]** — engine facts που πρέπει να σεβαστεί το νέο
   routing: units μπορούν να συνυπάρχουν σε tile (ΜΗΝ χτιστεί collision avoidance)· hands
   διαγράφονται κάθε EOD και ξαναγεννιούνται στο shed → το commute είναι ημερήσιο, όχι εφάπαξ
   κόστος· DROP no-op σε LOCKED shed tiles μέχρι να αγοραστούν quadrants· WATER δίνει +1 yield
   σε καρότα ηλικίας 2-3 (το υπάρχον "water πριν το harvest" είναι σωστό — να διατηρηθεί).

---

## 6. Self-check — δεύτερο pass πάνω στα ίδια τα ευρήματα

**Υποψίες που ΑΠΟΡΡΙΦΘΗΚΑΝ ως false positives κατά τον επανέλεγχο (μην ξαναψαχτούν):**

- *«Movement collision/deadlock μεταξύ units»* — ΛΑΘΟΣ: το engine MOVE δεν έχει occupancy
  check (:309-317), units στοιβάζονται ελεύθερα. Αφαιρέθηκε από τα αίτια του v1c (§1.6).
- *«Το πότισμα καρότου πριν το harvest (test_g9) είναι σπατάλη»* — ΛΑΘΟΣ: το WATER σε
  non-ongoing crop ηλικίας [(max_yield_day+1)//2, max_yield_day] προσθέτει +1 yield
  (engine :380-388). Η συμπεριφορά είναι σωστή και κερδοφόρα.
- *«Το extract_metrics είναι performance bottleneck»* — ΛΑΘΟΣ: μετρήθηκε 0.5s/720-step episode
  (και τα δύο seats μαζί)· το compare() ήδη περνά `metrics=False`.
- *«Το `_simulate_market` αποκλίνει από το engine lockstep»* — ΔΕΝ επιβεβαιώθηκε απόκλιση:
  side-by-side σύγκριση με το `_process_market` (:521-605) έδειξε πιστή αναπαραγωγή (quotes
  και για τους δύο πριν τα commits, `_refresh_prices` ανά index, BUY_PRODUCT στο inventory−1,
  malformed abort). Μένει το L2 (escape hatch) μόνο.
- *«Το REGRESSED χρειάζεται και mean-check»* — η επιπλέον συνθήκη `mean_diff < -margin` στο
  compare.py είναι μαθηματικά πλεονάζουσα (mean < ci_upper πάντα), όχι λάθος.

**Επαληθεύτηκε καθαρό (δεν χρειάζεται νέο review):** t-table τιμές/παρεμβολή· paired-CI
ορθότητα· median από raw orientations (συμβατό με τα acceptance gates)· INCOMPLETE σε per-seed
errors· jsonl truncation όταν δεν γίνεται resume· `_VERSION_RE` fullmatch μπλοκάρει `..`/`/`/`\`
(path traversal στο checkpoint.py — ΟΚ)· sanitized replay filenames· G13 runtime reset σωστό σε
mirror, sequential episodes και εναλλαγή orientations (το `step==0` reset καλύπτει stale
contexts)· atomic-PLANT seed reservation σωστό για units πάνω στο tile τους· executor order
budget αριθμητικά ορθό (max 7 ≤ 10)· fingerprint agent/ ↔ v1b manifest ταυτίζεται· 80/80 tests.

**Όρια της ανάλυσης (δηλωμένα):** ο v1c κώδικας δεν υπάρχει στο repo (σωστά revert-αρισμένος),
άρα το §1 αποδίδει το αίτιο μέσω των δομικών ιδιοτήτων του v1b scheduler που θα εκτελούσε το
v1c workload — τα δομικά κενά είναι CONFIRMED, η ακριβής σύνθεση των 5-9 losses ανά variant
είναι [PLAUSIBLE]. Το oscillation (§1.5) επίσης [PLAUSIBLE] — αν χρειαστεί απόδειξη, τα G11
receipts του Pre-check #4 θα τη δώσουν δωρεάν στο πρώτο retry run.
