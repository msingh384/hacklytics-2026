# Basic Backend Prompt: IMDb Scraper + FastAPI + Supabase

Use this as a spec to rebuild a **simpler** IMDb-reviews backend in another application. All logic is described in one place; optional single-file code at the end.

---

## 1. Where IMDb Scraping Lives (This Project)

- **File:** `app/scraper.py`
- **Role:** Fetches IMDb user reviews for a movie by **IMDb title ID** (e.g. `tt0468569`).
- **How it works:**
  - Opens `https://www.imdb.com/title/{imdb_id}/reviews/`.
  - Parses HTML with **BeautifulSoup** (looks for `<article class="... user-review-item">`, then title, rating, content, date, username, permalink, helpful count).
  - To get more than the first ~25 reviews it either:
    - Uses **Playwright** to click “See all” / “25 more” and keep loading, or
    - Uses **requests** + IMDb’s `_ajax` endpoint with a pagination key from `__NEXT_DATA__` (first page + one _ajax pass).
  - Exposes a generator: `_scrape_imdb_reviews_up_to(imdb_id, max_reviews=1000)` that yields dicts like `{ "title", "content", "rating", "date", "username", "permalink", "imdb_review_id", "helpful_count" }`.

So: **scraping** = `app/scraper.py`; **API and DB** = FastAPI in `app/main.py` + Supabase in `app/supabase_client.py`.

---

## 2. How It’s Built With FastAPI (Current App)

- **FastAPI app:** `app/main.py`
- **Supabase:** `app/supabase_client.py` — `get_supabase()` returns a client; needs `SUPABASE_URL` and `SUPABASE_ANON_KEY` in `.env`.
- **Table:** `reviews` with columns such as: `movie_id`, `movie_title`, `movie_review`, `rating` (numeric), `created_at`.
- **Flow:**
  - **POST /scrape** (body: `{ "imdb_id": "tt0468569" }`) → calls scraper, maps each review to a row, inserts into `reviews` in batches (e.g. 50).
  - **GET /reviews/{imdb_id}** → reads from Supabase `reviews` where `movie_id = imdb_id`, returns list (with optional skip/limit).

---

## 3. Simpler Rebuild: Routes to Implement

Keep only two main behaviors:

### POST — Add a scraped movie to Supabase

- **Route:** `POST /scrape` or `POST /movies`
- **Body (JSON):** `{ "imdb_id": "tt0468569" }` (optional: `"max_reviews": 500` to cap how many to scrape)
- **Behavior:**
  1. Normalize `imdb_id` (e.g. ensure `tt` prefix).
  2. Call the IMDb scraper for that ID (same logic as `app/scraper.py`).
  3. Optionally fetch movie title from the same IMDb page (e.g. from `<title>` or `<h1>`).
  4. Map each scraped review to one row: `movie_id`, `movie_title`, `movie_review` (content), `rating` (parsed number).
  5. Insert rows into Supabase table `reviews` in batches (e.g. 50) to avoid timeouts.
- **Response (JSON):** e.g. `{ "imdb_id": "tt0468569", "movie_title": "The Dark Knight", "total_stored": 500, "message": "Stored 500 reviews." }`

### GET — Get reviews from the database

- **Route:** `GET /reviews/{imdb_id}` or `GET /movies/{imdb_id}/reviews`
- **Query (optional):** `skip=0`, `limit=50` for pagination.
- **Behavior:**
  1. Normalize `imdb_id`.
  2. Query Supabase `reviews` where `movie_id = imdb_id`, order by `created_at` desc, apply skip/limit.
  3. Return total count + list of reviews (e.g. `id`, `movie_id`, `movie_title`, `movie_review`, `rating`, `created_at`).
- **Response (JSON):** e.g. `{ "imdb_id": "tt0468569", "total": 500, "reviews": [ ... ] }`

---

## 4. Dependencies (Minimal)

- **FastAPI** — web framework
- **httpx** or **requests** — HTTP for fetching IMDb (and optional title fetch)
- **beautifulsoup4** — parse IMDb HTML
- **supabase** — Supabase Python client
- **python-dotenv** — load `SUPABASE_URL`, `SUPABASE_ANON_KEY`
- Optional: **playwright** — only if you want to scrape many pages (click “See all”); otherwise requests + one _ajax page is enough for a smaller set.

---

## 5. Optional: Single-File FastAPI Backend

Below is a **minimal single-file** FastAPI app you can drop into another project. It uses **requests + BeautifulSoup** only (no Playwright), scrapes the first page + one _ajax load, and exposes:

- **POST /scrape** — add one scraped movie to Supabase
- **GET /reviews/{imdb_id}** — get stored reviews from DB

Copy into e.g. `main.py` or `app.py`, install deps, set `.env`, and run with `uvicorn main:app --reload`.

```python
# basic_backend_single_file.py — minimal IMDb scrape + Supabase, single file
import json
import os
import re
from typing import Generator

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel
from supabase import create_client

load_dotenv()

# --- Supabase ---
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "")

def get_supabase():
    if not SUPABASE_URL or not SUPABASE_ANON_KEY:
        raise ValueError("Set SUPABASE_URL and SUPABASE_ANON_KEY in .env")
    return create_client(SUPABASE_URL, SUPABASE_ANON_KEY)

# --- Scraper (simplified: requests + first page + _ajax) ---
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Accept-Language": "en-US,en;q=0.9",
}

def _parse_reviews(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    out = []
    for article in soup.find_all("article", class_=lambda c: c and "user-review-item" in str(c)):
        d = {}
        a = article.find("a", href=lambda h: h and "/review/" in str(h))
        if a: d["title"] = a.get_text(strip=True)
        r = article.find(class_=lambda c: c and "review-rating" in str(c))
        if r: d["rating"] = r.get_text(strip=True)
        c = article.find(class_=lambda c: c and "ipc-html-content" in str(c))
        if c: d["content"] = c.get_text(strip=True)
        if d.get("title") or d.get("content"):
            out.append(d)
    return out

def _pagination_key(html: str) -> str | None:
    soup = BeautifulSoup(html, "html.parser")
    script = soup.find("script", id="__NEXT_DATA__")
    if not script or not script.string:
        return None
    try:
        data = json.loads(script.string)
        title = (data.get("props", {}).get("pageProps", {}).get("contentData", {}).get("data", {}).get("title") or {})
        if isinstance(title, dict) and "reviews" in title:
            return title["reviews"].get("pageInfo", {}).get("endCursor")
    except Exception:
        pass
    return None

def scrape_imdb_reviews(imdb_id: str, max_reviews: int = 500) -> Generator[dict, None, None]:
    imdb_id = imdb_id.strip().lower()
    if not imdb_id.startswith("tt"):
        imdb_id = f"tt{imdb_id}"
    url = f"https://www.imdb.com/title/{imdb_id}/reviews/?ref_=tt_ql_urv"
    session = requests.Session()
    session.headers.update(HEADERS)
    session.headers["Referer"] = url
    r = session.get(url, timeout=15)
    r.raise_for_status()
    seen = set()
    html = r.text
    key = _pagination_key(html)
    for rev in _parse_reviews(html):
        t = rev.get("title") or rev.get("content") or ""
        if t and t not in seen:
            seen.add(t)
            yield rev
            if len(seen) >= max_reviews:
                return
    if not key or len(seen) >= max_reviews:
        return
    ajax = f"https://www.imdb.com/title/{imdb_id}/reviews/_ajax"
    r2 = session.get(ajax, params={"ref_": "tt_ql_urv", "paginationKey": key}, timeout=15)
    if r2.status_code != 200:
        return
    for rev in _parse_reviews(r2.text):
        t = rev.get("title") or rev.get("content") or ""
        if t and t not in seen:
            seen.add(t)
            yield rev
            if len(seen) >= max_reviews:
                return

def _rating_num(s: str | None) -> float | None:
    if not s or not str(s).strip():
        return None
    m = re.match(r"^(\d+(?:\.\d+)?)\s*(?:/\s*10)?$", str(s).strip())
    return float(m.group(1)) if m else None

def _movie_title(imdb_id: str) -> str | None:
    try:
        r = requests.get(
            f"https://www.imdb.com/title/{imdb_id}/reviews/",
            headers={"User-Agent": HEADERS["User-Agent"]},
            timeout=5,
        )
        if r.status_code != 200:
            return None
        soup = BeautifulSoup(r.text, "html.parser")
        t = soup.find("title")
        if t and " - User reviews" in t.get_text():
            return t.get_text().split(" - User reviews")[0].strip()
        h1 = soup.find("h1")
        if h1:
            return h1.get_text(strip=True).replace(" - User reviews", "").strip()
    except Exception:
        pass
    return None

# --- FastAPI ---
app = FastAPI(title="IMDb Reviews API", version="1.0.0")

class ScrapeBody(BaseModel):
    imdb_id: str
    max_reviews: int = 500

@app.post("/scrape")
def post_scrape(body: ScrapeBody):
    """Scrape IMDb reviews for the given movie and store them in Supabase."""
    imdb_id = body.imdb_id.strip().lower()
    if not imdb_id.startswith("tt"):
        imdb_id = f"tt{imdb_id}"
    try:
        supabase = get_supabase()
    except ValueError as e:
        raise HTTPException(status_code=503, detail=str(e))
    movie_title = _movie_title(imdb_id)
    batch, batch_size, total = [], 50, 0
    try:
        for rev in scrape_imdb_reviews(imdb_id, max_reviews=body.max_reviews):
            text = (rev.get("content") or rev.get("title") or "").strip()
            if not text:
                continue
            batch.append({
                "movie_id": imdb_id,
                "movie_title": movie_title,
                "movie_review": text,
                "rating": _rating_num(rev.get("rating")),
            })
            if len(batch) >= batch_size:
                supabase.table("reviews").insert(batch).execute()
                total += len(batch)
                batch = []
        if batch:
            supabase.table("reviews").insert(batch).execute()
            total += len(batch)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return {
        "imdb_id": imdb_id,
        "movie_title": movie_title,
        "total_stored": total,
        "message": f"Stored {total} reviews.",
    }

@app.get("/reviews/{imdb_id}")
def get_reviews(
    imdb_id: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
):
    """Get stored reviews for this movie from the database."""
    imdb_id = imdb_id.strip().lower()
    if not imdb_id.startswith("tt"):
        imdb_id = f"tt{imdb_id}"
    try:
        supabase = get_supabase()
    except ValueError as e:
        raise HTTPException(status_code=503, detail=str(e))
    r = (
        supabase.table("reviews")
        .select("id, movie_id, movie_title, movie_review, rating, created_at", count="exact")
        .eq("movie_id", imdb_id)
        .order("created_at", desc=True)
        .range(skip, skip + limit - 1)
        .execute()
    )
    return {
        "imdb_id": imdb_id,
        "total": r.count or 0,
        "reviews": r.data or [],
    }

@app.get("/")
def root():
    return {
        "message": "IMDb Reviews API",
        "docs": "/docs",
        "POST /scrape": "Body: { imdb_id, optional max_reviews }. Scrape and store in Supabase.",
        "GET /reviews/{imdb_id}": "Get stored reviews (optional ?skip=0&limit=50).",
    }
```

---

## Summary

| What            | In this repo        | In the simpler rebuild        |
|-----------------|---------------------|-------------------------------|
| IMDb scraping   | `app/scraper.py`    | Same logic or the single-file snippet above |
| POST add movie  | `POST /scrape`      | `POST /scrape` (body: `imdb_id`, optional `max_reviews`) |
| GET from DB     | `GET /reviews/{imdb_id}` | `GET /reviews/{imdb_id}` (?skip, ?limit) |
| DB              | Supabase `reviews`  | Same table shape: `movie_id`, `movie_title`, `movie_review`, `rating` |

Use **basic_backend_prompt.md** as the single reference to rebuild this backend in another app, optionally using the single-file code at the end.