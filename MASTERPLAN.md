# MASTERPLAN — Kaggriculture Competitive Agent

> Βασισμένο αποκλειστικά στο περιεχόμενο του repo: [README.md](README.md), [discussion.md](discussion.md),
> [competition_info.md](competition_info.md) (επίσημη σελίδα διαγωνισμού: Overview, Timeline, Evaluation,
> How to Play, CLI workflow, FAQ),
> [kaggriculture-getting-started.ipynb](kaggriculture-getting-started.ipynb),
> [kaggriculture-visualized-what-every-crop-pays.ipynb](kaggriculture-visualized-what-every-crop-pays.ipynb).
> Το engine (`kaggriculture.py`) **δεν βρίσκεται στο repo** — ζει στο πακέτο `kaggle-environments`
> (η ladder τρέχει ≥1.32.3, το viz notebook έτρεξε σε 1.32.4). Όπου docs και engine διαφωνούν,
> **υπερισχύει το engine** — οι γνωστές αποκλίσεις καταγράφονται στην §7.

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
- Ladder benchmark (dataset, ~691 teams): **median τελικό bank ≈ $44.781**· ο κορυφαίος του dataset τελείωσε με 4/4 τεταρτημόρια και 20 ζώα (viz cells 54-56). Για σύγκριση, το Carrot Crew (6 tiles, 1 farmer) βγάζει ~$7-8k.

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

### Αμφισημίες / ελλείψεις που εντόπισα
1. **Αντιστοίχιση `hands` λίστας ↔ μονάδων**: τεκμαίρεται σειρά πρόσληψης (ίδια με `private.inventories[1:]`), δεν τεκμηριώνεται ρητά πουθενά.
2. **Μετράνε τα HIRE/BUY_LAND στο όριο των 10 market orders;** Το README (:94) λέει «up to 10 market actions» και τα HIRE/BUY_LAND είναι market actions — λογικά ναι, αλλά δεν επιβεβαιώνεται.
3. **Interleaving με άνισο πλήθος orders**: «processed in order simultaneously (one from each player) while both players have orders» (README.md:94) — τι ακριβώς συμβαίνει όταν ο ένας έχει 3 orders και ο άλλος 10; Η φράση «ο πρώτος που πουλά παίρνει την καλύτερη τιμή» (discussion.md:140) αφορά προφανώς διαδοχικά turns, όχι το ίδιο turn — θέλει επαλήθευση στο engine.
4. `PLANT` όταν πολλαπλές μονάδες φυτεύουν ταυτόχρονα με ανεπαρκείς σπόρους → **καμία δεν φυτεύει** (README.md:56-57) — παγίδα για multi-hand σχεδιασμό.
5. `max_lifespan_step` σε plant dict: μονάδα μέτρησης steps (π.χ. 96 = τέλος ημέρας 4 για carrot στο viz cell 37) — η ακριβής σημασιολογία του decay «-1 κάθε 2 turns» (README.md:126) θέλει έλεγχο στο engine.

---

## 3. Στρατηγική ανάλυση

### 3.1 Το θεμελιώδες: actions > χρήματα
Με $3.000 αρχικά και hands σχεδόν δωρεάν (5 hands = $12/μέρα = 115 worker-turns), ο περιοριστικός πόρος είναι τα **actions και η λογιστική τους** (commute, ένα action/tile/μέρα για πότισμα). Κάθε στρατηγική ιεραρχείται από το «πόσα παραγωγικά tile-actions/μέρα αγοράζει». Το χάσμα ladder median ($44.8k) vs starter ($7-8k) είναι ακριβώς scale: γη + hands + ζώα.

### 3.2 Οικονομικές ευκαιρίες, ιεραρχημένες
1. **Sheep/cow με CARE = ο ισχυρότερος compounder.** Sheep cared: +$5.575/season σε base prices, και οι τιμές wool/milk συνήθως τρέχουν *πάνω* από base λόγω town demand χωρίς επαρκή προσφορά (το hero replay δείχνει τιμές να ανεβαίνουν όλη τη σεζόν). Κόστος 3 actions/ζώο/μέρα (FEED+CARE+HARVEST/COLLECT) — γι' αυτό ζώα και hands είναι μία απόφαση. Προσοχή στο **max_held cap**: αφήνεις 2 production days ασυγκόμιστα και η παραγωγή σταματά (viz cell 20).
2. **Carrot = μηχανή cash-flow αρχής** (turnover 3 μέρες, +$85/κύκλο/tile σε base). Χρηματοδοτεί γρήγορα land/ζώα. Η above-curve της είναι sqrt/0.7 — μέτρια ανθεκτική.
3. **Wheat = τριπλός ρόλος**: ζωοτροφή (1/ζώο/μέρα — καλλιέργησέ το αντί να το αγοράζεις, το BUY_PRODUCT ανεβάζει την τιμή σου), πώληση σε glut-ανθεκτική καμπύλη (log above), και με λίπασμα από τα ζώα φτάνει 6 μονάδες. Ο κύκλος ζώα→λίπασμα→wheat→ζωοτροφή+πώληση είναι σχεδιασμένη συνέργεια.
4. **Melon = χρυσός με ημερομηνία λήξης.** $142/tile-day σε base — αλλά τετραγωνική κατάρρευση (158 μονάδες → $1) και μηδενική στήριξη από shops. Παίζεται *οπορτουνιστικά*: λίγα tiles, πώληση σε τρίκλες όταν price ≥ threshold, και **παρακολούθηση της φάρμας του αντιπάλου** — αν εκείνος φυτεύει melons μαζικά, ωρίμανσή τους σε ~10 μέρες σημαίνει επερχόμενο glut: πούλα πριν από αυτόν ή απόφυγε το crop.
5. **Timing πωλήσεων ↔ town ramp**: η ζήτηση ×2 από μέρα 10, ×4 από μέρα 20 και τα shops προστίθενται κάθε 3 μέρες — **ίδια αγαθά αξίζουν περισσότερα αργότερα**, εντός των ορίων του shed cap 100. Trickle selling πάντα (orders λύνονται unit-by-unit)· ποτέ dump στο floor.
6. **BUY_LAND νωρίς-μέτρια**: NE ($1k) μόλις υπάρχει εργασία να το δουλέψει (πρακτικά μέρες 1-4)· SW/SE όταν το workforce κλιμακώνεται. Απόσβεση <7 μέρες, αλλά αγορά γης χωρίς hands είναι νεκρό κεφάλαιο.
7. **Παρατήρηση `unlocked_shops`**: ποια shops άνοιξαν είναι τυχαίο ανά episode — το crop mix mid-season πρέπει να προσαρμόζεται στη ζήτηση που όντως ξεκλείδωσε (π.χ. Pet Café → 12 carrots/μέρα, Yarn Store → 2× wool).

### 3.3 Αλληλεπίδραση με τον αντίπαλο
Μόνο μέσω αγοράς, αλλά όχι αμελητέα: κοινό inventory ανά προϊόν σημαίνει ότι η υπερπαραγωγή του αντιπάλου **ρίχνει και τις δικές σου τιμές** (και αντίστροφα, οι αγορές του wheat/fertilizer τις ανεβάζουν για σένα). Ορθολογική απάντηση: (α) διαφοροποίηση χαρτοφυλακίου απέναντι σε mono-crop αντιπάλους, (β) προληπτική πώληση πριν την προβλέψιμη συγκομιδή του, (γ) στροφή σε staples όταν τα premium κορεστούν. Ένας agent που *διαβάζει* αγορά + φάρμα αντιπάλου έχει δομικό πλεονέκτημα απέναντι στα trajectory-copy bots που κυριαρχούν στο public LB (discussion.md:136-138) — αυτά δεν προσαρμόζονται όταν η αγορά τους έχει ήδη κορεστεί.

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

---

## 5. Οδικός χάρτης υλοποίησης

> Ημερολόγιο (competition_info.md:26-35): σήμερα 5 Αυγ 2026 → Final Submission Deadline **30 Σεπ 2026**
> (~8 εβδομάδες)· μετά 1-~15 Οκτ episodes χωρίς νέες υποβολές. Ενδεικτική κατανομή: Φάσεις 0-1 μέσα στον
> Αύγουστο (πρώτο submission στη ladder όσο νωρίτερα γίνεται — δωρεάν πληροφορία), Φάση 2 έως αρχές
> Σεπτεμβρίου, Φάση 3 έως ~20 Σεπ, τελευταία εβδομάδα μόνο champion/challenger κλείδωμα των 2 slots.

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
- **Paired seeds**: κάθε αλλαγή αξιολογείται με A και B στο ίδιο σετ seeds, κριτήριο `|mean(diff)| > 2×SE(diff)` και ομοιόμορφη φορά στα περισσότερα seeds. Το seat μπορεί να επηρεάζει μέσω weed RNG — έλεγχος και στα δύο seats μέχρι να αποδειχθεί συμμετρία για το δικό μας bot.
- **Προσοχή**: price-reactive versions αποκλίνουν στο trajectory → το pairing κερδίζει λιγότερο variance reduction από ό,τι στο Carrot Crew (viz cell 52). Αντιστάθμιση: περισσότερα seeds (24-48).

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
1. **Κινούμενο engine**: 2 versions σε μία εβδομάδα (locked-tile passability άλλαξε συμπεριφορά spawn/movement). Κάθε νέα έκδοση `kaggle-environments` απαιτεί re-run του regression suite. Mitigation: pinned version + `engine_facts.md` + micro-tests.
2. **Το engine source δεν είναι στο repo** — όλα τα παραπάνω βασίζονται σε docs/discussion/notebook outputs μέχρι να διαβαστεί το πραγματικό `kaggriculture.py` (Φάση 0, blocking).
3. **Copying meta στο Bradley-Terry**: αν το τελικό tournament έχει πολλά copy-bots με σχεδόν ίδιες τραγιέκτορίες, τα head-to-head τους κρίνονται σε λεπτομέρειες αγοράς — η προσαρμοστικότητά μας είναι πλεονέκτημα, αλλά η τελική κατάταξη σε πεδίο ομοιογενών αντιπάλων μπορεί να έχει υψηλό variance.
4. **Matchmaking κατά τη διάρκεια** (αργή σύγκλιση, λιγότερα παιχνίδια σε ψηλό rating — discussion.md:117-127): το mid-competition LB είναι θορυβώδες σήμα· οι αποφάσεις μας πρέπει να στηρίζονται στο local bench, όχι στο ημερήσιο rating.
5. **Άγνωστη διανομή αντιπάλων στο final**: αν κυριαρχήσουν agents που flood-άρουν συγκεκριμένα προϊόντα, τα tuned sell-thresholds μας μετατοπίζονται — γι' αυτό η Φάση 3 δοκιμάζει flooders κάθε προϊόντος.
6. **Σιωπηλά no-ops**: bug στο action formatting δεν σκάει ποτέ — μόνο χαμηλώνει το σκορ αθόρυβα. Mitigation: assertion layer τοπικά που επαληθεύει ότι κάθε intended action άλλαξε πράγματι το state.
7. **Config drift στη ladder**: η επίσημη σελίδα (competition_info.md:346-360) τεκμηριώνει τα ίδια defaults με το README (720 steps, 10×10, $3.000, 10 orders) — το ρίσκο πλέον περιορίζεται σε σιωπηλά `marketParams` overrides ή μελλοντικές αλλαγές από τους οργανωτές (διατηρούν ρητά το δικαίωμα αλλαγής timeline, competition_info.md:37).
8. **Στρατηγική των 2 active slots**: με μόνο τα 2 τελευταία submissions να μετράνε στο final, ένα βιαστικό upload λίγο πριν το deadline μπορεί να αντικαταστήσει την καλύτερη έκδοσή μας. Mitigation: κατεψυγμένο «champion» + «challenger» πρωτόκολλο τις τελευταίες μέρες.

---

## Ανοιχτά Ερωτήματα προς Έρευνα

> Ενημέρωση 2026-08-05: το [competition_info.md](competition_info.md) συμπληρώθηκε και **έλυσε** τα πρώην
> ερωτήματα για timeline/prizes (deadline 30 Σεπ 2026, top-10 × $5.000), submission limits (5/μέρα,
> latest 2 active και στο final, όριο 100 MiB), server resources (1.6 vCPU / 6.5 GiB RAM / 8 GiB HDD,
> αρχεία στο `/kaggle_simulations/agent/`), competition slug (`kaggriculture` — το
> `kaggriculture-gdm-internal` του getting-started ήταν παρωχημένο), format υποβολής (`main.py` στο root)
> και ladder config (η επίσημη σελίδα τεκμηριώνει τα ίδια defaults με το README). Παραμένουν ανοιχτά:

1. **Ακριβής μηχανική του τελικού Bradley-Terry tournament** (competition_info.md:53-54 δίνει μόνο περίγραμμα): πόσα episodes ανά ζεύγος, πώς επιλέγονται τα ζευγάρια στο 2-εβδομάδων παράθυρο, αν το BT τρέχει σε *όλα* τα episodes της περιόδου ή μόνο στα μετά το deadline, τι σημαίνει λειτουργικά «leaderboard convergence» (competition_info.md:35), πώς σταθμίζονται οι ισοπαλίες. *Γιατί μετράει:* κρίνει πόσο νωρίς πρέπει να κλειδώσουν τα 2 τελικά submissions (περισσότερα παιχνίδια = μικρότερο σ) — και δεδομένων των 10 **ισόποσων** βραβείων, το βέλτιστο target είναι «σταθερά top-10», όχι high-variance κυνήγι του #1.
2. **Το `kaggriculture.py` δεν υπάρχει στο repo.** Πρέπει να εγκατασταθεί το `kaggle-environments` και να διαβαστεί/επαληθευτεί το engine source (και να μπει αντίγραφο/έκδοση στο repo ως reference); Ποια έκδοση τρέχει ΤΩΡΑ η ladder (η 1.32.4 του notebook ή νεότερη — το επίσημο Docker image αναφέρεται στο competition_info.md:532); *Γιατί μετράει:* όλη η §7 βασίζεται σε δευτερογενείς πηγές· το engine είναι το source of truth και έχει ήδη αλλάξει 2 φορές.
3. **Σημασιολογία market queue στο ίδιο turn** (README.md:94, 194): με άνισα πλήθη orders, τι σειρά ακολουθείται όταν ο ένας παίκτης εξαντλήσει τα δικά του; Μετράνε HIRE/BUY_LAND στο cap των 10; Υπάρχει πλεονέκτημα στη θέση ενός SELL μέσα στη λίστα; *Γιατί μετράει:* το trickle-selling και το «πούλα πριν τον αντίπαλο» είναι κεντρικά στο σχέδιο — χρειάζονται τη σωστή μικροδομή.
4. **Χαρτογράφηση `hands` action list ↔ μονάδες** και συμπεριφορά σε mismatch μεγεθών (λιγότερα/περισσότερα ops από hands). *Γιατί μετράει:* ο multi-unit scheduler είναι η καρδιά του agent· λάθος mapping = σιωπηλά χαμένα actions.
5. **Semantics του decay**: «η διαθέσιμη απόδοση μειώνεται κατά 1 κάθε δεύτερο turn» (README.md:126) — turns ή μέρες; Πώς ακριβώς συνδέεται με το `max_lifespan_step`; *Γιατί μετράει:* καθορίζει τα deadline συγκομιδής, ειδικά για tomato/strawberry και όψιμα melons.
6. **Weed RNG και seat-dependence** (viz cell 45): πόσο επηρεάζει το seat έναν agent που δουλεύει όλο το board; Χρειάζεται το testing και στα δύο seats μόνιμα; *Γιατί μετράει:* κόστος CPU του πειραματικού πρωτοκόλλου (×2) και εγκυρότητα των συγκρίσεων.
7. **Χρονικά όρια στο server**: το `actTimeout = 1s` + 60s overage μετρήθηκε locally (viz cell 51) και το hardware είναι πλέον γνωστό (1.6 vCPU, competition_info.md:528), αλλά δεν επιβεβαιώνεται ρητά ότι το ίδιο actTimeout ισχύει στο submission runtime — και 1.6 vCPU είναι πιθανώς αισθητά αργότερο από το dev μηχάνημα. *Γιατί μετράει:* ανώτατο όριο για lookahead/search στο executor· θέλει μέτρηση από logs πραγματικού ladder episode.
8. **Πρόσβαση/χρησιμότητα των replay datasets**: το επίσημο `kaggle/kaggriculture-episodes-index` (discussion.md:11) και το community `georgymamarin/kaggriculture-episodes` — θα τα κατεβάσουμε; Πόσο πρόσφατα/πλήρη είναι; Επιπλέον: τι περιέχει το competition data package του `kaggle competitions download kaggriculture` (competition_info.md:419); *Γιατί μετράει:* τροφοδοτούν τη Φάση 3 (meta analysis) και ενδεχόμενο IL στη Φάση 4.
9. **Απόφαση χρήστη — compute budget:** πόσες CPU-ώρες διαθέτουμε για sweeps/self-play; (Ο χρονικός ορίζοντας είναι πλέον γνωστός: deadline 30 Σεπ 2026 → **~8 εβδομάδες** από σήμερα.) *Γιατί μετράει:* καθορίζει αριθμό seeds ανά σύγκριση και εύρος tuning· με 8 εβδομάδες οι Φάσεις 0-3 χωράνε άνετα και η Φάση 4 (RL) είναι εφικτή μόνο αν αποφασιστεί νωρίς.
10. **Απόφαση χρήστη — προτίμηση αρχιτεκτονικής:** αποδέχεσαι το προτεινόμενο μονοπάτι «heuristic scheduler + tuning, RL μόνο αν plateau», ή θέλεις εξ αρχής ML-first προσέγγιση (IL/BC από τα top replays); *Γιατί μετράει:* διαφορετική υποδομή από τη Φάση 1 (feature pipeline, training loop) και διαφορετικό ρίσκο/χρονοδιάγραμμα.
11. **Απόφαση χρήστη — στάση απέναντι στο copying meta:** καθαρά αυτόνομος agent, ή επιτρέπεται υβρίδιο που αξιοποιεί γνωστά ισχυρά openings από replays ως prior με adaptive fallback; *Γιατί μετράει:* ηθική/πρακτική επιλογή που επηρεάζει τη Φάση 3 και τη διαφοροποίησή μας στο τελικό tournament.
12. **Απόφαση χρήστη — team status:** παίζουμε solo ή υπάρχει ενδεχόμενο συνεργασίας/merge (Team Merger Deadline 23 Σεπ 2026, competition_info.md:31); *Γιατί μετράει:* τα όρια 5 submissions/μέρα και 2 active slots είναι ανά ομάδα — ένα merge αλλάζει το submission budget και τον συντονισμό των 2 τελικών slots.
