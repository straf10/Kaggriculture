# current_phase.md — Φάση 2: Πρώτο submission + σύγκλιση προς την ελίτ

> **Working plan της τρέχουσας φάσης** — εκτελεί τη στρατηγική του
> [docs/MASTERPLAN.md](docs/MASTERPLAN.md)· **δεν την επαναδιαπραγματεύεται**. Αντικαθιστά το
> παλιό `plan.md` (Φάσεις 0-1, ολοκληρωμένες — διαγράφηκε 2026-08-06, το πλήρες ιστορικό του ζει
> στο git). Engine ground truth: το εγκατεστημένο `kaggle-environments==1.32.4`·
> το [engine_reference/kaggriculture.py](engine_reference/kaggriculture.py) είναι read-only
> αντίγραφο για line refs. Όπου docs και engine διαφωνούν, υπερισχύει το engine.
>
> Δημιουργία: **2026-08-06**. Deadline: **30 Σεπ 2026** (~8 εβδομάδες). Τελική κατάταξη:
> Bradley-Terry σε ~2 εβδομάδες episodes **μετά** το deadline (MASTERPLAN §1, Φάση 3 άξονας δ).
>
> ---
>
> ## 🔒 ΚΑΝΟΝΑΣ ΑΚΟΛΟΥΘΙΑΣ (2026-08-07) — τίποτα από τα παρακάτω δεν αγγίζει το τρέχον v1g run
>
> Στις **2026-08-07** μπήκαν 4 νέα εξωτερικά δεδομένα (πλήρης ανάλυση:
> [docs/meta/competition_updates.md](docs/meta/competition_updates.md) 4 εγγραφές +
> [docs/meta/ladder_snapshots.md 2026-08-07](docs/meta/ladder_snapshots.md#meta0807)). Το v1g gate
> **έτρεχε ήδη** όταν καταγράφηκαν. Όλες οι αλλαγές που περιγράφονται σε αυτό το έγγραφο ως
> **v1g.1 / v1g.2 / v1h′** εκτελούνται **ΜΕΤΑ** το κλείσιμο του v1g, με αυτή τη σειρά και για
> συγκεκριμένο λόγο ανά περίπτωση:
>
> | Βήμα | Γιατί ΔΕΝ γίνεται τώρα |
> |---|---|
> | Engine bump 1.32.4 → 1.32.5 | Αλλαγή engine στη μέση ενός gate **ακυρώνει τη σύγκριση**: το `compare()` μετρά A vs B στο ίδιο seed· αν το B έτρεξε σε άλλο engine, το mean_diff δεν σημαίνει τίποτα. Επίσης θα κοκκινίσει το `test_engine_reference_matches_installed` και θα μπερδέψει κάθε παράλληλο pytest. |
> | Αλλαγή `agent/config.py` (SHEEP target) | Ο agent φορτώνεται **σε κάθε worker process ξεχωριστά** και το v1g τρέχει 10 workers· επεξεργασία του `agent/` κατά τη διάρκεια του run δίνει **ανάμεικτα** αποτελέσματα μεταξύ seeds — ακριβώς το είδος σιωπηλής μόλυνσης που έκρυψε το `c7767bb` regression. |
> | Shop-adaptive layer (`agent/state.py`, `executor.py`) | Ίδιος λόγος + θα άλλαζε το ίδιο το baseline έναντι του οποίου κρίνεται το v1g. |
>
> **Επιτρέπεται τώρα:** μόνο εγγραφή σε `.md` (αυτό το αρχείο, `docs/`, `memory.md`) — τα docs δεν
> διαβάζονται από κανέναν worker.
>
> **Πρώτο πράγμα όταν κλείσει το v1g:** το §Β.0 «Τι χρειάζομαι από το v1g episode report»
> παρακάτω — **πριν** από οποιαδήποτε αλλαγή κώδικα, γιατί δύο από τις αποφάσεις (SHEEP target,
> fertilizer timing) εξαρτώνται από αριθμούς που **μόνο** εκείνο το run μπορεί να δώσει.

**Πού είμαστε σε μία παράγραφο:** Φάση 1 **κλειστή** — v1e αποδεκτό (median **$42.555** vs
`starter`, 96/96 wins σε HOLDOUT, [checkpoints/v1e](checkpoints/v1e), memory.md 2026-08-06).
Όλη η υποδομή μέτρησης δουλεύει (parallel compare, dev/holdout split, metric gates, episode
report, G11 receipts). Το χάσμα με την ελίτ είναι **δομικό, όχι παραμετρικό**: ~$42,6k έναντι
$125,3k median της ζώνης Elo ≥2800. Δύο δουλειές, με αυτή τη σειρά: **(Α) πρώτο submission
ΤΩΡΑ** (δωρεάν πληροφορία από την πραγματική ladder — MASTERPLAN §5 «όσο νωρίτερα γίνεται»),
**(Β) κλιμάκωση προς το engine optimum** (crew → ζώα → 3ο quadrant → sell-ahead), κάθε βήμα
με το ίδιο gate πρωτόκολλο.

---

## 0. Το χάσμα, αριθμητικά (τι πρέπει να αλλάξει)

Σύγκριση του v1e (τρέχον [agent/config.py](agent/config.py)) με το modal top farm της ελίτ
([topfarms-19](docs/meta/ladder_snapshots.md#topfarms-19), Elo ≥2800, 08-05) και τα top-decile
timings ([data/derived/top_agent_profiles.md](data/derived/top_agent_profiles.md)):

| Διάσταση | v1e σήμερα | Ελίτ | Δράση |
|---|---|---|---|
| Median bank | ~$42,6k (vs starter) | ~~$125,3k~~ → **$115,7k** ⚠️α | — (αποτέλεσμα των παρακάτω) |
| Hands | ~~`hands_target: 3`~~ → **6** | ~~12~~ → **5-6** ⚠️β | ✅ **v1f κλειστό** |
| Ζώα | 3 (1 COW + 1 SHEEP + 1 GOOSE) | **13-14** (8 cow + 5-6 sheep· goose μόλις 15% adoption) | **v1g** (τρέχει) |
| Quadrants | 2 (NW+NE) | **3 (NE+NW+SW)· SE ποτέ** (#3 → median μέρα 11) | **v1h′** |
| Crops | 10 carrot + 31 strawberry | ~~6 strawberry + 1 wheat~~ **μη συγκρίσιμο** ⚠️γ | **κανένα rebalance** — βλ. ⚠️γ |
| Sell timing | στατικά sell floors ανά προϊόν | πωλήσεις σε ημερολόγιο πάνω σε γνωστά cliffs | **v1i** (άξονας β) |
| **Προσαρμογή σε ζήτηση** | **καμία** — το `unlocked_shops` έχει αφαιρεθεί από το snapshot | το ίδιο (κανείς δεν το κάνει ακόμα) | **v1g.2** ⚠️δ — *νέα γραμμή* |

**⚠️α — ο απόλυτος στόχος «$125k» αποσύρεται.** Το money median της ζώνης Elo ≥2700 έπεσε
$125.877 → **$115.664** στις 08-06, **ενώ** το score-median ανέβηκε +135 Elo
([ladder_snapshots 2026-08-07](docs/meta/ladder_snapshots.md#meta0807)). Δηλαδή το απόλυτο bank
είναι **δείκτης κορεσμού της κοινής αγοράς**, όχι δείκτης ποιότητας — και το BT μετρά W/L, όχι $.
Μετά τη balance change (§0bis) θα πέσει κι άλλο για όλους. **Ο στόχος γίνεται σχετικός**: «κερδίζω
τον προηγούμενο checkpoint σε holdout» + «κερδίζω σε mirror margin», όχι «φτάνω τα $X».

**⚠️β — η γραμμή «3 → 12 hands» ήταν λάθος και το v1f το βρήκε ανεξάρτητα.** Το 12 προερχόταν από
το [topfarms-19](docs/meta/ladder_snapshots.md#topfarms-19) (08-05). Το 08-06 report δίνει modal
**5 hands** (2ο: 6) και εξηγεί ρητά την αιτία: **fib hire-cost ceiling** — οι παίκτες στέλνουν
200-300 HIRE orders και πληρώνουν μόνο τα πρώτα. Το δικό μας v1f screen κατέληξε στο ίδιο σημείο
από **άλλο μονοπάτι** (h10/h12 `REGRESSED` λόγω idle hands σε σταθερό tile ceiling). Δύο
ανεξάρτητοι μηχανισμοί, ίδιο νούμερο ⇒ το `hands_target=6` είναι σταθερό· **καμία περαιτέρω
κλιμάκωση crew** χωρίς πρώτα να μεγαλώσει το πραγματικό workload.

**⚠️γ — ΜΗΝ κάνεις rebalance προς το modal farm: είναι measurement artifact.** Το fingerprint της
ελίτ μετριέται στο **τέλος** του επεισοδίου, και στο engine τα crops **δεν επιβιώνουν**:
- one-shot (WHEAT/CARROT/MELON): `HARVEST` κάνει `farm["tiles"][fy][fx] = None`
  (`engine_reference/kaggriculture.py:411-412`) — το tile αδειάζει μόλις θεριστεί·
- **STRAWBERRY επίσης**: μόλις φτάσει `max_yield` (ηλικίες 10/12/14/16) το `_daily_refresh_plants`
  του θέτει `max_lifespan_step`, και μετά το `_decay_plants` κάνει `yield_units -= 1` κάθε 2 turns
  με **`<= 0` ⇒ `{"kind": "WEED"}`** (`:742-744`). Αν έχει ήδη θεριστεί (`yield_units == 0`), το
  **πρώτο** decay tick το μετατρέπει σε WEED. Strawberry μέρας 0 ⇒ WEED **μέρα ~17-18**.

Επιβεβαίωση μέσα στο ίδιο report: **1.366/1.366 seats** πουλάνε wheat (μέρα 2), melon (10),
**strawberry (18)**, fertilizer (3), milk (10), wool (9), με early seeds **wheat 14,0 / melon 11,6
ανά παίκτη**. Δεν πουλάς ό,τι δεν καλλιεργείς. **Συνέπεια:** η ελίτ είναι wheat+melon-βαριά νωρίς
**και** ζώα· το «6 strawberry + 1 wheat» είναι **κάτω φράγμα**, όχι mix. Η γραμμή «Crops» του
πίνακα συνέκρινε **ζωντανά** tiles (δικά μας, μετρημένα από config) με **επιζώντα** tiles (δικά
τους) — μη συγκρίσιμα μεγέθη. Το v1h **δεν** κάνει πλέον portfolio rebalance προς το modal.

**⚠️δ — νέα, πραγματική τρύπα.** Το [agent/state.py](agent/state.py):14 αφαίρεσε το
`unlocked_shops` από το snapshot ως «zero real readers» (review L9). Ήταν σωστό τότε. Γίνεται
liability μόλις κυκλοφορήσει το shops-with-replacement (§0bis) — και έχει αξία **ακόμα και πριν**
από αυτό, γιατή ήδη σήμερα η σειρά ξεκλειδώματος είναι τυχαία ανά episode.

Δύο προειδοποιήσεις πριν αντιγράψουμε αριθμούς:
1. Το modal farm είναι η **καλύτερη εκτίμηση του engine optimum υπό ανταγωνισμό**, όχι συνταγή
   (MASTERPLAN §3.4 άξονας α). Το δικό μας strawberry-βαρύ mix έχει το υψηλότερο win rate ως
   πρωτεύον crop στο full ladder (70%, n=441 — §3.2bis)· η σύγκλιση αφορά πρωτίστως **μάζα ζώων
   + crew**, όχι απαραίτητα την εγκατάλειψη του strawberry. Κάθε rebalance περνά gate.
2. Τα wheat-primary record games ([daily-11](docs/meta/ladder_snapshots.md#daily-11)) είναι
   single-game ενδείξεις — δεν αλλάζουν το mix χωρίς δεύτερη μέτρηση.

---

## 0bis. Το εισερχόμενο engine ρίσκο (2026-08-07) — αριθμοί, όχι ανησυχία

Οι οργανωτές **ανακοίνωσαν** balance changes. Επαληθεύσαμε τοπικά (κατέβασμα sdist
`kaggle-environments==1.32.5`, diff έναντι `engine_reference/`, **χωρίς install**) ότι:

- Το **1.32.5 ΔΕΝ τις περιέχει.** Ολόκληρο το `.py` diff = **103 γραμμές, μία αλλαγή** (shed ops
  πριν το LOCKED guard, §v1g.1)· `kaggriculture.json` diff **κενό**·
  `TOWN_CENTER_DEMAND_SCHEDULE`, `townCenterSellInterval: 12` και το φίλτρο
  `remaining = [s for s in SHOPS if s not in unlocked]` **byte-identical** με το 1.32.4.
- Άρα: **ανακοινωμένες, αδημοσίευτες**. Η ladder σήμερα τρέχει ακόμα το παλιό μοντέλο ζήτησης.
  Δεν σχεδιάζουμε για κάτι που δεν υπάρχει — σχεδιάζουμε **ώστε να μη μας κοστίσει όταν έρθει**.

### 0bis.1 Τι αλλάζει, ποσοτικά

**(α) Town center −79%.** `townCenterSellInterval` 12 → 24 (2 ticks/μέρα → 1) **και** flat ×1
(αφαιρείται το ramp ×2@d10 / ×4@d20). Σεζόν ανά προϊόν: `10×2 + 10×4 + 10×8 = 140` → `30×1 = 30`.
Ανά φάση: μέρες 0-9 **−50%**, 10-19 **−75%**, 20-29 **−87,5%** — χτυπά δυσανάλογα τη φάση
ρευστοποίησης. Ακυρώνει το MASTERPLAN §3.2#6 («ίδια αγαθά αξίζουν περισσότερα αργότερα»).

**(β) Ποιος πονάει.** Το shop demand (6 μον./προϊόν/μέρα ανά instance, ×2 σε single-product shop)
είναι **πολλαπλάσιο** του town center, άρα η ζημιά συγκεντρώνεται στα προϊόντα χωρίς shop κάλυψη:
- **MELON**: κανένα από τα 8 shops δεν το αγοράζει ⇒ 100% εξαρτημένο από το TC ⇒ 140 → 30
  μονάδες/σεζόν με cliff στις 158. Παύει να είναι στρατηγικό crop. **Εμείς φυτεύουμε 0** — το meta
  φυτεύει 11,6 seeds/παίκτη. **Η αλλαγή χτυπά το meta πολύ πιο δυνατά από εμάς: είναι ευκαιρία,
  όχι απειλή.**
- **FERTILIZER**: εκτός `TOWN_CENTER_PRODUCTS` **και** εκτός κάθε shop menu — μηδενική NPC ζήτηση
  πριν και μετά. Αμετάβλητο, αλλά βλ. §v1g.2 (β).

**(γ) Shops με επανάθεση — εδώ είναι η δική μας έκθεση.** 8 κληρώσεις από 8 τύπους (cap
`MAX_SHOP_INSTANCES = 8`). Αναμενόμενοι **διακριτοί** τύποι `8·(1−(7/8)⁸) = 5,25` αντί για 8:

| Προϊόν | Shops που το αγοράζουν | P(κανένα) | Παραγωγή μας (v1g) | Cliff (μον. ως $1) |
|---|---|---|---|---|
| **WOOL** | YARN_STORE μόνο (1/8, single ⇒ 12/μέρα) | **34,4%** | **~160** (5 sheep) | **59** |
| CARROT | PET_CAFE, FARMERS_MARKET (2/8) | 10,0% | 6 tiles | 842 |
| EGG | BAKERY, BRUNCH_SPOT (2/8) | 10,0% | 1 GOOSE | >2.000 |
| MILK | PIZZA/ICE_CREAM/SMOOTHIE (3/8) | 2,3% | **~264** (8 cow) | **76** |
| STRAWBERRY | BRUNCH/ICE_CREAM/SMOOTHIE/FARMERS_MKT (4/8) | 0,39% | 24 tiles | 62 |
| WHEAT | BAKERY/PIZZA/BRUNCH/ICE_CREAM/FARMERS_MKT (5/8) | **0,04%** | feed + πώληση | **>2.000** |
| MELON | **κανένα** | 100% | 0 ✅ | 158 |

*(cliffs υπολογισμένα με `market_price(item, 10000+n)` του 1.32.4· παραγωγή = pickups × cared
yield: sheep 8 pickups × (1+3), cow 11 × (1+2))*

**Το κρίσιμο σενάριο:** 160 μονάδες wool έναντι cliff **59**. Απορροφώνται μόνο από YARN_STORE
(12/μέρα ≈ 288/σεζόν). Στο **34,4%** των επεισοδίων χωρίς YARN_STORE η μόνη ζήτηση wool είναι
**1 μονάδα/μέρα** από το TC ⇒ το wool πάει στο $1 και τα 5 sheep γίνονται **καθαρό κόστος**
($500 αγορά + 5 wheat/μέρα feed + 10 unit-turns/μέρα). Δεν είναι ακραίο tail — είναι 1 στα 3.

**(δ) Νέα ιεράρχηση μετά την αλλαγή:** WHEAT ↑↑ (5/8 κάλυψη, καμία cliff, ήδη υποχρεωτικό ως
feed) · STRAWBERRY ↑ (4/8, σταθερό) · MILK ↑ · **WOOL ↓ (variance)** · CARROT ↓ (variance) ·
MELON ↓↓↓ · FERTILIZER αμετάβλητα μηδενικής NPC ζήτησης.

### 0bis.2 Δύο engine facts που επαληθεύσαμε (από competitor notebooks, ως *evidence*)

Πηγή: *Yummers* / *Exact Marginal Impact* (v22→v23). **Ταξινόμηση: EVIDENCE, όχι πηγή κώδικα** —
είναι frozen-route artifacts, ακριβώς το replay-copy meta που δεν ακολουθούμε (Ανοιχτό #11).
Και οι δύο ισχυρισμοί ελέγχθηκαν **ανεξάρτητα στο δικό μας `engine_reference/`**:

1. **Το fertilizer inventory είναι μονότονα αύξον** ⇒ η τιμή του **δεν ανακάμπτει ποτέ**, ούτε μία
   μονάδα. Άρα το «κρατάω και πουλάω αργότερα» είναι **καθαρή απώλεια**, και η σειρά πώλησης
   έναντι του αντιπάλου είναι παιχνίδι μηδενικού αθροίσματος. Μεγέθη: curve **493 μονάδες** ως το
   floor, base $100, `p(+60) = $88` — **ρηχή καμπύλη ⇒ μεγάλη γραμμή εσόδων** για 13-14 ζώα
   (~325 μονάδες/σεζόν· **~650 σε mirror**, δηλαδή πάνω από το cliff). Το meta το ξέρει ήδη:
   fertilizer πρώτη πώληση **μέρα 3, από 1.366/1.366 seats**.
2. **Sell execution είναι per-unit με pre-sell quote** ⇒ το έσοδο q μονάδων είναι
   `Σ_{i=0..q-1} p(s+i)`, **όχι** `q·p(s+q)`. Ο [agent/executor.py](agent/executor.py):89
   ελέγχει `market_price(product, inventory + sell_units + safety_units) > floor` — **endpoint,
   άρα συντηρητικό**: υποεκτιμά το έσοδο, δεν το υπερεκτιμά. **Δεν είναι bug** — αλλά αφήνει
   έσοδο στο τραπέζι σε ρηχές καμπύλες (fertilizer, carrot, wheat). Φυσικό v1i item.

---

## ΜΕΡΟΣ Α — Πρώτο submission (εκτελείται ΤΩΡΑ, πριν από κάθε νέο feature)

Το v1e πληροί τα κριτήρια Φάσης 1 (96/96 vs starter, median ≥$40k). Κάθε μέρα χωρίς submission
είναι χαμένη πληροφορία ladder. Διαδικασία (από το παλιό plan §6, αμετάβλητη):

> **Ενημέρωση 2026-08-06 (δ):** το πρώτο submission πακετάρεται από το **παγωμένο
> `checkpoints/v1e`**, όχι από `main.py agent/` του repo root κατά γράμμα — βλ.
> [baselines/2026-08-06/validation.md](baselines/2026-08-06/validation.md) — επειδή δύο commits
> μετά το checkpoint (`99db4fb`, `c7767bb`) είχαν εισάγει ένα μη-απομονωμένο ~$614/episode
> regression έναντι του παγωμένου checkpoint (DEV_SEEDS).
>
> **Ενημέρωση 2026-08-06 (ε) — bisect ΛΥΘΗΚΕ:** root cause εντοπίστηκε στο
> [agent/executor.py](agent/executor.py)'s wheat-purchase block (το `c7767bb` αφαίρεσε το
> `hour == 0` gate, κάνοντας το κάθε-ώρα recheck να παρεξηγεί τη φυσιολογική κατανάλωση wheat
> από το FEED ως νέο shortfall και να ξανααγοράζει). Διορθώθηκε ώστε το `wheat_needed` να
> υπολογίζεται από τα `unfed_animals` (`fed_today` flag) αντί για το σύνολο `placed_animals` —
> βλ. memory.md 2026-08-06 (ε) για πλήρη ανάλυση. Καθαρό `compare` σε DEV_SEEDS: mean_diff=-9.70
> (se=30.89, στατιστικά αδιάκριτο από 0), `pytest tests/` 133 passed. Το τρέχον repo-root
> `agent/` είναι πλέον ξανά συμπεριφορικά ισοδύναμο του `checkpoints/v1e` — το v1f μπορεί να
> ξεκινήσει από αυτό ως βάση.

### Α.1 Checklist προ-υποβολής

- [ ] **Format**: `tar -czf submission.tar.gz main.py agent/` — `main.py` στο **root** του
  αρχείου (competition_info.md:421-429)· υποβολή από **CLI**, όχι notebook.
- [ ] **Loader contract (G12)**: exported `agent` = τελευταίο callable· imports top-level·
  κανένα `__file__` shim· vendored constants fallback ([agent/_vendored.py](agent/_vendored.py))
  parity-tested.
- [ ] **Timing**: cold-process profile και στα 2 seats· gate `max_turn × 3 < 1s` (<333ms
  τοπικά — ο server έχει 1.6 vCPU, πιθανώς αργότερος)· cold import/turn-1 χωριστά.
- [ ] **Determinism (G13)**: ίδιο seed σε 2 fresh processes + διαφορετικό `PYTHONHASHSEED` →
  ταυτόσημο trajectory.
- [ ] **Mirror smoke**: `python -m harness.cli play main.py main.py --steps 720` — `clean=True`,
  καμία αυτοκαταστροφή αγοράς, κανένα cache cross-talk.
- [ ] **Μέγεθος** < 100 MiB · `pytest tests/` πλήρως πράσινο · `KAGGRI_DEBUG` **off** by default.

### Α.2 Εντολές

```powershell
kaggle competitions submit kaggriculture -f submission.tar.gz -m "v1e rule-based baseline"
kaggle competitions submissions kaggriculture          # status + SUBMISSION_ID
kaggle competitions episodes <SUBMISSION_ID>           # -v για CSV
kaggle competitions replay <EPISODE_ID> -p ./baselines/<date>/replays
kaggle competitions logs <EPISODE_ID> 0 -p ./baselines/<date>/logs   # index = seat
```

Το CLI auth είναι λυμένο (`KAGGLE_API_TOKEN` στο `.env`, `userHasEntered: True`).

### Α.3 Baseline καταγραφή — `baselines/2026-08-XX/`

- [ ] `local_bench.json`: `compare(v1e, "starter", HOLDOUT_SEEDS)` raw rows + fingerprints +
  mirror bank (+ vs `"pass"`/`"random"`).
- [ ] `validation.md` (pass/fail + χρόνος) · `rating_trajectory.csv` (πρώτα ~20 episodes) ·
  `leaderboard_snapshot.md` (ημέρα 1 και 3) · 2-3 **ηττημένα** replays + logs για post-mortem.
- [ ] Από τα logs πραγματικού episode: επιβεβαίωση `actTimeout`/χρόνων στο server (Ανοιχτό #7).

### Α.4 Slots

5 uploads/μέρα, **μόνο τα 2 τελευταία active** και αυτά μπαίνουν στο final. 1ο upload = v1e
baseline. Κάθε επόμενο upload **μόνο** με directional `IMPROVED` σε holdout-confirm — όχι
«δοκιμαστικά». Τελευταία εβδομάδα πριν τις 30/09: κατεψυγμένο champion/challenger.

---

## ΜΕΡΟΣ Β — Increments σύγκλισης v1f → v1i

**Σειρά και σκεπτικό (MASTERPLAN §5.0):** capacity πρώτα (crew), μετά το ακριβό κεφάλαιο (ζώα),
μετά γη, μετά market intelligence. Κάθε increment: υλοποίηση → contract/guard tests → metric
gate → `compare` σε DEV (screen) → **holdout-confirm 48 seeds** → immutable checkpoint. Baseline
κάθε gate = το προηγούμενο αποδεκτό checkpoint (τώρα: `checkpoints/v1e`). `REGRESSED` = STOP
και revert· `INCONCLUSIVE` σε holdout = STOP για απόφαση.

> **[ενημ. 2026-08-07] Αναθεωρημένη σειρά μετά το v1g:**
> `v1g` (τρέχει) → **`Β.0` συλλογή δεδομένων** → **`v1g.1` engine bump** → **`v1g.2` shop-adaptive
> + fertilizer timing** → **`v1h′` SW quadrant** → `v1i` sell-ahead. Το v1g.1 μπαίνει πριν από
> κάθε άλλο κώδικα γιατί αλλάζει το ίδιο το engine — κάθε gate που τρέχει μετά πρέπει να έχει
> baseline **στο ίδιο engine**, αλλιώς συγκρίνουμε μήλα με πορτοκάλια.

### Β.0 — ⚠️ ΤΙ ΧΡΕΙΑΖΟΜΑΙ ΑΠΟ ΤΟ v1g EPISODE REPORT (πριν από κάθε αλλαγή κώδικα)

Δύο αποφάσεις παρακάτω (**SHEEP target**, **fertilizer sell timing**) **δεν** μπορούν να ληφθούν
από θεωρία — εξαρτώνται από το τι πραγματικά συνέβη στην αγορά με 13-14 ζώα. Ζητώ **ρητά** τα
παρακάτω, ώστε να ξέρεις τι να κατεβάσεις/παράξεις:

**Β.0.1 — Από το τοπικό v1g run (δεν χρειάζεται δίκτυο, υπάρχει ήδη):**

```powershell
# 1) Το report ενός αντιπροσωπευτικού seed, με receipts ενεργά
$env:KAGGRI_DEBUG = "1"
python -m harness.cli play main.py checkpoints/v1f/main.py --seed 0 --seat 0 --render-html
python -m harness.cli report <το replay path που τύπωσε το play>
# 2) Το ίδιο για ένα seed που το v1g ΕΧΑΣΕ (βρες το από το results.jsonl του gate)
```

Από αυτά χρειάζομαι **τέσσερα νούμερα**, όλα ήδη παραγόμενα από το `harness/metrics.py` /
`harness/report.py` (πίνακας μετρικών MASTERPLAN §6, σημείο 3 «μέση τιμή πώλησης ανά προϊόν vs
base»):

| # | Μετρική | Γιατί τη χρειάζομαι | Κατώφλι απόφασης |
|---|---|---|---|
| 1 | **Μέση realized τιμή πώλησης WOOL** (και σύνολο μονάδων) | base $200, cliff 59 μονάδες. Παράγουμε ~160. | Αν `avg < $80` ⇒ το wool είναι ήδη κορεσμένο **πριν** τη balance change ⇒ SHEEP target κάτω |
| 2 | **Μέση realized τιμή πώλησης MILK** (και σύνολο μονάδων) | base $160, cliff 76. Παράγουμε ~264. | Αν `avg < $70` ⇒ το ίδιο για COW |
| 3 | **Μέση realized τιμή + σύνολο μονάδων FERTILIZER**, **και η κατανομή ανά μέρα** | base $100, cliff 493, μηδενική NPC ζήτηση | Αν πουλάμε αργά (median μέρα > 10) ⇒ αφήνουμε λεφτά στο τραπέζι· το meta πουλά μέρα 3 |
| 4 | **`animals_escaped`, `weeds_lost`, `unexplained_noops`, `shed_overflow_burnt`** | metric gate v1g + το γνωστό pre-existing `weeds_lost` | `animals_escaped > 0` ⇒ το FEED logistics έσπασε στα 14 ζώα ⇒ STOP |

**Αν το report δεν σερβίρει το «avg sell price ανά προϊόν»** ως έτοιμο πεδίο: υπάρχει ήδη στο
`extract_metrics` (`units_sold_at_or_below_5`, `sales_count`) αλλά **όχι** ανά προϊόν — τότε η
πρώτη δουλειά του Β.0 είναι να προστεθεί `avg_sell_price_by_product` εκεί. **Προσοχή:**
[harness/cli.py](harness/cli.py)'s `_results_json_dict` **δεν σερβίρει** αρκετά από τα νεότερα
gate πεδία στο `results.json` (γνωστό από memory.md 2026-08-06 (δ)) — μη συμπεράνεις ότι μια
μετρική λείπει επειδή δεν φαίνεται στο JSON· διάβασε το `CompareResult` object απευθείας σε Python.

**Β.0.2 — Από το Kaggle (χρειάζεται δίκτυο· εσύ ή ο agent):**

```powershell
kaggle competitions submissions kaggriculture              # τρέχον status/score του v1e
kaggle competitions episodes <SUBMISSION_ID> -v            # CSV με τα episodes
kaggle competitions replay <EPISODE_ID> -p ./baselines/2026-08-XX/replays
```

Χρειάζομαι **2-3 replays από ΗΤΤΕΣ** του live v1e. Λόγος: όλα τα σημερινά μας δεδομένα για την
ελίτ είναι **aggregates τρίτων** (meta reports). Ένα δικό μας χαμένο episode δείχνει *ποιο
προϊόν* μας κατέρρευσε και *ποια μέρα* — η μόνη άμεση μέτρηση της δικής μας έκθεσης στον κορεσμό.

**Β.0.3 — Προαιρετικό, μόνο αν θέλουμε να προλάβουμε το shops-with-replacement:** re-download του
community dataset (`kagglehub.dataset_download("georgymamarin/kaggriculture-episodes")` — το
snapshot μας σταματά στις **08-04**, MASTERPLAN §3.2bis freshness note το χαρακτηρίζει
**υποχρεωτικό** πριν τη Φάση 3). Χρειάζομαι από εκεί μία στήλη που **δεν** έχουμε ποτέ κοιτάξει:
τα `unlocked_shops` ανά episode, ώστε να μετρηθεί εμπειρικά **πόσο** διαφέρει το τελικό bank
ανάμεσα σε episodes με/χωρίς YARN_STORE. Αυτό μετατρέπει το §0bis(γ) από θεωρητικό υπολογισμό σε
μετρημένο effect size.

> **(η) Β.0 ΟΛΟΚΛΗΡΩΘΗΚΕ 2026-08-07 — data-gathering session, καμία αλλαγή σε `agent/config.py`.**
>
> **Β.0.1 verdict re-confirm:** το `runs/gate_v1g_*` **όντως δεν υπήρχε** (επιβεβαιώθηκε)· κανένα
> `results.jsonl`/`.json` με τους αριθμούς δεν επιβίωσε πουθενά στο repo, μόνο πρόζα στο
> `memory.md`/commit message. Το `gates/confirm_log.jsonl` entry που όντως έτρεξε
> (`2026-08-07T11:57:48`, verdict `IMPROVED`, `go: false`) είχε `agent_a_fp` που **δεν** ταίριαζε
> με το fingerprint του `checkpoints/v1g` — ο κώδικας που πέρασε το holdout gate δεν ήταν
> bit-identical με αυτό που τελικά έγινε checkpoint (ανεξήγητο, πιθανόν trivial diff). Λύθηκε με
> **live re-run** του holdout-confirm (τρέχον `main.py` = fingerprint του checkpoint, vs
> `checkpoints/v1f`, `--metrics`, persisted σε `runs/gate_v1g_reconfirm_holdout/` +
> `gates/gate_v1g_reconfirm_holdout/` — το πρώτο durable artifact του v1g gate που υπάρχει στο
> repo): verdict **IMPROVED**, mean_diff **+$25,343.2/ep** (se 594.7, σχεδόν ταυτόσημο με το
> claimed +$25.343/se=594.65), **96/96** episode wins, `animals_escaped_a=0` σε όλα τα 96,
> `metric_gate_passed=False` **αποκλειστικά λόγω `weeds_lost_a=768`** (pre-existing issue, ήδη
> στο v1e baseline — όχι v1g regression). Ο πυρήνας του claim επιβεβαιώθηκε ανεξάρτητα.
>
> **Β.0.1 — οι 4 αριθμοί** (main.py vs `checkpoints/v1f`, seed 0 + τυχαίο seed 25 — v1g κέρδισε
> και τα δύο, δεν βρέθηκε χαμένο seed σε 48/48 holdout):
> | # | Μετρική | seed 0 | seed 25 | Verdict |
> |---|---|---|---|---|
> | 1 | avg WOOL / units | $233.9 / 58 | $244.5 / 58 | πολύ πάνω από $80 — **δεν** χρειάζεται screen |
> | 2 | avg MILK / units | $271.8 / 175 | $266.7 / 175 | πολύ πάνω από $70 — **δεν** χρειάζεται screen |
> | 3 | avg FERTILIZER / units, median day | $70.3 / 205, day **18** | $70.3 / 205, day **18** | **πουλάμε αργά** — meta πουλά day 3 |
> | 4 | animals_escaped / weeds_lost / noops / shed_overflow | 0 / 8 / None / 0 | 0 / 8 / None / 0 | καθαρό, weeds_lost=pre-existing |
>
> **Απόφαση:** το §v1g note (ζ) παραπάνω ("τρέξε screen `{8,5}` vs `{6,3}` vs `{8,3}` αν avg <
> κατώφλια") **δεν ενεργοποιείται** — το SHEEP/COW target 6C+4S **μένει ως έχει**, καμία ανάγκη
> screen προς τα κάτω. Το πραγματικό εύρημα είναι το #3 (fertilizer αργά) — ήδη καλύπτεται από το
> προγραμματισμένο **v1g.2 fertilizer timing** work παρακάτω, όχι νέο increment.
>
> **Β.0.2 — 3 χαμένα replays του live v1e** (`SUBMISSION 55301989`, 8 επεισόδια κατέβηκαν, 3
> ήττες): vs Joseph Garcia (42.216 vs 56.379), Vincent Pan (42.520 vs 57.216), Mehrdad ALMASI
> (40.459 vs 45.886). Και στα 3: `animals_escaped=0`, `weeds_lost=15` (ίδιο pre-existing pattern),
> οι δικές μας avg sell prices υγιέστατες (wool ~$230-236, milk ~$252-277, fertilizer ~$85-94 —
> καμία τιμή δεν κατέρρευσε), παραγωγή ταυτόσημη και στα 3 (ακόμα μικρό v1e, 3 ζώα). Η απόκλιση
> bank ξεκινά **μέση παρτίδα (~μέρα 11-13)**, όχι μέρα 0 — συνεπές με «οι αντίπαλοι compound-άρουν
> πιο γρήγορα με μεγαλύτερη λειτουργία», το ίδιο επιχείρημα πίσω από v1f/v1g. Καμία λογιστική
> βλάβη στο replay· τίποτα δεν αμφισβητεί την κατεύθυνση scale-up.
>
> **Β.0.3 — προαιρετικό, ΔΕΝ έτρεξε πλήρως.** Το community dataset ανανεώθηκε **σήμερα**
> (2026-08-07 00:43, το "σταματά στις 08-04" δεν ισχύει πια). Το μικρό `episode_features.csv`
> (1.7MB) κατέβηκε και ελέγχθηκε: **καμία στήλη `unlocked_shops`/shop-related δεν υπάρχει** στα
> δομημένα CSV (35 στήλες, καμία). Θα χρειαζόταν πλήρες parsing του `replays.parquet`
> (**738MB**) για το effect size. **Αναβλήθηκε σκόπιμα**: αν το v1g.2 shop-adaptive work
> χρειαστεί τον ακριβή αριθμό αντί για τον θεωρητικό υπολογισμό (§0bis(γ)), μπαίνει ως
> ξεχωριστό, στοχευμένο βήμα **μέσα** στο v1g.2 — όχι τώρα.
>
> **Side finding:** ένα δεύτερο, παράλληλο session έκανε ήδη submit το v1g checkpoint στο Kaggle
> (`SUBMISSION_ID 55324447`, status COMPLETE, `publicScore 508.3`) πριν κλείσει αυτό το session —
> ρητή εντολή χρήστη, όχι πρόβλημα. Προσοχή στην ερμηνεία του score: μόνο **2 πραγματικά
> επεισόδια** έχουν παιχτεί μέχρι στιγμής (1W/1L) έναντι 23 του v1e (`publicScore 549.2`) — το
> `508.3 < 549.2` **δεν** είναι σήμα regression, είναι ασύγκλιτο μικρό δείγμα. Νέα μετρική
> `units_sold_by_product` + `day` per sale προστέθηκε στο `harness/metrics.py`'s
> `extract_metrics()` (δεν υπήρχε ήδη — το `average_sell_price` υπήρχε per-product).
>
> **Επόμενο:** `v1g.1` (engine bump 1.32.4→1.32.5) — καμία εξάρτηση από άλλα ευρήματα αυτού του
> session, μπορεί να ξεκινήσει άμεσα.

### v1f — Crew scale-up (3 → 12 hands) [ΠΡΩΤΟ]

Το φθηνότερο κομμάτι του χάσματος: fib κόστη σημαίνουν 12 hands ≈ **$232/μέρα** — ψίχουλα
μπροστά σε ό,τι παράγουν 12×23 worker-turns. Οι νικητές έχουν 1,19× peak crew / 1,23× hires,
και το `total_hires` είναι το ισχυρότερο correlate του bank (+0,76).

- **Config**: `planner.hands_target` 3 → κλιμακωτά (screen 6/8/10/12 σε DEV — όχι «κράτα το
  max», top-3 → confirm). Το `capacity_safety_factor` και το capacity gate του
  [agent/planner.py](agent/planner.py) πρέπει να **διαβάζουν το πραγματικό φορτίο** (tiles +
  ζώα + μεταφορές), αλλιώς τα έξτρα hands μένουν idle και το κόστος γίνεται καθαρή ζημιά.
- **Τεχνικά σημεία**: HIRE μπαίνει **νωρίς** στη market λίστα (μετράει στο cap των 10 orders —
  §2 Αμφισημία #2)· τα hands διαγράφονται κάθε EOD, άρα το commute είναι ημερήσιο κόστος —
  η ανάθεση tasks σε 12 units πρέπει να μείνει nearest-first με το urgency tier του
  §1.5.2 fix (`urgency_slack_margin`), που είναι ήδη σχεδιασμένο για αυτό.
- **Έλεγχος φορτίου scheduler**: το v1c-εποχής STOP ήταν capacity-related· με 13 units το
  `assign()` πρέπει να μείνει <333ms/turn. Profile πριν το gate.
- **Αποδοχή**: metric gate (`water_weeds_lost == 0` ∧ `plant_decay_units_lost == 0` ∧
  `unexplained_noops == 0`) → $-gate vs `checkpoints/v1e` → checkpoint `v1f`.

> **(στ) v1f ΟΛΟΚΛΗΡΩΘΗΚΕ 2026-08-06 — `checkpoints/v1f` δημιουργήθηκε, `hands_target=6`.**
> Screen 6/8/10/12 σε `DEV_SEEDS`: h6/h8 `IMPROVED`, h10/h12 `REGRESSED` (fixed 41 crop tiles +
> 3 ζώα δεν έχουν άλλη δουλειά πέρα από ~7-8 hands' worth of unit-turns — τα έξτρα hands μένουν
> idle, το hiring cost γίνεται καθαρή ζημιά, ακριβώς όπως προειδοποιούσε το spec). Μόνο h6/h8
> πήγαν σε holdout-confirm (`REGRESSED` = STOP, όχι μηχανικό "top-3"). Holdout αποτέλεσμα: h6
> +$2241.72/ep (se=48.97, 96/96 wins), h8 +$1107.15/ep (se=48.45, 96/96 wins) — μη επικαλυπτόμενα
> 95% CI, h6 νικητής. Metric gate (το ρητό 3-item spec εδώ, όχι το αυστηρότερο harness-wide
> `metric_gate_passed`) καθαρό και στα δύο. Σημείωση: `weeds_lost` (ευρύτερο PLANT→WEED
> counter, διαφορετικό από `water_weeds_lost`) βρέθηκε μη-μηδενικό ήδη στο `checkpoints/v1e`
> baseline (pre-existing, όχι v1f regression) — καταγράφεται εδώ ως ανοιχτό θέμα για μελλοντικό
> increment, δεν μπλόκαρε το v1f. Capacity gate στο [agent/planner.py](agent/planner.py)
> ενημερώθηκε ώστε το crop-target budget να αφαιρεί πρώτα τη σταθερή daily FEED/CARE ζήτηση
> των ζώων (`_animal_daily_demand`) πριν μοιράσει τα υπόλοιπα unit-turns σε καλλιέργειες.
> HIRE-ordering (tier 0) και nearest-first assignment επιβεβαιώθηκαν επαρκή as-is για 12+
> units, χωρίς αλλαγή κώδικα· `assign()` profiled στα 13 units: max 63.73ms, πολύ κάτω από το
> 333ms/turn όριο.

### v1g — Μάζα ζώων (3 → ~13, cow/sheep-βαρύ)

Ο ισχυρότερος compounder του παιχνιδιού (sheep cared: +$5.575/season, cow +$4.635 — §3.2#1).
Στόχος-οροφή από την ελίτ: **8 cow + 5 sheep**· το GOOSE μένει στο 1 ή αφαιρείται (15%
adoption, χαμηλό yield — μετρημένη απόφαση στο screen). Timings top-decile: cow μέρα 0,
sheep μέρα 5 — ήδη συμβατά με το v1d design.

- **Χωροθέτηση**: χρειάζονται ~11 νέα PASTURE tiles. Τα `animal_structure_tiles` επεκτείνονται
  σε NW/NE κοντά στο shed (FEED/CARE/COLLECT = ημερήσιο commute ×13) — τα strawberry targets
  χαμηλής προτεραιότητας ανακατανέμονται. **Δεν** τοποθετούνται δομές σε μη-αγορασμένη γη
  (το BUY_LAND gate απαιτεί every-planned-animal-placed — βλ. σχόλιο COOP στο config).
- **Feed logistics στα 13 ζώα = 13 wheat/μέρα.** Αυτό είναι το πραγματικό τεχνικό ρίσκο:
  - Πηγές: καλλιέργεια wheat (χωρίς sell-cliff, ίσως γι' αυτό η ελίτ κρατά wheat tiles) vs
    `BUY_PRODUCT WHEAT` (ανεβάζει την τιμή που πληρώνουμε εμείς). Screen και τα δύο μίγματα.
  - Το wheat πρέπει να είναι **στο inventory του unit πριν το FEED** (G5)· procurement ≥1
    turn νωρίτερα, reserved ledger — ήδη το v1d pattern, τώρα ×13.
  - `FEED` έχει τον ίδιο zero-slack θάνατο με το WATER (`consecutive_unfed >= 2` → escape =
    χαμένα $400-500 κεφαλαίου) — τα FEED tasks είναι tier-0 urgency.
- **CARE παντού**: cared ζώο αποδίδει `1 + interval` ανά pickup (cow ×3, sheep ×4) — το CARE
  είναι η κερδοφορία, όχι προαιρετικό. COLLECT_FERTILIZER καθημερινά (δεν συσσωρεύεται)·
  το fertilizer πωλείται ή πάει σε wheat (cap 6).
- **max_held (G8)**: pickup κάθε production day, αλλιώς η παραγωγή σταματά σιωπηλά.
- **Αποδοχή**: metric gate + `animals_escaped == 0` + 0 clipped production ticks → $-gate vs
  `v1f` → checkpoint `v1g`. Προσδοκία: εδώ ζει το μεγαλύτερο κομμάτι του $42k→$125k.

> **[ενημ. 2026-08-07] Επιπλέον έλεγχος στο v1g verdict — μη το προσπεράσεις.** Ένα καθαρό
> `IMPROVED` vs `v1f` **δεν** αποδεικνύει ότι τα ζώα 9-14 αξίζουν. Το v1f έχει 3 ζώα, άρα το v1g
> κερδίζει σχεδόν σίγουρα σε απόλυτο $ — αλλά η ερώτηση είναι αν το **marginal** ζώο είναι θετικό.
> Με ~264 μονάδες milk έναντι cliff 76 και ~160 wool έναντι cliff 59 (§0bis γ), και με το
> `compare()` να τρέχει **και τα δύο seats** (άρα σε mirror ο συνολικός όγκος **διπλασιάζεται**),
> είναι απολύτως πιθανό τα τελευταία ζώα να πουλάνε κοντά στο floor. **Αν το Β.0.1 #1/#2 δείξει
> avg sell price κάτω από τα κατώφλια, τρέξε ένα μικρό screen `{COW:8,SHEEP:5}` (τρέχον) vs
> `{6,3}` vs `{8,3}` σε `DEV_SEEDS` πριν προχωρήσεις.** Είναι φθηνό και απαντά το ερώτημα
> οριστικά· χωρίς αυτό κουβαλάμε άγνωστο κόστος σε όλα τα επόμενα increments.

> **(ζ) v1g ΟΛΟΚΛΗΡΩΘΗΚΕ 2026-08-07 — `checkpoints/v1g` δημιουργήθηκε, `targets={COW:6,SHEEP:4,
> GOOSE:0}`, `hands_target=6`.** Η ελίτ-οροφή 8 COW + 5 SHEEP (+/- 1 GOOSE, 13-14 ζώα) **ΔΕΝ**
> περνάει το metric gate σε κανένα screened `hands_target` (676-885 `animals_escaped` σε 96
> dev-screen episodes) — το feed logistics ρίσκο που προειδοποιούσε το §Feed logistics
> παραπάνω επιβεβαιώθηκε πραγματικό, όχι υποθετικό. 5 root-cause fixes χρειάστηκαν πριν
> μηδενιστούν τα escapes σε *οποιοδήποτε* μέγεθος: (1) parallel `allowed_unit`-restricted WHEAT
> PICKUP tasks αντί για ένα aggregated task/μέρα (μονός carrier αδύνατο να καλύψει 13 tiles σε
> distance ≤8 εντός 24 turns)· (2) reorder `market_orders()` ώστε το WHEAT purchase να τρέχει
> πριν το BUY_SEED/BUY_ANIMAL, όχι μετά (αντέστρεφε την τεκμηριωμένη `_ORDER_TIER` προτεραιότητα
> για την πραγματική δέσμευση cash)· (3) wheat-reserve guard (`FEED_RESERVE_DAYS=2`) στο
> BUY_ANIMAL ώστε η μαζική αγορά ζώων μέρα 0 να μην αδειάζει το bankroll πριν προλάβει να
> ταΐσει· (4) πλήρης wheat-need offer σε κάθε unit αντί για `divmod`-based rationing (το
> rationing άφηνε units υψηλού index με `count=0` όσο συρρικνωνόταν η ημερήσια ανάγκη, δομικά
> starved)· (5) urgent deadline (`urgency_slack_margin`) για ζώα ήδη σε `consecutive_unfed >= 1`
> — χωρίς αυτό το raw-position tie-break του `assign()` (`task.pos[1]` πρώτα) ευνοούσε πάντα
> το ίδιο tile έναντι ενός άλλου σε δεσμευμένη χωρητικότητα, deterministic starvation
> ανεξάρτητα από seed. **Screen sweep μεγέθους** (§απάντηση στο (στ) note παραπάνω, DEV_SEEDS,
> `both_seats=True`): 7 ζώα (4C+3S) καθαρό `IMPROVED` +$24404/ep· 10 ζώα (6C+4S) καθαρό
> `IMPROVED` +$25384/ep — **peak**· 11 ζώα (7C+4S) καθαρό αλλά χειρότερο +$18940/ep· 12 ζώα
> (7C+5S) ξανααποτυγχάνει το gate (`water_weeds_lost=15`)· 13-14 ζώα (8C+5S ± GOOSE) αποτυγχάνει
> βαριά (660-885 escapes). Νικητής: **10 ζώα (6 COW + 4 SHEEP, GOOSE αφαιρέθηκε)** — η κορυφή
> είναι πριν το feed-logistics overhead αρχίσει να τρώει την επιπλέον ζωική απόδοση, όχι στην
> ελίτ-οροφή. HOLDOUT_SEEDS confirm: `IMPROVED`, +$25343/ep (se=594.65), 96/96 episode wins vs
> `checkpoints/v1f`, 0 errors, metric gate καθαρό (0 σε όλα τα 4 hard-gate metrics). GOOSE
> αφαιρέθηκε ως μετρημένη απόφαση (15% adoption, χαμηλό yield, δεν χωράει στο 10-ζώο βέλτιστο).

### v1g.1 — Engine bump 1.32.4 → **1.32.5** [ΑΜΕΣΩΣ ΜΕΤΑ ΤΟ v1g, ΠΡΙΝ ΑΠΟ ΚΑΘΕ ΑΛΛΟ ΚΩΔΙΚΑ]

**Τι είναι:** το 1.32.5 μετακίνησε τα `DROP` / `PICKUP` / `PLACE`-into-shed **πριν** το
`if tile == "LOCKED": return` guard. Σχόλιο του ίδιου του engine: *«three of the four shed-access
tiles start LOCKED, so guarding them first would make the shed unreachable from those tiles»*.
Ολόκληρο το υπόλοιπο diff: **καμία** άλλη αλλαγή, `kaggriculture.json` κενό (§0bis).

**Γιατί μας αφορά — υπάρχει hardcoded λάθος παραδοχή:**
[agent/scheduler.py](agent/scheduler.py):182 λέει
`access = (4, 4)  # the only initially unlocked shed-access tile`. Ήταν **αληθές** στο 1.32.4·
γίνεται **ψευδές** στο 1.32.5. Τα hands γεννιούνται και στα 4 κεντρικά tiles **αγνοώντας το
LOCKED** (`SHED_ACCESS = ((4,4),(5,4),(4,5),(5,5))`, [agent/constants.py](agent/constants.py):25),
άρα σήμερα ένα hand που ξεκινά στο (5,4)/(4,5)/(5,5) πρέπει να περπατήσει **πρώτα** στο (4,4) για
κάθε PICKUP/DROP. Με το v1g αυτό είναι **13-14 WHEAT pickups + 13-14 COLLECT_FERTILIZER τη μέρα**
— επαναλαμβανόμενο κόστος 1-2 turns ανά διαδρομή, ×6 hands, ×30 μέρες.

**Πώς υλοποιείται (με τη σειρά — η σειρά είναι το μισό του βήματος):**
1. `pip install -U kaggle-environments` (→ 1.32.5) **αφού** έχει κλείσει και checkpoint-αριστεί
   το v1g.
2. `pytest tests/` — **το `test_engine_reference_matches_installed` ΘΑ κοκκινίσει· αυτό είναι το
   tripwire, όχι bug.** Ό,τι **άλλο** κοκκινίσει είναι πραγματική αλλαγή συμπεριφοράς και θέλει
   διερεύνηση πριν προχωρήσεις.
3. Refresh του `engine_reference/` (και τα 4 αρχεία: `.py`, `.json`, `README.md`, `AGENTS.md` — το
   tripwire συγκρίνει και τα markdown, memory.md 2026-08-06).
4. **Ξανά-baseline**: `create_checkpoint` δεν αρκεί — τρέξε `compare(checkpoints/v1g,
   checkpoints/v1g, DEV_SEEDS)` **στο νέο engine** για να δεις πόσο μετακίνησε το ίδιο το engine
   τα απόλυτα νούμερα. Κάθε επόμενο gate συγκρίνεται σε αυτό το νέο baseline.
5. **Μόνο τότε** η αλλαγή κώδικα: αντικατάσταση του `access = (4, 4)` με «κοντινότερο tile από το
   `SHED_ACCESS` ως προς τη θέση του unit».

**Παγίδες που περιμένω:**
- ⚠️ **Το `access` δεν είναι μόνο προορισμός, είναι και σημείο εκκίνησης υπολογισμού απόστασης.**
  Αν το `assign()` υπολογίζει `best_distance` με βάση το (4,4), αλλάζοντας τον προορισμό αλλάζεις
  σιωπηλά και το sort key του scheduler (`task_slack = deadline_step - step - (best_distance+1)`,
  §1.5.2). Δηλαδή ένα «καθαρά logistics» fix μπορεί να μετακινήσει την **προτεραιοποίηση** — grep
  για κάθε χρήση του `access` πριν αλλάξεις τη μία γραμμή.
- ⚠️ **Ο κανόνας `_is_shed_adjacent` δεν άλλαξε** — μόνο ο LOCKED guard. Μην υποθέσεις ότι
  «οποιοδήποτε tile δίπλα στο κέντρο» δουλεύει· είναι πάντα ακριβώς τα 4.
- ⚠️ **Το submission bundle κουβαλά `agent/_vendored.py`** με αντιγραμμένες σταθερές. Αν το 1.32.5
  είχε αλλάξει σταθερά, το vendored fallback θα ήταν σιωπηλά παλιό. Εδώ **δεν** άλλαξε καμία
  (json diff κενό), αλλά ο έλεγχος parity πρέπει να ξανατρέξει ως μέρος του βήματος 2.
- ⚠️ **Η ladder μπορεί να τρέχει άλλη έκδοση από εμάς.** Το bump μας ευθυγραμμίζει με το PyPI
  latest, όχι απαραίτητα με τον server. Αν το fix εκμεταλλευτεί συμπεριφορά που ο server δεν έχει
  ακόμα, τα PICKUP/DROP από locked tiles γίνονται **σιωπηλά no-ops** (το engine δεν πετά ποτέ
  σφάλμα) — δηλαδή hands που «δουλεύουν» χωρίς αποτέλεσμα. **Mitigation:** το fix να είναι
  **degradation-safe** — αν το PICKUP από locked tile αποτύχει, το επόμενο turn ο ίδιος unit
  βρίσκεται ήδη ένα βήμα από το (4,4)· διάλεξε το κοντινότερο **ξεκλείδωτο** tile όταν υπάρχει
  ισοπαλία απόστασης, ώστε η χειρότερη περίπτωση να είναι «ίδια συμπεριφορά με σήμερα».
- **Αποδοχή:** metric gate → $-gate vs `checkpoints/v1g` **στο νέο engine** → checkpoint `v1g.1`.

### v1g.2 — Shop-adaptive market layer + fertilizer timing

**Γιατί τώρα και όχι στο v1i:** το §0bis(γ) δείχνει ότι σε **34,4%** των μελλοντικών επεισοδίων
τα 5 sheep θα παράγουν προϊόν χωρίς αγοραστή. Αλλά **και σήμερα** η σειρά ξεκλειδώματος είναι
τυχαία ανά episode — απλώς σήμερα ξεκλειδώνουν τελικά **όλα** τα 8, οπότε το ρίσκο είναι θέμα
*χρονισμού* αντί *ύπαρξης*. Το feature αποδίδει και στα δύο καθεστώτα, άρα δεν είναι στοίχημα
στην ανακοίνωση.

**(α) Επαναφορά του `unlocked_shops` στο snapshot.** Το [agent/state.py](agent/state.py):14 το
αφαίρεσε ως «zero real readers» (review L9) — σωστά τότε, λάθος τώρα. Είναι **δημόσιο πεδίο**
(`obs.town.unlocked_shops`), μηδενικό κόστος ανάγνωσης.

**(β) Παράγωγη μετρική: `npc_daily_demand[product]`.** Υπολογίζεται **ακριβώς**, όχι κατ' εκτίμηση,
από δύο πράγματα που ξέρουμε ντετερμινιστικά:
```
per_shop = 2 if len(SHOPS[shop]) == 1 else 1        # single-product shops αγοράζουν διπλά
ticks_per_day = turns_per_day // townShopSellInterval    # 24 // 4 = 6
demand[p] = Σ_over_unlocked_shops( per_shop if p in SHOPS[shop] ) * ticks_per_day
          + town_center_units_per_day(p)             # 2 σήμερα (×ramp), 1 μετά την αλλαγή
```
Οι `SHOPS` και τα intervals είναι **importable από το engine** (ήδη το κάνουμε στο
[agent/constants.py](agent/constants.py)) — καμία hardcoded παραδοχή.

**(γ) Πού καταναλώνεται η μετρική.** Δύο σημεία, όχι περισσότερα:
1. **`sell_floor_price` δυναμικό**: το σημερινό `CONFIG["executor"]["sell_floor_price"]` είναι
   στατικός πίνακας. Γίνεται `max(static_floor, f(npc_daily_demand))` — όταν η ημερήσια ζήτηση
   ενός προϊόντος είναι ~0, το να το πουλάς επιθετικά είναι **αυτοκαταστροφή**: κατεβάζεις μόνιμα
   την τιμή χωρίς κανείς να την ανεβάζει πίσω.
2. **Ρυθμός πώλησης (units/turn)**: πούλα ανά μέρα το πολύ όσο απορροφά η ζήτηση + ένα μικρό
   περιθώριο. Αυτό είναι το ίδιο trickle logic που ήδη υπάρχει — αλλάζει μόνο το *κατώφλι*.

**(δ) Fertilizer: πούλα νωρίς, πάντα.** Ξεχωριστός κανόνας γιατί η ζήτηση είναι **μηδενική εξ
ορισμού** (§0bis 0bis.2#1): η τιμή είναι μονότονα φθίνουσα, άρα το «περίμενε καλύτερη τιμή» είναι
πάντα λάθος. Πρακτικά: FERTILIZER SELL με **πρώιμο order index** (πριν από τα SELL των προϊόντων
που έχουν NPC ζήτηση και θα ανακάμψουν), κάθε μέρα, χωρίς floor πέρα από ένα μικρό ελάχιστο.

> **[ενημ. 2026-08-07, §Β.0]** Εμπειρικά επιβεβαιωμένο, όχι μόνο θεωρητικό: 2 seeds (main.py vs
> `checkpoints/v1f`) έδειξαν **median FERTILIZER sale day = 18** (meta πουλά μέρα 3) — το (δ) πιο
> πάνω λύνει ακριβώς αυτό.

**(α.1) Sub-step αναβεβλημένο από το Β.0, μπαίνει εδώ αν χρειαστεί:** το effect size του
`unlocked_shops` στο τελικό bank (episodes με/χωρίς YARN_STORE) **δεν** υπάρχει σε κανένα
δομημένο CSV του community dataset (`episode_features.csv`, 35 στήλες, ελέγχθηκε 2026-08-07) —
θα χρειαστεί parsing του raw `replays.parquet` (**738MB**). Αν το (α)/(γ) παραπάνω χρειαστεί τον
ακριβή αριθμό αντί για τον θεωρητικό υπολογισμό του §0bis(γ) για να βαθμονομηθεί, αυτό το
parsing μπαίνει **εδώ**, ως στοχευμένο βήμα μέσα στο v1g.2 — όχι νωρίτερα.

**Παγίδες:**
- ⚠️ **Μην αλλάξεις το crop mix με βάση τα shops.** Είναι δελεαστικό («άνοιξε PET_CAFE ⇒ φύτεψε
  carrot»), αλλά τα shops ξεκλειδώνουν **κάθε 3 μέρες** ενώ το strawberry θέλει 16 μέρες ως
  παραγωγή — τη στιγμή που ξέρεις τη ζήτηση, η απόφαση φύτευσης έχει ήδη ληφθεί. **Το feature
  αφορά ΜΟΝΟ την πώληση**, όχι τον planner. (Το crop mix προσαρμόζεται μέσω του v1h′ portfolio,
  με μετρημένο gate.)
- ⚠️ **Το 10-order cap.** Ένα δυναμικό sell layer τείνει να παράγει περισσότερα SELL orders. Το
  engine κόβει `q[:10]` **positional, όχι priority-aware** (memory.md 2026-08-06 (στ)) — άρα κάθε
  νέο order σπρώχνει έξω το τελευταίο. Το `_ORDER_TIER` πρέπει να επανελεγχθεί: HIRE μένει tier 0.
- ⚠️ **Μην κάνεις το floor συνάρτηση της *στιγμιαίας* τιμής** — θα ταλαντωθεί (πουλάς → πέφτει η
  τιμή → σταματάς → ανεβαίνει → πουλάς). Συνάρτηση της **ζήτησης** (σταθερή μέσα στη μέρα), όχι
  της τιμής.
- ⚠️ **G13 determinism**: καμία ανάγνωση `unlocked_shops` δεν επιτρέπεται να εξαρτάται από
  **σειρά iteration set/dict** — το `unlocked_shops` είναι list, κράτα τη σειρά της ή ταξινόμησε.
- **Αποδοχή**: metric gate → $-gate vs `v1g.1` → checkpoint `v1g.2`. **Επιπλέον gate ειδικά γι'
  αυτό το feature**: ένα ad-hoc run με **χειροκίνητα περιορισμένο** `unlocked_shops` (π.χ. χωρίς
  YARN_STORE) πρέπει να δείξει ότι ο agent **σταματά** να ξεπουλά wool — αλλιώς το feature είναι
  γραμμένο αλλά ανενεργό. Αυτό δεν το πιάνει κανένα seed-based gate, γιατί σήμερα ξεκλειδώνουν όλα.

### v1h′ — 3ο quadrant (SW)

- **Trigger όπως το NE**: reserve-based (`land.min_reserve`), όχι hardcoded μέρα — η ελίτ
  αγοράζει το #3 γύρω στη μέρα 11, αλλά το δικό μας self-regulating trigger (χρήματα + διαθέσιμο
  workforce) απέδωσε ήδη στο v1c. SW = $2k. **SE ($4k): ΔΕΝ αγοράζεται** — κανείς στην ελίτ
  δεν το κάνει (topfarms-19)· μόνο με μετρημένο λόγο.
- **Χρήση SW**: επέκταση pasture/strawberry με βάση ό,τι κέρδισε στο v1g screen — όχι
  αυτόματο mirror των NW counts (το v1c δίδαγμα: ο 1:1 mirror του carrot έσκασε στην
  κοινή αγορά· `ne_carrot_tiles: 3`, όχι 7).

> **[ενημ. 2026-08-07] Το «rebalance χαρτοφυλακίου» αφαιρέθηκε από τον τίτλο και από το scope.**
> Στηριζόταν στη σύγκλιση προς το modal top farm, το οποίο αποδείχθηκε **measurement artifact**
> (§0 ⚠️γ): τα crops δεν επιβιώνουν ως τη μέρα 30 στο engine, άρα το «8 cow + 6 sheep, καθόλου
> crops» μετρά **επιζώσες δομές**, όχι στρατηγική. Ένα rebalance προς αυτό θα ήταν αντιγραφή
> σφάλματος μέτρησης. Το SW παραμένει (η γη είναι μετρήσιμα ωφέλιμη), το portfolio όχι.
>
> **Τι αλλάζει πρακτικά στη χρήση του SW, με βάση τη νέα ιεράρχηση (§0bis δ):**
> - **WHEAT ανεβαίνει σε πραγματικό crop, όχι μόνο ζωοτροφή.** 5/8 shop κάλυψη (P(κανένα) =
>   0,04%), **καμία cliff** (>2.000 μονάδες ως το floor έναντι 59-76 για wool/milk), και με 13-14
>   ζώα έχουμε **δωρεάν fertilizer** που το ανεβάζει στο cap 6 μονάδων/tile. Είναι το μόνο προϊόν
>   που δεν μπορούμε να κορέσουμε, και το meta το πουλά ήδη από τη **μέρα 2**.
> - **WOOL/MILK δεν επεκτείνονται στο SW** μέχρι να απαντηθεί το Β.0.1 #1/#2. Αν είμαστε ήδη σε
>   κορεσμό στα 13-14 ζώα, το SW pasture είναι **αρνητικής αξίας**, όχι απλά μηδενικής.
> - **CARROT όχι** (10% κίνδυνος να μη ξεκλειδώσει αγοραστής + το v1c εύρημα ότι καταρρέει πρώτο).
>
> ⚠️ **Παγίδα του BUY_LAND gate:** το gate απαιτεί **κάθε planned animal ήδη τοποθετημένο** πριν
> αγοράσει γη (comment COOP στο [agent/config.py](agent/config.py)). Αν το v1h′ προσθέσει
> animal targets στο SW, δημιουργείται **circular deadlock**: δεν αγοράζεις SW γιατί υπάρχει
> ατοποθέτητο ζώο, και δεν τοποθετείται γιατί το tile του είναι στο SW. Το ίδιο λάθος έχει ήδη
> αποφευχθεί δύο φορές (COOP στο v1e, PASTURE στο v1g — και τα δύο έμειναν στο NW γι' αυτόν
> ακριβώς τον λόγο). **Κάθε νέα δομή στο SW απαιτεί πρώτα αλλαγή του gate**, όχι απλή προσθήκη
> tile στο config.

- **Αποδοχή**: metric gate → $-gate vs `v1g.2` → checkpoint `v1h`. Μετά το v1h, ξανατρέχει το
  Φάσης-1 συνολικό κριτήριο σε νέο επίπεδο: median vs starter — και **2ο submission αν
  holdout-confirm `IMPROVED`** έναντι του v1e που ήδη ανέβηκε.

### v1i — Sell-ahead arbitrage (άξονας β — «πούλα πριν το κύμα»)

Πρώτο market-intelligence feature, **μετά** την κλίμακα (χωρίς όγκο παραγωγής δεν υπάρχει τι
να χρονίσεις). Η απόδειξη αξίας: one-turn preemption = 31-1 σε mirrors, +$2.304 μέσο margin
([agents-1](docs/meta/ladder_snapshots.md#agents-1))· και το BT μετρά W/L — mirrors που
κρίνονται σε +$3 είναι πραγματικότητα της κορυφής.

- **Μηχανισμός (MASTERPLAN §3.3):** πρόβλεψη του sell wave από τρεις πηγές, καμία hardcoded:
  1. **Meta ημερολόγιο ως prior** ([topfarms-22](docs/meta/ladder_snapshots.md#topfarms-22)):
     strawberry 1η πώληση ~μέρα 16, melon ~10, wool ~9, milk ~8 — *πρώτη βαθμονόμηση, θα
     μετακινηθεί* (το V13-R3 είναι δημόσιο και θα αντιγραφεί).
  2. **Ζωντανό market inventory** έναντι των γνωστών cliffs 1.32.x: **strawberry 62 / wool
     59 / milk 76 / melon 158** net μονάδες ως το $1 floor· wheat χωρίς cliff
     ([docs/reference/market.md](docs/reference/market.md)).
  3. **Ορατά ώριμα tiles του αντιπάλου** (η φάρμα του είναι δημόσια — §2): πόσες μονάδες
     ωριμάζουν και πότε ⇒ πότε θα χτυπήσει το κύμα του την αγορά.
- **Εκτέλεση**: μετάθεση των δικών μας SELL **πριν** το προβλεπόμενο κύμα, trickle
  (unit-by-unit lockstep — πλεονέκτημα μόνο σε προγενέστερο order index, §2 Αμφισημία #3),
  ποτέ dump που ανοίγει εμείς το cliff. Το `market_price()` είναι importable από το engine —
  ο υπολογισμός marginal revenue είναι ακριβής, όχι εκτίμηση.

> **[ενημ. 2026-08-07] Δύο συγκεκριμένες βελτιώσεις που μπαίνουν εδώ:**
>
> **(1) Ακριβές άθροισμα αντί endpoint.** Το [agent/executor.py](agent/executor.py):89 ελέγχει
> `market_price(product, inventory + sell_units + safety_units) > floor`. Επειδή η εκτέλεση είναι
> **per-unit με pre-sell quote**, το πραγματικό έσοδο είναι `Σ_{i=0..q-1} p(s+i)` και η **πρώτη**
> μονάδα εισπράττει `p(s)`, όχι `p(s+q)`. Ο σημερινός έλεγχος είναι **συντηρητικός** (υποεκτιμά ⇒
> δεν πουλάμε ενώ θα έπρεπε) — **όχι bug**, αλλά χαμένο έσοδο σε ρηχές καμπύλες. Αντικατάσταση με
> άθροιση μονάδα-μονάδα: πούλα όσο η **επόμενη** μονάδα αποδίδει `p(s+i) > floor`.
> ⚠️ **Παγίδα:** μην αντικαταστήσεις το `safety_units` με το άθροισμα — είναι δύο διαφορετικά
> πράγματα. Το `opponent_price_safety_units` μοντελοποιεί το **δικό του** ταυτόχρονο SELL στο ίδιο
> index (lockstep), το άθροισμα μοντελοποιεί τη **δική μας** ολίσθηση. Χρειάζονται και τα δύο.
>
> **(2) Το prior ημερολόγιο μετακινήθηκε — όπως προβλέφθηκε.** Σύγκριση
> [topfarms-22](docs/meta/ladder_snapshots.md#topfarms-22) (08-05) με το
> [08-07 snapshot](docs/meta/ladder_snapshots.md#meta0807) (δεδομένα 08-06):
> **milk 8 → 10 · strawberry 16 → 18 · wool 9 → 9 · melon 10 → 10**, και νέο:
> **fertilizer μέρα 3, από 1.366/1.366 seats**. Δύο από τα τέσσερα μετακινήθηκαν κατά 2 μέρες
> **μέσα σε μία μέρα ladder**. Αυτό είναι η εμπειρική απόδειξη του MASTERPLAN §3.3 warning:
> **το ημερολόγιο είναι seed για bootstrap, ποτέ σταθερά**. Αν ο v1i μηχανισμός χρειάζεται
> hardcoded μέρα για να δουλέψει, είναι λάθος σχεδιασμένος.
- **Όριο (Ανοιχτό #11)**: χρησιμοποιούμε **στατιστικά** του meta (πότε πουλάνε), ποτέ
  trajectories/routes. Καμία αντιγραφή του V13-R3 κώδικα — είναι evidence, όχι πηγή.
- **Αποδοχή**: $-gate vs `v1h` **και** mirror-margin έλεγχος (να μη χαλάει το δικό μας mirror).

### Μετά τα increments: BBO sweeps (προτεραιότητα #6)

CMA-ES/Optuna στο `CONFIG` **μόνο αφού** υπάρχουν τα v1f-v1i features — πριν από αυτά
βελτιστοποιεί σε λάθος ταβάνι (§3.4). Στο screen→confirm πρωτόκολλο, ποτέ «κράτα το max».

---

## ΜΕΡΟΣ Γ — Bench & robustness (άξονες γ, δ — τρέχει παράλληλα, κλείνει ~20/09)

1. **Mirror margin metric** στο bench (§7#3): κάθε compare καταγράφει και το margin σε
   mirror matches, όχι μόνο W/L — η κορυφή κρίνεται σε ψίχουλα (+$3).
2. **Robustness matrix Φάσης 3** με «αυριανά» σενάρια, όχι μόνο σημερινούς flooders:
   αντίπαλοι με δικό τους sell-ahead· sell ημερολόγια μετατοπισμένα **±2-4 μέρες** από το
   topfarms-22· wheat/staple-βαριά fields· mono-crop flooders κάθε προϊόντος· do-nothing
   (optimization ceiling). Tuning που κερδίζει οριακά σήμερα αλλά καταρρέει σε μετατοπισμένο
   ημερολόγιο **απορρίπτεται**.

   > **[ενημ. 2026-08-07] Τρία νέα υποχρεωτικά σενάρια ζήτησης** — δεν καλύπτονται από κανένα
   > seed, γιατί σήμερα ξεκλειδώνουν πάντα **και τα 8** shops. Απαιτούν χειροκίνητο override του
   > `unlocked_shops` (ή `env.configuration`), όχι νέο seed set:
   >
   > | Σενάριο | Πώς στήνεται | Τι πρέπει να αποδειχθεί |
   > |---|---|---|
   > | **Χωρίς YARN_STORE** | `unlocked_shops` χωρίς `YARN_STORE` | Ο agent **σταματά** να ξεπουλά wool· δεν κρατά 5 sheep σε καθαρή ζημιά |
   > | **Διπλά shops** | π.χ. 3× `FARMERS_MARKET` + 2× `BAKERY` | Το sell rate ανεβαίνει εκεί που υπάρχει διπλή ζήτηση — αλλιώς το §v1g.2(β) δεν διαβάζεται πουθενά |
   > | **Flat town center** | `townCenterSellInterval = 24` + patched `TOWN_CENTER_DEMAND_SCHEDULE` σε `[(0,1)]` | Το late-game sell timing δεν καταρρέει όταν φύγει το ×4 ramp |
   >
   > ⚠️ Το τρίτο σενάριο **προσομοιώνει την ανακοινωμένη αλλαγή πριν κυκλοφορήσει** — είναι ο
   > φθηνότερος τρόπος να ξέρουμε αν μας πονάει, χωρίς να στοιχηματίσουμε τίποτα πάνω της.
   > Στήνεται με monkeypatch στο **harness**, ποτέ στο `agent/` (θα μόλυνε το submission).

3. **Meta refresh πριν τη Φάση 3**: re-download του community dataset (υποχρεωτικό —
   MASTERPLAN §3.2bis freshness note· snapshot μας: **08-04**) + νέα μέρα topfarms για το
   consensus anomaly και τη wheat-primary επιβεβαίωση. **Νέο ερώτημα προς το dataset (Β.0.3):**
   effect size του `unlocked_shops` στο τελικό bank — ποτέ δεν το έχουμε κοιτάξει.
4. **Engine bump detector**: σε κάθε νέο `kaggle-environments` στη ladder →
   `pip install -U` + `pytest tests/` — ό,τι κοκκινίσει είναι η αλλαγή συμπεριφοράς.
   Το 1.32.4 μένει pinned μέχρι να περάσει το suite στη νέα έκδοση.

   > **[ενημ. 2026-08-07] Ο detector έγινε συγκεκριμένος και πρέπει να τρέχει ΧΩΡΙΣ install.**
   > Η διαδικασία που χρησιμοποιήθηκε για να ανιχνευθεί το 1.32.5 ενώ έτρεχε το v1g gate — και
   > είναι η **σωστή** διαδικασία γενικά, γιατί δεν πειράζει το ενεργό περιβάλλον:
   >
   > ```powershell
   > pip index versions kaggle-environments            # LATEST vs INSTALLED
   > pip download kaggle-environments==<νέα> --no-deps --no-binary :all: -d <scratchpad>
   > tar -xzf ...; diff -u engine_reference/kaggriculture.py <extracted>/kaggriculture.py
   > diff -u engine_reference/kaggriculture.json <extracted>/kaggriculture.json   # ⚠️ ΜΗΝ το παραλείψεις
   > ```
   >
   > ⚠️ **Το `.json` diff είναι εξίσου σημαντικό με το `.py`** — εκεί ζουν τα
   > `townCenterSellInterval`, `turnsPerDay`, `maxMarketOrdersPerTurn`, `shedCapacity`. Μια balance
   > change μπορεί να είναι **αποκλειστικά** json και να μη φαίνεται καθόλου στον κώδικα.
   > ⚠️ **Ο έλεγχος γίνεται τακτικά, όχι μόνο όταν κάτι σπάσει.** Οι οργανωτές έχουν ήδη
   > ανακοινώσει balance changes (§0bis)· η επόμενη έκδοση είναι πιθανόν αυτή που τις φέρνει, και
   > θέλουμε να το μάθουμε από diff, όχι από ανεξήγητη πτώση rating.

---

## Πρωτόκολλο (αμετάβλητο — ισχύει για κάθε gate αυτής της φάσης)

- **Seeds**: `DEV_SEEDS` 0-47 (screening) · `HOLDOUT_SEEDS` 100-147 (μόνο confirm, καμία
  tuning απόφαση) · `SMOKE_SEEDS` 0-11 (ποτέ GO) · `CONFIRM2_SEEDS` 200-247 **καμένο** για το
  v1c ερώτημα ([harness/seeds.py](harness/seeds.py)). GO **μόνο** από `stage=holdout-confirm`
  με `metrics_checked` και καθαρό metric gate.
- **Metric gates πριν το $-verdict**: `water_weeds_lost == 0` ∧ `plant_decay_units_lost == 0`
  (+ ανά increment: `animals_escaped`, clipped ticks, `unexplained_noops`).
- **Immutable checkpoint** σε **κάθε** αποδεκτή κατάσταση, με fingerprint verification (G15).
- **Both seats πάντα** — το weed RNG είναι seat- και opponent-tile-fill-εξαρτώμενο (§2 #6).
- **Ρητά εκτός** (standing αποφάσεις, δεν επανεξετάζονται χωρίς νέα δεδομένα): RL (μόνο στον
  4-πλό trigger του §4)· BC/IL/trajectory copying και κάθε replay-derived prior (Ανοιχτό #11)·
  W&B (τοπικό HTML report)· εκτέλεση κώδικα από competitor notebooks (evidence, όχι πηγή).

## Χρονοδιάγραμμα (ενδεικτικό)

| Βήμα | Στόχος | Κατάσταση |
|---|---|---|
| Α. Submission v1e + baselines | 08-06 | ✅ **ΕΓΙΝΕ** (SUBMISSION_ID 55301989) |
| v1f crew | 08-06 | ✅ **ΚΛΕΙΣΤΟ** (`hands_target=6`) |
| v1g ζώα | 08-07 | 🔄 **ΤΡΕΧΕΙ** |
| **Β.0 συλλογή δεδομένων από v1g report** | 08-08 | ⏸ αμέσως μετά το v1g |
| **v1g.1 engine bump 1.32.5 + shed access** | 08-08 → 08-09 | ⏸ *πριν από κάθε άλλο κώδικα* |
| **v1g.2 shop-adaptive + fertilizer timing** | 08-09 → 08-13 | ⏸ |
| v1h′ SW quadrant (**χωρίς** portfolio rebalance) (+2ο submission αν IMPROVED) | 08-13 → 08-18 | ⏸ |
| v1i sell-ahead (+ exact per-unit sum) | 08-18 → 08-28 | ⏸ |
| BBO sweeps + Φάση 3 robustness (**+3 σενάρια ζήτησης**) | Σεπτέμβριος → ~09-20 | ⏸ |
| Champion/challenger κλείδωμα 2 slots | 09-23 → 09-30 | ⏸ |

> **Το v1g.2 πήρε 4 μέρες, όχι 1**, επειδή περιλαμβάνει και το ad-hoc gate με χειροκίνητο
> `unlocked_shops` — που είναι **η μόνη** επαλήθευση ότι το feature πραγματικά ενεργοποιείται.
> Ένα shop-adaptive layer που περνά τα seed gates αλλά δεν αλλάζει ποτέ συμπεριφορά είναι
> χειρότερο από το τίποτα: κουβαλά την πολυπλοκότητα χωρίς το όφελος.

Ο χρόνος δεν είναι ο περιοριστικός πόρος — η ποιότητα του gate είναι. Κανένα βήμα δεν
προσπερνά το confirm για να «προλάβει» την ημερομηνία του πίνακα.
