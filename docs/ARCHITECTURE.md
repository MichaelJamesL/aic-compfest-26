# Architecture

How the code is laid out, what each boundary is for, and the invariants that
must survive every refactor. Read before adding a module or changing the
engine contract.

## Repository layout

```
aic-compfest-26/
├── ai-engine/          Python package `src` — the AI pipeline. Importable, no HTTP.
│   ├── src/            config, schemas, embed, knowledge, context, signals,
│   │                   vision, prompts, engine, demo
│   ├── tests/          pytest, no network and no DB required
│   ├── eval/           cases.yaml + run_eval.py (needs the real API)
│   └── doc/PLAN.md     historical plan; superseded where it disagrees with this file
├── backend/            FastAPI + SQLAlchemy 2, synchronous
│   ├── app/            config, db, models, schemas, auth, errors, repositories,
│   │                   services, adapters, main
│   └── tests/          pytest + TestClient, SQLite in-memory
├── frontend/           Vite + React application, served by nginx in Compose
├── docs/               see docs/INDEX.md
└── docker-compose.yml  Postgres/pgvector, backend, and web services
```

## Process topology

One Python process. The backend **imports** the AI engine; there is no second
service and no RPC between them.

```
browser ──HTTP──▶ backend (FastAPI)  ──import──▶ src.MaintenanceEngine
                      │                                │
                      ▼                                ├──▶ DeepSeek  (pydantic_ai Agent)
              app DB (SQLite dev /                     └──▶ pgvector  (knowledge base)
              Postgres deploy)
```

Two databases are in play and they are **not** the same store:

- **App DB** (`backend/app/models.py`, `DATABASE_URL` in `backend/.env`) — assets,
  readings, documents metadata, business context, analysis runs, work orders,
  audit events. SQLite by default; Postgres for deployment.
- **Knowledge base** (`ai-engine/src/knowledge.py`, `DATABASE_URL` in the
  ai-engine env) — one table, `doc_chunk`, with a 384-dim `VECTOR` column and an
  HNSW index. Postgres + pgvector only.

The engine reads `AIENGINE_DATABASE_URL`; the backend reads `DATABASE_URL`.
They used to share the name and, running in one process, pointed at each
other's store.

## The contract

`ai-engine/src/schemas.py` **is** the interface. The backend touches exactly
three things:

```python
from src import MaintenanceEngine, AnalysisRequest, AnalysisResult
engine.analyze(request) -> AnalysisResult   # full structured analysis
engine.ask(request, question) -> str        # plain-text grounded Q&A
```

Everything else in `src/` is private to the engine. The backend must never
import `signals`, `context`, `prompts`, or `vision` directly — if the backend
needs something from them, it belongs on the facade.

`AnalysisRequest` is **optional-everything** on purpose. The tier never gates
logic; the engine reasons over whatever fields are populated. This is what
implements the *Partial-input analysis* requirement (`FR.md`) and the
"graceful degradation" demo beat — same code path, less input, shallower answer.

## Analysis data flow

```
AnalysisRequest
   │
   ├─ signals.detect_anomalies(readings)      deterministic  (IQR fence per tag)
   ├─ vision.inspect(asset_id, images)        deterministic  (PatchCore, optional extra)
   ├─ signals.health_score(...)               deterministic  (weighted deductions from 100)
   ├─ knowledge.search(query, asset_id, factory_id, k=5)  deterministic  (pgvector cosine)
   └─ context.select_context(...)             packs the above into a ContextBundle
                                              under a token budget, stable ordering
   │
   ▼
prompts.build_user_turn(bundle, tier)  →  pydantic_ai Agent (DeepSeek, output_type=AnalysisResult)
   │
   ▼
engine.analyze() overwrites the model's copy of:
   health_score, anomalies, defects, sources, tier, model
   │
   ▼
AnalysisResult
```

## Invariants — do not break these

1. **The LLM explains numbers; it never produces them.** `health_score`,
   `anomalies`, and `defects` are computed before the model is called and
   **overwritten on the result after** it returns (`engine.py`). Same for the
   audit trail: `sources`, `tier`, `model`. If you add a defensible number
   (scheduling window, defect rate, cost estimate), compute it deterministically
   and overwrite it the same way. This is the project's core claim — see
   `FINAL_IDEA.md` §15 "Angka".
2. **No background work anywhere.** No schedulers, no queues, no async workers,
   no retraining, no auto-tuning, no polling loops. Everything happens inside a
   synchronous request. This is a competition rule, not a preference
   (`DECISIONS.md` D4).
3. **Framework-first.** Structured output and retry belong to `pydantic_ai`
   (`output_type=`, `retries=1`), not to hand-rolled JSON parsing. Settings
   belong to `pydantic-settings`. Validation belongs to pydantic. A hand-rolled
   version of any of these is a regression — one was already deleted once.
4. **The prompt prefix stays stable.** The system prompt is constant and all
   volatile content goes in the user turn, so DeepSeek's context cache hits.
   Do not interpolate timestamps, ids, or counts into `prompts.SYSTEM`.
5. **The engine is importable without a network or a GPU.** `import src` must
   not require `DEEPSEEK_API_KEY`, a live Postgres, or `anomalib`. Vision is
   behind the `[vision]` extra and imported inside functions. Keep it that way —
   the backend's offline stub path depends on it.
6. **Multi-tenancy by `factory_id`.** Every app-DB query filters on
   `identity.factory_id`. `repositories.one_or_404` exists so this is not
   forgotten. A new query that omits it is a bug.

## Determinism boundary — the table to check yourself against

| Output | Produced by | Kind |
| --- | --- | --- |
| `health_score`, `health_summary` | `signals.health_score` | rules |
| `anomalies` | `signals.detect_anomalies` | rules |
| `defects` | `vision.inspect` (PatchCore) — **to be replaced by the fine-tuned classifier**, see `requirements/AI_ENGINE.md` | model, frozen params |
| defect → candidate failure mode | `mapping/qc_failure_modes.yaml` — **not yet built** | knowledge table |
| maintenance window, runner-up, blockers | `decide.py` — **not yet built** | rules |
| `sources`, `tier`, `model` | `engine.analyze` | provenance |
| `root_causes`, `recommendation`, `explanation`, `work_order`, `priority` | DeepSeek via pydantic_ai | LLM, grounded |

`priority` is the one shared field: rules supply a delta (from the mapping
table), the LLM supplies the level and the reason. Everything else is on exactly
one side of the line.

## Backend layering

```
main.py         routes only — parse, delegate, serialize
services.py     use cases: run_analysis, work-order transition, engine factory
repositories.py DB access helpers + audit trail
models.py       SQLAlchemy tables
schemas.py      pydantic request/response models
auth.py         demo identity from X-Demo-User / X-Factory-ID headers
adapters.py     mock PLC / IoT / ERP
errors.py       the single error envelope
config.py       pydantic-settings
```

Business logic in `main.py` is a smell. It once carried a second, divergent
copy of `services.transition` and its `TRANSITIONS` table, so the state machine
the app ran was not the one the tests checked. There is one of each now, in
`services.py`. New logic goes there.

### Engine selection

`services.engine_factory(settings)` returns either the real
`MaintenanceEngine` (when `AI_ENGINE_ENABLED=true`) or `StubEngine`, an offline
stand-in that returns the same shape with `model="offline-stub"`. The stub is
what makes `backend/tests` run with no API key and no Postgres, and what keeps
the app demonstrable if DeepSeek is unreachable during recording. Keep the two
shapes identical; `tests/test_unit.py::test_offline_engine_contract_shape`
guards it.

### Auth

`X-Demo-User` and `X-Factory-ID` headers, mapped to a frozen `Identity`
dataclass. This is deliberately **not** authentication — real auth is on the
roadmap list (`FR.md`) because the rulebook excludes it. It exists so
`factory_id` scoping and the audit trail have an actor.

## Env vars

| Var | Used by | Default | Notes |
| --- | --- | --- | --- |
| `DEEPSEEK_API_KEY` | ai-engine | — | required for real analysis |
| `AIENGINE_MODEL` | ai-engine | `deepseek-chat` | escalation to `deepseek-reasoner` is a one-line change |
| `AIENGINE_CONTEXT_BUDGET` | ai-engine | `40000` | prompt corpus token budget |
| `AIENGINE_TIMEOUT` | ai-engine | `120` | single completion timeout |
| `AIENGINE_BANK_DIR` | ai-engine | `ai-engine/.banks` | PatchCore memory banks |
| `DATABASE_URL` | backend | `sqlite:///./backend.db` | the application database |
| `AIENGINE_DATABASE_URL` | ai-engine | `postgresql://…:5433/aic26` | the pgvector knowledge base; falls back to `DATABASE_URL` when the package runs standalone |
| `APP_ENV` | backend | `local` | offline stub allowed in `local`/`demo`/`test` |
| `AI_ENGINE_ENABLED` | backend | `false` | flip to use the real engine |
| `STORAGE_PATH` | backend | `./storage` | uploaded original files |
| `DEPLOYMENT_TIER` | backend | `starter` | reported by `/config/capabilities`; does not gate engine logic |

## Deployment

`docker-compose.yml` starts Postgres/pgvector, the backend, and the web app.
Copy the root `.env.example` to `.env` before running Compose. Compose requires
explicit database URLs and credentials; `backend/.env.example` remains for
SQLite-based local development and must not be used inside the containers.
The backend image installs both packages and runs as the unprivileged
`appuser` with a writable storage volume.
