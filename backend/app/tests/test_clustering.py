from __future__ import annotations

from app.integrations.vector_store import IndexedChunk
from app.services.clustering import cluster_review_chunks_from_vector_store


class _DummyGemini:
    def label_clusters_from_full_reviews(self, movie_title: str, cluster_payloads: list[dict]) -> list[str]:
        return [f"Theme {idx + 1}" for idx, _ in enumerate(cluster_payloads)]


class _FakeVectorStore:
    def __init__(self, chunks: list[IndexedChunk]):
        self._chunks = chunks

    def list_movie_chunks(self, movie_id: str, *, include_vectors: bool = True, limit: int | None = None) -> list[IndexedChunk]:
        rows = [chunk for chunk in self._chunks if chunk.movie_id == movie_id]
        if limit is not None:
            rows = rows[:limit]
        return rows


def test_cluster_labels_do_not_stay_generic_when_gemini_falls_back() -> None:
    movie_id = "tt001"
    chunks = [
        IndexedChunk(
            chunk_id="c1",
            movie_id=movie_id,
            text="The ending felt rushed and abrupt.",
            source="user",
            vector=[1.0, 0.0],
        ),
        IndexedChunk(
            chunk_id="c2",
            movie_id=movie_id,
            text="Rushed finale with no emotional payoff.",
            source="critic",
            vector=[0.95, 0.05],
        ),
        IndexedChunk(
            chunk_id="c3",
            movie_id=movie_id,
            text="Characters lacked depth and arc.",
            source="user",
            vector=[0.0, 1.0],
        ),
        IndexedChunk(
            chunk_id="c4",
            movie_id=movie_id,
            text="Flat character development weakened the story.",
            source="critic",
            vector=[0.05, 0.95],
        ),
    ]
    store = _FakeVectorStore(chunks)
    gemini = _DummyGemini()

    clusters, examples = cluster_review_chunks_from_vector_store(
        movie_id=movie_id,
        movie_title="Example Movie",
        vector_store=store,  # type: ignore[arg-type]
        gemini=gemini,  # type: ignore[arg-type]
        max_clusters=2,
        chunk_metadata={
            "c1": {"full_review_text": "The ending felt rushed and abrupt with little closure."},
            "c2": {"full_review_text": "Rushed finale with no emotional payoff in the final act."},
            "c3": {"full_review_text": "Characters lacked depth and clear motivations."},
            "c4": {"full_review_text": "Flat character development weakened the overall story arc."},
        },
    )

    assert len(clusters) == 2
    assert all(not cluster["label"].lower().startswith("theme") for cluster in clusters)
    assert examples
    assert all(example["review_text"] for example in examples)
