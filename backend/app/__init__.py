"""Backend application package.

Domain modules: assets, readings, maintenance, documents, qc, analysis, work_orders.
Each domain has its own models.py, schemas.py, routes.py, service.py.
"""

# Compat: tests and old code do `from app import models, services`.
# Re-export all models and services from their domain homes.
import types as _types

from .assets.models import Asset, BusinessContext, Factory  # noqa: F401
from .readings.models import Reading  # noqa: F401
from .maintenance.models import MaintenanceRecord  # noqa: F401
from .documents.models import Document  # noqa: F401
from .qc.models import QCBatch, QCImage  # noqa: F401
from .analysis.models import AnalysisRun  # noqa: F401
from .work_orders.models import AuditEvent, WorkOrder  # noqa: F401

models = _types.SimpleNamespace(
    Asset=Asset,
    BusinessContext=BusinessContext,
    Factory=Factory,
    Reading=Reading,
    MaintenanceRecord=MaintenanceRecord,
    Document=Document,
    QCBatch=QCBatch,
    QCImage=QCImage,
    AnalysisRun=AnalysisRun,
    AuditEvent=AuditEvent,
    WorkOrder=WorkOrder,
)

from .analysis.service import (  # noqa: E402
    engine_factory,
    engine_request,
    input_disclosure,
    run_analysis,
    StubEngine,
)
from .work_orders.service import (  # noqa: E402
    TRANSITIONS,
    transition,
)

services = _types.SimpleNamespace(
    engine_factory=engine_factory,
    engine_request=engine_request,
    input_disclosure=input_disclosure,
    run_analysis=run_analysis,
    StubEngine=StubEngine,
    TRANSITIONS=TRANSITIONS,
    transition=transition,
)