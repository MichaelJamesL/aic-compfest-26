# ai-engine

Predictive-maintenance AI pipeline for AIC Compfest. The package the FastAPI
backend imports to turn raw sensor data and camera images into a typed
maintenance analysis: health score, anomalies, visual defects, root causes,
recommendation, priority, recommended window, blockers, and a draft work order.

Reasoning is handled by **DeepSeek** (OpenAI-compatible endpoint); the knowledge
base lives in **Postgres/pgvector**; anomaly detection, health scoring, and
visual defect detection are **deterministic rules** (IQR fence + weighted
deductions + PatchCore visual anomaly detection), not a trained model.

## Layout

```
ai-engine/
  pyproject.toml            # package "src"; deps: pydantic-ai, pydantic, numpy,
                            # fastembed, psycopg[binary], pgvector, tiktoken
  src/
    __init__.py             # exports MaintenanceEngine, schemas
    config.py               # env: DEEPSEEK_API_KEY, DATABASE_URL, model id, budgets
    schemas.py              # the contract with backend — pydantic models
    embed.py                # fastembed wrapper: embed(texts) -> vectors
    knowledge.py            # pgvector ingest + similarity search
    context.py              # select_context(): retrieve + token-budget the prompt corpus
    signals.py              # anomaly detection + health scoring (pure, no LLM)
    vision.py               # PatchCore visual anomaly detection (pure, no LLM)
    prompts.py              # system prompt + task templates
    engine.py               # MaintenanceEngine facade (pydantic_ai agents)
    demo.py                 # end-to-end demo fixture
  tests/                    # test_signals.py, test_engine.py, test_vision.py
  eval/                     # cases.yaml + run_eval.py
```

Backend installs it with `uv add ../ai-engine` (path dep) and imports. Backend verification can also run without the AI package in offline mode; this is a deterministic stub, not a fallback claim about DeepSeek availability:

```python
from src import MaintenanceEngine
```

## Usage

```python
from src import MaintenanceEngine, AnalysisRequest, Asset, Tier

engine = MaintenanceEngine()  # needs DEEPSEEK_API_KEY
result = engine.analyze(AnalysisRequest(
    tier=Tier.PROFESSIONAL,
    asset=Asset(id="pump-01", name="Cooling water pump 1", type="pump"),
    readings=[...],   # list[SensorReading]
    images=[...],     # list[str] — paths to camera images (optional)
    history=[...],    # list[MaintenanceRecord]
    business=...,     # BusinessContext
))
# result.health_score, result.anomalies, result.defects, result.recommendation,
# result.priority, result.work_order, result.sources, ...
```

Two entry points on the facade:

- `analyze(request) -> AnalysisResult` — full structured analysis (Starter /
  Standard / Professional).
- `ask(request, question) -> str` — plain-text Q&A grounded in the retrieved
  corpus (Starter tier).

## Setup

Requires Python ≥ 3.11 and [uv](https://docs.astral.sh/uv/).

```bash
cd ai-engine
uv sync --extra dev          # base install (no vision)
uv sync --extra dev --extra vision  # with PatchCore visual QC
```

Set these env vars (or put them in a `.env` loaded by the backend):

```
DEEPSEEK_API_KEY=sk-...
DATABASE_URL=postgresql://postgres:postgres@localhost:5433/aic26
```

Optional tuning: `AIENGINE_MODEL` (default `deepseek-chat`),
`AIENGINE_CONTEXT_BUDGET` (default `40000` tokens), `AIENGINE_TIMEOUT`.

## Knowledge base

Documents are embedded with `intfloat/multilingual-e5-large` (1024-dim,
handles Indonesian and English, runs on CPU, no key) and stored in pgvector. Ingest from the backend's upload
endpoint:

```python
from src import knowledge, Document

knowledge.init_schema()
knowledge.ingest(Document(id="sop-1", title="Bearing Replacement SOP", kind="sop", text="..."), asset_id="pump-01")
```

Retrieval is automatic: `analyze` builds a retrieval query from the asset and
operator report, searches pgvector, packs the top chunks into the 64K prompt
budget, and lists everything actually used in `result.sources`.

## Visual QC (optional)

When `AnalysisRequest.images` is non-empty, the engine runs **PatchCore**
unsupervised visual anomaly detection (via [anomalib](https://github.com/openvinotoolkit/anomalib))
on each image before calling the LLM. The result is a typed `DefectFinding`
per image — score, threshold, severity, region — which flows into the health
score and the prompt exactly like sensor anomalies. Defects are deterministic,
not hallucinated.

Install with `--extra vision` (adds ~3GB for torch + anomalib). Configure
through env vars: `AIENGINE_BANK_DIR`, `AIENGINE_DEFECT_THRESHOLD`,
`AIENGINE_PATCHCORE_BACKBONE`.

## Design notes

- **Optional-everything request.** The tier doesn't gate logic — the engine
  reasons over whatever fields are populated, and the backend decides what to
  send per tier. Starter sends a `manual_condition`; Professional sends readings
  plus a full `BusinessContext`.
- **Numbers are deterministic, not the LLM's.** `health_score`, `anomalies`, and
  `defects` come from `signals.py` (IQR fence + weighted deductions) and
  `vision.py` (PatchCore). The model *explains* the score; it can't invent it.
  `tier`, `model`, and `sources` are also set by the engine, so the audit trail
  can't be hallucinated.
- **Validate + retry is the framework's job.** The DeepSeek call runs through a
  pydantic_ai `Agent` with `output_type=AnalysisResult` and `retries=1`; the
  framework validates the structured output and re-prompts on failure. The
  hand-rolled parse/retry loop is gone.
- **No embedding API from DeepSeek/Anthropic** — hence the local `fastembed`
  embedder, which keeps retrieval working offline.

## Tests & eval

```bash
uv run pytest                 # unit tests, no API/DB/vision needed
uv run python -m src.demo     # end-to-end against the real API + local Postgres
uv run python eval/run_eval.py  # scores priority/root-cause/retry across cases.yaml
```

The demo fixture is a bearing drifting up to 90°C with an 85°C SOP threshold and
a spare part 5 days out. It also generates synthetic camera plates, fits
PatchCore on nominal images, and inspects a scratched plate — so defects appear
in the result alongside the bearing anomaly. Run it twice — the second run
should show a non-zero `cache_read_tokens`, confirming the prompt prefix is
stable for DeepSeek's context cache.

## Escalating to deepseek-reasoner

For the hardest Professional-tier scheduling/constraint calls, switch the model
in one place (`src/config.py`, `MODEL`). Decide based on the Phase 3 eval
numbers, not intuition.
