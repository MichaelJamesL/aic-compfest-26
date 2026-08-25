"""QC defect classification — NOT USED BY THE CURRENT PIPELINE.

Kept for future development. `context.select_context` runs PatchCore detection
only: it answers "is this image abnormal", which is the question the deployed
model can answer honestly. This module answers "which defect class", and the
checkpoint that exists cannot: it is fine-tuned on MVTec `screw` (15.8% overall
on its own held-out split, 1.4% on `good`), so on any other product it returns
a confident label for an object it has never seen. See qc/METRICS.md.

Wiring it back on means retraining on the customer's own product, and probably
replacing gradient fine-tuning with few-shot centroids so a line can be set up
from a handful of labelled examples rather than hundreds.

Original docstring follows.

QC defect classification: which defect, not merely whether one is there.

`vision` answers "is this image abnormal" from a memory bank of good units.
This answers "which defect class", which is the key `mapping/qc_failure_modes.yaml`
uses to reach a machine failure mode. Detection without classification cannot
say what the defect implies about the machine.

The checkpoint is the one `qc/train.py` writes: a fine-tuned mobilenet_v3_small
plus the class list it was trained on. Missing torch or a missing checkpoint
means no opinion, never a crash — same contract as `vision` and `knowledge`.
"""
from __future__ import annotations

from pathlib import Path

from . import config

_MODEL = None
_CLASSES: list[str] = []
# ImageNet statistics, because the backbone was pre-trained on it. Must match
# qc/train.py — a different normalisation silently degrades every prediction.
IMAGE_SIZE = 224
MEAN, STD = [0.485, 0.456, 0.406], [0.229, 0.224, 0.225]
NOMINAL = "good"


def available() -> bool:
    """Whether a classifier can run: torch installed and a checkpoint on disk."""
    from importlib.util import find_spec

    if find_spec("torch") is None or find_spec("torchvision") is None:
        return False
    return Path(config.QC_CLASSIFIER_PATH).is_file()


def _load():
    global _MODEL, _CLASSES
    if _MODEL is not None:
        return _MODEL

    import torch
    from torch import nn
    from torchvision.models import mobilenet_v3_small

    checkpoint = torch.load(config.QC_CLASSIFIER_PATH, map_location="cpu", weights_only=False)
    _CLASSES = list(checkpoint["classes"])
    model = mobilenet_v3_small()
    model.classifier[3] = nn.Linear(model.classifier[3].in_features, len(_CLASSES))
    model.load_state_dict(checkpoint["state_dict"])
    model.eval()
    _MODEL = model
    return model


def classify(paths: list[str]) -> list[tuple[str, float]]:
    """(class, confidence) per image, or [] when no classifier is available.

    [] is not "everything is good" — the caller must not read it as a verdict.
    """
    if not paths or not available():
        return []

    import torch
    from PIL import Image
    from torchvision import transforms

    model = _load()
    prepare = transforms.Compose([
        transforms.Resize((IMAGE_SIZE, IMAGE_SIZE)),
        transforms.ToTensor(),
        transforms.Normalize(MEAN, STD),
    ])

    out: list[tuple[str, float]] = []
    with torch.no_grad():
        for path in paths:
            try:
                # The screws are greyscale; the backbone expects three channels.
                image = Image.open(path).convert("RGB")
            except (FileNotFoundError, OSError):
                continue
            probabilities = torch.softmax(model(prepare(image).unsqueeze(0))[0], dim=0)
            index = int(torch.argmax(probabilities))
            out.append((_CLASSES[index], float(probabilities[index])))
    return out


def demo() -> None:
    """Runnable check: no checkpoint means no opinion, never a crash."""
    original = config.QC_CLASSIFIER_PATH
    try:
        config.QC_CLASSIFIER_PATH = "/nonexistent/model.pt"
        assert available() is False
        assert classify(["whatever.png"]) == []
    finally:
        config.QC_CLASSIFIER_PATH = original

    if available():
        print("classifier present:", Path(config.QC_CLASSIFIER_PATH))
    print("classify demo ok")


if __name__ == "__main__":
    demo()
