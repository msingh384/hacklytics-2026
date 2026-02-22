"""
Wikipedia plot scraper using Parsoid REST API.
Extracted from wiki_scraper.ipynb - fetches Plot section from a movie's Wikipedia page.
"""
from __future__ import annotations

import re
from urllib.parse import quote

import requests
from bs4 import BeautifulSoup


def _clean_wiki_text(s: str) -> str:
    """Remove citation markers and normalize whitespace."""
    s = re.sub(r"\[(?:\d+|note\s*\d+|citation needed)\]", "", s, flags=re.IGNORECASE)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def get_wikipedia_plot(movie_title: str) -> tuple[str, str] | None:
    """Return the Plot section text and page title from a movie's Wikipedia page.

    Uses Parsoid REST API for consistent section markup.
    Locates the section whose heading is exactly 'Plot' (case-insensitive).

    Args:
        movie_title: The movie title to search for (e.g. "Inception", "Avengers: Endgame").

    Returns:
        (plot_text, page_title) if found, else None.

    Raises:
        ValueError: if movie_title is empty, page not found (404), or disambiguation page.
        requests.HTTPError: for other HTTP errors.
    """
    if not isinstance(movie_title, str) or not movie_title.strip():
        raise ValueError("movie_title must be a non-empty string")

    title = movie_title.strip()
    slug = title.replace(" ", "_")
    rest_url = f"https://en.wikipedia.org/api/rest_v1/page/html/{quote(slug)}"
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; plot-scraper/1.0; +https://example.com)",
        "Accept": "text/html; charset=utf-8",
    }

    resp = requests.get(rest_url, headers=headers, timeout=30)
    if resp.status_code == 404:
        raise ValueError(f"Wikipedia page not found (404) for title: {movie_title!r}")
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")

    title_text = soup.title.get_text(" ", strip=True) if soup.title else ""
    if "may refer to" in title_text.lower():
        raise ValueError(f"Disambiguation page encountered for {movie_title!r}")

    page_title = title_text.replace(" - Wikipedia", "").strip() or title

    plot_section = None
    for sec in soup.find_all("section"):
        hdr = sec.find(re.compile(r"^h[1-6]$"))
        if not hdr:
            continue
        hdr_txt = hdr.get_text(" ", strip=True)
        if hdr_txt and hdr_txt.strip().lower() == "plot":
            plot_section = sec
            break

    if plot_section is None:
        return None

    paragraphs = []
    for p in plot_section.find_all("p", recursive=True):
        txt = p.get_text(" ", strip=True)
        if txt:
            paragraphs.append(txt)

    if not paragraphs:
        return None

    plot_text = "\n\n".join(paragraphs)
    plot_text = _clean_wiki_text(plot_text)

    return (plot_text, page_title) if plot_text else None
