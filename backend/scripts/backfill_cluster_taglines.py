#!/usr/bin/env python3
"""
Backfill taglines for existing complaint_clusters using Gemini.
Run from backend dir: python scripts/backfill_cluster_taglines.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import get_settings
from app.integrations.gemini import GeminiClient
from app.services.datastore import DataStore


def main() -> None:
    settings = get_settings()
    if not settings.has_supabase:
        print("ERROR: Supabase not configured")
        sys.exit(1)
    if not settings.gemini_api_key:
        print("ERROR: GEMINI_API_KEY not set")
        sys.exit(1)

    store = DataStore(settings)
    gemini = GeminiClient(settings)

    if not store.client:
        print("ERROR: No Supabase client")
        sys.exit(1)

    # Fetch all clusters
    rows = (
        store.client.table("complaint_clusters")
        .select("cluster_id,movie_id,label,summary,review_count")
        .execute()
        .data
        or []
    )

    if not rows:
        print("No clusters to backfill")
        return

    # Group by movie_id
    by_movie: dict[str, list[dict]] = {}
    for row in rows:
        mid = row.get("movie_id") or ""
        by_movie.setdefault(mid, []).append(row)

    print(f"Found {len(rows)} clusters across {len(by_movie)} movies", flush=True)

    updated = 0
    for movie_id, clusters in by_movie.items():
        try:
            taglines = gemini.generate_cluster_taglines(clusters)
            for idx, cluster in enumerate(clusters):
                tagline = taglines[idx] if idx < len(taglines) else f"Theme {idx + 1}"
                cluster_id = cluster.get("cluster_id")
                if cluster_id:
                    store.client.table("complaint_clusters").update({"tagline": tagline}).eq(
                        "cluster_id", cluster_id
                    ).execute()
                    updated += 1
                    print(f"  {movie_id} {cluster_id[:8]}... -> {tagline!r}", flush=True)
        except Exception as e:
            print(f"  ERROR {movie_id}: {e}")

    print(f"\nUpdated {updated} clusters with taglines", flush=True)


if __name__ == "__main__":
    main()
