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
  --with python-multipart --with pillow --with pytest --with httpx pytest -q
# ai-engine
cd ai-engine && uv sync --extra dev && uv run pytest -q
```

---

> **Blok 0 landed.** Eight entries were deleted from this file when their fixes
> merged with tests: the approval chain, the shadowed state machine, the dead
> document route, the swallowed re-index NameError, the `PATCH /assets` crash,
> the `progress` NameError, the readiness-branch argument order, and the
> colliding `DATABASE_URL`. `backend/tests` went from 5 to 31.

## Blocking

---

### `#compliance-finetune` — the QC model is not yet part of the analysis chain {#compliance-finetune}

**Where:** `ai-engine/qc/` and the analysis pipeline.

The rulebook states twice that *"Model wajib di fine tune sesuai dengan inovasi
fitur per tim"* (`DECISIONS.md` D1). A MobileNetV3-Small classifier,
preprocessing script, split, weights, and training script now exist under
`qc/`, but the classifier is not wired into the analysis pipeline and the
committed metrics are stale. PatchCore does not satisfy the class-to-failure-
mode chain by itself.

This is a compliance risk, not a bug, and it remains open until the metrics are
regenerated and classifier output reaches the typed analysis result. See
`requirements/AI_ENGINE.md` for the remaining deliverables.

---

## High

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

## Low

### `#chunk-heading-heuristic` — chunking splits on almost anything

`knowledge._split_chunks` treats any line of ≤40 characters not ending in `.` as
a heading. Bullet lists, table rows, and part numbers all split, producing many
small chunks and diluting retrieval. Restrict the heuristic to markdown headings
and numbered section titles.

### `#analysis-history-out-of-scope`

`GET /api/v1/assets/{asset_id}/analyses` implements *Analysis History*, which
`FR.md` explicitly moved to the roadmap because the rulebook excludes it. It is
harmless as an API, but it must not get a screen in the UI. Do not build on it.
