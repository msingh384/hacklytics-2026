from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from app.config import Settings

try:
    from supabase import Client, create_client
except ImportError:  # pragma: no cover
    Client = None
    create_client = None


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
        self._client: Client | None = None
        self._memory_chunks: dict[str, IndexedChunk] = {}

        use_supabase = bool(
            settings.use_supabase_vector
            and settings.supabase_url
            and settings.supabase_service_role_key
            and create_client is not None
        )
        if use_supabase:
            try:
                self._client = create_client(
                    settings.supabase_url,
                    settings.supabase_service_role_key,
                )
            except Exception:
                self._client = None

    @property
    def mode(self) -> str:
        return "supabase" if self._client is not None else "memory"

    def upsert(self, chunks: list[IndexedChunk]) -> int:
        if not chunks:
            return 0

        if self._client:
            # Dedupe by chunk_id (last wins) to avoid Postgres "cannot affect row a second time"
            seen: dict[str, dict[str, Any]] = {}
            for item in chunks:
                seen[item.chunk_id] = {
                    "movie_id": item.movie_id,
                    "chunk_id": item.chunk_id,
                    "text": item.text,
                    "source": item.source,
                    "embedding": item.vector,
                }
            rows = list(seen.values())
            batch_size = 200
            total = 0
            try:
                for i in range(0, len(rows), batch_size):
                    batch = rows[i : i + batch_size]
                    self._client.table("review_embeddings").upsert(
                        batch,
                        on_conflict="chunk_id",
                    ).execute()
                    total += len(batch)
                return total
            except Exception as e:
                import sys
                print(f"review_embeddings upsert failed: {e}", file=sys.stderr)

        for chunk in chunks:
            self._memory_chunks[chunk.chunk_id] = chunk
        return len(chunks)

    @staticmethod
    def _parse_embedding(value: Any) -> list[float]:
        if isinstance(value, list):
            return [float(item) for item in value]
        if isinstance(value, tuple):
            return [float(item) for item in value]
        if isinstance(value, str):
            raw = value.strip()
            if raw.startswith("[") and raw.endswith("]"):
                raw = raw[1:-1]
            if not raw:
                return []
            parts = [item.strip() for item in raw.split(",") if item.strip()]
            out: list[float] = []
            for part in parts:
                try:
                    out.append(float(part))
                except ValueError:
                    continue
            return out
        return []

    def list_movie_chunks(
        self,
        movie_id: str,
        *,
        include_vectors: bool = True,
        limit: int | None = None,
    ) -> list[IndexedChunk]:
        if self._client:
            columns = "movie_id,chunk_id,text,source,embedding,id" if include_vectors else "movie_id,chunk_id,text,source,id"
            start = 0
            page_size = 1000
            rows: list[dict[str, Any]] = []

            try:
                while True:
                    size = page_size
                    if limit is not None:
                        remaining = limit - len(rows)
                        if remaining <= 0:
                            break
                        size = min(size, remaining)
                    if size <= 0:
                        break

                    end = start + size - 1
                    batch = (
                        self._client.table("review_embeddings")
                        .select(columns)
                        .eq("movie_id", movie_id)
                        .order("id")
                        .range(start, end)
                        .execute()
                        .data
                        or []
                    )
                    rows.extend(batch)
                    if len(batch) < size:
                        break
                    start += size
            except Exception:
                rows = []

            output: list[IndexedChunk] = []
            for row in rows:
                vector = self._parse_embedding(row.get("embedding")) if include_vectors else []
                output.append(
                    IndexedChunk(
                        chunk_id=str(row.get("chunk_id") or ""),
                        movie_id=str(row.get("movie_id") or movie_id),
                        text=str(row.get("text") or ""),
                        source=str(row.get("source") or "user"),
                        vector=vector,
                    )
                )
            return output

        items = [chunk for chunk in self._memory_chunks.values() if chunk.movie_id == movie_id]
        if limit is not None:
            items = items[:limit]
        if include_vectors:
            return items
        return [
            IndexedChunk(
                chunk_id=item.chunk_id,
                movie_id=item.movie_id,
                text=item.text,
                source=item.source,
                vector=[],
            )
            for item in items
        ]

    def delete_for_movie(self, movie_id: str) -> int:
        """Remove all embeddings for a movie. Returns count deleted."""
        if self._client:
            try:
                r = self._client.table("review_embeddings").delete().eq("movie_id", movie_id).execute()
                return len(r.data or [])
            except Exception:
                return 0
        removed = sum(1 for c in list(self._memory_chunks.values()) if c.movie_id == movie_id)
        for cid, c in list(self._memory_chunks.items()):
            if c.movie_id == movie_id:
                del self._memory_chunks[cid]
        return removed

    def has_movie(self, movie_id: str) -> bool:
        if self._client:
            try:
                result = (
                    self._client.table("review_embeddings")
                    .select("chunk_id")
                    .eq("movie_id", movie_id)
                    .limit(1)
                    .execute()
                )
                return bool(result.data and len(result.data) > 0)
            except Exception:
                return False
        return any(chunk.movie_id == movie_id for chunk in self._memory_chunks.values())

    def search(self, movie_id: str, query_vector: list[float], top_k: int = 5) -> list[dict[str, Any]]:
        if self._client:
            try:
                result = self._client.rpc(
                    "match_review_embeddings",
                    {
                        "query_embedding": query_vector,
                        "p_movie_id": movie_id,
                        "match_count": top_k,
                    },
                ).execute()
                rows = result.data or []
                return [
                    {
                        "chunk_id": r.get("chunk_id", ""),
                        "score": float(r.get("similarity", 0.0)),
                        "text": r.get("text", ""),
                        "source": r.get("source", "unknown"),
                    }
                    for r in rows
                ]
            except Exception:
                pass

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
        self._client = None
