from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


class MovieCandidate(BaseModel):
    movie_id: str
    title: str
    year: Optional[str] = None
    genre: Optional[str] = None
    poster: Optional[str] = None
    imdb_rating: Optional[float] = None
    rotten_tomatoes: Optional[str] = None
    audience_score: Optional[str] = None
    has_analysis: Optional[bool] = None


class MovieSearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=200)
    year: Optional[str] = None
    selected_imdb_id: Optional[str] = None
    session_id: Optional[str] = None


class PipelineStartResponse(BaseModel):
    status: Literal["needs_selection", "queued", "ready", "failed"]
    job_id: Optional[str] = None
    movie_id: Optional[str] = None
    candidates: list[MovieCandidate] = []
    message: Optional[str] = None


class JobStatus(BaseModel):
    job_id: str
    status: Literal["queued", "running", "ready", "failed"]
    stage: str
    progress: int = Field(ge=0, le=100)
    movie_id: Optional[str] = None
    message: Optional[str] = None
    error: Optional[str] = None
    updated_at: datetime


class ReviewRecord(BaseModel):
    review_id: Optional[str] = None
    movie_id: str
    movie_title: Optional[str] = None
    movie_review: str
    rating: Optional[float] = None
    source: Literal["user", "critic"]


class PlotBeat(BaseModel):
    movie_id: str
    beat_order: int
    label: str
    beat_text: str


class MovieCharacter(BaseModel):
    movie_id: str
    character_id: str
    name: str
    role: str
    analysis: str


class ComplaintCluster(BaseModel):
    movie_id: str
    cluster_id: str
    label: str
    summary: str
    review_count: int

class ClusterExample(BaseModel):
    movie_id: str
    cluster_id: str
    example_id: str
    review_text: str
    source: Literal["user", "critic"]
    review_reference: Optional[str] = None


class WhatIfSuggestion(BaseModel):
    movie_id: str
    suggestion_id: str
    text: str
    linked_cluster_ids: list[str]


class MovieDetails(BaseModel):
    movie_id: str
    title: str
    year: Optional[str] = None
    genre: Optional[str] = None
    poster: Optional[str] = None
    imdb_rating: Optional[float] = None
    rotten_tomatoes: Optional[str] = None
    audience_score: Optional[str] = None
    plot: Optional[str] = None
    full_omdb: dict[str, Any] = {}


class MovieAnalysisResponse(BaseModel):
    movie: MovieDetails
    plot_summary: Optional[str] = None
    expanded_plot: Optional[str] = None
    plot_beats: list[PlotBeat]
    characters: list[MovieCharacter]
    clusters: list[ComplaintCluster]
    cluster_examples: list[ClusterExample]
    what_if_suggestions: list[WhatIfSuggestion]
    review_samples: list[ReviewRecord]


class StoryOption(BaseModel):
    option_id: str
    label: str
    text: str


class StoryStartRequest(BaseModel):
    movie_id: str
    what_if_id: Optional[str] = None
    custom_what_if: Optional[str] = None
    session_id: str


class StoryStartResponse(BaseModel):
    story_session_id: str
    movie_id: str
    what_if: str
    narrative: str
    options: list[StoryOption]
    step_number: int
    total_steps: int = 3


class StoryStepRequest(BaseModel):
    story_session_id: str
    option_id: str
    session_id: str


class StoryStepResponse(BaseModel):
    story_session_id: str
    step_number: int
    narrative: str
    options: list[StoryOption] = []
    ending: Optional[str] = None
    is_complete: bool


class StoryCoverageRequest(BaseModel):
    story_session_id: str
    ending_text: str


class CoverageCluster(BaseModel):
    cluster_label: str
    addressed: bool
    evidence_excerpt: str
    review_reference: str


class ThemeCoverageScore(BaseModel):
    score_total: int
    breakdown: dict[str, int]
    per_cluster: list[CoverageCluster]


class SaveGenerationRequest(BaseModel):
    movie_id: str
    session_id: str
    story_session_id: str
    ending_text: str
    story_payload: dict[str, Any]
    score_payload: ThemeCoverageScore


class GenerationResponse(BaseModel):
    generation_id: str
    movie_id: str
    session_id: str
    ending_text: str
    votes: int
    score_total: int
    created_at: datetime


class GenerationDetailResponse(BaseModel):
    """Full generation for viewing saved ending (from Explore)."""
    generation_id: str
    movie_id: str
    movie_title: str
    ending_text: str
    votes: int
    score_total: int
    created_at: datetime
    story_payload: dict[str, Any] = {}
    score_payload: ThemeCoverageScore | None = None


class VoteRequest(BaseModel):
    session_id: str
    value: int = Field(ge=-1, le=1)


class VoteResponse(BaseModel):
    generation_id: str
    votes: int


class LeaderboardItem(BaseModel):
    generation_id: str
    movie_id: str
    movie_title: str
    ending_text: str
    votes: int
    score_total: int
    created_at: datetime
    user_vote: int | None = None  # 1 = upvoted, -1 = downvoted, None = no vote


class LeaderboardResponse(BaseModel):
    items: list[LeaderboardItem]


class EmbeddingRequest(BaseModel):
    movie_id: str


class EmbeddingResponse(BaseModel):
    movie_id: str
    chunks_indexed: int
    critics_available: bool
    status: Literal["indexed", "skipped"]


class SearchRequest(BaseModel):
    movie_id: str
    query: str
    top_k: int = Field(default=5, ge=1, le=20)


class SearchResult(BaseModel):
    chunk_id: str
    score: float
    text: str
    source: str


class SearchResponse(BaseModel):
    results: list[SearchResult]


class TTSRequest(BaseModel):
    text: str = Field(min_length=1, max_length=5000)
