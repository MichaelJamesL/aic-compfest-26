"""Embedding wrapper over fastembed's multilingual e5 model.

intfloat/multilingual-e5-large: 1024-dim (matches the VECTOR(1024) schema),
handles Indonesian and English in one model, runs on CPU, no API key.
"""
from __future__ import annotations

from fastembed import TextEmbedding

MODEL_NAME = "intfloat/multilingual-e5-large"

_model: TextEmbedding | None = None


def _ensure_model() -> TextEmbedding:
    global _model
    if _model is None:
        _model = TextEmbedding(MODEL_NAME)  # downloads on first use
    return _model


def embed(texts: list[str]) -> list[list[float]]:
    """Embed a list of texts into 1024-dim vectors."""
    model = _ensure_model()
    return [vec.tolist() for vec in model.embed(texts)]