#!/usr/bin/env python3
"""
Seed user_reviews and critic_reviews from CSV exports.
Run from project root: python -m scripts.seed_from_csv
Requires: SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY in .env
"""
from __future__ import annotations

import csv
import os
import re
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

try:
    from supabase import create_client
except ImportError:
    print("Install supabase: pip install supabase")
    sys.exit(1)


def parse_rating(review_score: str | None) -> float | None:
    """Parse review_score (e.g. '94', '9/10', '3.5/4') to numeric 0-10."""
    if not review_score or not str(review_score).strip():
        return None
    s = str(review_score).strip()
    # "94" -> 9.4 (assume out of 100)
    m = re.match(r"^(\d+(?:\.\d+)?)\s*/\s*10$", s)
    if m:
        return float(m.group(1))
    m = re.match(r"^(\d+(?:\.\d+)?)\s*/\s*4$", s)
    if m:
        return float(m.group(1)) * 2.5  # scale to 10
    m = re.match(r"^(\d+(?:\.\d+)?)$", s)
    if m:
        v = float(m.group(1))
        return v / 10.0 if v > 10 else v  # 94 -> 9.4, 7 -> 7
    return None


def seed_user_reviews(supabase, csv_path: Path, batch_size: int = 100) -> int:
    """Seed user_reviews from CSV. Returns count inserted."""
    if not csv_path.exists():
        print(f"Missing {csv_path}")
        return 0

    rows: list[dict] = []
    seen: set[tuple[str, str]] = set()
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            movie_id = (r.get("movie_id") or "").strip()
            review_id = (r.get("id") or "").strip() or None
            key = (movie_id, review_id or "")
            if key in seen:
                continue
            seen.add(key)
            rating = None
            if r.get("rating"):
                try:
                    rating = float(r["rating"])
                except ValueError:
                    pass
            rows.append({
                "movie_id": movie_id,
                "movie_title": (r.get("movie_title") or "").strip() or None,
                "movie_review": (r.get("movie_review") or "").strip(),
                "rating": rating,
                "review_id": review_id,
            })

    total = 0
    for i in range(0, len(rows), batch_size):
        batch = rows[i : i + batch_size]
        try:
            supabase.rpc("seed_user_reviews_bulk", {"rows": batch}).execute()
            total += len(batch)
            print(f"  user_reviews: {total}/{len(rows)}")
        except Exception as e:
            print(f"  Batch error: {e}")
            raise
    return total


def seed_critic_reviews(supabase, csv_path: Path, batch_size: int = 100) -> int:
    """Seed critic_reviews from CSV. Returns count inserted."""
    if not csv_path.exists():
        print(f"Missing {csv_path}")
        return 0

    rows: list[dict] = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            year = None
            if r.get("year"):
                try:
                    year = int(r["year"])
                except ValueError:
                    pass

            review_date = None
            if r.get("review_date"):
                try:
                    from datetime import datetime
                    review_date = datetime.strptime(r["review_date"], "%Y-%m-%d").date().isoformat()
                except Exception:
                    pass

            top_critic = None
            if r.get("top_critic", "").lower() in ("true", "1", "yes"):
                top_critic = True
            elif r.get("top_critic", "").lower() in ("false", "0", "no"):
                top_critic = False

            n_candidates = None
            if r.get("n_title_candidates"):
                try:
                    n_candidates = int(r["n_title_candidates"])
                except ValueError:
                    pass

            rating = parse_rating(r.get("review_score"))

            rows.append({
                "imdb_id": (r.get("imdb_id") or "").strip() or None,
                "title": (r.get("title") or "").strip() or None,
                "review_content": (r.get("review_content") or "").strip(),
                "rating": rating,
                "critic_name": (r.get("critic_name") or "").strip() or None,
                "year": year,
                "rotten_tomatoes_link": (r.get("rotten_tomatoes_link") or "").strip() or None,
                "match_method": (r.get("match_method") or "").strip() or None,
                "n_title_candidates": n_candidates,
                "top_critic": top_critic,
                "publisher_name": (r.get("publisher_name") or "").strip() or None,
                "review_type": (r.get("review_type") or "").strip() or None,
                "review_score": (r.get("review_score") or "").strip() or None,
                "review_date": review_date,
            })

    total = 0
    for i in range(0, len(rows), batch_size):
        batch = rows[i : i + batch_size]
        try:
            supabase.table("critic_reviews").insert(batch).execute()
            total += len(batch)
            print(f"  critic_reviews: {total}/{len(rows)}")
        except Exception as e:
            print(f"  Error: {e}")
            raise
    return total


def _truncate_tables(supabase) -> None:
    """Clear existing data so we can do a fresh seed.
    PostgREST limits affect deletes; we loop delete-by-id until empty."""
    for table in ("user_reviews", "critic_reviews"):
        try:
            n = 0
            while True:
                r = (
                    supabase.table(table)
                    .select("id", count="exact")
                    .limit(1000)
                    .execute()
                )
                ids = [row["id"] for row in (r.data or [])]
                if not ids:
                    break
                supabase.table(table).delete().in_("id", ids).execute()
                n += len(ids)
            print(f"  Truncated {table} ({n} rows)")
        except Exception as e:
            print(f"  Truncate {table}: {e}")


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--fresh", action="store_true", help="Truncate tables before seeding")
    args = parser.parse_args()

    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        print("Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY in .env")
        sys.exit(1)

    # CSV paths: project root (Rewrite/)
    root = Path(__file__).resolve().parent.parent.parent
    user_csv = root / "user_reviews_rows.csv"
    critic_csv = root / "critic_reviews_rows.csv"

    supabase = create_client(url, key)

    if args.fresh:
        print("Truncating tables...")
        _truncate_tables(supabase)

    print("Seeding user_reviews...")
    u_count = seed_user_reviews(supabase, user_csv)
    print(f"  Done: {u_count} rows")

    print("Seeding critic_reviews...")
    c_count = seed_critic_reviews(supabase, critic_csv)
    print(f"  Done: {c_count} rows")

    print(f"\nTotal: {u_count} user_reviews, {c_count} critic_reviews")


if __name__ == "__main__":
    main()
