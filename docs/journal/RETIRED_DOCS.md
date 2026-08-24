# Retired documents — a redirect for old citations

Code comments and older notes across this repo cite planning documents that have since been
**consolidated into a single roadmap** or were **per-pass working files**. None of them are lost —
each doc's full text is in git history. This page says what each one was and where its content lives
now, so a `plan.md §…` or `current_phase.md §…` breadcrumb in a comment stays resolvable.

| Cited as | What it was | Retired | Where its content is now |
|---|---|---|---|
| `plan.md` | The original strategy + measurement-protocol doc | 2026-08-06 | Folded into `MASTERPLAN.md`/`current_phase.md`, then into [`ROADMAP.md`](../../ROADMAP.md) (§2 measurement protocol, §3 protocol/standing rules). Full text in git history. |
| `docs/MASTERPLAN.md` | Consolidated strategy doc | 2026-08-11 | [`ROADMAP.md`](../../ROADMAP.md). Full text in git history. |
| `current_phase.md` | The active-phase working doc (per-version `§v1x` notes) | 2026-08-11 | [`ROADMAP.md`](../../ROADMAP.md) + the per-session narrative in [`memory.md`](memory.md). The `§v1x` engine/behaviour findings it recorded are also inline in the `agent/` code comments that cite it. Full text in git history. |
| `prompt.md` | A **rolling** per-pass brief (overwritten each shipping pass) | 2026-08-24 | Each pass's outcome is recorded in [`memory.md`](memory.md) and the shipped logic is in `agent/` + `analysis/build_*_submission.py`. Because it was overwritten every pass, a `prompt.md §X` citation refers to whatever it held **at that commit** — read it via `git log -p` on that path. |
| `review.md`, `review_<hash>_<date>.md` | AI code-review dumps | ongoing | Kept locally under `docs/reviews/` (gitignored as raw working notes). The findings that mattered were applied to the code and are described in the comments that cite them. |

## Section-number caveat

The **2026-08-20 ROADMAP restructure** renumbered sections. Citations written before that date use the
old numbers: the old **§3.3 STOP register is now §6**, **§2.1.4 → §3.1(4)**, **§4.5 → §5.3**, and
**§4.3's stage sections → §7**. When an older comment or memory entry cites a `ROADMAP §…`, apply that
map.

*(This tombstone exists so that consolidating the planning docs did not silently break the ~480
provenance breadcrumbs that cite them. The breadcrumbs are kept on purpose — they record why a given
line of code exists — and this page is what makes them resolvable.)*
