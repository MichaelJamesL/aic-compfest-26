from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np

from . import config
from .schemas import DefectFinding
from .signals import _severity

_INFERENCES: dict[str, object] = {}

if TYPE_CHECKING:
    from anomalib.deploy import TorchInferencer


def fit(asset_id: str, normal_dir: str | Path) -> Path:
    from anomalib.data import Folder
    from anomalib.deploy import ExportType
    from anomalib.engine import Engine
    from anomalib.models import Patchcore

    datamodule = Folder(
        name=asset_id,
        root=str(normal_dir),
        normal_dir=".",
        normal_split_ratio=0.0,
    )
    datamodule.setup()
    model = Patchcore(backbone=config.PATCHCORE_BACKBONE)
    engine = Engine()
    engine.fit(model, datamodule)
    bank_dir = Path(config.BANK_DIR)
    bank_dir.mkdir(parents=True, exist_ok=True)
    engine.export(model, ExportType.TORCH, export_root=str(bank_dir))
    return bank_dir / f"{asset_id}.pt"


def _load_inferencer(asset_id: str) -> object:
    from anomalib.deploy import TorchInferencer

    model_path = Path(config.BANK_DIR) / f"{asset_id}.pt"
    return TorchInferencer(path=str(model_path))


def inspect(asset_id: str, paths: list[str], subject="asset") -> list[DefectFinding]:
    if asset_id not in _INFERENCES:
        _INFERENCES[asset_id] = _load_inferencer(asset_id)
    inferencer = _INFERENCES[asset_id]

    findings: list[DefectFinding] = []
    for image_path in paths:
        pred = inferencer.predict(image_path)
        score = float(pred.pred_score)
        threshold = float(pred.pred_threshold)
        threshold = config.DEFECT_THRESHOLD if config.DEFECT_THRESHOLD is not None else threshold
        label = "defect" if int(pred.pred_label) == 1 else "ok"
        mult = score / threshold if threshold > 0 else 0.0
        severity = _severity(mult)
        region = _nonzero_region(pred.pred_mask) if pred.pred_mask is not None else None
        findings.append(DefectFinding(
            image=image_path,
            subject=subject,
            score=score,
            threshold=threshold,
            label=label,
            severity=severity,
            region=region,
            heatmap_path=None,
        ))
    return findings


def _nonzero_region(mask: np.ndarray) -> tuple[int, int, int, int]:
    ys, xs = np.where(mask > 0)
    if not ys.size:
        return (0, 0, 0, 0)
    x, y = int(xs.min()), int(ys.min())
    w = int(xs.max()) - x + 1
    h = int(ys.max()) - y + 1
    return (x, y, w, h)