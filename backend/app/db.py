from collections.abc import Generator
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from .config import get_settings

class Base(DeclarativeBase):
    pass

def _engine():
    url = get_settings().database_url
    args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    options = {"connect_args": args, "pool_pre_ping": True}
    if url == "sqlite://":
        options["poolclass"] = StaticPool
    return create_engine(url, **options)

engine = _engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db() -> None:
    from .assets.models import Asset, BusinessContext, Factory  # noqa: F401
    from .readings.models import Reading  # noqa: F401
    from .maintenance.models import MaintenanceRecord  # noqa: F401
    from .documents.models import Document  # noqa: F401
    from .qc.models import QCBatch, QCImage  # noqa: F401
    from .analysis.models import AnalysisRun  # noqa: F401
    from .work_orders.models import AuditEvent, WorkOrder  # noqa: F401
    Base.metadata.create_all(engine)
    # The project has no migration runner yet; keep the small demo schema
    # upgrade safe for databases created before these columns/tables existed.
    columns = {column["name"] for column in inspect(engine).get_columns("assets")}
    if "external_id" not in columns:
        with engine.begin() as connection:
            connection.execute(text("ALTER TABLE assets ADD COLUMN external_id VARCHAR(200)"))
    with engine.begin() as connection:
        connection.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS uq_asset_external_id ON assets (factory_id, external_id) WHERE external_id IS NOT NULL"))
    wo_columns = {column["name"] for column in inspect(engine).get_columns("work_orders")}
    additions = {
        "technician_result_json": "JSON",
        "result_submitted_at": "DATETIME",
        "verification_json": "JSON",
        "verified_at": "DATETIME",
    }
    missing = {name: definition for name, definition in additions.items() if name not in wo_columns}
    if missing:
        with engine.begin() as connection:
            for name, definition in missing.items():
                connection.execute(text(f"ALTER TABLE work_orders ADD COLUMN {name} {definition}"))
    maintenance_columns = {column["name"] for column in inspect(engine).get_columns("maintenance_records")}
    if "external_id" not in maintenance_columns:
        with engine.begin() as connection:
            connection.execute(text("ALTER TABLE maintenance_records ADD COLUMN external_id VARCHAR(200)"))
    with engine.begin() as connection:
        connection.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS uq_maintenance_external_id ON maintenance_records (factory_id, external_id) WHERE external_id IS NOT NULL"))
    qc_columns = {column["name"] for column in inspect(engine).get_columns("qc_batches")}
    qc_additions = {"phase": "VARCHAR(100) DEFAULT 'inspection'", "product": "VARCHAR(200) DEFAULT ''"}
    missing_qc = {name: definition for name, definition in qc_additions.items() if name not in qc_columns}
    if missing_qc:
        with engine.begin() as connection:
            for name, definition in missing_qc.items():
                connection.execute(text(f"ALTER TABLE qc_batches ADD COLUMN {name} {definition}"))
