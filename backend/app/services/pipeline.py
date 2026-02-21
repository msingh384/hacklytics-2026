from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from app.integrations.gemini import GeminiClient
from app.integrations.imdb_scraper import scrape_imdb_reviews
from app.integrations.omdb import OmdbClient
from app.integrations.vector_store import IndexedChunk, VectorStore
from app.integrations.wikipedia import WikipediaPlotClient
from app.schemas import JobStatus, MovieCandidate, PipelineStartResponse
from app.services.clustering import cluster_review_chunks
from app.services.datastore import DataStore
from app.services.embedding import EmbeddingService
from app.utils.text import split_into_review_chunks, stable_id


@dataclass
class JobRecord:
    job_id: str
    status: str
    stage: str
    progress: int
    movie_id: str | None
    message: str | None
    error: str | None
    updated_at: datetime


class MoviePipelineService:
    def __init__(
        self,
        *,
        store: DataStore,
        omdb: OmdbClient,
        wiki: WikipediaPlotClient,
        gemini: GeminiClient,
        embedder: EmbeddingService,
        vector_store: VectorStore,
    ):
        self.store = store
        self.omdb = omdb
        self.wiki = wiki
        self.gemini = gemini
        self.embedder = embedder
        self.vector_store = vector_store
        self.jobs: dict[str, JobRecord] = {}

    def _set_job(self, job_id: str, **changes: Any) -> None:
        current = self.jobs[job_id]
        for key, value in changes.items():
            setattr(current, key, value)
        current.updated_at = datetime.now(timezone.utc)

    def _as_status(self, record: JobRecord) -> JobStatus:
        return JobStatus(
            job_id=record.job_id,
            status=record.status,
            stage=record.stage,
            progress=record.progress,
            movie_id=record.movie_id,
            message=record.message,
            error=record.error,
            updated_at=record.updated_at,
        )

    def get_job(self, job_id: str) -> JobStatus | None:
        record = self.jobs.get(job_id)
        return self._as_status(record) if record else None

    async def start_from_search(
        self,
        *,
        query: str,
        year: str | None,
        selected_imdb_id: str | None,
    ) -> PipelineStartResponse:
        movie_id = selected_imdb_id
        candidates: list[MovieCandidate] = []

        if not movie_id:
            known = self.store.search_movies(query, limit=10)
            if len(known) == 1:
                movie_id = known[0]["movie_id"]
            else:
                try:
                    candidates = await asyncio.to_thread(self.omdb.search_by_title, query, year)
                except RuntimeError:
                    # OMDB key missing. Fall back to existing local catalog.
                    candidates = [
                        MovieCandidate(
                            movie_id=item["movie_id"],
                            title=item.get("title", ""),
                            year=item.get("year"),
                            poster=item.get("poster"),
                            imdb_rating=item.get("imdb_rating"),
                            rotten_tomatoes=item.get("rotten_tomatoes"),
                            audience_score=item.get("audience_score"),
                        )
                        for item in known
                    ]

                if len(candidates) != 1:
                    return PipelineStartResponse(
                        status="needs_selection",
                        candidates=candidates,
                        message="Select one movie to continue the preparation pipeline.",
                    )
                movie_id = candidates[0].movie_id

        if not movie_id:
            return PipelineStartResponse(status="failed", message="No movie selected")

        movie = self.store.get_movie(movie_id)
        if movie and self.store.get_clusters(movie_id) and self.store.get_plot_beats(movie_id) and self.store.get_what_ifs(movie_id):
            return PipelineStartResponse(status="ready", movie_id=movie_id, message="Movie already prepared.")

        job_id = str(uuid4())
        self.jobs[job_id] = JobRecord(
            job_id=job_id,
            status="queued",
            stage="queued",
            progress=0,
            movie_id=movie_id,
            message="Pipeline queued",
            error=None,
            updated_at=datetime.now(timezone.utc),
        )
        asyncio.create_task(self._run_job_with_timeout(job_id, movie_id, query=query, year=year))
        return PipelineStartResponse(status="queued", job_id=job_id, movie_id=movie_id, message="Pipeline started")

    async def _run_job_with_timeout(self, job_id: str, movie_id: str, query: str, year: str | None) -> None:
        try:
            await asyncio.wait_for(
                self._run_job(job_id, movie_id, query, year),
                timeout=300,
            )
        except asyncio.TimeoutError:
            self._set_job(
                job_id,
                status="failed",
                stage="timeout",
                progress=100,
                error="Pipeline timed out after 5 minutes",
                message="Pipeline timed out",
            )

    async def _run_job(self, job_id: str, movie_id: str, query: str, year: str | None) -> None:
        try:
            self._set_job(job_id, status="running", stage="fetching_movie", progress=5, message="Loading movie metadata")
            movie = self.store.get_movie(movie_id)
            if not movie:
                omdb_payload = await asyncio.to_thread(self.omdb.fetch_by_imdb_id, movie_id)
                if not omdb_payload:
                    raise RuntimeError("OMDB did not return movie details")
                movie = self.store.upsert_movie(omdb_payload)

            title = movie.get("title") or query
            self._set_job(job_id, stage="user_reviews", progress=20, message="Checking user reviews")
            user_count = self.store.count_user_reviews(movie_id)
            if user_count == 0:
                scraped = await asyncio.to_thread(scrape_imdb_reviews, movie_id, 1200)
                rows = [
                    {
                        "review_id": item.review_id,
                        "movie_review": item.text,
                        "rating": item.rating,
                    }
                    for item in scraped
                ]
                self.store.insert_user_reviews(movie_id, title, rows)

            self._set_job(job_id, stage="critic_reviews", progress=35, message="Loading critic reviews")
            critics = self.store.get_critic_reviews(movie_id, title)

            self._set_job(job_id, stage="embedding", progress=50, message="Embedding and indexing reviews")
            index_payload = await self.index_embeddings_for_movie(movie_id, title, critics)

            self._set_job(job_id, stage="clustering", progress=65, message="Clustering complaints")
            clusters, examples = await asyncio.to_thread(
                cluster_review_chunks,
                movie_id,
                title,
                index_payload["chunks"],
                index_payload["vectors"],
                self.gemini,
                7,
            )
            self.store.replace_clusters(movie_id, clusters, examples)

            self._set_job(job_id, stage="plot", progress=78, message="Fetching plot summary")
            plot_summary = self.store.get_plot_summary(movie_id)
            plot_text: str | None = plot_summary.get("plot_text") if plot_summary else None
            if not plot_text:
                fetched = await asyncio.to_thread(self.wiki.fetch_plot, title, movie.get("year"))
                if fetched:
                    plot_text, page_title = fetched
                    self.store.save_plot_summary(movie_id, plot_text, page_title)
                else:
                    plot_text = movie.get("plot")
                    if plot_text:
                        self.store.save_plot_summary(movie_id, plot_text, "omdb_fallback")

            self._set_job(job_id, stage="beats", progress=88, message="Generating plot beats")
            if plot_text:
                package = await asyncio.to_thread(self.gemini.generate_plot_package, title, plot_text)
                beats = package.get("beats", [])
                expanded_plot = package.get("expanded_plot")
                self.store.replace_plot_beats(movie_id, beats, expanded_plot)

            self._set_job(job_id, stage="what_if", progress=94, message="Generating what-if suggestions")
            top_clusters = self.store.get_clusters(movie_id)[:3]
            labels = [item.get("label", "") for item in top_clusters]
            base_plot = plot_text or movie.get("plot") or ""
            what_if_texts = await asyncio.to_thread(self.gemini.generate_what_if, title, labels, base_plot)
            what_if_rows = []
            for idx, text in enumerate(what_if_texts[:3], start=1):
                linked = [top_clusters[idx - 1]["cluster_id"]] if idx - 1 < len(top_clusters) else []
                what_if_rows.append(
                    {
                        "movie_id": movie_id,
                        "suggestion_id": stable_id(movie_id, "whatif", str(idx), text[:60]),
                        "text": text,
                        "linked_cluster_ids": linked,
                    }
                )
            self.store.replace_what_ifs(movie_id, what_if_rows)

            self._set_job(job_id, status="ready", stage="ready", progress=100, message="Movie preparation complete")
        except Exception as exc:  # pragma: no cover
            self._set_job(job_id, status="failed", stage="failed", progress=100, error=str(exc), message="Pipeline failed")

    async def index_embeddings_for_movie(
        self,
        movie_id: str,
        movie_title: str,
        critics: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        user_reviews = self.store.get_user_reviews(movie_id, limit=600)
        critic_reviews = critics if critics is not None else self.store.get_critic_reviews(movie_id, movie_title)

        chunks: list[dict[str, Any]] = []
        for source, rows in (("user", user_reviews), ("critic", critic_reviews)):
            for row in rows:
                text = row.get("movie_review") or row.get("review_content")
                if not text:
                    continue
                for chunk_idx, chunk in enumerate(split_into_review_chunks(text, max_sentences=3), start=1):
                    chunk_id = stable_id(movie_id, source, row.get("movie_title", ""), str(chunk_idx), chunk[:120])
                    chunks.append(
                        {
                            "chunk_id": chunk_id,
                            "movie_id": movie_id,
                            "text": chunk,
                            "source": source,
                        }
                    )

        if not chunks:
            return {"chunks": [], "vectors": [], "indexed": 0, "critics_available": bool(critic_reviews)}

        vectors = await asyncio.to_thread(self.embedder.encode, [item["text"] for item in chunks])
        indexed_chunks = [
            IndexedChunk(
                chunk_id=item["chunk_id"],
                movie_id=movie_id,
                text=item["text"],
                source=item["source"],
                vector=vectors[idx],
            )
            for idx, item in enumerate(chunks)
        ]
        await asyncio.to_thread(self.vector_store.upsert, indexed_chunks)

        return {
            "chunks": chunks,
            "vectors": vectors,
            "indexed": len(indexed_chunks),
            "critics_available": bool(critic_reviews),
        }
