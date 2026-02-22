#!/usr/bin/env python3
"""
Run the full pipeline for a movie WITH database writes.
Usage:
  cd backend && python -m scripts.run_full_pipeline tt1375666
  cd backend && python -m scripts.run_full_pipeline tt1375666 --force --save-output
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from app.config import get_settings
from app.services.container import build_services


async def main() -> None:
    args = [a for a in sys.argv[1:] if a not in ("--force", "--save-output")]
    force = "--force" in sys.argv
    save_output = "--save-output" in sys.argv
    movie_id = args[0] if args else "tt1375666"
    save_dir = Path(__file__).resolve().parent.parent / "pipeline_outputs" if save_output else None
    settings = get_settings()
    if not settings.has_supabase:
        print("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY required")
        sys.exit(1)

    services = build_services(settings)
    if force:
        print(f"Force mode: clearing analysis and embeddings for {movie_id}...")
        services.store.clear_analysis_for_movie(movie_id)
        n = services.vector_store.delete_for_movie(movie_id)
        print(f"  Deleted {n} review_embeddings rows")
    if save_output:
        print(f"Outputs will be saved to {save_dir}")
    print(f"Starting pipeline for movie_id={movie_id} (with DB writes)...")
    result = await services.pipeline.start_from_search(
        query=movie_id,
        year=None,
        selected_imdb_id=movie_id,
        save_dir=save_dir,
    )
    if result.status == "ready":
        print(f"Movie already prepared: {movie_id}")
        return
    if result.status == "failed":
        print(f"Failed: {result.message}")
        sys.exit(1)
    job_id = result.job_id
    print(f"Job {job_id} queued. Polling...")
    for _ in range(120):
        status = services.pipeline.get_job(job_id)
        if not status:
            print("Job not found")
            break
        print(f"  {status.stage} ({status.progress}%): {status.message}")
        if status.status == "ready":
            print(f"Done. Movie {movie_id} prepared.")
            return
        if status.status == "failed":
            print(f"Failed: {status.error}")
            sys.exit(1)
        await asyncio.sleep(2)
    print("Timeout")


if __name__ == "__main__":
    asyncio.run(main())
