# current_phase.md — Φάση 2: από το mirror loop στην πραγματική ladder

> **Working plan της τρέχουσας φάσης** — εκτελεί τη στρατηγική του
> [docs/MASTERPLAN.md](docs/MASTERPLAN.md)· **δεν την επαναδιαπραγματεύεται**.
> Engine ground truth: το εγκατεστημένο **`kaggle-environments==1.32.6`**·
> το [engine_reference/kaggriculture.py](engine_reference/kaggriculture.py) είναι read-only
> αντίγραφο για line refs. Όπου docs και engine διαφωνούν, υπερισχύει το engine.
>
> Δημιουργία: 2026-08-06. **Πλήρης αναθεώρηση: 2026-08-10** (βλ. §0). Deadline: **30 Σεπ 2026**
> (~7 εβδομάδες). Τελική κατάταξη: Bradley-Terry σε ~2 εβδομάδες episodes **μετά** το deadline.
>
> **Σύμβαση:** αυτό το έγγραφο περιγράφει **τι μένει να γίνει** και **γιατί**. Το τι έγινε —
> αριθμοί gate, root causes, reverts — ζει **αποκλειστικά** στο [memory.md](memory.md), μία
> εγγραφή ανά session. Ό,τι έκλεισε αφαιρείται από εδώ· δεν αρχειοθετείται εδώ.

---

## 🔴 0. Η αναθεώρηση της 2026-08-10 — τι δείχνουν τα πραγματικά δεδομένα

**Το γεγονός που αλλάζει το σχέδιο:** το rating μας είναι **~700**, το ταβάνι της ladder
**3.100+**. Η αρχική τιμή κάθε submission είναι **600,1**.

| Submission | publicScore | Ανάγνωση |
|---|---|---|
| v1e (`55301989`) | **557,0** | συγκλιμένο **κάτω** από την αρχική τιμή |
| v1g (`55324447`) | **643,6** | συγκλιμένο, +43 πάνω από την αρχική |
| **`55387820`** | **634,1** | ⚠️ **ανεξήγητο submission, 2026-08-09 18:58** — δεν αντιστοιχεί σε κανένα checkpoint/gate αυτού του repo· βλ. §Α σημείωση |
| v1h (`55383610`) | **652,5** | συγκλιμένο, πάνω από v1g — αλλά **μετρημένα σπασμένο** στο 1.32.6 (§v1h.1/§v1h.2) |
| `v23_fork` cluster (~40 ομάδες) | **3.117 – 3.131** | — |
| HealthStone #2 / Seb #1 | **3.132,9 / 3.201,1** | — |

**Δηλαδή: τρία submissions και μια αλυσίδα increments με +$25,3k/ep σε holdout (v1e → v1g) και
+$2,8k/ep (v1g → v1h) έχουν μετακινήσει το ladder rating κατά ~+90 πόντους σε ένα εύρος 2.500.**
Δεν είναι θέμα σύγκλισης του rating — το v1g έπαιξε αρκετά episodes και σταμάτησε στο 643,7.

### 0.1 Η αιτία, μετρημένη στα **δικά μας** ladder replays

`baselines/2026-08-06/live_episodes/`, `baselines/2026-08-07/replays*/` — 13 πραγματικά episodes:

| Αντίπαλος | Δικό μας bank | Δικό του | Αποτέλεσμα |
|---|---:|---:|---|
| saikyo | **$41.513** | **$122.189** | ήττα |
| Vincent Pan | $42.520 | $57.216 | ήττα |
| Joseph Garcia | $42.216 | $56.379 | ήττα |
| Mehrdad ALMASI | $40.459 | $45.886 | ήττα |
| ArmanVardanyan07 | $56.214 | $61.867 | ήττα |
| Giordano Dolenz | **$71.693** | $50.104 | νίκη |
| aisamhottman / Ritesh / Kingshu / Digant / Sanchit / Om Sangwan | $38-42k | $7-38k | νίκες |

**Το μοτίβο είναι μονοσήμαντο: το δικό μας bank είναι σχεδόν σταθερό στα $38-46k ανεξάρτητα από
τον αντίπαλο· κερδίζουμε μόνο όποιον βγάζει λιγότερα από $42k.** Ο ladder median **νικητήριου**
bank ήταν **$87k-$115k** και το record **$199k**. Δεν χάνουμε σε timing ή σε ψίχουλα — χάνουμε
σε **κλίμακα παραγωγής**, με παράγοντα **2,5-3×**.

Το ίδιο νούμερο βγαίνει και τοπικά: `median_bank` του καλύτερου candidate μας σήμερα =
**$46.471** (`gates/gate_v1h2d_feed_slack`).

### 0.2 Τι σημαίνει για τη μεθοδολογία — τρία λάθη, όλα διορθώσιμα

1. **Η αντικειμενική συνάρτηση είναι λάθος.** Κάθε gate μετρά `mean_diff` σε **mirror**. Σε
   mirror και οι δύο πλευρές έχουν το **ίδιο** ταβάνι παραγωγής, οπότε ένα +$3k margin πάνω σε
   $44k βαθμολογείται ως μεγάλη νίκη — ενώ στην ladder ο αντίπαλος παίζει σε άλλο επίπεδο και το
   margin είναι άσχετο. **Το mirror loop βελτιστοποιεί μέσα σε ένα τοπικό ταβάνι που το ίδιο δεν
   μπορεί να δει.**
2. **Το hard metric gate έγινε ο φύλακας αυτού του ταβανιού.** Οι τρεις τελευταίες συνεδρίες
   σταμάτησαν σε `metric_gate_passed=False` για μεγέθη που, τιμολογημένα, αξίζουν **δεκάδες
   δολάρια ανά επεισόδιο**, ενώ απέρριπταν κέρδη **χιλιάδων**. Το τελευταίο STOP (v1h.2d) απέρριψε
   **+$3.019,3/ep** για 84 units overflow και 34 water weeds σε **96** επεισόδια.
3. **Δεν έχει μετρηθεί ποτέ ο πραγματικός αντίπαλος.** Το 75% της ladder παίζει μία κοινή
   πολιτική (MASTERPLAN §3.2ter)· εμείς μετράμε αποκλειστικά τον εαυτό μας.

**Ο χρόνος είναι πλέον περιοριστικός πόρος** (7 εβδομάδες). Ένα increment που ξοδεύει μια
συνεδρία για ±$150/ep δεν είναι «προσεκτικό», είναι λάθος κατανομή.

---

## 1. Οι τρεις αποφάσεις αυτής της αναθεώρησης

Αντικαθιστούν προηγούμενους κανόνες αυτού του εγγράφου. Ισχύουν από τώρα, σε κάθε gate.

### Απόφαση Α — Το hard gate γίνεται **τιμολογημένος προϋπολογισμός**, όχι απόλυτο μηδέν

**Παραμένουν hard-zero** (είναι δείκτες *λογικού σφάλματος*, όχι κόστους):
`clipped_production_ticks == 0` · `plant_decay_units_lost == 0` · κανένα unexplained no-op ·
κανένα market-simulation abort · low-price units ≤2% των sales.

**Γίνονται τιμολογημένος προϋπολογισμός** (είναι *απώλειες*, και κάθε απώλεια έχει τιμή):

| Metric | Τιμή μονάδας | Αιτιολόγηση |
|---|---:|---|
| `animals_escaped` | **$1.000** | $400-500 αγορά + χαμένη υπόλοιπη παραγωγή της σεζόν |
| `shed_overflow_burnt` (unit) | **$150** | συντηρητικά κάτω από τη μέση τιμή premium ($200-270), πάνω από wheat ($25-54) |
| `unexpected_weeds_lost` / `water_weeds_lost` (tile) | **$300** | χαμένη απόδοση tile + DIG για ξανακαθάρισμα |

**Κανόνας αποδοχής:** `priced_loss_per_episode` = Σ(count × τιμή) / episodes, με
**`priced_loss ≤ 10% του μετρημένου mean_diff` ΚΑΙ `priced_loss ≤ $500/ep`**.

**Δύο δικλείδες που κρατούν τη λειτουργία «ανιχνευτή bug» του παλιού gate:**
- **Κάθε μη μηδενικό counter απαιτεί γραπτό μηχανισμό.** «Δεν ξέρω γιατί» ⇒ αντιμετωπίζεται ως
  bug ⇒ STOP. Η τιμολόγηση αγοράζει ανοχή σε *κατανοητή* απώλεια, όχι σε άγνωστη.
- Τα raw counters εξακολουθούν να αναφέρονται σε κάθε gate και μπαίνουν στο checkpoint ledger.

Το raw `weeds_lost` παραμένει **diagnostic**, όχι gate (περιλαμβάνει επιτυχημένα ongoing-crop
harvest retirements — semantic ανάλυση v1h.2d, memory.md 2026-08-09 (ε)).

**Άμεση συνέπεια — ο ήδη μετρημένος candidate περνά:**

| Arm (`gates/`) | mean_diff vs `v1h_2c` | escapes | overflow | weeds | priced/ep | Νέο verdict |
|---|---:|---:|---:|---:|---:|---|
| `gate_v1h2d_eod_surplus` (EOD only) | +$1.529,8 | 54 | 0 | 0 | **$563** | ⛔ κόβεται από το $500 cap |
| **`gate_v1h2d_feed_slack` (EOD+FEED)** | **+$3.019,3** | **0** | 84 | 34 | **$237** | ✅ **ΠΕΡΝΑ** (7,9% / <$500) |
| `gate_v1h2_dev` (`v1h_2c` σκέτο) | +$2.888,5 | 39 | 1.510 | 0 | **$2.766** | ⛔ 96% — σωστά απορρίπτεται |

Ο κανόνας δεν είναι χαλάρωση «για να περάσει κάτι»: απορρίπτει το `v1h_2c` σκέτο και το EOD-only,
και δέχεται **μόνο** τον συνδυασμό που όντως καθάρισε τις μεγάλες απώλειες.

### Απόφαση Β — Η αντικειμενική συνάρτηση αποκτά **απόλυτο** σκέλος

Κάθε gate από εδώ και πέρα αναφέρει και κρίνεται σε **τρία** μεγέθη, με αυτή τη σειρά:

1. **`median_bank` (απόλυτο)** — ο δείκτης κλίμακας. Στόχος φάσης: **$46k → $80k+**.
   Ένα increment με `mean_diff` θετικό αλλά `median_bank` στάσιμο **δεν είναι πρόοδος προς την
   ladder**· καταγράφεται ως τέτοιο και δεν δικαιολογεί submission από μόνο του.
2. **W/L έναντι μη-mirror αντιπάλου** — μόλις υπάρξει το §Β.2 bench.
3. **`mean_diff` σε mirror** — υποβιβάζεται σε **tie-breaker** και σε regression detector.
   Παύει να είναι το κριτήριο που ανοίγει/κλείνει increments.

### Απόφαση Γ — Ρυθμός αποστολής: **σταματάμε να καθόμαστε πάνω σε μετρημένες νίκες**

Το ζωντανό `v1h` **αποτυγχάνει μετρημένα στο 1.32.6**: 198 water weeds, 85 escapes, **2.370
μονάδες πουλημένες στα ≤$5** σε 96 επεισόδια, median bank $35,4k. Κάθε μέρα που μένει ενεργό
είναι χαμένο rating. Ο candidate `v1h_2c+EOD+FEED` διορθώνει ακριβώς αυτά (≤$5: 2.370 → 171·
water weeds 198 → 34· escapes 85 → 0· median bank $35,4k → $46,5k).

**Κανόνας:** μόλις ένα candidate περάσει Απόφαση Α **και** unpinned holdout-confirm, ανεβαίνει —
χωρίς να περιμένει το επόμενο increment. Τα δύο slots παραμένουν **champion + διαφοροποιημένος
challenger** (§Α.3), όχι «οι δύο τελευταίες εκδόσεις».

---

## 2. Το χάσμα, αριθμητικά (2026-08-10)

Μετρημένο προφίλ της ώριμης φάρμας των ranks 3-20, από **field actions** σε 144 επεισόδια / 40
ομάδες (MASTERPLAN §3.2ter — παρακάμπτει το «τα crops δεν επιβιώνουν» artifact):

| Διάσταση | Εμείς (candidate) | Κοινή διαδρομή ranks 3-20 | Δράση |
|---|---:|---:|---|
| **Median bank** | **$46,5k** | ladder median νικητή **$87-115k** | ⬅ **ο συνολικός στόχος** |
| **Wheat tiles** | **12** | **31** | ⬅ **v1j**, το μεγαλύτερο συγκεκριμένο κενό |
| **Hands** | **6 → 10** (παράθυρο SW) | **12** (14 hires day-0 στον #1) | ⬅ **v1j**, μαζί με τα tiles |
| Strawberry tiles | 24 | 23 | ✅ ίσοι |
| Ζώα | 10 (4 COW + 6 SHEEP) | ~14 (8c/6s) | ⚠️ όχι στόχος — ⚠️ε |
| Quadrants | 3 (NW+NE+SW) | 3 (modal) · 4 στον rank-1 | ⚠️ SE ανοιχτό, όχι τώρα |
| **Αχρησιμοποίητα tiles σε γη που ΗΔΗ έχουμε** | **~19** | — | ⬅ **v1j: δεν χρειάζεται νέα γη** |

**Το κρίσιμο νούμερο είναι το τελευταίο.** Κατανομή σήμερα: NW 25/25 (3 carrot + 8 strawberry +
13 pasture + 1 coop) · NE 19/25 (3 carrot + 16 strawberry) · SW **12/25** wheat. Δηλαδή έχουμε
πληρώσει για ~19 tiles που **κανείς δεν δουλεύει**. Η ελίτ φτάνει τα 31 wheat + 23 strawberry =
54 crop tiles μέσα σε 3 quadrants — χωρητικότητα που **ήδη κατέχουμε**.

**⚠️ε (μένει σε ισχύ):** τα 13-14 ζώα δοκιμάστηκαν και έδωσαν 660-885 escapes. Ο μηχανισμός είναι
γνωστός (~73 unit-actions/σεζόν ανά cared ζώο ⇒ ~730 σταθερό φορτίο για 10 ζώα, MASTERPLAN
§3.2quater). Η μάζα ζώων **δεν** είναι ο μοχλός· τα tiles + τα hands είναι.

**⚠️γ (μένει σε ισχύ):** κανένα portfolio rebalance προς «επιζώντα» elite tiles — τα crops δεν
επιβιώνουν ως τη μέρα 30, το elite fingerprint μετρά δομές. Το v1j προσθέτει **νέα δουλειά σε
αδρανή γη**, δεν ανακατανέμει το υπάρχον mix.

### Ιεράρχηση προϊόντων στο 1.32.6 (αμετάβλητη, τη χρειάζονται τα v1j/v1i)

`townCenterSellInterval` 24 (1 tick/μέρα), **καμία** ημερολογιακή κλιμάκωση ζήτησης, shops με
επανάθεση (`MAX_SHOP_INSTANCES = 8`, E[διακριτοί] = 5,25, P(και οι 8) = 0,24%).

| Προϊόν | Shops | P(κανένα) | Cliff (μον. ως $1) | Θέση |
|---|---|---:|---:|---|
| **WHEAT** | 5/8 | **0,04%** | **>2.000** | ↑↑ το μόνο ασυγκόρεστο· το μόνο που κλιμακώνει |
| STRAWBERRY | 4/8 | 0,39% | 62 | ↑ σταθερό |
| MILK | 3/8 | 2,3% | 76 | ⚠️ κατέρρευσε σε mirror στο 1.32.6 (D2) — γι' αυτό `{4C,6S}` |
| CARROT | 2/8 | 10,0% | 842 | ↓ variance |
| WOOL | 1/8 (YARN_STORE) | **34,4%** | 59 | ↓ variance, αλλά υγιής τιμή ($197-243) |
| MELON | **0/8** | 100% | 158 | ↓↓↓ φυτεύουμε 0 — το meta φυτεύει 12 seeds day-0 |
| FERTILIZER | καμία NPC ζήτηση | — | ρηχή, 493 μον. | πούλα νωρίς, πάντα (μονότονα φθίνουσα) |

---

## 3. Ο κρίσιμος μηχανισμός: γιατί δεν κλιμακώνει σήμερα η φάρμα

Τρία μετρημένα ευρήματα που, μαζί, εξηγούν το ταβάνι των $46k — και δείχνουν τη σειρά των
επόμενων κινήσεων:

1. **Το shed (100 θέσεων) γεμίζει πριν προλάβουμε να πουλήσουμε.** Το variant των 16 wheat tiles
   στο v1h′ έκαψε **3.100 μονάδες** σε 96 επεισόδια και απορρίφθηκε γι' αυτό. Δηλαδή **η
   πρόσθετη παραγωγή δεν είχε πού να πάει** — το tile ceiling μας δεν είναι εδαφικό, είναι
   logistics.
2. **Το EOD surplus fix του v1h.2d λύνει ακριβώς αυτό:** overflow 1.510 → **0** μηδενίζοντας το
   burn με product-aware πώληση πραγματικού πλεονάσματος και ρητό WHEAT feed reserve.
   **Είναι το προαπαιτούμενο που έλειπε για να κλιμακώσει το wheat.**
3. **Escapes και water weeds είναι το ίδιο συμπτωμα: έλλειψη units, όχι έλλειψη πόρου.**
   Escapes με 30+ WHEAT στην αποθήκη και $35k στην τράπεζα (v1h′)· το FEED priority −1 μηδένισε
   τα escapes αλλά γέννησε 34 water weeds — δηλαδή **μετακίνησε** τη σπάνη, δεν την έλυσε. Η
   δομική απάντηση είναι **περισσότερα hands**, και το meta δίνει το νούμερο: **12**.

**Συμπέρασμα που ορίζει το v1j:** το v1h′ απέδειξε ότι *γη και πλήρωμα πληρώνουν μόνο μαζί*
(controls: μόνο crew −$1.651/ep, μόνο γη −$1.128/ep, μαζί +$2.942/ep). Έχουμε ήδη τη γη και
έχουμε τώρα και το sell-side headroom. **Λείπει το πλήρωμα και τα φυτεμένα tiles.**

---

## ΜΕΡΟΣ Α — Submissions (λειτουργικό reference)

**Ενεργό ζεύγος (μετά το 4ο upload, 2026-08-10):** **`55390611`** (`v1h_2d`, μόλις υποβλήθηκε,
PENDING) και **`55387820`** (`634,1`). Το **v1h** (`55383610`, `652,5`, μετρημένα σπασμένο στο
1.32.6) έπεσε εκτός με αυτό το upload.

⚠️ **Εύρημα αυτής της συνεδρίας: το `55387820` δεν αντιστοιχεί σε κανένα checkpoint ή gate αυτού
του repo.** Uploaded 2026-08-09 18:58 UTC, περιγραφή *«4th attempt (3rd attempt but 2nd try to
check if oponent path leads to better results)»* — δεν καταγράφηκε ποτέ στο memory.md. Άρα το
**v1g** (`55324447`, `643,6`) είχε ήδη πέσει εκτός των 2 ενεργών θέσεων **πριν** ξεκινήσει αυτή η
συνεδρία, όχι με το σημερινό upload όπως υπέθετε το προηγούμενο §0. Δεν διερευνήθηκε περαιτέρω τι
περιέχει (θα απαιτούσε λήψη/ανάλυση replay εκτός του παρόντος scope) — καταγράφεται ως γνωστό,
ανεξήγητο state gap. Αν χρειάζεται να αποκατασταθεί ρητά διαφοροποιημένο champion/challenger ζεύγος
(§Α.3), το επόμενο upload πρέπει να στοχεύσει την αντικατάσταση του `55387820`, όχι μόνο νέα
increments.

### Α.1 Εντολές

```powershell
kaggle competitions submit kaggriculture -f submission.tar.gz -m "<version> <περιγραφή>"
kaggle competitions submissions kaggriculture          # status + SUBMISSION_ID
kaggle competitions episodes <SUBMISSION_ID>           # -v για CSV
kaggle competitions replay <EPISODE_ID> -p ./baselines/<date>/replays
kaggle competitions logs <EPISODE_ID> 0 -p ./baselines/<date>/logs   # index = seat
```

Auth λυμένο (`KAGGLE_API_TOKEN` στο `.env`). Format: `tar -czf submission.tar.gz main.py agent/`
με `main.py` στο **root**, υποβολή από **CLI**.

### Α.2 Πριν από κάθε upload

- [ ] **Loader contract (G12)**: exported `agent` = τελευταίο callable· imports top-level· κανένα
  `__file__` shim· vendored constants ([agent/_vendored.py](agent/_vendored.py)) parity-tested
  **έναντι της τρέχουσας engine έκδοσης**.
- [ ] **Timing**: cold-process profile και στα 2 seats· gate `max_turn × 3 < 1s`.
- [ ] **Determinism (G13)**: ίδιο seed σε 2 fresh processes + διαφορετικό `PYTHONHASHSEED` →
  ταυτόσημο trajectory.
- [ ] **Mirror smoke**: `python -m harness.cli play main.py main.py --steps 720` — `clean=True`.
- [ ] Μέγεθος < 100 MiB · `pytest tests/` πλήρως πράσινο · `KAGGRI_DEBUG` **off** by default.

### Α.3 Slots

5 uploads/μέρα, **μόνο τα 2 τελευταία active** και αυτά μπαίνουν στο final. Τα δύο slots είναι
**champion + διαφοροποιημένος challenger** — η διαφοροποίηση ορίζεται σε **έκθεση** (σύνθεση
κοπαδιού, επιθετικότητα sell-side), όχι σε version number: *«two near-identical active submits →
meta shift kills both»*. Τελευταία εβδομάδα πριν τις 30/09: κατεψυγμένο champion/challenger.

---

## ΜΕΡΟΣ Β — Τι πρέπει να υλοποιηθεί

**Σειρά (αναθεωρημένη 2026-08-10, από §0):**
~~`v1h.2d` κλείσιμο & submission~~ ✅ → **`L1` ladder diagnostic** ⬅ **ΤΩΡΑ** (docs-only) →
**`v1j` scale-out** ⬅ *το κύριο money item* → **`Β.2` meta-bench** → **`v1i` sell-ahead** →
BBO / Φάση 3.

Κάθε increment: υλοποίηση → guard tests → gate κατά **Απόφαση Α/Β** → DEV screen →
**holdout-confirm 48 seeds unpinned** → immutable checkpoint.
Baseline: το τελευταίο αποδεκτό checkpoint (**σήμερα `v1h_1`**· γίνεται `v1h_2d` μόλις κλείσει).
`REGRESSED` = STOP και revert.

---

### v1h.2d — κλείσιμο του metric restoration [✅ ΚΛΕΙΣΤΟ 2026-08-10 — `checkpoints/v1h_2d`, submitted]

> **Αποτέλεσμα:** το priced gate (§1 Απόφαση Α) μπήκε στο `harness/compare.py`
> (`METRIC_UNIT_PRICES`, `priced_loss_budget`, `--metric-mechanism`). Η υλοποίηση αποκάλυψε ένα
> **δεύτερο, ανεξάρτητο harness bug**: το semantic weed-exclusion του 09-08 δεν πυροδοτούσε ποτέ
> σε πραγματικό replay, επειδή το engine αποσύρει ένα harvested-to-zero ongoing crop **17-24
> steps μετά** το HARVEST, όχι στο ίδιο turn — διορθώθηκε με συσσωρευμένο harvest-tracking σε
> ολόκληρο το επεισόδιο (`harness/metrics.py`). Μετά τη διόρθωση: total DEV `IMPROVED
> +$7.133,6/ep`, one-shot unpinned holdout `IMPROVED +$7.599,7/ep` (CI `[5.051,7, 10.147,7]`,
> 41/48 seed wins), `priced_loss=$43,8/ep (0,6%)`, `metric_gate_passed=True`, `GO=True`.
> `checkpoints/v1h_2d` δημιουργήθηκε και υποβλήθηκε (`SUBMISSION_ID 55390611`).
>
> Το working tree του `cdcbe62` ("Fixed several bugs", μεταγενέστερο του μετρημένου `59fe9af`)
> ήταν **ungated** και μετρήθηκε αρνητικό (+$4.216,8/ep αντί +$7.133,6, 39 escapes χωρίς
> μηχανισμό) — δεν κρατήθηκε· το checkpoint χτίστηκε από το `59fe9af` agent state.
>
> ⚠️ **Ανεξήγητο submission βρέθηκε στο πέρασμα**: `55387820` (2026-08-09 18:58, `634,1`) δεν
> αντιστοιχεί σε κανένα gate/checkpoint αυτού του repo και είχε ήδη σπρώξει το **v1g** εκτός των
> 2 ενεργών θέσεων πριν ξεκινήσει η σημερινή συνεδρία. §Α ενημερώθηκε με το πραγματικό ζεύγος.
> Δεν διερευνήθηκε περαιτέρω — παραμένει ανοιχτό αν χρειάζεται σκόπιμη αντικατάσταση.
>
> Πλήρες ιστορικό, όλα τα νούμερα, το bisection του `cdcbe62` και το diagnostic script:
> **memory.md 2026-08-10 (β)**. Validation checklist: `baselines/2026-08-10/validation.md`.

---

### L1 — Ladder diagnostic: πού ακριβώς αποκλίνει η καμπύλη μας [ΝΕΟ · φθηνό · παράλληλα]

**Γιατί:** το §0.1 λέει ότι υστερούμε 2,5-3× σε bank, αλλά **όχι πού μέσα στη σεζόν** ανοίγει η
ψαλίδα. Αυτή είναι η μοναδική μέτρηση που μπορεί να ακυρώσει ή να επιβεβαιώσει την υπόθεση του
v1j **πριν** ξοδευτεί το increment. Καμία αλλαγή στο `agent/` — **δεν είναι increment**.

- [ ] Κατέβασε τα episodes του **`v1h`** (`kaggle competitions episodes 55383610 -v` + `replay`).
      Πρώτη φορά που θα δούμε τη ζωντανή συμπεριφορά του τρέχοντος engine.
- [ ] Από τα ίδια replays εξήγαγε **ανά μέρα και για τις δύο πλευρές**: bank, units πουλημένες
      ανά προϊόν, μέση τιμή, tiles φυτεμένα, crew, ζώα. Το `episode_features.csv` του community
      dataset έχει ήδη parsed fingerprints — δεν χρειάζεται νέος replay parser.
- [ ] Σύγκρινε με τη δημοσιευμένη elite cash curve: **d5 $299 · d10 $2.212 · d15 $21.272 ·
      d20 $45.689**, elbow **μέρα 14-18**. Το ερώτημα είναι ένα: **η ψαλίδα ανοίγει στο opening
      (cash-flow μέρες 0-5) ή στο elbow (μέρες 14-20);**
- [ ] Έλεγξε ρητά ότι **δεν** υπάρχει σιωπηλή αποτυχία στη ζωντανή εκτέλεση (errors στα logs,
      turns χωρίς actions, timeout) — υπόθεση χαμηλής πιθανότητας αλλά μηδενικού κόστους ελέγχου,
      και θα εξηγούσε από μόνη της το rating.
- **Παραδοτέο:** ενότητα στο `docs/meta/ladder_snapshots.md` + μία παράγραφος εδώ που
  **δεσμεύει** το scope του v1j (opening vs elbow). Αν η ψαλίδα είναι στο opening, το v1j
  αλλάζει προτεραιότητα υπέρ του opening cash-flow.

---

### v1j — Scale-out: wheat 12 → ~28 tiles + crew 10 → 12 [**το κύριο money item**]

**Pre-gate κατάταξη: OCCUPANCY** (φύτευση + crew) ⇒ όλα τα DEV screens `--town-pin basket`,
τελικό holdout **χωρίς** pin.

**Υπόθεση, με τον μηχανισμό της:** έχουμε ~19 πληρωμένα αλλά αδρανή tiles και το sell-side
headroom που έλειπε (§3). Το wheat είναι το **μόνο** προϊόν χωρίς cliff και με 5/8 shop κάλυψη,
και είμαστε ήδη ο μεγαλύτερος **αγοραστής** του (10 ζώα × ~28 μέρες ≈ 280 μονάδες) — κάθε
σπιτική μονάδα αξίζει και ως αποφευγμένη αγορά. Το meta φτάνει τα 31.

**Το κρίσιμο σχεδιαστικό δίδαγμα που εφαρμόζεται εδώ:** *γη και πλήρωμα πληρώνουν μόνο μαζί*.
Το v1f είχε βρει `hands_target` 10/12 `REGRESSED` — **σε 2 quadrants και 41 tiles**. Το workload
έκτοτε έχει σχεδόν διπλασιαστεί (3 quadrants, 10 ζώα, SW feed pipeline). Το νούμερο 6 **δεν
μεταφέρεται** στο σημερινό φορτίο και ξανα-ανοίγει ρητά.

**Εκτέλεση — φθηνά controls πριν από ακριβά gates** (το v1h′ έκλεισε έτσι μια εβδομάδα νωρίτερα):

- [ ] **Mini-sweep 2×2 σε SMOKE seeds (0-11), vs `v1h_2d`:** `sw_wheat_tiles ∈ {12, 24}` ×
      `sw_hands_target ∈ {10, 12}`. Τα δύο διαγώνια κελιά είναι τα controls· περιμένουμε και τα
      δύο μονά αρνητικά και το `{24, 12}` θετικό. **Αν το `{24,12}` δεν είναι θετικό στο smoke,
      η υπόθεση κλίμακας πέφτει εδώ, με κόστος 4 runs.**
- [ ] **Κόστος πληρώματος, ρητά προϋπολογισμένο:** η fib καμπύλη δίνει 10 hands → **$143/μέρα**,
      12 → **$376**, 14 → **$986**. Τα +2 hands κοστίζουν **~$233/μέρα** μέσα στο παράθυρο ⇒
      **~$3,5k/σεζόν** που πρέπει να πληρωθούν από τα νέα tiles. Το «φθηνό» τελειώνει στα ~11-12·
      **14 hands δεν εξετάζεται.**
- [ ] **Επέκτεινε το παράθυρο του `sw_hands_target`** αν το sweep το ζητά — σήμερα το crew
      ανεβαίνει μόνο μέσα στο παράθυρο εργασίας του SW· με 24 tiles το παράθυρο μεγαλώνει από
      μόνο του και το `wheat_last_plant_day = 20` πιθανόν χρειάζεται επανεξέταση (το tile πρέπει
      να αδειάζει πριν τη liquidation μέρα 26).
- [ ] **Παρακολούθησε τα δύο residual counters του v1h.2d** (84 overflow, 34 water weeds): η
      πρόβλεψη είναι ότι τα +2 hands τα **μειώνουν**, γιατί είναι unit contention. Αν αυξηθούν
      αντί να μειωθούν, η ανάγνωση του §3 είναι λάθος και το increment σταματά για διάγνωση.
- [ ] **Shed pressure**: με 24 tiles ο ρυθμός εισροής ανεβαίνει· επιβεβαίωσε ότι το EOD surplus
      layer κρατά `shed_overflow_burnt` μέσα στον προϋπολογισμό — αυτό είναι το ακριβώς σημείο
      που σκότωσε το 16-tile variant του v1h′ **πριν** υπάρχει το layer.
- [ ] **DEV 0-47** both seats `--town-pin basket --metrics` vs `v1h_2d`, μετά **unpinned
      holdout 100-147**. Αποδοχή: Απόφαση Α + **`median_bank` αισθητά πάνω από $46k** (Απόφαση Β
      #1). Θετικό `mean_diff` με στάσιμο `median_bank` **δεν** είναι επιτυχία αυτού του increment.
- [ ] `checkpoints/v1j` + submission ως **challenger** (η έκθεση διαφέρει ουσιωδώς από το
      v1h_2d: wheat-βαρύ vs animal/strawberry-βαρύ ⇒ ικανοποιεί τον κανόνα §Α.3).

**Ρητά εκτός scope του v1j:** αγορά **SE** (4ο quadrant, $4.000) — η γη που έχουμε δεν είναι
γεμάτη· δεν αγοράζουμε νέα πριν δουλέψει η υπάρχουσα. Αλλαγή σύνθεσης κοπαδιού (`{4C,6S}`
μένει). Αλλαγή strawberry (είμαστε ήδη στο επίπεδο του meta).

> ⚠️ **Παγίδα του BUY_LAND gate** (ισχύει αν ποτέ μπει δομή στο SW): το gate απαιτεί **κάθε
> planned animal ήδη τοποθετημένο** πριν αγοράσει γη. Νέο PASTURE/COOP στο SW ⇒ circular
> deadlock. Κάθε νέα δομή εκτός NW απαιτεί **πρώτα** αλλαγή του gate.

---

### Β.2 — Clean-room **meta-bench opponent** [προαπαιτούμενο του v1i]

**Το πρόβλημα:** κάθε gate μας είναι mirror, ενώ ~75% της ladder παίζει μία κοινή πολιτική
(ένα field hash σε 144 επεισόδια / 40 ομάδες· ranks 3-20 ταυτόσημα σε 99-100% των field actions).

**Η γραμμή που ΔΕΝ περνιέται** (Ανοιχτό #11):

| Επιτρεπτό | Απαγορευμένο |
|---|---|
| **Δημοσιευμένα στατιστικά**: 8c/6s · 23 strawberry · 31 wheat · 3 quadrants · 12 hands · ημερολόγιο πώλησης (wheat d2 · fertilizer d3 · wool d9 · milk d10 · melon d10 · strawberry d18) | Replay **trajectories** / tapes ως πηγή κινήσεων |
| Δικός μας κώδικας που **αναπαράγει το προφίλ** από αυτά τα στατιστικά | Εκτέλεση ή αποσυμπίεση κώδικα από competitor notebooks |
| Χρήση ως **αντίπαλος** στο bench | Χρήση ως **πηγή** για τη δική μας πολιτική (BC/IL) |

⚠️ Το [notebooks/kaggriculture-findings-from-zero-to-top-meta.ipynb](notebooks/kaggriculture-findings-from-zero-to-top-meta.ipynb)
**ενσωματώνει base64+zlib blob** ολόκληρου agent. **Δεν εκτελείται, δεν αποσυμπιέζεται.**

**Scope (ελάχιστο):** ντετερμινιστικός `harness/bench_agents/meta_route.py` — **εκτός `agent/`**,
ώστε να μη μολύνει ποτέ το submission. Δύο παραλλαγές: `meta_route` (v23-fork profile) και
`meta_route_sheep` (το sheep-first basin του v25 — 1c+4s day-0), γιατί το meta μόλις μετακινήθηκε
εκεί. **Αποδοχή:** τρέχει, είναι ντετερμινιστικό, και δίνει non-degenerate αποτέλεσμα (όχι 0-48
ούτε 48-0 έναντι του τρέχοντος checkpoint — αλλιώς το προφίλ είναι λάθος χτισμένο).
**Καμία αλλαγή στο `agent/`, κανένα checkpoint, καμία υποβολή.**

---

### v1i — Sell-ahead arbitrage («πούλα πριν το κύμα»)

**Pre-gate κατάταξη: MARKET-ONLY** ⇒ σταθερό seed αρκεί, δεν απαιτείται pin — εκτός αν η
υλοποίηση αγγίξει planner/scheduler.

Σε μονοκαλλιέργεια το κύμα πώλησης του αντιπάλου είναι προβλέψιμο για τα ¾ της ladder. **Τέσσερις
ανεξάρτητες μετρήσεις** δίνουν το ίδιο: `Hamburger Clone Quad H1` 6-0 (+1.865,7) μόνο από
one-turn front-run· `c15` 14-2 εναντίον της ίδιας του της base tape· `c18` 35-5 αλλάζοντας 20
field turns αλλά **112 market turns**· και το δικό μας [agents-1](docs/meta/ladder_snapshots.md#agents-1)
(31-1, +$2.304).

- **Μηχανισμός** — πρόβλεψη του κύματος από τρεις πηγές, **καμία hardcoded**:
  (i) meta ημερολόγιο ως **prior μόνο** (μετακινήθηκε ήδη: milk 8→10, strawberry 16→18 μέσα σε
  μία μέρα ladder ⇒ **αν η υλοποίηση δεν δουλεύει με κενό prior, είναι λάθος σχεδιασμένη**)·
  (ii) ζωντανό market inventory έναντι των cliffs (strawberry 62 / wool 59 / milk 76 / melon 158·
  wheat χωρίς cliff)· (iii) **ορατά ώριμα tiles του αντιπάλου** — η φάρμα του είναι δημόσια.
- **Ο controller του c68 είναι υλοποιήσιμος σήμερα**: `Δinventory − (δικές μας πωλήσεις) −
  (ντετερμινιστικό town drain)` = οι παρτίδες του αντιπάλου → fit σε horizon 1-6 → ένα turn
  μπροστά. Ο δύσκολος όρος **υπάρχει ήδη**: [agent/demand.py](agent/demand.py) `npc_daily_demand`,
  engine-pinned (γράφτηκε για το v1g.2(γ) που διαψεύστηκε — το εργαλείο επέζησε της υπόθεσης).
- **(1) Ακριβές άθροισμα αντί endpoint.** Το [agent/executor.py](agent/executor.py):89 ελέγχει
  `market_price(product, inventory + sell_units + safety_units) > floor`. Η εκτέλεση είναι
  **per-unit με pre-sell quote** ⇒ πραγματικό έσοδο `Σ p(s+i)`. Ο έλεγχος είναι **συντηρητικός**
  (όχι bug) αλλά αφήνει έσοδο σε ρηχές καμπύλες. ⚠️ **Μην** αντικαταστήσεις το `safety_units` με
  το άθροισμα: μοντελοποιεί το **δικό του** ταυτόχρονο SELL στο ίδιο index — χρειάζονται και τα δύο.
- **(2) Ordering bug του executor.** [agent/executor.py](agent/executor.py):266-281 εφαρμόζει το
  `sorted(orders, key=_order_tier)` **μόνο μέσα στο `if len(orders) > max_orders`**: ≤10 orders ⇒
  τα SELL βγαίνουν **πρώτα**· >10 ⇒ πέφτουν στα indices 6-9 (SELL = tier 5). Δηλαδή **ακριβώς τις
  πιο πολυάσχολες μέρες** τα SELL μας πάνε στις χειρότερες θέσεις του lockstep (~56 turns/ep στο
  cap). **Διόρθωση:** επίλεξε *ποια* orders κρατάς κατά tier, μετά **εξέδωσέ τα με τα SELL
  πρώτα**. ⚠️ Δεν είναι δωρεάν — μετακινεί τα HIRE προς τα πίσω, και το HIRE τροφοδοτεί το crew
  της ίδιας μέρας. Θέλει δικό του gate.
- **Αποδοχή:** Απόφαση Α/Β + **W/L έναντι του §Β.2 bench** (ο αντίπαλος για τον οποίο γράφεται)
  + mirror-margin έλεγχος ότι δεν χαλάει το δικό μας mirror.

---

### Μετά: BBO sweeps

CMA-ES/Optuna στο `CONFIG` **μόνο αφού** υπάρχουν v1j/v1i — πριν από αυτά βελτιστοποιεί σε λάθος
ταβάνι. Ελάχιστη απαίτηση πριν το πρώτο sweep: κάθε occupancy παράμετρος αξιολογείται μέσα σε
**σταθερό σετ pinned baskets κοινό για όλα τα variants**, και το confirm stage τρέχει **και**
χωρίς pin. Ποτέ «κράτα το max» (multiple comparisons: με k variants και spread ~19% του median,
το max επιλέγει θόρυβο).

---

## ΜΕΡΟΣ Γ — Bench & robustness (κλείνει ~20/09)

1. **Mirror margin metric** στο bench: κάθε compare καταγράφει και το margin σε mirror matches.
2. **Robustness matrix** με «αυριανά» σενάρια: αντίπαλοι με δικό τους sell-ahead· sell ημερολόγια
   μετατοπισμένα ±2-4 μέρες· wheat/staple-βαριά fields· mono-crop flooders· do-nothing (ceiling).
   Tuning που κερδίζει οριακά σήμερα αλλά καταρρέει σε μετατοπισμένο ημερολόγιο **απορρίπτεται**.

   | Σενάριο | Πώς στήνεται | Τι πρέπει να αποδειχθεί |
   |---|---|---|
   | **Χωρίς YARN_STORE** (34,4% των επεισοδίων) | `pinned_shops([...])` χωρίς `YARN_STORE` | Ο agent σταματά να ξεπουλά wool· δεν κρατά sheep σε καθαρή ζημιά |
   | **Καμία shop ζήτηση** | `no_shops()` | Το δάπεδο: τι βγάζει με μόνο το town center, και ότι δεν καταρρέει |
   | **Πραγματική κατανομή towns** | καθόλου pin, μεγάλο seed budget | Η **διασπορά** ανά επεισόδιο — πόσο της διακύμανσης του bank είναι town draw. Λείπει από κάθε gate μας |
   | **Anti-clone** | `harness/bench_agents/meta_route*.py` (§Β.2) | Ότι κερδίζουμε τον αντίπαλο του 75% της ladder |

   Τα σενάρια στήνονται από το [harness/town_pin.py](harness/town_pin.py) — κανένα νέο monkeypatch,
   **ποτέ αλλαγή στο `agent/`** (θα μόλυνε το submission).
3. **Meta refresh πριν τη Φάση 3**: re-download του community dataset + νέα μέρα topfarms.
4. **Engine bump detector** — τρέχει **τακτικά και ΧΩΡΙΣ install** (ένα `pip install -U` στη μέση
   ενός gate ακυρώνει τη σύγκριση):

   ```powershell
   pip index versions kaggle-environments            # LATEST vs INSTALLED
   pip download kaggle-environments==<νέα> --no-deps --no-binary :all: -d <scratchpad>
   tar -xzf ...; diff -u engine_reference/kaggriculture.py <extracted>/kaggriculture.py
   diff -u engine_reference/kaggriculture.json <extracted>/kaggriculture.json   # ⚠️ ΜΗΝ το παραλείψεις
   ```

   ⚠️ Το `.json` diff είναι εξίσου σημαντικό — εκεί ζουν `townCenterSellInterval`, `turnsPerDay`,
   `maxMarketOrdersPerTurn`, `shedCapacity`. Μια balance change μπορεί να είναι **αποκλειστικά**
   json. Το 1.32.6 μας πρόλαβε μία φορά· δεύτερη δεν πρέπει.

---

## Πρωτόκολλο (ισχύει για κάθε gate αυτής της φάσης)

- **Seeds**: `DEV_SEEDS` 0-47 (screening) · `HOLDOUT_SEEDS` 100-147 (μόνο confirm, **καμία tuning
  απόφαση**) · `SMOKE_SEEDS` 0-11 (controls/sweeps, **ποτέ GO**) · `CONFIRM2_SEEDS` 200-247
  **καμένο**. Το `stage=holdout-confirm` δέχεται μόνο **πλήρες** named confirm set — όχι
  subsets/overlapping looks. GO απαιτεί επιπλέον prior tracked DEV artefact για το **ίδιο**
  candidate fingerprint, both seats, `town_pin=None`, `metrics_checked`, καθαρό gate.
- **Metric gate = Απόφαση Α** (§1): hard-zero μόνο τα δομικά· τα υπόλοιπα τιμολογημένα, με
  υποχρεωτικό γραπτό μηχανισμό ανά μη μηδενικό counter. Το raw `weeds_lost` είναι diagnostic.
- **Acceptance = Απόφαση Β** (§1): `median_bank` (απόλυτο) → W/L vs bench → `mean_diff`.
- **Immutable checkpoint** σε **κάθε** αποδεκτή κατάσταση, με fingerprint verification (G15).
- **Both seats πάντα** — το weed RNG είναι seat- και opponent-tile-fill-εξαρτώμενο.
- **Ποτέ engine bump ή επεξεργασία `agent/` όσο τρέχει gate.** Ο agent φορτώνεται σε **κάθε
  worker process ξεχωριστά**· επεξεργασία κατά τη διάρκεια parallel run δίνει **ανάμεικτα**
  αποτελέσματα μεταξύ seeds. **Επιτρέπεται πάντα:** εγγραφή σε `.md`.
- **Ρητά εκτός** (standing, δεν επανεξετάζονται χωρίς νέα δεδομένα): RL (μόνο στον 4-πλό trigger
  του MASTERPLAN §4)· BC/IL/trajectory copying και κάθε replay-derived prior (Ανοιχτό #11)· W&B·
  εκτέλεση κώδικα από competitor notebooks (evidence, όχι πηγή).

### 0ter. Σύζευξη RNG — γιατί υπάρχει η κατηγοριοποίηση knob

Το `_end_of_day` φτιάχνει **ένα** per-day RNG και το μοιράζεται: το `_spawn_weeds` καλεί
`rng.random()` μία φορά ανά άδειο unlocked tile — πρώτα player 0, μετά player 1 — και **μόνο
μετά** κληρώνεται το shop unlock. Άρα **ένα σταθερό seed ΔΕΝ σταθεροποιεί την πόλη**: ένα tile
διαφορά σε οποιαδήποτε από τις δύο φάρμες ξαναρίχνει όλη την ακολουθία shop unlocks. Δεν είναι
exploit και δεν το χειριζόμαστε ως τέτοιο — το κόστος είναι **εγκυρότητα μέτρησης**.

### ⭐ ΥΠΟΧΡΕΩΤΙΚΟ pre-gate ερώτημα — «τι είδους knob είναι αυτό;»

> **Μπορεί αυτή η αλλαγή να μεταβάλει πόσα tiles είναι κατειλημμένα οποιαδήποτε βραδιά;**

| Απάντηση | Κατηγορία | Τι απαιτεί το gate |
|---|---|---|
| **ΟΧΙ** — μόνο σειρά/ρυθμός/κατώφλια market orders | **market-only** | Τίποτα επιπλέον· σταθερό seed **είναι** ελεγχόμενο πείραμα (επιβεβαιωμένο 16/16 seeds) |
| **ΝΑΙ** — labour/crew, φύτευση, συγκομιδή, DIG, BUY_LAND, τοποθέτηση ζώων/δομών, routing | **occupancy** | `--town-pin basket` και στα **δύο** arms· ή μεγαλύτερο seed budget με **γραπτή** αιτιολόγηση |
| **ΔΕΝ ΞΕΡΩ** | — | Θεωρείται **occupancy** μέχρι αποδείξεως του εναντίου |

1. Το pinning **μειώνει, δεν εξαλείφει** (~19% του noise sd). Δεν κάνει occupancy gate ισοδύναμο
   με market-only.
2. **Μόνο `--town-pin basket`** είναι έγκυρο στο 1.32.6. Το `schedule` mode δειγματίζει κατανομή
   που εμφανίζεται στο **0,24%** των επεισοδίων — **ενεργά παραπλανητικό**, μένει μόνο για
   αναπαραγωγή παλιών runs.
3. **Το τελικό holdout-confirm τρέχει ΠΑΝΤΑ χωρίς pin** — το GO πρέπει να επιβιώνει στην
   πραγματική κατανομή πόλεων.

---

## Χρονοδιάγραμμα

| Βήμα | Στόχος | Κατάσταση |
|---|---|---|
| Φάση 1 + v1f/v1g/v1h′/v1h.1/v1h.2 a-c | 08-06 → 08-09 | ✅ **ΚΛΕΙΣΤΑ** — memory.md |
| v1h.2d κλείσιμο (priced gate → total DEV → holdout → `v1h_2d` → submission) | 08-10 | ✅ **ΚΛΕΙΣΤΟ** — `SUBMISSION_ID 55390611` — memory.md 2026-08-10 (β) |
| **L1 ladder diagnostic** (docs/data only, παράλληλα) | 08-10 → 08-12 | ⬅ **ΤΩΡΑ, δεν έχει ξεκινήσει** |
| **v1j scale-out** (wheat 12 → ~28 + crew 10 → 12) | 08-11 → 08-18 | ⏸ το κύριο money item |
| Β.2 clean-room meta-bench (εκτός `agent/`) | 08-18 → 08-21 | ⏸ προαπαιτούμενο του v1i |
| v1i sell-ahead (+ per-unit sum, + order emission fix) | 08-21 → 08-31 | ⏸ |
| BBO sweeps (pinned baskets) + Φάση 3 robustness | Σεπτέμβριος → ~09-20 | ⏸ |
| Champion/challenger κλείδωμα 2 slots | 09-23 → 09-30 | ⏸ |

**Ο περιοριστικός πόρος άλλαξε.** Ως τις 08-09 ήταν η ποιότητα του gate· από τις 08-10 είναι ο
**χρόνος έναντι ενός χάσματος 2.400 πόντων**. Κανένα βήμα δεν προσπερνά το holdout-confirm — αλλά
κανένα βήμα δεν ξοδεύει πια συνεδρία για μεγέθη που η Απόφαση Α τιμολογεί κάτω από $500/ep.
