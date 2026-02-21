#!/usr/bin/env python3
"""
Add 25 featured movies to the movies table by fetching from OMDB API.
Run: cd backend && python -m scripts.seed_movies
Requires: SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, OMDB_API_KEY in .env
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from app.config import get_settings
from app.integrations.omdb import OmdbClient
from app.services.datastore import DataStore

# 25 movies to add (imdb_id, display_name for logging)
MOVIES = [
    ("tt0107290", "Jurassic Park"),
    ("tt1375666", "Inception"),
    ("tt0076759", "Star Wars: A New Hope"),
    ("tt0816692", "Interstellar"),
    ("tt3783958", "La La Land"),
    ("tt0088247", "The Terminator"),
    ("tt4154756", "Avengers: Infinity War"),
    ("tt4154796", "Avengers: Endgame"),
    ("tt0114709", "Toy Story"),
    ("tt0317219", "Cars"),
    ("tt0110357", "The Lion King"),
    ("tt1160419", "Dune"),
    ("tt0831387", "Godzilla"),
    ("tt5950044", "Batman v Superman: Dawn of Justice"),
    ("tt0993846", "The Wolf of Wall Street"),
    ("tt1343092", "The Great Gatsby"),
    ("tt0137523", "Fight Club"),
    ("tt0088763", "Back to the Future"),
    ("tt2096673", "Inside Out"),
    ("tt0441773", "Kung Fu Panda"),
    ("tt2119532", "Hacksaw Ridge"),
    ("tt0145487", "Spider-Man"),
    ("tt0198781", "Monsters, Inc."),
    ("tt0800369", "Thor"),
]


def main() -> None:
    settings = get_settings()
    if not settings.omdb_api_key:
        print("Set OMDB_API_KEY in .env")
        sys.exit(1)
    if not settings.has_supabase:
        print("Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY in .env")
        sys.exit(1)

    omdb = OmdbClient(settings)
    store = DataStore(settings)

    added = 0
    failed = []

    for movie_id, display_name in MOVIES:
        try:
            payload = omdb.fetch_by_imdb_id(movie_id)
            if not payload:
                failed.append((movie_id, display_name, "OMDB returned no data"))
                continue
            store.upsert_movie(payload)
            title = payload.get("Title", display_name)
            print(f"  Added: {title} ({movie_id})")
            added += 1
        except Exception as e:
            failed.append((movie_id, display_name, str(e)))
            print(f"  Failed: {display_name} ({movie_id}): {e}")

    print(f"\nDone: {added} movies added to movies table")
    if failed:
        print(f"Failed ({len(failed)}):")
        for mid, name, err in failed:
            print(f"  - {name} ({mid}): {err}")


if __name__ == "__main__":
    main()
