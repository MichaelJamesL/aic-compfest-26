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
    #: how many reference images the fitted model itself calls anomalous. Near
    #: zero on a clean set; high means the references were not all good units.
    flagged_in_training: int = 0