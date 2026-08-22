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
and is the `request_id` in error bodies — surface it in the UI's error state.

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

`message` is a machine-ish token, not user copy. The frontend maps it to
Indonesian copy; it must never be printed raw.

## Gotchas the frontend must know

1. **`AssetOut` returns `specs` and `specs_json`** — the same object under two
   keys. Read `specs`. (`AssetOut` inherits `specs_json` from `AssetIn` and adds
   an alias.) Consolidate when convenient; the frontend should not depend on
   `specs_json`.
2. **`PUT …/business-context` is a full replace, not a patch.** Fields you omit
   are written as `null`. Always send the complete object — read, merge, send.
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
| GET | `/health/ready` | `{"status":"ready","database":"ok","storage":"ok"}` — failure branch broken, `DEFECTS.md#ready-jsonresponse-args` |
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
| PATCH | `/api/v1/assets/{asset_id}` | **broken** — `DEFECTS.md#patch-asset-specs` |
| POST | `/api/v1/assets/import` | multipart `file` (`.csv` or `.json`) → `{"imported":1,"errors":[]}`. Columns: `name` (required), `asset_type`, `criticality`, `external_id` (idempotency key). Bad rows are reported, not fatal. |

`criticality` ∈ `low | medium | high | critical`. `asset_type` is free text.

### Knowledge base

| Method | Path | Notes |
| --- | --- | --- |
| POST | `/api/v1/knowledge/documents` | multipart `file` + query `kind` (`sop` default, `manual`, `log`) + optional `asset_id`. 201 `DocumentOut`. Max 10 MB. Extensions: `.txt .md .csv .json .pdf` — **no images**, `DEFECTS.md#no-image-upload`. Declared twice in source, `DEFECTS.md#duplicate-doc-route` |
| GET | `/api/v1/knowledge/documents` | `DocumentOut[]` where `status="active"` |
| POST | `/api/v1/knowledge/documents/{doc_id}/reindex` | **always fails** — `DEFECTS.md#reindex-nameerror` |

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
| GET | `/api/v1/assets/{asset_id}/readings` | raw rows, newest first |
| PUT | `/api/v1/assets/{asset_id}/condition` | `{"condition":"chatter noise"}` → echo. Writes `business_context.operator_report`. |
| PUT | `/api/v1/assets/{asset_id}/business-context` | `{"production_schedule","spareparts":[],"sparepart_eta","technicians_available","operator_report"}` → echo. **Full replace.** |
| POST | `/api/v1/assets/{asset_id}/maintenance-records` | `{"performed_at","action","findings","parts_used":[]}` → `{"id"}` |

There is **no batch reading endpoint**, so a sensor CSV must be posted row by
row today. `ReadingBatchIn` exists in `schemas.py` unused — see
`requirements/BACKEND.md`.

### Analysis

```http
POST /api/v1/assets/{asset_id}/analyses           201
{"tier":"professional","trigger":"manual","manual_condition":"chatter",
 "include_history":true,"include_business_context":true}
→ {"id","status":"succeeded","result":{…AnalysisResult…},
   "engine_mode":"offline_stub","error_code":null,"error_message":null,
   "health_score":78,"priority":"medium"}
```

`status` ∈ `succeeded | failed`. On failure `result` is `null` and
`error_code` is `AI_ENGINE_UNAVAILABLE` or `ANALYSIS_FAILED` — the HTTP status is
still 201, so **check `status`, not the status code.**

`engine_mode` ∈ `ai_engine | offline_stub | unavailable | error`.

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
   "asset_id","analysis_id","factory_id","created_at","updated_at"}
```

| Method | Path | Transition | State |
| --- | --- | --- | --- |
| GET | `/api/v1/work-orders` | — | works |
| POST | `/api/v1/work-orders/{id}/approve` | `draft → pending_approval` | **misnamed; nothing reaches `approved`** — `DEFECTS.md#wo-approve` |
| POST | `/api/v1/work-orders/{id}/schedule` | `approved → scheduled` | unreachable |
| POST | `/api/v1/work-orders/{id}/start` | `scheduled → in_progress` | unreachable |
| POST | `/api/v1/work-orders/{id}/block` | `in_progress → blocked` | unreachable |
| POST | `/api/v1/work-orders/{id}/complete` | `in_progress → completed` | unreachable |
| POST | `/api/v1/work-orders/{id}/cancel` | → `cancelled` | works from `pending_approval` |
| POST | `/api/v1/work-orders/{id}/progress` | `{"percentage":0-100,"note":""}` | **broken** — `DEFECTS.md#progress-nameerror` |

State machine (the intended one):

```
draft → pending_approval → approved → scheduled → in_progress → completed
             │                 │          │            │
             ├→ rejected       └──────────┴────────────┴→ cancelled
             │                                     in_progress ⇄ blocked
```

`completed`, `cancelled`, `rejected` are terminal. An illegal transition is
409 `invalid_transition:<from>-><to>`.

### Misc

| Method | Path | Response |
| --- | --- | --- |
| GET | `/api/v1/dashboard/summary` | `{"assets":n,"open_work_orders":n,"analyses":n}` |
| GET | `/api/v1/integrations/health` | `{"plc":"mock","iot":"mock","erp":{"status":"ok","adapter":"mock-erp"}}` |

---

## Routes that must exist and do not

Required by `FR.md` rows or by the locked demo chain (`DECISIONS.md` D11), with
no implementation today. Frontend: build against these shapes; backend: these
are the open work items.

| Method | Path | For | FR row |
| --- | --- | --- | --- |
| POST | `/api/v1/assets/{id}/readings:batch` | sensor CSV in one request | Machine condition input |
| POST | `/api/v1/assets/{id}/qc-batches` | multipart QC images → `{"batch_id","images":[…],"count"}` | Product QC input |
| GET | `/api/v1/qc-batches/{id}` | per-image `defect_class` + confidence, batch defect rate, per-class trend | Product quality report |
| POST | `/api/v1/work-orders/{id}/approve` | `pending_approval → approved` (the real one) | Coordinator approval |
| POST | `/api/v1/work-orders/{id}/reject` | `pending_approval → rejected` + reason | Coordinator approval |
| POST | `/api/v1/work-orders/{id}/result` | technician submits work done, findings, parts used, photos | Maintenance progress input |
| POST | `/api/v1/work-orders/{id}/verify` | one synchronous `engine.verify()` → `{"verdict":"resolved\|partial\|not_resolved","evidence":[],"follow_up":[]}` | Maintenance result verification |
| GET | `/api/v1/work-orders/{id}/report` | final report: problem, action, verdict, final asset state | Post maintenance report |
| GET | `/api/v1/work-orders/{id}/export?format=csv\|json` | export for the customer's own system | Work order & report export |
| POST | `/api/v1/assets/{id}/ingest/plc` | pull one sync batch from `adapters.MockPLC` | PLC / Controller integration |
| POST | `/api/v1/assets/{id}/ingest/iot` | same via `MockIoT` | IoT sensor integration |

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
