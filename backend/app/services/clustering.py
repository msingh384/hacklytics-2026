from __future__ import annotations

import math
import re
from collections import Counter, defaultdict
from typing import Any

import numpy as np

from app.integrations.gemini import GeminiClient
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
    label_input: list[list[str]] = []
    for _, indices in ordered_groups:
        label_input.append([chunks[i]["text"][:220] for i in indices[:4]])
    generated_labels = gemini.label_clusters(movie_title, label_input)

    clusters: list[dict[str, Any]] = []
    examples: list[dict[str, Any]] = []

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
            examples.append(
                {
                    "movie_id": movie_id,
                    "cluster_id": cluster_id,
                    "example_id": stable_id(cluster_id, chunk["chunk_id"], str(example_pos)),
                    "review_text": chunk["text"],
                    "source": chunk.get("source", "user"),
                    "review_reference": chunk["chunk_id"],
                }
            )

    return clusters, examples
