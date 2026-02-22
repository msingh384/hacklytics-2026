from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from typing import Any

import requests
from bs4 import BeautifulSoup

from app.utils.text import parse_rating, stable_id


HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
}
PAGINATION_DELAY_SECONDS = 0.7
MAX_PAGES_PER_STRATEGY = 80
DEFAULT_MIN_REVIEWS = 300
MIN_REVIEW_TEXT_LEN = 40
ENTRYPOINT_STRATEGIES: tuple[dict[str, str], ...] = (
    {"sort": "helpfulnessScore", "dir": "desc", "ratingFilter": "0"},
    {"sort": "submissionDate", "dir": "desc", "ratingFilter": "0"},
    {},
)

_PAGINATION_KEY_RE = re.compile(
    r'"(?:paginationKey|endCursor|nextCursor)"\s*:\s*"([^"]+)"',
    re.IGNORECASE,
)
_QUERY_PAGINATION_RE = re.compile(
    r"[?&]paginationKey=([^&\"'>]+)",
    re.IGNORECASE,
)
_REVIEW_URL_ID_RE = re.compile(r"/review/([a-zA-Z0-9]+)/")


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


def _as_text(value: Any) -> str | None:
    if isinstance(value, str):
        text = value.strip()
        return text or None
    if isinstance(value, dict):
        for key in ("plainText", "originalText", "text", "body", "content", "value"):
            parsed = _as_text(value.get(key))
            if parsed:
                return parsed
    if isinstance(value, list):
        parts = [_as_text(item) for item in value]
        joined = " ".join([part for part in parts if part])
        return joined.strip() or None
    return None


def _as_rating(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, dict):
        for key in ("value", "rating", "ratingValue", "score"):
            if key in value:
                parsed = _as_rating(value.get(key))
                if parsed is not None:
                    return parsed
        return None
    return parse_rating(str(value)) if value is not None else None


def _as_author(value: Any) -> str | None:
    if isinstance(value, str):
        text = value.strip()
        return text or None
    if isinstance(value, dict):
        for key in ("nickName", "displayName", "name", "userName", "username"):
            item = value.get(key)
            if isinstance(item, str) and item.strip():
                return item.strip()
    return None


def _as_helpful_count(value: Any) -> int | None:
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, dict):
        for key in ("upVotes", "upvoteCount", "helpfulVotes", "helpfulCount", "value"):
            parsed = _as_helpful_count(value.get(key))
            if parsed is not None:
                return parsed
        return None
    if isinstance(value, str):
        return _extract_helpful_count(value)
    return None


def _normalize_permalink(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    link = value.strip()
    if not link:
        return None
    if link.startswith("/"):
        return f"https://www.imdb.com{link}"
    if link.startswith("http://") or link.startswith("https://"):
        return link
    return None


def _extract_review_id_from_permalink(permalink: str | None) -> str | None:
    if not permalink:
        return None
    match = _REVIEW_URL_ID_RE.search(permalink)
    return match.group(1) if match else None


def _iter_json_payloads(html: str) -> list[Any]:
    soup = BeautifulSoup(html, "html.parser")
    payloads: list[Any] = []

    next_data = soup.find("script", attrs={"id": "__NEXT_DATA__"})
    if next_data:
        raw = next_data.string or next_data.get_text(strip=False)
        if raw:
            try:
                payloads.append(json.loads(raw))
            except (json.JSONDecodeError, TypeError):
                pass

    for script in soup.find_all("script", attrs={"type": "application/json"}):
        raw = script.string or script.get_text(strip=False)
        if not raw:
            continue
        try:
            payloads.append(json.loads(raw))
        except (json.JSONDecodeError, TypeError):
            continue

    return payloads


def _collect_pagination_keys_from_json(node: Any, keys: list[str]) -> None:
    if isinstance(node, dict):
        for k, value in node.items():
            if k in {"endCursor", "paginationKey", "nextCursor"} and isinstance(value, str):
                candidate = value.strip()
                if candidate and " " not in candidate and len(candidate) > 6:
                    keys.append(candidate)
            _collect_pagination_keys_from_json(value, keys)
    elif isinstance(node, list):
        for value in node:
            _collect_pagination_keys_from_json(value, keys)


def _extract_pagination_keys(html: str) -> list[str]:
    """Extract pagination cursors for loading additional review pages."""
    keys: list[str] = []
    soup = BeautifulSoup(html, "html.parser")

    for payload in _iter_json_payloads(html):
        _collect_pagination_keys_from_json(payload, keys)

    for attr in ("data-key", "data-pagination-key"):
        for el in soup.find_all(attrs={attr: True}):
            value = el.get(attr)
            if isinstance(value, str):
                candidate = value.strip()
                if candidate and " " not in candidate and len(candidate) > 6:
                    keys.append(candidate)

    for match in _PAGINATION_KEY_RE.findall(html):
        key = match.strip()
        if key and " " not in key and len(key) > 6:
            keys.append(key)
    for match in _QUERY_PAGINATION_RE.findall(html):
        key = match.strip()
        if key and " " not in key and len(key) > 6:
            keys.append(key)

    seen: set[str] = set()
    deduped: list[str] = []
    for key in keys:
        if key in seen:
            continue
        seen.add(key)
        deduped.append(key)
    return deduped


def _extract_helpful_count(text: str | None) -> int | None:
    if not text:
        return None
    match = re.search(r"(\d+)\s+out of", text)
    if match:
        return int(match.group(1))
    match = re.search(r"(\d+)", text)
    return int(match.group(1)) if match else None


def _parse_reviews_from_dom(html: str) -> list[ScrapedReview]:
    soup = BeautifulSoup(html, "html.parser")
    items: list[ScrapedReview] = []
    for article in soup.find_all(["article", "div"]):
        css_classes = " ".join(article.get("class", []))
        if not any(token in css_classes for token in ("user-review-item", "review-container", "lister-item-content")):
            continue

        title_el = article.find("a", href=lambda x: bool(x and "/review/" in x))
        title = title_el.get_text(strip=True) if title_el else None

        content_el = article.select_one('[data-testid="review-content"]')
        if not content_el:
            content_el = article.find(class_=lambda c: bool(c and "ipc-html-content" in c))
        if not content_el:
            content_el = article.find(class_=lambda c: bool(c and "show-more__control" in c))
        if not content_el:
            content_el = article.find(class_=lambda c: bool(c and "content" in c))
        if not content_el:
            continue
        text = content_el.get_text(" ", strip=True)
        if len(text) < MIN_REVIEW_TEXT_LEN:
            continue

        rating_el = article.find(class_=lambda c: bool(c and "rating-other-user-rating" in c))
        if not rating_el:
            rating_el = article.select_one('[data-testid="review-rating"]')
        rating = parse_rating(rating_el.get_text(strip=True) if rating_el else None)

        author_el = article.find(class_=lambda c: bool(c and "display-name-link" in c))
        if not author_el:
            author_el = article.select_one('[data-testid="author-name"]')
        author = author_el.get_text(strip=True) if author_el else None

        date_el = article.find(class_=lambda c: bool(c and "review-date" in c))
        if not date_el:
            date_el = article.select_one('[data-testid="review-date"]')
        created_at = date_el.get_text(strip=True) if date_el else None

        helpful_el = article.find(class_=lambda c: bool(c and "actions" in c))
        if not helpful_el:
            helpful_el = article.select_one('[data-testid="review-actions"]')
        helpful_count = _extract_helpful_count(helpful_el.get_text(" ", strip=True) if helpful_el else None)

        permalink = None
        if title_el and title_el.get("href"):
            href = str(title_el.get("href"))
            permalink = f"https://www.imdb.com{href}" if href.startswith("/") else href

        review_id = _extract_review_id_from_permalink(permalink) or stable_id(title or "", text[:120], author or "")
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


def _coerce_review_from_json_node(node: dict[str, Any]) -> ScrapedReview | None:
    text: str | None = None
    for key in ("content", "reviewText", "text", "body", "description"):
        if key in node:
            text = _as_text(node.get(key))
            if text:
                break
    if not text or len(text) < MIN_REVIEW_TEXT_LEN:
        return None

    title = None
    for key in ("title", "headline", "summary", "reviewTitle"):
        if key in node:
            title = _as_text(node.get(key))
            if title:
                break

    rating = None
    for key in ("authorRating", "rating", "ratingValue", "userRating", "score"):
        if key in node:
            rating = _as_rating(node.get(key))
            if rating is not None:
                break

    author = None
    for key in ("author", "authorName", "user", "creator"):
        if key in node:
            author = _as_author(node.get(key))
            if author:
                break

    created_at = None
    for key in ("submissionDate", "reviewDate", "dateCreated", "createdAt", "publishedDate"):
        value = node.get(key)
        if isinstance(value, str) and value.strip():
            created_at = value.strip()
            break

    helpful_count = None
    for key in ("helpfulness", "upVotes", "upvoteCount", "helpfulVotes", "helpfulCount"):
        if key in node:
            helpful_count = _as_helpful_count(node.get(key))
            if helpful_count is not None:
                break

    permalink = None
    for key in ("reviewUrl", "permalink", "url", "href", "link"):
        if key in node:
            permalink = _normalize_permalink(node.get(key))
            if permalink:
                break

    raw_id = node.get("reviewId") or node.get("review_id") or node.get("id") or node.get("legacyId")
    review_id = str(raw_id).strip() if isinstance(raw_id, (str, int)) else None
    if review_id and "/" in review_id:
        review_id = review_id.rsplit("/", 1)[-1]
    if not review_id:
        review_id = _extract_review_id_from_permalink(permalink)

    has_review_signature = bool(review_id or permalink or author or rating is not None or created_at)
    if not has_review_signature:
        return None
    if not review_id:
        review_id = stable_id(title or "", text[:120], author or "")

    return ScrapedReview(
        review_id=review_id,
        title=title,
        text=text,
        rating=rating,
        author=author,
        created_at=created_at,
        permalink=permalink,
        helpful_count=helpful_count,
    )


def _walk_json_for_reviews(node: Any, out: list[ScrapedReview]) -> None:
    if isinstance(node, dict):
        item = _coerce_review_from_json_node(node)
        if item:
            out.append(item)
        for value in node.values():
            _walk_json_for_reviews(value, out)
    elif isinstance(node, list):
        for value in node:
            _walk_json_for_reviews(value, out)


def _parse_reviews_from_embedded_json(html: str) -> list[ScrapedReview]:
    items: list[ScrapedReview] = []
    for payload in _iter_json_payloads(html):
        _walk_json_for_reviews(payload, items)
    return items


def _merge_reviews(existing: dict[str, ScrapedReview], incoming: list[ScrapedReview], max_reviews: int) -> int:
    seen_text_keys = {stable_id(item.text[:240].lower(), item.author or "") for item in existing.values()}
    inserted = 0
    for item in incoming:
        dedupe_id = item.review_id or stable_id(item.title or "", item.text[:120], item.author or "")
        text_key = stable_id(item.text[:240].lower(), item.author or "")

        current = existing.get(dedupe_id)
        if current is not None:
            if len(item.text) > len(current.text):
                existing[dedupe_id] = item
            continue
        if text_key in seen_text_keys:
            continue

        existing[dedupe_id] = item
        seen_text_keys.add(text_key)
        inserted += 1
        if len(existing) >= max_reviews:
            break
    return inserted


def _parse_reviews(html: str) -> list[ScrapedReview]:
    merged: dict[str, ScrapedReview] = {}
    _merge_reviews(merged, _parse_reviews_from_dom(html), max_reviews=10_000)
    _merge_reviews(merged, _parse_reviews_from_embedded_json(html), max_reviews=10_000)
    return list(merged.values())


def _fetch_page(
    session: requests.Session,
    url: str,
    *,
    params: dict[str, str] | None,
    timeout_seconds: int = 25,
) -> str | None:
    try:
        response = session.get(url, params=params, timeout=timeout_seconds)
    except requests.RequestException:
        return None
    if response.status_code != 200:
        return None
    return response.text


def _fetch_next_page_html(
    session: requests.Session,
    imdb_id: str,
    pagination_key: str,
    strategy_params: dict[str, str],
) -> str | None:
    base_params = dict(strategy_params)
    base_params["paginationKey"] = pagination_key

    html = _fetch_page(
        session,
        f"https://www.imdb.com/title/{imdb_id}/reviews/_ajax",
        params={**base_params, "ref_": "undefined"},
    )
    if html:
        return html

    return _fetch_page(
        session,
        f"https://www.imdb.com/title/{imdb_id}/reviews/",
        params={**base_params, "ref_": "tt_urv"},
    )


def scrape_imdb_reviews(
    movie_id: str,
    max_reviews: int = 800,
    min_reviews: int = DEFAULT_MIN_REVIEWS,
) -> list[ScrapedReview]:
    imdb_id = _normalize_imdb_id(movie_id)
    review_url = f"https://www.imdb.com/title/{imdb_id}/reviews/"
    target_reviews = max(1, max_reviews)
    minimum_target = max(0, min(min_reviews, target_reviews))

    session = requests.Session()
    session.headers.update(HEADERS)
    session.headers["Referer"] = review_url

    collected: dict[str, ScrapedReview] = {}
    page_signatures: set[str] = set()

    for strategy_params in ENTRYPOINT_STRATEGIES:
        if len(collected) >= target_reviews:
            break

        html = _fetch_page(session, review_url, params=strategy_params)
        if not html:
            continue

        signature = stable_id(str(len(html)), html[:300])
        if signature in page_signatures:
            continue
        page_signatures.add(signature)

        _merge_reviews(collected, _parse_reviews(html), max_reviews=target_reviews)
        if len(collected) >= target_reviews:
            break

        seen_keys: set[str] = set()
        keys = _extract_pagination_keys(html)
        pages = 0
        stagnant_pages = 0

        while keys and len(collected) < target_reviews and pages < MAX_PAGES_PER_STRATEGY:
            key = next((item for item in keys if item not in seen_keys), None)
            if not key:
                break
            seen_keys.add(key)
            pages += 1
            time.sleep(PAGINATION_DELAY_SECONDS)

            next_html = _fetch_next_page_html(session, imdb_id, key, strategy_params)
            if not next_html:
                stagnant_pages += 1
                if stagnant_pages >= 2:
                    break
                continue

            page_fingerprint = stable_id(str(len(next_html)), next_html[:300])
            if page_fingerprint in page_signatures:
                stagnant_pages += 1
                if stagnant_pages >= 2:
                    break
                continue
            page_signatures.add(page_fingerprint)

            added = _merge_reviews(collected, _parse_reviews(next_html), max_reviews=target_reviews)
            if added == 0:
                stagnant_pages += 1
            else:
                stagnant_pages = 0
            if stagnant_pages >= 2:
                break

            keys = _extract_pagination_keys(next_html)

        if len(collected) >= minimum_target:
            break

    return list(collected.values())[:target_reviews]
