"""Cluster-centric knowledge graph built from datastore (no LLM, no Neo4j)."""

from __future__ import annotations

from typing import Any

from app.services.datastore import DataStore


def build_cluster_graph(store: DataStore, movie_id: str) -> dict[str, list[dict[str, Any]]]:
    """Build graph from movie metadata, clusters, and examples. Returns {nodes, edges} for Cytoscape."""
    movie = store.get_movie(movie_id)
    if not movie:
        return {"nodes": [], "edges": []}

    clusters = store.get_clusters(movie_id)
    if not clusters:
        return {"nodes": [], "edges": []}

    examples = store.get_cluster_examples(movie_id)
    examples_by_cluster: dict[str, list[dict[str, Any]]] = {}
    for ex in examples:
        cid = ex.get("cluster_id", "")
        if cid not in examples_by_cluster:
            examples_by_cluster[cid] = []
        examples_by_cluster[cid].append({
            "text": ex.get("review_text", ""),
            "source": ex.get("source", "user"),
        })

    title = movie.get("title") or movie_id
    genre = movie.get("genre")
    imdb = movie.get("imdb_rating")
    rt = movie.get("rotten_tomatoes")
    audience = movie.get("audience_score")

    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []

    # Movie node
    nodes.append({
        "data": {"id": movie_id, "label": title[:50], "type": "MOVIE"},
    })

    # Genre node
    if genre:
        genre_id = f"{movie_id}::genre"
        nodes.append({"data": {"id": genre_id, "label": genre, "type": "GENRE"}})
        edges.append({
            "data": {"id": f"{movie_id}-genre", "source": movie_id, "target": genre_id, "label": "genre"},
        })

    # Rating nodes
    if imdb is not None:
        rid = f"{movie_id}::imdb"
        nodes.append({"data": {"id": rid, "label": f"IMDB {imdb}", "type": "RATING"}})
        edges.append({
            "data": {"id": f"{movie_id}-imdb", "source": movie_id, "target": rid, "label": "rating"},
        })
    if rt:
        rid = f"{movie_id}::rt"
        nodes.append({"data": {"id": rid, "label": f"RT {rt}", "type": "RATING"}})
        edges.append({
            "data": {"id": f"{movie_id}-rt", "source": movie_id, "target": rid, "label": "rating"},
        })
    if audience:
        rid = f"{movie_id}::audience"
        nodes.append({"data": {"id": rid, "label": f"Audience {audience}", "type": "RATING"}})
        edges.append({
            "data": {"id": f"{movie_id}-audience", "source": movie_id, "target": rid, "label": "rating"},
        })

    # Cluster nodes with examples
    for c in clusters:
        cid = c.get("cluster_id", "")
        label = c.get("tagline") or c.get("label", "Theme")
        review_count = c.get("review_count", 0)
        examples_list = examples_by_cluster.get(cid, [])[:5]
        nodes.append({
            "data": {
                "id": cid,
                "label": f"{label} ({review_count})",
                "type": "CLUSTER",
                "review_count": review_count,
                "summary": c.get("summary", ""),
                "examples": examples_list,
            },
        })
        edges.append({
            "data": {
                "id": f"{movie_id}-{cid}",
                "source": movie_id,
                "target": cid,
                "label": "complaint",
            },
        })

    return {"nodes": nodes, "edges": edges}
