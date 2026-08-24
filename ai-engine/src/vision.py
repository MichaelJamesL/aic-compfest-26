from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np

from . import config
from .schemas import DefectFinding
from .signals import _severity

_INFERENCES: dict[str, object] = {}
_THRESHOLDS: dict[str, float] = {}

if TYPE_CHECKING:
    from anomalib.deploy import TorchInferencer


def _threshold_path(asset_id: str) -> Path:
    return Path(config.BANK_DIR) / f"{asset_id}.threshold"


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
    target = bank_dir / f"{asset_id}.pt"
    exported = sorted(bank_dir.rglob("model.pt"), key=lambda p: p.stat().st_mtime, reverse=True)
    if exported:
        exported[0].rename(target)

    # ponytail: anomalib no longer exports the F1-optimal threshold. Compute it
    # from the training set as the max anomaly score, then save it next to the
    # model file so inspect() doesn't need config.
    scores = _compute_scores(target, Path(normal_dir))
    threshold = max(float(np.max(scores)) * 1.5, 0.5) if scores.size else 0.5
    _threshold_path(asset_id).write_text(json.dumps(threshold))

    return target


def _compute_scores(model_path, normal_dir: Path) -> np.ndarray:
    import os

    from anomalib.deploy import TorchInferencer

    os.environ.setdefault("TRUST_REMOTE_CODE", "1")

    inferencer = TorchInferencer(path=str(model_path))
    scores = []
    for img in sorted(normal_dir.iterdir()):
        if img.suffix.lower() in (".png", ".jpg", ".jpeg"):
            pred = inferencer.predict(str(img))
            scores.append(float(pred.pred_score.item()))
    if scores:
        return np.array(scores, dtype=float)
    return np.array([0.5], dtype=float)


def _load_inferencer(asset_id: str) -> object:
    import os

    from anomalib.deploy import TorchInferencer

    os.environ.setdefault("TRUST_REMOTE_CODE", "1")

    model_path = Path(config.BANK_DIR) / f"{asset_id}.pt"
    tp = _threshold_path(asset_id)
    if tp.exists():
        _THRESHOLDS[asset_id] = json.loads(tp.read_text())
    return TorchInferencer(path=str(model_path))


def _threshold_for(asset_id: str) -> float:
    if config.DEFECT_THRESHOLD is not None:
        return config.DEFECT_THRESHOLD
    return _THRESHOLDS.get(asset_id, 0.5)


def inspect(asset_id: str, paths: list[str], subject="asset", phase=None) -> list[DefectFinding]:
    if asset_id not in _INFERENCES:
        _INFERENCES[asset_id] = _load_inferencer(asset_id)
    inferencer = _INFERENCES[asset_id]

    findings: list[DefectFinding] = []
    for image_path in paths:
        pred = inferencer.predict(image_path)
        score = float(pred.pred_score.item())
        threshold = _threshold_for(asset_id)
        label = "defect" if score > threshold else "ok"
        mult = score / threshold if threshold > 0 else 0.0
        severity = _severity(mult)
        region = _nonzero_region(pred.pred_mask.numpy()) if pred.pred_mask is not None else None
        findings.append(DefectFinding(
            image=image_path,
            subject=subject,
            score=score,
            threshold=threshold,
            label=label,
            severity=severity,
            region=region,
            heatmap_path=None,
            phase=phase,
        ))
    return findings


def _nonzero_region(mask: np.ndarray) -> tuple[int, int, int, int]:
    if mask.ndim == 3:
        mask = mask.squeeze(0)
    ys, xs = np.where(mask > 0)
    if not ys.size:
        return (0, 0, 0, 0)
    x, y = int(xs.min()), int(ys.min())
    w = int(xs.max()) - x + 1
    h = int(ys.max()) - y + 1
    return (x, y, w, h)