from datetime import datetime
from typing import Any
from pydantic import BaseModel, ConfigDict, Field


class SparePartIn(BaseModel):
    id: str
    name: str
    stock: int = 0
    unit: str = "pcs"
    min_stock: int | None = None
    eta: str | None = None


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


class BusinessIn(BaseModel):
    production_schedule: str | None = None
    inventory: list[SparePartIn] = []
    technicians_available: int | None = Field(default=None, ge=0)
    operator_report: str | None = None