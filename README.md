# SIENA

SIENA is a synchronous predictive-maintenance system for small and mid-size
factories. It combines machine readings, operator reports, SOPs, maintenance
history, QC inputs, production context, spare parts, and technician context into
an evidence-grounded maintenance decision.

The end-to-end flow is:

```text
setup data -> analyze asset -> review recommendation -> approve work order
-> technician execution -> AI verification -> maintenance report
```

The repository contains three components:

| Component | Responsibility | Technology |
| --- | --- | --- |
| `frontend/` | Setup, analysis, reports, work orders, and technician flow | React, TypeScript, Vite, Tailwind v4 |
| `backend/` | HTTP API, persistence, workflow, audit trail, and integrations | FastAPI, SQLAlchemy, PostgreSQL/SQLite |
| `ai-engine/` | Signals, retrieval, prompts, structured reasoning, and verification | Python, pydantic_ai, DeepSeek, pgvector |

The backend imports `ai-engine` in the same Python process. There is no separate
AI HTTP service. Docker Compose runs the complete stack: frontend, backend,
PostgreSQL with pgvector, and the AI engine.

## Key Capabilities

- Import assets from CSV or JSON.
- Upload SOPs, manuals, maintenance history, and QC standards.
- Import sensor readings from CSV or batch JSON API requests.
- Enter production schedule, spare parts, technician availability, and operator reports.
- Detect sensor anomalies with IQR fences or an available per-asset baseline.
- Calculate a deterministic machine health score from 0 to 100.
- Retrieve relevant SOP and history chunks with local embeddings and pgvector.
- Use DeepSeek for grounded root-cause analysis, explanation, recommendation, and work-order drafting.
- Upload QC image batches; the visual classifier integration is still being completed.
- Submit recommendations for coordinator approval.
- Record technician execution and synchronously verify the result.
- Generate post-maintenance reports and export work orders/reports as CSV or JSON.
- Run with complete Docker Compose deployment.

## Quick Start

The recommended path is Docker Compose. See the complete guide in
[`docs/SETUP.md`](docs/SETUP.md).

```bash
cp .env.example .env
docker compose up --build -d
```

Open `http://localhost:5173`.

Verify the services:

```bash
curl http://localhost:8000/health/ready
curl http://localhost:8000/config/capabilities
docker compose ps
```

For real DeepSeek reasoning, edit the root `.env` before starting Compose:

```env
AI_ENGINE_ENABLED=true
DEEPSEEK_API_KEY=your_deepseek_api_key
```

The root `.env` is used by Docker Compose. `backend/.env` is only for local
SQLite development and is not read by Compose.

## Guided Tour

For a first run, follow this order:

1. Read this README for the product, architecture, and MVP boundary.
2. Follow [`docs/SETUP.md`](docs/SETUP.md) to configure and start the stack.
3. Load the demo scenario using the commands in the next section.
4. Open the frontend and follow the operational flow below.
5. Read [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for implementation boundaries and data flow.
6. Read [`docs/API.md`](docs/API.md) when changing or integrating an endpoint.
7. Read [`docs/STATUS.md`](docs/STATUS.md) before claiming or extending a feature.

The recommended demonstration flow is:

```text
Setup
  -> register or import assets, documents, history, and business context
Analyze
  -> select an asset, add sensor data or operator condition, and run analysis
Review
  -> inspect health score, anomalies, root causes, recommendation, and sources
Coordinate
  -> create a work order and approve or reject it
Execute
  -> technician submits performed work, findings, parts, and evidence
Verify
  -> AI verifies the result and produces the final maintenance report
```

The system supports analysis with partial input. For a deeper result, provide
sensor readings, relevant documents, maintenance history, business context, and
QC images where the visual pipeline is available. The UI shows which inputs were
available and which were missing for each analysis.

## Demo Data

The repository includes a complete factory scenario in [`demo-data/`](demo-data/):
8 machines, sensor exports, 35 maintenance records, business context, and
technical documents. With the stack running, load it through the same API paths
used by the application:

```bash
python3 demo-data/seed.py --api http://localhost:8000
```

To also reindex documents into the AI knowledge base:

```bash
python3 demo-data/seed.py --api http://localhost:8000 --reindex
```

Read [`demo-data/README.md`](demo-data/README.md) for data sources, machine
scenarios, idempotency behavior, and regeneration instructions.

## Environment and Databases

Compose uses two logical PostgreSQL databases:

- `app`: assets, readings, documents, business context, analyses, work orders, and audit events.
- `ai`: the pgvector `doc_chunk` knowledge base used by retrieval.

They must remain separate. The root `.env` controls the Compose credentials and
internal service URLs. Uploaded files and model artefacts are persisted in named
Docker volumes.

## MVP Boundary

The MVP is intentionally synchronous and focuses on core inference. It does not
include background jobs, schedulers, automatic feedback loops, auto-tuning,
continuous learning, real-time sensor streaming, notifications, advanced
multi-machine dashboards, direct ERP/CMMS integration, or production
authentication. PLC/IoT adapters are mock/import paths for the demonstration.

Health score and sensor anomaly detection are deterministic. DeepSeek explains
those signals and produces structured recommendations; it does not define the
audit-critical numbers. Coordinator approval and technician verification remain
human-controlled.

## Documentation Map

| Document | Purpose |
| --- | --- |
| [`docs/SETUP.md`](docs/SETUP.md) | Complete Docker, AI, demo-data, local development, and troubleshooting guide |
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | System boundaries, data flow, and invariants |
| [`docs/API.md`](docs/API.md) | Verified frontend-backend HTTP contract |
| [`docs/STATUS.md`](docs/STATUS.md) | Implementation status and known gaps per requirement |
| [`docs/FR.md`](docs/FR.md) | Functional requirements and scope |
| [`docs/design/SCREENS.md`](docs/design/SCREENS.md) | Screen behavior and UI states |
| [`docs/design/VISUAL_LANGUAGE.md`](docs/design/VISUAL_LANGUAGE.md) | Frontend visual system and constraints |
| [`demo-data/README.md`](demo-data/README.md) | Demo dataset and seed workflow |
| [`Metodologi-SIENA.docx`](Metodologi-SIENA.docx) | Proposal methodology and technical implementation narrative |

## Checks

```bash
cd ai-engine && uv run pytest
cd backend && uv run pytest
cd frontend && npm run test && npm run build
docker compose config -q
```
