import json
from collections.abc import Generator
from uuid import uuid4
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
    from .assets.models import Asset, AssetSparePart, BusinessContext, Factory, SparePart  # noqa: F401
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
    if "operator_report" not in columns:
        with engine.begin() as connection:
            connection.execute(text("ALTER TABLE assets ADD COLUMN operator_report TEXT"))
    with engine.begin() as connection:
        connection.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS uq_asset_external_id ON assets (factory_id, external_id) WHERE external_id IS NOT NULL"))
    # business_contexts went from asset-keyed to factory-keyed; a primary key cannot
    # be widened in place, so carry the one per-machine field over and rebuild.
    if "asset_id" in {column["name"] for column in inspect(engine).get_columns("business_contexts")}:
        with engine.begin() as connection:
            carried = connection.execute(
                text("SELECT asset_id, operator_report FROM business_contexts WHERE operator_report IS NOT NULL")
            ).all()
            for asset_id, report in carried:
                connection.execute(
                    text("UPDATE assets SET operator_report = :report WHERE id = :asset_id"),
                    {"report": report, "asset_id": asset_id},
                )
            connection.execute(text("DROP TABLE business_contexts"))
        Base.metadata.create_all(engine)
    # one technician per factory became a roster
    bc_columns = {column["name"] for column in inspect(engine).get_columns("business_contexts")}
    if "technicians_json" not in bc_columns:
        with engine.begin() as connection:
            connection.execute(text("ALTER TABLE business_contexts ADD COLUMN technicians_json JSON"))
            connection.execute(text("UPDATE business_contexts SET technicians_json = '[]'"))
    if "technician_schedule" in bc_columns:
        with engine.begin() as connection:
            for factory_id, technician in connection.execute(
                text("SELECT factory_id, technician_schedule FROM business_contexts WHERE technician_schedule IS NOT NULL")
            ).all():
                connection.execute(
                    text("UPDATE business_contexts SET technicians_json = :roster WHERE factory_id = :factory_id"),
                    {"roster": json.dumps([technician if isinstance(technician, dict) else json.loads(technician)]),
                     "factory_id": factory_id},
                )
            connection.execute(text("ALTER TABLE business_contexts DROP COLUMN technician_schedule"))
    # spare parts left the business_contexts JSON blob for their own table, so they
    # can be linked to the machines they actually fit.
    if "spareparts_json" in bc_columns:
        from .assets.models import SparePart
        with engine.begin() as connection:
            for factory_id, blob in connection.execute(
                text("SELECT factory_id, spareparts_json FROM business_contexts WHERE spareparts_json IS NOT NULL")
            ).all():
                parts = blob if isinstance(blob, list) else json.loads(blob)
                for part in parts:
                    if not isinstance(part, dict):
                        part = {"id": str(part), "name": str(part)}
                    connection.execute(
                        SparePart.__table__.insert().values(
                            id=str(uuid4()), factory_id=factory_id,
                            code=part.get("id") or part.get("name", ""), name=part.get("name", ""),
                            stock=part.get("stock", 0), unit=part.get("unit", "pcs"),
                            min_stock=part.get("min_stock"), eta=part.get("eta"),
                        )
                    )
            connection.execute(text("ALTER TABLE business_contexts DROP COLUMN spareparts_json"))
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
