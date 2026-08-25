# HTTP API contract

The interface between `frontend/` and `backend/`. **Every shape below was
captured from a running server**, not transcribed from source — trust this file
over reading `main.py`, and update it in the same commit as any route change.

Base URL: `http://localhost:8000`. All product routes are under `/api/v1`.

## Identity

Two headers on every request. This is demo scoping, not authentication
(`FR.md` puts real auth on the roadmap).

```
X-Demo-User: demo-engineer      # → role engineer (default)
X-Factory-ID: demo-factory      # → tenant scope (default)
```

Roles: `demo-viewer`, `demo-technician`, `demo-manager`, `demo-admin`; anything
else is `engineer`. `X-Factory-ID` must match `[A-Za-z0-9][A-Za-z0-9_-]{0,63}`
or the request 400s. A `X-Request-ID` header is echoed back on every response,
truncated to 36 characters when longer, and is the `request_id` in error bodies —
surface it in the UI's error state.

## Error envelope

Every error uses one shape. Never render a raw FastAPI error.

```jsonc
{
  "error": {
    "code": "VALIDATION_ERROR",          // NOT_FOUND | CONFLICT | VALIDATION_ERROR
    "message": "Input tidak valid",
    "details": [{"field": "body.name", "reason": "String should have at least 1 character"}],
    "request_id": "50d9a869-5eb7-4cf5-909d-6b81d9e0f927"
  }
}
```

| Status | `code` | When |
| --- | --- | --- |
| 404 | `NOT_FOUND` | message ends in `_not_found` (`asset_not_found`, `analysis_not_ready`, …) |
| 409 | `CONFLICT` | `invalid_transition:<from>-><to>` — an illegal work-order state change |
| 422 | `VALIDATION_ERROR` | pydantic body/query validation, and file-upload rejections |
| 403 | `FORBIDDEN` | the role may not perform this action (approval, rejection) |
| 400 | `VALIDATION_ERROR` | malformed `X-Factory-ID` |

FastAPI's own `HTTPException` is wrapped in the same envelope, so a 403 never
arrives as `{"detail": …}`.

`message` is a machine-ish token, not user copy. The frontend maps it to
Indonesian copy; it must never be printed raw.

## Gotchas the frontend must know

1. **`AssetOut` returns `specs` and `specs_json`** — the same object under two
   keys. Read `specs`. (`AssetOut` inherits `specs_json` from `AssetIn` and adds
   an alias.) Consolidate when convenient; the frontend should not depend on
   `specs_json`.
2. **`PUT /api/v1/business-context` is a full replace, not a patch.** Fields you
   omit are written as `null`. Always send the complete object — read, merge, send.
   It is **factory-wide**: shifts, technician roster and spare part stock are set
   once, not per analysis. Only the operator report is per machine, via
   `PUT …/assets/{id}/condition`.
3. **Datetimes come back without a timezone suffix** on SQLite
   (`"2026-08-20T10:00:00"`), even though the columns are `timezone=True`.
   Treat every timestamp as UTC and normalise on the client; do not feed the raw
   string to `new Date()` and assume local time is wrong or right.
4. **List routes without a `response_model` return the raw table row** —
   readings, work orders and analyses include `factory_id` and other internals.
   Type them narrowly on the client and ignore the extras.
5. **`POST …/analyses` is synchronous and slow.** With the real engine it is one
   DeepSeek call (up to `AIENGINE_TIMEOUT`, default 120 s). There is no polling
   endpoint and no job queue by design. The UI must hold a determinate-feeling
   progress state for up to two minutes — see `design/SCREENS.md`.

---

## Implemented routes

Verified working unless annotated.

### Health & capabilities

| Method | Path | Response |
| --- | --- | --- |
| GET | `/health/live` | `{"status":"ok"}` |
| GET | `/health/ready` | `{"status":"ready","database":"ok","storage":"ok"}`; returns 503 with component statuses when not ready |
| GET | `/config/capabilities` | `{"tier":"starter","capabilities":{"assets":true,"documents":true,"analysis":true,"work_orders":true,"mock_plc":true,"ai_engine":false}}` |

`capabilities.ai_engine` tells the UI whether answers come from the real engine
or the offline stub. Show it; do not hide the difference.

### Assets

```http
POST /api/v1/assets            201
{"name":"CNC-02","asset_type":"cnc-mill","criticality":"high","location":null,"specs_json":{}}
→ {"name":"CNC-02","asset_type":"cnc-mill","criticality":"high","location":null,
   "specs_json":{...},"specs":{...},"id":"<uuid>","factory_id":"demo-factory","status":"active"}
```

| Method | Path | Notes |
| --- | --- | --- |
| GET | `/api/v1/assets` | `AssetOut[]`, ordered by name |
| POST | `/api/v1/assets` | 201, audited |
| GET | `/api/v1/assets/{asset_id}` | 404 `asset_not_found` |
| PATCH | `/api/v1/assets/{asset_id}` | updates asset fields and returns `AssetOut` |
| POST | `/api/v1/assets/import` | multipart `file` (`.csv` or `.json`) → `{"imported":1,"errors":[]}`. Columns: `name` (required), `asset_type`, `criticality`, `external_id` (idempotency key). Bad rows are reported, not fatal. |

`criticality` ∈ `low | medium | high | critical`. `asset_type` is free text.

### Knowledge base

| Method | Path | Notes |
| --- | --- | --- |
| POST | `/api/v1/knowledge/documents` | multipart `file` + query `kind` (`sop` default, `manual`, `log`, `qc_standard`, `maintenance_history`) + optional `asset_id`. 201 `DocumentOut`. Max `MAX_UPLOAD_BYTES` (default 10 MB). Extensions: `.txt .md .csv .json .pdf` — `.xlsx` is only supported by maintenance-history import; images use the separate QC batch route. Text PDFs are extracted with bounded pages/text; malformed or over-limit PDFs return validation errors. |
| GET | `/api/v1/knowledge/documents` | `DocumentOut[]` where `status="active"` |
| POST | `/api/v1/knowledge/documents/{doc_id}/reindex` | tenant-scoped, idempotently replaces that document's chunks when ai-engine and pgvector are available; otherwise records `failed` with an error |

```jsonc
// DocumentOut
{"id":"…","title":"SOP-CNC-04.txt","kind":"sop","filename":"SOP-CNC-04.txt",
 "size_bytes":30,"ingestion_status":"pending","ingestion_error":null}
```

`ingestion_status` ∈ `pending | ready | failed`. Upload only sets `pending` —
embedding happens on reindex. The UI must show this state per document, because
a `pending` document is **not** in the RAG corpus and will not appear in
`result.sources`.

### Readings & context

| Method | Path | Body → Response |
| --- | --- | --- |
| POST | `/api/v1/assets/{asset_id}/readings` | `{"tag","value","unit","recorded_at","source","external_id"}` → `{"id","quality"}`. Idempotent on `external_id`: a repeat returns the existing row. |
| POST | `/api/v1/assets/{asset_id}/readings:batch` | JSON `{"readings":[ReadingIn,…]}` (1–5000) → `{"count","readings":[{"id","quality"},…]}`. Each row reuses single-reading idempotency. |
| POST | `/api/v1/assets/{asset_id}/readings/import` | multipart CSV with `tag,value,unit,recorded_at,source,external_id` → count, row errors and reading results. Each row reuses single-reading idempotency. |
| GET | `/api/v1/assets/{asset_id}/readings` | raw rows, newest first |
| PUT | `/api/v1/assets/{asset_id}/condition` | `{"condition":"chatter noise"}` → echo. Writes `asset.operator_report` — the one per-machine piece of business context. |
| POST | `/api/v1/assets/{asset_id}/maintenance-records` | `{"performed_at","action","findings","parts_used":[]}` → `{"id"}` |
| POST | `/api/v1/maintenance-records/import` | multipart `.csv` or `.xlsx`; rows use `asset_id` or tenant-local `asset_external_id`, plus `performed_at`, `action`, optional `findings`, comma-separated `parts_used`, and optional tenant-scoped `external_id`. Repeating an external id creates no duplicate and returns a row error. |

Batch readings are accepted in one request, with the same `external_id`
idempotency semantics as the single-reading route.

### Business context (factory-wide)

| Method | Path | Notes |
| --- | --- | --- |
| GET | `/api/v1/business-context` | `{"production_schedule":{"work_time":{day:{start,end}}},"inventory":[SparePart],"technicians":[TechnicianSchedule]}`; empty fields when never set |
| PUT | `/api/v1/business-context` | same shape → echo. **Full replace.** Times are `HH:MM` or `HH:MM:SS`; days are lowercase English names. Mirrors `ai-engine/src/schemas.py`. |

Each `SparePart` carries `asset_ids`: the machines it fits, many-to-many. Linking a
machine from another factory is a 404, not a silent drop. **An analysis only ever
sees the target machine's parts** — the rest of the warehouse is never sent to the
engine, so a part with no `asset_ids` reaches no analysis at all.

### Quality control batches

| Method | Path | Notes |
| --- | --- | --- |
| POST | `/api/v1/assets/{asset_id}/qc-batches` | multipart `files` with PNG/JPEG images. The server decodes images, enforces per-image (5 MB), aggregate (50 MB), and count (20) limits, stores generated safe keys, and returns the batch plus images. |
| GET | `/api/v1/qc-batches/{id}` | tenant-scoped batch with image metadata, `defect_count`, and `defect_rate` |

QC images can be selected for analysis with `qc_batch_id`; their resolved
storage paths are passed to the engine and recorded in `request_snapshot`.

### Analysis

```http
POST /api/v1/assets/{asset_id}/analyses           201
{"tier":"professional","trigger":"manual","manual_condition":"chatter",
 "include_history":true,"include_business_context":true}
→ {"id","status":"succeeded","result":{…AnalysisResult…},
   "engine_mode":"offline_stub","error":null,"error_code":null,"error_message":null,
    "health_score":78,"priority":"medium",
    "input_disclosure":{"available":["manual_condition"],"missing":["readings","history","business_context","qc_images"],"limitations":[{"token":"readings","reason":"no_readings"},{"token":"history","reason":"not_in_snapshot"},{"token":"business_context","reason":"not_in_snapshot"},{"token":"qc_images","reason":"no_qc_images"}]}}
```

`status` ∈ `succeeded | failed`. On failure `result` is `null` and
`error_code` is `AI_ENGINE_UNAVAILABLE` or `ANALYSIS_FAILED` — the HTTP status is
still 201, so **check `status`, not the status code.**

`engine_mode` ∈ `ai_engine | offline_stub | unavailable | error`.

Both analysis responses include the same `status`, `error`, `error_code`,
`health_score`, `priority`, and `input_disclosure` fields. POST also retains
`error_message` for existing clients; GET additionally includes
`request_snapshot`. `input_disclosure` is derived only from the immutable
request snapshot:

```jsonc
{
  "available": ["readings", "history", "business_context", "manual_condition", "qc_images"],
  "missing": ["readings", "history", "business_context", "manual_condition", "qc_images"],
  "limitations": [
    {"token": "readings", "reason": "no_readings"},
    {"token": "history", "reason": "not_in_snapshot"},
    {"token": "business_context", "reason": "not_in_snapshot"},
    {"token": "qc_images", "reason": "no_qc_images"}
  ]
}
```

The five stable tokens are `readings`, `history`, `business_context`,
`manual_condition`, and `qc_images`. A token occurs in exactly one of
`available` or `missing`. `limitations` contains one object for each missing
token, with machine-token reasons such as `no_readings`, `not_in_snapshot`,
`no_manual_condition`, and `no_qc_images`. The disclosure does not add to or
modify `request_snapshot`; excluded history or business context therefore
appears as missing with `not_in_snapshot`.

`result` is the engine's `AnalysisResult`:

```jsonc
{
  "health_score": 78,                       // int 0–100, deterministic
  "health_summary": "…",
  "anomalies": [{"tag":"torque_nm","observed":92.4,"expected_range":[58.1,81.2],
                 "severity":"high","method":"iqr"}],
  "defects":   [{"image":"…","subject":"product","score":0.81,"threshold":0.5,
                 "label":"defect","severity":"high","region":[x,y,w,h],
                 "heatmap_path":null,"method":"patchcore"}],
  "root_causes":[{"cause":"…","confidence":0.7,"evidence":["…"]}],
  "recommendation": "…",
  "priority": "low|medium|high|critical",
  "recommended_window": "within 48h",       // string today; becomes structured, see below
  "explanation": "…",                       // cites documents as [title]
  "blockers": ["…"],
  "work_order": {"title","steps":[],"parts":[],"est_duration_h":3.0,
                 "required_skills":[],"safety_notes":[]},
  "tier": "professional", "model": "deepseek-chat",
  "sources": ["SOP-CNC-04#3"]               // "<doc title>#<chunk id>"
}
```

| Method | Path | Notes |
| --- | --- | --- |
| GET | `/api/v1/analyses/{analysis_id}` | adds `request_snapshot` — the exact inputs used. This is what powers the "what did the AI actually see" panel and the partial-input disclosure. |
| GET | `/api/v1/assets/{asset_id}/analyses` | history. **Do not build a screen on this** — `DEFECTS.md#analysis-history-out-of-scope`. |
| POST | `/api/v1/assets/{asset_id}/ask` | `{"question":"…"}` → `{"answer":"…"}`. Plain-text grounded Q&A. |

### Work orders

```http
POST /api/v1/analyses/{analysis_id}/work-orders   201
→ {"id","title","description","priority","status":"draft","details_json":{…work_order…},
   "asset_id","analysis_id","factory_id","technician_result_json":null,
   "result_submitted_at":null,"created_at","updated_at"}
```

| Method | Path | Transition | Role |
| --- | --- | --- | --- |
| GET | `/api/v1/work-orders` | — | any |
| POST | `/api/v1/work-orders/{id}/submit` | `draft → pending_approval` | any |
| POST | `/api/v1/work-orders/{id}/approve` | `pending_approval → approved` | **manager / admin** |
| POST | `/api/v1/work-orders/{id}/reject` | `pending_approval → rejected` | **manager / admin** — body `{"reason": "…"}`, required; stored on `details_json.rejection_reason` |
| POST | `/api/v1/work-orders/{id}/schedule` | `approved → scheduled` | any |
| POST | `/api/v1/work-orders/{id}/start` | `scheduled → in_progress` | any |
| POST | `/api/v1/work-orders/{id}/block` | `in_progress → blocked` | any |
| POST | `/api/v1/work-orders/{id}/complete` | rejected; completion requires resolved verification | any |
| POST | `/api/v1/work-orders/{id}/cancel` | → `cancelled` | any |
| POST | `/api/v1/work-orders/{id}/progress` | records progress; **never completes** | any |

`approve` and `reject` are the autonomy boundary made literal: the AI proposes,
a coordinator decides. A non-coordinator gets 403 with code `FORBIDDEN`.
`progress` records a note and a percentage and deliberately does **not** close
the work order — completion goes through verification.

`POST /api/v1/work-orders/{id}/result` accepts `{"work_done":"…","findings":"…","parts_used":[],"evidence":[]}` and is technician-only. The same payload retry returns the stored result; a conflicting retry returns 409. `POST /api/v1/work-orders/{id}/verify` is synchronous and tenant-scoped for any role, returning `{"id":"…","status":"completed|in_progress","verification":{"verdict":"resolved|partial|not_resolved","evidence":[],"follow_up":[],"ingestion":{"status":"ready|failed","error":null}},"verified_at":"…"}`. The app transaction commits the completed work order, relational maintenance record, and history document before best-effort vector ingestion. Repeated verification creates no duplicates and retries failed ingestion. Only `resolved` changes `in_progress` to `completed`; the other verdicts remain `in_progress`. Verification success is independent of best-effort knowledge ingestion. `GET /api/v1/work-orders/{id}/report` is tenant-scoped and any role.

`GET /api/v1/work-orders/{id}/export?format=json|csv` returns a tenant-scoped attachment containing the work order and, when available, its report. JSON uses `application/json`; CSV uses `text/csv` and both include `Content-Disposition`. Each export also calls the deterministic `MockERP.push()` adapter and writes a `work_order.exported` audit event containing the requested format and accepted ERP result. This is the scoped ERP substitute described by `FR.md`, not a real ERP integration.

State machine (the intended one):

```
draft → pending_approval → approved → scheduled → in_progress → completed
             │                 │          │            │
              ├→ rejected       └──────────┴────────────┴→ cancelled
              │                                     in_progress ⇄ blocked
              │                                     resolved verification → completed
```

`completed`, `cancelled`, `rejected` are terminal. An illegal transition is
409 `invalid_transition:<from>-><to>`.

### Misc

| Method | Path | Response |
| --- | --- | --- |
| GET | `/api/v1/dashboard/summary` | `{"assets":n,"open_work_orders":n,"analyses":n}` |
| GET | `/api/v1/integrations/health` | `{"plc":"mock","iot":"mock","erp":{"status":"ok","adapter":"mock-erp"}}` |

| POST | `/api/v1/assets/{id}/ingest/plc` | pulls from `MockPLC` and persists the returned readings |
| POST | `/api/v1/assets/{id}/ingest/iot` | pulls from `MockIoT` and persists the returned readings |

---

## Routes that remain open

Required by `FR.md` rows or by the locked demo chain (`DECISIONS.md` D11). The
remaining backend work is listed below; frontend: build against the verified
shapes above.

| Method | Path | For | FR row |
| --- | --- | --- | --- |
No required backend routes remain open in this batch. Future contract changes are listed below.

Two contract changes land with these:

- `AnalysisResult.defects[]` gains `defect_class` and `class_confidence`
  (`DEFECTS.md#defect-class`).
- `AnalysisResult` gains a structured schedule instead of the free-text
  `recommended_window`:

```jsonc
"schedule": {
  "chosen":    {"start":"2026-08-24T22:00:00Z","end":"2026-08-25T00:00:00Z",
                "expected_cost":18400000,"rationale":"…"},
  "runner_up": {"start":"…","end":"…","expected_cost":24100000,
                "lost_because":"scrap accumulates for 3 more shifts"},
  "blockers":  ["insert TNMG ETA 2 days"]
}
```

Both are deterministic (`decide.py`), so the engine overwrites them on the
result exactly like `health_score`. See `ARCHITECTURE.md` → Invariants.
