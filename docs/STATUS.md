# Status

The scoreboard. Every Primary FR row from [`FR.md`](FR.md) against what the code
actually does today. Roll-up only — details live in the three checklists under
[`requirements/`](requirements/).

Last verified: 23 August 2026, by running the backend, AI, frontend, and Docker
checks for this slice. Browser pass and clean-clone deployment were not run.

```
ai-engine  uv run pytest -q                  → 22 passed, 2 skipped
backend    documented dependency command     → 54 passed
backend    AI-enabled TestModel integration  → 1 passed
frontend   npm run test && npm run build     → 121 passed (11 files), build clean
           browser pass                      → not run in this verification
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
| 1 | Document upload | backend | `done` | Upload, validation, storage, text-PDF extraction and tenant-scoped re-index are covered by backend tests. |
| 2 | Maintenance history upload | backend | `done` | Single-record POST plus tenant-scoped CSV/XLSX bulk import with row errors are tested. |
| 3 | Asset information upload | backend | `done` | CSV/JSON import, idempotent on `external_id` — `test_import_and_document` |
| 4 | QC standard / product spec upload | backend | `done` | `qc_standard` and `maintenance_history` document kinds are accepted consistently across contracts and upload/retrieval. |

### Operational input

| # | Requirement | Area | State | Evidence / gap |
| --- | --- | --- | --- | --- |
| 5 | Machine condition input | backend | `done` | Single reading, JSON batch, tenant-scoped CSV import and mock ingest are tested. |
| 6 | Business context input | backend | `probed` | Full replace semantics; documented in `API.md` |
| 7 | Product QC input | backend | `partial` | Scoped PNG/JPEG QC batch upload now works and is tested; classifier processing remains in the AI-engine track. |
| 8 | Maintenance progress input | backend | `done` | `test_progress_records_without_completing`; recording progress no longer closes the work order |

### AI analysis

| # | Requirement | Area | State | Evidence / gap |
| --- | --- | --- | --- | --- |
| 9 | Maintenance recommendation | ai-engine | `done` | `test_engine.py` with `TestModel`; end-to-end in `src.demo` |
| 10 | Root cause analysis | ai-engine | `done` | same |
| 11 | Constraint-based reasoning | ai-engine | `partial` | Business context reaches the prompt. Constraints are *narrated*, not *computed* — no `decide.py`. |
| 12 | Maintenance prioritization | ai-engine | `partial` | LLM assigns priority. The deterministic `priority_delta` from the mapping table does not exist. |
| 13 | Maintenance scheduling optimization | ai-engine | `none` | Free-text `recommended_window` from the LLM. The objective function (`FINAL_IDEA.md` §4) is unimplemented — no candidates, no feasibility filter, no runner-up. |
| 14 | Anomaly detection | ai-engine | `partial` | IQR fence is tested for clean, low-side, high-side and both-side outliers. Baselines are recomputed per call instead of fitted and frozen. |
| 15 | Machine health scoring | ai-engine | `done` | Five scoring and timestamp-normalization tests in `test_signals.py` |
| 16 | Product defect classification | ai-engine | `none` | **Compliance risk** — `DEFECTS.md#compliance-finetune`. Fine-tuned QC artifacts exist, but the classifier is not wired into analysis output. |
| 17 | Product quality analysis | ai-engine | `none` | Blocked on 16 |
| 18 | QC-based machine signal analysis | ai-engine | `none` | Blocked on 16 and 19. **This is the differentiator.** |
| 19 | Defect-to-failure-mode mapping | ai-engine | `none` | `mapping/qc_failure_modes.yaml` not written; contents are ready in `FINAL_IDEA.md` §7.2 |
| 20 | Sparepart requirement & availability check | ai-engine | `none` | Spareparts and ETA reach the prompt; nothing checks them or turns an ETA into a blocker |
| 21 | Technician assignment | ai-engine | `partial` | Work orders carry `required_skills` and the LLM may name a technician. No roster, so no real assignment. |
| 22 | Maintenance result verification | both | `done` | Typed synchronous verification and tenant-scoped result/verify routes; resolved-only completion. |
| 23 | Post maintenance analysis | both | `done` | Verification persists history, attempts synchronous knowledge ingest, exposes status and final report API. |
| 24 | Decision explanation & traceability | ai-engine | `partial` | `explanation` + `sources` exist and are engine-set (`done` at that level); live ingestion now supplies citations, but the losing alternative does not exist (13). |

### Output generation

| # | Requirement | Area | State | Evidence / gap |
| --- | --- | --- | --- | --- |
| 25 | Machine health summary | both | `done` | API `probed`; UI verified by `AnalysisResult.test.tsx` (donut, band, deduction breakdown) |
| 26 | Work order generation | both | `done` | `test_starter_flow`; draft renders and is asserted in the UI |
| 27 | Maintenance report | frontend | `done` | `Flow.test.tsx` asserts the rendered backend report payload |
| 28 | Maintenance execution status | both | `done` | Full lifecycle green in `test_full_work_order_lifecycle`; the UI renders the six-state track |
| 29 | Product quality report | both | `none` | Blocked on 7 and 16 |
| 30 | Post maintenance report | both | `done` | Tenant-scoped report API and frontend report are implemented and tested |
| 31 | Work order & report export | backend | `done` | Tenant-scoped JSON/CSV attachments call deterministic `MockERP.push()` and audit the format/result; content headers are tested. |

### System & integration

| # | Requirement | Area | State | Evidence / gap |
| --- | --- | --- | --- | --- |
| 32 | Coordinator approval | both | `done` | `submit` → `approve`/`reject`, role-gated to manager/admin, rejection carries a required reason. Asserted on both sides. |
| 33 | Partial-input analysis | both | `done` | Backend returns deterministic `input_disclosure` from the immutable `request_snapshot`; stable available/missing tokens and limitations are asserted by `test_analysis_disclosure_is_snapshot_derived_and_flags_are_respected`. |
| 34 | PLC / controller integration | backend | `done` | `/assets/{id}/ingest/plc` calls `MockPLC.pull()` and persists readings — `test_batch_readings_and_mock_ingest_are_idempotent` |
| 35 | IoT sensor integration | backend | `done` | `/assets/{id}/ingest/iot` calls the shared mock-ingest path — `test_batch_readings_and_mock_ingest_are_idempotent` |
| 36 | Docker deployment | backend | `partial` | Compose config and backend/web image builds pass; existing-volume smoke passes, but isolated clean-clone deployment is not claimed |

### Roll-up

| State | Count |
| --- | --- |
| `done` | 20 |
| `probed` | 2 |
| `partial` | 10 |
| `broken` | 0 |
| `none` | 8 |

Two readings of this table, both worth holding:

- **The differentiator now has an intake path.** QC classification and
  defect-to-failure-mode reasoning remain in the AI-engine track.
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

1. ~~Approve/reject routes~~ — **done.** FR 8, 28 and 32 are green and demo
   steps 10–13 are reachable.
2. ~~Document ingestion against a live pgvector~~ — **done for the approved slice.**
   Tenant-scoped upload → reindex → query and repeat reindex were smoke-tested;
   text PDFs are extracted and empty/image-only PDFs are reported honestly.
3. **`DEFECTS.md#compliance-finetune`** — wire the fine-tuned QC classifier into
   analysis output and regenerate its metrics. Highest-cost compliance gap,
   cannot be substituted.
4. **`mapping/qc_failure_modes.yaml` + corroboration** — turns the
   differentiator from a claim into a mechanism. The file's contents are already
   written in `FINAL_IDEA.md` §7.2.
6. **Frontend from zero** — seven screens. Runs in parallel with everything
   above against the shapes in `API.md`.
7. **`decide.py`** — the scheduling optimiser and the runner-up. This is what
   makes "optimal" a number instead of an adjective.
8. ~~`engine.verify()` + the verify route~~ — **done.** Result submission, synchronous verification, and report API are covered by backend tests.
9. **Compose + Dockerfile + a clean-clone run.** Do this *early*, not last: the
   rulebook requires the judges to run it, and it is the single cheapest way to
   fail.
10. Remaining one-line fixes.

Cut order if time runs short is fixed in `DECISIONS.md` — reduce classifier
classes, simplify `decide.py` to risk tiers, fewer seed machines, unstyled
frontend. Never cut: the fine-tuned model, a working `docker compose`, the
proof-of-work video, the proposal's methodology section.
