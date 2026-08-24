from typing import Literal
from pydantic import BaseModel, Field


class AnalysisIn(BaseModel):
    tier: Literal["starter", "standard", "professional"] = "starter"
    trigger: str = "manual"
    manual_condition: str | None = None
    include_history: bool = True
    include_business_context: bool = True
    qc_batch_id: str | None = None


class AskIn(BaseModel):
    question: str = Field(min_length=1)