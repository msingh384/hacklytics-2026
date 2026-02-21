from __future__ import annotations

import re
import time
from typing import Any

import requests
from bs4 import BeautifulSoup, Tag

from app.config import Settings
from app.utils.text import normalize_title


_CITATION_RE = re.compile(r"\[\d+\]")
_WS_RE = re.compile(r"\s+")


class WikipediaPlotClient:
    API_URL = "https://en.wikipedia.org/w/api.php"

    def __init__(self, settings: Settings):
        self.settings = settings
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": settings.wikipedia_user_agent})

    def _request(self, params: dict[str, Any]) -> dict[str, Any]:
        response = self.session.get(
            self.API_URL,
            params={"format": "json", **params},
            timeout=self.settings.request_timeout_seconds,
        )
        response.raise_for_status()
        return response.json()

    def _search_candidates(self, title: str, year: str | None) -> list[str]:
        query = f"{title} ({year} film)" if year else f"{title} film"
        data = self._request(
            {
                "action": "query",
                "list": "search",
                "srsearch": query,
                "srlimit": 10,
            }
        )
        results = data.get("query", {}).get("search", [])
        return [item.get("title", "") for item in results if item.get("title")]

    def _score_candidate(self, title: str, year: str | None, candidate: str) -> int:
        score = 0
        norm_target = normalize_title(title)
        norm_candidate = normalize_title(candidate)

        if norm_target in norm_candidate:
            score += 5
        if "film" in norm_candidate or "movie" in norm_candidate:
            score += 3
        if year and year in candidate:
            score += 4
        if "disambiguation" in norm_candidate:
            score -= 5
        return score

    def _pick_page(self, title: str, year: str | None) -> str | None:
        candidates = self._search_candidates(title, year)
        if not candidates:
            return None
        ranked = sorted(candidates, key=lambda c: self._score_candidate(title, year, c), reverse=True)
        return ranked[0]

    def _extract_plot_from_html(self, html_fragment: str) -> str | None:
        soup = BeautifulSoup(html_fragment, "html.parser")

        heading = soup.find("span", attrs={"id": "Plot"})
        if heading is None:
            for h2 in soup.find_all("h2"):
                text = h2.get_text(" ", strip=True)
                if text == "Plot":
                    heading = h2
                    break

        if heading is None:
            return None

        start_node: Tag | None
        if heading.name == "span":
            start_node = heading.find_parent("h2")
        else:
            start_node = heading

        if start_node is None:
            return None

        chunks: list[str] = []
        node = start_node.find_next_sibling()
        while node is not None:
            if isinstance(node, Tag) and node.name == "h2":
                break
            if isinstance(node, Tag) and node.name in {"p", "ul", "ol"}:
                chunks.append(node.get_text(" ", strip=True))
            node = node.find_next_sibling()

        raw = "\n".join([chunk for chunk in chunks if chunk])
        cleaned = _WS_RE.sub(" ", _CITATION_RE.sub("", raw)).strip()
        return cleaned or None

    def fetch_plot(self, movie_title: str, movie_year: str | None) -> tuple[str, str] | None:
        page = self._pick_page(movie_title, movie_year)
        if not page:
            return None

        time.sleep(1)
        payload = self._request(
            {
                "action": "parse",
                "page": page,
                "prop": "text",
                "disableeditsection": 1,
                "redirects": 1,
            }
        )

        html = payload.get("parse", {}).get("text", {}).get("*", "")
        if not html:
            return None

        plot = self._extract_plot_from_html(html)
        if not plot:
            return None

        page_title = payload.get("parse", {}).get("title", page)
        return plot, page_title
