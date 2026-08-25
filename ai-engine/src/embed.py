"""Embedding wrapper over fastembed's multilingual model.

sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2: 384-dim, handles
Indonesian and English in one model, runs on CPU, no API key.

Chosen over intfloat/multilingual-e5-large (1024-dim) after measuring both on
Indonesian maintenance queries: same top-1 accuracy, ~4x the separation between
the correct chunk and the runner-up, ~6x faster, and 0.22GB on disk instead of
2.24GB. e5 also expects "query: "/"passage: " prefixes that this wrapper never
added, so it was running off-spec.
"""
from __future__ import annotations

from fastembed import TextEmbedding

MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

# The pgvector column width is derived from this — see knowledge.init_schema.
# Changing the model means changing this, and every stored vector becomes
# unusable because cosine distance is undefined across dimensions.
DIM = 384

_model: TextEmbedding | None = None


def _ensure_model() -> TextEmbedding:
    global _model
    if _model is None:
        _model = TextEmbedding(MODEL_NAME)  # downloads on first use
    return _model


def embed(texts: list[str]) -> list[list[float]]:
    """Embed a list of texts into DIM-dimensional vectors."""
    model = _ensure_model()
    return [vec.tolist() for vec in model.embed(texts)]
