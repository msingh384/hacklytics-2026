from __future__ import annotations

import math
import re
from collections import Counter, defaultdict
from typing import Any

import numpy as np

from app.integrations.gemini import GeminiClient
from app.integrations.vector_store import VectorStore
from app.utils.text import stable_id

try:
    from sklearn.cluster import KMeans
except ImportError:  # pragma: no cover
    KMeans = None


_WORD_RE = re.compile(r"[a-zA-Z]{4,}")
_STOP = {
    "this",
    "that",
    "with",
    "from",
    "they",
    "their",
    "there",
    "were",
    "have",
    "about",
    "would",
    "could",
    "movie",
    "film",
}


def _summarize_texts(texts: list[str]) -> str:
    words = Counter()
    for text in texts:
        for word in _WORD_RE.findall(text.lower()):
            if word in _STOP:
                continue
            words[word] += 1
    if not words:
        return "Audience concern cluster"
    top = ", ".join([word for word, _ in words.most_common(5)])
    return f"Recurring concerns: {top}"


def _fallback_label_from_texts(texts: list[str], cluster_pos: int) -> str:
    words = Counter()
    for text in texts:
        for word in _WORD_RE.findall(text.lower()):
            if word in _STOP:
                continue
            words[word] += 1
    if not words:
        return f"Concern {cluster_pos}"
    top = [word.title() for word, _ in words.most_common(2)]
    if len(top) == 1:
        return top[0]
    return " ".join(top)


def _normalize_label(label: str) -> str:
    clean = re.sub(r"\s+", " ", label.strip())
    return clean


def _is_generic_label(label: str) -> bool:
    return bool(re.fullmatch(r"(theme|cluster|concern)\s*\d*", label.strip(), flags=re.IGNORECASE))


def _finalize_labels(generated: list[str], cluster_texts: list[list[str]]) -> list[str]:
    output: list[str] = []
    used: set[str] = set()

    for idx, texts in enumerate(cluster_texts, start=1):
        candidate = generated[idx - 1] if idx - 1 < len(generated) else ""
        candidate = _normalize_label(candidate)
        if not candidate or _is_generic_label(candidate):
            candidate = _fallback_label_from_texts(texts, idx)

        base = candidate
        suffix = 2
        while candidate.lower() in used:
            candidate = f"{base} {suffix}"
            suffix += 1
        used.add(candidate.lower())
        output.append(candidate)

    return output


def cluster_review_chunks(
    movie_id: str,
    movie_title: str,
    chunks: list[dict[str, Any]],
    vectors: list[list[float]],
    gemini: GeminiClient,
    max_clusters: int = 7,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if not chunks or not vectors:
        return [], []

    n_samples = len(vectors)
    cluster_count = min(max_clusters, max(1, min(4, n_samples)))
    if n_samples >= 10:
        cluster_count = min(max_clusters, max(3, int(math.sqrt(n_samples))))

    data = np.array(vectors)

    if KMeans is not None and len(chunks) > 1 and cluster_count > 1:
        model = KMeans(n_clusters=cluster_count, random_state=42, n_init=10)
        labels = model.fit_predict(data).tolist()
    else:
        labels = [idx % cluster_count for idx in range(n_samples)]

    groups: dict[int, list[int]] = defaultdict(list)
    for idx, label in enumerate(labels):
        groups[int(label)].append(idx)

    ordered_groups = sorted(groups.items(), key=lambda item: len(item[1]), reverse=True)[:max_clusters]
    clusters: list[dict[str, Any]] = []
    examples: list[dict[str, Any]] = []

    cluster_payloads: list[dict[str, Any]] = []
    cluster_texts: list[list[str]] = []
    for cluster_pos, (raw_label, indices) in enumerate(ordered_groups, start=1):
        cluster_id = stable_id(movie_id, "cluster", str(raw_label), str(cluster_pos))
        top_indices = indices[:3]
        top_reviews = [
            chunks[i].get("full_review_text") or chunks[i]["text"]
            for i in top_indices
        ]
        cluster_texts.append([chunks[i].get("full_review_text") or chunks[i]["text"] for i in indices])
        cluster_payloads.append({
            "cluster_id": cluster_id,
            "review_count": len(indices),
            "top_reviews": top_reviews,
        })

    generated_labels = _finalize_labels(
        gemini.label_clusters_from_full_reviews(movie_title, cluster_payloads),
        cluster_texts,
    )

    for cluster_pos, ((raw_label, indices), label) in enumerate(zip(ordered_groups, generated_labels), start=1):
        cluster_id = stable_id(movie_id, "cluster", str(raw_label), str(cluster_pos))
        texts = [chunks[i]["text"] for i in indices]
        summary = _summarize_texts(texts)

        clusters.append(
            {
                "movie_id": movie_id,
                "cluster_id": cluster_id,
                "label": label,
                "summary": summary,
                "review_count": len(indices),
            }
        )

        for example_pos, idx in enumerate(indices[:3], start=1):
            chunk = chunks[idx]
            full_text = chunk.get("full_review_text") or chunk["text"]
            examples.append(
                {
                    "movie_id": movie_id,
                    "cluster_id": cluster_id,
                    "example_id": stable_id(cluster_id, chunk["chunk_id"], str(example_pos)),
                    "review_text": full_text,
                    "source": chunk.get("source", "user"),
                    "review_reference": chunk["chunk_id"],
                }
            )

    return clusters, examples


def cluster_review_chunks_from_vector_store(
    movie_id: str,
    movie_title: str,
    vector_store: VectorStore,
    gemini: GeminiClient,
    max_clusters: int = 7,
    chunk_metadata: dict[str, dict[str, Any]] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    indexed_chunks = vector_store.list_movie_chunks(movie_id, include_vectors=True)
    if not indexed_chunks:
        return [], []

    chunks: list[dict[str, Any]] = []
    vectors: list[list[float]] = []
    for item in indexed_chunks:
        if not item.chunk_id or not item.vector:
            continue
        meta = chunk_metadata.get(item.chunk_id, {}) if chunk_metadata else {}
        chunks.append(
            {
                "chunk_id": item.chunk_id,
                "movie_id": item.movie_id,
                "text": item.text,
                "source": item.source,
                "full_review_text": meta.get("full_review_text") or meta.get("text") or item.text,
            }
        )
        vectors.append(item.vector)

    if not chunks or not vectors:
        return [], []

    return cluster_review_chunks(
        movie_id,
        movie_title,
        chunks,
        vectors,
        gemini,
        max_clusters,
    )
