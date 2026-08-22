# AI engine — requirements & status

Scope: `ai-engine/`. Owner: AI engineer. Read
[`../ARCHITECTURE.md`](../ARCHITECTURE.md) before changing the contract, and
[`../DEFECTS.md`](../DEFECTS.md) before touching `signals.py`.

## Verify

```bash
cd ai-engine
uv sync --extra dev
uv run pytest -q                  # unit; no API key, no DB, no vision
uv run python -m src.demo         # end-to-end; needs DEEPSEEK_API_KEY + pgvector
uv run python eval/run_eval.py    # priority accuracy / root-cause hit rate / retry rate
```

Last full run: `11 passed, 1 skipped` (the skip is
`test_fit_inspect_round_trip`, which needs the `[vision]` extra).

Tick a box only under the rule in [`../INDEX.md`](../INDEX.md#checklist-rules).

---

## 1. Contract & facade

- [x] `AnalysisRequest` / `AnalysisResult` pydantic contract, optional-everything — verified: `uv run pytest tests/test_engine.py`
- [x] `MaintenanceEngine.analyze()` routes request → context → agent → result with `tier` preserved — verified: `test_analyze_returns_valid_result_with_tier_preserved` (uses `pydantic_ai` `TestModel`, no network)
- [x] Engine overwrites `health_score`, `anomalies`, `defects`, `sources`, `tier`, `model` on the model's output — verified: same test asserts the deterministic fields survive the model
- [ ] `MaintenanceEngine.ask()` plain-text grounded Q&A — **untested**: the code path is exercised only through the backend's offline stub. No unit test with `TestModel`, and `src.demo` was not run in this session. One `TestModel` test closes this.
- [ ] `MaintenanceEngine.verify(work_order, technician_result)` → verdict + evidence — not started. Required by `FR.md` *Maintenance result verification* and demo step 12 (`DECISIONS.md` D4). One synchronous call, no loop, no retraining.
- [ ] `defect_class` + `class_confidence` on `DefectFinding` — **broken by design**: see `../DEFECTS.md#defect-class`. Contract change; update `API.md` and frontend types together.
- [ ] Structured `schedule` object replacing free-text `recommended_window` — not started; shape is in `API.md`.

## 2. Deterministic signals

- [x] Per-tag IQR fence anomaly detection — verified: `test_clean_series_has_no_anomalies`, `test_planted_spike_is_flagged`, `test_too_few_points_returns_empty`
- [x] Weighted-deduction health score (anomalies, defects, overdue, repeat) — verified: `test_health_score_falls_as_anomalies_worsen`, `test_overdue_maintenance_deducts`, `test_health_score_falls_as_defect_severity_rises`
- [x] Severity mapping from fence multiples — verified: `test_severity_mapping`
- [ ] Low-side outliers — **broken**: `../DEFECTS.md#signals-low-outlier-crash`. Crashes the whole analysis. Fix and add all three cases (low-only, high-only, both).
- [ ] Per-asset baselines fitted from a nominal period (median, IQR, p90/p95) and **frozen** — not started. `FINAL_IDEA.md` §8.3 promises it and the rulebook requires static parameters at demo time. Today every call recomputes the fence from the request's own readings, which means a slow drift becomes the new normal and stops being flagged.
- [ ] Trend rules (`trend_up over last 50 cycles`, `variance > 2x baseline`) needed by the mapping corroboration step — not started.

## 3. QC vision — the fine-tuned model *(highest priority; compliance)*

`../DEFECTS.md#compliance-finetune` explains the risk. The rulebook requires one
team-fine-tuned model, and this is it.

- [x] `vision.inspect()` PatchCore wrapper producing typed `DefectFinding` — verified: `test_defectfinding_model`, `test_nonzero_region`, `test_nonzero_region_empty`; `test_fit_inspect_round_trip` skipped without the `[vision]` extra
- [ ] `qc/preprocess.py` — resize 224×224, ImageNet normalisation, augmentation (h-flip, small rotation, brightness jitter), class-weighted imbalance handling, object-disjoint train/val/test split — not started (`FINAL_IDEA.md` §8.3)
- [ ] `qc/train.py` — MobileNetV3-Small or ResNet18 transfer learning, 5 defect classes + `good`, target < 1 hour on CPU — not started
- [ ] Trained weights committed and loadable offline — not started
- [ ] `qc/METRICS.md` — per-class accuracy, confusion matrix, split sizes — not started. The proposal requires the model-development narrative.
- [ ] Classifier wired into the pipeline in place of / alongside PatchCore, emitting `defect_class` — not started
- [ ] Batch aggregation: defect rate per batch and per class, across batches — not started (needed for the "three batches in a row" demo beat)

Dataset: MVTec AD `screw` (CC BY-NC-SA 4.0 — **state the non-commercial licence
openly in the proposal**). Classes: `thread_top`, `thread_side`, `scratch_head`,
`scratch_neck`, `manipulated_front`, `good`. Fallback if the licence is a
problem: a synthetic defect generator (`DECISIONS.md` D2) — never a binary
ok/defect dataset, which would empty the mapping.

## 4. Defect → failure-mode mapping *(the differentiator)*

- [ ] `mapping/qc_failure_modes.yaml` — not started. Full contents are in `FINAL_IDEA.md` §7.2; copy them, do not re-invent.
- [ ] Loader + validation (every `corroborate.tag` must be a real sensor tag; every `source` must resolve to an ingested document) — not started
- [ ] Corroboration step: check each candidate failure mode's signals against the readings before any priority change — not started
- [ ] **Restraint path**: when signals do not corroborate, say so explicitly ("defect rate is up, no machine signal supports it, likely material/handling") and do **not** raise priority — not started. This is a demo beat, not an edge case (`FINAL_IDEA.md` §7.3).
- [ ] `priority_delta` fed to the LLM as an input it must respect, with the mapping row cited — not started

## 5. Scheduling optimiser — `decide.py`

The objective function is fixed wording; use it verbatim from `FINAL_IDEA.md`
§4. ~150 lines, no LLM.

- [ ] Enumerate candidate windows from production-schedule gaps, plus "now, stop production" — not started
- [ ] Drop infeasible candidates: sparepart not arrived, no technician with the required skill, SOP prohibits — not started
- [ ] Score `P(fail before window) × downtime_cost + production_loss_during_window + accumulated_scrap` — not started
- [ ] Return winner **plus runner-up plus why it lost** plus blockers — not started. The runner-up is what turns "optimal" from an adjective into a number a judge can argue with.
- [ ] Result overwritten onto `AnalysisResult` by the engine, never authored by the LLM — not started

## 6. Retrieval / knowledge base

- [ ] pgvector schema + HNSW cosine index, 1024-dim — **untested**: implemented, but every path needs a live Postgres and none was run here. Nothing in `tests/` touches `knowledge.py`.
- [ ] Local `fastembed` `intfloat/multilingual-e5-large` embeddings — **untested**: same. A test that embeds two strings and asserts 1024 dimensions needs no DB and would cover it.
- [x] Token-budgeted, stably-ordered context packing — verified: `test_engine.py` drives `select_context` through `analyze` (`uv run pytest tests/test_engine.py`)
- [x] `sources` audit trail built from the chunks actually used — verified: `test_analyze_returns_valid_result_with_tier_preserved`
- [ ] `ContextDoc.distance` actually holds a similarity — `../DEFECTS.md#knowledge-distance-name`
- [ ] Chunking heuristic splits on real headings only — `../DEFECTS.md#chunk-heading-heuristic`
- [ ] Completed work orders written back as new maintenance-history documents — not started. This is the *only* form of "learning" allowed in this round: knowledge, not weights (`DECISIONS.md` D4).

## 7. Prompting & model

- [ ] Stable system prefix, volatile content in the user turn (DeepSeek context cache) — **unproven**: the structure is right, but the claim is that a second run reports non-zero `cache_read_tokens`, and no such run is recorded. `src.demo` reads `last_usage`; run it twice and record the number.
- [x] Structured output + retry owned by `pydantic_ai` (`output_type=AnalysisResult`, `retries=1`) — verified: `test_engine.py` with `TestModel`
- [x] Every agent has an explicit `name=` — true by inspection of `engine.py`; trivially checkable, no test warranted
- [ ] Citation enforcement — the prompt asks for `[title]` citations but nothing checks that a cited title exists in the retrieved corpus. Add a post-check that flags uncited claims. Not started.
- [ ] Prompt covers the mapping table, the schedule object, and the restraint rule — blocked on §4 and §5

## 8. Evaluation

- [ ] `eval/cases.yaml` + `eval/run_eval.py` scoring priority accuracy, root-cause hit rate, retry rate — **not run**: the harness is written, but it needs `DEEPSEEK_API_KEY` and has never been executed here. Until it produces a number, "we evaluated it" is not a claim we can make.
- [ ] A committed baseline result to compare against — not started. Without a number on record, "we evaluated it" is unverifiable in the proposal.
- [ ] Cases covering the QC→failure-mode chain, including the restraint case — blocked on §4
- [ ] Cases covering partial input (same asset, minimal vs full) — not started; this is the graceful-degradation claim (`FINAL_IDEA.md` §11)

## 9. Packaging & hygiene

- [x] `import src` works with no API key, no DB, no `anomalib` — verified: `uv run pytest` passes with none of them present
- [x] Vision isolated behind the `[vision]` extra with in-function imports — verified: the vision test skips cleanly
- [ ] `python-dotenv` and `pillow` declared — `../DEFECTS.md#undeclared-deps`
- [ ] `AIENGINE_DATABASE_URL` split from the backend's `DATABASE_URL` — `../DEFECTS.md#env-database-url`
- [ ] `scripts/gen_synthetic.py` — generator for production schedule, sparepart stock + ETA, technician roster, SOP corpus, with its assumptions documented — not started (`DECISIONS.md` D2/D10; the proposal must describe how synthetic data was produced)
- [ ] `doc/PLAN.md` reconciled with reality or archived — it still describes `analysis.py` and the `aiengine` package name, both gone.

---

## Explicitly not building

From `FR.md` roadmap and `DECISIONS.md` D4. Do not add these even if asked
casually — overbuilding is scored against us.

Continuous learning · auto-tuning · retraining · automatic feedback loops ·
background jobs of any kind · bulk testing scripts · real-time streaming ·
multi-asset fleet optimisation.
