# competition_updates.md — ημερολόγιο εισερχόμενης πληροφορίας

> **APPEND-ONLY.** Εδώ προσγειώνεται **κάθε** νέα πληροφορία από τη σελίδα του διαγωνισμού:
> ανακοινώσεις οργανωτών, απαντήσεις σε απορίες χρηστών, διορθώσεις κανόνων, engine bumps,
> αλλαγές leaderboard, οτιδήποτε. **Νεότερο πρώτα.** Ποτέ δεν διαγράφουμε εγγραφή — αν κάτι
> αποδειχθεί λάθος, γράφεται **νέα** εγγραφή που το ανασκευάζει.
>
> **Ο κύκλος ζωής μιας εγγραφής:**
> 1. Καταγράφεται εδώ ως raw, με ημερομηνία και πηγή.
> 2. Αν αλλάζει **κανόνα** → προωθείται στο [reference/engine_deltas.md](docs/reference/engine_deltas.md) με status `⚠️ UNVERIFIED`, και ιδανικά γράφεται test στο [tests/test_engine_facts.py](tests/test_engine_facts.py) που το κάνει `✅ TESTED`.
> 3. Αν αλλάζει **αριθμό απόδοσης** → [reference/economics.md](docs/reference/economics.md) ή [reference/market.md](docs/reference/market.md).
> 4. Αν αλλάζει **meta/ladder** → νέα εγγραφή στο [meta/ladder_snapshots.md](docs/meta/ladder_snapshots.md).
> 5. Αν αλλάζει **στρατηγική προτεραιότητα** → συζήτηση για MASTERPLAN/plan.md, **όχι** σιωπηλή αλλαγή.
>
> Το πεδίο `Ενέργεια` κάθε εγγραφής λέει σε ποιο βήμα βρίσκεται. Εγγραφή με `Ενέργεια: εκκρεμεί`
> είναι ανοιχτή δουλειά.

## Σχήμα εγγραφής

```markdown
### YYYY-MM-DD — <τίτλος σε μία γραμμή>

**Πηγή:** forum thread / επίσημη ανακοίνωση / leaderboard / Kaggle CLI / δικό μας τεστ
**Τι λέει:** <verbatim ή πιστή περίληψη — ό,τι χρειάζεται για να μην ξαναδιαβαστεί η πηγή>
**Impact:** <τι αλλάζει πρακτικά για τον agent μας· "κανένα" είναι έγκυρη απάντηση>
**Ενέργεια:** <εκκρεμεί | προωθήθηκε σε <αρχείο> | test: <όνομα> | καμία (FYI)>
```

---

## Εγγραφές

### 2026-08-07 — ⚠️ ΑΝΑΚΟΙΝΩΜΕΝΕΣ balance changes: town center −79% ζήτηση· shops **με επανάθεση**

**Πηγή:** επίσημη ανακοίνωση οργανωτών, thread «Upcoming Balance Changes» (8 votes· αναφέρεται
ήδη στο live meta report της 08-06 ως *engine balance watch*).

**Τι λέει (verbatim σημεία):**
1. «we're reducing the overall demand for products from the town» — το town center γίνεται
   **flat ×1 για όλη τη σεζόν** (αφαιρείται το `TOWN_CENTER_DEMAND_SCHEDULE` ramp ×2 από μέρα 10 /
   ×4 από μέρα 20) **και** `townCenterSellInterval` **12 → 24**, δηλαδή **1 tick/μέρα** αντί για 2.
   Το *μενού* του town center (όλα τα PRODUCTS πλην FERTILIZER) μένει αμετάβλητο.
2. «shops will now be sampled WITH replacement» — το `_end_of_day` δεν φιλτράρει πια τα ήδη
   ξεκλειδωμένα shops· ίδιο shop μπορεί να ξεκλειδώσει πολλές φορές και **κάθε instance
   καταναλώνει ανεξάρτητα** (π.χ. 3× FARMERS_MARKET και **κανένα** YARN_STORE). Νέα σταθερά
   `MAX_SHOP_INSTANCES = 8` (εκεί ήταν de facto και το παλιό ταβάνι «1 από κάθε ένα από τα 8»).
   Schedule ξεκλειδώματος (κάθε 3 μέρες) και demand ανά shop **αμετάβλητα**.

**Τι ΔΕΝ έχει γίνει ακόμα (επαληθευμένο τοπικά 2026-08-07):** το `kaggle-environments==1.32.5`
(sdist κατεβασμένο και diff-αρισμένο σε scratchpad, timestamp 2026-08-06 21:30) περιέχει
**μόνο** το shed/LOCKED fix της επόμενης εγγραφής. `TOWN_CENTER_DEMAND_SCHEDULE`,
`townCenterSellInterval: 12` και το `remaining = [s for s in SHOPS if s not in unlocked]`
φίλτρο είναι **byte-identical** με το 1.32.4· `kaggriculture.json` diff **κενό**. Άρα οι
αλλαγές είναι **ανακοινωμένες αλλά αδημοσίευτες** — η ladder σήμερα τρέχει ακόμα το παλιό
μοντέλο ζήτησης.

**Impact (αριθμοί από το `_town_consume` + `SHOPS` + `market_price` του 1.32.4):**

*α) Town center — σεζόν ανά προϊόν:* παλιό `10×2 + 10×4 + 10×8 = 140` μονάδες· νέο `30×1 = 30`.
**−79%**. Ανά φάση: μέρες 0-9 −50%, 10-19 −75%, 20-29 **−87,5%**. Χτυπά δυσανάλογα το late game,
δηλαδή ακριβώς τη φάση όπου η ελίτ ρευστοποιεί.

*β) Ποιος πονάει:* το shop demand (6 μον./προϊόν/μέρα ανά instance, ×2 σε single-product shop)
είναι πολλαπλάσιο του town center — άρα η ζημιά συγκεντρώνεται στα προϊόντα **χωρίς shop κάλυψη**:
- **MELON: κανένα shop δεν το αγοράζει** → η ζήτησή του πέφτει 140 → 30 μονάδες/σεζόν, με
  cliff στις 158 μονάδες. Το melon ουσιαστικά **παύει να είναι στρατηγικό crop**. Εμείς
  φυτεύουμε 0· το meta φυτεύει ~11,6 melon seeds/παίκτη και πουλά batch 12,8 τη μέρα 10
  ([ladder_snapshots 2026-08-07](docs/meta/ladder_snapshots.md#meta0807)) — **η αλλαγή χτυπά το meta πολύ
  πιο δυνατά από εμάς**.
- **FERTILIZER: εκτός `TOWN_CENTER_PRODUCTS` ΚΑΙ εκτός κάθε shop menu** → μηδενική NPC ζήτηση,
  και πριν και μετά. Αμετάβλητο, αλλά βλ. εγγραφή Yummers παρακάτω.

*γ) Shops με επανάθεση — 8 κληρώσεις από 8 τύπους (cap 8 instances):* αναμενόμενοι **διακριτοί**
τύποι `8·(1−(7/8)⁸) = 5,25` αντί για 8. Πιθανότητα να **λείπει εντελώς** ο μοναδικός αγοραστής
ενός προϊόντος:

| Προϊόν | Shops που το αγοράζουν | P(κανένα) | Έκθεσή μας |
|---|---|---|---|
| **WOOL** | YARN_STORE μόνο (1/8, single-product ⇒ 12/μέρα) | **34,4%** | ⚠️ **5 SHEEP στο v1g** |
| CARROT | PET_CAFE, FARMERS_MARKET (2/8) | 10,0% | 6 tiles (3 NW + 3 NE) |
| EGG | BAKERY, BRUNCH_SPOT (2/8) | 10,0% | 1 GOOSE (αμελητέο) |
| TOMATO | PIZZA_SHOP, FARMERS_MARKET (2/8) | 10,0% | δεν το καλλιεργούμε |
| MILK | PIZZA/ICE_CREAM/SMOOTHIE (3/8) | 2,3% | 8 COW |
| STRAWBERRY | BRUNCH/ICE_CREAM/SMOOTHIE/FARMERS_MARKET (4/8) | 0,39% | ✅ κύριο crop |
| WHEAT | BAKERY/PIZZA/BRUNCH/ICE_CREAM/FARMERS_MARKET (5/8) | 0,04% | ✅ feed + πώληση |
| MELON | **κανένα** | 100% | ✅ 0 tiles |

Σε συνδυασμό με τα sell cliffs του 1.32.4 (μονάδες πάνω από I0=10.000 μέχρι το floor $1:
**wool 59 · strawberry 62 · milk 76 · melon 158 · fertilizer 493 · carrot 842 · wheat/egg >2.000**)
το κρίσιμο σενάριο είναι: **v1g παράγει ~160 μονάδες wool/σεζόν (5 sheep × 8 pickups × 4 cared)
έναντι cliff 59** — απορροφάται μόνο από YARN_STORE (12/μέρα ≈ 288/σεζόν). Στο **34,4%** των
επεισοδίων χωρίς YARN_STORE, η μόνη ζήτηση wool θα είναι **1 μονάδα/μέρα** από το town center
και το wool καταρρέει στο $1. Αντίστοιχα milk: ~264 μονάδες (8 cow × 11 pickups × 3) έναντι
cliff 76 και αναμενόμενα 3 milk-shop instances.

**Impact στην ιεράρχηση crops (μετά την αλλαγή):** WHEAT ↑↑ (5/8 κάλυψη, καμία cliff, ήδη
υποχρεωτικό ως feed) · STRAWBERRY ↑ (σταθερό, 4/8) · MILK ↑ · WOOL ↓ (variance) ·
CARROT ↓ (variance) · MELON ↓↓↓ · FERTILIZER αμετάβλητο-μηδενικό ως NPC ζήτηση.
Επίσης: **λιγότερη συνολική ζήτηση = λιγότερα χρήματα στο σύστημα** — τα απόλυτα ladder banks
(median $115,7k σήμερα) θα πέσουν για όλους· το δικό μας $-gap θα κλείσει εν μέρει μηχανικά.
Μην κυνηγάμε το απόλυτο νούμερο.

**Ενέργεια:** εκκρεμεί — απόφαση χρήστη για (1) shop-adaptive layer (το
[agent/state.py](agent/state.py):14 **αφαίρεσε** το `unlocked_shops` από το snapshot ως «zero
real readers» — αυτό γίνεται πλέον πραγματικό liability), (2) επανεξέταση του SHEEP target του
v1g, (3) engine-bump detector ώστε η κυκλοφορία της αλλαγής να μη μας βρει αδιάβαστους. Δεν
προωθείται σε `engine_deltas.md` μέχρι να υπάρξει έκδοση που το υλοποιεί.

### 2026-08-07 — Engine bump 1.32.4 → **1.32.5**: shed actions δουλεύουν από LOCKED tiles

**Πηγή:** PyPI (`pip index versions kaggle-environments` → LATEST 1.32.5)· diff του sdist έναντι
του [engine_reference/](engine_reference/) (2026-08-07, τοπικά, **χωρίς install** — τρέχει
v1g gate).

**Τι λέει:** ολόκληρο το `.py` diff είναι **103 γραμμές, μία αλλαγή**: τα `DROP` / `PICKUP` /
`PLACE`-into-shed μετακινήθηκαν **πριν** το `if tile == "LOCKED": return` guard. Σχόλιο του
engine: *«three of the four shed-access tiles start LOCKED, so guarding them first would make the
shed unreachable from those tiles»*. Το `README.md` ενημερώθηκε αντίστοιχα (2 παράγραφοι).
`kaggriculture.json`: **κανένα** diff. Καμία balance αλλαγή — βλ. εγγραφή παραπάνω.

**Impact:** άμεσα θετικό και **μη εκμεταλλευόμενο σήμερα**. Το
[agent/scheduler.py](agent/scheduler.py):182 έχει hardcoded
`access = (4, 4)  # the only initially unlocked shed-access tile` — αληθές στο 1.32.4, **ψευδές
στο 1.32.5**. Τα hands γεννιούνται και στα 4 κεντρικά tiles αγνοώντας το LOCKED
(`SHED_ACCESS = ((4,4),(5,4),(4,5),(5,5))`), άρα σήμερα ένα hand που ξεκινά στο (5,4)/(4,5)/(5,5)
πρέπει να περπατήσει πρώτα στο (4,4) για κάθε PICKUP/DROP. Με το v1g (13 ζώα ⇒ 13 WHEAT
pickups/μέρα + 13 COLLECT_FERTILIZER) αυτό είναι επαναλαμβανόμενο κόστος 1-2 turns/διαδρομή.
Διόρθωση = «διάλεξε το κοντινότερο shed-access tile ανά unit», εντοπισμένη αλλαγή.

**Ενέργεια:** εκκρεμεί — bump **μετά** το κλείσιμο του v1g gate (αλλαγή engine στη μέση ενός
gate ακυρώνει τη σύγκριση), μετά `pytest tests/` (το
`test_engine_reference_matches_installed` θα κοκκινίσει by design — είναι το tripwire) και
re-baseline του checkpoint.

### 2026-08-07 — Discussion «Thoughts on RL vs. Deterministic Baselines» — επιβεβαιώνει standing απόφαση

**Πηγή:** forum thread (παίκτης, όχι οργανωτής).
**Τι λέει:** δοκίμασε PPO/SAC· κόλλησε σε (α) τεράστιο observation space, (β) delayed rewards των
crop cycles, (γ) **zero-tolerance μηχανικές** (μία χαμένη μέρα ποτίσματος / ένα άταιστο ζώο =
cascade σε χρεοκοπία) που το RL δεν μαθαίνει νωρίς στο training. Στράφηκε σε deterministic
heuristics για τα logistics + rule-based market logic από πάνω, με «immediate and massive jump in
consistency». Ρωτά αν κάποιος πετυχαίνει με RL μόνο στο market layer.
**Impact:** **κανένα σε δράση** — είναι ανεξάρτητη, εμπειρική επιβεβαίωση της standing απόφασης
(MASTERPLAN §4 «Γιατί όχι καθαρό RL τώρα», current_phase.md «Ρητά εκτός»), από παίκτη που
πλήρωσε το κόστος αντί για μας. Το «RL μόνο στο market layer» είναι ακριβώς το υβριδικό μονοπάτι
που το MASTERPLAN §4 κρατά ανοιχτό ως BBO στο economic-planner layer — καμία αναθεώρηση.
**Ενέργεια:** καμία (FYI)

### 2026-08-07 — Competitor notebooks *Yummers* / *Exact Marginal Impact* (v22 → v23) — 2 μηχανιστικά ευρήματα

**Πηγή:** δύο δημόσια competitor notebooks («44/46 Strict-Future Top-30 | v22 Price Impact» και το
v23 challenger). **Ταξινόμηση: EVIDENCE, όχι πηγή κώδικα** (Ανοιχτό #11 — καμία αντιγραφή route ή
πολιτικής· και τα δύο είναι frozen-route artifacts, ακριβώς το replay-copy meta που δεν
ακολουθούμε).

**Τι λένε — δύο ισχυρισμοί που επαληθεύσαμε ανεξάρτητα στο engine 1.32.4:**
1. *«FERTILIZER is special: town shops and Town Center never consume it»* — **ΕΠΙΒΕΒΑΙΩΜΕΝΟ**:
   `TOWN_CENTER_PRODUCTS = [p for p in PRODUCTS if p != "FERTILIZER"]` και το FERTILIZER δεν
   εμφανίζεται σε κανένα από τα 8 `SHOPS` menus. **Συνέπεια που μας αφορά άμεσα:** το fertilizer
   inventory είναι **μονότονα αύξον** — η τιμή του δεν ανακάμπτει ποτέ, ούτε μία μονάδα. Άρα το
   να κρατάς fertilizer είναι **καθαρή απώλεια** και η σειρά πώλησης είναι ζήτημα μηδενικού
   αθροίσματος με τον αντίπαλο. Μεγέθη: curve **493 μονάδες** ως το floor (base $100· p(+60)=$88 —
   ρηχή καμπύλη, άρα πραγματικά μεγάλη γραμμή εσόδων), έναντι **~325 μονάδες/σεζόν** που παράγουν
   13 ζώα — **~650 σε mirror**, δηλαδή πάνω από το cliff. Το v1g πρέπει να πουλά fertilizer
   **νωρίς και συνεχώς**, με πρώιμο order index.
2. *v23: «the game executes sells one unit at a time, using the pre-sell inventory quote»* —
   **ΕΠΙΒΕΒΑΙΩΜΕΝΟ** (MASTERPLAN §2 Αμφισημία #3, per-unit lockstep· README: sell price = pre-sell).
   Το σωστό έσοδο q μονάδων είναι `Σ_{i=0..q-1} p(s+i)`, **όχι** `q·p(s+q)` ούτε `q·p(s)`.
   Ο δικός μας [agent/executor.py](agent/executor.py):89 χρησιμοποιεί endpoint έλεγχο
   `market_price(product, inventory + sell_units + safety_units) > floor` — συντηρητικό
   (υποεκτιμά το έσοδο, δεν υπερεκτιμά), άρα **όχι bug**, αλλά αφήνει έσοδο στο τραπέζι σε ρηχές
   καμπύλες. Ακριβής άθροιση = εντοπισμένη βελτίωση, φυσικό μέρος του v1i.

**Impact:** κανένα στη στρατηγική δομή· δύο συγκεκριμένα, μετρήσιμα market-layer items για το
v1i (και ένα προαιρετικό fertilizer-timing item για το v1g follow-up).
**Ενέργεια:** εκκρεμεί (v1i scope)· τα δύο engine facts είναι ήδη συνεπή με το
[reference/market.md](docs/reference/market.md) — δεν χρειάζεται διόρθωση εκεί.

### 2026-08-06 — Διευκρίνιση: deactivated submissions δεν μετράνε στο τελικό Bradley-Terry

**Πηγή:** forum thread (πρώην docs/source/info.md, item 3· διαγράφηκε μετά την εξαγωγή —
πλήρες κείμενο στο git history commit πριν από αυτή την εγγραφή). Attribution σε οργανωτή
**μη επιβεβαιωμένο** — μοιάζει με host reply αλλά δεν αναφέρεται ρητά.
**Τι λέει:** «The Final B-T tournament will use all episodes between active agents across the
whole competition. Any episodes your agent played against now deactivated agents will not
count.» Δηλαδή το τελικό tournament είναι cumulative σε όλη τη διάρκεια (όχι μόνο τις 2
εβδομάδες μετά το deadline), αλλά episodes εναντίον submissions που έχουν since
απενεργοποιηθεί (π.χ. αντικαταστάθηκαν από νεότερο upload, δικό μας ή αντιπάλου) αποκλείονται
εντελώς από το fit.
**Impact:** Διευκρινίζει το ασαφές σημείο στην εγγραφή 2026-07-29 παρακάτω («εκείνα τα
episodes» = cumulative minus deactivated, όχι μόνο τα μετά-deadline). Δεν αλλάζει άμεσα
στρατηγική· FYI για το πώς μετράει η συχνότητα re-submit.
**Ενέργεια:** καμία (FYI) — αβέβαιο attribution, δεν αλλάζει engine rule ώστε να προωθηθεί σε
engine_deltas.md.

### 2026-08-06 — Διευκρίνιση: notebook σε "code" mode μετράει ως submission

**Πηγή:** forum thread (πρώην docs/source/info.md, item 6· διαγράφηκε μετά την εξαγωγή).
**Τι λέει:** Ερώτημα αν notebook ανεβασμένο στο "code" tab του competition μετράει αυτόματα ως
submission. Απάντηση: ναι, οτιδήποτε submit-άρεται μετράει.
**Impact:** Καμία επίδραση στη δική μας ροή (CLI submit με main.py/tar.gz, όχι Kaggle Notebook
editor).
**Ενέργεια:** καμία (FYI)

### 2026-08-06 — Αναδιοργάνωση docs· δημιουργία αυτού του ημερολογίου

**Πηγή:** εσωτερική απόφαση (session 2026-08-06)
**Τι λέει:** Τα `docs/` αναδιοργανώθηκαν σε `source/` (raw, verbatim), `reference/` (curated,
agent-facing), `meta/` (χρονικά ευμετάβλητο). Το `docs/game_rules.md` ήταν byte-identical με το
`engine_reference/README.md` και διαγράφηκε· οι παραπομπές `README.md:NNN` δείχνουν πλέον εκεί.
**Impact:** Κανένα στη συμπεριφορά του agent. Οι παραπομπές `viz cell N` του MASTERPLAN είναι
πλέον επιλύσιμες μέσω των anchors στο `reference/`.
**Ενέργεια:** ολοκληρώθηκε· προστέθηκε tripwire για drift του `engine_reference/README.md` και
`AGENTS.md` στο `test_engine_reference_matches_installed`.

### ~2026-08-03 — Engine fix: τα locked tiles έγιναν διαβατά (≥1.32.3)

**Πηγή:** [forum thread 731635](https://www.kaggle.com/competitions/kaggriculture/discussion/731635)
(αναφορά: Victor Mercklé), μέσω viz cell 23
**Τι λέει:** Πριν την 1.32.3 μια μονάδα **δεν μπορούσε** να πατήσει σε μη-αγορασμένο tile, οπότε
ένα hand που spawn-άριζε στο `(5,5)` έμενε παγιδευμένο ως τη νύχτα. Το fix κυκλοφόρησε και ο
**ladder τρέχει το διορθωμένο engine από τις 3 Αυγ 2026**.
**Impact:** Καταργεί την ανάγκη για locked-tile guard στο movement· αντίθετα, τέτοιος guard
**κοστίζει** 25/69 worker-turns (viz cell 24).
**Ενέργεια:** προωθήθηκε σε [reference/engine_deltas.md](docs/reference/engine_deltas.md) D13/D14.
⚠️ Δουλεύουμε σε **1.32.4** — συμβατό. Σε κάθε ύποπτη αλλαγή: `pytest tests/test_engine_facts.py`.

### 2026-07-31 (περίπου) — Επίσημες απαντήσεις οργανωτή σε 3 ερωτήματα κανόνων

**Πηγή:** `bovard` (οργανωτής), [source/discussion.md:100-112](docs/source/discussion.md)
**Τι λέει:** (1) Το fertilizer **πωλείται** — το README ενημερώθηκε. (2) **Δεν** χρειάζεται CARE
για fertilizer· το σχόλιο στον κώδικα ήταν παραπλανητικό και διορθώθηκε· επιβεβαιώθηκε ότι **δεν
συσσωρεύεται**. (3) Το 24-day `T` window είναι **σκόπιμη σχεδιαστική επιλογή** (οι πρώτες μέρες
είναι setup-heavy), όχι υπόλειμμα.
**Impact:** Το fertilizer από ζώα είναι πουλήσιμο έσοδο **και** input· τα ζώα παράγουν fertilizer
ανεξάρτητα από CARE.
**Ενέργεια:** προωθήθηκε σε [reference/engine_deltas.md](docs/reference/engine_deltas.md) D2/D7/§5·
tests: `test_fertilizer_sell_accepted`, `test_fertilizer_available_no_care_required`.

### 2026-07-29 (περίπου) — Ανακοίνωση: το τελικό evaluation είναι Bradley-Terry

**Πηγή:** επίσημη ανακοίνωση οργανωτών, [source/discussion.md:1-6](docs/source/discussion.md)
**Τι λέει:** Μετά το submission deadline (30 Σεπ) τα submissions **συνεχίζουν να παίζουν για 2
εβδομάδες**· στο τέλος τρέχει **ένα ενιαίο Bradley-Terry tournament** πάνω σε εκείνα τα episodes
για την τελική κατάταξη. Στόχος: μείωση της επίδρασης των «hot streaks».
**Impact:** Ευνοεί **σταθερά ισχυρό, ντετερμινιστικό** bot έναντι high-variance. Με 10 **ισόποσα**
βραβεία των $5.000, ο σωστός στόχος είναι «σταθερά top-10», όχι high-variance #1.
**Ενέργεια:** ήδη ενσωματωμένο σε [MASTERPLAN §7](docs/MASTERPLAN.md).

### 2026-07-29 (περίπου) — Daily Top Episodes Dataset

**Πηγή:** επίσημη ανακοίνωση, [source/discussion.md:8-11](docs/source/discussion.md)
**Τι λέει:** Καθημερινά τα episodes ταξινομούνται κατά μέσο rating των agents και κατεβαίνουν έως
**20 GB replays** σε νέο dataset:
[kaggle/kaggriculture-episodes-index](https://www.kaggle.com/datasets/kaggle/kaggriculture-episodes-index).
Υπάρχει και το community dataset `georgymamarin/kaggriculture-episodes`.
**Impact:** Πηγή για gap analysis και target curves.
**Ενέργεια:** χρησιμοποιείται σε [meta/ladder_snapshots.md](docs/meta/ladder_snapshots.md).
⚠️ **Όριο του repo:** τα replays είναι **διαγνωστικό και target curve, ΠΟΤΕ πηγή κινήσεων** —
BC/IL/trajectory copying είναι μόνιμα εκτός scope ([MASTERPLAN §3.4](docs/MASTERPLAN.md)).

---

## Ανοιχτά ερωτήματα προς τη σελίδα του διαγωνισμού

Πράγματα που θα ήταν χρήσιμο να επιβεβαιωθούν από οργανωτές ή forum:

1. **Πώς ακριβώς υπολογίζεται το skill rating;** Χρήστες αναφέρουν επιβράδυνση κερδών (70-80
   πόντοι/παιχνίδι στα 1850 → 13-20 στα 2450) και αραίωση matchmaking στα υψηλά ratings. Η
   υπόθεση της κοινότητας είναι κρυφό σ à la Orbit Wars (`N(μ, σ²)`), χωρίς επίσημη επιβεβαίωση.
   ([source/discussion.md:116-133](docs/source/discussion.md))
2. **Πόσο πραγματικά συζεύγνυνται οι δύο παίκτες;** Ανοιχτή ανησυχία για **trajectory copying**
   από δημόσια replays. Θέση οργανωτών: η κοινή αγορά *είναι* ο μηχανισμός σύζευξης — «αν
   πουλάτε και οι δύο το ίδιο, υποφέρουν και τα δύο κέρδη· ο πρώτος που πουλά παίρνει την
   καλύτερη τιμή». ([source/discussion.md:135-141](docs/source/discussion.md))
