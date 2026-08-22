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
to use `MaintenanceEngine`; unavailable imports or database dependencies fall
back safely to the offline stub. Main flow: create asset, post condition
or readings, run analysis, create draft work order, then transition it through
approval and execution. Documents retain original files and ingestion status.
