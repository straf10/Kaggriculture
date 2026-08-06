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
