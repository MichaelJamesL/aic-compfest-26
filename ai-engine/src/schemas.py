"""The contract between ai-engine and the FastAPI backend.

Optional-everything is deliberate: the tier does not gate logic. The engine
reasons over whatever fields are populated, and the backend decides what to
populate per tier. This file is the whole interface — write it first and agree
on it before either side builds.
"""
from __future__ import annotations

from datetime import datetime, time
from enum import StrEnum
from typing import Dict, Literal, Optional

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
    kind: Literal["sop", "manual", "log", "qc_standard", "maintenance_history"] = "sop"
    text: str
    factory_id: str | None = None

class DayOfWeek(StrEnum):
    MONDAY = "monday"
    TUESDAY = "tuesday"
    WEDNESDAY = "wednesday"
    THURSDAY = "thursday"
    FRIDAY = "friday"
    SATURDAY = "saturday"
    SUNDAY = "sunday"

class TimeInterval(BaseModel):
    start: time
    end: time

class TechnicianSchedule(BaseModel):
    name: str
    role: str
    specialty: str | None = None
    work_time: Dict[DayOfWeek, TimeInterval] = Field(default_factory=dict)
    occupied_time: Dict[DayOfWeek, list[TimeInterval]] = Field(default_factory=dict)

class ProductionSchedule(BaseModel):
    work_time: Dict[DayOfWeek, TimeInterval] = Field(default_factory=dict)

class SparePart(BaseModel):
    id: str
    name: str
    stock: int = 0
    unit: str = "pcs"
    min_stock: int | None = None
    eta: str | None = None


class QCBatch(BaseModel):
    phase: str
    asset_id: str
    product: str
    images: list[str] = Field(default_factory=list)


class PhaseQC(BaseModel):
    phase: str
    asset_id: str
    product: str
    inspected: int
    defects: int
    defect_rate: float
    findings: list[DefectFinding] = Field(default_factory=list)


class BusinessContext(BaseModel):
    production_schedule: ProductionSchedule = Field(default_factory=ProductionSchedule)
    inventory: list[SparePart] = Field(
        default_factory=list,
        description="Available spare parts for this asset (snapshot from backend, not full warehouse inventory).",
    )
    technicians: list[TechnicianSchedule] = Field(default_factory=list)
    operator_report: str | None = None


class FailureModeLink(BaseModel):
    """What a defect class implies about the machine, and whether sensors agree."""

    defect_class: str
    images: int = 1
    failure_modes: list[str] = Field(default_factory=list)
    #: tags whose rule in the table actually held. Empty means proposed only.
    corroborated_by: list[str] = Field(default_factory=list)
    #: 0 unless a signal corroborated — the table's own restraint rule.
    priority_delta: int = 0
    recommended_action: str = ""
    source: str = ""


class DefectFinding(BaseModel):
    image: str
    subject: Literal["asset", "product"] = "asset"
    score: float
    threshold: float
    label: Literal["ok", "defect"]
    severity: Literal["low", "medium", "high", "critical"] = "low"
    region: tuple[int, int, int, int] | None = None
    heatmap_path: str | None = None
    method: str = "patchcore"
    phase: str | None = None
    #: from the fine-tuned classifier, when one is available
    defect_class: str | None = None
    class_confidence: float | None = None


class AnalysisRequest(BaseModel):
    tier: Tier
    asset: Asset
    factory_id: str | None = None
    readings: list[SensorReading] = Field(default_factory=list)
    images: list[str] = Field(default_factory=list)
    qc_batches: list[QCBatch] = Field(default_factory=list)
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


class TechnicianResult(BaseModel):
    """Evidence submitted by the technician after executing a work order."""

    work_done: str = ""
    findings: str = ""
    parts_used: list[str] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)


class VerificationResult(BaseModel):
    verdict: Literal["resolved", "partial", "not_resolved"]
    evidence: list[str] = Field(default_factory=list)
    follow_up: list[str] = Field(default_factory=list)


class AnalysisResult(BaseModel):
    health_score: int  # 0-100, from signals.py, not the LLM
    health_summary: str
    anomalies: list[Anomaly]
    defects: list[DefectFinding] = Field(default_factory=list)
    qc_by_phase: list[PhaseQC] = Field(default_factory=list)
    failure_modes: list[FailureModeLink] = Field(default_factory=list)
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
    similarity: float | None = None


class ContextBundle(BaseModel):
    assets_facts: str
    anomalies: list[Anomaly]
    defects: list[DefectFinding] = Field(default_factory=list)
    qc_by_phase: list[PhaseQC] = Field(default_factory=list)
    failure_modes: list[FailureModeLink] = Field(default_factory=list)
    health_score: int
    corpus: list[ContextDoc]
    history: list[MaintenanceRecord]
    business: BusinessContext
    manual_condition: str | None = None

    @property
    def all_findings(self) -> list[DefectFinding]:
        """Asset-level inspection plus every QC phase.

        Images uploaded as a QC batch land in `qc_by_phase`, not in `defects`.
        Reading `defects` alone told the prompt no images were inspected while a
        batch of eight sat in the bundle, and left the health score untouched by
        a 100% defect rate.
        """
        return [*self.defects, *(f for phase in self.qc_by_phase for f in phase.findings)]

    @property
    def defect_rate(self) -> float:
        findings = self.all_findings
        if not findings:
            return 0.0
        defective = sum(1 for d in findings if d.label == "defect")
        return defective / len(findings)

    @property
    def source_names(self) -> list[str]:
        titles = [f"{d.title}#{d.chunk_id}" for d in self.corpus]
        return titles
