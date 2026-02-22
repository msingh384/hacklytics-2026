"""Neo4j graph store for movie knowledge graphs."""

from __future__ import annotations

import logging
from typing import Any

from app.config import Settings
from app.utils.text import stable_id

logger = logging.getLogger(__name__)

try:
    from neo4j import GraphDatabase
except ImportError:
    GraphDatabase = None


class Neo4jGraph:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._driver = None
        self._enabled = bool(
            settings.neo4j_password
            and GraphDatabase is not None
        )

        if self._enabled:
            try:
                self._driver = GraphDatabase.driver(
                    settings.neo4j_uri,
                    auth=(settings.neo4j_user, settings.neo4j_password),
                )
                self._driver.verify_connectivity()
                self._ensure_schema()
            except Exception:
                logger.warning("Neo4j connection failed, graph features disabled", exc_info=True)
                self._enabled = False
                if self._driver:
                    try:
                        self._driver.close()
                    except Exception:
                        pass
                    self._driver = None

    @property
    def enabled(self) -> bool:
        return self._enabled

    def verify_connectivity(self) -> bool:
        if not self._driver:
            return False
        try:
            self._driver.verify_connectivity()
            return True
        except Exception:
            return False

    def _ensure_schema(self) -> None:
        with self._driver.session() as session:
            session.run(
                "CREATE CONSTRAINT movie_id IF NOT EXISTS FOR (m:Movie) REQUIRE m.movie_id IS UNIQUE"
            )
            session.run(
                "CREATE CONSTRAINT chunk_id IF NOT EXISTS FOR (c:Chunk) REQUIRE c.chunk_id IS UNIQUE"
            )
            session.run(
                "CREATE CONSTRAINT entity_id IF NOT EXISTS FOR (e:Entity) REQUIRE e.entity_id IS UNIQUE"
            )

    def _run(self, query: str, parameters: dict[str, Any] | None = None) -> list[dict]:
        if not self._driver:
            return []
        with self._driver.session() as session:
            result = session.run(query, parameters or {})
            return [dict(record) for record in result]

    def upsert_movie_chunk_entities(
        self,
        movie_id: str,
        movie_title: str,
        chunks: list[dict[str, Any]],
    ) -> tuple[int, int, int]:
        """Upsert Movie, Chunks, Entities, and relations. Returns (chunks, entities, relations)."""
        if not self._driver:
            return 0, 0, 0

        total_entities = 0
        total_relations = 0

        with self._driver.session() as session:
            session.run(
                """
                MERGE (m:Movie {movie_id: $movie_id})
                ON CREATE SET m.title = $title
                ON MATCH SET m.title = $title
                """,
                {"movie_id": movie_id, "title": movie_title},
            )

            for chunk_data in chunks:
                chunk_id = chunk_data["chunk_id"]
                text = chunk_data.get("text", "")[:10000]
                idx = chunk_data.get("idx", 0)

                session.run(
                    """
                    MATCH (m:Movie {movie_id: $movie_id})
                    MERGE (c:Chunk {chunk_id: $chunk_id})
                    ON CREATE SET c.movie_id = $movie_id, c.text = $text, c.idx = $idx
                    ON MATCH SET c.text = $text, c.idx = $idx
                    WITH m, c
                    MERGE (m)-[:HAS_CHUNK]->(c)
                    """,
                    {
                        "movie_id": movie_id,
                        "chunk_id": chunk_id,
                        "text": text,
                        "idx": idx,
                    },
                )

                entities = chunk_data.get("entities", [])
                for ent in entities:
                    name = str(ent.get("name", "")).strip()[:500]
                    etype = str(ent.get("type", "CONCEPT")).upper()[:50]
                    if not name:
                        continue
                    if etype not in (
                        "CHARACTER",
                        "LOCATION",
                        "OBJECT",
                        "EVENT",
                        "ORG",
                        "CONCEPT",
                    ):
                        etype = "CONCEPT"
                    entity_id = stable_id(movie_id, name)

                    session.run(
                        """
                        MERGE (e:Entity {entity_id: $entity_id})
                        ON CREATE SET e.name = $name, e.type = $type
                        ON MATCH SET e.name = $name, e.type = $type
                        WITH e
                        MATCH (c:Chunk {chunk_id: $chunk_id})
                        MERGE (c)-[:MENTIONS]->(e)
                        """,
                        {
                            "entity_id": entity_id,
                            "name": name,
                            "type": etype,
                            "chunk_id": chunk_id,
                        },
                    )
                    total_entities += 1

                relations = chunk_data.get("relations", [])
                for rel in relations:
                    s_name = str(rel.get("source", "")).strip()[:500]
                    t_name = str(rel.get("target", "")).strip()[:500]
                    rtype = str(rel.get("type", "RELATED_TO"))[:100]
                    conf = float(rel.get("confidence", 0.8))
                    if not s_name or not t_name or s_name == t_name:
                        continue
                    s_id = stable_id(movie_id, s_name)
                    t_id = stable_id(movie_id, t_name)

                    session.run(
                        """
                        MATCH (a:Entity {entity_id: $source_id})
                        MATCH (b:Entity {entity_id: $target_id})
                        MERGE (a)-[r:REL]->(b)
                        ON CREATE SET r.type = $rtype, r.chunk_id = $chunk_id, r.confidence = $conf
                        ON MATCH SET r.type = $rtype, r.chunk_id = $chunk_id, r.confidence = $conf
                        """,
                        {
                            "source_id": s_id,
                            "target_id": t_id,
                            "rtype": rtype,
                            "chunk_id": chunk_id,
                            "conf": conf,
                        },
                    )
                    total_relations += 1

        return len(chunks), total_entities, total_relations

    def get_graph(self, movie_id: str, limit: int = 100) -> dict[str, list]:
        """Return nodes and edges formatted for Cytoscape.js."""
        if not self._driver:
            return {"nodes": [], "edges": []}

        with self._driver.session() as session:
            nodes_result = session.run(
                """
                MATCH (m:Movie {movie_id: $movie_id})-[:HAS_CHUNK]->(c:Chunk)-[:MENTIONS]->(e:Entity)
                WITH DISTINCT e
                LIMIT $limit
                RETURN e.entity_id AS id, e.name AS name, e.type AS type
                """,
                {"movie_id": movie_id, "limit": limit},
            )
            nodes = []
            seen = set()
            for r in nodes_result:
                nid = r["id"]
                if nid in seen:
                    continue
                seen.add(nid)
                nodes.append(
                    {
                        "data": {
                            "id": nid,
                            "label": r["name"],
                            "type": r["type"] or "CONCEPT",
                        },
                    }
                )

            entity_ids = list(seen)
            if not entity_ids:
                return {"nodes": [], "edges": []}

            edges_result = session.run(
                """
                MATCH (a:Entity)-[r:REL]->(b:Entity)
                WHERE a.entity_id IN $ids AND b.entity_id IN $ids
                RETURN a.entity_id AS source, b.entity_id AS target, r.type AS type, r.chunk_id AS chunk_id
                LIMIT $limit
                """,
                {"ids": entity_ids, "limit": limit * 2},
            )
            edges = []
            edge_set = set()
            for r in edges_result:
                key = (r["source"], r["target"], r.get("chunk_id") or "")
                if key in edge_set:
                    continue
                edge_set.add(key)
                edge_id = f"{r['source']}-{r['target']}-{r.get('chunk_id', '')}"
                edges.append(
                    {
                        "data": {
                            "id": edge_id,
                            "source": r["source"],
                            "target": r["target"],
                            "label": r["type"] or "RELATED_TO",
                            "chunk_id": r.get("chunk_id"),
                        },
                    }
                )

        return {"nodes": nodes, "edges": edges}

    def get_chunk_text(self, chunk_id: str) -> str | None:
        if not self._driver:
            return None
        rows = self._run(
            "MATCH (c:Chunk {chunk_id: $chunk_id}) RETURN c.text AS text",
            {"chunk_id": chunk_id},
        )
        if rows and rows[0].get("text"):
            return str(rows[0]["text"])
        return None

    def close(self) -> None:
        if self._driver:
            try:
                self._driver.close()
            except Exception:
                pass
            self._driver = None
