"""
Wikipedia plot client - uses wiki_scraper for Parsoid-based Plot section extraction.
"""
from __future__ import annotations

import logging

from app.config import Settings
from app.integrations.wiki_scraper import get_wikipedia_plot

logger = logging.getLogger(__name__)


class WikipediaPlotClient:
    """Fetches plot summaries from Wikipedia using the Parsoid REST API."""

    def __init__(self, settings: Settings):
        self.settings = settings

    def fetch_plot(self, movie_title: str, movie_year: str | None) -> tuple[str, str] | None:
        """Fetch the Plot section from a movie's Wikipedia page.

        Args:
            movie_title: The movie title (e.g. "Inception", "Avengers: Endgame").
            movie_year: Optional year; used to form "Title (year) film" if direct lookup fails.

        Returns:
            (plot_text, page_title) if found, else None.
        """
        if not movie_title or not str(movie_title).strip():
            return None

        title = str(movie_title).strip()

        # Try direct title first (e.g. "Inception", "Avengers: Endgame")
        result = self._try_fetch(title)
        if result is not None:
            return result

        # Fallback: try "Title (film)" for generic film pages
        if movie_year:
            result = self._try_fetch(f"{title} ({movie_year} film)")
            if result is not None:
                return result
        result = self._try_fetch(f"{title} (film)")
        if result is not None:
            return result

        return None

    def _try_fetch(self, title: str) -> tuple[str, str] | None:
        try:
            return get_wikipedia_plot(title)
        except (ValueError, Exception) as e:
            logger.debug("Wikipedia fetch failed for %r: %s", title, e)
            return None
