"""The contract between ai-engine and the FastAPI backend.

Optional-everything is deliberate: the tier does not gate logic. The engine
reasons over whatever fields are populated, and the backend decides what to
populate per tier. This file is the whole interface — write it first and agree
on it before either side builds.
"""
from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal, Optional

from pydantic import BaseModel, Field


class Tier(StrEnum):
    STARTER = "starter"
    STANDARD = "standard"
    PROFESSIONAL = "professional"


class Asset(BaseModel):
    id: str
    name: str = ""
    type: str = ""  # e.g. "pump", "compressor", "cnc-mill"
    criticality: Literal["low", "medium", "high", "critical"] = "medium"
    install_date: Optional[datetime] = None
    specs: dict = Field(default_factory=dict)  # e.g. {"max_temp_c": 85}


class SensorReading(BaseModel):
    tag: str  # e.g. "bearing_temp_c"
    value: float
    unit: str = ""
    recorded_at: datetime


class MaintenanceRecord(BaseModel):
    asset_id: str
    performed_at: datetime
    action: str = ""
    findings: str = ""
    parts_used: list[str] = Field(default_factory=list)


class Document(BaseModel):
    id: str
    title: str
    kind: Literal["sop", "manual", "log"] = "sop"
    text: str


class BusinessContext(BaseModel):
    production_schedule: str | None = None
    spareparts: list[str] = Field(default_factory=list)
    sparepart_eta: str | None = None  # e.g. "bearing SKF-6204 ETA 5 days"
    technicians_available: int | None = None
    operator_report: str | None = None


class AnalysisRequest(BaseModel):
    tier: Tier
    asset: Asset
    readings: list[SensorReading] = Field(default_factory=list)
    manual_condition: str | None = None
    history: list[MaintenanceRecord] = Field(default_factory=list)
    business: BusinessContext = Field(default_factory=BusinessContext)
    # documents are NOT passed inline — they live in pgvector, retrieved by
    # asset + query.


class Anomaly(BaseModel):
    tag: str
    observed: float
    expected_range: tuple[float, float]
    severity: Literal["low", "medium", "high", "critical"]
    method: str = "iqr"  # how it was detected


class RootCause(BaseModel):
    cause: str
    confidence: float  # 0-1
    evidence: list[str] = Field(default_factory=list)


class WorkOrder(BaseModel):
    title: str
    steps: list[str] = Field(default_factory=list)
    parts: list[str] = Field(default_factory=list)
    est_duration_h: float | None = None
    required_skills: list[str] = Field(default_factory=list)
    safety_notes: list[str] = Field(default_factory=list)


class AnalysisResult(BaseModel):
    health_score: int  # 0-100, from signals.py, not the LLM
    health_summary: str
    anomalies: list[Anomaly]
    root_causes: list[RootCause]
    recommendation: str
    priority: Literal["low", "medium", "high", "critical"]
    recommended_window: str | None = None
    explanation: str  # cites SOP/history/constraints by name
    blockers: list[str] = Field(default_factory=list)
    work_order: WorkOrder | None = None
    tier: Tier | None = None  # filled by the engine, not the model
    model: str | None = None  # filled by the engine, not the model
    sources: list[str] = Field(default_factory=list)  # audit trail


class ContextDoc(BaseModel):
    """A retrieved chunk plus provenance, for the trail and the prompt."""

    title: str
    kind: str
    text: str
    chunk_id: int | None = None
    distance: float | None = None


class ContextBundle(BaseModel):
    assets_facts: str
    anomalies: list[Anomaly]
    health_score: int
    corpus: list[ContextDoc]
    history: list[MaintenanceRecord]
    business: BusinessContext
    manual_condition: str | None = None

    @property
    def source_names(self) -> list[str]:
        titles = [f"{d.title}#{d.chunk_id}" for d in self.corpus]
        return titles