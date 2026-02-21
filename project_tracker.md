# DirectorsCut Project Tracker

## Overview
DirectorsCut is built as a FastAPI backend plus a React frontend, with Supabase for structured storage, Actian VectorAI (or in-memory vector fallback) for semantic retrieval, and Gemini for plot/story intelligence; work is organized into backend and frontend phases with focused mini milestones.

## Backend

### B1 - DB and scrapers
- Document `user_reviews` / `critic_reviews` key behavior with IMDb ID (`movie_id`) as canonical key.
- Add `movies` (full OMDB payload) and `plot_summary` (Wikipedia Plot section text).
- Implement OMDB get-or-fetch by IMDb ID/title with persistent storage.
- Add tables for plot beats, complaint clusters/examples, what-if suggestions, generations, votes.
- Implement IMDb user review scraping routes and read routes for reviews.
- Implement Wikipedia Plot-only scraper with title/year page resolution and fallback behavior.
- Add DB/scraper integration tests.

### B2 - Embeddings and Actian
- Chunk user + critic reviews into 1-3 sentence chunks.
- Generate embeddings and upsert into Actian/in-memory vector store by `movie_id`.
- Expose FastAPI routes for embedding index and vector search by movie.
- Add Actian/mock integration coverage.

### B3 - Clustering and what-if
- Cluster movie chunk embeddings with dynamic cluster count (max 7).
- Label clusters via Gemini and store representative examples.
- Generate exactly 3 what-if suggestions from top clusters.
- Expose API routes through analysis payload.

### B4 - Plot and beats (Gemini)
- Use Wikipedia Plot summary first (OMDB plot fallback) as narrative source.
- Generate expanded plot + structured beats via Gemini.
- Persist beats and serve them by `movie_id`.

### B5 - Story engine (Gemini)
- Start from selected what-if and context beats.
- Use one Gemini call per step for exactly 3 choice rounds.
- Enforce strict JSON payload contracts for narrative/options/ending.
- Provide theme coverage scoring endpoint.

### B6 - Community
- Save anonymous generations by session/device ID.
- Vote on generations.
- Provide explore leaderboard sorted by votes.

## Frontend

### F1 - Shell and design
- App shell/routing/navigation.
- Refined-elegance theme system + poster component + responsive layout.

### F2 - Discovery and search
- Home page with featured catalog grouped by genre.
- Search page with pipeline trigger and progress UI.

### F3 - Analysis dashboard
- Poster hero, complaint clusters, examples, plot beats, what-if list.
- Fast hand-off into rewrite flow.

### F4 - Rewrite flow
- Typing animation narrative panel.
- 3-step branching with progress indicator and API orchestration.

### F5 - Ending and score
- Ending page with score breakdown and evidence panel.
- Save ending action and share placeholder.

### F6 - Community
- Explore leaderboard page with vote controls.
- Live vote updates in UI.

## Testing
- Backend unit tests for text chunking, Wikipedia plot extraction, and story-step engine.
- Integration-ready architecture for Supabase and Actian (with memory fallback for local development).
- Frontend flows wired for search -> prepare -> analysis -> rewrite -> ending -> explore.

## Definition Of Done (Summary)
- 25-movie capable architecture with search-triggered pipeline.
- Poster-first discovery cards (placeholder poster support).
- 3-step interactive rewrite and ending score display.
- Save/vote/explore community loop with leaderboard by votes.
- Share button intentionally non-functional ("Coming soon").
