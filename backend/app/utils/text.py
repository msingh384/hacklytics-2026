from __future__ import annotations

import hashlib
import re
from typing import Iterable


_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")
_NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")


def normalize_title(title: str) -> str:
    return _NON_ALNUM_RE.sub(" ", title.lower()).strip()


def normalize_imdb_id(movie_id: str) -> str:
    """Ensure IMDb ID has tt prefix for consistent DB matching."""
    cleaned = (movie_id or "").strip().lower()
    return cleaned if cleaned.startswith("tt") else f"tt{cleaned}"



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
