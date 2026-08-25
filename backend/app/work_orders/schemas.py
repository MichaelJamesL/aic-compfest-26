from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field, model_validator


class WorkOrderUpdate(BaseModel):
    title: str | None = None; description: str | None = None


class RejectIn(BaseModel):
    reason: str = Field(min_length=1, max_length=1000)


class ProgressIn(BaseModel):
    percentage: int = Field(ge=0, le=100); note: str = ""


class ScheduleIn(BaseModel):
    """A coordinator's correction to who does the job and when."""
    technician: str = Field(min_length=1, max_length=200)
    start: datetime
    end: datetime

    @model_validator(mode="after")
    def _ordered(self):
        if self.end <= self.start:
            raise ValueError("end must be after start")
        return self


class TechnicianResultIn(BaseModel):
    work_done: str = ""
    findings: str = ""
    parts_used: list[str] = []
    evidence: list[str] = []


class VerificationResultOut(BaseModel):
    verdict: Literal["resolved", "partial", "not_resolved"]
    evidence: list[str] = []
    follow_up: list[str] = []