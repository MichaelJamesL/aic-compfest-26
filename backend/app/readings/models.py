from datetime import datetime, timezone
from uuid import uuid4
from sqlalchemy import DateTime, Float, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from ..db import Base

def now(): return datetime.now(timezone.utc)
def uid(): return str(uuid4())


class Reading(Base):
    __tablename__ = "sensor_readings"
    __table_args__ = (UniqueConstraint("factory_id", "asset_id", "external_id", name="uq_reading_external_id"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    factory_id: Mapped[str] = mapped_column(String(36), index=True)
    asset_id: Mapped[str] = mapped_column(ForeignKey("assets.id"), index=True)
    tag: Mapped[str] = mapped_column(String(100), index=True)
    value: Mapped[float] = mapped_column(Float)
    unit: Mapped[str] = mapped_column(String(30), default="")
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    source: Mapped[str] = mapped_column(String(30), default="manual")
    external_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    quality: Mapped[str] = mapped_column(String(30), default="good")