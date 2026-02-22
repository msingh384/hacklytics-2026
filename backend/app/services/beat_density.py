"""Compute complaint density per plot beat by mapping review embeddings to beat embeddings."""

from __future__ import annotations

from typing import Any

import numpy as np

from app.integrations.vector_store import VectorStore
from app.services.datastore import DataStore
from app.services.embedding import EmbeddingService


def compute_beat_complaint_density(
    movie_id: str,
    store: DataStore,
    vector_store: VectorStore,
    embedder: EmbeddingService,
) -> dict[int, float]:
    """
    Map review embeddings to plot beat embeddings and compute similarity score density per beat.
    Returns beat_order -> normalized density (0-1) for heat visualization.
    """
    beats = store.get_plot_beats(movie_id)
    if not beats:
        return {}

    chunks = vector_store.list_movie_chunks(movie_id, include_vectors=True, limit=500)
    if not chunks:
        return {beat.get("beat_order", i): 0.0 for i, beat in enumerate(beats)}

    # Embed each beat: label + beat_text for semantic coverage
    beat_texts = [
        f"{b.get('label', '')} {b.get('beat_text', '')}".strip() or f"Beat {b.get('beat_order', i)}"
        for i, b in enumerate(beats)
    ]
    beat_vectors = embedder.encode(beat_texts)
    beat_orders = [b.get("beat_order", i) for i, b in enumerate(beats)]

    # Build chunk vectors
    chunk_vectors = [c.vector for c in chunks if c.vector and len(c.vector) == len(beat_vectors[0])]
    if not chunk_vectors:
        return {bo: 0.0 for bo in beat_orders}

    chunk_arr = np.array(chunk_vectors, dtype=float)
    q_norm = np.linalg.norm(chunk_arr, axis=1, keepdims=True)
    q_norm = np.where(q_norm == 0, 1.0, q_norm)
    chunk_arr = chunk_arr / q_norm

    # Per-beat: sum of cosine similarities with all chunks (complaint density)
    densities: dict[int, float] = {}
    for i, beat_vec in enumerate(beat_vectors):
        v = np.array(beat_vec, dtype=float)
        v_norm = np.linalg.norm(v)
        if v_norm == 0:
            densities[beat_orders[i]] = 0.0
            continue
        v = v / v_norm
        sims = np.dot(chunk_arr, v)
        sims = np.maximum(sims, 0)  # Only positive similarity (complaint relevance)
        densities[beat_orders[i]] = float(np.sum(sims))

    # Normalize to 0-1 for heat scale
    max_d = max(densities.values()) if densities else 0
    if max_d > 0:
        densities = {k: v / max_d for k, v in densities.items()}
    return densities
