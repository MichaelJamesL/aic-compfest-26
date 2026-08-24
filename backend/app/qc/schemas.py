from datetime import datetime
from pydantic import BaseModel, ConfigDict


class QCImageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str; filename: str; mime_type: str; size_bytes: int
    defect_class: str | None = None; class_confidence: float | None = None


class QCBatchOut(BaseModel):
    id: str; asset_id: str; factory_id: str; phase: str; product: str; count: int
    defect_count: int; defect_rate: float; images: list[QCImageOut]; created_at: datetime


class ModelFitOut(BaseModel):
    asset_id: str; product: str; bank_path: str; images_used: int