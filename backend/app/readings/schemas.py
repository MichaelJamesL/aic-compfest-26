from datetime import datetime
from pydantic import BaseModel, Field


class ReadingIn(BaseModel):
    tag: str; value: float; unit: str = ""; recorded_at: datetime; source: str = "manual"; external_id: str | None = None


class ReadingBatchIn(BaseModel):
    readings: list[ReadingIn] = Field(min_length=1, max_length=5000)