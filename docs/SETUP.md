# Setup Guide

This guide runs the complete SIENA stack with Docker Compose. It also includes
the real DeepSeek path, demo data, local development, and common fixes.

## Requirements

- Docker Desktop with Compose v2.
- A DeepSeek API key for real AI analysis. It is not needed for offline stub mode.
- Python 3 for the optional demo-data seed script.
- Node 20+ and `npm` only for frontend development outside Docker.
- `uv` only for backend or AI-engine development outside Docker.

Check Docker first:

```bash
docker --version
docker compose version
```

## Configuration

Run all commands from the repository root.

Create the Compose environment file:

```bash
cp .env.example .env
```

Edit the root `.env` for real AI:

```env
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_DB=postgres
APP_DATABASE=app
AI_DATABASE=ai

DATABASE_URL=postgresql+psycopg://postgres:postgres@db:5432/app
AIENGINE_DATABASE_URL=postgresql://postgres:postgres@db:5432/ai

APP_ENV=demo
AI_ENGINE_ENABLED=true
AIENGINE_TIMEOUT=120
DEEPSEEK_API_KEY=your_deepseek_api_key
DEPLOYMENT_TIER=starter
```

Use a real secret in `DEEPSEEK_API_KEY`; do not commit `.env`. The root `.env`
is the file read by Compose. `backend/.env` is for local SQLite development and
does not configure the containers.

## Start with Docker Compose

Build and start all services in the background:

```bash
docker compose up --build -d
```

The first build can take longer because it installs Python and Node
dependencies. Compose starts:

1. PostgreSQL with the pgvector extension.
2. The `app` and `ai` databases plus the `doc_chunk` vector table.
3. The backend and its imported AI engine.
4. The frontend.

Check that all services are ready:

```bash
docker compose ps
curl http://localhost:8000/health/ready
curl http://localhost:8000/config/capabilities
```

Expected capability output contains:

```json
{"ai_engine": true}
```

Open the application at `http://localhost:5173`.

Follow logs while testing:

```bash
docker compose logs -f backend
docker compose logs -f web
```

Stop the stack without deleting data:

```bash
docker compose down
```

## Compose Modes

The repository contains `docker-compose.override.yml`, which Compose loads
automatically when running `docker compose ...` from the root. It enables
development mode:

- Vite serves the frontend on port `5173`.
- `frontend/`, `backend/`, and `ai-engine/` are bind-mounted.
- Frontend and backend changes reload without rebuilding every source change.

For the production-style nginx frontend image without the automatic override,
run only the base file explicitly:

```bash
docker compose -f docker-compose.yml up --build -d
```

If you use the base file explicitly, source changes require another build.

## Load the Demo Scenario

With the stack running, seed the included factory data:

```bash
python3 demo-data/seed.py --api http://localhost:8000
```

This loads assets, sensor readings, baselines, maintenance history, business
context, operator conditions, and documents. To upload and reindex the documents
into the pgvector knowledge base:

```bash
python3 demo-data/seed.py --api http://localhost:8000 --reindex
```

The seed script is designed to be re-runnable. Assets, readings, and maintenance
records use external IDs for idempotency. Read [`../demo-data/README.md`](../demo-data/README.md)
for the full scenario and data provenance.

## Real AI versus Offline Stub

Real AI requires all of the following:

- `AI_ENGINE_ENABLED=true` in the root `.env`.
- A valid `DEEPSEEK_API_KEY` in the root `.env`.
- Network access from the backend container to DeepSeek.
- A healthy PostgreSQL/pgvector service for retrieval.

When `AI_ENGINE_ENABLED=false`, the backend uses `StubEngine` in demo/local/test
environments. The stub has the same response shape but does not call DeepSeek.
The API exposes the mode through `/config/capabilities` and each analysis result.

Do not expect the real AI path to be instantaneous. An analysis is synchronous
and can take up to `AIENGINE_TIMEOUT` seconds. There is no polling endpoint or
background job by design.

## Local Backend Development

Docker Compose is the recommended path. For backend-only work, SQLite and the
offline stub avoid the need for PostgreSQL or an API key:

```bash
cd backend
cp .env.example .env
uv sync --extra dev
uv run uvicorn app.main:app --reload --port 8000
```

To run the real local engine in the backend environment, install the local AI
package explicitly because `backend/pyproject.toml` does not define an `ai`
extra:

```bash
cd backend
uv sync --extra dev
uv pip install -e ../ai-engine
```

Then set `AI_ENGINE_ENABLED=true`, `DEEPSEEK_API_KEY`, and a reachable
`AIENGINE_DATABASE_URL` in `backend/.env`. This local path is separate from the
Compose path.

## Local AI Engine Development

```bash
cd ai-engine
uv sync --extra dev
uv run pytest
```

The base AI engine tests do not need a network, API key, or live database. The
optional visual dependency is installed separately:

```bash
uv sync --extra dev --extra vision
```

The visual path requires PatchCore model artefacts and is not required for the
basic sensor-and-document analysis flow.

## Local Frontend Development

Start the backend first on port `8000`, then run:

```bash
cd frontend
npm install
npm run dev
```

The Vite development server runs on `http://localhost:5173` and proxies API
requests to `http://localhost:8000`.

Run frontend checks:

```bash
npm run test
npm run build
npm run lint
```

## Database and Storage

Compose uses named volumes:

- `db_data`: PostgreSQL data.
- `backend_storage`: uploaded files and generated artefacts.
- `model_cache`: local FastEmbed model cache.

The application database and AI knowledge base are separate databases in the
same PostgreSQL container. Do not point `DATABASE_URL` and
`AIENGINE_DATABASE_URL` at the same database.

To reset a development database and delete all local Compose data:

```bash
docker compose down -v
docker compose up --build -d
```

This is destructive. It removes the database, uploaded files, and cached model
volumes. Use it only when the local data can be discarded.

## Troubleshooting

### `db-bootstrap` password authentication failed

The existing `db_data` volume was initialized with credentials different from
the root `.env`. Either restore the original credentials or reset the local
volume:

```bash
docker compose down
docker volume rm aic-compfest-26_db_data
docker compose up --build -d
```

The volume removal deletes local database data.

### The old frontend is still displayed

Check for old containers occupying ports `5173` or `8000`:

```bash
docker ps --format '{{.Names}} {{.Image}} {{.Ports}}'
lsof -nP -iTCP:5173 -sTCP:LISTEN
```

Stop the old project container, then restart the current Compose project:

```bash
docker compose down
docker compose up --build -d
```

Hard-refresh the browser with `Cmd + Shift + R` on macOS.

### `AI_ENGINE_ENABLED` is false

Confirm that the value is in the root `.env`, not only `backend/.env`:

```bash
docker compose config | grep AI_ENGINE_ENABLED
```

The effective value must be `true`. Restart Compose after changing `.env`:

```bash
docker compose up -d --force-recreate backend
```

### Port already allocated

Another process or old container owns port `5433`, `8000`, or `5173`. Identify
it with `lsof`, stop it, and rerun Compose. Do not change only the host port in
`.env`; the internal database URL must continue to use hostname `db` and port
`5432` from the backend container.

### Analysis fails with `AI_ENGINE_UNAVAILABLE`

Check the backend logs and verify the API key, network access, and database:

```bash
docker compose logs --tail=100 backend
curl http://localhost:8000/health/ready
curl http://localhost:8000/config/capabilities
```

### Documents are uploaded but not used by analysis

Upload only marks a document as pending. Reindex it from the UI or use the demo
seed command with `--reindex`. A document must have `ingestion_status=ready`
before it can appear in analysis sources.

## Useful API Headers

The demo uses deterministic tenant-scoping headers, not production authentication:

```text
X-Demo-User: demo-engineer
X-Factory-ID: demo-factory
```

The frontend adds these automatically. See [`API.md`](API.md) for the complete
HTTP contract and error envelope.

## Verification Checklist

```bash
docker compose config -q
docker compose ps
curl http://localhost:8000/health/ready
curl http://localhost:8000/config/capabilities
python3 demo-data/seed.py --api http://localhost:8000
```

For code changes, run the checks for the affected area:

```bash
cd ai-engine && uv run pytest
cd backend && uv run pytest
cd frontend && npm run test && npm run build
```
