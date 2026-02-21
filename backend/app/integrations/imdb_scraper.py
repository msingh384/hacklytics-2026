from __future__ import annotations

import json
import re
from dataclasses import dataclass

import requests
from bs4 import BeautifulSoup

from app.utils.text import parse_rating, stable_id


HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Accept-Language": "en-US,en;q=0.9",
}


@dataclass
class ScrapedReview:
    review_id: str
    title: str | None
    text: str
    rating: float | None
    author: str | None
    created_at: str | None
    permalink: str | None
    helpful_count: int | None


def _normalize_imdb_id(movie_id: str) -> str:
    cleaned = movie_id.strip().lower()
    return cleaned if cleaned.startswith("tt") else f"tt{cleaned}"


def _extract_pagination_key(html: str) -> str | None:
    soup = BeautifulSoup(html, "html.parser")
    load_more = soup.find("button", attrs={"id": "load-more-trigger"})
    if load_more and load_more.get("data-key"):
        return str(load_more.get("data-key"))

    next_data = soup.find("script", attrs={"id": "__NEXT_DATA__"})
    if not next_data or not next_data.string:
        return None

    try:
        payload = json.loads(next_data.string)
        node = payload.get("props", {}).get("pageProps", {}).get("contentData", {})
        reviews = node.get("data", {}).get("title", {}).get("reviews", {})
        return reviews.get("pageInfo", {}).get("endCursor")
    except Exception:
        return None


def _extract_helpful_count(text: str | None) -> int | None:
    if not text:
        return None
    match = re.search(r"(\d+)\s+out of", text)
    if match:
        return int(match.group(1))
    match = re.search(r"(\d+)", text)
    return int(match.group(1)) if match else None


def _parse_reviews(html: str) -> list[ScrapedReview]:
    soup = BeautifulSoup(html, "html.parser")
    items: list[ScrapedReview] = []
    for article in soup.find_all("article"):
        css_classes = " ".join(article.get("class", []))
        if "user-review-item" not in css_classes:
            continue

        title_el = article.find("a", href=lambda x: bool(x and "/review/" in x))
        title = title_el.get_text(strip=True) if title_el else None

        content_el = article.find(class_=lambda c: bool(c and "ipc-html-content" in c))
        if not content_el:
            continue
        text = content_el.get_text(" ", strip=True)
        if not text:
            continue

        rating_el = article.find(class_=lambda c: bool(c and "rating-other-user-rating" in c))
        rating = parse_rating(rating_el.get_text(strip=True) if rating_el else None)

        author_el = article.find(class_=lambda c: bool(c and "display-name-link" in c))
        author = author_el.get_text(strip=True) if author_el else None

        date_el = article.find(class_=lambda c: bool(c and "review-date" in c))
        created_at = date_el.get_text(strip=True) if date_el else None

        helpful_el = article.find(class_=lambda c: bool(c and "actions" in c))
        helpful_count = _extract_helpful_count(helpful_el.get_text(" ", strip=True) if helpful_el else None)

        permalink = None
        if title_el and title_el.get("href"):
            href = str(title_el.get("href"))
            permalink = f"https://www.imdb.com{href}" if href.startswith("/") else href

        review_id = stable_id(title or "", text[:120], author or "")
        items.append(
            ScrapedReview(
                review_id=review_id,
                title=title,
                text=text,
                rating=rating,
                author=author,
                created_at=created_at,
                permalink=permalink,
                helpful_count=helpful_count,
            )
        )
    return items


def scrape_imdb_reviews(movie_id: str, max_reviews: int = 800) -> list[ScrapedReview]:
    imdb_id = _normalize_imdb_id(movie_id)
    review_url = f"https://www.imdb.com/title/{imdb_id}/reviews/"

    session = requests.Session()
    session.headers.update(HEADERS)
    session.headers["Referer"] = review_url

    response = session.get(review_url, timeout=20)
    response.raise_for_status()

    collected: dict[str, ScrapedReview] = {}
    html = response.text

    for review in _parse_reviews(html):
        collected[review.review_id] = review
        if len(collected) >= max_reviews:
            return list(collected.values())

    key = _extract_pagination_key(html)
    while key and len(collected) < max_reviews:
        ajax_resp = session.get(
            f"https://www.imdb.com/title/{imdb_id}/reviews/_ajax",
            params={"paginationKey": key, "ref_": "undefined"},
            timeout=20,
        )
        if ajax_resp.status_code != 200:
            break

        html = ajax_resp.text
        for review in _parse_reviews(html):
            collected[review.review_id] = review
            if len(collected) >= max_reviews:
                break

        next_key = _extract_pagination_key(html)
        if not next_key or next_key == key:
            break
        key = next_key

    return list(collected.values())
