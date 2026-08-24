from datetime import datetime, timezone
from uuid import uuid4
from sqlalchemy import DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from ..db import Base

def now(): return datetime.now(timezone.utc)
def uid(): return str(uuid4())


class QCBatch(Base):
    __tablename__ = "qc_batches"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    factory_id: Mapped[str] = mapped_column(String(36), index=True)
    asset_id: Mapped[str] = mapped_column(ForeignKey("assets.id"), index=True)
    phase: Mapped[str] = mapped_column(String(100), default="inspection")
    product: Mapped[str] = mapped_column(String(200), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class QCImage(Base):
    __tablename__ = "qc_images"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    factory_id: Mapped[str] = mapped_column(String(36), index=True)
    batch_id: Mapped[str] = mapped_column(ForeignKey("qc_batches.id"), index=True)
    asset_id: Mapped[str] = mapped_column(ForeignKey("assets.id"), index=True)
    filename: Mapped[str] = mapped_column(String(255))
    mime_type: Mapped[str] = mapped_column(String(100))
    size_bytes: Mapped[int] = mapped_column(Integer)
    storage_key: Mapped[str] = mapped_column(String(500))
    defect_class: Mapped[str | None] = mapped_column(String(100), nullable=True)
    class_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)