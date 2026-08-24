from datetime import datetime
from pydantic import BaseModel


class MaintenanceIn(BaseModel):
    performed_at: datetime; action: str; findings: str = ""; parts_used: list[str] = []; external_id: str | None = None