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

> **Blok 0 landed.** Eight entries were deleted from this file when their fixes
> merged with tests: the approval chain, the shadowed state machine, the dead
> document route, the swallowed re-index NameError, the `PATCH /assets` crash,
> the `progress` NameError, the readiness-branch argument order, and the
> colliding `DATABASE_URL`. `backend/tests` went from 5 to 14.

## Blocking

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

## Medium

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
