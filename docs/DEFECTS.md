# Verified defects

Every entry below was found by **running** the code in this repo, not by
reading it — except the four marked *(by inspection)*, which are unreachable at
runtime only because an earlier defect blocks the path to them.

Ordered by severity. Anchors (`#wo-approve`) are referenced from the checklists.
Delete an entry when its fix lands **and** a test covers it.

Environment used for reproduction:

```bash
# backend
cd backend && uv run --no-project --python 3.11 \
  --with 'fastapi>=0.115' --with 'sqlalchemy>=2.0' --with 'pydantic-settings>=2.5' \
  --with python-multipart --with pytest --with httpx pytest -q
# ai-engine
cd ai-engine && uv sync --extra dev && uv run pytest -q
```

---

## Blocking

### `#wo-approve` — a work order can never be approved {#wo-approve}

**Where:** [backend/app/main.py](../backend/app/main.py) — the `approve` route
and the `for _path,_target in (…)` loop below it.

`POST /work-orders/{id}/approve` transitions `draft → pending_approval`. The
route loop then registers `schedule`, `start`, `block`, `complete`, `cancel` —
but **no route targets `approved`, and there is no reject route at all**. The
state machine requires `pending_approval → approved → scheduled`, so every work
order dead-ends at `pending_approval`.

```
approve   200 pending_approval
schedule  409 invalid_transition:pending_approval->scheduled
start     409 invalid_transition:pending_approval->in_progress
```

This breaks the entire human-in-the-loop chain — the autonomy boundary that
`FINAL_IDEA.md` §5 and `DECISIONS.md` D9 make a headline claim, and steps 10–13
of the locked demo chain (D11). Nothing downstream of approval is reachable.

**Fix:** rename the current route to `submit` (`draft → pending_approval`), add
`POST /work-orders/{id}/approve` → `approved` and `POST /work-orders/{id}/reject`
→ `rejected`, both carrying the approver identity into the audit event. Add a
test that walks `draft → pending_approval → approved → scheduled → in_progress →
completed`.

---

### `#no-image-upload` — QC images cannot be uploaded {#no-image-upload}

**Where:** [backend/app/main.py](../backend/app/main.py) `ALLOWED_EXTENSIONS`.

```python
ALLOWED_EXTENSIONS = {".txt", ".md", ".csv", ".json", ".pdf"}
```

No image extension is accepted, and there is no QC-image endpoint of any kind.
`AnalysisRequest.images` is therefore always empty in production, so
`vision.inspect` never runs from the API. *Product QC input*, *Product defect
classification*, and *QC-based machine signal analysis* — three Primary FR rows
and the project's stated differentiator — have no path in.

```
POST /api/v1/knowledge/documents  file=x.jpg → 422 unsupported_extension:.jpg
```

**Fix:** add `POST /api/v1/assets/{asset_id}/qc-batches` accepting multiple
images, storing them under `STORAGE_PATH`, returning a batch id; pass the stored
paths as `AnalysisRequest.images`. Keep documents and QC images on separate
routes — they have different size limits and different validation.

---

### `#compliance-finetune` — no fine-tuned model exists {#compliance-finetune}

**Where:** `ai-engine/` — `qc/` does not exist.

The rulebook states twice that *"Model wajib di fine tune sesuai dengan inovasi
fitur per tim"* (`DECISIONS.md` D1). The stack today is a DeepSeek API call,
pre-trained `fastembed` embeddings, IQR rules, and PatchCore — a pre-trained
unsupervised anomaly detector. **Zero fine-tuning.** PatchCore does not count:
nothing is trained, and its `ok`/`defect` output cannot drive the
defect→failure-mode mapping (see `#defect-class`).

This is a compliance risk, not a bug, and it is listed here because it is the
highest-cost item still open. See `requirements/AI_ENGINE.md` for the required
deliverables (`qc/train.py`, `qc/preprocess.py`, weights, `qc/METRICS.md`).

---

## High

### `#signals-low-outlier-crash` — low-side anomalies raise ValueError {#signals-low-outlier-crash}

**Where:** [ai-engine/src/signals.py](../ai-engine/src/signals.py) in
`detect_anomalies`.

```python
observed, upper_out, lower_out = np.max(above), 0.0, 0.0
```

runs before `if above.size:`, so a tag whose only outlier is **below** the fence
calls `np.max` on an empty array.

```python
vals = [50, 50.2, 49.8, 50.1, 50.3, 49.9, 50.0, 50.1, 5.0]   # one low outlier
detect_anomalies(rs)
# ValueError: zero-size array to reduction operation maximum which has no identity
```

Real and likely: a dropped sensor reading, a stalled spindle, and a pressure
loss all present as low-side outliers. It crashes `select_context`, so the whole
analysis 500s.

`upper_out`, `lower_out`, and `iqr_dist` are dead variables, and the branch that
compares a low outlier against a high one can never be true. Rewrite the block
rather than patching the guard: pick the observation with the largest absolute
distance beyond its own fence, then compute severity from that.

**Fix + test:** add a `test_signals.py` case for a low-only outlier, a
high-only outlier, and both-sides.

---

### `#transition-shadowed` — two state machines, tests check the unused one {#transition-shadowed}

**Where:** [backend/app/main.py](../backend/app/main.py) imports
`from .services import run_analysis, transition`, then **redefines** both
`TRANSITIONS` and `transition` further down the same file. The local definitions
win for every route.

The two tables also disagree: `services.TRANSITIONS["draft"]` is
`{"pending_approval", "cancelled"}`, `main.TRANSITIONS["draft"]` is
`{"pending_approval"}`. `tests/test_unit.py` imports from `services`, so the
state machine the app actually runs is untested.

**Fix:** delete the copy in `main.py` and the now-unused import shadowing; keep
one table in `services.py`. Point the test at the live one.

---

### `#patch-asset-specs` — PATCH /assets/{id} always 500s {#patch-asset-specs}

**Where:** [backend/app/main.py](../backend/app/main.py) `update_asset`.

```python
a.specs_json = data.specs      # AssetIn has `specs_json`, not `specs`
# AttributeError: 'AssetIn' object has no attribute 'specs'
```

`AssetOut` aliases `specs_json → specs` for output; `AssetIn` does not. The
route is unreachable in the current tests.

**Fix:** `a.specs_json = data.specs_json`, and add the round-trip to
`test_api.py`. While there, decide one name for the field across `AssetIn`,
`AssetOut`, and the frontend, and record it in `API.md`.

---

### `#reindex-nameerror` — document re-index can never succeed {#reindex-nameerror}

**Where:** [backend/app/main.py](../backend/app/main.py) `reindex_document`.

The handler calls `knowledge.ingest(Document(...))`, but `Document` is not
imported — `from .schemas import *` exports `DocumentOut`, not `Document` (the
engine's `Document` lives in `src.schemas`). The resulting `NameError` is
swallowed by the `except Exception` and written to the row, so the endpoint
returns **200 with `ingestion_status: "failed"`** every time — a silent failure
that looks like a working endpoint.

```
POST /api/v1/knowledge/documents/{id}/reindex
200 {"ingestion_status":"failed","ingestion_error":"No module named 'src'"}
```

(The message differs when `src` is installed; the outcome does not.)

**Fix:** `from src import Document as EngineDocument` inside the handler, next
to the `knowledge` import. Narrow the `except` so an unexpected error is not
recorded as an ingestion failure. Test with `AI_ENGINE_ENABLED=true` against a
live pgvector.

---

## Medium

### `#duplicate-doc-route` — the same route is declared twice {#duplicate-doc-route}

`POST /api/v1/knowledge/documents` is registered twice in
[backend/app/main.py](../backend/app/main.py), by two functions both named
`document`. Starlette matches the **first**, so the validated version (with
`_check_file` and the size limit) is the live one and the second is dead code —
but the file reads as if the unvalidated one were in effect, and a reorder would
silently drop file validation.

```python
len([r for r in app.routes if r.path == "/api/v1/knowledge/documents" and "POST" in r.methods])  # 2
```

**Fix:** delete the second definition, along with the stray mid-file
`import re` / `from pydantic import validator` (the latter is a deprecated
pydantic v1 import and is unused).

---

### `#progress-nameerror` — technician progress raises NameError *(by inspection)* {#progress-nameerror}

**Where:** [backend/app/main.py](../backend/app/main.py) `progress`.

The handler calls `audit(db, identity, request.state.request_id, …)` but has no
`request: Request` parameter, and no module-level `request` exists. Both
branches touch it, so every successful call raises `NameError` → 500.

Currently unreachable: a work order cannot reach `in_progress`
(see `#wo-approve`), so the status guard rejects the call first with 409.

**Fix:** add `request: Request` to the signature. Then reconsider the design —
`percentage == 100` silently completing the work order bypasses the verification
step the autonomy boundary requires. Progress should record progress; completion
should go through verification.

---

### `#ready-jsonresponse-args` — the readiness failure branch is itself broken *(by inspection)* {#ready-jsonresponse-args}

**Where:** [backend/app/main.py](../backend/app/main.py) `ready`.

```python
return JSONResponse(503, {"status": "not_ready", "database": "error"})
```

`JSONResponse(content, status_code=…)` — the arguments are swapped, so the
degraded path returns `content=503` with a dict as the status code and raises.
The healthy path returns 200 correctly, which is why tests pass.

**Fix:** `JSONResponse(status_code=503, content={...})`. Test by pointing
`DATABASE_URL` at a dead host.

---

### `#env-database-url` — one env var, two different databases {#env-database-url}

`backend/app/config.py` reads `DATABASE_URL` for the application database
(SQLite by default). `ai-engine/src/config.py` reads `DATABASE_URL` for the
pgvector knowledge base. They run **in the same process**. Setting one to a
Postgres URL points the other at the same server; leaving the backend on SQLite
means the engine tries to open a SQLite URL with `psycopg` and fails.

**Fix:** rename the engine's variable to `AIENGINE_DATABASE_URL` (keeping
`DATABASE_URL` as a fallback for standalone use), and document both in
`.env.example`. Cheap now, painful during a recorded demo.

---

### `#defect-class` — DefectFinding has no defect class {#defect-class}

**Where:** [ai-engine/src/schemas.py](../ai-engine/src/schemas.py).

```python
label: Literal["ok", "defect"]
```

The differentiator chain needs `thread_top` / `thread_side` / `scratch_head` /
`scratch_neck` / `manipulated_front` to look up candidate failure modes.
`DECISIONS.md` D2 says it outright: *"Jangan pakai dataset biner ok/defect —
mapping-nya jadi kosong lagi."* A binary label cannot key into
`mapping/qc_failure_modes.yaml`.

**Fix:** add `defect_class: str | None` and `class_confidence: float | None` to
`DefectFinding`, produced by the fine-tuned classifier (`#compliance-finetune`).
This is a change to the backend↔engine contract — update `API.md` and the
frontend types in the same change.

---

### `#stub-health-inverted` — the offline stub gets worse the more data it has {#stub-health-inverted}

**Where:** [backend/app/services.py](../backend/app/services.py) `StubEngine.analyze`.

```python
score = max(0, 100 - min(70, len(request.readings) * 2) - (20 if request.manual_condition else 0))
```

Health is a function of *how many readings exist*, so 35 readings alone yield a
`critical` asset. The stub is what runs with `AI_ENGINE_ENABLED=false` — the
default, and the fallback if DeepSeek is unreachable while recording.

**Fix:** call `src.signals.detect_anomalies` and `signals.health_score` from the
stub. They are pure, dependency-light, and already tested; the stub then differs
from the real engine only in that it writes no narrative. That also keeps the
demo honest if the API is down.

---

## Low

### `#undeclared-deps` — two imports are not declared {#undeclared-deps}

`ai-engine/src/config.py` imports `dotenv`, and `ai-engine/tests/test_vision.py`
imports `PIL`. Neither `python-dotenv` nor `pillow` is in
`ai-engine/pyproject.toml`; both resolve today only as transitive dependencies
(`python-dotenv 1.2.2`, `pillow 12.3.0`). A dependency bump can remove either
and break `import src` — the failure mode is an import error at container start.

**Fix:** declare `python-dotenv` in `dependencies` and `pillow` in the `dev`
extra.

### `#knowledge-distance-name` — `distance` holds a similarity

`ai-engine/src/knowledge.py` selects `1 - (embedding <=> %s) AS distance` and
stores it in `ContextDoc.distance`. That expression is cosine *similarity*
(higher is better); the ordering is correct because it sorts on the raw
operator, but anything that later filters or ranks on `.distance` will invert.
Rename the field to `similarity`.

### `#chunk-heading-heuristic` — chunking splits on almost anything

`knowledge._split_chunks` treats any line of ≤40 characters not ending in `.` as
a heading. Bullet lists, table rows, and part numbers all split, producing many
small chunks and diluting retrieval. Restrict the heuristic to markdown headings
and numbered section titles.

### `#analysis-history-out-of-scope`

`GET /api/v1/assets/{asset_id}/analyses` implements *Analysis History*, which
`FR.md` explicitly moved to the roadmap because the rulebook excludes it. It is
harmless as an API, but it must not get a screen in the UI. Do not build on it.
