# MASTERPLAN — Kaggriculture Competitive Agent

> Βασισμένο αποκλειστικά στο περιεχόμενο του repo: [README.md](engine_reference/README.md), [discussion.md](docs/source/discussion.md),
> [competition_info.md](docs/source/competition_info.md) (επίσημη σελίδα διαγωνισμού: Overview, Timeline, Evaluation,
> How to Play, CLI workflow, FAQ),
> [kaggriculture-getting-started.ipynb](notebooks/kaggriculture-getting-started.ipynb),
> [kaggriculture-visualized-what-every-crop-pays.ipynb](notebooks/kaggriculture-visualized-what-every-crop-pays.ipynb).
> Το engine (`kaggriculture.py`) **δεν βρίσκεται στο repo** — ζει στο πακέτο `kaggle-environments`
> (η ladder τρέχει ≥1.32.3, το viz notebook έτρεξε σε 1.32.4). Όπου docs και engine διαφωνούν,
> **υπερισχύει το engine** — οι γνωστές αποκλίσεις καταγράφονται στην §7.
>
> **Οδηγός παραπομπών (reorg 2026-08-06 — μόνο διαδρομές άλλαξαν, κανένα περιεχόμενο):**
> `README.md:NNN` → [engine_reference/README.md](engine_reference/README.md) (το πρώην
> `docs/game_rules.md` ήταν byte-identical αντίγραφό του και διαγράφηκε)·
> `discussion.md:NNN` → [source/discussion.md](docs/source/discussion.md)·
> `competition_info.md:NNN` → [source/competition_info.md](docs/source/competition_info.md)·
> `viz cell N` / `meta cell N` → `## cell [N]` στο [source/notebooks/](docs/source/notebooks/), με τους
> αριθμούς συγκεντρωμένους σε [reference/economics.md](docs/reference/economics.md),
> [reference/market.md](docs/reference/market.md) και [meta/ladder_snapshots.md](docs/meta/ladder_snapshots.md).
> Πλοήγηση σε όλα: [INDEX.md](docs/INDEX.md).

---

## 1. Περίληψη κανόνων — μόνο ό,τι επηρεάζει αποφάσεις

### Δομή παιχνιδιού
- 2 παίκτες, **ξεχωριστές φάρμες 10×10** (4 τεταρτημόρια 5×5), **κοινή αγορά**. Καμία φυσική αλληλεπίδραση — μόνο μέσω τιμών (README.md:132, discussion.md:140).
- **720 turns = 30 μέρες × 24 turns** (README.md:35). Start: $3.000, τεταρτημόριο NW, 1 farmer, shed στο κέντρο.
- **Νίκη: περισσότερα χρήματα στην τράπεζα στο τέλος. Απούλητο inventory ΔΕΝ μετράει** (README.md:248-254). Μόνο το αποτέλεσμα (W/L/T) κινεί rating, όχι το περιθώριο (viz cell 57).

### Χρονισμός ημέρας (κρίσιμο)
- Κάθε turn: 1 action ανά μονάδα (farmer + hands) + έως **10 market orders** (README.md:94, 354).
- Σειρά επεξεργασίας turn: validation → player actions → market queue → town consumption → day/market refresh (README.md:236-246).
- **End of day**: έλεγχος unwatered/unfed (2 συνεχόμενες μέρες = weed/απόδραση), παραγωγή, **auto-drop όλων των inventories στο shed (cap 100 — το πλεόνασμα καταστρέφεται)**, τα hands εξαφανίζονται, ο farmer γυρνά στο shed το πρωί, τυχαία weeds (README.md:147, 165· viz cell 8-9).
- **Η μέρα φύτευσης μετράει ως 1η άποτιστη μέρα**: σπόρος που δεν ποτίστηκε τη μέρα φύτευσης γίνεται weed το ίδιο βράδυ (README.md:113, discussion.md:23). Νέο ζώο ξεκινά με `consecutive_unfed = 0` — επιβιώνει την 1η μέρα άταιστο (README.md:115).

### Καλλιέργειες & ζώα (νούμερα από το engine — viz cells 11-19)
| | Κόστος | Base $ | Παραγωγή |
|---|---|---|---|
| Wheat | 10 | 25 | one-shot, ημ. 4· max 4 με πότισμα, **6 μόνο με λίπασμα** |
| Carrot | 20 | 35 | one-shot, ημ. 3· max 3 με πότισμα, 4 με λίπασμα — **ταχύτερο turnover** |
| Tomato | 50 | 60 | ongoing: +1/μέρα, ηλικίες 8-11 (×4 σύνολο), μετά decay |
| Strawberry | 100 | 120 | ongoing: +1 στις ηλικίες 10/12/14/16 (×4 σύνολο), μετά decay — **όχι απεριόριστη** |
| Melon | 80 | 250 | one-shot· cap 6 στην **ημέρα 10** (όχι 12) με καθημερινό πότισμα |
| Goose | 300 + coop | egg 50 | από ημ. 4, κάθε 1 μέρα· max_held 4 |
| Cow | 400 + pasture | milk 160 | από ημ. 8, κάθε 2 μέρες· max_held 6 |
| Sheep | 500 + pasture | wool 200 | από ημ. 6, κάθε 3 μέρες· max_held 6 |

- **Bonus window one-shot**: από ⌈max_yield_day/2⌉, +1 μονάδα/ποτισμένη μέρα (+2 με λίπασμα), cap στο max_yield (README.md:123-124).
- **CARE (engine)**: κάθε μέρα fed+cared → `pending_care_bonus += 1`· καταβάλλεται ολόκληρο στην επόμενη προγραμματισμένη παραγωγή *αν* το ζώο είναι ταϊσμένο τότε (README.md:75-80). Άρα cared ζώο αποδίδει `1 + interval` ανά pickup: goose ×2, cow ×3, sheep ×4. **Season totals (αγορά ημέρα 0, base prices, feed στα $25, χωρίς credit λιπάσματος): goose +1.675 / cow +4.635 / sheep +5.575 cared — έναντι +275 / +635 / +375 μόνο fed** (viz cell 19). Το CARE είναι αυτό που κάνει τα ζώα κερδοφόρα, όχι προαιρετικό extra.
- **Λίπασμα**: 1/ζώο/μέρα δωρεάν (χωρίς CARE, χωρίς συσσώρευση — collect πριν το επόμενο), ή αγορά $100. Είναι ο **μόνος δρόμος για wheat στο cap 6** (viz cell 17). Πωλείται κανονικά (επιβεβαίωση οργανωτή, discussion.md:102-104).

### Αγορά (ο πυρήνας του παιχνιδιού)
- Σπόροι/ζώα: απεριόριστη προσφορά, **σταθερές τιμές**. Οι τιμές πώλησης προϊόντων κινούνται με το inventory γύρω από `I0 = 10.000`, **ασύμμετρες καμπύλες ανά προϊόν** (README.md:206-232). Floor $1· **πωλήσεις στο floor δεν προσθέτουν inventory** (README.md:196).
- Orders εκτελούνται **unit-by-unit ταυτόχρονα** μεταξύ παικτών· ή τιμή γλιστράει *ενώ* πουλάς (README.md:194). Buy price = post-buy, sell price = pre-sell (README.md:202).
- **Staples αντέχουν glut, premium καταρρέουν**: melon φτάνει το floor $1 μετά από **158 net μονάδες** (τετραγωνική above-curve), ενώ wheat μετά από 400 μονάδες πουλά ακόμα $20 (viz cell 29). Dump 100 melons μονομιάς: εισπράττεις $21.721 από τα $25.000 της αρχικής τιμής — 87% (viz cell 31).
- `BUY_PRODUCT` μόνο για **WHEAT και FERTILIZER** (README.md:200).
- **Town = μοτέρ ζήτησης**: shops ξεκλειδώνουν κάθε 3 μέρες (τυχαία σειρά από 8), καθένα τρώει το μενού του κάθε 4 turns (6 μον./προϊόν/μέρα, single-product ×2 = 12/μέρα)· town center κάθε 12 turns, **×2 από μέρα 10, ×4 από μέρα 20** (README.md:169-173· viz cell 34). **Κανένα shop δεν αγοράζει melon ή fertilizer** — το melon στηρίζεται μόνο στο town center → η πιο εύθραυστη τιμή του παιχνιδιού (viz cell 35).

### Εργασία, γη, logistics
- **HIRE**: n-οστή πρόσληψη της μέρας κοστίζει `fib(n)` (1,1,2,3,5,8,13…), reset κάθε πρωί· τα hands φεύγουν το βράδυ (README.md:155-157). **5 hands = 12 coins = έως 115 worker-turns/μέρα** — τα actions είναι ο σπάνιος πόρος και τα hands σχεδόν δωρεάν (viz cells 22-23).
- Hands spawn στα 4 κεντρικά tiles (4,4),(5,4),(4,5),(5,5) **αγνοώντας αν είναι LOCKED**· locked tiles είναι πλέον διασχίσιμα (engine ≥1.32.3), αλλά το (5,5) πρώιμα είναι περικυκλωμένο από locked (README.md:158-159, discussion.md:34).
- **BUY_LAND**: σταθερή σειρά NE $1k → SW $2k → SE $4k (README.md:107· viz cell 6). Τεταρτημόριο 25 tiles αποσβένει σε <7 μέρες με μέτρια $25/tile-day (viz cell 26) — το πραγματικό κόστος είναι η εργασία και το commute από το shed.
- Shed: **cap 100 non-seed items**, σπόροι σε ξεχωριστό απεριόριστο slot (README.md:147). Το shed ΔΕΝ είναι tile — πρόσβαση μόνο από τα 4 κεντρικά tiles (README.md:149).
- **Invalid actions = σιωπηλά no-ops** — το engine δεν πετά σφάλμα ποτέ (viz cell 38).
- Χρόνος: `actTimeout` **1 s/turn + 60 s overage** συνολικά (viz cell 51-52) — τεράστιο περιθώριο για heuristics/search, όριο για βαριά imports.

### Αξιολόγηση & χρονοδιάγραμμα (competition_info.md:26-54)
- **Timeline**: Start 29 Ιουλ 2026 · **Final Submission Deadline 30 Σεπ 2026** · 1-~15 Οκτ συνεχίζονται episodes «μέχρι σύγκλισης» και μετά η κατάταξη κλειδώνει. (Σήμερα 5 Αυγ → **~8 εβδομάδες ανάπτυξης**.)
- **Prizes: 10 ισόποσα βραβεία $5.000 (θέσεις 1-10)** — δεν υπάρχει premium για την 1η θέση· στόχος είναι το **top-10**, όχι το #1. Αυτό ευνοεί συντηρητικό, σταθερό agent έναντι high-variance στρατηγικών.
- **Submissions: 5/μέρα, μόνο τα 2 πιο πρόσφατα active** για matchmaking **και για το final leaderboard** (competition_info.md:40, 523). Submission = απόφαση lineup, όχι save slot.
- Rating: μόνο W/L/T μετράει, όχι το περιθώριο coins· αλλαγή ανάλογη της διαφοράς rating· ties φέρνουν τα ratings κοντά (competition_info.md:46-52). Νεότερα bots παίζουν πολύ συχνότερα· κρυφό σ κατά discussion.md:117-133.
- **Τελική κατάταξη: μετά το deadline ~2 εβδομάδες επιπλέον episodes «to reduce uncertainty» και ένα ενιαίο Bradley-Terry tournament πάνω σε εκείνα τα episodes** (competition_info.md:53-54, discussion.md:4).
- **Runtime submission**: 1.6 vCPUs, 6.5 GiB RAM, 8 GiB HDD, όριο μεγέθους 100 MiB· τα αρχεία στο `/kaggle_simulations/agent/` — τα imports πρέπει να δείχνουν εκεί (competition_info.md:520-529). Validation episode εναντίον αντιγράφου του εαυτού του· σε Error κατεβαίνουν logs (competition_info.md:44).
- Υπάρχει επίσημο daily dataset με top episodes (έως 20 GB replays/μέρα) για IL/BC/στατιστικά (discussion.md:8-11), συν το community dataset `georgymamarin/kaggriculture-episodes` (viz cell 53-54).
- Γνωστή ανησυχία: **trajectory copying** από δημόσια replays — ο μόνος πραγματικός coupling μηχανισμός είναι η κοινή αγορά, και οι οργανωτές το επικαλούνται ως άμυνα («αν πουλάτε και οι δύο το ίδιο, υποφέρουν και τα δύο κέρδη — ο πρώτος που πουλά παίρνει την καλύτερη τιμή», discussion.md:136-140).
- Ladder benchmark **[ενημ. 2026-08-06 — αντικαθιστά την παλιά ανάγνωση «median ≈ $44.781, κορυφαίος με 4/4 τεταρτημόρια και 20 ζώα» (viz cells 54-56, δεδομένα πρώτων ημερών)]:** median νικητήριο bank πλέον **$87.436**, record **$199.499** ([ladder_snapshots daily-8](meta/ladder_snapshots.md#daily-8))· το modal top farm της ελίτ (Elo ≥2800, 08-05) είναι **8 cow + 5 sheep + 6 strawberry + 1 wheat · 12 hands · 3 τεταρτημόρια (NE+NW+SW, SE ποτέ)**, median $125.271 ([topfarms-19](meta/ladder_snapshots.md#topfarms-19)). Για σύγκριση, το Carrot Crew (6 tiles, 1 farmer) βγάζει ~$7-8k. Ο ladder κινείται μέρα-μέρα — η τρέχουσα μέτρηση ζει πάντα στο [meta/ladder_snapshots.md](meta/ladder_snapshots.md), όχι εδώ.

---

## 2. State / Action Space

### Observation (README.md:258-325, επιβεβαιωμένο live στο viz cell 37)
```
player, day, hour
farms[2]      # ΔΗΜΟΣΙΑ και για τους δύο: money, tiles[y][x], farmer[x,y],
              # hands[[x,y]...], unlocked_quadrants, hires_today
market        # κοινό: inventory{...}, prices{...} για τα 9 προϊόντα
town          # κοινό: unlocked_shops[...]
private       # ΜΟΝΟ δικό σου: shed{...}, seeds{...}, inventories[farmer, hands...]
```
- Tile: `None` | `"LOCKED"` | plant dict (`crop, planted_day, watered_today, consecutive_unwatered, yield_units, max_lifespan_step, fertilized_until_day`) | weed | coop/pasture dict (`animal, fed_today, consecutive_unfed, cared_today, fertilizer_available, pending_care_bonus, yield_units`).
- **Κρίσιμο για στρατηγική: η φάρμα του αντιπάλου είναι πλήρως ορατή** (tiles, χρήματα, workers) — κρυφά μόνο shed/seeds/carried inventories. Άρα μπορείς να **προβλέψεις την επερχόμενη προσφορά του** (π.χ. πόσα melons ωριμάζουν και πότε) πριν χτυπήσει την αγορά.
- Επιπλέον runtime πεδία: `step`, `remainingOverageTime` (φαίνονται στα notebooks· το getting-started χρησιμοποιεί `obs.get("step")`).

### Action (dict με 3 κλειδιά — viz cell 38)
| Κλειδί | Περιεχόμενο |
|---|---|
| `farmer` | 1 op: `NORTH/SOUTH/EAST/WEST/PASS`, `PLANT <crop>`, `WATER`, `HARVEST`, `FERTILIZE`, `DIG`, `BUILD_COOP`, `BUILD_PASTURE`, `PLACE <item> [n]`, `PICKUP <item> [n]`, `DROP`, `FEED`, `CARE`, `COLLECT_FERTILIZER` |
| `hands` | λίστα, 1 op ανά hand (ίδιο μενού) |
| `market` | έως 10, με τη σειρά: `["SELL", item, n]`, `["BUY_SEED", crop, n]`, `["BUY_ANIMAL", animal, n]`, `["BUY_PRODUCT", item, n]` (μόνο wheat/fertilizer), `["HIRE"]`, `["BUY_LAND"]` |

### Αμφισημίες / ελλείψεις που εντόπισα — **όλες ΛΥΘΗΚΑΝ 2026-08-05 από ανάγνωση `kaggriculture.py` v1.32.4** (reference copy: [engine_reference/](../engine_reference/))
1. ~~Αντιστοίχιση `hands` λίστας ↔ μονάδων~~ **ΛΥΘΗΚΕ**: επιβεβαιωμένο — `hands_actions[i]` ↔ `farm["hands"][i]` (`interpreter`: `enumerate(hands_actions)` με `idx=h_idx+1`, `_farmer_position` δείχνει `farm["hands"][idx-1]`), ίδια σειρά με `private["inventories"][1:]" (και τα δύο γεμίζουν στο `_do_hire` με το ίδιο append). Mismatch: λιγότερα actions από hands → τα επιπλέον hands απλά δεν κάνουν τίποτα (δεν επεξεργάζονται καν)· περισσότερα actions από hands → τα actions πέραν του `len(farm["hands"])` παίρνουν `pos=None` και κάνουν σιωπηλά no-op. Καμία σύγκρουση/σφάλμα σε καμία περίπτωση.
2. ~~Μετράνε τα HIRE/BUY_LAND στο όριο των 10 market orders;~~ **ΛΥΘΗΚΕ: ΝΑΙ.** `_process_market`: `queues.append(q[:max_orders])` κόβει την ωμή λίστα στα 10 πριν καν διαχωριστεί ο τύπος του order — HIRE/BUY_LAND μετράνε σαν οποιοδήποτε άλλο market order, το 11ο+ πετιέται σιωπηλά.
3. ~~Interleaving με άνισο πλήθος orders~~ **ΛΥΘΗΚΕ**: επεξεργασία ανά **index θέσης** στη λίστα (`for i in range(max_len)`), όχι ανά τύπο order. Σε κάθε index: HIRE/BUY_LAND εκτελούνται άτομικά ανά παίκτη αμέσως· SELL/BUY_* μπαίνουν σε **per-unit lockstep loop** — και οι δύο παίκτες βλέπουν την **ίδια τιμή στο ίδιο unit** (quote πριν από commit, με βάση κοινό pre-commit inventory), μετά committance και ταυτόχρονη ενημέρωση inventory πριν το επόμενο unit. Άρα μέσα στο ίδιο index είναι δίκαιο/συμμετρικό· το «ο πρώτος που πουλά παίρνει καλύτερη τιμή» ισχύει μόνο **μεταξύ διαφορετικών index θέσεων** (π.χ. αν βάλεις SELL στη θέση 0 και ο αντίπαλος στη θέση 5, το δικό σου order εξαντλείται πρώτο σε καλύτερη τιμή). Αν ένας παίκτης έχει λιγότερα orders, απλά δεν συμμετέχει στα index πέρα από το μήκος της λίστας του — δεν μπλοκάρει τον άλλο.
4. `PLANT` όταν πολλαπλές μονάδες φυτεύουν ταυτόχρονα με ανεπαρκείς σπόρους → **καμία δεν φυτεύει** — **επιβεβαιώθηκε στο engine** (`interpreter`: `blocked = {crop for crop, n in plant_demand.items() if n > seeds.get(crop, 0)}`, όλα τα PLANT για το blocked crop γίνονται PASS).
5. ~~`max_lifespan_step` / decay semantics~~ **ΛΥΘΗΚΕ**: μονάδα = **steps (turns), όχι μέρες**. One-shot crops: `max_lifespan_step = (planted_day + max_yield_day + 1) * turns_per_day` (ορίζεται στη φύτευση). Ongoing crops: `-1` (καμία φθορά) μέχρι να φτάσουν το `max_yield` στο `_daily_refresh_plants`, οπότε μπαίνει `(next_day+1)*turns_per_day`. Από εκεί, `_decay_plants` τρέχει **κάθε turn**: αν `step >= max_lifespan_step` και `(step - max_lifespan_step) % 2 == 0` → `yield_units -= 1`· στο 0 γίνεται WEED. Δηλαδή ακριβώς «-1 κάθε 2 turns από την ημέρα deadline», literal turns όχι μέρες.
6. **Νέο εύρημα (δεν ήταν στη λίστα, αλλά κρίσιμο):** `_end_of_day` χρησιμοποιεί **ένα κοινό `rng` instance διαδοχικά και για τους δύο παίκτες** (`rng = random.Random((seed*1_000_003) ^ day)`, μετά `_spawn_weeds(farm, ...)` για player 0 πρώτα, μετά player 1). Μέσα στο `_spawn_weeds`, `rng.random()` καλείται **μόνο για tiles που είναι `None`** (short-circuit `and`) — άρα ο αριθμός των draws που καταναλώνει ο player 0 εξαρτάται από το πόσα άδεια tiles έχει η **δική του** φάρμα, και ο player 1 συνεχίζει το stream από εκεί που σταμάτησε ο player 0. **Αυτό σημαίνει ότι η δική σου στρατηγική πλήρωσης tiles μετατοπίζει το weed RNG του αντιπάλου** — ένας απρόσμενος coupling μηχανισμός πέρα από την αγορά. Seat 0 vs seat 1 δεν είναι συμμετρικά ούτε στο ίδιο seed. Ενισχύει την ανάγκη του §6 «test και στα δύο seats», αλλά δείχνει ότι ούτε αυτό αρκεί πλήρως — ο συγκεκριμένος συνδυασμός tile-fill και των δύο παικτών καθορίζει το draw offset.

---

## 3. Στρατηγική ανάλυση

### 3.1 Το θεμελιώδες: actions > χρήματα
Με $3.000 αρχικά και hands σχεδόν δωρεάν (5 hands = $12/μέρα = 115 worker-turns), ο περιοριστικός πόρος είναι τα **actions και η λογιστική τους** (commute, ένα action/tile/μέρα για πότισμα). Κάθε στρατηγική ιεραρχείται από το «πόσα παραγωγικά tile-actions/μέρα αγοράζει». Το χάσμα ladder median ($44.8k) vs starter ($7-8k) είναι ακριβώς scale: γη + hands + ζώα.

> **Διόρθωση από πραγματικά replays (ενημερώθηκε 2026-08-05 με το πλήρες dataset ιστορικού, βλ. §3.2bis):** το thesis «actions > money» παραμένει σωστό στο επίπεδο «ξεκλείδωσε αρκετά hands/γη», αλλά **δεν μεταφράζεται σε «κάνε περισσότερα actions» μόλις κι οι δύο πλευρές έχουν ήδη κλιμακώσει.** Σε 4.932 πραγματικά ladder πλευρές (691 ομάδες, όλο το ιστορικό της ladder μέχρι σήμερα), το raw `tiles_planted` είναι σχεδόν ταυτόσημο μεταξύ νικητών/ηττημένων (ratio 1.02×) — η νίκη δεν κρίνεται από το πόσα tiles φυτεύεις. Υπάρχει όμως πραγματικό, μέτριο edge σε crew/labor: νικητές έχουν 1.19× μεγαλύτερο peak crew και 1.23× περισσότερα hires από ηττημένους — αρκετό για να μετράει, όχι δραματικό. Το marginal edge είναι κυρίως allocation quality (σωστό crop, σωστό timing πώλησης — βλ. crop win rates στο §3.2bis), με ένα μικρότερο πραγματικό συνεισφέρον labor scale.

### 3.2 Οικονομικές ευκαιρίες, ιεραρχημένες
1. **Sheep/cow με CARE = ο ισχυρότερος compounder.** Sheep cared: +$5.575/season σε base prices, και οι τιμές wool/milk συνήθως τρέχουν *πάνω* από base λόγω town demand χωρίς επαρκή προσφορά (το hero replay δείχνει τιμές να ανεβαίνουν όλη τη σεζόν). Κόστος 3 actions/ζώο/μέρα (FEED+CARE+HARVEST/COLLECT) — γι' αυτό ζώα και hands είναι μία απόφαση. Προσοχή στο **max_held cap**: αφήνεις 2 production days ασυγκόμιστα και η παραγωγή σταματά (viz cell 20).
2. **Strawberry = το πιο action-efficient crop, και το πλήρες ιστορικό ladder το επιβεβαιώνει έντονα** (βλ. §3.2bis: 70% win rate ως πρωτεύον crop σε n=441 πλευρές — κατά πολύ το πιο νικηφόρο, αν και μειοψηφική επιλογή έναντι wheat/melon). Μηχανιστική εξήγηση από το engine: ongoing crop, η παραγωγή (ages 10/12/14/16, ×4 total, $120 base/μονάδα) συσσωρεύεται **αυτόματα** στο `_daily_refresh_plants` ανεξάρτητα από το WATER — το πότισμα χρειάζεται μόνο για να μην πεθάνει το φυτό (2 συνεχόμενες άποτιστες μέρες = weed), άρα αρκεί πότισμα κάθε δεύτερη μέρα. Αντίθετα το Carrot απαιτεί πλήρη κύκλο water+harvest+replant κάθε 3 μέρες. Για ένα agent όπου τα actions είναι ο σπάνιος πόρος, το Strawberry αποδίδει $480 βάσης/tile σε ~16-20 μέρες με τη μισή σχεδόν συχνότητα επίσκεψης που θέλει το Carrot — είναι η καθαρότερη έκφραση του §3.1 thesis, όχι εξαίρεση σε αυτό, και οι περισσότεροι αντίπαλοι δεν το εκμεταλλεύονται ακόμα (minority strategy, wheat/melon είναι πολύ πιο συχνά ως πρωτεύον). Σύσταση: αναβάθμιση από «αγνοημένο» σε **βασικό crop της Φάσης 1**, τουλάχιστον στο επίπεδο του Carrot.
3. **Carrot = μηχανή cash-flow αρχής** (turnover 3 μέρες, +$85/κύκλο/tile σε base). Χρηματοδοτεί γρήγορα land/ζώα/strawberry seeds. Η above-curve της είναι sqrt/0.7 — μέτρια ανθεκτική. Πλήρες-δείγμα εύρημα (§3.2bis): ως πρωτεύον crop βγαίνει ~48% win rate (n=816) — ουσιαστικά break-even, συνεπές με τη διαίσθηση «εργαλείο εκκίνησης/cash-flow, όχι πρωτεύουσα στρατηγική νίκης» (η παλιότερη τιμή 0% προερχόταν από δείγμα n=5 και ήταν θόρυβος — καλό παράδειγμα γιατί χρειάζονται μεγάλα δείγματα, βλ. §3.2bis).
4. **Wheat = τριπλός ρόλος**: ζωοτροφή (1/ζώο/μέρα — καλλιέργησέ το αντί να το αγοράζεις, το BUY_PRODUCT ανεβάζει την τιμή σου), πώληση σε glut-ανθεκτική καμπύλη (log above), και με λίπασμα από τα ζώα φτάνει 6 μονάδες. Ο κύκλος ζώα→λίπασμα→wheat→ζωοτροφή+πώληση είναι σχεδιασμένη συνέργεια. Παρότι είναι το πιο συχνό πρωτεύον crop στο ladder (n=1940, το μεγαλύτερο δείγμα), το win rate του ως πρωτεύον είναι μόλις ~51% — καλό σαν support/staple, όχι σαν πρωτεύων οικονομικός μοχλός (αυτό το ρόλο τον κρατά το Strawberry, βλ. #2).
5. **Melon = χρυσός με ημερομηνία λήξης.** $142/tile-day σε base — αλλά τετραγωνική κατάρρευση (158 μονάδες → $1) και μηδενική στήριξη από shops. Παίζεται *οπορτουνιστικά*: λίγα tiles, πώληση σε τρίκλες όταν price ≥ threshold, και **παρακολούθηση της φάρμας του αντιπάλου** — αν εκείνος φυτεύει melons μαζικά, ωρίμανσή τους σε ~10 μέρες σημαίνει επερχόμενο glut: πούλα πριν από αυτόν ή απόφυγε το crop. Παρότι είναι το δεύτερο πιο συχνό πρωτεύον crop στο ladder (n=1380), win rate μόλις ~49% — πολλοί αντίπαλοι το παίζουν ως κύριο crop, όχι οπορτουνιστικά, και προφανώς δεν βγαίνουν κερδισμένοι σε σχέση με το Strawberry.
6. **Timing πωλήσεων ↔ town ramp**: η ζήτηση ×2 από μέρα 10, ×4 από μέρα 20 και τα shops προστίθενται κάθε 3 μέρες — **ίδια αγαθά αξίζουν περισσότερα αργότερα**, εντός των ορίων του shed cap 100. Trickle selling πάντα (orders λύνονται unit-by-unit)· ποτέ dump στο floor.
7. **BUY_LAND νωρίς-μέτρια**: NE ($1k) μόλις υπάρχει εργασία να το δουλέψει (πρακτικά μέρες 1-4)· SW/SE όταν το workforce κλιμακώνεται. Απόσβεση <7 μέρες, αλλά αγορά γης χωρίς hands είναι νεκρό κεφάλαιο. **Διόρθωση (§3.2bis):** μια πρώτη ανάλυση με ένα μόνο top-3 vs mid-ladder anecdote είχε δείξει «record holder αγοράζει γη μέρα 0, ο μέσος αντίπαλος ποτέ» — στο πλήρες dataset (4.932 πλευρές) αυτό **δεν επιβεβαιώνεται**: `first_land_day` νικητών (6.96) vs ηττημένων (6.65) είναι ουσιαστικά ίδιο (ratio 1.05×, αν κάτι οι νικητές αγοράζουν λίγο *αργότερα*). Το land timing παραμένει λογικό βήμα οικονομικά (αποσβένεται <7 μέρες), αλλά δεν είναι μετρήσιμο διαφοροποιητικό στοιχείο νίκης/ήττας στο πραγματικό ladder — δεν αξίζει να το υπερτιμήσουμε στο tuning της Φάσης 2.
8. **Παρατήρηση `unlocked_shops`**: ποια shops άνοιξαν είναι τυχαίο ανά episode — το crop mix mid-season πρέπει να προσαρμόζεται στη ζήτηση που όντως ξεκλείδωσε (π.χ. Pet Café → 12 carrots/μέρα, Yarn Store → 2× wool).

### 3.2bis Επιβεβαίωση από πραγματικά ladder replays (2026-08-05, πλήρες dataset ιστορικού)

> **[ενημ. 2026-08-06 — φρεσκάδα πηγής]:** τα νούμερα αυτής της ενότητας μετρήθηκαν σε snapshot
> του community dataset **έως 2026-08-04** και ο ladder έκτοτε κινήθηκε αισθητά (median winner
> bank $87.436 στις 08-06, +52% σε μία μέρα — [daily-17](meta/ladder_snapshots.md#daily-17))·
> επιπλέον η 08-05 μόνη της πρόσθεσε ~3.200 episodes (>40% του corpus). Τα δομικά συμπεράσματα
> (crop tier list, labor edge, όχι land-timing edge) παραμένουν οι καλύτερες εκτιμήσεις μας, αλλά
> **κάθε απόλυτο νούμερο εδώ είναι ιστορικό** — τρέχουσες τιμές: [meta/ladder_snapshots.md](meta/ladder_snapshots.md).
> Πριν τη Φάση 3, ξανακατέβασμα του dataset (βλ. τέλος ενότητας) είναι υποχρεωτικό, όχι προαιρετικό.

Δύο notebooks στο repo δίνουν την **μεθοδολογία** parsing πάνω σε πραγματικά replay JSON, αλλά τα δικά τους baked outputs ήταν στατικά snapshots από τις πρώτες 2-3 μέρες. Κατεβάσαμε ζωντανά το community dataset **`georgymamarin/kaggriculture-episodes`** (μέσω `kagglehub`, token σε `.env`/`KAGGLE_API_TOKEN`, gitignored) και τρέξαμε φρέσκια ανάλυση πάνω σε **4.932 decisive ladder πλευρές / 691 ομάδες, όλο το ιστορικό 2026-07-30 έως σήμερα** — δραματικά μεγαλύτερο δείγμα από τα notebooks. Τα δομημένα αρχεία (`episodes.csv`, `agents.csv`, `teams.csv`, `daily_stats.csv`, `episode_features.csv` — το τελευταίο έχει *ήδη* parsed strategy fingerprints ανά επεισόδιο/seat, δεν χρειάζεται δικός μας replay parser) μπήκαν στο repo στο [data/kaggriculture-episodes/](../data/kaggriculture-episodes/); το ογκώδες `replays.parquet` (213MB, raw replay JSON) έμεινε μόνο στο τοπικό kagglehub cache — ξανακατεβαίνει σε δευτερόλεπτα με `kagglehub.dataset_download("georgymamarin/kaggriculture-episodes")` όποτε χρειαστεί.

**Πραγματικό tier list (n≥8 games, Wilson 95% CI)** — π.χ. στα υψηλότερα δείγματα: **Victor @ Tufa Labs** 70.9% winrate σε 117 games, **RuiKimura4** 80.0% σε 55 games, **Raiden.B** 72.6% σε 95 games· χαμηλότερο άκρο **Rudraksh Zodage** 17.8% σε 45 games. Χρήσιμο ως πρώτος πραγματικός opponent bench για τη Φάση 3.

**Primary-crop win rate, πλήρες δείγμα** (πολύ πιο αξιόπιστο από τα μικρά δείγματα των notebooks):
| Crop | Win rate ως πρωτεύον | n | Σχόλιο |
|---|---|---|---|
| Strawberry | **70%** | 441 | Μειοψηφική επιλογή, κατά πολύ η πιο νικηφόρα |
| Wheat | 51% | 1.940 | Το πιο συχνό πρωτεύον, αλλά break-even |
| Melon | 49% | 1.380 | Δεύτερο πιο συχνό, break-even |
| Carrot | 48% | 816 | Break-even, συνεπές με ρόλο cash-flow |
| Tomato | 32% | 189 | Σπάνιο και αδύναμο |
| (κανένα σαφές) | 30% | 166 | Χειρότερο από όλα — unfocused farms χάνουν |

**Fingerprint νικητών vs ηττημένων** (πλήρες δείγμα, βλ. διόρθωση §3.1): `final_money` 1.75× (εν μέρει κυκλικό — είναι σχεδόν ο ορισμός της νίκης), `peak_crew` 1.19×, `total_hires` 1.23×, `first_land_day` 1.05× (**όχι πραγματική διαφορά** — διόρθωση #7 παραπάνω), `tiles_planted` 1.02× (πρακτικά ίδιο). Labor scale έχει πραγματικό αλλά μέτριο edge· raw action volume και land timing όχι.

**Πραγματική ημερήσια εξέλιξη (`daily_stats.csv`, σε πραγματικά $, όχι rating score):**
| Ημερομηνία | Games | Median winner bank | p90 | Record |
|---|---|---|---|---|
| 07-30 | 726 | $37.002 | $90.104 | $157.449 |
| 07-31 | 1.902 | $68.690 | $108.053 | $172.970 |
| 08-01 | 448 | $83.130 | $122.167 | $180.499 |
| 08-02 | 225 | $80.767 | $158.597 | $180.911 |
| 08-03 | 187 | $74.981 | $165.966 | $197.632 |
| 08-04 | 191 | $50.771 | $152.903 | $180.508 |

Η ραγδαία άνοδος ήταν στις πρώτες ~36 ώρες (07-30→07-31)· **από 08-01 και μετά το record σταθεροποιείται γύρω στα $178-198k** και το median κάνει salto (ακόμα και πτώση στις 08-04, πιθανόν νέα/αδύναμα submissions που μπαίνουν στο pool) — πιο ήπια εικόνα από το «ραγδαία κλιμακούμενο» που έδειχνε το πρώτο notebook snapshot στις 07-31. Σημείωση κλίμακας: αυτά τα νούμερα (δεκάδες χιλιάδες $) είναι εντελώς διαφορετική κλίμακα από τα `top_avg_score`/`median_avg_score` του `data/archive/manifest.csv` (εκατοντάδες-χιλιάδες) — αυτό το δεύτερο είναι σχεδόν σίγουρα rating/σκορ κατάταξης, όχι χρήματα· μην τα συγχέεις.

**Μεθοδολογικό μάθημα που αξίζει να κρατήσουμε:** το anecdote «ο νικητής αγόρασε γη μέρα 0» (από 1 top-3 replay) φάνηκε πειστικό αλλά δεν επιβεβαιώθηκε στο πλήρες δείγμα (#7 παραπάνω) — small-N replay ανάλυση (ό,τι θα βγάλουν και τα δύο notebooks αν τρέξουν σε 1 μέρα δεδομένων) μπορεί να δείξει πραγματικά sample-specific patterns που δεν γενικεύονται. Το `episode_features.csv` με τις 4.932+ γραμμές είναι η πιο αξιόπιστη πηγή που έχουμε σήμερα και αξίζει να ξαναρτεθεί (νέο `kagglehub.dataset_download`) κοντά στη Φάση 3 για ενημερωμένο opponent bench.

### 3.3 Αλληλεπίδραση με τον αντίπαλο
Μόνο μέσω αγοράς, αλλά όχι αμελητέα: κοινό inventory ανά προϊόν σημαίνει ότι η υπερπαραγωγή του αντιπάλου **ρίχνει και τις δικές σου τιμές** (και αντίστροφα, οι αγορές του wheat/fertilizer τις ανεβάζουν για σένα). Ορθολογική απάντηση: (α) διαφοροποίηση χαρτοφυλακίου απέναντι σε mono-crop αντιπάλους, (β) προληπτική πώληση πριν την προβλέψιμη συγκομιδή του, (γ) στροφή σε staples όταν τα premium κορεστούν. Ένας agent που *διαβάζει* αγορά + φάρμα αντιπάλου έχει δομικό πλεονέκτημα απέναντι στα trajectory-copy bots που κυριαρχούν στο public LB (discussion.md:136-138) — αυτά δεν προσαρμόζονται όταν η αγορά τους έχει ήδη κορεστεί.

**[ενημ. 2026-08-06] Το (β) «προληπτική πώληση» αναβαθμίζεται από ιδέα σε σχεδιαστική απαίτηση — «πούλα πριν το κύμα»:** το meta πουλά σε **προβλέψιμο ημερολόγιο** ([topfarms-22](meta/ladder_snapshots.md#topfarms-22): strawberry 1η πώληση μέρα 16, batch 8,9· melon μέρα 10· wool μέρα 9· milk μέρα 8) πάνω σε προϊόντα με γνωστά sell-cliffs στο 1.32.x (**strawberry 62 / wool 59 / milk 76 / melon 158** net μονάδες ως το floor — [reference/market.md](reference/market.md)). Το V13-R3 notebook απέδειξε τοπικά ότι μια μετάθεση πώλησης **ενός μόλις turn** νωρίτερα από το κύμα αξίζει **χιλιάδες $ ανά παιχνίδι** σε mirror matchups (31-1 vs exact V21.1, μέσο margin +$2.304 — [agents-1](meta/ladder_snapshots.md#agents-1))· και το structured-economic-policy δίνει τη θεωρία: το swing από μετάθεση πώλησης = 2× το price-impact ορθογώνιο (§6 του notebook), ενώ το withholding είναι μεταφορά αξίας στον αντίπαλο όταν εκείνος είναι ο μεγαλύτερος πωλητής στο παράθυρο (§8). **Δικός μας μηχανισμός (για v1f+):** πρόβλεψη του κύματος από (i) το meta ημερολόγιο ως prior, (ii) το ζωντανό market inventory, (iii) τα ορατά ώριμα tiles του αντιπάλου — και τοποθέτηση των δικών μας SELL **πριν** το προβλεπόμενο κύμα, με trickle ώστε να μην ανοίγουμε εμείς το cliff. ⚠️ Ρητή πρόβλεψη: **το ημερολόγιο θα μετακινηθεί** όσο περισσότεροι υιοθετούν sell-ahead (ήδη το V13-R3 είναι δημόσιο) — οι αριθμοί του topfarms-22 είναι η *πρώτη βαθμονόμηση*, όχι σταθερά· ο μηχανισμός πρέπει να διαβάζει την αγορά, όχι να hard-codάρει μέρες. Σημείωση συμβατή με το Ανοιχτό #11: χρησιμοποιούμε **στατιστικά του meta** (πότε πουλάνε), όχι trajectories.

### 3.4 Gap analysis — πού είμαστε πραγματικά (2026-08-05)

Μετά την αποδοχή του v1b (plan.md §3.3), η σύγκριση με το πραγματικό ladder είναι:

| | Εμείς (v1b, τοπικά) | Ladder (πραγματικά δεδομένα, §3.2bis) |
|---|---|---|
| Median bank | ~$21k | median winner bank **$50-83k**· median τελικό **$44.8k** |
| Record | — | **~$180-198k**, σταθεροποιημένο από 08-01 |
| Quadrants | 1 (NW) | κορυφαίος του dataset: **4/4** |
| Ζώα | **0** | κορυφαίος: **20** |
| Crew | ~4 units (farmer + 3 hands) | νικητές 1.19× peak_crew έναντι ηττημένων |

**[ενημ. 2026-08-06 — αντικαθιστά τον πίνακα παραπάνω ως τρέχουσα ανάγνωση· ο παλιός μένει για την καμπύλη.]**
Με το v1e Phase-1 αποδεκτό (median **$42.555** vs starter, 96/96, `checkpoints/v1e` — memory.md 2026-08-06) και τις μετρήσεις 08-05/08-06:

| | Εμείς (v1e, τοπικά vs starter) | Ελίτ ζώνη ≥2800 (08-05, [topfarms-19](meta/ladder_snapshots.md#topfarms-19)) | Full ladder (08-06, [daily-8](meta/ladder_snapshots.md#daily-8)) |
|---|---|---|---|
| Median bank | **~$42,6k** | **$125,3k** | median winner $87,4k · record $199,5k |
| Quadrants | 2 (NW+NE) | **3 (NE+NW+SW)** — SE ποτέ | — |
| Ζώα | 3 | **13** (8 cow + 5 sheep) | — |
| Hands | ~6 | **12** | total hires: ισχυρότερο correlate (+0,76, [daily-13](meta/ladder_snapshots.md#daily-13)) |

**Άξονας (α) — το οικονομικό optimum του engine ως στόχος κλίμακας:** το modal top farm
(8 cow + 5 sheep + 6 strawberry + 1 wheat, 12 hands, γη NE+NW+SW με build order hire@0/cow@0/sheep@0/land@7)
δεν είναι συνταγή προς αντιγραφή αλλά η καλύτερη διαθέσιμη εκτίμηση του *engine optimum υπό
ανταγωνισμό* — *αυτό* ορίζει τα capacity targets των v1c/v1d: **3ο τεταρτημόριο, ~13 ζώα
βαριά σε cow/sheep, crew 12+**. Το SE (κόστος $4k) δεν το αγοράζει κανείς στην ελίτ — να μην
το αγοράσουμε ούτε εμείς χωρίς μετρημένο λόγο. Δύο επιφυλάξεις: (i) το ανεξάρτητο
structured-economic-policy notebook συγκλίνει στα δομικά (3 τεταρτημόρια, SE χωρίς ζώα, 12-13
hands, 15 ζώα) αλλά διαφωνεί στο crop (melon-primary αντί strawberry) — η δομή είναι πιο βέβαιη
από το crop mix· (ii) στα φρέσκα full-ladder fingerprints εμφανίστηκαν **wheat-primary record
games** ([daily-11](meta/ladder_snapshots.md#daily-11)) — single-game ενδείξεις, θέλουν δεύτερη
μέτρηση πριν αλλάξουν το mix μας.

**Συμπέρασμα που καθορίζει προτεραιότητες: το χάσμα είναι δομικό, όχι παραμετρικό.** Ένας agent με 1 quadrant και 0 ζώα έχει ταβάνι ~$25-30k όσο καλά κι αν tunαριστεί — τα ζώα με CARE είναι κατά την §3.2#1 ο ισχυρότερος compounder ($5.575/sheep/season cared). Άρα **κάθε parameter sweep πριν υπάρξουν v1c (γη) και v1d (ζώα) βελτιστοποιεί σε λάθος ταβάνι**. Αντίστροφα: η αιτία που δεν έχουμε ακόμα αυτά τα features δεν είναι έλλειψη χρόνου αλλά ότι **ο scheduler δεν αντέχει το φορτίο** (v1c STOP ×3, review.md C1). Σειρά που προκύπτει: capacity/routing redesign → features → tuning.

**Κενό στα δεδομένα που πρέπει να καλυφθεί:** το `data/kaggriculture-episodes/episode_features.csv` **δεν έχει καμία στήλη για ζώα ή για τελικό πλήθος quadrants** (στήλες: `final_money, peak_crew, total_hires, first_land_day, elbow_day, tiles_planted, plants_*, price_*`). Δηλαδή με τα σημερινά structured δεδομένα **δεν μπορούμε να απαντήσουμε το πιο κρίσιμο ερώτημα σχεδιασμού: πόσα ζώα έχουν οι νικητές, ποιου είδους, και ποια μέρα τα αγοράζουν.** Απαιτεί parsing του raw `replays.parquet` (213MB, kagglehub cache) ή του επίσημου daily dataset — βλ. §5.0 βήμα 3. Δευτερεύον: το community dataset σταματά στις 08-04, άρα re-download αξίζει *περιοδικά* (κάθε 1-2 εβδομάδες), όχι άμεσα.

**Οριοθέτηση της χρήσης replays (διευκρίνιση του Ανοιχτού #11):** αναλύουμε replays για **στόχο και διάγνωση** (τι χαρτοφυλάκιο, ποιο timing, ποια κλίμακα) — ποτέ ως πηγή κινήσεων ή ως BC/IL prior. Η δύναμη των κορυφαίων είναι στην **εκτέλεση** (routing/logistics), που δεν μεταφέρεται με μίμηση: ένα replay λέει «20 ζώα τη μέρα 12», δεν λέει πώς τα τάιζε χωρίς να χάσει το πότισμα. Άρα το «να φτάσουμε στο ίδιο baseline με αντιγραφή και μετά να βελτιώσουμε» **δεν είναι εφικτό** — το replay δίνει target curve, όχι συνταγή.

---

## 4. Αρχιτεκτονική λύσης

### Σύσταση: **Layered heuristic scheduler + αναλυτικό market model, με tuned παραμέτρους μέσω paired-seed self-play. RL μόνο ως Φάση 4, αν χρειαστεί.**

Δομή τριών επιπέδων:

1. **Economic planner (ανά μέρα / on-event):** αποφασίζει χαρτοφυλάκιο tiles (crops/ζώα ανά τεταρτημόριο), αγορές γης, στόχο αριθμού hands, στόχους πωλήσεων ανά προϊόν. Χρησιμοποιεί το **ακριβές `market_price()`** — τα constants και η συνάρτηση είναι importable από το ίδιο το engine (`from kaggle_environments.envs.kaggriculture.kaggriculture import CROPS, ANIMALS, MARKET_PARAMS, market_price` — viz cell 1), άρα το marginal revenue κάθε πώλησης υπολογίζεται *ακριβώς*, όχι κατ' εκτίμηση. Προβλέπει town demand ντετερμινιστικά (γνωστά intervals) και προσφορά αντιπάλου από τα ορατά tiles του.
2. **Task scheduler (ανά turn):** μετατρέπει τους στόχους σε λίστα εργασιών (WATER πριν από όλα, FEED/CARE, HARVEST, PLANT, FERTILIZE, μεταφορές στο shed) και τις αναθέτει σε farmer+hands με έναν greedy/Hungarian matcher απόστασης. Λύνει το πρόβλημα που ανέδειξε το viz cell 57 σημείο 1: «τα hands είναι extra actions, όχι extra judgement» — η αξία των hands ξεκλειδώνεται μόνο με σωστό assignment.
3. **Market executor (ανά turn):** trickle sells με βάση marginal price (πούλα όσο `price(inv+k) ≥ κατώφλι`), αγορές σπόρων/ζώων/λιπάσματος, HIRE στην αρχή της μέρας, BUY_LAND on-trigger.

### Γιατί όχι καθαρό RL (τώρα)
| | Heuristic + tuning | Learned policy (RL/IL) |
|---|---|---|
| Observation | πλήρης, δομημένη, deterministic engine — ιδανική για κανόνες | τεράστιο structured state, μακρύς ορίζοντας (720 steps), sparse τελικό reward |
| Οικονομία | **κλειστού τύπου**: τιμές/αποδόσεις υπολογίζονται ακριβώς | πρέπει να τη μάθει από την αρχή |
| Evaluation | Bradley-Terry σε binary outcomes ευνοεί σταθερά ισχυρό, ντετερμινιστικό bot (discussion.md:123 — «favors deterministic methods») | κέρδος μόνο αν το ceiling των heuristics αποδειχθεί χαμηλό |
| Ρίσκο | χαμηλό, πλήρως debuggable, 1s/turn άνετο | timeout/dependency ρίσκο στο server, δύσκολο debugging σιωπηλών no-ops |
| Copying meta | ένα adaptive bot νικά copiers όταν η αγορά κορεστεί | IL πάνω σε replays κληρονομεί τη μη-προσαρμοστικότητα |

Το παιχνίδι είναι σχεδόν single-agent optimization με ασθενή σύζευξη μέσω αγοράς — η «σκακιστική» συνιστώσα είναι μικρή, η operations-research συνιστώσα τεράστια. Υβριδικό μονοπάτι αν χρειαστεί: κρατάμε τον scheduler και μαθαίνουμε **μόνο** το economic-planner layer (μικρός χώρος παραμέτρων → CMA-ES/Optuna πάνω σε self-play, ή offline RL σε top-episode replays για initialization).

### Ποσοτικοποίηση του «όχι καθαρό RL τώρα» (2026-08-05)

Η απόφαση επανεξετάστηκε ρητά μετά από πρόταση για **παράλληλη** εκπαίδευση RL δίπλα στα heuristics, και **επιβεβαιώνεται** — τώρα με αριθμούς αντί για διαίσθηση:

- **Ταχύτητα simulator:** ~3s ανά 720-step episode (μετρημένο στο Βήμα 0: 24 episodes σε 73s) ⇒ **~240 env-steps/s ανά core**. PPO σε πρόβλημα αυτού του ορίζοντα θέλει 10⁷-10⁸ steps· ακόμα και με 32 cores μιλάμε για **ημέρες** καθαρής προσομοίωσης ανά training run.
- **Η GPU δεν βοηθά.** Το bottleneck είναι ο Python interpreter του engine (CPU-bound), όχι το backprop. Η αξία του remote server (Ανοιχτό #9) είναι τα **cores**, όχι η RTX 3090.
- **Πραγματικό κόστος σωστού setup:** vectorized reimplementation του engine (numpy/numba) = 2-4 εβδομάδες, **συν** διαρκές ρίσκο απόκλισης από το ground truth — δηλαδή διπλασιασμός του κόστους συντήρησης του `tests/test_engine_facts.py` (Ρίσκο #1).
- **Action space:** 1 op ανά unit (5+ units) × ~17 τύποι ops × θέσεις, **συν** έως 10 market orders ανά turn. Χωρίς hierarchical/factored actions + action masking δεν εκπαιδεύεται· και μόλις γραφτεί το masking, έχει ήδη κωδικοποιηθεί χειροκίνητα το μεγαλύτερο μέρος της γνώσης που υποτίθεται ότι θα μάθαινε.
- **Reward:** sparse, terminal, ορίζοντας 720 βημάτων, credit assignment μέσα από κινούμενη αγορά.
- **Χρονοδιάγραμμα:** deadline 30 Σεπ ⇒ ~8 εβδομάδες. Το RL θα κατανάλωνε τις μισές με αβέβαιο αποτέλεσμα, ενώ τα ζώα+γη έχουν **γνωστή** αξία (§3.2#1, §3.4).
- **Meta:** το Bradley-Terry σε binary outcomes ευνοεί deterministic bots (discussion.md:123)· η υψηλή διακύμανση μιας learned policy τιμωρείται, και τα 10 **ισόποσα** βραβεία κάνουν στόχο το «σταθερά top-10», όχι το high-variance #1.

**Κλίμακα ML επιλογών, με φθίνουσα αξία ανά μονάδα ρίσκου:**

1. **Black-box optimization του `CONFIG`** (CMA-ES/Optuna πάνω σε paired self-play) — υπάρχων harness, καμία νέα dependency στο submission, μηδενικό runtime ρίσκο. Είναι το «learning» της Φάσης 4 με το ~1% του κόστους.
2. **Learned μόνο στο market/timing layer** — με επιφύλαξη: το `market_price()` είναι κλειστού τύπου και importable, άρα ένα *αναλυτικό* μοντέλο εκεί πιθανότατα κερδίζει το learned. Δικαιολογείται μόνο για opponent-reactive timing.
3. **Πλήρες RL** — μόνο με ρητό trigger (παρακάτω).

**Trigger ενεργοποίησης Φάσης 4-RL** (γράφεται εκ των προτέρων ώστε να μην είναι post-hoc δικαιολόγηση) — απαιτούνται **και τα τέσσερα**: (α) v1e ολοκληρωμένο με γη + ζώα + liquidation, (β) BBO sweep ≥2 γύρων δεν δίνει `IMPROVED` σε 48 seeds, (γ) το τοπικό median bank παραμένει <60% του τρέχοντος ladder median winner bank, (δ) απομένουν ≥3 εβδομάδες πριν το deadline.

---

## 5. Οδικός χάρτης υλοποίησης

> Ημερολόγιο (competition_info.md:26-35): σήμερα 5 Αυγ 2026 → Final Submission Deadline **30 Σεπ 2026**
> (~8 εβδομάδες)· μετά 1-~15 Οκτ episodes χωρίς νέες υποβολές. Ενδεικτική κατανομή: Φάσεις 0-1 μέσα στον
> Αύγουστο (πρώτο submission στη ladder όσο νωρίτερα γίνεται — δωρεάν πληροφορία), Φάση 2 έως αρχές
> Σεπτεμβρίου, Φάση 3 έως ~20 Σεπ, τελευταία εβδομάδα μόνο champion/challenger κλείδωμα των 2 slots.

### 5.0 Κατάσταση & άμεση σειρά εργασιών (ενημέρωση 2026-08-05)

Η **Φάση 0 έκλεισε** (engine tests + harness + CLI auth). Η **Φάση 1 έχει v0→v1b αποδεκτά**· **v1c (γη) έχει STOP** μετά από 3 αποτυχημένα capacity variants, **v1d/v1e δεν ξεκίνησαν**. Επιπλέον υπάρχει **ενεργό regression**: το working `agent/` μετά την εφαρμογή του review.md είναι **−$2.195 έναντι του immutable `checkpoints/v1b`** (se≈$93, CI [−2.399, −1.991], 24/24 episode losses, μηδέν errors) — δηλαδή **κάθε μελλοντικό gate είναι σήμερα μπλοκαρισμένο**, αφού όλα τα increments gate-άρουν εναντίον του v1b.

Σειρά προτεραιοτήτων (αιτιολόγηση: §3.4 για το «γιατί δομικό», §4 για το RL, §6.1 για το πρωτόκολλο, §8 για την παρατηρησιμότητα):

| # | Εργασία | Γιατί τώρα |
|---|---|---|
| 1 | **Ξεμπλοκάρισμα του −$2.195** μέσω αυτοματοποιημένου ablation: κάθε αλλαγή του τελευταίου session εκτίθεται ως flag στο `CONFIG` και τα combos τρέχουν παράλληλα εναντίον του immutable v1b | Blocker για κάθε gate· και πρώτη πραγματική χρήση της υποδομής του #2 |
| 2 | **Parallel `compare()` + dev/holdout seed split** (§6.1) | Φθηνό, ξεκλειδώνει τα #1/#5/#6· χωρίς αυτό κάθε sweep είναι ώρες αντί για λεπτά |
| 3 | **Gap analysis από raw top replays** (§3.4): ζώα/quadrants/crew ανά μέρα για τους top-winrate agents | Απαντά «γη ή ζώα πρώτα;» με δεδομένα αντί για μαντεψιά — ακριβώς το ερώτημα όπου το v1c απέτυχε 3 φορές |
| 4 | **Episode report + G11 receipts viewer** (§8.1) | Το v1c έχει ήδη αποτύχει 3× «στα τυφλά» (review.md H4)· χωρίς observability το retry είναι 4η τυφλή προσπάθεια |
| 5 | **v1c/v1d** με capacity/routing redesign (review.md §5 pre-checks 1-9) | Εδώ ζει το πραγματικό χάσμα $21k → $45k+ |
| 6 | **BBO sweeps (CMA-ES/Optuna) στο `CONFIG`** | Αποδίδουν μόνο αφού υπάρχουν features προς tuning (§3.4) |
| 7 | **RL** | Μόνο στο trigger της §4 |

**[ενημ. 2026-08-06] Οι τέσσερις στρατηγικοί άξονες, σε σειρά προτεραιότητας** (λεπτομέρειες στις παραπεμπόμενες ενότητες — η σειρά #1-#7 παραπάνω παραμένει ως έχει, οι άξονες λένε *προς τι* χτίζουν τα βήματα):
- **(α) Κλίμακα προς το engine optimum** (§3.4): v1c/v1d targets = 3ο τεταρτημόριο, ~13 ζώα cow/sheep, crew 12+ — το χάσμα $42,6k → $125k είναι ακόμα δομικό.
- **(β) Sell-ahead arbitrage** (§3.3): μηχανισμός «πούλα πριν το κύμα» από meta ημερολόγιο + ζωντανό inventory — πρώτο feature *μετά* την κλίμακα, με πρώτη βαθμονόμηση τα [topfarms-22](meta/ladder_snapshots.md#topfarms-22) νούμερα.
- **(γ) Προσαρμοστικότητα vs copy-bots** (§7#3): διατήρηση του αυτόνομου/adaptive σχεδιασμού· mirror margins στο bench.
- **(δ) Post-deadline robustness** (Φάση 3): σχεδίαση για εύρος από metas — η τελική BT κατάταξη παίζεται σε meta που δεν έχουμε δει.

**Ρητά εκτός λίστας (αποφασισμένο, να μην επανεξεταστεί χωρίς νέα δεδομένα):** πλήρες RL από τώρα, παράλληλα με τα heuristics (§4)· behavioral cloning / trajectory copying από replays (§3.4 οριοθέτηση)· αύξηση seeds ως *λύση* στο τρέχον regression — το regression έχει se≈$93 και 24/24 ήττες, δεν είναι θόρυβος δείγματος.

### Φάση 0 — Υποδομή & ground truth (1-2 μέρες δουλειάς)
- Setup: `pip install -U "kaggle-environments>=1.32.4"`, pin & καταγραφή version (η ladder άλλαξε engine 2 φορές σε μια βδομάδα — viz cell 23).
- **Ανάγνωση του `kaggriculture.py` του πακέτου** και επαλήθευση με micro-tests όλων των αποκλίσεων της §7 + των αμφισημιών της §2 (interleaving, όριο 10 orders, decay semantics).
- Harness: `play(agent, seed, opponent, seat)`, paired-seed `compare()` (υιοθέτηση από viz cells 46-50), αποθήκευση replays, timing profiler.
- **Deliverables:** `engine_facts.md` (επιβεβαιωμένοι κανόνες), `harness/` με CLI, baseline scores των starter/melon-maxxer/Carrot Crew στα ίδια seeds.

### Φάση 1 — Rule-based agent v1 (3-5 μέρες)
- Υλοποίηση των 3 layers της §4 με συντηρητικές παραμέτρους: carrot-open → NE land ~μέρα 2 → 2-4 hands/μέρα → 4-6 ζώα (sheep/cow) με FEED+CARE+COLLECT_FERTILIZER → wheat για feed → trickle selling με marginal-price κατώφλια → κλιμάκωση hands/γης όσο υπάρχει έργο.
- Guards: ποτέ άποτιστο φυτό/άταιστο ζώο (top priority), shed ≤100 (πούλα πριν το overflow), όχι φύτευση χωρίς επαρκή σπόρο, όχι πώληση στο floor, χειρισμός hand σε locked tile.
- **Στόχος/Deliverable:** `main.py` που περνά validation episode, νικά σταθερά το `starter` σε 12/12 seeds και πιάνει bank ≥ $40k (ladder median) locally. Πρώτο submission για βαθμονόμηση στην πραγματική ladder.

### Φάση 2 — Simulation & tuning (συνεχόμενο, 1-2 εβδομάδες)
- Παραμετροποίηση όλων των thresholds (πότε land, πόσα hands, crop mix ανά φάση σεζόν, sell κατώφλια ανά προϊόν) σε ένα config dict.
- Sweeps με paired seeds (≥24 seeds, κριτήριο: |mean diff| > 2×SE — μεθοδολογία viz cell 50) εναντίον πάγκου αντιπάλων: starter, melon-maxxer, snapshot του δικού μας v1, mimic των public baselines (π.χ. λογική «Diversified Scheduler»: 7 hands, mixed portfolio).
- Ενσωμάτωση opponent-aware market logic: πρόβλεψη supply αντιπάλου από ορατά tiles, προληπτικές πωλήσεις.
- **Deliverables:** tuned config, opponent bench, αναφορά ευαισθησίας παραμέτρων.

### Φάση 3 — Robustness & meta (1 εβδομάδα)
- Λήψη replays από το επίσημο daily dataset (discussion.md:11) → ανάλυση top-agent συμπεριφορών (πότε πουλάνε, τι φυτεύουν) → προσθήκη counter-συμπεριφορών όπου η αγορά το επιτρέπει.
- Stress tests: mono-crop flooder αντίπαλοι (κάθε προϊόν), αντίπαλος που αγοράζει επιθετικά wheat/fertilizer, do-nothing αντίπαλος (καθαρό optimization ceiling), και τα δύο δικά μας bots αντικριστά (mirror match — ανιχνεύει self-glut).
- Χειρισμός κάθε συνδυασμού `unlocked_shops` (τυχαίο ανά episode) — το crop mix πρέπει να προσαρμόζεται, όχι να υποθέτει μέση περίπτωση.
- **Deliverables:** robustness matrix (score vs κάθε αντίπαλο × 24 seeds), hardening fixes.
- **[ενημ. 2026-08-06] Άξονας (δ) — post-deadline robustness ως ρητό κριτήριο σχεδίασης:** η τελική κατάταξη είναι Bradley-Terry πάνω σε **~2 εβδομάδες episodes ΜΕΤΑ το deadline** (competition_info.md:53-54), δηλαδή ο agent θα κριθεί σε ένα meta που δεν μπορούμε να δούμε πριν κλειδώσει. Και το meta κινείται γρήγορα: median +210% σε 144h ([daily-17](meta/ladder_snapshots.md#daily-17)), route families ανεβοκατεβαίνουν μέσα σε μέρες (§7#3). Άρα η Φάση 3 βελτιστοποιεί για **εύρος από metas, όχι για το σημερινό**: ο robustness matrix να περιλαμβάνει και «αυριανά» σενάρια — αντιπάλους με sell-ahead δικό τους (το V13-R3 είναι δημόσιο, θα αντιγραφεί), μετατοπισμένα sell ημερολόγια (±2-4 μέρες από το topfarms-22), και wheat/staple-βαριά fields — όχι μόνο τους σημερινούς flooders. Το tuning που κερδίζει οριακά στο σημερινό bench αλλά καταρρέει σε μετατοπισμένο ημερολόγιο απορρίπτεται.

### Φάση 4 — Μάθηση (προαιρετική, μόνο αν η Φάση 2-3 δείξει plateau)
- Πρώτα black-box optimization (CMA-ES/Optuna) του planner config σε self-play — φθηνό, χωρίς αλλαγή αρχιτεκτονικής.
- Αν χρειαστεί περισσότερο: policy μόνο για το market/portfolio layer (το micromanagement μένει scripted), με IL initialization από top replays + fine-tuning με self-play. Έλεγχος ότι το inference χωρά άνετα στο 1s/turn χωρίς βαριά dependencies.
- **Deliverables:** σύγκριση learned vs tuned-heuristic στον ίδιο πάγκο· υποβάλλεται μόνο αν κερδίζει με στατιστική σημαντικότητα.

### Συνεχώς (όλες οι φάσεις)
- Τακτικά submissions — **επιβεβαιωμένα όρια: 5/μέρα, μόνο τα 2 τελευταία active και αυτά μπαίνουν στο final** (competition_info.md:40, 523). Νέο submission = συχνά παιχνίδια = γρήγορη πληροφορία, αλλά κάθε upload «καίει» ένα από τα 2 active slots — πριν το deadline της 30ής Σεπ, τα 2 τελευταία uploads πρέπει να είναι οι 2 καλύτερες εκδόσεις μας.
- Παρακολούθηση πραγματικών επιδόσεων μέσω CLI: `kaggle competitions episodes <SUBMISSION_ID>`, λήψη replays (`kaggle competitions replay <EPISODE_ID>`) και logs (`kaggle competitions logs <EPISODE_ID> <idx>`) για post-mortem πραγματικών ηττών (competition_info.md:439-457).
- Regression suite πριν από κάθε submission (βλ. §6).

---

## 6. Metrics & Testing Plan

### Πρωτόκολλο μέτρησης (από viz cells 46-52, επαληθευμένο)
- **Ντετερμινισμός**: ίδιο seed = ίδιο παιχνίδι *μόνο* αν ο agent είναι deterministic (όχι unseeded random/clock/set-iteration). Sanity check σε fresh process πριν από κάθε πειραματικό run.
- **Paired seeds**: κάθε αλλαγή αξιολογείται με A και B στο ίδιο σετ seeds, κριτήριο `|mean(diff)| > 2×SE(diff)` και ομοιόμορφη φορά στα περισσότερα seeds. Το seat μπορεί να επηρεάζει μέσω weed RNG — έλεγχος και στα δύο seats μέχρι να αποδειχθεί συμμετρία για το δικό μας bot (δες §2 Αμφισημία #6: το seat-effect εξαρτάται και από το tile-fill του αντιπάλου, όχι μόνο το seat index).
- **Πραγματικό μέγεθος variance (2026-08-05, από ladder replays — §3.2bis):** το ίδιο submission έχει game-to-game spread τυπικά **~19% του median bank του, ακραία έως 950%**. Αυτό είναι το ρεαλιστικό benchmark για το πόσο θόρυβο πρέπει να περιμένουμε ακόμα κι από ένα σταθερό δικό μας bot — ενισχύει την ανάγκη για 24-48 seeds ανά σύγκριση (όχι λιγότερα) και εξηγεί γιατί ένα και μοναδικό εντυπωσιακό game δεν αποδεικνύει τίποτα.
- **Προσοχή**: price-reactive versions αποκλίνουν στο trajectory → το pairing κερδίζει λιγότερο variance reduction από ό,τι στο Carrot Crew (viz cell 52). Αντιστάθμιση: περισσότερα seeds (24-48).

### 6.1 Πειραματικό πρωτόκολλο για sweeps (νέο, 2026-08-05)

Τα παραπάνω αρκούν για «μία αλλαγή τη φορά». Μόλις τρέχουμε **πολλά variants μαζί** (§5.0 #1 και #6) χρειάζονται τρεις επιπλέον κανόνες, αλλιώς τα αποτελέσματα είναι θόρυβος με επίφαση εγκυρότητας:

1. **Dev/holdout seed split.** Σταθερό **dev set** (π.χ. seeds 0-47) για κάθε screening/tuning· **holdout set** (π.χ. 100-147) που **δεν αγγίζεται σε καμία απόφαση tuning** και χρησιμοποιείται μόνο για την τελική επιβεβαίωση ενός increment ή ενός tuned config. Χωρίς αυτό, ένα sweep 20 variants κάνει overfit στα λίγα seeds της v1a-v1b εποχής και το «κέρδος» εξατμίζεται στην ladder.
2. **Screen → confirm, ποτέ «κράτα το max».** Με spread ~19% του median, αν τρέξεις k variants και κρατήσεις το καλύτερο, επιλέγεις θόρυβο με πιθανότητα που μεγαλώνει με το k (multiple comparisons). Πρωτόκολλο: screen όλων των variants σε dev seeds → κράτα top-3 → **confirm σε holdout με 48+ seeds** και directional verdict· **GO μόνο από το confirm stage**.
3. **Παραλληλισμός ανά seed.** Το `compare()` είναι CPU-bound και embarrassingly parallel (~3s/episode). Ένα multiprocessing pool πάνω στα seeds είναι το μοναδικό πράγμα που κάνει τα #1/#6 πρακτικά. Απαιτήσεις ορθότητας: fresh process ανά episode (ήδη το πρωτόκολλο ντετερμινισμού), ένα `results.jsonl` row ανά ολοκληρωμένο seed γραμμένο σειριακά από τον parent (ήδη υπάρχει incremental writing), και το fingerprint guard (review.md M2) να ελέγχεται **πριν** το dispatch.

**Μέθοδος bisect για regressions (νέο εργαλείο):** όταν ένα *σύνολο* αλλαγών χαλάει το σκορ, κάθε αλλαγή εκτίθεται ως boolean flag στο `CONFIG` με default = τρέχουσα συμπεριφορά, και τρέχει το πλήρες (ή fractional) factorial σε dev seeds εναντίον του immutable προηγούμενου checkpoint. Αντικαθιστά το χειροκίνητο «δοκίμασε να απενεργοποιήσεις κάτι και ξαναπαίξε», που στο session 2026-08-05 κατανάλωσε ώρες και **δεν** απομόνωσε την αιτία.

### Πίνακας μετρικών ανά run
1. Τελικό bank (και το bank του αντιπάλου — το W/L είναι ό,τι μετράει στην ladder).
2. Καμπύλη bank/turn (εντοπισμός stalls).
3. Λειτουργικά: worker-turns που πήγαν σε κίνηση vs δουλειά, φυτά που χάθηκαν σε weeds, ζώα που δραπέτευσαν, items που κάηκαν στο shed cap, μονάδες πουλημένες ≤$5, μέση τιμή πώλησης ανά προϊόν vs base.
4. Χρόνος: max/median turn time, συνολική κατανάλωση overage.

### Exploitability & edge cases (checklist από discussion.md/notebooks)
- [ ] Πότισμα την ημέρα φύτευσης — κανένα φυτό δεν γίνεται weed την 1η νύχτα (discussion.md:23).
- [ ] Hand που spawn-άρει σε locked tile (και το σενάριο εγκλωβισμού στο (5,5)) δεν κολλάει τον scheduler (discussion.md:34).
- [ ] DIG μόνο σε άδεια structures (discussion.md:21).
- [ ] Κανένα dump που φτάνει το floor· έλεγχος ότι το trickle logic σέβεται το «floor sales δεν προσθέτουν inventory».
- [ ] Ζώα: pickup κάθε production day (max_held), FEED πάντα πριν CARE στην προτεραιότητα.
- [ ] 10-order cap: ποτέ πάνω από 10 (σιωπηλή απόρριψη), HIRE/BUY_LAND μπαίνουν νωρίς στη λίστα.
- [ ] Mirror match (bot vs bot): δεν αυτοκαταστρέφεται η αγορά μας.
- [ ] Timeout: κανένα turn > 500ms locally· imports lazy/ελαφριά — και **έλεγχος σε περιβάλλον ~1.6 vCPU / 6.5 GiB RAM** (τα specs του server, competition_info.md:526-528), όχι μόνο στο dev μηχάνημα.
- [ ] Submission format: **`main.py` στο root** (single file ή tar.gz με `main.py` στο root — competition_info.md:421-429)· imports με paths σχετικά προς `/kaggle_simulations/agent/` (competition_info.md:524)· δοκιμή μέσω validation episode. Προσοχή στο notebook pitfall του discussion.md:37.
- [ ] Οι built-in αντίπαλοι `"pass"`, `"random"`, `"starter"` (competition_info.md:387) στον πάγκο regression.

---

## 7. Ρίσκα & αποκλίσεις docs/engine

### Επιβεβαιωμένες αποκλίσεις (engine υπερισχύει — discussion.md:16-37, 100-112)
| # | Θέμα | Docs έλεγαν | Engine κάνει |
|---|---|---|---|
| 1 | CARE bonus | +2/μέρα (παλιό rulebook) | **+1/μέρα** (το README του repo, :77, είναι πλέον σωστό) |
| 2 | Πώληση fertilizer | «μόνο αγορά» (AGENTS.md/Getting Started) | **SELL δεκτό** — επίσημη επιβεβαίωση |
| 3 | DIG σε structures | υπονοούσε ότι καθαρίζει coop/pasture | **no-op σε κατειλημμένα**· μόνο άδεια |
| 4 | Πότισμα ημέρας φύτευσης | παραλειπόταν | μέρα φύτευσης = 1η άποτιστη· weed το ίδιο βράδυ αν δεν ποτιστεί |
| 5 | Melon max yield | «day 12» | cap 6 μονάδων στην **ημέρα 10** (11-12 νεκρές μέρες) |
| 6 | Strawberry | «every other day» αόριστα | **ακριβώς 4 παραγωγές** (ηλικίες 10/12/14/16), μετά πεθαίνει |
| 7 | Yield/tile/day πίνακας | ασυνεπείς τύποι | πραγματικά: tomato 1/μέρα, strawberry 0.5/μέρα κ.λπ. |
| 8 | `fertilizer_available` | «set after CARE» (παλιό σχόλιο) | **κάθε επιζών ζώο**, χωρίς CARE· δεν συσσωρεύεται |
| 9 | Shed | «orthogonally adjacent» χωρίς συντεταγμένες | δεν είναι tile· πρόσβαση μόνο (4,4),(5,4),(4,5),(5,5) |
| 10 | T calibration | «24-day game» έμοιαζε λάθος | σκόπιμο 24-day window (επίσημη απάντηση) |

### Ρίσκα που μπορούν να ανατρέψουν τη στρατηγική
1. **Κινούμενο engine**: 2 versions σε μία εβδομάδα (locked-tile passability άλλαξε συμπεριφορά spawn/movement). Κάθε νέα έκδοση `kaggle-environments` απαιτεί re-run του regression suite. Mitigation: pinned version (**1.32.4**, εγκατεστημένο σε `.venv/` — δες §2 Αμφισημία #2) + micro-tests όποτε αλλάξει.
2. ~~**Το engine source δεν είναι στο repo**~~ **ΛΥΘΗΚΕ (2026-08-05):** διαβάστηκε το πλήρες `kaggriculture.py`, reference copy στο [engine_reference/](../engine_reference/). Οι Αμφισημίες #1-6 της §2 λύθηκαν όλες από αυτό — δεν στηριζόμαστε πια σε δευτερογενείς πηγές για market queue/hands mapping/decay/weed RNG.
3. **Copying meta στο Bradley-Terry — [ενημ. 2026-08-06: πλέον εμπειρικά επιβεβαιωμένο, όχι υπόθεση]**: η κορυφή του LB κυριαρχείται από **route families** (177-180 notebook: το παλιό δημόσιο v21/Dennis route έπεσε 19/46 στο φρέσκο top-30, ενώ Konstantin 40/46 και Richard Silence 41/46 medoids κυριαρχούν — route drift σε εξέλιξη)· τα δημόσια V13-R3/93-wr δείχνουν το επόμενο στάδιο του αγώνα: **στα mirror matches η νίκη κρίνεται σε λεπτομέρειες αγοράς** — από +$2.304 μέσο margin με one-turn sell preemption έως μετατροπή draws σε νίκες των **+$3** ([agents-1](meta/ladder_snapshots.md#agents-1))· και το BT μετρά W/L, όχι margin. Συνέπειες: (i) η παλιά ανάγνωση «αντιγράφεις το χθεσινό meta = χάνεις» επιβεβαιώνεται — τα routes μετακινούνται κάτω από τους copiers (και ο record holder της 07-31 «Victor @» εμφανίζει πλέον παιχνίδια κοντά στο μηδέν — fragility)· (ii) **άξονας (γ):** το πλεονέκτημά μας απέναντι σε copy-bots είναι η προσαρμοστικότητα (ζωντανή ανάγνωση αγοράς/αντιπάλου, §3.3), αλλά πρέπει και να **μην χάνουμε τα δικά μας mirrors σε ψίχουλα** — τα stress tests της Φάσης 3 να μετράνε και margin σε mirror, όχι μόνο W/L· (iii) η τελική κατάταξη σε πεδίο ομοιογενών αντιπάλων παραμένει υψηλού variance.
4. **Matchmaking κατά τη διάρκεια** (αργή σύγκλιση, λιγότερα παιχνίδια σε ψηλό rating — discussion.md:117-127): το mid-competition LB είναι θορυβώδες σήμα· οι αποφάσεις μας πρέπει να στηρίζονται στο local bench, όχι στο ημερήσιο rating.
5. **Άγνωστη διανομή αντιπάλων στο final**: αν κυριαρχήσουν agents που flood-άρουν συγκεκριμένα προϊόντα, τα tuned sell-thresholds μας μετατοπίζονται — γι' αυτό η Φάση 3 δοκιμάζει flooders κάθε προϊόντος.
6. **Σιωπηλά no-ops**: bug στο action formatting δεν σκάει ποτέ — μόνο χαμηλώνει το σκορ αθόρυβα. Mitigation: assertion layer τοπικά που επαληθεύει ότι κάθε intended action άλλαξε πράγματι το state.
7. **Config drift στη ladder**: η επίσημη σελίδα (competition_info.md:346-360) τεκμηριώνει τα ίδια defaults με το README (720 steps, 10×10, $3.000, 10 orders) — το ρίσκο πλέον περιορίζεται σε σιωπηλά `marketParams` overrides ή μελλοντικές αλλαγές από τους οργανωτές (διατηρούν ρητά το δικαίωμα αλλαγής timeline, competition_info.md:37).
8. **Στρατηγική των 2 active slots**: με μόνο τα 2 τελευταία submissions να μετράνε στο final, ένα βιαστικό upload λίγο πριν το deadline μπορεί να αντικαταστήσει την καλύτερη έκδοσή μας. Mitigation: κατεψυγμένο «champion» + «challenger» πρωτόκολλο τις τελευταίες μέρες.

---

## 8. Παρατηρησιμότητα & Visualization (νέο, 2026-08-05)

Δύο ξεχωριστά προβλήματα με διαφορετικές λύσεις: **(α)** «τι έκανε ο agent σε ένα episode» και **(β)** «ποιο variant/config κερδίζει σε δεκάδες runs».

### 8.1 Παρακολούθηση ενός episode

- **Ο επίσημος interactive player υπάρχει ήδη offline.** Το `kaggle-environments` κουβαλά bundled visualizer (`kaggle_environments/envs/kaggriculture/visualizer/default/dist/index.html`, ~14.7 MB) και το `html_renderer` (engine_reference/kaggriculture.py:992-997). Δηλαδή `env.render(mode="html")` μετά από `env.run(...)` δίνει τον κανονικό οπτικό player του διαγωνισμού **χωρίς Kaggle και χωρίς δίκτυο**. Ροή: play ενός seed → εγγραφή `episode.html` → άνοιγμα στο **VSCode Simple Browser** (`Ctrl+Shift+P` → «Simple Browser: Show»). Σε notebook, το `mode="ipython"` το ενσωματώνει inline.
- **Text renderer για step-through debugging:** `renderer()` (:965-983) τυπώνει board tile-tile + prices + shed/seeds ανά step — ιδανικό με breakpoint ή ως «ταινία» στο terminal.
- **Όριο και των δύο:** δείχνουν *τι έγινε στο board*, όχι *γιατί το αποφάσισε ο agent*. Το oscillation του session 2026-08-05 (units που πηγαινοέρχονταν μεταξύ δύο tiles) φαίνεται ως κίνηση, αλλά η αιτία — ποιο task ανατέθηκε, με ποιο slack, γιατί άλλαξε — όχι.
- **Δικό μας episode report (το πραγματικά διαγνωστικό κομμάτι):** αυτόνομο HTML δίπλα στο replay, χτισμένο πάνω στα ήδη υπάρχοντα `harness/metrics.py` + G11 receipts (`agent/receipts.py`, `agent/debug.py`). Ελάχιστο περιεχόμενο: καμπύλη bank και για τα 2 seats· unit-turns σε κίνηση vs εργασία vs idle· `water_weeds_lost`/`plant_decay_units_lost` ανά μέρα· heatmap κατάστασης farm ανά μέρα· τιμές πώλησης vs base ανά προϊόν· και **timeline ανάθεσης task ανά unit** — η μόνη οπτικοποίηση που θα είχε δείξει το oscillation αμέσως. Μηδενικές εξαρτήσεις, version-controllable.

### 8.2 Παρακολούθηση πειραμάτων (sweeps)

| Επιλογή | Πότε αξίζει |
|---|---|
| **W&B** | Sweeps στον remote Linux server με θέαση από παντού· sweep orchestration, parallel-coordinates, σύγκριση configs. Το καλύτερο fit για §5.0 #6 |
| **Optuna Dashboard** | Αν επιλεγεί Optuna για το BBO — param importance/parallel-coords δωρεάν, τοπικά, χωρίς λογαριασμό |
| **MLflow** | Self-hosted, offline, καμία εξωτερική εξάρτηση· φτωχότερο UI |
| **Static HTML report από το `results.jsonl`** | Μηδενικές εξαρτήσεις, version-controlled, ανοίγει στο VSCode Simple Browser |

**Απόφαση:** το `runs/**/results.jsonl` **παραμένει η πηγή αλήθειας** — έχει ήδη `_meta` row με code fingerprints και resume guard (review.md M2) και αποτελεί το reproducibility backbone· **δεν** μεταναστεύει σε εξωτερική υπηρεσία. Οποιοδήποτε tracker μπαίνει **από πάνω ως view**, μόνο για sweeps, και η απώλειά του δεν επιτρέπεται να ακυρώνει κανένα gate.

**Δύο προειδοποιήσεις:** (i) το W&B ανεβάζει config + metrics σε **εξωτερική υπηρεσία** — εν μέσω ενεργού διαγωνισμού αυτό είναι λεπτομέρειες στρατηγικής· τα private projects το καλύπτουν, αλλά είναι συνειδητή απόφαση του χρήστη, όχι default. (ii) Απαιτεί login/API key από τον χρήστη — δεν στήνεται αυτόνομα από τον agent.

**Απόφαση χρήστη (2026-08-06):** κρατάμε το τοπικό static HTML report (§8.1 `harness/report.py`)· **όχι W&B**. Δεν χρειάζεται να ξαναρωτηθεί εκτός αν προκύψει πραγματική ανάγκη για sweep orchestration (§5.0#6, εκτός scope προς το παρόν).

---

## Ανοιχτά Ερωτήματα προς Έρευνα

> Ενημέρωση 2026-08-05: το [competition_info.md](docs/source/competition_info.md) συμπληρώθηκε και **έλυσε** τα πρώην
> ερωτήματα για timeline/prizes (deadline 30 Σεπ 2026, top-10 × $5.000), submission limits (5/μέρα,
> latest 2 active και στο final, όριο 100 MiB), server resources (1.6 vCPU / 6.5 GiB RAM / 8 GiB HDD,
> αρχεία στο `/kaggle_simulations/agent/`), competition slug (`kaggriculture` — το
> `kaggriculture-gdm-internal` του getting-started ήταν παρωχημένο), format υποβολής (`main.py` στο root)
> και ladder config (η επίσημη σελίδα τεκμηριώνει τα ίδια defaults με το README). Παραμένουν ανοιχτά:

> **Ενημέρωση 2026-08-05 (β) — αποφάσεις χρήστη, ερωτήματα #9-12 έλυσαν:**
> compute = **remote Linux server, RTX 3090 24GB VRAM** (άνετο για paired-seed sweeps παράλληλα στη Φάση 2
> και για IL/fine-tuning αν χρειαστεί η Φάση 4 — GPU δεν είναι bottleneck, ο agent δεν χρειάζεται GPU στο
> submission runtime, μόνο για offline training/tuning)· αρχιτεκτονική = **heuristic-first επιβεβαιωμένο**,
> RL μόνο σε plateau όπως προτάθηκε· στάση copying meta = **καθαρά αυτόνομος agent**, όχι replay priors·
> team status = **solo**, τα 5/μέρα + 2 active slots είναι όλα δικά μας χωρίς συντονισμό τρίτων.
> Παραμένουν ανοιχτά μόνο τα καθαρά ερευνητικά #1-8 παρακάτω (μη-blocking πλην του #2).

1. **Ακριβής μηχανική του τελικού Bradley-Terry tournament** (competition_info.md:53-54 δίνει μόνο περίγραμμα): πόσα episodes ανά ζεύγος, πώς επιλέγονται τα ζευγάρια στο 2-εβδομάδων παράθυρο, αν το BT τρέχει σε *όλα* τα episodes της περιόδου ή μόνο στα μετά το deadline, τι σημαίνει λειτουργικά «leaderboard convergence» (competition_info.md:35), πώς σταθμίζονται οι ισοπαλίες. *Γιατί μετράει:* κρίνει πόσο νωρίς πρέπει να κλειδώσουν τα 2 τελικά submissions (περισσότερα παιχνίδια = μικρότερο σ) — και δεδομένων των 10 **ισόποσων** βραβείων, το βέλτιστο target είναι «σταθερά top-10», όχι high-variance κυνήγι του #1.
2. ~~**Το `kaggriculture.py` δεν υπάρχει στο repo**~~ **ΛΥΘΗΚΕ (2026-08-05):** venv (`.venv/`, Python 3.11 — το 3.14 του μηχανήματος δεν έχει ακόμα Windows wheels για το `pygame` dependency), `pip install "kaggle-environments>=1.32.4"` → εγκαταστάθηκε **1.32.4**, ίδιο version με το viz notebook. Reference copy στο [engine_reference/](../engine_reference/) (`kaggriculture.py`, `.json`, README.md, AGENTS.md του πακέτου).
3. ~~**Σημασιολογία market queue στο ίδιο turn**~~ **ΛΥΘΗΚΕ** — δες Αμφισημία #3 στην §2 παραπάνω: ΝΑΙ μετράνε HIRE/BUY_LAND στο cap των 10· επεξεργασία ανά index θέσης, per-unit lockstep με κοινή τιμή στο ίδιο unit, πλεονέκτημα μόνο σε προγενέστερο index.
4. ~~**Χαρτογράφηση `hands` action list ↔ μονάδες**~~ **ΛΥΘΗΚΕ** — δες Αμφισημία #1 στην §2 παραπάνω: index-to-index mapping με `farm["hands"]`, mismatch = σιωπηλό no-op και στις δύο κατευθύνσεις, καμία σύγκρουση.
5. ~~**Semantics του decay**~~ **ΛΥΘΗΚΕ** — δες Αμφισημία #5 στην §2 παραπάνω: literal turns/steps, όχι μέρες· `-1 κάθε 2 steps` από το `max_lifespan_step`.
6. ~~**Weed RNG και seat-dependence**~~ **ΛΥΘΗΚΕ, και χειρότερο απ' όσο υποθέταμε** — δες Αμφισημία #6 (νέο εύρημα) στην §2 παραπάνω: το seat-effect δεν είναι απλώς "ίδιο RNG, διαφορετική σειρά κλήσης" — ο αριθμός των draws που καταναλώνει ο player 0 εξαρτάται από **πόσα κενά tiles έχει η δική του φάρμα εκείνη τη μέρα**, οπότε το weed-RNG offset του player 1 μετατοπίζεται ανάλογα με τη estratégia γεμίσματος του player 0. Δεν αρκεί το testing και στα δύο seats με σταθερό αντίπαλο· το seed+seat+opponent-tile-fill συνδυασμός καθορίζει το αποτέλεσμα. Το πρωτόκολλο του §6 (test και στα δύο seats) παραμένει σωστό ως ελάχιστο, αλλά η μεθοδολογία πρέπει να αναγνωρίζει ότι το ίδιο seed δεν εγγυάται ίδια weed έκβαση αν αλλάξει ο αντίπαλος.
7. **Χρονικά όρια στο server**: το `actTimeout = 1s` + 60s overage μετρήθηκε locally (viz cell 51) και το hardware είναι πλέον γνωστό (1.6 vCPU, competition_info.md:528), αλλά δεν επιβεβαιώνεται ρητά ότι το ίδιο actTimeout ισχύει στο submission runtime — και 1.6 vCPU είναι πιθανώς αισθητά αργότερο από το dev μηχάνημα. *Γιατί μετράει:* ανώτατο όριο για lookahead/search στο executor· θέλει μέτρηση από logs πραγματικού ladder episode.
8. ~~**Πρόσβαση/χρησιμότητα των replay datasets**~~ **ΠΛΗΡΩΣ ΛΥΘΗΚΕ (2026-08-05):** κατεβάσαμε ζωντανά το community dataset `georgymamarin/kaggriculture-episodes` μέσω `kagglehub` (token σε `.env`, gitignored) — 4.932 decisive πλευρές, 691 ομάδες, όλο το ιστορικό μέχρι σήμερα, ~216MB συνολικά. Δομημένα αρχεία (μικρά, χωράνε στο repo) στο [data/kaggriculture-episodes/](../data/kaggriculture-episodes/); το βαρύ `replays.parquet` (213MB raw replay JSON) έμεινε στο τοπικό kagglehub cache, ξανακατεβαίνει σε δευτερόλεπτα όποτε χρειαστεί. Πλήρη ευρήματα στο §3.2bis: πραγματικό tier list με ονόματα/Wilson CI, primary-crop win rates σε μεγάλο δείγμα, real-$ ημερήσια εξέλιξη. Το επίσημο daily index (`kaggle/kaggriculture-episodes-YYYY-MM-DD`, raw JSON, ως 20GB/μέρα) παραμένει ακατέβατο — δεν χρειάστηκε, το community dataset με το έτοιμο `episode_features.csv` κάλυψε την ανάγκη πιο αποδοτικά. *Γιατί μετράει:* τροφοδοτεί ήδη τη Φάση 3 (meta analysis) νωρίτερα απ' ό,τι προγραμματισμένο, και διόρθωσε ένα λάθος συμπέρασμα (land-timing edge) πριν μπει στο tuning της Φάσης 2.
9. ~~**Απόφαση χρήστη — compute budget**~~ **ΛΥΘΗΚΕ (2026-08-05):** remote Linux server, RTX 3090 24GB VRAM. Άνετο για paired-seed sweeps (48+ seeds) στη Φάση 2 παράλληλα, και αρκετό για IL initialization + fine-tuning αν ενεργοποιηθεί η Φάση 4. Η GPU δεν παίζει ρόλο στο submission runtime (CPU-only, 1.6 vCPU) — χρησιμοποιείται μόνο offline για tuning/training.
10. ~~**Απόφαση χρήστη — προτίμηση αρχιτεκτονικής**~~ **ΛΥΘΗΚΕ (2026-08-05):** επιβεβαιώθηκε heuristic scheduler + tuning από την αρχή, RL μόνο αν οι Φάσεις 2-3 δείξουν plateau, όπως στη σύσταση της §4.
11. ~~**Απόφαση χρήστη — στάση απέναντι στο copying meta**~~ **ΛΥΘΗΚΕ (2026-08-05):** καθαρά αυτόνομος agent — κανένα replay-derived prior/opening. Ο agent στηρίζεται αποκλειστικά στο economic model + adaptive αντίδραση στην ορατή φάρμα του αντιπάλου, όχι σε μιμητισμό δημόσιων trajectories. Η ανάλυση replays στη Φάση 3 (discussion.md:11) χρησιμοποιείται μόνο για benchmarking/counter-στρατηγικές, όχι ως πηγή κίνησεων. **Διευκρίνιση εύρους (2026-08-05, μετά από ερώτημα χρήστη «να αντιγράψουμε τη στρατηγική των πρώτων»):** επιτρέπεται και ενθαρρύνεται η εξαγωγή **δομής** στρατηγικής από replays (χαρτοφυλάκιο, κλίμακα crew/γης/ζώων, timing) ως **target curve και διαγνωστικό** — απαγορεύεται η αντιγραφή trajectories και κάθε BC/IL prior. Πλήρης αιτιολόγηση στην §3.4.
12. ~~**Απόφαση χρήστη — team status**~~ **ΛΥΘΗΚΕ (2026-08-05):** solo. Τα 5 submissions/μέρα και 2 active slots είναι εξ ολοκλήρου δικά μας, χωρίς ανάγκη συντονισμού merge πριν το Team Merger Deadline (23 Σεπ 2026).
