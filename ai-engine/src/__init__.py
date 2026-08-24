"""src - predictive-maintenance AI pipeline for the AIC backend.

The single import surface: `from src import MaintenanceEngine`.
"""
from __future__ import annotations

from . import knowledge
from .engine import MaintenanceEngine
from .schemas import (
    AnalysisRequest,
    AnalysisResult,
    Anomaly,
    Asset,
    BusinessContext,
    DefectFinding,
    Document,
    MaintenanceRecord,
    PhaseQC,
    QCBatch,
    RootCause,
    SensorReading,
    SparePart,
    Tier,
    TechnicianResult,
    VerificationResult,
    WorkOrder,
)

__version__ = "0.1.0"

__all__ = [
    "MaintenanceEngine",
    "AnalysisRequest",
    "AnalysisResult",
    "Tier",
    "Asset",
    "SensorReading",
    "MaintenanceRecord",
    "Document",
    "BusinessContext",
    "Anomaly",
    "DefectFinding",
    "PhaseQC",
    "QCBatch",
    "RootCause",
    "SparePart",
    "WorkOrder",
    "TechnicianResult",
    "VerificationResult",
]
