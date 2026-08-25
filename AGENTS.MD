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
                │  signals + vision → context → pydantic_ai    │
                └───┬──────────────────────┬──────────────────┘
                    │                      │
        ┌───────────▼──────────┐  ┌────────▼──────────┐
        │      knowledge.py    │  │      DeepSeek      │
        │  pgvector RAG        │  │  pydantic_ai Agent │
        │  fastembed e5-multi  │  │  structured output │
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
  median + IQR), visual defect detection (PatchCore via anomalib), and health
  scoring (weighted deductions) are pure rules in `signals.py` and `vision.py`.
  The model *explains* the score; it can never invent it.
  `tier`, `model`, and `sources` are also set by the engine, so the audit trail
  can't be hallucinated.

## Documentation

**Start at [`docs/INDEX.md`](docs/INDEX.md).** It maps every document to the
task it answers, and carries the session protocol and the checklist rules. Load
two or three files from there instead of exploring the repo.

The ones you will need most:

| File | For |
| --- | --- |
| [`docs/STATUS.md`](docs/STATUS.md) | Where every requirement actually stands. Read at the start of every session. |
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | Module boundaries, data flow, and the invariants that must survive every refactor. |
| [`docs/API.md`](docs/API.md) | The verified HTTP contract between frontend and backend. |
| [`docs/DEFECTS.md`](docs/DEFECTS.md) | Reproduced bugs. Read before editing `backend/app/main.py` or `ai-engine/src/signals.py`. |
| [`docs/requirements/`](docs/requirements/) | One checklist per area: AI_ENGINE, BACKEND, FRONTEND. |
| [`docs/design/`](docs/design/) | Visual language extracted from the reference, and the screen specs. |
| [`docs/FR.md`](docs/FR.md) | The competition's functional-requirement table — official names and scope. |
| [`docs/FINAL_IDEA.md`](docs/FINAL_IDEA.md) | Single source of truth for the idea. §15 holds fixed wording; use it verbatim in UI copy. |
| [`docs/DECISIONS.md`](docs/DECISIONS.md) | Locked decisions D0–D11 and why. Read before proposing an architecture change. |

Do not read `FINAL_IDEA.md` or `DECISIONS.md` in full for a coding task — the
engineering docs above already carry what code needs.

## Onboarding

**You do not need Postgres or a DeepSeek key to work on `backend/` or
`frontend/`.** The backend defaults to SQLite (auto-created on first boot) and
to `StubEngine`, an offline stand-in with the same output shape. Only
`ai-engine/` work — RAG, prompts, real analysis — needs the database and the key.

### Prerequisites

| Tool | For | Check |
| --- | --- | --- |
| [uv](https://docs.astral.sh/uv/) | `ai-engine/` and `backend/` | `uv --version` |
| Node 20+ | `frontend/` | `node -v` |
| Docker | the pgvector knowledge base | `docker compose config -q` |

uv manages the Python versions and virtualenvs itself — no `python -m venv`, no
`pip`, no global installs.

### 1. Database — pgvector (ai-engine only)

```bash
docker compose up -d db          # Postgres 16 + pgvector on :5433
```

Then create the one table the knowledge base uses (`doc_chunk`, `VECTOR(1024)`
+ HNSW index):

```bash
cd ai-engine && uv run python -c "from src import knowledge; knowledge.init_schema()"
```

The **app** database is a separate store and needs none of this — the backend
calls `Base.metadata.create_all` on startup and seeds `demo-factory`.

### 2. `ai-engine/`

```bash
cd ai-engine
uv sync --extra dev
uv run pytest                    # 19 passed, 1 skipped — no network, no DB
```

For real analysis, export `DEEPSEEK_API_KEY` and run the end-to-end demo
(needs step 1):

```bash
uv run python -m src.demo
```

Optional extras: `--extra vision` (anomalib/PatchCore), `--extra qc` (CPU torch,
pinned to the `pytorch-cpu` index).

### 3. `backend/`

```bash
cd backend
cp .env.example .env             # defaults are the offline-friendly ones
uv sync --extra dev
uv run pytest                    # 14 passed — SQLite in-memory, no DB, no key
uv run uvicorn app.main:app --reload --port 8000
```

Verify it is up:

```bash
curl localhost:8000/health/ready          # {"status":"ready",...}
curl localhost:8000/config/capabilities   # ai_engine:false → the stub is live
```

To switch from the stub to the real engine, install the local link and flip the
flag in `.env`:

```bash
uv sync --extra dev --extra ai   # editable link to ../ai-engine
# .env: AI_ENGINE_ENABLED=true + DEEPSEEK_API_KEY=...
```

### 4. `frontend/`

```bash
cd frontend
npm install
npm run dev                      # :5173, proxies /api /config /health → :8000
npm run test                     # vitest
npm run build                    # tsc -b && vite build
```

`npm run test` and `npm run build` currently fail on a fresh clone —
`src/lib/` is missing from the repo (see Troubleshooting). `npm run lint` and
`npm install` are clean.

The dev server proxies to `localhost:8000`, so start the backend first. Read
[`docs/design/VISUAL_LANGUAGE.md`](docs/design/VISUAL_LANGUAGE.md) before
touching anything visual — its §9 banned-pattern list is not advisory.

### Running the whole stack

Three terminals, in this order:

```bash
docker compose up -d db                              # only if using the real engine
cd backend  && uv run uvicorn app.main:app --port 8000 --reload
cd frontend && npm run dev
```

Then open <http://localhost:5173>.

Or run the whole thing in Docker **with hot reload**, one command:

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build
```

`backend` runs `uvicorn --reload` and `web` runs the vite dev server, both with
the source bind-mounted, so edits on the host reload in the container — for
`ai-engine/src` too, via `PYTHONPATH`. The overlay is deliberately **not** named
`docker-compose.override.yml`, because that loads automatically: plain
`docker compose up` must stay the built production image the judges run.

### Troubleshooting

| Symptom | Cause and fix |
| --- | --- |
| `npm run test` fails: `Failed to resolve import "../lib/cn"` | `frontend/src/lib/` is missing from the repo — six modules (`cn`, `csv`, `format`, `health`, `severity`, `useRequest`) are imported but never committed. The frontend cannot build until they land. |
| `docker compose up -d db` → `port is already allocated` | Something else holds `:5433`. Free it, or change the host port in `docker-compose.yml` **and** `AIENGINE_DATABASE_URL`. |
| `/config/capabilities` shows `ai_engine:false` when you wanted the real engine | `AI_ENGINE_ENABLED` is not `true`, or `uv sync --extra ai` was never run. The backend falls back to the stub instead of failing. |
| Analysis returns `model:"offline-stub"` | Same as above — this is the offline path, working as designed. |
| Engine reads the wrong database | `DATABASE_URL` (app DB) and `AIENGINE_DATABASE_URL` (knowledge base) are **different stores** in one process. Do not point them at each other. |

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
- **Visual defect detection** → `vision.py` using **anomalib** (`anomalib.models.Patchcore`).
  Fit once per asset on nominal images; infer on request. Contained behind
  `[vision]` extra — base install is unchanged.
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

Run the checks for the area you touched.

| Area | Command | Needs |
| --- | --- | --- |
| `ai-engine/` | `cd ai-engine && uv run pytest` | nothing — no API, no DB |
| `ai-engine/` | `uv run python -m src.demo` | `DEEPSEEK_API_KEY` + pgvector |
| `ai-engine/` | `uv run python eval/run_eval.py` | `DEEPSEEK_API_KEY` — scores priority accuracy, root-cause hit rate, retry rate over `eval/cases.yaml` |
| `backend/` | `cd backend && uv run pytest` | nothing — SQLite in-memory + `StubEngine` |
| `frontend/` | `cd frontend && npm run test` | nothing |
| `frontend/` | `npm run build && npm run lint` | nothing |
| deploy | `docker compose config -q` | Docker |
