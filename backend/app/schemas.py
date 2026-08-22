from datetime import datetime
from typing import Any
from pydantic import BaseModel, ConfigDict, Field

class AssetIn(BaseModel):
    name: str = Field(min_length=1)
    asset_type: str = "machine"
    criticality: str = "medium"
    location: str | None = None
    specs_json: dict[str, Any] = {}
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
    performed_at: datetime; action: str; findings: str = ""; parts_used: list[str] = []
class AnalysisIn(BaseModel):
    tier: str = "starter"; trigger: str = "manual"; manual_condition: str | None = None
    include_history: bool = True; include_business_context: bool = True
class WorkOrderUpdate(BaseModel):
    title: str | None = None; description: str | None = None
class ProgressIn(BaseModel):
    percentage: int = Field(ge=0, le=100); note: str = ""
class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str; title: str; kind: str; filename: str; size_bytes: int; ingestion_status: str; ingestion_error: str | None
class AskIn(BaseModel): question: str = Field(min_length=1)
