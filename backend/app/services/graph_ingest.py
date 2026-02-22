"""Knowledge graph ingestion from reviews, ratings, and movie info."""

from __future__ import annotations

from typing import Any

from app.integrations.gemini import GeminiClient
from app.integrations.neo4j_graph import Neo4jGraph
from app.services.datastore import DataStore
from app.utils.text import chunk_script, stable_id


def _build_review_corpus(store: DataStore, movie_id: str, movie: dict[str, Any]) -> str:
    """Build combined text from reviews, clusters, and movie metadata for graph extraction."""
    parts: list[str] = []

    # Movie metadata
    title = movie.get("title") or movie_id
    genre = movie.get("genre")
    plot = movie.get("plot")
    imdb = movie.get("imdb_rating")
    rt = movie.get("rotten_tomatoes")
    audience = movie.get("audience_score")
    meta: list[str] = [f"Movie: {title}"]
    if genre:
        meta.append(f"Genre: {genre}")
    if imdb is not None:
        meta.append(f"IMDB rating: {imdb}")
    if rt:
        meta.append(f"Rotten Tomatoes: {rt}")
    if audience:
        meta.append(f"Audience score: {audience}")
    if plot:
        meta.append(f"Plot: {plot}")
    parts.append("\n".join(meta))

    # Clusters (complaint themes) and examples
    clusters = store.get_clusters(movie_id)
    if clusters:
        cluster_lines: list[str] = ["Complaint themes from audience reviews:"]
        for c in clusters:
            cluster_lines.append(f"- {c.get('label', '')}: {c.get('summary', '')}")
        parts.append("\n".join(cluster_lines))
        examples = store.get_cluster_examples(movie_id)
        if examples:
            example_texts = [e.get("review_text", "") for e in examples if e.get("review_text")]
            if example_texts:
                parts.append("Example review excerpts:\n" + "\n\n".join(example_texts[:20]))

    # User reviews
    user_reviews = store.get_user_reviews(movie_id, limit=300)
    if user_reviews:
        texts: list[str] = []
        for r in user_reviews:
            t = r.get("movie_review", "")
            rating = r.get("rating")
            if t:
                texts.append(f"[Rating: {rating}] {t}" if rating is not None else t)
        if texts:
            parts.append("User reviews:\n" + "\n\n".join(texts))

    # Critic reviews
    critic_reviews = store.get_critic_reviews(movie_id, title)
    if critic_reviews:
        texts = []
        for r in critic_reviews:
            t = r.get("movie_review", "")
            rating = r.get("rating")
            if t:
                texts.append(f"[Critic rating: {rating}] {t}" if rating is not None else t)
        if texts:
            parts.append("Critic reviews:\n" + "\n\n".join(texts))

    return "\n\n---\n\n".join(parts)


class GraphIngestService:
    def __init__(self, graph: Neo4jGraph, gemini: GeminiClient, store: DataStore):
        self.graph = graph
        self.gemini = gemini
        self.store = store

    def ingest_from_reviews(self, movie_id: str) -> dict[str, int]:
        """Build corpus from reviews/ratings/clusters, chunk, extract entities/relations, upsert to Neo4j."""
        if not self.graph.enabled:
            return {"chunks": 0, "entities": 0, "relations": 0, "error": "Neo4j not configured"}

        movie = self.store.get_movie(movie_id)
        if not movie:
            return {"chunks": 0, "entities": 0, "relations": 0, "error": "Movie not found"}

        movie_title = movie.get("title") or movie_id
        corpus = _build_review_corpus(self.store, movie_id, movie)
        if not corpus.strip():
            return {"chunks": 0, "entities": 0, "relations": 0, "error": "No reviews or data for this movie"}

        chunks_raw = chunk_script(corpus)
        chunks_data: list[dict[str, Any]] = []

        for idx, chunk_text in enumerate(chunks_raw):
            chunk_id = stable_id(movie_id, "review_chunk", str(idx), chunk_text[:200])
            extracted = self.gemini.extract_entities_relations(movie_title, chunk_text, source="reviews")
            chunks_data.append(
                {
                    "chunk_id": chunk_id,
                    "movie_id": movie_id,
                    "text": chunk_text,
                    "idx": idx,
                    "entities": extracted.get("entities", []),
                    "relations": extracted.get("relations", []),
                }
            )

        if not chunks_data:
            return {"chunks": 0, "entities": 0, "relations": 0}

        n_chunks, n_entities, n_relations = self.graph.upsert_movie_chunk_entities(
            movie_id=movie_id,
            movie_title=movie_title,
            chunks=chunks_data,
        )
        return {"chunks": n_chunks, "entities": n_entities, "relations": n_relations}
