# ladder_snapshots.md — τι κερδίζει στην πράξη, ανά ημερομηνία

> **Κινούμενος στόχος.** Κάθε εγγραφή είναι μια *μέτρηση σε συγκεκριμένη ημερομηνία*, όχι κανόνας.
> Ο ladder βελτιώνεται όσο κοιμάσαι — δες §"Ρυθμός" κάθε snapshot. **Νεότερο πρώτα.**
>
> Πηγή: τα community notebooks στο [notebooks/](notebooks), εξαγμένα με
> `python analysis/nb_extract.py <notebook> -o docs/source/notebooks/ --no-code`. Τα πλήρη dumps:
> [source/notebooks/](docs/source/notebooks).
>
> **Πώς ανανεώνεται:** τα δύο notebooks (*Live Meta Report*, *What actually wins*) **ξανατρέχουν
> προγραμματισμένα στο Kaggle**. Ξανακατέβασέ τα → τρέξε τον extractor → **πρόσθεσε νέα εγγραφή
> εδώ**, μη διορθώσεις την παλιά. Οι παλιές εγγραφές είναι η καμπύλη του meta.
> Τρίτη πηγή από 2026-08-06: *What the Top Farms Do* (cjlcjlcjl) — αυτοπεριγράφεται ως daily
> tracker («watch the MODAL META line move»), οπότε πιθανότατα ξανατρέχει κι αυτό· αξίζει
> επανέλεγχος στο Kaggle σε κάθε ανανέωση.

---

## ⚠️ Πώς συγκρίνονται τα νούμερα μεταξύ τους

Τα notebooks μετρούν **διαφορετικούς πληθυσμούς** και δεν είναι άμεσα συγκρίσιμα:

| Πηγή | Δείγμα | Τι σημαίνει το «μέσο bank» του |
|---|---|---|
| *Live Meta Report* | Πλήρες crawl του ladder (community dataset) | **Ολόκληρος** ο ladder, από τα πιο αδύναμα ως τα πιο δυνατά bots |
| *What actually wins* | Δείγμα ≤300 replays **της ημέρας, ταξινομημένα κατά rating** | **Η κορυφή** του ladder |
| *What the Top Farms Do* | Επίσημο daily dataset, **ζώνη Elo ≥2800** (§8.5: ≥2700) | **Μόνο η κορυφαία ζώνη** — οι median του είναι median *της ελίτ*, όχι του ladder |
| *V13-R3* (agent notebook) | **Τοπικό** paired-seed cross-play (engine 1.32.4): 96+32+96 παιχνίδια vs παγωμένους proxies / exact V21.1 / public controls | Δεν είναι ladder — μετρά «ποιος κερδίζει ποιον» σε παγωμένους αντιπάλους· έμμεση μαρτυρία για το mirror meta |
| *93-wr* (agent notebook) | Ισχυρίζεται 100 τοπικά episodes vs v21.1 — **μη αναπαραγόμενα** (το run του 2026-08-06 διαρκεί 4s και δεν παίζει κανένα παιχνίδι) | Αναξιόπιστο ως μέτρηση· μόνο ποιοτική ένδειξη για mirror tie-breaks |

Άρα «median win $39,6k» και «μέσο profit νικητή $118k» **δεν διαφωνούν** — είναι ο median όλου του
ladder έναντι του μέσου όρου της κορυφής.

---

## 2026-08-06 — *Live Meta Report* (ανανέωση) + 3 agent notebooks ως έμμεση μαρτυρία

**Πηγές:** (α) *Kaggriculture Daily Replays: The Live Meta Report* (Georgy Mamarin, run 2026-08-06
05:47 UTC, community dataset, δεδομένα έως **2026-08-05 23:46 UTC** — πλήρες crawl του ladder)·
(β) τρία competitor-agent notebooks (*structured-economic-policy*, *V13-R3*, *93-wr*) — **τοπικά
cross-play πειράματα, όχι μετρήσεις ladder** (βλ. πίνακα πληθυσμών παραπάνω). Πλήρη dumps:
[source/notebooks/](../source/notebooks).

### Full-ladder κατανομή: ο μέσος ανέβηκε, το ταβάνι κρατάει <a id="daily-8"></a>

**7.639 episodes · 6.184 full replays (81%) · 1.519 teams · 6,3 μέρες** (cell 4).
Νικητήρια banks: **p25 $45.405 · median $87.436 · p90 $144.790 · record $199.499** (ZechHuang) —
το ρεκόρ είναι **2,3×** τον median (cell 8).

Σύγκριση με 07-31 ([meta-6](#meta-6)): median $39.652 → $87.436 (**+120% σε ~5 μέρες**), record
$157.449 → $199.499 (+27%). Ο λόγος record/median έπεσε **4,0× → 2,3×** — η μέση συμπιέζεται προς
την κορυφή (συνεπές με [wins-10](#wins-10) και [topfarms-26](#topfarms-26)).

*Chart-only* (εικόνες cells 1, 4): η κατανομή νικητήριων banks είναι **διπλοκόρυφη** (~$40k και
~$90–110k) — δύο πληθυσμοί στρατηγικών, όχι ένα συνεχές· και η 08-05 ήταν μέρα-ρεκόρ
δραστηριότητας (~3.200 episodes, >40% όλου του corpus σε μία μέρα).

### Ρυθμός: +210% σε 144 ώρες <a id="daily-17"></a>

Median winning bank **$37.002 → $114.709 σε 144h** (**+210%**)· η τελευταία μέρα **+52%** έναντι
της προηγούμενης (cell 17). [07-31: +115% σε 12h — [meta-15](#meta-15).] Chart cell 17: το best
single game της ημέρας έχει πλατό ~$195–200k ενώ ο median ανεβαίνει — *the middle rises, the
ceiling holds*. Διασπορά ανά submission: **17%** του median (χειρότερη 1.109%, cell 21) — ίδια
τάξη με το 19% της 07-31 ([meta-19](#meta-19))· ένα episode εξακολουθεί να μην αποδεικνύει τίποτα.

### Fingerprints: το wheat εμφανίστηκε στην κορυφή <a id="daily-11"></a>

| Ποιος | Bank | Hires/μέρα | Peak crew | 1η γη (μέρα) | Tiles | Top crop |
|---|---:|---:|---:|---:|---:|---|
| **ZechHuang** (record) | $199.499 | 10,2 | 12 | 7 | 131 | **Wheat** |
| Q.qlmmm | $197.632 | 11,1 | 14 | **0** | 126 | Strawberry |
| Mazga | $195.147 | 9,5 | 15 | 7 | 135 | **Wheat** |
| *Raiden.B (mid-ladder)* | $79.631 | 9,2 | 10 | 9 | 141 | Wheat |

Δύο από τα τρία κορυφαία games είναι **Wheat-primary** — νέο έναντι 07-31
(Strawberry/Melon/Melon, [meta-11](#meta-11)) και διαφορετικό από το modal top farm
(6 strawberry + 1 wheat, [topfarms-19](#topfarms-19)). Πιθανή εξήγηση από το policy notebook
(chart cell 11): **το wheat δεν έχει sell-cliff** — η sell-side καμπύλη του είναι σχεδόν επίπεδη
(~0,92× ακόμα και στο +160 inventory), άρα κλιμακώνει χωρίς κορεσμό· και στο παιχνίδι-ρεκόρ το
wheat τρέχει **$25→$54** πάνω από base $25 (cell 15) = ζήτηση feed από ζωικές φάρμες.
⚠️ Τα fingerprints διαβάζουν **ένα καλύτερο παιχνίδι** ανά submission ([meta-23](#meta-23)) —
όχι μέση συμπεριφορά· το «wheat στην κορυφή» θέλει δεύτερη μέτρηση πριν γίνει ανάγνωση.

### Συσχετίσεις (n=12.354 seats) και elbows <a id="daily-13"></a>

**total hires +0,76** (ισχυρότερο σήμα)· peak crew κοντά· **first land day −0,04** (≈ μηδέν)·
strawberry **+0,61** το καλύτερο crop (cell 13). *Chart-only:* melon μόλις ~+0,1 παρά τα
melon-heavy record games· carrot/tomato **αρνητικά** (~−0,25). Το `elbow_day` συσχετίζεται 0,8
με το bank (cell 11)· elbows top-1/2/3: **μέρα 14–18** (cell 26) έναντι 11/15/11 στις 07-31
([meta-8](#meta-8)) — τα μεγάλα παιχνίδια μένουν «κοντά στο μηδέν» ακόμα πιο βαθιά στη σεζόν
πριν την έκρηξη (chart cell 8: επίπεδα ως turn ~250–270).

### Leaderboard: ασυμφωνία πηγών (flag)

Chart cell 1 (run 05:47 UTC, community ratings): **#1 «somewhere after» ~3.090**, μετά lucaskna /
Dennis Gioche / Lucien de Rubempre / Ibad Ur Rahman ~2.930–2.950. Το topfarms notebook (run 07:05
UTC, επίσημο LB) έδινε **#1 Ben Hamilton 3.043,7** ([topfarms-26](#topfarms-26)). Διαφορετικά
rating συστήματα/χρονικές στιγμές — μην τα συγχέεις. *Chart-only* (cell 21): ο Kaito Fukami
(676 games) είναι ο πιο συνεπής των top-6 (~$150k στενό κουτί)· ο «Victor @» (record holder
της 07-31) έχει πλέον παιχνίδια **κοντά στο μηδέν** — ένδειξη fragility/route drift.

### Consensus 85% → 24%: παραμένει ανεπιβεβαίωτο

Δεν υπάρχει νεότερο run του topfarms notebook από το ήδη καταγεγραμμένο (08-05 entry). Η
διπλοκόρυφη κατανομή του full-ladder crawl δεν επιβεβαιώνει ούτε διαψεύδει «διάσπαση» της ελίτ —
μετρά άλλον πληθυσμό. Μένει ανοιχτό μέχρι δεύτερη μέρα topfarms δεδομένων.

### Έμμεση μαρτυρία από τα 3 agent notebooks (τοπικά cross-play — ΟΧΙ ladder) <a id="agents-1"></a>

**V13-R3** (cells 0/9/13): εναντίον του exact δημόσιου V21.1 **31-1** (96,9% per-game, 16/16
paired seeds θετικά, μέσο margin **+$2.304**)· εναντίον 6 top-route replay proxies **91-5**
(94,8%, μέσο **+$4.396**)· εναντίον 6 δημόσιων controls **96-0**. Μηχανισμός: **one-turn sell
preemption** ≤30 units (STRAWBERRY/MELON/MILK/WOOL, βήματα ~120–680) με near-mirror gate (route
distance ≤6) και append (όχι front-insert) στη σειρά αγοράς. *Chart cell 5:* παράθυρα preemption
strawberry ~βήματα 420–680, melon ~260–290 & ~520–550 — συνεπή με το sell rhythm
[topfarms-22](#topfarms-22) (strawberry 1η πώληση μέρα 16 ≈ βήμα 384+). **Πρώτη ποσοτική ένδειξη
ότι το «πούλα πριν το κύμα» πληρώνει χιλιάδες ανά παιχνίδι σε mirror matchups** — ευθεία
υποστήριξη του άξονα (β) του MASTERPLAN. Provenance: schedule από OceanMix episode 90343084,
hazard prior από 6 top-route replays (cell 13).

**93-wr** (cells 5/6): αλλάζοντας μόνο `_GLUT_WEIGHT` + liquidation step 718→700 στο v21.1,
ισχυρίζεται μετατροπή **42% draws → 0%** με νίκες margin **+$3** (19 από τα 20 δειγμένα episodes,
cell 6). Ποιοτική ένδειξη ότι **στα mirrors η νίκη κρίνεται σε μονοψήφια δολάρια** — και το
Bradley-Terry μετρά W/L, όχι margin. ⚠️ Αναξιόπιστο ως μέτρηση: το run του 2026-08-06 διαρκεί 4s
και δεν παίζει κανένα παιχνίδι (οι πίνακες είναι hardcoded markdown)· «up to 12 market orders»
ενώ το engine κόβει στα 10· «Average Win Margin 53.5» ασύμβατο με τα +$3 των episodes·
placeholder «[Original Author's Name]» στον τίτλο. Κανένα νούμερό του δεν μεταφέρεται ως μέτρηση.

**structured-economic-policy** (engine **1.32.4 pinned + asserted**, cell 1 — τα market νούμερά
του είναι συμβατά με το μοντέλο του διαγωνισμού): ανεξάρτητο design που συγκλίνει στα δομικά
χαρακτηριστικά του modal top farm — **3 τεταρτημόρια** (γη μέρες 5 & 9), **SE με 0 animal slots**,
**12 hands** (13 από μέρα 21), στόχος 15 ζώα — αλλά **melon-primary** (10 melon tiles NW) αντί
strawberry. Θεωρητικά αποτελέσματα: §6 *order-timing symmetry* — το swing από μετάθεση πώλησης
= 2× το price-impact ορθογώνιο (cell 9)· §8 *withholding is a transfer* — το να κρατάς απόθεμα
είναι μεταφορά αξίας **στον αντίπαλο** όταν εκείνος είναι ο μεγαλύτερος πωλητής στο παράθυρο
(cell 12). Θεμελιώνει πότε το sell-ahead πληρώνει και πότε όχι.

Ταυτότητες: το **93-wr είναι fork του v21.1 του Kaito Fukami** — δηλαδή το 177-180 notebook
ταυτοποιείται πλέον ως δικό του (cell 7 credits). Ο συγγραφέας του structured-economic-policy
δεν προκύπτει από τα metadata (χωρίς kaggle block).

---

## 2026-08-05 — *What the Top Farms Do — A Live Meta* (νέα πηγή)

**Πηγή:** cjlcjlcjl, run 2026-08-06 07:05 UTC, στο **επίσημο** daily dataset
(`kaggle/kaggriculture-episodes-2026-08-05`). **Δείγμα:** ζώνη Elo **≥2800** — 610 episodes,
1.220 παίκτες· το §8.5 Daily Meta Report χρησιμοποιεί ζώνη **≥2700** — 742 episodes, 1.484 παίκτες.
Πλήρες dump: [source/notebooks/kaggriculture-what-the-top-farms-do-a-live-meta.md](../source/notebooks/kaggriculture-what-the-top-farms-do-a-live-meta.md).

### Το modal top farm — η κορυφή ΔΕΝ είναι πια «4/4 τεταρτημόρια + 20 ζώα» <a id="topfarms-19"></a>

**22% των παικτών της ζώνης ≥2800** (24% στη ζώνη ≥2700, cell 28) παίζουν **ακριβώς** την ίδια φάρμα:

> **8 αγελάδες + 5 πρόβατα · 6 strawberry + 1 wheat · 12 hands · γη NE+NW+SW** — το **SE ≈ 0%** αγορασμένο.

- Build order (median): **hire@0, cow@0, sheep@0, land@7**.
- Money στην κορυφαία ζώνη: **median $125.271, max $173.012** (ζώνη ≥2700: median $125.877).
- Νικητές vs ηττημένοι: **$128.287 vs $123.876** — σχεδόν ταυτόσημα πρώιμα οικονομικά·
  η διαφορά κρίνεται αργά και λεπτά, όπως έδειξε και το snapshot 2026-08-01 ([wins-6](#wins-6)).

### Ρυθμός πωλήσεων (πρώτη μέρα πώλησης / μέσο batch) <a id="topfarms-22"></a>

| Προϊόν | 1η πώληση (μέρα) | Batch |
|---|---:|---:|
| Wheat | 5 | 17,9 |
| Fertilizer | 5 | 4,4 |
| Milk | 8 | 7,2 |
| Wool | 9 | 7,3 |
| Melon | 10 | 8,5 |
| **Strawberry** | **16** | **8,9** |

Cash curve (median on-hand cash, όχι net worth): **d5=$127 · d10=$1.435 · d15=$20.732 · d20=$42.961**
— όλα επανεπενδύονται βαθιά μέσα στη σεζόν (συνεπές με [meta-8](#meta-8)).

### Meta clock: η σύγκλιση άρχισε <a id="topfarms-26"></a>

| | 07-30 | 08-04 |
|---|---:|---:|
| Median Elo | 670 | **2.767** |
| Top Elo | 1.152 | **2.996** |

Τελευταία μέρα: **μόνο +36/+37** — η εκρηκτική φάση τελείωσε, η κορυφή συγκλίνει.
Consensus share **85% → 24% σε μία μέρα** (ο συγγραφέας το σημειώνει ως πιθανή ανωμαλία
μέτρησης — μην το διαβάσεις ως πραγματική διάσπαση του meta χωρίς δεύτερη μέρα δεδομένων).
Leaderboard (2026-08-06): **#1 Ben Hamilton 3.043,7 · Konstantin03 3.032,1 · Subin An 2.996,0**.

### ⚠️ Engine mismatch <a id="topfarms-2"></a>

Το εγκατεστημένο `kaggle-environments` του notebook δίνει strawberry cliff **~247 units**·
ο διαγωνισμός τρέχει **1.32.x με cliff 62** (wool 59 / milk 76 / melon 158). Όλα τα νούμερα
του notebook χρησιμοποιούν το embedded 1.32.x μοντέλο — ίδια έκδοση με το MASTERPLAN §1.
Αν δεις αλλού «cliff ~247», είναι από νεότερο build, όχι από τον διαγωνισμό.

### Συμπληρωματικό context: το replay-copy meta (177-180 notebook)

Το agent notebook *177/180 Fresh Top-30 v21.1 Conditional Memory* (run 2026-08-06 04:29,
snapshot 515 episodes από τα top-30 submissions) δείχνει ότι **η κορυφή του LB κυριαρχείται
από αντιγραφή routes**: το παλιό δημόσιο v21/Dennis route έπεσε στο **19/46** στο φρέσκο
top-30, ενώ τα τρέχοντα route families (Konstantin **40/46**, Richard Silence **41/46** medoids)
κυριαρχούν. Επιβεβαιώνει το MASTERPLAN §7 ρίσκο #3: το να αντιγράψεις το χθεσινό meta
είναι ήδη χαμένη στρατηγική — τα routes μετακινούνται (route drift).

### Ενημερωμένο χάσμα (αντικαθιστά την ανάγνωση της κλείδας παρακάτω)

| Μέτρο | Εμείς (v1e) | Κορυφαία ζώνη (≥2800, 08-05) |
|---|---:|---:|
| Median bank | ~$42,6k | **$125,3k** |
| Quadrants | 2 (NW+NE) | **3 (NE+NW+SW)** — SE ποτέ |
| Ζώα | 3 | **13** (8 cow + 5 sheep) |
| Hands | — | **12** |

*(Το «4/4 τεταρτημόρια + 20 ζώα» της παλιάς ανάγνωσης δεν είναι πια το top meta — βλ.
πρόταση διόρθωσης MASTERPLAN §3.4.)*

---

## 2026-08-01 — *What actually wins on the Kaggriculture ladder*

**Δείγμα:** 290 αποφασισμένα παιχνίδια (580 πλευρές) από 300 replays της 1ης Αυγ, 75 διακριτοί
agents. Μέσο final profit: **νικητές $118.420 | ηττημένοι $110.265**.

### Το πιο σημαντικό εύρημα: ο όγκος δεν διακρίνει <a id="wins-6"></a>

Μέσοι όροι ενεργειών σε ολόκληρη τη σεζόν, νικητές έναντι ηττημένων:

| Ενέργεια | Νικητές | Ηττημένοι | Λόγος |
|---|---:|---:|---:|
| plant | 74,2 | 81,0 | **0,9** |
| sell | 331,1 | 322,3 | 1,0 |
| hire | 290,9 | 294,7 | 1,0 |
| harvest | 258,1 | 256,1 | 1,0 |
| fert | 287,2 | 280,8 | 1,0 |
| buy_animal | 7,6 | 8,0 | 1,0 |
| buy_land | 2,5 | 2,8 | 0,9 |

> **Στην κορυφή του ladder όλοι κάνουν τα ίδια πράγματα σε σχεδόν ίδιες ποσότητες.** Οι νικητές
> φυτεύουν *λιγότερο* και αγοράζουν *λιγότερη* γη. Η διαφορά δεν είναι πλέον «πόσο» — είναι
> **πότε, τι, και σε ποια τιμή**. Ένα bot που απλώς κάνει *περισσότερα* δεν ανεβαίνει από εδώ.

### Win rate ανά κύριο crop <a id="wins-8"></a>

| Primary crop | Win rate | n |
|---|---:|---:|
| **STRAWBERRY** | **53%** | 515 |
| MELON | 43% | 7 |
| WHEAT | 30% | 53 |
| CARROT | 0% | 5 |

> Το **STRAWBERRY είναι το de facto meta** — 515 από 580 πλευρές. Τα υπόλοιπα δείγματα είναι
> πολύ μικρά για συμπέρασμα (MELON n=7, CARROT n=5). Το εύρημα δεν είναι «το strawberry είναι
> καλύτερο», είναι «**σχεδόν όλοι** παίζουν strawberry» — που, δεδομένης της γραμμικής καμπύλης
> κατάρρευσής του ([market.md §3](docs/reference/market.md#3-saturation--πόσο-αντέχει-το-κάθε-προϊόν)),
> είναι επίσης η μεγαλύτερη ευκαιρία αρμπιτράζ για όποιον πουλά **πριν** από αυτούς.

### Ρυθμός βελτίωσης (daily index) <a id="wins-10"></a>

| Ημερομηνία | Episodes | Top avg score | Median avg score |
|---|---:|---:|---:|
| 2026-07-30 | 864 | 1.152,4 | 669,8 |
| 2026-07-31 | 928 | 1.427,0 | 1.175,3 |
| 2026-08-01 | 829 | 1.580,6 | 1.348,2 |

*(Αυτά είναι **ratings**, όχι banks. Ο median κυνηγά το top: +101% σε δύο μέρες.)*

---

## 2026-07-31 — *Kaggriculture Daily Replays: The Live Meta Report*

**Δείγμα:** 1.285 episodes (100% με πλήρες replay), 1.196 ladder games, 255 submissions, 95 teams,
12 ώρες ladder. Τα validation (self-play, 7%) εξαιρούνται από κάθε σύγκριση ισχύος.

### Κατανομή νικητήριων banks <a id="meta-6"></a>

| p25 | median | p90 | **record** |
|---:|---:|---:|---:|
| $28.707 | **$39.652** | $96.424 | **$157.449** |

Το ρεκόρ είναι **4,0×** τον median νικητή.

### Το σχήμα ενός μεγάλου παιχνιδιού <a id="meta-8"></a>

> Κάθε κορυφαία φάρμα περνά **το ένα δέκατο** του τελικού της bank στην **in-game μέρα 11 / 15 / 11**
> (top-1/2/3). **Εκεί κρίνεται το παιχνίδι, όχι στο τελευταίο σπριντ.** Το bank μένει κοντά στο
> μηδέν βαθιά μέσα στη σεζόν όσο τα πάντα επανεπενδύονται, και μετά αναλαμβάνει ο ανατοκισμός.

### Strategy fingerprints <a id="meta-11"></a>

| Ποιος | Bank | Hires/μέρα | Peak crew | 1η γη (μέρα) | Tiles φυτεμένα | Top crop |
|---|---:|---:|---:|---:|---:|---|
| **Victor @ Tufa Labs** (record) | $157.449 | 10,8 | **13** | **0** | 105 | Strawberry |
| Max Manushin | $143.707 | 7,9 | 12 | 10 | 78 | Melon |
| Max Manushin | $135.131 | 7,9 | 12 | 10 | 73 | Melon |
| *Maxim (mid-ladder)* | $38.514 | 6,8 | 7 | **ποτέ** | 86 | Melon |

> **Το μετρήσιμο πλεονέκτημα του πρωταθλητή είναι εργασία και γη:** crew **13** έναντι **7** του
> mid-ladder, και γη τη **μέρα 0** ενώ η mid-ladder φάρμα δεν αγοράζει **ποτέ**. Τα τρία
> μεγαλύτερα κέρδη **διαφωνούν** για το ποιο crop να πρωταγωνιστεί (Strawberry, Melon, Melon) —
> **αυτό που επαναλαμβάνεται είναι τα οικονομικά γύρω από το φυτό, όχι το φυτό.**

### Αγορά μέσα στο παιχνίδι-ρεκόρ <a id="meta-13"></a>

Melon: ξεκινά **$250**, πάτος **$184**, κορυφή **$278** — διακύμανση **38%** του base.
Wheat: **$25 → $56** με base $25. *«Το wheat που σκαρφαλώνει τόσο πάνω από το base συνήθως σημαίνει
φάρμες με ζώα που αγοράζουν feed πιο γρήγορα απ' ό,τι τροφοδοτεί η πόλη.»*

### Ρυθμός & θόρυβος

- Ο median νικητήριος bank πήγε **$27.880 → $60.016 σε 12 ώρες ladder** (**+115%**)· η πιο πρόσφατη μέρα κινήθηκε **+29%** έναντι της προηγούμενης. <a id="meta-15"></a>
- Τυπική διασπορά ανά submission (≥4 παιχνίδια): **19%** του median bank (χειρότερη: 950%). <a id="meta-19"></a> **Ένα episode δεν αποδεικνύει σχεδόν τίποτα.**

### Επιφυλάξεις του ίδιου του συγγραφέα <a id="meta-23"></a>

- Τα fingerprints διαβάζουν **ένα καλύτερο παιχνίδι** ανά submission — σκίτσο στην κορυφή του, όχι μέση συμπεριφορά.
- Το corpus είναι **crawl, όχι απογραφή**· νέο submission μπορεί να καθυστερεί ώρες.
- Τα head-to-head κελιά στέκονται σε **λίγα παιχνίδια** — 100% σε 2 παιχνίδια είναι ανέκδοτο.
- Οι εκτιμήσεις διασποράς είναι **τάξης μεγέθους**, όχι ακριβείς.

---

## Σταθερή ανάγνωση: το χάσμα μας

> **⚠️ Ξεπερασμένο (2026-08-06):** ο πίνακας παρακάτω βασίζεται στις μετρήσεις 31 Ιουλ – 1 Αυγ.
> Το «Ladder top: 4 quadrants / 20 ζώα» δεν ισχύει πια — δες το ενημερωμένο χάσμα στην
> εγγραφή **2026-08-05** παραπάνω (3 quadrants, 13 ζώα, 12 hands, median $125k στην κορυφαία ζώνη).
> Κρατιέται ως έχει για την καμπύλη του meta.

| Μέτρο | Εμείς (v1e, holdout vs `starter`) | Ladder median | Ladder top |
|---|---:|---:|---:|
| Median bank | **~$42,6k** | ~$40-45k | ~$118k (avg κορυφής), record $157k |
| Quadrants | 2 (NW + NE) | — | **4** |
| Ζώα | 3 | — | **20** |
| Peak crew | — | 7 | **13** |

*(Δικά μας νούμερα: [memory.md](memory.md), εγγραφή 2026-08-06. Το ladder αναφέρεται σε
μετρήσεις 31 Ιουλ - 1 Αυγ και **έχει ήδη μετακινηθεί**.)*

> **Το χάσμα είναι δομικό, όχι παραμετρικό** — και το snapshot της 1ης Αυγ το επιβεβαιώνει από
> την ανάποδη: στην κορυφή, οι μετρήσεις όγκου (plant/sell/hire/harvest) είναι **ταυτόσημες**
> μεταξύ νικητών και ηττημένων. Πρώτα κλίμακα (γη + hands + ζώα), μετά ποιότητα απόφασης· το
> tuning παραμέτρων πριν από αυτά βελτιστοποιεί σε λάθος ταβάνι
> ([MASTERPLAN §3.4](docs/MASTERPLAN.md)).
