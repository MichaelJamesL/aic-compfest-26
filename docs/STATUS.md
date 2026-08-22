# Status

The scoreboard. Every Primary FR row from [`FR.md`](FR.md) against what the code
actually does today. Roll-up only — details live in the three checklists under
[`requirements/`](requirements/).

Last verified: 23 August 2026, by running both test suites and probing the API
live. Re-verify before trusting this file after any significant merge.

```
ai-engine  uv run pytest -q                 → 11 passed, 1 skipped
backend    pytest -q (python 3.11)          →  5 passed
frontend   —                                → does not exist
```

**States**

| | Meaning |
| --- | --- |
| `done` | Implemented and covered by a passing test in the repo |
| `probed` | Implemented and verified by hand against a running server; no committed test |
| `partial` | Some of it works; the gap is named |
| `broken` | Present but does not work — see `DEFECTS.md` |
| `none` | Not started |

---

## Scoreboard — 36 Primary requirements

### Knowledge setup

| # | Requirement | Area | State | Evidence / gap |
| --- | --- | --- | --- | --- |
| 1 | Document upload | backend | `partial` | Upload, validation and storage work (`test_import_and_document`). Ingestion into pgvector never succeeds — `DEFECTS.md#reindex-nameerror`. PDFs store empty text. |
| 2 | Maintenance history upload | backend | `partial` | Single-record POST is `probed`. No bulk CSV/Excel import, which is what "upload" means here. |
| 3 | Asset information upload | backend | `done` | CSV/JSON import, idempotent on `external_id` — `test_import_and_document` |
| 4 | QC standard / product spec upload | backend | `none` | No document `kind` for it, not retrievable |

### Operational input

| # | Requirement | Area | State | Evidence / gap |
| --- | --- | --- | --- | --- |
| 5 | Machine condition input | backend | `partial` | Single reading (`probed`, idempotent) and manual condition (`done`). No CSV batch ingest — `ReadingBatchIn` is defined and unused. |
| 6 | Business context input | backend | `probed` | Full replace semantics; documented in `API.md` |
| 7 | Product QC input | backend | `broken` | No image extension accepted, no QC endpoint — `DEFECTS.md#no-image-upload` |
| 8 | Maintenance progress input | backend | `broken` | `DEFECTS.md#progress-nameerror`, and unreachable behind `#wo-approve` |

### AI analysis

| # | Requirement | Area | State | Evidence / gap |
| --- | --- | --- | --- | --- |
| 9 | Maintenance recommendation | ai-engine | `done` | `test_engine.py` with `TestModel`; end-to-end in `src.demo` |
| 10 | Root cause analysis | ai-engine | `done` | same |
| 11 | Constraint-based reasoning | ai-engine | `partial` | Business context reaches the prompt. Constraints are *narrated*, not *computed* — no `decide.py`. |
| 12 | Maintenance prioritization | ai-engine | `partial` | LLM assigns priority. The deterministic `priority_delta` from the mapping table does not exist. |
| 13 | Maintenance scheduling optimization | ai-engine | `none` | Free-text `recommended_window` from the LLM. The objective function (`FINAL_IDEA.md` §4) is unimplemented — no candidates, no feasibility filter, no runner-up. |
| 14 | Anomaly detection | ai-engine | `partial` | IQR fence works and is tested; low-side outliers crash — `DEFECTS.md#signals-low-outlier-crash`. Baselines are recomputed per call instead of fitted and frozen. |
| 15 | Machine health scoring | ai-engine | `done` | Three tests in `test_signals.py` |
| 16 | Product defect classification | ai-engine | `none` | **Compliance risk** — `DEFECTS.md#compliance-finetune`. No fine-tuned model exists. |
| 17 | Product quality analysis | ai-engine | `none` | Blocked on 16 |
| 18 | QC-based machine signal analysis | ai-engine | `none` | Blocked on 16 and 19. **This is the differentiator.** |
| 19 | Defect-to-failure-mode mapping | ai-engine | `none` | `mapping/qc_failure_modes.yaml` not written; contents are ready in `FINAL_IDEA.md` §7.2 |
| 20 | Sparepart requirement & availability check | ai-engine | `none` | Spareparts and ETA reach the prompt; nothing checks them or turns an ETA into a blocker |
| 21 | Technician assignment | ai-engine | `partial` | Work orders carry `required_skills` and the LLM may name a technician. No roster, so no real assignment. |
| 22 | Maintenance result verification | both | `none` | No `engine.verify()`, no `POST …/verify`. Demo step 12. |
| 23 | Post maintenance analysis | both | `none` | Blocked on 22 |
| 24 | Decision explanation & traceability | ai-engine | `partial` | `explanation` + `sources` exist and are engine-set (`done` at that level), but `sources` is empty in practice because ingestion fails (1), and the losing alternative does not exist (13). |

### Output generation

| # | Requirement | Area | State | Evidence / gap |
| --- | --- | --- | --- | --- |
| 25 | Machine health summary | backend | `probed` | API returns it; **no UI** |
| 26 | Work order generation | backend | `done` | `test_starter_flow`; **no UI** |
| 27 | Maintenance report | frontend | `none` | Data exists, nothing renders it |
| 28 | Maintenance execution status | backend | `broken` | States past `pending_approval` are unreachable — `DEFECTS.md#wo-approve` |
| 29 | Product quality report | both | `none` | Blocked on 7 and 16 |
| 30 | Post maintenance report | both | `none` | Blocked on 22 |
| 31 | Work order & report export | backend | `none` | CSV/JSON export not implemented |

### System & integration

| # | Requirement | Area | State | Evidence / gap |
| --- | --- | --- | --- | --- |
| 32 | Coordinator approval | backend | `broken` | Nothing can reach `approved`; no reject route — `DEFECTS.md#wo-approve`. The governance headline is non-functional. |
| 33 | Partial-input analysis | both | `partial` | The engine genuinely reasons over whatever is present (that is the hard part, and it works). Nothing *states* which inputs were missing or what that cost — which is the requirement. |
| 34 | PLC / controller integration | backend | `partial` | `MockPLC` exists with a health endpoint; `pull()` is never called by any route |
| 35 | IoT sensor integration | backend | `partial` | Same |
| 36 | Docker deployment | backend | `partial` | Compose starts Postgres only; `Dockerfile` does not install the ai-engine; never run from a clean clone |

### Roll-up

| State | Count |
| --- | --- |
| `done` | 5 |
| `probed` | 2 |
| `partial` | 12 |
| `broken` | 4 |
| `none` | 13 |

Two readings of this table, both worth holding:

- **The four `broken` rows matter more than the thirteen `none` rows.** Rows 7,
  8, 28 and 32 are one chain — QC intake → approval → execution → status — and
  that chain is the entire second half of the demo. Unbuilt work is a schedule
  problem; a broken chain is a demo that cannot be recorded.
- **The `partial` rows are where the claims live.** Rows 11, 12, 13, 24 and 33
  are each implemented far enough to look finished in a code review and not far
  enough to support what the proposal says about them: constraints are narrated
  rather than computed, priority has no deterministic component, "optimal" has
  no arithmetic behind it, traceability cites an empty corpus, and partial-input
  analysis works but never says what was missing. These are the rows a technical
  judge will probe.

---

## What to do next

Ordered by what unblocks the most, not by what is easiest. Rationale for each is
in the linked checklist.

1. **`DEFECTS.md#wo-approve`** — approve/reject routes. One afternoon. Unblocks
   FR 8, 28, 32 and demo steps 10–13. Nothing else in the second half of the
   demo can be built or recorded until this works.
2. **`DEFECTS.md#reindex-nameerror`** — document ingestion. Every grounding and
   citation claim in the proposal currently has an empty corpus behind it.
3. **`DEFECTS.md#compliance-finetune`** — the QC classifier. The rulebook
   requires a fine-tuned model; there is none. Highest cost, hard deadline,
   cannot be substituted.
4. **`mapping/qc_failure_modes.yaml` + corroboration** — turns the
   differentiator from a claim into a mechanism. The file's contents are already
   written in `FINAL_IDEA.md` §7.2.
5. **`DEFECTS.md#no-image-upload`** — QC image intake, so 3 and 4 have a path
   through the product rather than a script.
6. **Frontend from zero** — seven screens. Runs in parallel with everything
   above against the shapes in `API.md`.
7. **`decide.py`** — the scheduling optimiser and the runner-up. This is what
   makes "optimal" a number instead of an adjective.
8. **`engine.verify()` + the verify route** — closes the loop.
9. **Compose + Dockerfile + a clean-clone run.** Do this *early*, not last: the
   rulebook requires the judges to run it, and it is the single cheapest way to
   fail.
10. **`DEFECTS.md#signals-low-outlier-crash`** and the remaining one-line fixes.

Cut order if time runs short is fixed in `DECISIONS.md` — reduce classifier
classes, simplify `decide.py` to risk tiers, fewer seed machines, unstyled
frontend. Never cut: the fine-tuned model, a working `docker compose`, the
proof-of-work video, the proposal's methodology section.
