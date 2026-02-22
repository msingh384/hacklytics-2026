"""Plot beat graph: beats, characters, clusters, and their relationships for visualization."""

from __future__ import annotations

from typing import Any

from app.services.datastore import DataStore


def _character_in_beat(character_name: str, beat_text: str) -> bool:
    """Check if character name appears in beat text (case-insensitive, handles partials)."""
    name_lower = character_name.strip().lower()
    text_lower = beat_text.lower()
    if not name_lower or not text_lower:
        return False
    # Handle "Dom Cobb" vs "Cobb" - check full name and last name
    parts = name_lower.split()
    return any(part in text_lower for part in parts if len(part) > 2)


def build_plot_beat_graph(
    store: DataStore,
    movie_id: str,
    beat_density: dict[str, float] | None = None,
) -> dict[str, list[dict[str, Any]]]:
    """
    Build graph from plot beats, characters, clusters for Cytoscape.js.
    Nodes: Movie, PlotBeat, Character, Cluster.
    Edges: HAS_BEAT, HAS_CHARACTER, APPEARS_IN, COMPLAINT, ADDRESSES_BEAT (cluster->beat via what-if).
    """
    movie = store.get_movie(movie_id)
    if not movie:
        return {"nodes": [], "edges": []}

    beats = store.get_plot_beats(movie_id)
    characters = store.get_characters(movie_id)
    clusters = store.get_clusters(movie_id)
    title = movie.get("title") or movie_id
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []

    # Movie node
    nodes.append({
        "data": {"id": movie_id, "label": title[:50], "type": "MOVIE"},
    })

    # Plot beat nodes
    for b in beats:
        beat_order = b.get("beat_order", 0)
        beat_id = f"{movie_id}::beat::{beat_order}"
        label = b.get("label", f"Beat {beat_order}")
        density = (beat_density or {}).get(str(beat_order), 0) if beat_density else None
        nodes.append({
            "data": {
                "id": beat_id,
                "label": label[:40],
                "type": "PLOT_BEAT",
                "beat_order": beat_order,
                "beat_text": b.get("beat_text", "")[:200],
                "complaint_density": density,
            },
        })
        edges.append({
            "data": {
                "id": f"{movie_id}-beat-{beat_order}",
                "source": movie_id,
                "target": beat_id,
                "label": "has_beat",
            },
        })

    # Character nodes + APPEARS_IN to beats
    for c in characters:
        char_id = c.get("character_id", f"{movie_id}::char::{c.get('name', '')}")
        name = c.get("name", "Unknown")
        role = c.get("role", "supporting")
        nodes.append({
            "data": {
                "id": char_id,
                "label": name[:30],
                "type": "CHARACTER",
                "role": role,
                "analysis": c.get("analysis", "")[:150],
            },
        })
        edges.append({
            "data": {
                "id": f"{movie_id}-char-{char_id}",
                "source": movie_id,
                "target": char_id,
                "label": "has_character",
            },
        })
        for b in beats:
            beat_text = b.get("beat_text", "")
            if _character_in_beat(name, beat_text):
                beat_order = b.get("beat_order", 0)
                beat_id = f"{movie_id}::beat::{beat_order}"
                edges.append({
                    "data": {
                        "id": f"{char_id}-beat-{beat_order}",
                        "source": char_id,
                        "target": beat_id,
                        "label": "appears_in",
                    },
                })

    # Cluster nodes + link to movie
    for cl in clusters:
        cid = cl.get("cluster_id", "")
        label = cl.get("tagline") or cl.get("label", "Theme")
        review_count = cl.get("review_count", 0)
        nodes.append({
            "data": {
                "id": cid,
                "label": f"{label[:25]} ({review_count})",
                "type": "CLUSTER",
                "review_count": review_count,
                "summary": cl.get("summary", "")[:100],
            },
        })
        edges.append({
            "data": {
                "id": f"{movie_id}-cluster-{cid}",
                "source": movie_id,
                "target": cid,
                "label": "complaint",
            },
        })

    return {"nodes": nodes, "edges": edges}
