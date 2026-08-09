"""town_pin: πινάρισμα της σειράς/σύνθεσης των shop unlocks σε ένα episode.

**Κατάσταση (από 2026-08-08): ενεργό, opt-in.** Το [harness/compare.py](compare.py) το
εισάγει και το χρησιμοποιεί **μόνο** όταν του δοθεί ρητά `town_pin=...` (CLI: `--town-pin`)·
χωρίς αυτό το argument κανένα monkeypatch δεν εφαρμόζεται και κάθε ήδη-παραγμένο αποτέλεσμα
παραμένει αναπαραγώγιμο byte-for-byte. `agent/` **δεν** το εισάγει ποτέ (θα μόλυνε το
submission).

**Γιατί υπάρχει.** Το `_end_of_day` του engine φτιάχνει **ένα** per-day RNG
(`random.Random((seed * 1_000_003) ^ day)`) και το μοιράζεται μεταξύ (i) του weed spawning,
που καλεί `rng.random()` **μία φορά ανά άδειο (`None`) unlocked tile** — πρώτα για τον
player 0, μετά για τον player 1 — και (ii) της κλήρωσης του shop unlock, που τρέχει
**μετά**. Άρα η θέση στο stream όπου κληρώνεται το shop είναι

    (άδεια unlocked tiles player 0) + (άδεια unlocked tiles player 1)

εκείνο το βράδυ. Συνέπεια: ένα σταθερό `configuration["seed"]` **δεν** σταθεροποιεί ποιο
shop ξεκλειδώνει. Οποιαδήποτε αλλαγή στον αριθμό των κατειλημμένων tiles — labour/crew,
φύτευση, συγκομιδή, DIG, BUY_LAND, τοποθέτηση ζώων — σε **οποιαδήποτε** από τις δύο πλευρές
ξαναρίχνει όλη την επόμενη ακολουθία shop unlocks, ακόμα και του αντιπάλου.

Πλήρης τεκμηρίωση του μηχανισμού: `docs/MASTERPLAN.md` §2 Αμφισημία #7 (και #6 για το
weed σκέλος). Ο επιχειρησιακός κανόνας «occupancy knob vs market-only knob»:
`current_phase.md` §Πρωτόκολλο.

**Τι ΔΕΝ κάνει** (μην το πουλήσεις σε κανένα gate ως πλήρη λύση):
- **Δεν διορθώνει τα weeds.** Ο player 0 τραβά draws πριν τον player 1, οπότε αλλαγή στη
  δική σου occupancy μετατοπίζει ακόμα το weed stream του αντιπάλου.
- **Δεν εξαφανίζει γνήσια seed-dependent αλληλεπιδράσεις.** Το μεγαλύτερο μέρος του
  υπόλοιπου θορύβου σε ένα occupancy test είναι η αλλαγή να αλληλεπιδρά πραγματικά με τη
  σεζόν — αυτό είναι σήμα ανθεκτικότητας, όχι κάτι προς εξάλειψη.
- **Αλλάζει την κατανομή που δειγματίζεις.** Ένα pinned αποτέλεσμα λέει ποιο variant είναι
  καλύτερο **στις πόλεις που πίναρες**. Πίναρε σετ που καλύπτει το εύρος
  (`schedule_for`)· και **μετά** τη balance change πίναρε baskets με επανάθεση
  (`basket_for`), όχι permutations — αλλιώς βαθμονομείς για μια πόλη που εμφανίζεται
  ~1 στα 416 παιχνίδια.

Ο μηχανισμός (context manager γύρω από το `_end_of_day`) είναι προσαρμοσμένη αναδιατύπωση
της ιδέας του community notebook `notebooks/your-seed-does-not-fix-the-town.ipynb` §8 —
evidence, όχι πηγή κώδικα agent (MASTERPLAN Ανοιχτό #11).

Χρήση::

    from harness.town_pin import pinned_shops, schedule_for

    with pinned_shops(schedule_for(seed)):
        result = play([candidate, "starter"], seed=seed)
    # και τα δύο arms μιας σύγκρισης πρέπει να τρέξουν μέσα στο ΙΔΙΟ pin

    # ή, μέσα από το gate harness (και τα δύο arms πινάρονται αυτόματα ανά seed):
    #   python -m harness.cli compare A B --seed-set dev --town-pin basket
"""
import contextlib
import random

import kaggle_environments.envs.kaggriculture.kaggriculture as _K

__all__ = [
    "SHOP_TYPES", "PIN_MODES", "pinned_shops", "no_shops", "schedule_for", "basket_for",
    "schedule_for_mode", "pinned_town",
]

#: Τα modes που δέχεται το `compare(town_pin=...)` / `--town-pin`. Ονόματα, όχι callables:
#: ένα mode πρέπει να ταξιδεύει μέσα από `ProcessPoolExecutor` (Windows spawn ⇒ pickle) και
#: να καταγράφεται αυτούσιο στο `_meta` row του `results.jsonl` (G15 reproducibility).
PIN_MODES = ("schedule", "basket", "no_shops")

# Ταξινομημένα, ώστε η σειρά να μην εξαρτάται από dict iteration order (G13 determinism).
SHOP_TYPES = tuple(sorted(_K.SHOPS))


@contextlib.contextmanager
def _patched_end_of_day(make_patch):
    """Αντικαθιστά προσωρινά το `_end_of_day`, αποθηκεύοντας ό,τι ίσχυε **τη στιγμή της
    εισόδου** (όχι ένα module-level snapshot) — άρα τα context managers αυτού του module
    φωλιάζουν και ξετυλίγονται σωστά ακόμα και σε exception."""
    previous = _K._end_of_day
    _K._end_of_day = make_patch(previous)
    try:
        yield
    finally:
        _K._end_of_day = previous


def pinned_shops(schedule):
    """Επιβάλλει ότι το k-οστό shop unlock του episode θα είναι το ``schedule[k]``.

    Αλλάζει **μόνο την ταυτότητα** του shop που μόλις προστέθηκε. Τα weeds συνεχίζουν να
    κληρώνονται από το ίδιο stream, η μέρα ανανεώνεται κανονικά, και οι δύο agents παίζουν
    την ίδια πολιτική στο ίδιο seed. Unlocks πέρα από το μήκος του ``schedule`` μένουν
    όπως τα έβγαλε το engine.

    Args:
        schedule: ακολουθία ονομάτων shop (βλ. `SHOP_TYPES`). Επιτρέπονται επαναλήψεις
            μόνο αν το engine υποστηρίζει draw με επανάθεση (post-balance-change)· στο
            1.32.5 το engine κληρώνει χωρίς επανάθεση, οπότε ένα schedule με διπλότυπα
            παράγει πόλη που το σημερινό engine δεν θα έβγαζε ποτέ μόνο του.
    """
    schedule = list(schedule)

    def make_patch(original):
        def patched(state, env, day):
            town = state[0].observation.town
            before = len(town["unlocked_shops"])
            original(state, env, day)
            if len(town["unlocked_shops"]) > before and before < len(schedule):
                town["unlocked_shops"][-1] = schedule[before]

        return patched

    return _patched_end_of_day(make_patch)


def no_shops():
    """Δεν ξεκλειδώνει κανένα shop: το town center μένει η μόνη ζήτηση στο παιχνίδι.

    Χρήσιμο ως **δάπεδο** (πόσα βγάζει ο agent χωρίς καμία shop ζήτηση) και ως το πιο
    ακραίο σενάριο της §ΜΕΡΟΣ Γ robustness matrix.
    """

    def make_patch(original):
        def patched(state, env, day):
            town = state[0].observation.town
            before = len(town["unlocked_shops"])
            original(state, env, day)
            del town["unlocked_shops"][before:]

        return patched

    return _patched_end_of_day(make_patch)


def schedule_for(seed):
    """Ντετερμινιστική **μετάθεση** των 8 τύπων shop για ένα seed (σημερινό engine).

    Ξεχωριστό RNG από αυτό του engine — το seed εδώ επιλέγει *ποια πόλη πινάρεις*, δεν
    έχει καμία σχέση με το `configuration["seed"]` του episode.
    """
    rng = random.Random(seed)
    order = list(SHOP_TYPES)
    rng.shuffle(order)
    return order


def basket_for(seed, n_instances=8):
    """Ντετερμινιστικό **basket με επανάθεση** (μοντέλο μετά τη balance change).

    Μετά την ανακοινωμένη αλλαγή τα shops κληρώνονται με επανάθεση με cap
    `MAX_SHOP_INSTANCES = 8`, οπότε η σύνθεση —όχι μόνο η σειρά— μεταβάλλεται. Ένα gate
    που σχεδιάζεται για εκείνο το καθεστώς πρέπει να πινάρει baskets από **αυτήν** την
    κατανομή, όχι permutations.
    """
    rng = random.Random(seed)
    return [rng.choice(SHOP_TYPES) for _ in range(n_instances)]


def schedule_for_mode(mode, seed):
    """Ο πινακισμένος κατάλογος shops για ένα `(mode, seed)` — ή `None` για «χωρίς pin».

    Είναι **συνάρτηση του seed**, όχι σταθερά: αυτό είναι το κρίσιμο σημείο του §Β.0′. Ένα
    σταθερό schedule για όλα τα seeds δεν μειώνει τον θόρυβο, δειγματίζει **μία** πόλη n
    φορές — και το verdict που βγαίνει ισχύει μόνο για εκείνη τη μία πόλη.

    `"no_shops"` επιστρέφει κενή λίστα (δεν υπάρχει schedule να καταγραφεί) — το mode, όχι το
    schedule, είναι αυτό που επιλέγει τον context manager στο `pinned_town`.
    """
    if mode is None:
        return None
    if mode == "schedule":
        return schedule_for(seed)
    if mode == "basket":
        return basket_for(seed)
    if mode == "no_shops":
        return []
    raise ValueError(f"town_pin: unknown mode {mode!r} — expected one of {PIN_MODES} or None")


@contextlib.contextmanager
def pinned_town(mode, schedule):
    """Το `(mode, schedule)` ζεύγος ως ένας context manager, συμπεριλαμβανομένου του «κανένα
    pin» (`mode=None`) — ώστε ο καλών να μη χρειάζεται branch γύρω από το `with`.

    Ανοίγει **μέσα** στο worker process: ένα context manager δεν περνά μέσα από
    `ProcessPoolExecutor` (δεν είναι picklable, και ένα monkeypatch του parent δεν υπάρχει
    καν στο spawned worker) — ταξιδεύει το `(mode, schedule)`, όχι το CM.
    """
    if mode is None:
        yield
    elif mode == "no_shops":
        with no_shops():
            yield
    elif mode in PIN_MODES:
        with pinned_shops(schedule or []):
            yield
    else:
        raise ValueError(f"town_pin: unknown mode {mode!r} — expected one of {PIN_MODES} or None")
