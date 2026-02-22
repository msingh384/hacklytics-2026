#!/usr/bin/env python3
"""
Dry-run pipeline: run one step or all steps with NO database writes.
Only inspects responses and optionally saves JSON outputs.

Usage:
  cd backend && python -m scripts.run_pipeline_step --movie-id tt1375666 --step all
  cd backend && python -m scripts.run_pipeline_step --movie-id tt1375666 --step omdb
  cd backend && python -m scripts.run_pipeline_step --movie-id tt1375666 --step all --save-response ./pipeline_outputs

Steps: omdb | imdb_scraper | critic_reviews | chunk | embed | cluster | wikipedia | plot_beats | what_if | all
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from app.config import get_settings
from app.integrations.gemini import GeminiClient
from app.integrations.imdb_scraper import DEFAULT_MIN_REVIEWS, scrape_imdb_reviews
from app.integrations.omdb import OmdbClient
from app.integrations.wikipedia import WikipediaPlotClient
from app.services.clustering import cluster_review_chunks
from app.services.datastore import DataStore
from app.services.embedding import EmbeddingService
from app.utils.text import split_into_review_chunks, stable_id


def _save(save_dir: Path | None, step_name: str, data: object) -> None:
    if not save_dir:
        return
    save_dir.mkdir(parents=True, exist_ok=True)
    path = save_dir / f"{step_name}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, default=str)
    print(f"  [saved] {path}")


def run_omdb(movie_id: str, store: DataStore, omdb: OmdbClient, save_dir: Path | None) -> dict:
    """Step 1: Fetch movie from OMDB. No DB write."""
    print("\n--- Step 1: OMDB ---")
    payload = omdb.fetch_by_imdb_id(movie_id)
    if not payload:
        print("  OMDB returned no data (check API key and movie id).")
        return {}
    print(f"  Title: {payload.get('Title')}")
    print(f"  Year: {payload.get('Year')}")
    print(f"  Plot length: {len(payload.get('Plot') or '')} chars")
    out = {k: v for k, v in payload.items() if k != "Response"}
    _save(save_dir, "01_omdb", out)
    return payload


def run_imdb_scraper(movie_id: str, max_reviews: int, save_dir: Path | None) -> list:
    """Step 2: Scrape IMDb user reviews. No DB write."""
    print("\n--- Step 2: IMDb scraper ---")
    reviews = scrape_imdb_reviews(
        movie_id,
        max_reviews=max_reviews,
        min_reviews=min(DEFAULT_MIN_REVIEWS, max_reviews),
    )
    print(f"  Scraped: {len(reviews)} reviews")
    if len(reviews) < min(DEFAULT_MIN_REVIEWS, max_reviews):
        print(f"  Warning: fewer than {min(DEFAULT_MIN_REVIEWS, max_reviews)} reviews were returned for this title.")
    if reviews:
        r = reviews[0]
        print(f"  Sample: review_id={r.review_id[:16]}... rating={r.rating} text_len={len(r.text)}")
        print(f"  Text snippet: {r.text[:200]}...")
    out = [
        {"review_id": r.review_id, "rating": r.rating, "text_len": len(r.text), "text_snippet": r.text[:300]}
        for r in reviews[:20]
    ]
    _save(save_dir, "02_imdb_reviews", {"count": len(reviews), "samples": out})
    return reviews


def run_critic_reviews(movie_id: str, title: str, store: DataStore, save_dir: Path | None) -> list:
    """Step 3: Load critic reviews from DB (read-only)."""
    print("\n--- Step 3: Critic reviews (read from DB) ---")
    if not store.client:
        print("  Supabase not configured; 0 critic reviews (set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY)")
        critics = []
    else:
        critics = store.get_critic_reviews(movie_id, title)
    print(f"  Loaded: {len(critics)} critic reviews")
    if len(critics) == 0 and store.client:
        print("  Tip: Ensure critic_reviews is seeded (python -m scripts.seed_from_csv) and imdb_id matches (e.g. tt1375666)")
    if critics:
        c = critics[0]
        print(f"  Sample: {list(c.keys())} text_len={len(c.get('movie_review',''))}")
    out = [{"movie_review_len": len(c.get("movie_review") or ""), "title": c.get("movie_title")} for c in critics[:20]]
    _save(save_dir, "03_critic_reviews", {"count": len(critics), "samples": out})
    return critics


def run_chunk(
    movie_id: str,
    user_reviews: list,
    critic_reviews: list,
    save_dir: Path | None,
) -> list[dict]:
    """Step 4: Chunk user + critic review text. No DB write."""
    print("\n--- Step 4: Chunking ---")
    chunks = []
    for source, rows in (("user", user_reviews), ("critic", critic_reviews)):
        for row in rows:
            full_text = row.get("movie_review") or row.get("review_content") or (getattr(row, "text", None) or "")
            if not full_text:
                continue
            for chunk_idx, chunk in enumerate(split_into_review_chunks(full_text, max_sentences=3), start=1):
                chunk_id = stable_id(
                    movie_id, source, row.get("movie_title", ""), str(chunk_idx), chunk[:120]
                )
                chunks.append({
                    "chunk_id": chunk_id,
                    "movie_id": movie_id,
                    "text": chunk,
                    "source": source,
                    "full_review_text": full_text,
                })
    print(f"  Chunks: {len(chunks)}")
    if chunks:
        print(f"  Sample chunk len: {len(chunks[0]['text'])}")
    out = [{"chunk_id": c["chunk_id"], "text_len": len(c["text"]), "source": c["source"]} for c in chunks[:30]]
    _save(save_dir, "04_chunks", {"count": len(chunks), "samples": out})
    return chunks


def run_embed(chunks: list[dict], embedder: EmbeddingService, save_dir: Path | None) -> tuple[list[dict], list]:
    """Step 5: Embed chunks. No vector store write."""
    print("\n--- Step 5: Embedding ---")
    if not chunks:
        print("  No chunks; skipping.")
        return [], []
    texts = [c["text"] for c in chunks]
    vectors = embedder.encode(texts)
    print(f"  Encoded: {len(vectors)} vectors, dim={len(vectors[0]) if vectors else 0}")
    # Save summary only (vectors are large)
    _save(save_dir, "05_embed", {"count": len(vectors), "dim": len(vectors[0]) if vectors else 0})
    return chunks, vectors


def run_cluster(
    movie_id: str,
    title: str,
    chunks: list[dict],
    vectors: list,
    gemini: GeminiClient,
    save_dir: Path | None,
) -> tuple[list[dict], list[dict]]:
    """Step 6: Cluster and label. No DB write."""
    print("\n--- Step 6: Clustering ---")
    if not chunks or not vectors:
        print("  No chunks/vectors; skipping.")
        return [], []
    clusters, examples = cluster_review_chunks(
        movie_id, title, chunks, vectors, gemini, max_clusters=7
    )
    print(f"  Clusters: {len(clusters)}")
    for c in clusters:
        print(f"    - {c.get('label')} (n={c.get('review_count')})")
    out_c = [{"cluster_id": c["cluster_id"], "label": c["label"], "review_count": c["review_count"]} for c in clusters]
    out_e = [{"example_id": e["example_id"], "review_text_snippet": (e["review_text"] or "")[:120]} for e in examples[:15]]
    _save(save_dir, "06_cluster", {"clusters": out_c, "examples_sample": out_e})
    return clusters, examples


def run_wikipedia(title: str, year: str | None, wiki: WikipediaPlotClient, save_dir: Path | None) -> tuple[str, str] | None:
    """Step 7: Fetch Wikipedia plot. No DB write."""
    print("\n--- Step 7: Wikipedia plot ---")
    result = wiki.fetch_plot(title, year)
    if not result:
        print("  No plot found.")
        return None
    plot_text, page_title = result
    print(f"  Page: {page_title}")
    print(f"  Plot length: {len(plot_text)} chars")
    print(f"  Snippet: {plot_text[:300]}...")
    _save(save_dir, "07_wikipedia", {"page_title": page_title, "plot_length": len(plot_text), "plot_text": plot_text})
    return result


def run_plot_beats(
    title: str,
    plot_text: str,
    gemini: GeminiClient,
    save_dir: Path | None,
) -> dict:
    """Step 8: Gemini plot package (beats + expanded_plot). No DB write."""
    print("\n--- Step 8: Plot beats (Gemini) ---")
    if not plot_text:
        print("  No plot text; skipping.")
        return {}
    package = gemini.generate_plot_package(title, plot_text)
    beats = package.get("beats", [])
    expanded = package.get("expanded_plot", "")
    characters = package.get("characters", [])
    print(f"  Beats: {len(beats)}")
    for b in beats:
        print(f"    {b.get('order')}. {b.get('label')}: { (b.get('text') or '')[:80]}...")
    print(f"  Characters: {len(characters)}")
    for c in characters[:5]:
        print(f"    - {c.get('name')} ({c.get('role')})")
    print(f"  Expanded plot length: {len(expanded)} chars")
    _save(save_dir, "08_plot_beats", package)
    return package


def run_what_if(
    title: str,
    cluster_labels: list[str],
    plot_context: str,
    gemini: GeminiClient,
    save_dir: Path | None,
) -> list[str]:
    """Step 9: Gemini what-if suggestions. No DB write."""
    print("\n--- Step 9: What-if (Gemini) ---")
    what_ifs = gemini.generate_what_if(title, cluster_labels[:3], plot_context)
    for i, w in enumerate(what_ifs, 1):
        print(f"  {i}. {w[:100]}...")
    _save(save_dir, "09_what_if", {"what_ifs": what_ifs, "cluster_labels": cluster_labels[:3]})
    return what_ifs


def run_all(
    movie_id: str,
    max_reviews: int,
    save_dir: Path | None,
    settings,
    store: DataStore,
    omdb: OmdbClient,
    wiki: WikipediaPlotClient,
    gemini: GeminiClient,
    embedder: EmbeddingService,
) -> None:
    """Run full pipeline in memory; no DB writes."""
    print(f"\n===== Dry run: full pipeline for movie_id={movie_id} (no DB writes) =====")

    # 1. OMDB
    omdb_payload = run_omdb(movie_id, store, omdb, save_dir)
    if not omdb_payload:
        print("Stopping: no OMDB data.")
        return
    title = omdb_payload.get("Title") or movie_id
    year = omdb_payload.get("Year")

    # 2. IMDb scraper
    user_reviews_raw = run_imdb_scraper(movie_id, max_reviews, save_dir)
    user_reviews = [
        {"movie_review": r.text, "rating": r.rating, "review_id": r.review_id}
        for r in user_reviews_raw
    ]

    # 3. Critic (read from DB only)
    critics = run_critic_reviews(movie_id, title, store, save_dir)

    # 4. Chunk
    chunks = run_chunk(movie_id, user_reviews, critics, save_dir)
    if not chunks:
        print("No chunks; stopping before embed.")
        return

    # 5. Embed
    _, vectors = run_embed(chunks, embedder, save_dir)
    if not vectors:
        print("No vectors; stopping before cluster.")
        return

    # 6. Cluster
    clusters, _ = run_cluster(movie_id, title, chunks, vectors, gemini, save_dir)
    if not clusters:
        print("No clusters; continuing with empty what-if labels.")

    # 7. Wikipedia
    wiki_result = run_wikipedia(title, year, wiki, save_dir)
    plot_text = wiki_result[0] if wiki_result else (omdb_payload.get("Plot") or "")

    # 8. Plot beats
    run_plot_beats(title, plot_text, gemini, save_dir)

    # 9. What-if
    labels = [c.get("label", "") for c in clusters[:3]]
    run_what_if(title, labels, plot_text[:4000], gemini, save_dir)

    print("\n===== Dry run complete =====")


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description="Run pipeline steps (dry run, no DB writes)")
    parser.add_argument("--movie-id", required=True, help="IMDb id e.g. tt1375666 (Inception)")
    parser.add_argument(
        "--step",
        default="all",
        choices=[
            "omdb", "imdb_scraper", "critic_reviews", "chunk", "embed", "cluster",
            "wikipedia", "plot_beats", "what_if", "all",
        ],
        help="Which step to run (or 'all')",
    )
    parser.add_argument("--max-reviews", type=int, default=300, help="Max IMDb reviews for scraper (default 300)")
    parser.add_argument("--save-response", type=Path, default=None, help="Directory to save JSON outputs")
    args = parser.parse_args()

    settings = get_settings()
    store = DataStore(settings)
    omdb = OmdbClient(settings)
    wiki = WikipediaPlotClient(settings)
    gemini = GeminiClient(settings)
    embedder = EmbeddingService(settings)

    save_dir = args.save_response

    if args.step == "all":
        run_all(
            args.movie_id,
            args.max_reviews,
            save_dir,
            settings,
            store,
            omdb,
            wiki,
            gemini,
            embedder,
        )
        return

    # Single step
    if args.step == "omdb":
        run_omdb(args.movie_id, store, omdb, save_dir)
        return
    if args.step == "imdb_scraper":
        run_imdb_scraper(args.movie_id, args.max_reviews, save_dir)
        return
    if args.step == "critic_reviews":
        movie = store.get_movie(args.movie_id)
        title = (movie.get("title") if movie else None) or ""
        if not title and omdb:
            payload = omdb.fetch_by_imdb_id(args.movie_id)
            title = (payload.get("Title") or "") if payload else ""
        run_critic_reviews(args.movie_id, title, store, save_dir)
        return
    if args.step == "chunk":
        movie = store.get_movie(args.movie_id)
        title = (movie.get("title") if movie else None) or ""
        user_rows = store.get_user_reviews(args.movie_id, limit=1200) if store.client else []
        critics = store.get_critic_reviews(args.movie_id, title) if store.client else []
        if not user_rows:
            print("  No user_reviews in DB; run imdb_scraper first (or use --step all).")
        run_chunk(args.movie_id, user_rows, critics, save_dir)
        return
    if args.step == "embed":
        movie = store.get_movie(args.movie_id)
        title = (movie.get("title") if movie else None) or ""
        user_rows = store.get_user_reviews(args.movie_id, limit=1200) if store.client else []
        critics = store.get_critic_reviews(args.movie_id, title) if store.client else []
        chunks = []
        for source, rows in (("user", user_rows), ("critic", critics)):
            for row in rows:
                full_text = row.get("movie_review") or row.get("review_content") or ""
                if not full_text:
                    continue
                for ci, ch in enumerate(split_into_review_chunks(full_text, max_sentences=3), 1):
                    cid = stable_id(args.movie_id, source, row.get("movie_title", ""), str(ci), ch[:120])
                    chunks.append({"chunk_id": cid, "movie_id": args.movie_id, "text": ch, "source": source, "full_review_text": full_text})
        run_embed(chunks, embedder, save_dir)
        return
    if args.step == "cluster":
        movie = store.get_movie(args.movie_id)
        title = (movie.get("title") if movie else None) or ""
        user_rows = store.get_user_reviews(args.movie_id, limit=1200) if store.client else []
        critics = store.get_critic_reviews(args.movie_id, title) if store.client else []
        chunks = []
        for source, rows in (("user", user_rows), ("critic", critics)):
            for row in rows:
                full_text = row.get("movie_review") or row.get("review_content") or ""
                if not full_text:
                    continue
                for ci, ch in enumerate(split_into_review_chunks(full_text, max_sentences=3), 1):
                    cid = stable_id(args.movie_id, source, row.get("movie_title", ""), str(ci), ch[:120])
                    chunks.append({"chunk_id": cid, "movie_id": args.movie_id, "text": ch, "source": source, "full_review_text": full_text})
        vectors = embedder.encode([c["text"] for c in chunks]) if chunks else []
        run_cluster(args.movie_id, title, chunks, vectors, gemini, save_dir)
        return
    if args.step == "wikipedia":
        movie = store.get_movie(args.movie_id)
        title = (movie.get("title") if movie else None) or ""
        year = movie.get("year") if movie else None
        if not title:
            payload = omdb.fetch_by_imdb_id(args.movie_id)
            if payload:
                title = payload.get("Title") or ""
                year = payload.get("Year")
        run_wikipedia(title, year, wiki, save_dir)
        return
    if args.step == "plot_beats":
        movie = store.get_movie(args.movie_id)
        title = (movie.get("title") if movie else None) or ""
        plot_summary = store.get_plot_summary(args.movie_id) if store.client else None
        plot_text = (plot_summary.get("plot_text") if plot_summary else None) or (movie.get("plot") if movie else "")
        if not plot_text:
            payload = omdb.fetch_by_imdb_id(args.movie_id)
            if payload:
                title = payload.get("Title") or title
                plot_text = payload.get("Plot") or ""
        if not title:
            title = args.movie_id
        run_plot_beats(title, plot_text, gemini, save_dir)
        return
    if args.step == "what_if":
        movie = store.get_movie(args.movie_id)
        title = (movie.get("title") if movie else None) or ""
        clusters = store.get_clusters(args.movie_id) if store.client else []
        plot_summary = store.get_plot_summary(args.movie_id) if store.client else None
        plot_text = (plot_summary.get("plot_text") if plot_summary else None) or (movie.get("plot") if movie else "") or ""
        if not title:
            payload = omdb.fetch_by_imdb_id(args.movie_id)
            if payload:
                title = payload.get("Title") or ""
                plot_text = plot_text or payload.get("Plot") or ""
        labels = [c.get("label", "") for c in clusters[:3]]
        run_what_if(title, labels, plot_text[:4000], gemini, save_dir)
        return


if __name__ == "__main__":
    main()
