# S11 — Ολοκλήρωση του οργάνου (B1-B4)

> **Τύπος:** brief υλοποίησης. Αυτοτελές — μην υποθέσεις τίποτα από προηγούμενη συνομιλία.
> **Γράφτηκε:** 2026-08-25. **Αναθεωρήθηκε 2026-08-27** — τα ολοκληρωμένα tasks (B3, B1, B2.0′)
> αντικαταστάθηκαν από τη σύνοψη της §1. Ανοιχτά μένουν **μόνο** τα B2.1-B2.5 και το B4.
> **Καμία αλλαγή σε `agent/`. Καμία υποβολή.** Το B2 είναι **μόνο μέτρηση**.

## Διάβασε πρώτα

`docs/plans/s10_instrument_rebuild.md` (§P4, §P1.6 — αυτά συμπληρώνει ό,τι μένει).
Memory: `price-floor-liquidation-sink`, `s9-live-read-55726984`,
`roadmap-is-the-plan-not-the-diary`.
`ROADMAP.md` §8 (ο πάγκος), §9 (προθεσμία).

---

## 1. Τι έχει ολοκληρωθεί (μην το ξαναδουλέψεις)

**B3 ✅ `a0c43d1` — fixtures αναπαραγωγής στο CI.** `tests/fixtures/replays.py` παράγει
*αληθινό* επεισόδιο μέσα από το engine στη μορφή που διαβάζει το `s8_replay_io.meta()`
(+ gzip)· `tests/conftest.py` το σερβίρει ως session-scoped corpus με monkeypatch στα
`SUBMISSIONS`/`_EXTRA_DIRS`. Τα replay tests έγιναν δύο στρώματα (στρώμα 1 παντού με
παραμετρικά κατώφλια, στρώμα 2 skipped στο clean clone). Το
`tests/test_s10_bench_alpha_synthetic.py` φυλάει το bit-exact `_alpha_one`. Suite: **415 passed**.

**B1 ✅ `1e90b75` — rating-zone join.** Η μηχανική μετακινήθηκε (δεν ξαναγράφτηκε) από το
`s7_ladder_census.leg_c` στο νέο `analysis/board_join.py` (`board_at`, `rating_zone`,
`episode_times`, `_load_lb`, `_closest_board`)· το `s7_ladder_census` κάνει import από εκεί.
Έκλεισαν πρώτα δύο κενά δεδομένων: και τα **5** snapshots στο `LB_SNAPSHOTS` (ήταν 2) και το
episodes CSV του `55675634` (κατέβηκε, κανονικοποιήθηκε στο `data/archive/raw/`). Το
`build_manifest` γεμίζει και τα πέντε πεδία, το `report_h2` απέκτησε `by_rating_zone` +
`by_rating_zone_controlled` με ρητή γραμμή `unmatched`. Αποδοχή: **379/509 matched = 74,5%**
(όριο 70%), `c=23 b=0` **αναλλοίωτο**.

**B2.0′ ✅ 2026-08-27 — ο spike πέρασε και τις τρεις πύλες.**
`analysis/s10_opponent_inventory.py::spike_per_step` / `spike_validate`, 20 ladder replays του
`55726984` → `data/derived/s10_opponent_spike.json`:

```
B2.0' spike PASS: exact_rate=0,982 (≥0,90), signal_coverage=0,571 (≥0,50),
                  bracket_coverage=0,967 (≥0,80)
14.380 βήματα: EXACT_ZERO 10.468 · MOD10 1.285 · AMBIGUOUS_WF 2.248 · EXACT 379
```

Τι χρειάστηκε για να περάσει (κρατημένο εδώ γιατί είναι μη-προφανές):
- **W/F detection μόνο σε `net_opp < 0`.** Το `net_opp = ΔM_p + consume_p − δικές_μας_nonfloor_p
  + δικές_μας_αγορές_p`. `net_opp > 0` σημαίνει ότι ο αντίπαλος **πούλησε** W/F, όχι ότι αγόρασε —
  σημαδεύοντας κάθε μη-μηδενικό `net_opp` ως `AMBIGUOUS_WF` η κάλυψη σήματος έμενε 0,29. Με
  `net_opp < 0` μόνο: 0,571. (81% των πραγματικών αγορών του αντιπάλου δίνουν `net_opp < 0`.)
- **Οι δικές μας `BUY_PRODUCT` W/F πρέπει να μπουν στο `net_opp`.** Χωρίς αυτές, ο δικός μας bot
  σκάλωνε ψευδώς το `AMBIGUOUS_WF` στο 20% των βημάτων.
- **NB έσοδα = `total_walk − δικές_μας_τιμές`, όχι walk πάνω στο `opp_nf`.** Για τα επτά
  NON_BUYABLE δεν γίνονται αγορές, άρα το *σύνολο* των τιμών είναι ντετερμινιστικό ανεξάρτητα από
  τη σειρά interleaving· το walk μόνο στο σκέλος του αντιπάλου υπέθετε σιωπηλά ότι πουλά πρώτος.

Οι επτά διορθώσεις της παλιάς §B2.−0.5 έχουν εφαρμοστεί: `hire` ακριβές από `len(hands)`, καμία
`max(0,…)` επισκευή, κανένα σημειακό πάνω σε πλατύ bracket, η `_our_committed_nb_sells` σβήστηκε
υπέρ του `_transition_events`.

**Ό,τι είναι πια κλειστό ερώτημα:** το **αθροιστικό ανά επεισόδιο** σύνολο floor units είναι
**μη-ταυτοποιήσιμο** και αποσύρθηκε ως λάθος ερώτημα (το ζητούμενο είναι $116 διάμεσος πάνω σε
ισοζύγιο $55.896, με τρεις μη-παρατηρήσιμους όρους $6-12k ο καθένας). **Μην το ξαναδοκιμάσεις.**
Όλα τα μεγέθη από δω και πέρα είναι **ανά βήμα ή ανά παράθυρο 24 γύρων**.

**Μετρημένη δομή του σήματος** (7.190 βήματα — δεδομένο εισόδου, μην το ξαναμετρήσεις): floor
πωλήσεις σε 242/7.190 βήματα (3,4%), και 49 βήματα με ≥10 μονάδες κρατούν το 57% όλων των floor
units. Και οι δύο πλευρές πουλάνε το ίδιο προϊόν στο ίδιο βήμα σε 4,6% των βημάτων.

---

## 2. Τι μένει

```
B2.1 → B2.2(γ) → B2.3 → B2.4 → B2.5 (κριτήριο θανάτου)  ──►  B4 μόνο αν περισσέψει χρόνος
```

🔴 **Checkpoint 2026-09-05.** Αν τα B2.1-B2.5 δεν έχουν κλείσει ως τότε, **σταμάτα το S11 όπου
είναι** και πήγαινε στο S12 — θέλει 5-7 μέρες (screen → confirm → gate → upload) και μία μέρα
περιθώριο πριν το cutoff ~09-23 (ROADMAP §9).

---

## B2.1 — Shed tracker: ο στενωτής του `MOD10`

**Σκοπός.** Το `MOD10` δίνει `floor_units(t) ∈ {R mod 10, +10, +20, …}` μέχρι το `shed_cap=100`.
Ένα άνω φράγμα στο απόθεμα του αντιπάλου ανά προϊόν κόβει τους περισσότερους κλάδους. Αυτό
**μόνο** είναι ο ρόλος του B2.1 — δεν είναι πρόβλεψη συγκομιδής.

**Το αρχικό shed είναι μηδέν** για κάθε προϊόν (επαληθευμένο). Άρα τρέχεις σωρευτικά από το 0:

```
shed_ub[p](t) = min(shed_cap, max(0, cum_harvest[p] + cum_bought[p] − cum_sold[p] − cum_consumed[p]))
```

**Εισροή — από τα δημόσια πλακίδια του αντιπάλου** (`obs["farms"][opp]["tiles"]`):
- `HARVEST` σε `kind == "PLANT"`: το `yield_units` πέφτει στο 0 και οι μονάδες πάνε στο
  `inventories`. Το προϊόν είναι το `tile["crop"]`.
- Ζώα: **δύο** kinds — `PASTURE` (COW→MILK, SHEEP→WOOL) **και** `COOP` (GOOSE→EGG). Προϊόν από
  `ANIMALS[tile["animal"]]["product"]`.
- 🔴 **Ξεχώρισε τη συγκομιδή από τη φθορά.** Και οι δύο μειώνουν το `yield_units`, αλλά το
  `_decay_plants` τρέχει **μετά** τις unit actions και μόνο όταν
  `step >= tile["max_lifespan_step"] and (step − mls) % 2 == 0`, και αφαιρεί **1**. Η συγκομιδή
  μηδενίζει. Έλεγξε τη συνθήκη decay πριν αποδώσεις μείωση σε συγκομιδή.
- `COLLECT_FERTILIZER`: παρατηρήσιμο ως `fertilizer_available` true→false ⇒ +1 FERTILIZER.

**Εκροή:**
- πωλήσεις: το B2.2(α) δίνει τις non-floor μονάδες ανά προϊόν ακριβώς· οι floor μονάδες από το
  B2.2(γ)·
- `FEED`: `fed_today` false→true ⇒ −1 WHEAT· `FERTILIZE`: αλλαγή `fertilized_until_day` ⇒
  −1 FERTILIZER·
- **end-of-day**: το `_drop_inventories_to_shed` πετάει την υπερχείλιση πάνω από `shed_cap=100`
  (σύνολο shed, όχι ανά προϊόν). Αυτό είναι το `L` του B2.3.

🔴 **Κάλεσε τους κανόνες του engine, μην τους ξαναγράψεις** — `_daily_refresh_plants`,
`_daily_refresh_animals`, `_decay_plants`, `_drop_inventories_to_shed` στο
`engine_reference/kaggriculture.py`. Το off-by-one του S10 P4 ήρθε από αντιγραφή του
`_town_consume`.

**Σειρά εκτέλεσης βήματος** (μην την υποθέσεις αλλιώς): unit actions → market → town consume →
`_decay_plants` → `_end_of_day` όταν `(step+1) % turns_per_day == 0`.

**Αποδοχή B2.1:** το `shed_ub` είναι **πάντα ≥** το πραγματικό `_private_total(private, p)` στα
≥20 replays (είναι άνω φράγμα — μία παραβίαση σημαίνει bug), και το διάμεσο πλάτος του `MOD10`
bracket μικραίνει μετρήσιμα σε σχέση με το `shed_cap`. Ανέφερε και τα δύο νούμερα.

---

## B2.2 — Εκροή

*(α) Non-floor μονάδες ανά προϊόν — ήδη ταυτοποιήσιμες, βγάλ' τες στο output.* Το ΔM δίνει ανά
προϊόν `opp_sell_nonfloor − opp_buy`. Το engine δέχεται `BUY_PRODUCT` **μόνο** για
`("WHEAT", "FERTILIZER")`, άρα για τα άλλα **επτά** (MELON, STRAWBERRY, MILK, WOOL, EGG, CARROT,
TOMATO) ισχύει `opp_buy ≡ 0` και το `opp_sell_nonfloor` **ταυτοποιείται ακριβώς σε μονάδες**.
Για WHEAT/FERTILIZER κράτα μόνο το net και δήλωσέ το ως net. Ο υπολογισμός υπάρχει ήδη μέσα στο
`spike_per_step`· το ζητούμενο εδώ είναι να **εκτεθεί ως πεδίο ανά προϊόν**, όχι να ξαναγραφτεί.
🔴 Όριο: ακριβές στις **μονάδες**. Το *έσοδο σε $* είναι ακριβές μόνο όταν εμείς δεν πουλήσαμε το
ίδιο προϊόν στο ίδιο βήμα (95,4% των βημάτων).

*(β) Floor σύνολο ανά βήμα.* ✅ **Έγινε στο B2.0′** — `spike_per_step`. Μην το ξαναγράψεις.

*(γ) Απόδοση των floor units ανά προϊόν, από τη δημόσια τιμή.* Το (β) δίνει σύνολο, όχι ανάλυση.
Σε κάθε βήμα διάβασε το `obs["market"]["prices"]` και όρισε `C(t) = {i : price_i == 1}` — τα
**μόνα** προϊόντα που μπορούν να πουλήθηκαν στο floor εκείνη τη στιγμή.
- `|C(t)| == 1` ⇒ η απόδοση είναι ακριβής·
- `|C(t)| > 1` ⇒ κατάνειμε αναλογικά **και** πέρασε το πλήρες εύρος `[0, R(t)]` στο
  `uncertainty_width` κάθε υποψήφιου προϊόντος·
- `|C(t)| == 0` και `R(t) != 0` ⇒ **σφάλμα ταυτότητας**. Κατέγραψέ το ως residual· μην το
  στρογγυλοποιήσεις και μην το κόψεις στο 0.

---

## B2.3 — Πεδία output (ανά προϊόν, ανά βήμα)

`opponent_total` (σημειακή), `lower_bound`, `upper_bound`, `uncertainty_width`, `floor_risk`,
`private_loss_risk`, `classification` (η τετράδα του B2.0′).

- `private_loss_risk` = το `L`: το κάψιμο υπερχείλισης του `_drop_inventories_to_shed` στο
  `_end_of_day` με `shed_cap=100`. **Φράξιμο, όχι εικασία** — ο αντίπαλος δεν μπορεί να έχει
  χάσει μονάδες αν το `shed_ub` του B2.1 δεν πλησίασε το 100.
- 🔴 Η μορφή `opponent_total_i = S_i − own_total_i` του S10 P4.1 **δεν είναι υλοποιήσιμη** —
  προϋποθέτει παρατηρήσιμο συνολικό `S_i` που δεν υπάρχει. Η διαδρομή είναι η λογιστική
  εισροής/εκροής των B2.1+B2.2.
- 🔴 Μη δώσεις σημειακό `opponent_total` πάνω σε πλατύ bracket. Είτε δώσ' του δικό του estimator,
  είτε άφησέ το `None` και άσε τα φράγματα να μιλήσουν.

---

## B2.4 — Επικύρωση σε ground truth

Ground truth: `private.shed` + `private.inventories` του seat του αντιπάλου, μέσω του υπάρχοντος
`_private_total`. **≥20 replays.** Το ground truth ζει σε **ξεχωριστή** συνάρτηση που δεν
μοιράζεται είσοδο με τον εκτιμητή.

Ανέφερε: **MAE ανά προϊόν**, **% βημάτων μη-identifiable** (όπου το `uncertainty_width` ξεπερνά
κατώφλι που **δηλώνεις εκ των προτέρων** στο output), και **coverage** (η αλήθεια μέσα στο
`[lower, upper]`).

🔴 Όλα **ανά βήμα ή ανά παράθυρο 24 γύρων** — ποτέ αθροιστικά ανά επεισόδιο.
🔴 Το `per_step_estimates` ήδη παράγει `opp_true_private_total` και το πετάει· η `validate()` δεν
το καταναλώνει ποτέ. **Σύνδεσέ το.**

**Θάνατος B2 (χωριστό από το B2.5):** `coverage` των bracketed βημάτων **< 0,80** ⇒ ο εκτιμητής
είναι **λάθος**, όχι απλώς αδύναμος. **STOP και ρώτα.** Μην πλατύνεις τα φράγματα για να περάσει.

---

## B2.5 — Κριτήριο θανάτου: dump predictor χωρίς διαρροή

**Ορισμός γεγονότος** (ίδιος με S10 P4.3 ώστε να συγκρίνεται): ο αντίπαλος πουλά **≥20 μονάδες**
ενός premium προϊόντος μέσα στους **επόμενους 24 γύρους**.

🔴 **Γράψε το leakage test ΠΡΩΤΑ, πριν τον predictor.** Τρέξε τον predictor σε replay όπου τα
`steps[t][1-seat]["action"]` έχουν αντικατασταθεί με `PASS` — οι προβλέψεις πρέπει να είναι
**bit-identical**. Αν αλλάξουν, διαρρέει προνομιακή πληροφορία. Το ίδιο test φυλάει και το
Βήμα 1 του B2.0′: αν οι δικές μας committed πωλήσεις περνούν κρυφά από διπλή-θέση προσομοίωση,
το PASS-replay θα τις αλλάξει και το test θα κοκκινίσει.

**Η λεπτή διάκριση.** Το `cum_opp_sell_nonfloor` **δεν** απαγορεύεται ως *ποσότητα* — το B2.2(α)
δείχνει ότι ταυτοποιείται ακριβώς από το δημόσιο ΔM. Απαγορεύεται ο **τρόπος** που το υπολόγισε
το S10: ανάγνωση του `steps[t][opp]["action"]`.

**Επιβολή:** η συνάρτηση πρόβλεψης παίρνει **μόνο** `obs` (η οπτική ενός seat) και **καμία**
πρόσβαση στο `steps`. Το ground truth περνά σε **ξεχωριστή** συνάρτηση βαθμολόγησης.

- **Αποδοχή:** precision **≥0,70 και για MELON και για STRAWBERRY** → η ιδέα ζει, ο σχεδιασμός
  πολιτικής πάει στο S12.
- **Θάνατος:** <0,70 σε οποιοδήποτε από τα δύο → η ιδέα πεθαίνει **οριστικά**, γράφεται ως τελική
  με τα MAE/coverage δίπλα ώστε να φαίνεται *γιατί*. Δεν ξανανοίγει χωρίς νέο μηχανισμό.

🟢 Το κριτήριο αφορά κυρίως *non-floor* premium πωλήσεις, που το B2.2(α) ήδη ταυτοποιεί ακριβώς.
Το floor κανάλι **δεν** είναι προϋπόθεση. **Πες ρητά στο `verdict` ποια διαδρομή έτρεξες.**

**Αποδοχή B2 συνολικά:** τα πεδία του B2.3 υπάρχουν στο output· exact-rate / identifiability /
coverage αναφέρονται **ανά βήμα**· το `verdict` λέει ποια διαδρομή ισχύει· ≥20 replays.

---

## B4 — Mirror arm (P1.6 του S10) — χαμηλή προτεραιότητα

**Δεν είναι έλεγχος πιστότητας.** Οι ταινίες είναι **δεμένες με τη θέση**: το `stream[0]` δείχνει
στα πλακίδια, τις θέσεις και το χρήμα του seat 0. Δοσμένο στο seat 1, αποσυγχρονίζεται αμέσως.
Το bit-exact κριτήριο του P1.2 **δεν ισχύει εδώ**.

**Το ερώτημα απαντήθηκε ήδη.** Το μόνο που θα μετρούσε το B4 — αν το πρόσημο του H2 οφείλεται στη
θέση — το δίνει το υπάρχον `by_seat`: seat 0 `c=10, b=0`· seat 1 `c=13, b=0`. Ίδιο πρόσημο,
συγκρίσιμο μέγεθος, και στις δύο θέσεις.

**Απόφαση.** Γράψε κώδικα **μόνο** αν τα B2.1-B2.5 έχουν κλείσει **και** μένουν ≥5 μέρες πριν το
cutoff. Αλλιώς: μία παράγραφος στο `ROADMAP.md §8` ότι το P1.6 καλύπτεται από το `by_seat` και
κλείνει — **και τίποτε άλλο**. Αυτό είναι νόμιμο αποτέλεσμα, όχι παράλειψη.

---

## Παραδοτέα (ανοιχτά)

| task | αρχεία |
|---|---|
| B2.1-B2.5 | `analysis/s10_opponent_inventory.py`, `data/derived/s10_opponent_inventory.json`, νέο test διαρροής (PASS-replay, bit-identical), ενημέρωση `ROADMAP.md §10` |
| B2 (αν χτυπήσει κριτήριο θανάτου) | μία καταχώρηση στο `ROADMAP.md §6` με MAE/coverage δίπλα, και **τίποτε άλλο** |
| B4 | είτε `analysis/s10_replay_bench.py` (mirror arm) είτε **μόνο** μία παράγραφος στο `ROADMAP.md §8` |

Παραδομένα: B3 → `a0c43d1`, B1 → `1e90b75`, B2.0′ → `data/derived/s10_opponent_spike.json` (§1).

## Πάγιοι κανόνες για όλο το πάσο

1. **Καμία αλλαγή σε `agent/`. Καμία υποβολή.** Το upload ανήκει στο S12.
2. Παράγωγα σε `data/derived/` (gitignored)· raw σε `data/archive/raw/` (gitignored).
3. Μη ρυθμίσεις παράμετρο ή κατώφλι για να περάσει πύλη. Χτύπησε κριτήριο θανάτου → **STOP και ρώτα**.
4. Μία υλοποίηση ανά έννοια. Μην αφήσεις δεύτερο board join, δεύτερο parser τιμών, ή δεύτερο
   αντίγραφο κανόνα του engine. Όπου χρειάζεσαι κανόνα του engine, **κάλεσέ τον** — το off-by-one
   του S10 P4 προήλθε από αντιγραφή του `_town_consume`.
5. Κάθε παράγωγο JSON φέρει `verdict` string, ημερομηνία παραγωγής, και — αν προέρχεται από τον
   πάγκο — το πεδίο `constraint` του P1.5.
6. Κάθε διόρθωση συνοδεύεται από test που **κοκκινίζει στον προ-διόρθωσης κώδικα**. Επαλήθευσέ το
   γυρίζοντας πίσω τη διόρθωση, μην το υποθέσεις.
7. **Μην αλλάξεις** το `harness/seeds.py::NAMED_SEED_SETS` και μην περάσεις ζωντανά seeds ως
   `--seed-set` (S10 P1.7 — παραμένει σε ισχύ).

## Επαληθευμένα σύμβολα (έλεγχος 2026-08-27 — μη τα ξαναμαντέψεις)

`_daily_refresh_plants`, `_daily_refresh_animals`, `_decay_plants`, `_drop_inventories_to_shed`
(«overflow is discarded», cap 100), `_hire_cost`, `_town_consume`, `_commit_unit`,
`ANIMALS[*]["cost"|"product"|"first_yield_day"|"interval"|"max_held"|"structure"]`,
`CROPS[*]["seed"|"ongoing"|"max_yield"|"interval"|"first_yield_day"]`,
tile kinds `PLANT|WEED|PASTURE|COOP`, `BUY_PRODUCT ∈ {WHEAT, FERTILIZER}`.
`harness/metrics.py::_transition_events(prev_step, cur_step, cfg)` → 7-tuple· το
`[2][seat]` είναι οι committed πωλήσεις με τιμές.
Δημόσια πεδία farm: `farmer`, `hands`, `hires_today`, `money`, `tiles`, `unlocked_quadrants`.
Δημόσια market: `obs["market"]["inventory"]`, `obs["market"]["prices"]`.
Ιδιωτικά: `private.{shed, inventories, seeds}` — **ground truth μόνο, ποτέ είσοδος εκτιμητή**.
Tile πεδία: PLANT `crop|yield_units|planted_day|max_lifespan_step|fertilized_until_day|
watered_today|consecutive_unwatered`· ζώο `animal|yield_units|placed_day|fed_today|cared_today|
fertilizer_available|consecutive_unfed`.
