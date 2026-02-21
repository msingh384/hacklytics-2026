from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from app.config import Settings

try:
    from cortex import CortexClient, DistanceMetric, Field, Filter  # type: ignore
except ImportError:  # pragma: no cover
    CortexClient = None
    DistanceMetric = None
    Field = None
    Filter = None


@dataclass
class IndexedChunk:
    chunk_id: str
    movie_id: str
    text: str
    source: str
    vector: list[float]


class VectorStore:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._use_actian = bool(settings.enable_actian and CortexClient is not None)
        self._client = None
        self._collection = settings.actian_collection
        self._memory_chunks: dict[str, IndexedChunk] = {}

        if self._use_actian:
            try:
                self._client = CortexClient(settings.actian_address)
                self._client.get_or_create_collection(
                    name=self._collection,
                    dimension=settings.embedding_dimension,
                    distance_metric=DistanceMetric.COSINE,
                )
            except Exception:
                self._use_actian = False
                self._client = None

    @property
    def mode(self) -> str:
        return "actian" if self._use_actian else "memory"

    def upsert(self, chunks: list[IndexedChunk]) -> int:
        if not chunks:
            return 0

        if self._use_actian and self._client:
            ids = [item.chunk_id for item in chunks]
            vectors = [item.vector for item in chunks]
            payloads = [
                {
                    "movie_id": item.movie_id,
                    "text": item.text,
                    "source": item.source,
                }
                for item in chunks
            ]
            self._client.batch_upsert(
                collection_name=self._collection,
                ids=ids,
                vectors=vectors,
                payloads=payloads,
            )
            self._client.flush(self._collection)
            return len(chunks)

        for chunk in chunks:
            self._memory_chunks[chunk.chunk_id] = chunk
        return len(chunks)

    def has_movie(self, movie_id: str) -> bool:
        if self._use_actian:
            # No cheap count API exposed in the beta SDK; use query with top_k=1.
            # If query fails, return False and allow caller to index again.
            try:
                probe = [0.0] * self.settings.embedding_dimension
                result = self._client.search(
                    collection_name=self._collection,
                    query_vector=probe,
                    top_k=1,
                    filter=Filter(must=[Field("movie_id", movie_id)]),
                )
                return bool(result)
            except Exception:
                return False
        return any(chunk.movie_id == movie_id for chunk in self._memory_chunks.values())

    def search(self, movie_id: str, query_vector: list[float], top_k: int = 5) -> list[dict[str, Any]]:
        if self._use_actian and self._client:
            results = self._client.search(
                collection_name=self._collection,
                query_vector=query_vector,
                top_k=top_k,
                filter=Filter(must=[Field("movie_id", movie_id)]),
            )
            return [
                {
                    "chunk_id": str(row.get("id")),
                    "score": float(row.get("score", 0.0)),
                    "text": row.get("payload", {}).get("text", ""),
                    "source": row.get("payload", {}).get("source", "unknown"),
                }
                for row in results
            ]

        candidates = [item for item in self._memory_chunks.values() if item.movie_id == movie_id]
        if not candidates:
            return []

        q = np.array(query_vector, dtype=float)
        q_norm = np.linalg.norm(q)
        if q_norm == 0:
            return []

        scored: list[tuple[float, IndexedChunk]] = []
        for chunk in candidates:
            v = np.array(chunk.vector, dtype=float)
            denom = q_norm * np.linalg.norm(v)
            score = float(np.dot(q, v) / denom) if denom else 0.0
            scored.append((score, chunk))

        scored.sort(key=lambda item: item[0], reverse=True)
        return [
            {
                "chunk_id": chunk.chunk_id,
                "score": score,
                "text": chunk.text,
                "source": chunk.source,
            }
            for score, chunk in scored[:top_k]
        ]

    def close(self) -> None:
        if self._client:
            try:
                self._client.close()
            except Exception:
                pass
