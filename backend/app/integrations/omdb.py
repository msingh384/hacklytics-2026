from __future__ import annotations

from typing import Any

import requests

from app.config import Settings
from app.schemas import MovieCandidate
from app.utils.text import extract_omdb_scores


class OmdbClient:
    BASE_URL = "https://www.omdbapi.com/"

    def __init__(self, settings: Settings):
        self.settings = settings
        self.session = requests.Session()

    def _request(self, params: dict[str, Any]) -> dict[str, Any]:
        if not self.settings.omdb_api_key:
            raise RuntimeError("OMDB_API_KEY is missing")
        final_params = {"apikey": self.settings.omdb_api_key, "r": "json", **params}
        response = self.session.get(
            self.BASE_URL,
            params=final_params,
            timeout=self.settings.request_timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()
        return payload

    def search_by_title(self, query: str, year: str | None = None) -> list[MovieCandidate]:
        payload = self._request({"s": query, "type": "movie", **({"y": year} if year else {})})
        if payload.get("Response") == "False":
            return []

        results = payload.get("Search", [])
        candidates: list[MovieCandidate] = []
        for item in results:
            candidates.append(
                MovieCandidate(
                    movie_id=item.get("imdbID", ""),
                    title=item.get("Title", ""),
                    year=item.get("Year"),
                    poster=None if item.get("Poster") == "N/A" else item.get("Poster"),
                )
            )
        return candidates

    def fetch_by_imdb_id(self, movie_id: str) -> dict[str, Any] | None:
        payload = self._request({"i": movie_id, "plot": "full"})
        if payload.get("Response") == "False":
            return None
        return payload

    def hydrate_candidate(self, movie_id: str) -> MovieCandidate | None:
        payload = self.fetch_by_imdb_id(movie_id)
        if not payload:
            return None
        imdb_rating, rotten_tomatoes, audience_score = extract_omdb_scores(payload)
        return MovieCandidate(
            movie_id=payload.get("imdbID", movie_id),
            title=payload.get("Title", ""),
            year=payload.get("Year"),
            genre=payload.get("Genre"),
            poster=None if payload.get("Poster") == "N/A" else payload.get("Poster"),
            imdb_rating=imdb_rating,
            rotten_tomatoes=rotten_tomatoes,
            audience_score=audience_score,
        )
