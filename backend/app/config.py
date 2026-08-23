from functools import lru_cache
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    app_env: str = "local"
    database_url: str = "sqlite:///./backend.db"
    storage_path: Path = Path("./storage")
    deployment_tier: str = "starter"
    demo_auth: bool = True
    ai_engine_enabled: bool = False
    ai_engine_timeout: int = 30
    max_upload_bytes: int = 10 * 1024 * 1024
    max_qc_image_bytes: int = 5 * 1024 * 1024
    max_qc_batch_bytes: int = 50 * 1024 * 1024
    max_qc_images: int = 20
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

@lru_cache
def get_settings() -> Settings:
    return Settings()
