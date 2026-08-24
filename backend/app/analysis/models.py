from datetime import datetime, timezone
from uuid import uuid4
from sqlalchemy import DateTime, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from ..db import Base

def now(): return datetime.now(timezone.utc)
def uid(): return str(uuid4())


class AnalysisRun(Base):
    __tablename__ = "analysis_runs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    factory_id: Mapped[str] = mapped_column(String(36), index=True)
    asset_id: Mapped[str] = mapped_column(String(36), index=True)
    tier: Mapped[str] = mapped_column(String(30))
    trigger: Mapped[str] = mapped_column(String(30), default="manual")
    status: Mapped[str] = mapped_column(String(30), default="queued")
    request_snapshot_json: Mapped[dict] = mapped_column(JSON, default=dict)
    result_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    health_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    priority: Mapped[str | None] = mapped_column(String(20), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    engine_mode: Mapped[str | None] = mapped_column(String(30), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    parent_analysis_id: Mapped[str | None] = mapped_column(String(36), nullable=True)