# Backend — requirements & status

Scope: `backend/`. Owner: backend engineer. Read [`../API.md`](../API.md) for
the wire contract and [`../DEFECTS.md`](../DEFECTS.md) before editing
`app/main.py`.

## Verify

```bash
cd backend
uv run --no-project --python 3.11 \
  --with 'fastapi>=0.115' --with 'sqlalchemy>=2.0' --with 'pydantic-settings>=2.5' \
   --with python-multipart --with pillow --with pypdf --with openpyxl --with '../ai-engine' --with pytest --with httpx pytest -q
```

Last full run: `53 passed, 1 skipped` (Python 3.11+). **Python 3.11+ is required** — the models use
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
- [x] `X-Request-ID` accepted, generated when absent, bounded to 36 characters, and echoed on the response — verified: `test_request_id_is_preserved_when_valid_and_bounded_when_long`
- [x] Audit events written for asset creation, analysis success/failure, work-order transitions, result, and verification — verified: `test_audit_events_cover_creation_analysis_failure_and_work_order_evidence` asserts each action and its `request_id`.
- [x] Path-traversal guard on upload storage keys (`_factory_storage_key`) — verified: hostile factory IDs and resolved upload paths are rejected by `test_factory_storage_key_rejects_hostile_input` and `test_upload_storage_path_is_contained`.
- [x] Offline `StubEngine` so the app runs with no API key — verified: `test_offline_engine_contract_shape`
- [x] `factory_id` isolation across tenants — verified: `test_factory_scoping_hides_other_tenants`; factory B reading factory A's asset gets 404, and a malformed `X-Factory-ID` (`../etc`) gets 400.
- [x] Stub health score is deterministic and signal-based — verified: `test_clean_readings_are_not_penalized_by_count`, `test_stub_uses_anomaly_score_and_history_without_manual_deduction`, `test_stub_fallback_detects_outlier_without_ai_package`
- [x] `main.py` reduced to routing; one state machine in `services.py` — verified: the duplicate `transition`/`TRANSITIONS` and the dead second `documents` route are gone; `test_illegal_transitions_are_refused_with_the_pair_named` now exercises the live table
- [x] Role enforcement actually applied — verified: `require_role` gates approve and reject; `test_approval_is_the_coordinators_alone` asserts 403 for engineer and technician, 200 for manager

## 2. Knowledge setup — FR *Knowledge setup*

- [x] Document upload with extension allow-list, 10 MB cap, original file retained, metadata row created — verified: `test_import_and_document`
- [x] Asset list import from CSV/JSON, idempotent on `external_id`, per-row error reporting — verified: `test_import_and_document`
- [x] Maintenance-history record endpoint — verified: probed live (`POST …/maintenance-records` → `{"id"}`)
- [x] Documents actually ingested into pgvector — tenant-scoped, idempotent reindex is covered by mocked backend integration tests and a live upload → reindex → query smoke; valid empty PDFs honestly remain unindexable.
- [x] PDF text extraction — text PDFs use `pypdf`; malformed PDFs reject and valid empty PDFs remain honestly unindexable — `test_text_pdf_extraction`, `test_pdf_extraction_rejects_malformed_and_keeps_valid_empty_pdf_honest`.
- [x] Maintenance history CSV/Excel import (bulk) — tenant-scoped CSV/XLSX parser with row errors and optional external-id idempotency — `test_bulk_history_csv_and_xlsx_are_scoped_and_report_row_errors`, `test_bulk_history_external_id_is_idempotent_and_malformed_xlsx_is_enveloped`.
- [x] QC standard / product specification upload — `qc_standard` and `maintenance_history` document kinds are accepted by backend, engine contract and frontend types.

## 3. Operational input — FR *Operational input*

- [x] Single sensor reading, idempotent on `external_id` — verified: probed live; a repeat returns the existing row
- [x] Manual machine condition (`PUT …/condition`) — verified: `test_starter_flow`
- [x] Business context (schedule, spareparts, ETA, technicians, operator report) — verified: probed live. Note it is a **full replace**; document it in the UI layer.
- [x] Sensor CSV batch ingest — CSV route reuses `persist_reading` and is idempotent — `test_sensor_csv_reuses_idempotent_persistence_and_reports_bad_rows`.
- [x] QC image batch upload — verified: `test_qc_batch_validates_signatures_scopes_and_audits`, `test_qc_batch_rejects_image_count_and_aggregate_size`; magic-byte validation, limits, generated storage keys, tenant/asset scoping, and audit are covered.
- [x] Maintenance progress input from the technician — verified: `test_progress_records_without_completing`. Recording progress no longer closes the work order, so completion still goes through verification.
- [x] Technician *result* submission (work done, findings, parts used, evidence) as a distinct thing from progress — verified: result/verification lifecycle tests, including conflicting retries.

## 4. Analysis — FR *AI Analysis*

- [x] `POST …/analyses` runs synchronously, persists a request snapshot, result, health score, priority, engine mode, duration — verified: `test_starter_flow` + live probe
- [x] Engine failures degrade to a stored `failed` run with an error code instead of a 500 — verified: `test_analysis_failure_is_stored`.
- [x] `GET /analyses/{id}` returns the result plus the exact input snapshot — verified: probed live
- [x] Grounded Q&A passthrough (`POST …/ask`) — verified: probed live
- [x] Real engine path exercised in CI or a test — covered by the backend integration test with the actual `MaintenanceEngine` and pydantic_ai `TestModel` when AI dependencies are available; no network.
- [x] QC images passed into `AnalysisRequest.images` — verified: `test_analysis_wires_qc_images_and_preserves_snapshot`.
- [x] Analysis include flags control engine input and snapshots — verified: `test_analysis_include_flags_control_request_and_snapshot`.
- [x] Partial-input disclosure: both analysis responses return deterministic `input_disclosure` derived from `request_snapshot_json`, with stable tokens in `available`/`missing` and machine-token limitations — verified: `test_analysis_disclosure_is_snapshot_derived_and_flags_are_respected`.
- [x] Analysis request tiers are validated (`starter`, `standard`, `professional`) and POST/GET expose the same status/error/error_code/health_score/priority/input_disclosure fields — verified: `test_analysis_tier_and_response_contract_are_consistent`.

## 5. Work orders & the autonomy boundary — FR *Coordinator approval*

The chain "AI proposes → coordinator approves → technician executes → AI
verifies" is the project's governance claim (`FINAL_IDEA.md` §5).

- [x] Draft work order generated from an analysis result, carrying steps/parts/skills/safety — verified: `test_starter_flow` + live probe
- [x] Work-order list — verified: probed live
- [x] Transitions are audited and irreversible past terminal states — verified: the lifecycle test walks all six states and asserts a completed order refuses `cancel`; rejection is terminal too
- [x] `approve` → `approved` and `reject` → `rejected` with a reason — verified: `test_full_work_order_lifecycle`, `test_rejection_records_its_reason`. `submit` is now the draft hand-off; `approve` is the coordinator's decision.
- [x] Work order becomes active only after approval, enforced server-side — verified: `schedule`/`start`/`complete` all 409 until `approved`, asserted in the lifecycle test
- [x] Verification endpoint calling `engine.verify()` once, returning verdict + evidence — verified: resolved, partial, not-resolved, idempotency, and failure tests.
- [x] Post-maintenance report — verified: report and tenant-scoping test.
- [x] Completed work order written back to the knowledge base as history — resolved verification persists a relational `MaintenanceRecord` and synchronously attempts ingestion; ingestion status is reported independently — `test_resolved_verification_reports_ingestion_failure_without_failing_verification`.
- [x] CSV/JSON export of work order and report — tenant-scoped attachments with content headers — `test_work_order_export_has_headers_and_tenant_isolation`.

## 6. Integrations — FR *System & Integration*

- [x] Mock PLC / IoT / ERP adapters exist with a health endpoint — verified: probed live
- [x] A route that actually ingests from `MockPLC.pull()` / `MockIoT` — verified: `test_batch_readings_and_mock_ingest_are_idempotent` covers the PLC route; both routes use the same tested adapter ingestion helper.
- [x] `MockERP.push()` reachable — export JSON/CSV calls the deterministic mock ERP adapter and audits the format plus ERP response; verified: `test_work_order_export_has_headers_and_tenant_isolation`.

## 7. Deployment — FR *Docker deployment*

The rulebook requires a README plus a compose file the judges can run from a
clean clone. Compose configuration and image builds pass; a clean-clone smoke
run is still required before marking this complete.

- [x] `docker-compose.yml` starts Postgres + pgvector with a healthcheck and rerunnable `db-bootstrap` for existing volumes — verified: `docker compose config` and `docker compose build`
- [x] `backend` service in compose — verified: backend depends on healthy `db` and successful `db-bootstrap`; `/health/ready` reports database and storage ready
- [x] `web` service in compose — verified: `docker compose config` and `docker compose build web`
- [x] `backend/Dockerfile` installs the ai-engine — verified: `docker compose build backend` succeeds from the repository root context
- [ ] Verified from a clean clone: `git clone && docker compose up` → working app — not claimed until web and Compose smoke are verified from a clean clone.
- [x] Environment examples cover both databases and `DEEPSEEK_API_KEY` — root `.env.example` is for Compose; `backend/.env.example` is for local SQLite development.
- [x] README paragraph quoting the MVP scope limits and stating compliance — root `README.md` quotes the static-parameter rule and lists the deliberate MVP limits.

## 8. Fixes queued from `../DEFECTS.md`

Blok 0 is done — eight entries deleted from `DEFECTS.md`, tests 5 → 31. What
remains, in order:

1. PDF extraction is implemented for text PDFs; valid empty or image-only PDFs remain unindexable by design and are reported as failed on reindex.

## Test coverage gaps

The committed tests cover the implemented paths. Missing, in priority order:

- [x] Full work-order lifecycle through every legal transition — verified: `test_full_work_order_lifecycle`
- [x] Every illegal transition returns 409 with the right message — verified: `test_illegal_transitions_are_refused_with_the_pair_named`
- [x] `factory_id` isolation: factory A cannot read or mutate factory B's rows — verified: `test_factory_scoping_hides_other_tenants`
- [x] Upload rejections: oversized file and bad extension — verified: `test_upload_rejections`
- [x] Analysis failure path: engine raises → run stored as `failed` with an error code, HTTP still 201 — verified: `test_analysis_failure_is_stored`
- [x] Error envelope shape asserted for 404 / 409 / 422 / 403 / 400 — verified: `test_error_envelope_shape`. FastAPI's own `HTTPException` is wrapped too, so a 403 never arrives as `{"detail": …}`.
