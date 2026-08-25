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
    operator_report: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)


class BusinessContext(Base):
    """One row per factory: shifts, roster and warehouse are plant-wide, not per machine.
    The per-machine operator report lives on Asset."""
    __tablename__ = "business_contexts"
    factory_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    production_schedule: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    technicians_json: Mapped[list] = mapped_column(JSON, default=list)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)

class SparePart(Base):
    """Factory warehouse stock. `code` is the client-facing id (a slug), unique per factory."""
    __tablename__ = "spare_parts"
    __table_args__ = (UniqueConstraint("factory_id", "code", name="uq_spare_part_code"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    factory_id: Mapped[str] = mapped_column(String(36), index=True)
    code: Mapped[str] = mapped_column(String(200))
    name: Mapped[str] = mapped_column(String(200))
    stock: Mapped[int] = mapped_column(Integer, default=0)
    unit: Mapped[str] = mapped_column(String(50), default="pcs")
    min_stock: Mapped[int | None] = mapped_column(Integer, nullable=True)
    eta: Mapped[str | None] = mapped_column(String(200), nullable=True)


class AssetSparePart(Base):
    """Which parts fit which machine. A part fits many machines, a machine takes many parts."""
    __tablename__ = "asset_spare_parts"
    asset_id: Mapped[str] = mapped_column(ForeignKey("assets.id"), primary_key=True)
    spare_part_id: Mapped[str] = mapped_column(ForeignKey("spare_parts.id"), primary_key=True)
