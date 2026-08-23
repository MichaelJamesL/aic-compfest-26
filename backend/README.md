# AIC Backend Starter

FastAPI + SQLAlchemy 2 synchronous MVP. SQLite is the default for local use and
tests; set `DATABASE_URL` to a PostgreSQL URL for deployment. The API uses a
deterministic demo identity: `X-Demo-User` and `X-Factory-ID` headers. This is
demo scoping only, not production authentication.

```bash
cd backend
python -m venv .venv && . .venv/bin/activate
pip install -e '.[dev]'
uvicorn app.main:app --reload
```

The offline engine is enabled by default and never uses the network. Install
the optional local `ai-engine` path dependency and set `AI_ENGINE_ENABLED=true`
to use `MaintenanceEngine`. When that flag is true, a missing or broken AI
engine is reported as an unavailable analysis, not silently replaced by the
stub. Main flow: create asset, post condition or readings, run analysis, create
draft work order, then transition it through approval and execution. Documents
retain original files and ingestion status.

## Docker deployment

From a clean clone, copy the root `.env.example` to `.env`, replace the example
credentials and `DEEPSEEK_API_KEY` as appropriate, then run:

```bash
docker compose up --build
```

Open `http://localhost:5173` (the API is also available at `:8000`). Compose starts one pgvector container with
separate `app` and `ai` databases, initializes the AI vector schema safely on a
new volume, waits for database and backend readiness checks, and persists
uploads and database data in named volumes. The default
`AI_ENGINE_ENABLED=false` is offline mode and uses the deterministic stub
without an API key; set it to `true` only with a valid `DEEPSEEK_API_KEY`.

This is an MVP deployment: demo headers are not production authentication,
there are no migrations or production TLS/secret management. The real AI path
also requires network access to DeepSeek and local embedding model downloads.
