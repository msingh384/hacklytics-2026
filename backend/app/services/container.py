from __future__ import annotations

from dataclasses import dataclass

from app.config import Settings
from app.integrations.elevenlabs import ElevenLabsClient
from app.integrations.gemini import GeminiClient
from app.integrations.neo4j_graph import Neo4jGraph
from app.integrations.omdb import OmdbClient
from app.integrations.vector_store import VectorStore
from app.integrations.wikipedia import WikipediaPlotClient
from app.services.datastore import DataStore
from app.services.graph_ingest import GraphIngestService
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
    elevenlabs: ElevenLabsClient
    embedder: EmbeddingService
    vector_store: VectorStore
    pipeline: MoviePipelineService
    story: StoryService
    neo4j_graph: Neo4jGraph
    graph_ingest: GraphIngestService


def build_services(settings: Settings) -> ServiceContainer:
    store = DataStore(settings)
    omdb = OmdbClient(settings)
    wiki = WikipediaPlotClient(settings)
    gemini = GeminiClient(settings)
    elevenlabs = ElevenLabsClient(settings)
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
    neo4j_graph = Neo4jGraph(settings)
    graph_ingest = GraphIngestService(neo4j_graph, gemini, store)

    return ServiceContainer(
        settings=settings,
        store=store,
        omdb=omdb,
        wiki=wiki,
        gemini=gemini,
        elevenlabs=elevenlabs,
        embedder=embedder,
        vector_store=vector_store,
        pipeline=pipeline,
        story=story,
        neo4j_graph=neo4j_graph,
        graph_ingest=graph_ingest,
    )
