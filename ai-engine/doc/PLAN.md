# ai-engine implementation plan

> **Deviation note (implementation):** the DeepSeek call is made through
> **pydantic_ai** (`pydantic_ai.Agent` + `OpenAIChatModel`/`DeepSeekProvider`)
> rather than the raw `openai` SDK. The structured-output validation and retry
> that the plan describes in `analysis.py` are now owned by the framework
> (`output_type=AnalysisResult`, `retries=1`) — `analysis.py` was deleted and
> the Agent lives in `engine.py`. The package directory is `src`, not
> `aiengine`. Core design (deterministic signals, optional-everything request,
> pgvector retrieval, 64K budget) is unchanged.

## Context

AIC Compfest submission: a predictive-maintenance system for mid-size factories. The repo (`aic-26`) is empty scaffolding — `ai-engine/`, `backend/`, `frontend/`, no commits. The task split (from the doc's image) is: **AI Engineer** owns the AI pipeline, RAG/knowledge base, prompt engineering, maintenance recommendation, root-cause analysis, and AI evaluation; **Backend** owns FastAPI, DB, Docker, uploads, and mock PLC/IoT/ERP integrations; **Frontend** owns the UI.

This plan covers only `ai-engine/`. Decisions confirmed with you:

- ai-engine is an **importable Python package** the FastAPI backend imports — one process, one Dockerfile. Separation of concern comes from module boundaries plus a single facade class.
- **DeepSeek API** for reasoning (OpenAI-compatible endpoint); **Postgres/pgvector** for the knowledge base.
- **Statistical rules** (rolling median / IQR) for anomaly detection and health scoring — no trained model.

The outcome: `backend` calls `MaintenanceEngine.analyze(...)` with whatever data it has, and gets back a typed result containing health score, anomalies, root causes, recommendation, priority, explanation, and a draft work order — everything the "AI Analysis" and "Output generation" rows of the requirement table need.

### What DeepSeek changes vs. a frontier-model plan

Three things drive the design, and they're the reason this plan differs from the obvious one:

1. **~64K context, not 1M.** You cannot stuff the whole corpus into every request. Retrieval is load-bearing from Phase 2, not a "later if needed" optimization. The prompt budget below is sized for it.
2. **No `json_schema` strict mode.** DeepSeek supports JSON *mode* (`response_format={"type": "json_object"}`) but not schema-enforced decoding. The model can return valid JSON with the wrong shape, so `analysis.py` validates with pydantic and retries once with the validation error appended. That retry is not optional — it's the price of the provider.
3. **No embeddings API.** DeepSeek doesn't ship one (neither does Anthropic). pgvector needs a local embedder — `fastembed` with `BAAI/bge-m3`, which handles Indonesian and English in one model, runs on CPU, needs no key, and downloads once into the Docker image. This is a plus for a hackathon demo: retrieval keeps working with the network unplugged.

Access is through the `openai` SDK pointed at `https://api.deepseek.com` — DeepSeek is wire-compatible, so no custom HTTP client.

### Model choice

Two models exist: `deepseek-chat` (V3) and `deepseek-reasoner` (R1, emits chain-of-thought before the answer).

**Start on `deepseek-chat` for everything.** It's faster, cheaper, and its JSON-mode output is the reliable one — `deepseek-reasoner` spends its budget on reasoning tokens and is the awkward fit for a strict output shape. Escalate the single hardest call (the Professional-tier scheduling/constraint reasoning) to `deepseek-reasoner` **only if** the Phase 3 eval shows `deepseek-chat` getting scheduling conflicts wrong. Model id lives in one constant; escalating is a one-line change plus a separate parse path.

## Layout

```
ai-engine/
  pyproject.toml            # package "aiengine"
                            # deps: openai, pydantic, numpy, fastembed, psycopg[binary], pgvector
  aiengine/
    __init__.py             # exports MaintenanceEngine, schemas
    config.py               # env: DEEPSEEK_API_KEY, DATABASE_URL, model id, budgets
    schemas.py              # the contract with backend — pydantic models
    embed.py                # fastembed wrapper: embed(texts) -> vectors
    knowledge.py            # pgvector ingest + similarity search
    context.py              # select_context(): retrieve + token-budget the prompt corpus
    signals.py              # anomaly detection + health scoring (pure, no LLM)
    prompts.py              # system prompt + task templates
    analysis.py             # the DeepSeek call: prompt -> AnalysisResult (validate + retry)
    engine.py               # MaintenanceEngine facade
  tests/
    test_signals.py         # asserts on synthetic series
    test_engine.py          # engine wiring with a stub analyzer
  eval/
    cases.yaml              # ~10 labelled scenarios
    run_eval.py             # scores recommendations against expected outcomes
```

Backend installs it with `pip install -e ../ai-engine` (or a path dep) and imports `from aiengine import MaintenanceEngine`.

## The contract (`schemas.py`)

This file is the whole interface between the two of you — write it first and agree on it before either side builds.

```python
class Tier(StrEnum): STARTER; STANDARD; PROFESSIONAL

class Asset(BaseModel):          # id, name, type, criticality, install_date, specs
class SensorReading(BaseModel):  # tag, value, unit, recorded_at
class MaintenanceRecord(BaseModel):  # asset_id, performed_at, action, findings, parts_used
class Document(BaseModel):       # id, title, kind ("sop"|"manual"), text
class BusinessContext(BaseModel):    # production_schedule, spareparts[], sparepart_eta,
                                     # technicians_available, operator_report — all Optional
class AnalysisRequest(BaseModel):
    tier: Tier
    asset: Asset
    readings: list[SensorReading] = []
    manual_condition: str | None = None
    history: list[MaintenanceRecord] = []
    business: BusinessContext = BusinessContext()
    # documents are NOT passed inline — they live in pgvector, retrieved by asset + query

class Anomaly(BaseModel):     # tag, observed, expected_range, severity, method
class RootCause(BaseModel):   # cause, confidence, evidence[]
class WorkOrder(BaseModel):   # title, steps[], parts[], est_duration_h, required_skills[], safety_notes[]
class AnalysisResult(BaseModel):
    health_score: int            # 0-100, from signals.py, not the LLM
    health_summary: str
    anomalies: list[Anomaly]
    root_causes: list[RootCause]
    recommendation: str
    priority: Literal["low","medium","high","critical"]
    recommended_window: str | None   # e.g. "Sat 14:00-18:00, after batch #221"
    explanation: str                 # cites SOP/history/constraints by name
    blockers: list[str]              # e.g. "bearing SKF-6204 ETA 5 days"
    work_order: WorkOrder | None
    tier: Tier
    model: str
    sources: list[str]               # doc titles + chunk ids actually retrieved — audit trail
```

**Optional-everything is deliberate.** The tier does not gate logic — the engine reasons over whatever fields are populated, and the backend decides what to populate per tier. Starter sends `manual_condition` and no readings; Professional sends readings plus a full `BusinessContext`. `tier` rides along as a label for the report and to skip anomaly detection when there are no readings. That satisfies "low adoption barrier" with zero branching code.

`documents` moved out of the request because with a 64K window the engine must choose what to include; handing it the full corpus per call and truncating would just move the retrieval problem to the caller.

## Modules

### `signals.py` — deterministic, no LLM

- `detect_anomalies(readings) -> list[Anomaly]`: per-tag rolling median + IQR fence (robust to the spikes we're trying to catch, unlike a mean/σ z-score). Severity from how many fences out. Returns `[]` when a tag has fewer than ~8 points.
- `health_score(asset, anomalies, history) -> tuple[int, str]`: weighted deduction from 100 — anomaly severity, days since last maintenance vs. interval, count of recent repeat failures. Weights live in one `HEALTH_WEIGHTS` dict at module top, tunable without touching logic.

Keeping the score out of the LLM makes it reproducible and defensible to judges: the same machine state always scores the same, and the LLM *explains* the score rather than inventing it. It also matters more here than it would with a frontier model — the smaller model is the part you least want inventing numbers.

### `embed.py`

Thin wrapper over `fastembed.TextEmbedding("BAAI/bge-m3")`, module-level singleton so the model loads once per process. `embed(texts: list[str]) -> list[list[float]]`. That's the whole file.

### `knowledge.py` — pgvector

Two functions and one table:

```sql
CREATE TABLE doc_chunk (
  id BIGSERIAL PRIMARY KEY,
  asset_id TEXT,              -- NULL = applies to all assets
  doc_id TEXT, doc_title TEXT, kind TEXT,
  chunk_index INT, text TEXT,
  embedding VECTOR(1024)
);
CREATE INDEX ON doc_chunk USING hnsw (embedding vector_cosine_ops);
```

- `ingest(document, asset_id=None)` — split on headings then ~800-char windows with overlap, embed, insert. Backend calls this from its upload endpoint.
- `search(query, asset_id, k)` — cosine similarity, filtered to this asset plus global docs.

Owning the schema here (rather than in backend's ORM) keeps retrieval self-contained; backend just calls `ingest`.

### `context.py`

`select_context(request, budget_tokens) -> ContextBundle` — build a retrieval query from the asset, its anomalies, and the operator report; `knowledge.search(...)`; add the N most recent maintenance records; pack to budget. Budget defaults to **~40K tokens**, leaving room for output and a safety margin inside the 64K window. Token counting via `tiktoken` `cl100k_base` as an approximation — DeepSeek's tokenizer differs, so treat the count as an estimate and keep the margin.

Ordering is stable and deterministic (sorted, no timestamps in the prefix) so DeepSeek's automatic context caching can hit — it's prefix-based like every KV cache, but there are no `cache_control` breakpoints to place. Put the corpus first and the volatile question last, and it works for free. Verify with `usage.prompt_cache_hit_tokens` on the response.

### `prompts.py`

- `SYSTEM` — the maintenance-engineer persona, the reasoning contract (weigh SOP, history, schedule, sparepart ETA, technician availability), the citation requirement, and the **output JSON shape spelled out explicitly with field descriptions and a worked example**. With no schema-enforced decoding, the prompt *is* the schema; this is where the effort goes.
- `build_user_turn(bundle, signals)` — the volatile part: asset facts, computed anomalies/score, retrieved chunks, business constraints, operator report.

### `analysis.py`

```python
def analyze(bundle, signals, client) -> AnalysisResult
```

`client.chat.completions.create(model=MODEL, response_format={"type": "json_object"}, messages=[...])`, then `AnalysisResult.model_validate_json(...)`. On `ValidationError`, retry **once** with the assistant's bad output and the pydantic error appended as a user turn — models fix their own shape errors reliably when shown the error. Second failure raises a typed `AnalysisError` the backend can turn into a 502.

After a successful parse, `health_score` and `anomalies` are overwritten from `signals.py` — the LLM never gets to fudge the numbers — and `sources` is filled from the bundle, not the model, so the audit trail can't be hallucinated.

Streaming is available but not needed for the JSON call; use non-streaming and set a generous client timeout.

### `engine.py`

```python
class MaintenanceEngine:
    def __init__(self, client=None, budget_tokens=40_000): ...
    def analyze(self, request: AnalysisRequest) -> AnalysisResult: ...
    def ask(self, request: AnalysisRequest, question: str) -> str: ...   # Starter Q&A, plain text
```

Four lines of orchestration: signals → context → analysis → override. This is the entire surface the backend touches; everything else is internal.

## Phases

1. **Contract + signals.** `config.py`, `schemas.py`, `signals.py`, `test_signals.py`. Backend can start against the schemas immediately — this unblocks the other two engineers on day one.
2. **Retrieval + the DeepSeek call.** `embed.py`, `knowledge.py`, `context.py`, `prompts.py`, `analysis.py`, `engine.py`. Ships Starter + Standard end-to-end (Q&A, recommendation, RCA, priority, work order, report, anomaly detection, health score). Retrieval is in this phase, not deferred — the 64K window requires it.
3. **Professional depth + eval.** Sharpen constraint reasoning (schedule conflict, sparepart ETA, technician availability → `recommended_window` and `blockers`); build `eval/cases.yaml` + `run_eval.py`. Decide `deepseek-reasoner` escalation here, on eval numbers rather than intuition.

**Explicitly skipped:** Continuous Learning (secondary in the spec — with rule-based scoring there is no model to retrain; the honest version is feeding closed work orders back as `history`, which the contract already supports). Notification and Dashboard are backend/frontend concerns.

## Verification

- `pytest ai-engine/tests` — `test_signals.py` asserts a planted spike is flagged and a clean series is not, and that health score falls monotonically as anomalies worsen. `test_engine.py` injects a stub analyzer so wiring is checked without an API call.
- `python -m aiengine.demo` — runs one fixture machine (bearing temperature drifting up, SOP saying replace at 85°C, sparepart 5 days out, production run ending Saturday) end-to-end against the real API and prints the result plus `usage`. If constraint reasoning works, the recommendation defers to Saturday and names the ETA as a blocker. Run it twice: the second run should show a non-zero `prompt_cache_hit_tokens`, which confirms the prefix is stable.
- `python eval/run_eval.py` — Phase 3; scores priority accuracy, root-cause hit rate, **and JSON-validation retry rate** across the labelled cases. That last number is the one that tells you whether the prompt's output contract is holding.
