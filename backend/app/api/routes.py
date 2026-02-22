from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import Response

from app.schemas import (
    EmbeddingRequest,
    EmbeddingResponse,
    GenerationDetailResponse,
    GenerationResponse,
    JobStatus,
    LeaderboardResponse,
    MovieAnalysisResponse,
    MovieCandidate,
    MovieDetails,
    MovieSearchRequest,
    PipelineStartResponse,
    ReviewRecord,
    SaveGenerationRequest,
    SearchRequest,
    SearchResponse,
    SearchResult,
    StoryCoverageRequest,
    StoryStartRequest,
    StoryStartResponse,
    StoryStepRequest,
    StoryStepResponse,
    ThemeCoverageScore,
    VoteRequest,
    VoteResponse,
    PlotBeat,
    ComplaintCluster,
    ClusterExample,
    WhatIfSuggestion,
    TTSRequest,
)
from app.services.container import ServiceContainer
from app.utils.text import extract_omdb_scores


router = APIRouter()


def _services(request: Request) -> ServiceContainer:
    return request.app.state.services


def _to_candidate(row: dict[str, Any], has_analysis: bool | None = None) -> MovieCandidate:
    return MovieCandidate(
        movie_id=row.get("movie_id") or row.get("imdbID") or "",
        title=row.get("title") or row.get("Title") or "",
        year=row.get("year") or row.get("Year"),
        genre=row.get("genre") or row.get("Genre"),
        poster=row.get("poster") or (None if row.get("Poster") == "N/A" else row.get("Poster")),
        imdb_rating=row.get("imdb_rating"),
        rotten_tomatoes=row.get("rotten_tomatoes"),
        audience_score=row.get("audience_score"),
        has_analysis=has_analysis,
    )


@router.get("/health")
def health(request: Request) -> dict[str, Any]:
    services = _services(request)
    return {
        "status": "ok",
        "store_mode": services.store.mode,
        "vector_mode": services.vector_store.mode,
        "embedding_mode": services.embedder.mode,
        "time": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/movies/featured", response_model=list[MovieCandidate])
def featured_movies(request: Request, limit: int = Query(default=25, ge=1, le=100)) -> list[MovieCandidate]:
    services = _services(request)
    rows = services.store.get_featured_movies(limit=limit)
    movie_ids = [row.get("movie_id") or "" for row in rows]
    has_analysis_map = services.store.movies_have_analysis(movie_ids)
    return [
        _to_candidate(row, has_analysis=has_analysis_map.get(row.get("movie_id") or "", False))
        for row in rows
    ]


@router.get("/movies/search", response_model=list[MovieCandidate])
async def search_movies(request: Request, q: str = Query(min_length=1), year: str | None = None) -> list[MovieCandidate]:
    services = _services(request)
    local_rows = services.store.search_movies(q, limit=25)
    local_ids = [row.get("movie_id") or "" for row in local_rows]
    has_analysis_map = services.store.movies_have_analysis(local_ids)
    local: dict[str, MovieCandidate] = {}
    for row in local_rows:
        movie_id = row.get("movie_id") or ""
        candidate = _to_candidate(row, has_analysis=has_analysis_map.get(movie_id, False))
        local[candidate.movie_id] = candidate

    remote_candidates: list[MovieCandidate] = []
    try:
        remote_candidates = await asyncio.to_thread(services.omdb.search_by_title, q, year)
    except Exception:
        remote_candidates = []

    q_lower = q.strip().lower()
    for item in remote_candidates:
        if item.movie_id not in local and (item.title or "").lower().startswith(q_lower):
            local[item.movie_id] = item

    return list(local.values())


@router.post("/pipeline/search", response_model=PipelineStartResponse)
async def start_pipeline(request: Request, payload: MovieSearchRequest) -> PipelineStartResponse:
    services = _services(request)
    return await services.pipeline.start_from_search(
        query=payload.query,
        year=payload.year,
        selected_imdb_id=payload.selected_imdb_id,
    )


@router.get("/pipeline/jobs/{job_id}", response_model=JobStatus)
def pipeline_status(request: Request, job_id: str) -> JobStatus:
    services = _services(request)
    status = services.pipeline.get_job(job_id)
    if not status:
        raise HTTPException(status_code=404, detail="Job not found")
    return status


@router.post("/movies/{movie_id}/prepare", response_model=PipelineStartResponse)
async def prepare_movie(request: Request, movie_id: str) -> PipelineStartResponse:
    services = _services(request)
    return await services.pipeline.start_from_search(query=movie_id, year=None, selected_imdb_id=movie_id)


@router.post("/movies/{movie_id}/refresh-plot")
async def refresh_plot_beats(request: Request, movie_id: str) -> dict:
    """Re-scrape Wikipedia plot and regenerate plot beats + expanded plot via Gemini."""
    services = _services(request)
    try:
        await services.pipeline.refresh_plot_beats(movie_id)
        return {"status": "ok", "message": "Plot beats refreshed"}
    except RuntimeError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/movies/{movie_id}/analysis", response_model=MovieAnalysisResponse)
def movie_analysis(request: Request, movie_id: str) -> MovieAnalysisResponse:
    services = _services(request)
    movie = services.store.get_movie(movie_id)
    if not movie:
        raise HTTPException(status_code=404, detail="Movie not found")

    if movie.get("omdb_payload") and isinstance(movie["omdb_payload"], dict):
        imdb_rating, rotten, audience = extract_omdb_scores(movie["omdb_payload"])
    else:
        imdb_rating, rotten, audience = movie.get("imdb_rating"), movie.get("rotten_tomatoes"), movie.get("audience_score")

    details = MovieDetails(
        movie_id=movie["movie_id"],
        title=movie.get("title") or "",
        year=movie.get("year"),
        genre=movie.get("genre"),
        poster=movie.get("poster"),
        imdb_rating=imdb_rating,
        rotten_tomatoes=rotten,
        audience_score=audience,
        plot=movie.get("plot"),
        full_omdb=movie.get("omdb_payload") or {},
    )

    plot_summary = services.store.get_plot_summary(movie_id)
    beats = [PlotBeat(**beat) for beat in services.store.get_plot_beats(movie_id)]
    clusters = [ComplaintCluster(**cluster) for cluster in services.store.get_clusters(movie_id)[:5]]
    examples = [ClusterExample(**example) for example in services.store.get_cluster_examples(movie_id)]
    what_ifs = [WhatIfSuggestion(**item) for item in services.store.get_what_ifs(movie_id)[:3]]

    user_reviews = services.store.get_user_reviews(movie_id, limit=8)
    critic_reviews = services.store.get_critic_reviews(movie_id, movie.get("title"), limit=8)
    samples: list[ReviewRecord] = []
    for row in user_reviews:
        samples.append(
            ReviewRecord(
                movie_id=movie_id,
                movie_title=row.get("movie_title") or movie.get("title"),
                movie_review=row.get("movie_review", ""),
                rating=row.get("rating"),
                source="user",
            )
        )
    for row in critic_reviews[:8]:
        samples.append(
            ReviewRecord(
                movie_id=movie_id,
                movie_title=row.get("movie_title") or movie.get("title"),
                movie_review=row.get("movie_review", ""),
                rating=row.get("rating"),
                source="critic",
            )
        )

    return MovieAnalysisResponse(
        movie=details,
        plot_summary=plot_summary.get("plot_text") if plot_summary else None,
        expanded_plot=movie.get("expanded_plot"),
        plot_beats=beats,
        clusters=clusters,
        cluster_examples=examples,
        what_if_suggestions=what_ifs,
        review_samples=samples,
    )


@router.get("/movies/{movie_id}/reviews", response_model=list[ReviewRecord])
def movie_reviews(request: Request, movie_id: str, limit: int = Query(default=80, ge=1, le=500)) -> list[ReviewRecord]:
    services = _services(request)
    movie = services.store.get_movie(movie_id)
    if not movie:
        raise HTTPException(status_code=404, detail="Movie not found")

    user_rows = services.store.get_user_reviews(movie_id, limit=limit)
    critic_rows = services.store.get_critic_reviews(movie_id, movie.get("title"), limit=limit)

    output: list[ReviewRecord] = []
    for row in user_rows:
        output.append(
            ReviewRecord(
                movie_id=movie_id,
                movie_title=row.get("movie_title") or movie.get("title"),
                movie_review=row.get("movie_review", ""),
                rating=row.get("rating"),
                source="user",
            )
        )
    for row in critic_rows:
        output.append(
            ReviewRecord(
                movie_id=movie_id,
                movie_title=row.get("movie_title") or movie.get("title"),
                movie_review=row.get("movie_review", ""),
                rating=row.get("rating"),
                source="critic",
            )
        )
    return output


@router.get("/movies/{movie_id}/plot")
def movie_plot(request: Request, movie_id: str) -> dict[str, Any]:
    services = _services(request)
    movie = services.store.get_movie(movie_id)
    if not movie:
        raise HTTPException(status_code=404, detail="Movie not found")
    plot = services.store.get_plot_summary(movie_id)
    return {
        "movie_id": movie_id,
        "plot_summary": plot.get("plot_text") if plot else None,
        "source_page": plot.get("source_page") if plot else None,
        "omdb_plot": movie.get("plot"),
        "expanded_plot": movie.get("expanded_plot"),
    }


@router.post("/embeddings/index", response_model=EmbeddingResponse)
async def index_embeddings(request: Request, payload: EmbeddingRequest) -> EmbeddingResponse:
    services = _services(request)
    movie = services.store.get_movie(payload.movie_id)
    if not movie:
        raise HTTPException(status_code=404, detail="Movie not found")

    result = await services.pipeline.index_embeddings_for_movie(
        payload.movie_id,
        movie_title=movie.get("title") or "",
    )
    return EmbeddingResponse(
        movie_id=payload.movie_id,
        chunks_indexed=result.get("indexed", 0),
        critics_available=result.get("critics_available", False),
        status="indexed" if result.get("indexed", 0) > 0 else "skipped",
    )


@router.post("/search/vector", response_model=SearchResponse)
async def search_vector(request: Request, payload: SearchRequest) -> SearchResponse:
    services = _services(request)
    query_vector = await asyncio.to_thread(services.embedder.encode_one, payload.query)
    rows = services.vector_store.search(payload.movie_id, query_vector, top_k=payload.top_k)
    return SearchResponse(
        results=[
            SearchResult(
                chunk_id=row["chunk_id"],
                score=row["score"],
                text=row["text"],
                source=row["source"],
            )
            for row in rows
        ]
    )


@router.post("/story/start", response_model=StoryStartResponse)
def start_story(request: Request, payload: StoryStartRequest) -> StoryStartResponse:
    services = _services(request)
    movie = services.store.get_movie(payload.movie_id)
    if not movie:
        raise HTTPException(status_code=404, detail="Movie not found")

    suggestions = services.store.get_what_ifs(payload.movie_id)
    selected = None
    if payload.what_if_id:
        selected = next((item for item in suggestions if item.get("suggestion_id") == payload.what_if_id), None)
    what_if = payload.custom_what_if or (selected.get("text") if selected else None)
    if not what_if:
        raise HTTPException(status_code=400, detail="No what-if selected")

    plot_data = services.store.get_plot_summary(payload.movie_id)
    plot_context = plot_data.get("plot_text") if plot_data else movie.get("plot") or ""
    beats = services.store.get_plot_beats(payload.movie_id)
    clusters = services.store.get_clusters(payload.movie_id)

    story_session_id, narrative, options, step_number = services.story.start_story(
        movie_id=payload.movie_id,
        movie_title=movie.get("title") or "",
        what_if=what_if,
        plot_context=plot_context,
        beats=beats,
        clusters=clusters,
        user_session_id=payload.session_id,
    )

    return StoryStartResponse(
        story_session_id=story_session_id,
        movie_id=payload.movie_id,
        what_if=what_if,
        narrative=narrative,
        options=options,
        step_number=step_number,
    )


@router.post("/story/step", response_model=StoryStepResponse)
def story_step(request: Request, payload: StoryStepRequest) -> StoryStepResponse:
    services = _services(request)
    try:
        result = services.story.continue_story(
            story_session_id=payload.story_session_id,
            option_id=payload.option_id,
            user_session_id=payload.session_id,
        )
    except KeyError:
        raise HTTPException(status_code=404, detail="Story session not found")
    except PermissionError:
        raise HTTPException(status_code=403, detail="Session mismatch")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    return StoryStepResponse(
        story_session_id=payload.story_session_id,
        step_number=result["step_number"],
        narrative=result["narrative"],
        options=result["options"],
        ending=result.get("ending"),
        is_complete=result["is_complete"],
    )


@router.post("/story/coverage", response_model=ThemeCoverageScore)
def story_coverage(request: Request, payload: StoryCoverageRequest) -> ThemeCoverageScore:
    services = _services(request)
    try:
        score = services.story.get_story_coverage(payload.story_session_id, payload.ending_text)
    except KeyError:
        raise HTTPException(status_code=404, detail="Story session not found")
    return ThemeCoverageScore(**score)


@router.post("/generations", response_model=GenerationResponse)
def save_generation(request: Request, payload: SaveGenerationRequest) -> GenerationResponse:
    services = _services(request)
    movie = services.store.get_movie(payload.movie_id)
    if not movie:
        raise HTTPException(status_code=404, detail="Movie not found")

    row = services.store.save_generation(
        movie_id=payload.movie_id,
        movie_title=movie.get("title") or "",
        session_id=payload.session_id,
        story_session_id=payload.story_session_id,
        ending_text=payload.ending_text,
        story_payload=payload.story_payload,
        score_payload=payload.score_payload.model_dump(),
    )

    created_at = datetime.fromisoformat(row["created_at"].replace("Z", "+00:00"))
    return GenerationResponse(
        generation_id=row["generation_id"],
        movie_id=row["movie_id"],
        session_id=row["session_id"],
        ending_text=row["ending_text"],
        votes=int(row.get("votes", 0)),
        score_total=int(row.get("score_total", 0)),
        created_at=created_at,
    )


@router.get("/generations/{generation_id}", response_model=GenerationDetailResponse)
def get_generation(request: Request, generation_id: str) -> GenerationDetailResponse:
    services = _services(request)
    row = services.store.get_generation(generation_id)
    if not row:
        raise HTTPException(status_code=404, detail="Generation not found")
    score_payload = row.get("score_payload")
    if isinstance(score_payload, dict):
        score_payload = ThemeCoverageScore(**score_payload)
    created_at = datetime.fromisoformat(str(row["created_at"]).replace("Z", "+00:00"))
    return GenerationDetailResponse(
        generation_id=row["generation_id"],
        movie_id=row["movie_id"],
        movie_title=row.get("movie_title") or "",
        ending_text=row["ending_text"],
        votes=int(row.get("votes", 0)),
        score_total=int(row.get("score_total", 0)),
        created_at=created_at,
        story_payload=row.get("story_payload") or {},
        score_payload=score_payload,
    )


@router.post("/generations/{generation_id}/vote", response_model=VoteResponse)
def vote_generation(request: Request, generation_id: str, payload: VoteRequest) -> VoteResponse:
    services = _services(request)
    total = services.store.vote_generation(generation_id, payload.session_id, payload.value)
    return VoteResponse(generation_id=generation_id, votes=total)


@router.get("/explore/leaderboard", response_model=LeaderboardResponse)
def leaderboard(
    request: Request,
    limit: int = Query(default=50, ge=1, le=100),
    session_id: str | None = Query(default=None),
) -> LeaderboardResponse:
    services = _services(request)
    items = services.store.leaderboard(limit=limit, session_id=session_id)
    return LeaderboardResponse(items=items)


@router.post("/tts/generate")
async def generate_tts(request: Request, payload: TTSRequest) -> Response:
    services = _services(request)
    if not services.elevenlabs.enabled:
        raise HTTPException(status_code=503, detail="ElevenLabs TTS is not configured")
    audio_bytes = await asyncio.to_thread(services.elevenlabs.generate_speech, payload.text)
    return Response(
        content=audio_bytes,
        media_type="audio/mpeg",
        headers={"Content-Disposition": "inline", "Cache-Control": "no-cache"},
    )
