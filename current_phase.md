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
| Median bank | ~$42,6k (vs starter) | **$125,3k** | — (αποτέλεσμα των παρακάτω) |
| Hands | `hands_target: 3` | **12** (hires = ισχυρότερο correlate, +0,76 — [daily-13](docs/meta/ladder_snapshots.md#daily-13)) | **v1f** |
| Ζώα | 3 (1 COW + 1 SHEEP + 1 GOOSE) | **13** (8 cow + 5 sheep· goose μόλις 15% adoption) | **v1g** |
| Quadrants | 2 (NW+NE) | **3 (NE+NW+SW)· SE ποτέ** (#3 → median μέρα 11) | **v1h** |
| Crops | 10 carrot + 31 strawberry | 6 strawberry + 1 wheat (+13 ζώα) | v1g/v1h rebalance, **μετρημένο** |
| Sell timing | στατικά sell floors ανά προϊόν | πωλήσεις σε ημερολόγιο πάνω σε γνωστά cliffs | **v1i** (άξονας β) |

Δύο προειδοποιήσεις πριν αντιγράψουμε αριθμούς:
1. Το modal farm είναι η **καλύτερη εκτίμηση του engine optimum υπό ανταγωνισμό**, όχι συνταγή
   (MASTERPLAN §3.4 άξονας α). Το δικό μας strawberry-βαρύ mix έχει το υψηλότερο win rate ως
   πρωτεύον crop στο full ladder (70%, n=441 — §3.2bis)· η σύγκλιση αφορά πρωτίστως **μάζα ζώων
   + crew**, όχι απαραίτητα την εγκατάλειψη του strawberry. Κάθε rebalance περνά gate.
2. Τα wheat-primary record games ([daily-11](docs/meta/ladder_snapshots.md#daily-11)) είναι
   single-game ενδείξεις — δεν αλλάζουν το mix χωρίς δεύτερη μέτρηση.

---

## ΜΕΡΟΣ Α — Πρώτο submission (εκτελείται ΤΩΡΑ, πριν από κάθε νέο feature)

Το v1e πληροί τα κριτήρια Φάσης 1 (96/96 vs starter, median ≥$40k). Κάθε μέρα χωρίς submission
είναι χαμένη πληροφορία ladder. Διαδικασία (από το παλιό plan §6, αμετάβλητη):

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

### v1h — 3ο quadrant (SW) + rebalance χαρτοφυλακίου

- **Trigger όπως το NE**: reserve-based (`land.min_reserve`), όχι hardcoded μέρα — η ελίτ
  αγοράζει το #3 γύρω στη μέρα 11, αλλά το δικό μας self-regulating trigger (χρήματα + διαθέσιμο
  workforce) απέδωσε ήδη στο v1c. SW = $2k. **SE ($4k): ΔΕΝ αγοράζεται** — κανείς στην ελίτ
  δεν το κάνει (topfarms-19)· μόνο με μετρημένο λόγο.
- **Χρήση SW**: επέκταση pasture/strawberry με βάση ό,τι κέρδισε στο v1g screen — όχι
  αυτόματο mirror των NW counts (το v1c δίδαγμα: ο 1:1 mirror του carrot έσκασε στην
  κοινή αγορά· `ne_carrot_tiles: 3`, όχι 7).
- **Αποδοχή**: metric gate → $-gate vs `v1g` → checkpoint `v1h`. Μετά το v1h, ξανατρέχει το
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
3. **Meta refresh πριν τη Φάση 3**: re-download του community dataset (υποχρεωτικό —
   MASTERPLAN §3.2bis freshness note) + νέα μέρα topfarms για το consensus anomaly και τη
   wheat-primary επιβεβαίωση.
4. **Engine bump detector**: σε κάθε νέο `kaggle-environments` στη ladder →
   `pip install -U` + `pytest tests/` — ό,τι κοκκινίσει είναι η αλλαγή συμπεριφοράς.
   Το 1.32.4 μένει pinned μέχρι να περάσει το suite στη νέα έκδοση.

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

| Βήμα | Στόχος |
|---|---|
| Α. Submission v1e + baselines | **08-07/08** |
| v1f crew | 08-08 → 08-11 |
| v1g ζώα | 08-11 → 08-17 |
| v1h SW + rebalance (+2ο submission αν IMPROVED) | 08-17 → 08-21 |
| v1i sell-ahead | 08-21 → 08-31 |
| BBO sweeps + Φάση 3 robustness | Σεπτέμβριος → ~09-20 |
| Champion/challenger κλείδωμα 2 slots | 09-23 → 09-30 |

Ο χρόνος δεν είναι ο περιοριστικός πόρος — η ποιότητα του gate είναι. Κανένα βήμα δεν
προσπερνά το confirm για να «προλάβει» την ημερομηνία του πίνακα.
