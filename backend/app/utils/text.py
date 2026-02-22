from __future__ import annotations

import hashlib
import re
from typing import Iterable


_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")
_NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")


def normalize_title(title: str) -> str:
    return _NON_ALNUM_RE.sub(" ", title.lower()).strip()


def chunk_script(
    text: str,
    min_tokens: int = 400,
    max_tokens: int = 800,
    overlap_tokens: int = 100,
) -> list[str]:
    """Split script into overlapping chunks (~400-800 tokens). 1 token ≈ 4 chars."""
    text = text.strip()
    if not text:
        return []
    chars_per_token = 4
    min_chars = min_tokens * chars_per_token
    max_chars = max_tokens * chars_per_token
    overlap_chars = overlap_tokens * chars_per_token
    step = max_chars - overlap_chars
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = start + max_chars
        chunk = text[start:end]
        if not chunk.strip():
            break
        chunks.append(chunk)
        if end >= len(text):
            break
        start = end - overlap_chars
    return chunks


def split_into_review_chunks(text: str, max_sentences: int = 3) -> list[str]:
    raw_sentences = [s.strip() for s in _SENTENCE_SPLIT_RE.split(text.strip()) if s.strip()]
    if not raw_sentences:
        return []
    if len(raw_sentences) <= max_sentences:
        return [" ".join(raw_sentences)]

    chunks: list[str] = []
    bucket: list[str] = []
    for sentence in raw_sentences:
        bucket.append(sentence)
        if len(bucket) >= max_sentences:
            chunks.append(" ".join(bucket))
            bucket = []
    if bucket:
        chunks.append(" ".join(bucket))
    return chunks


def coalesce_text(parts: Iterable[str | None]) -> str:
    return " ".join([p.strip() for p in parts if p and p.strip()]).strip()


def stable_id(*parts: str) -> str:
    joined = "::".join(parts)
    return hashlib.sha1(joined.encode("utf-8")).hexdigest()[:16]


def parse_rating(value: str | None) -> float | None:
    if not value:
        return None
    match = re.search(r"(\d+(?:\.\d+)?)", str(value))
    if not match:
        return None
    try:
        return float(match.group(1))
    except ValueError:
        return None


def extract_omdb_scores(payload: dict) -> tuple[float | None, str | None, str | None]:
    imdb_rating = parse_rating(payload.get("imdbRating"))
    rotten = None
    audience = None

    ratings = payload.get("Ratings") or []
    for entry in ratings:
        source = str(entry.get("Source", ""))
        val = str(entry.get("Value", ""))
        if "Rotten Tomatoes" in source:
            rotten = val
        if "Internet Movie Database" in source and imdb_rating is None:
            imdb_rating = parse_rating(val)
        if "Metacritic" in source and audience is None:
            audience = val

    if audience is None and imdb_rating is not None:
        audience = f"{int(round(imdb_rating * 10))}%"

    return imdb_rating, rotten, audience
