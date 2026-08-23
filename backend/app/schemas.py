from datetime import datetime
from typing import Any
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field

class AssetIn(BaseModel):
    name: str = Field(min_length=1)
    asset_type: str = "machine"
    criticality: str = "medium"
    location: str | None = None
    specs_json: dict[str, Any] = {}
    external_id: str | None = None
class AssetOut(AssetIn):
    model_config = ConfigDict(from_attributes=True)
    specs: dict[str, Any] = Field(serialization_alias="specs", validation_alias="specs_json")
    id: str; factory_id: str; status: str
class ReadingIn(BaseModel):
    tag: str; value: float; unit: str = ""; recorded_at: datetime; source: str = "manual"; external_id: str | None = None
class ReadingBatchIn(BaseModel):
    readings: list[ReadingIn] = Field(min_length=1, max_length=5000)
class ConditionIn(BaseModel):
    condition: str = Field(min_length=1)
class BusinessIn(BaseModel):
    production_schedule: str | None = None
    spareparts: list[str] = []
    sparepart_eta: str | None = None
    technicians_available: int | None = Field(default=None, ge=0)
    operator_report: str | None = None
class MaintenanceIn(BaseModel):
    performed_at: datetime; action: str; findings: str = ""; parts_used: list[str] = []; external_id: str | None = None
class AnalysisIn(BaseModel):
    tier: Literal["starter", "standard", "professional"] = "starter"; trigger: str = "manual"; manual_condition: str | None = None
    include_history: bool = True; include_business_context: bool = True
    qc_batch_id: str | None = None
class QCImageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str; filename: str; mime_type: str; size_bytes: int
    defect_class: str | None = None; class_confidence: float | None = None
class QCBatchOut(BaseModel):
    id: str; asset_id: str; factory_id: str; count: int
    defect_count: int; defect_rate: float; images: list[QCImageOut]; created_at: datetime
class WorkOrderUpdate(BaseModel):
    title: str | None = None; description: str | None = None
class RejectIn(BaseModel):
    # A rejection without a reason teaches the next analysis nothing.
    reason: str = Field(min_length=1, max_length=1000)
class ProgressIn(BaseModel):
    percentage: int = Field(ge=0, le=100); note: str = ""
class TechnicianResultIn(BaseModel):
    work_done: str = ""
    findings: str = ""
    parts_used: list[str] = []
    evidence: list[str] = []
class VerificationResultOut(BaseModel):
    verdict: Literal["resolved", "partial", "not_resolved"]
    evidence: list[str] = []
    follow_up: list[str] = []
class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str; title: str; kind: str; filename: str; size_bytes: int; ingestion_status: str; ingestion_error: str | None
class AskIn(BaseModel): question: str = Field(min_length=1)
