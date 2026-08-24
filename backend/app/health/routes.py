import tempfile
from fastapi import Depends
from fastapi.responses import JSONResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from ..assets.models import Factory
from ..config import get_settings
from ..db import get_db


def register_routes(app):
    @app.get("/health/live")
    def live():
        """Liveness probe — always returns 200."""
        return {"status": "ok"}

    @app.get("/health/ready")
    def ready(db: Session = Depends(get_db)):
        """Readiness probe — checks database and storage."""
        database = "ok"
        storage = "ok"
        try:
            db.execute(select(func.count()).select_from(Factory))
        except Exception:
            database = "error"
        try:
            storage_path = get_settings().storage_path
            storage_path.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(dir=storage_path, prefix=".ready-", delete=True) as probe:
                probe.write(b"ready")
                probe.flush()
        except Exception:
            storage = "error"
        if database != "ok" or storage != "ok":
            return JSONResponse(status_code=503, content={"status": "not_ready", "database": database, "storage": storage})
        return {"status": "ready", "database": database, "storage": storage}

    @app.get("/config/capabilities")
    def capabilities():
        """Return deployment tier and enabled feature flags."""
        s = get_settings()
        return {
            "tier": s.deployment_tier,
            "capabilities": {
                "assets": True,
                "documents": True,
                "analysis": True,
                "work_orders": True,
                "mock_plc": True,
                "ai_engine": s.ai_engine_enabled,
            },
        }