# AGENTS.MD

Project guidance for AI coding agents working in this repository.

## Overview

AIC Compfest submission: a **predictive-maintenance system for mid-size
factories**. Sensor/log data from machines is turned into a typed maintenance
analysis — health score, anomalies, root-cause analysis, a maintenance
recommendation, priority, an optimal maintenance window, and a draft work
order — grounded in a knowledge base of SOPs and maintenance history.

The monorepo is split across three roles:

| Area | Owner | What it owns |
| --- | --- | --- |
| `ai-engine/` | AI Engineer | AI pipeline, RAG/knowledge base, prompt engineering, maintenance recommendation, root-cause analysis, AI evaluation |
| `backend/` | Backend Engineer | FastAPI, DB, Docker, file uploads, mock PLC/IoT/ERP integrations |
| `frontend/` | Frontend Engineer | UI/UX, upload flow, input forms, results/report/work-order pages, dashboard |

## High-level architecture

```
                ┌─────────────────────────────────────────────┐
                │                     backend/                 │
                │  FastAPI + Postgres/pgvector + Docker        │
                │  uploads · mock PLC/IoT/ERP · auth           │
                └───────────────┬─────────────────────────────┘
                                │ import (one process, one image)
                                ▼
                ┌─────────────────────────────────────────────┐
                │                     ai-engine/               │
                │  MaintenanceEngine (the only surface)        │
                │  signals → context → pydantic_ai agent       │
                └───┬──────────────────────┬──────────────────┘
                    │                      │
        ┌───────────▼──────────┐  ┌────────▼──────────┐
        │      knowledge.py    │  │      DeepSeek      │
        │  pgvector RAG        │  │  pydantic_ai Agent │
        │  fastembed e5-multi   │  │  structured output │
        └──────────────────────┘  └────────────────────┘
```

- **`ai-engine`** is an importable Python package (`src/`). `backend` imports
  `from src import MaintenanceEngine` — one process, one Dockerfile. The facade
  `MaintenanceEngine` is the entire contract.
- **Reasoning** goes through **DeepSeek** via **pydantic_ai**
  (`OpenAIChatModel` + `DeepSeekProvider`). Structured output and retry are
  owned by the framework (`output_type=AnalysisResult`, `retries=1`).
- **Knowledge base** is **Postgres/pgvector**. Embeddings come from local
  `fastembed` (`intfloat/multilingual-e5-large` — Indonesian + English, CPU, no key, offline).
- **Signals are deterministic, not the LLM's.** Anomaly detection (rolling
  median + IQR) and health scoring (weighted deductions) are pure rules in
  `signals.py`. The model *explains* the score; it can never invent it.
  `tier`, `model`, and `sources` are also set by the engine, so the audit trail
  can't be hallucinated.

## Functional requirements (AIC Compfest)

See **[`docs/FR.md`](docs/FR.md)** — the single source of truth for the
functional requirements, module/feature table, and the Starter/Standard/
Professional deployment packages.

## Onboarding

1. **Install [uv](https://docs.astral.sh/uv/)** (Python package/dependency manager).
2. **Start the DB** (Postgres + pgvector):
   ```bash
   docker compose up -d
   ```
3. **Install the AI engine** and run its tests:
   ```bash
   cd ai-engine
   uv sync --extra dev
   uv run pytest
   ```
4. **Init the knowledge-base schema**:
   ```bash
   uv run python -c "from src import knowledge; knowledge.init_schema()"
   ```
5. **Set env vars** (or a backend `.env`): `DEEPSEEK_API_KEY`,
   `DATABASE_URL` (defaults to `postgresql://postgres:postgres@localhost:5433/aic26`).
6. Validate end-to-end with the demo:
   ```bash
   uv run python -m src.demo
   ```

## How to develop (framework first)

**Rule: do not hand-roll something a framework already provides.** Before
writing low-level code, load and follow the relevant framework skill (see
below). Common patterns:

- **AI agents / structured output / DeepSeek** → use **pydantic_ai**. Prefer
  `Agent(...)` with `output_type=` and `retries=` over manual chat-completions +
  hand-rolled JSON validation. The old manual validate/retry loop in
  `analysis.py` was deleted for exactly this reason.
- **Pydantic models** → the package contract (`src/schemas.py`) *is* pydantic.
  Optional-everything is deliberate; the tier does not branch logic.
- **Observability** → pydantic_ai has first-class Logfire integration
  (`logfire.instrument_pydantic_ai()`). Pass an explicit `name=` to every
  `Agent`.
- **Signals/scoring** → deterministic rules in `signals.py`; keep the LLM out
  of the numbers. Weights live in one `HEALTH_WEIGHTS` dict.
- **Retrieval** → `knowledge.py` (pgvector) + `context.py` (token-budgeted
  `select_context`). Keep the prompt prefix stable for DeepSeek's context cache.
- **Tests** → pytest. Use pydantic_ai's `TestModel`/`FunctionModel` for
  deterministic agent tests without hitting the network or DB.

### Using framework skills

When a task matches an installed skill, **load it first** via the skill tool
and follow its guidance. The relevant skills for this repo:

- **`building-pydantic-ai-agents`** — building AI agents, tools, structured
  output, streaming, testing with `TestModel`/`FunctionModel`. Use whenever you
  touch `pydantic_ai` or `Agent`.
- **`pydantic`** — complex data modeling with Pydantic (constraints, model
  hierarchies).
- **`logfire-instrumentation`** / **`logfire-query`** / **`logfire-ui`** —
  adding, querying, and viewing observability.
- **`ponytail`** — the default engineering posture: the laziest solution that
  actually works, stdlib/native first, delete over add.
- **`building-pydantic-ai-agents` → `references/`** — load the specific
  reference (AGENTS-CORE, TOOLS-CORE, TESTING-AND-DEBUGGING, etc.) for the
  task family.

## Verification

- `cd ai-engine && uv run pytest` — unit tests (no API/DB needed).
- `uv run python -m src.demo` — real end-to-end against DeepSeek + local DB.
- `uv run python eval/run_eval.py` — scores priority accuracy, root-cause hit
  rate, and retry rate across `eval/cases.yaml`.
- `docker compose config` — validates the DB deployment.