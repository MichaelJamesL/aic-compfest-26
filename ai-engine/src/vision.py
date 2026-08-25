from __future__ import annotations

import json
import tempfile
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


def fit(asset_id: str, normal_dir: str | Path) -> dict:
    """Fit a memory bank from images of good units.

    Returns the bank path plus a self-check: how many of the training images the
    fitted model itself calls anomalous. On a clean reference set that number is
    near zero. A high one means the references were not all good units, and the
    bank will mark almost everything defective — which is exactly what a silently
    bad bank looks like from the outside, so it is reported rather than left to
    be discovered by an analysis that rejects every product.
    """
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
    bank_dir = Path(config.BANK_DIR)
    bank_dir.mkdir(parents=True, exist_ok=True)
    # anomalib writes a versioned workspace under ./results relative to the
    # process cwd, which is not writable in the container and is 2GB of run
    # artefacts on a workstation. Only the exported bank is worth keeping.
    with tempfile.TemporaryDirectory() as workspace:
        engine = Engine(default_root_dir=workspace)
        engine.fit(model, datamodule)
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

    # anomalib 2.x hands back a score already binarised against the threshold it
    # learned, so "how many did it flag" is a count of scores at the top end.
    flagged = int((scores >= 0.5).sum()) if scores.size else 0
    return {
        "path": target,
        "images": int(scores.size),
        "flagged_in_training": flagged,
    }


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


def available() -> bool:
    """Whether the visual inspection stack can run at all.

    anomalib is an optional extra and is not in the deployed backend image, so
    this is routinely False. A missing extra must not take an analysis down —
    the sensors, history and business context are still worth reasoning over.
    """
    from importlib.util import find_spec

    return find_spec("anomalib") is not None


def trained(name: str) -> bool:
    """Whether a memory bank exists for this asset or product."""
    return (Path(config.BANK_DIR) / f"{name}.pt").exists()


def inspect(asset_id: str, paths: list[str], subject="asset", phase=None) -> list[DefectFinding]:
    if not paths or not available() or not trained(asset_id):
        # No opinion, rather than a crash or a false "no defects found". The
        # caller reports the images as unscored — see input_disclosure.
        return []
    if asset_id not in _INFERENCES:
        _INFERENCES[asset_id] = _load_inferencer(asset_id)
    inferencer = _INFERENCES[asset_id]

    findings: list[DefectFinding] = []
    for image_path in paths:
        pred = inferencer.predict(image_path)
        score = float(pred.pred_score.item())
        threshold = _threshold_for(asset_id)
        # anomalib 2.x post-processes before handing the score back: pred_score
        # arrives already normalised against the threshold it learned, and
        # pred_label carries its verdict. Comparing that to a threshold computed
        # here marked every image "ok", because a binarised score can never
        # exceed a multiplier of it. Trust the model's own verdict when it gives
        # one; the hand-rolled fence stays for banks exported by older versions.
        verdict = getattr(pred, "pred_label", None)
        if verdict is not None:
            defect = bool(verdict.item() if hasattr(verdict, "item") else verdict)
        else:
            defect = score > threshold
        label = "defect" if defect else "ok"
        # How much of the frame the model marked, which is a real measure of how
        # bad it is — unlike a score that is already collapsed to 0 or 1.
        mask = pred.pred_mask.numpy() if pred.pred_mask is not None else None
        flagged = float(mask.mean()) if mask is not None and mask.size else 0.0
        severity = _severity(flagged / 0.02) if defect else "low"
        region = _nonzero_region(mask) if mask is not None else None
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