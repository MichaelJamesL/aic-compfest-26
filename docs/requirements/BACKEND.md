# Backend — requirements & status

Scope: `backend/`. Owner: backend engineer. Read [`../API.md`](../API.md) for
the wire contract and [`../DEFECTS.md`](../DEFECTS.md) before editing
`app/main.py` — it currently contains duplicated routes and a shadowed state
machine.

## Verify

```bash
cd backend
uv run --no-project --python 3.11 \
  --with 'fastapi>=0.115' --with 'sqlalchemy>=2.0' --with 'pydantic-settings>=2.5' \
  --with python-multipart --with pytest --with httpx pytest -q
```

Last full run: `14 passed`. **Python 3.11+ is required** — the models use
`str | None` at class scope, which is a `TypeError` on 3.9. If pytest collection
fails with `unsupported operand type(s) for |`, you are on the wrong interpreter.

Tick a box only under the rule in [`../INDEX.md`](../INDEX.md#checklist-rules).

---

## 1. Foundation

- [x] FastAPI app, synchronous throughout, no background work — verified: `pytest -q`
- [x] SQLAlchemy 2 models with `factory_id` scoping on every table — verified: `test_starter_flow`
- [x] SQLite for dev/test, `DATABASE_URL` swappable to Postgres — verified: tests run on `sqlite://` in-memory via `StaticPool`
- [x] Demo identity from `X-Demo-User` / `X-Factory-ID`, with `factory_id` format validation — verified: `test_starter_flow` (defaults path)
- [x] Single error envelope `{code, message, details, request_id}` for 404 / 409 / 422 — verified: probed live; shapes recorded in `../API.md`
- [x] `X-Request-ID` accepted, generated when absent, echoed on the response — verified: probed live (`X-Request-ID: probe-123` round-trips; a request without one gets a generated uuid)
- [ ] Audit events written for asset creation, analysis completion, and work-order transitions — **unasserted**: `test_starter_flow` walks the code paths but never reads the `audit_events` table, so a silently dropped write would pass. Assert the rows.
- [ ] Path-traversal guard on upload storage keys (`_factory_storage_key`) — **untested**: the function looks correct, but no test feeds it a hostile `factory_id`. A security control with no test is not a control. (A hostile header is rejected earlier by `auth`, verified below — but the guard itself is still uncovered.)
- [x] Offline `StubEngine` so the app runs with no API key — verified: `test_offline_engine_contract_shape`
- [x] `factory_id` isolation across tenants — verified: probed live; factory B reading factory A's asset gets 404, and a malformed `X-Factory-ID` (`../etc`) gets 400. Needs a committed test, listed below.
- [ ] Stub health score that is not nonsense — **broken**: `../DEFECTS.md#stub-health-inverted`. It is the default engine and the fallback on camera.
- [x] `main.py` reduced to routing; one state machine in `services.py` — verified: the duplicate `transition`/`TRANSITIONS` and the dead second `documents` route are gone; `test_illegal_transitions_are_refused_with_the_pair_named` now exercises the live table
- [x] Role enforcement actually applied — verified: `require_role` gates approve and reject; `test_approval_is_the_coordinators_alone` asserts 403 for engineer and technician, 200 for manager

## 2. Knowledge setup — FR *Knowledge setup*

- [x] Document upload with extension allow-list, 10 MB cap, original file retained, metadata row created — verified: `test_import_and_document`
- [x] Asset list import from CSV/JSON, idempotent on `external_id`, per-row error reporting — verified: `test_import_and_document`
- [x] Maintenance-history record endpoint — verified: probed live (`POST …/maintenance-records` → `{"id"}`)
- [ ] Documents actually ingested into pgvector — **partial**: the swallowed `NameError` is fixed and the endpoint now reports honestly (missing text, ai-engine absent, or the real ingest error) instead of always saying `failed`. **Untested against a live pgvector** — needs `AI_ENGINE_ENABLED=true` and a running database.
- [ ] PDF text extraction — `.pdf` is accepted but `extracted_text` is only filled for text-like types, so a PDF SOP ingests as an empty document.
- [ ] Maintenance history CSV/Excel import (bulk) — only single-record POST exists. FR says upload.
- [ ] QC standard / product specification upload — no distinct `kind`; treat as a document kind and make it retrievable.

## 3. Operational input — FR *Operational input*

- [x] Single sensor reading, idempotent on `external_id` — verified: probed live; a repeat returns the existing row
- [x] Manual machine condition (`PUT …/condition`) — verified: `test_starter_flow`
- [x] Business context (schedule, spareparts, ETA, technicians, operator report) — verified: probed live. Note it is a **full replace**; document it in the UI layer.
- [ ] Sensor CSV batch ingest — not started. `ReadingBatchIn` is defined and unused; a CSV of a few hundred rows currently needs a request per row.
- [ ] QC image batch upload — **broken/missing**: `../DEFECTS.md#no-image-upload`. Blocks the differentiator end to end.
- [x] Maintenance progress input from the technician — verified: `test_progress_records_without_completing`. Recording progress no longer closes the work order, so completion still goes through verification.
- [ ] Technician *result* submission (work done, findings, parts used, evidence) as a distinct thing from progress — not started; it is the input to verification.

## 4. Analysis — FR *AI Analysis*

- [x] `POST …/analyses` runs synchronously, persists a request snapshot, result, health score, priority, engine mode, duration — verified: `test_starter_flow` + live probe
- [ ] Engine failures degrade to a stored `failed` run with an error code instead of a 500 — **untested**: `run_analysis` has the `except` branches, but nothing forces the engine to raise. This is the path the demo falls back to if DeepSeek is unreachable, so it deserves a test more than the happy path does.
- [x] `GET /analyses/{id}` returns the result plus the exact input snapshot — verified: probed live
- [x] Grounded Q&A passthrough (`POST …/ask`) — verified: probed live
- [ ] Real engine path exercised in CI or a test — `AI_ENGINE_ENABLED=true` is never tested; the only proof it works is `src.demo`, which bypasses the backend entirely.
- [ ] QC images passed into `AnalysisRequest.images` — blocked on §3
- [ ] Partial-input disclosure: the response states which inputs were absent and how that limits the decision — not started. This is FR *Partial-input analysis*, a Primary row, and the graceful-degradation demo beat. The data is already in `request_snapshot_json`; it needs to be summarised deliberately, not inferred by the UI.

## 5. Work orders & the autonomy boundary — FR *Coordinator approval*

The chain "AI proposes → coordinator approves → technician executes → AI
verifies" is the project's governance claim (`FINAL_IDEA.md` §5). It is
currently **broken at the first step**.

- [x] Draft work order generated from an analysis result, carrying steps/parts/skills/safety — verified: `test_starter_flow` + live probe
- [x] Work-order list — verified: probed live
- [x] Transitions are audited and irreversible past terminal states — verified: the lifecycle test walks all six states and asserts a completed order refuses `cancel`; rejection is terminal too
- [x] `approve` → `approved` and `reject` → `rejected` with a reason — verified: `test_full_work_order_lifecycle`, `test_rejection_records_its_reason`. `submit` is now the draft hand-off; `approve` is the coordinator's decision.
- [x] Work order becomes active only after approval, enforced server-side — verified: `schedule`/`start`/`complete` all 409 until `approved`, asserted in the lifecycle test
- [ ] Verification endpoint calling `engine.verify()` once, returning verdict + evidence — not started (needs the engine method too)
- [ ] Post-maintenance report — not started
- [ ] Completed work order written back to the knowledge base as history — not started; the loop-closing step of the demo chain
- [ ] CSV/JSON export of work order and report — not started (FR *Work order & report export*)

## 6. Integrations — FR *System & Integration*

- [x] Mock PLC / IoT / ERP adapters exist with a health endpoint — verified: probed live
- [ ] A route that actually ingests from `MockPLC.pull()` / `MockIoT` — not started. `adapters.MockPLC` is imported in `main.py` and never called, so two Primary FR rows are satisfied by a health check alone. One sync ingest endpoint each closes the gap honestly (live connections are explicitly out of scope, `DECISIONS.md` D5).
- [ ] `MockERP.push()` reachable — currently dead code; either wire it to export or delete it.

## 7. Deployment — FR *Docker deployment*

The rulebook requires a README plus a compose file the judges can run from a
clean clone. This is a hard requirement and it is not met.

- [x] `docker-compose.yml` starts Postgres + pgvector with a healthcheck — verified: `docker compose config` exits clean
- [ ] `backend` service in compose — not started; compose starts the database only
- [ ] `web` service in compose — blocked on the frontend existing
- [ ] `backend/Dockerfile` installs the ai-engine — it copies `ai-engine/` but only runs `pip install ./backend`, so `from src import MaintenanceEngine` fails inside the image
- [ ] Verified from a clean clone: `git clone && docker compose up` → working app — not started. Do this early, not on the last day.
- [x] `.env.example` covering both databases and `DEEPSEEK_API_KEY` — verified: the engine reads `AIENGINE_DATABASE_URL` and no longer picks up the backend's SQLite URL
- [ ] README paragraph quoting the MVP scope limits and stating compliance — not started (`DECISIONS.md` D4: free points, ten seconds of a judge's time)

## 8. Fixes queued from `../DEFECTS.md`

Blok 0 is done — eight entries deleted from `DEFECTS.md`, tests 5 → 14. What
remains, in order:

1. `#no-image-upload` — QC image intake. Unblocks the differentiator.
2. `#stub-health-inverted` — make the offline path defensible on camera.
3. Document ingestion verified against a live pgvector, not just the error paths.

## Test coverage gaps

The 5 passing tests cover a happy path only. Missing, in priority order:

- [x] Full work-order lifecycle through every legal transition — verified: `test_full_work_order_lifecycle`
- [x] Every illegal transition returns 409 with the right message — verified: `test_illegal_transitions_are_refused_with_the_pair_named`
- [x] `factory_id` isolation: factory A cannot read or mutate factory B's rows — verified: `test_factory_scoping_hides_other_tenants`
- [x] Upload rejections: oversized file and bad extension — verified: `test_upload_rejections`
- [ ] Analysis failure path: engine raises → run stored as `failed` with an error code, HTTP still 201
- [x] Error envelope shape asserted for 404 / 409 / 422 / 403 / 400 — verified: `test_error_envelope_shape`. FastAPI's own `HTTPException` is wrapped too, so a 403 never arrives as `{"detail": …}`.
