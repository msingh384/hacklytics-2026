from __future__ import annotations

import hashlib
from typing import Iterable

import numpy as np

from app.config import Settings

try:
    from sentence_transformers import SentenceTransformer
except ImportError:  # pragma: no cover
    SentenceTransformer = None


class EmbeddingService:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._model = None
        if SentenceTransformer is not None:
            try:
                self._model = SentenceTransformer(settings.embedding_model)
            except Exception:
                self._model = None

    @property
    def mode(self) -> str:
        return "sentence-transformers" if self._model is not None else "hash"

    def _hash_vector(self, text: str) -> list[float]:
        seed = int(hashlib.sha1(text.encode("utf-8")).hexdigest()[:8], 16)
        rng = np.random.default_rng(seed)
        vec = rng.normal(0, 1, size=self.settings.embedding_dimension)
        norm = np.linalg.norm(vec)
        if norm:
            vec = vec / norm
        return vec.astype(float).tolist()

    def encode(self, texts: Iterable[str]) -> list[list[float]]:
        values = list(texts)
        if not values:
            return []

        if self._model is None:
            return [self._hash_vector(text) for text in values]

        vectors = self._model.encode(values, normalize_embeddings=True)
        if hasattr(vectors, "tolist"):
            return vectors.tolist()
        return [list(map(float, row)) for row in vectors]

    def encode_one(self, text: str) -> list[float]:
        vectors = self.encode([text])
        return vectors[0] if vectors else [0.0] * self.settings.embedding_dimension
