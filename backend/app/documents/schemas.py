from pydantic import BaseModel, ConfigDict


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str; title: str; kind: str; filename: str; size_bytes: int
    ingestion_status: str; ingestion_error: str | None