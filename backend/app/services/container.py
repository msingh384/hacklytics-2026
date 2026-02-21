from __future__ import annotations

from dataclasses import dataclass

from app.config import Settings
from app.integrations.gemini import GeminiClient
from app.integrations.omdb import OmdbClient
from app.integrations.vector_store import VectorStore
from app.integrations.wikipedia import WikipediaPlotClient
from app.services.datastore import DataStore
from app.services.embedding import EmbeddingService
from app.services.pipeline import MoviePipelineService
from app.services.story import StoryService


@dataclass
class ServiceContainer:
    settings: Settings
    store: DataStore
    omdb: OmdbClient
    wiki: WikipediaPlotClient
    gemini: GeminiClient
    embedder: EmbeddingService
    vector_store: VectorStore
    pipeline: MoviePipelineService
    story: StoryService


def build_services(settings: Settings) -> ServiceContainer:
    store = DataStore(settings)
    omdb = OmdbClient(settings)
    wiki = WikipediaPlotClient(settings)
    gemini = GeminiClient(settings)
    embedder = EmbeddingService(settings)
    vector_store = VectorStore(settings)
    pipeline = MoviePipelineService(
        store=store,
        omdb=omdb,
        wiki=wiki,
        gemini=gemini,
        embedder=embedder,
        vector_store=vector_store,
    )
    story = StoryService(gemini)

    return ServiceContainer(
        settings=settings,
        store=store,
        omdb=omdb,
        wiki=wiki,
        gemini=gemini,
        embedder=embedder,
        vector_store=vector_store,
        pipeline=pipeline,
        story=story,
    )
