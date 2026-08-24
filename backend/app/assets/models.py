from datetime import datetime, timezone
from uuid import uuid4
from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from ..db import Base


def now(): return datetime.now(timezone.utc)
def uid(): return str(uuid4())


class Factory(Base):
    __tablename__ = "factories"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    name: Mapped[str] = mapped_column(String(200))
    deployment_tier: Mapped[str] = mapped_column(String(30), default="starter")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Asset(Base):
    __tablename__ = "assets"
    __table_args__ = (UniqueConstraint("factory_id", "external_id", name="uq_asset_external_id"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    factory_id: Mapped[str] = mapped_column(ForeignKey("factories.id"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    asset_type: Mapped[str] = mapped_column(String(100), default="machine")
    criticality: Mapped[str] = mapped_column(String(20), default="medium")
    status: Mapped[str] = mapped_column(String(30), default="active")
    location: Mapped[str | None] = mapped_column(String(200), nullable=True)
    specs_json: Mapped[dict] = mapped_column(JSON, default=dict)
    external_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)


class BusinessContext(Base):
    __tablename__ = "business_contexts"
    asset_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    factory_id: Mapped[str] = mapped_column(String(36), index=True)
    production_schedule: Mapped[str | None] = mapped_column(Text, nullable=True)
    spareparts_json: Mapped[list] = mapped_column(JSON, default=list)
    sparepart_eta: Mapped[str | None] = mapped_column(String(200), nullable=True)
    technicians_available: Mapped[int | None] = mapped_column(Integer, nullable=True)
    operator_report: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)