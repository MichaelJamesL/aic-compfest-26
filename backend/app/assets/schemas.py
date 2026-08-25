from datetime import datetime, time
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field


class SparePartIn(BaseModel):
    id: str
    name: str
    stock: int = 0
    unit: str = "pcs"
    min_stock: int | None = None
    eta: str | None = None
    #: machines this part fits. Analysis only ever sees the target machine's parts.
    asset_ids: list[str] = []


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


class ConditionIn(BaseModel):
    condition: str = Field(min_length=1)


DayOfWeek = Literal["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]


class TimeIntervalIn(BaseModel):
    start: time
    end: time


class ProductionScheduleIn(BaseModel):
    work_time: dict[DayOfWeek, TimeIntervalIn] = {}


class TechnicianScheduleIn(BaseModel):
    name: str
    role: str
    specialty: str | None = None
    work_time: dict[DayOfWeek, TimeIntervalIn] = {}
    occupied_time: dict[DayOfWeek, list[TimeIntervalIn]] = {}


class BusinessIn(BaseModel):
    """Factory-wide. The per-machine operator report goes to /assets/{id}/condition."""
    production_schedule: ProductionScheduleIn | None = None
    inventory: list[SparePartIn] = []
    technicians: list[TechnicianScheduleIn] = []