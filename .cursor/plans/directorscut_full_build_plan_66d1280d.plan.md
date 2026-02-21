---
name: DirectorsCut Full Build Plan
overview: A two-part plan (Backend then Frontend) to build DirectorsCut end-to-end, with a project_tracker.md that defines backend/frontend phases and mini milestones. The plan aligns the existing DB (user_reviews, critic_reviews) with the PRD schema, reuses patterns from the Actian embedding/story POC and IMDb scraper doc, and emphasizes backend/DB connectivity testing.
todos: []
isProject: false
---

# DirectorsCut — Full Application Build Plan

## Current state

- **Docs only:** [prd.md](prd.md), [actian_vector_db.md](actian_vector_db.md), [imbd_scraper.md](imbd_scraper.md). No app code in repo yet.
- **Existing DB (Supabase)** — inspected via MCP:
  - **user_reviews** (36k+ rows): scraped from **25 chosen movies**; `movie_id`, `movie_title`, `movie_review`, `rating`, etc. Only the IMDb scraper writes here.
  - **critic_reviews** (23k+ rows): pre-existing; lookup by `imdb_id` when present, else by **movie title** (normalized, case-insensitive).
- **MVP scope:** **25 movies** (already in user_reviews) form the base catalog; **search** is required so users can type a movie name and trigger the full pipeline (OMDB → user reviews → critic lookup → embed → Actian). No “3 movies” limit from PRD.
- **POC patterns:** Actian doc = embedding/vector; IMDb doc = scrape → user_reviews. **No Wikipedia plot scraper POC** — see §1.7 for in-depth spec.

---

## Part 1: Backend

### 1.1 Database architecture and keys

Use **IMDb ID** (e.g. `tt0468569`) as the **canonical movie key** everywhere: `user_reviews`, `critic_reviews`, and any new tables.

- **user_reviews:** Populated **only** by the IMDb scraper. Key: `movie_id` (IMDb ID). Use for clustering, embeddings, and "get reviews" by movie.
- **critic_reviews:** **Read-only** in the app; pre-existing data only. When `imdb_id` is null, **search by `title`** (normalized, case-insensitive). Backend supports lookup by `imdb_id` when present, else by `title`. 
- **New tables (per PRD §9.1):** Add only what the MVP needs, all keyed by `movie_id` (IMDb ID) where applicable:
  - **movies** — One row per movie; **from OMDB API only** (see §1.4). Store full OMDB response. Primary key: `movie_id` = imdbID. **No re-fetch:** once pulled from OMDB we add to DB and use that. Missing **Poster** → use **placeholder image** in poster component. Rotten Tomatoes / audience from Ratings or imdbRating.
  - **plot_summary** — **Separate table** keyed by `movie_id`: stores Wikipedia Plot section (plain text) for Gemini beats. Create via migration/MCP during build.
  - **plot_beats** — `movie_id` + beat order + label/text (Gemini output from plot).
  - **complaint_clusters** — `movie_id` + cluster_id + label; **dynamic** clustering, **max 7** per movie (frontend displays 5).
  - **cluster_examples** — Links clusters to review chunks (e.g. cluster_id, chunk_id or review reference).
  - **what_if_suggestions** — `movie_id` + suggestion text + linked cluster(s).
  - **generations** — Saved endings (e.g. user/session id, movie_id, story payload, score).
  - **votes** — Votes on generations (generation_id, user/session, value).

**Actian (vector store):** Embed **user_reviews and critic_reviews** (both); key payloads by `movie_id`. **Error handling:** if no critic reviews exist for a movie, continue without failing. Chunk size: 1–3 sentences. Idempotent get-or-create.

### 1.3 Gemini plot and story pipeline (reimagine flow)

- **Plot source for beats:** **Wikipedia plot section primary;** fall back to OMDB Plot if no Wikipedia plot is available.
- **Plot → expanded plot + structured beats:** Feed the Wikipedia-scraped plot (or OMDB fallback) into Gemini. Ask Gemini to (1) produce an **expanded plot** (clearer, more detailed) and (2) **structure it into beats** in an LLM-friendly format. Store both in `movies` / `plot_beats` for story generation.
- **What-if:** Exactly **3 what-if options** per movie, from **top clusters**.
- **Story generation:** **One Gemini call per step** (not one-shot). Each step receives previous choices in context; returns narrative + 3 options (or wrap-up/ending on final step). Narrative **under 8 sentences** per segment. **Tone:** Adapt to the plot and movie theme.
- **Strict JSON** per step: `narrative` and `options[]` (or `ending`); enforce via system prompt + parsing.

### 1.4 Movies table: OMDB API (Context7 docs)

- **Source:** [OMDB API](https://www.omdbapi.com/) — REST API for movie information. Docs referenced via Context7 MCP (`/websites/omdbapi`).
- **Endpoint:** `GET http://www.omdbapi.com/?apikey=[key]&` with **required** `apikey`; use `**i`** (IMDb ID, e.g. tt1285016) or `**t`** (title); optional `**y`** (year), `**plot=full`** for full plot, `**r=json`**.
- **Lookup:** By `i=<imdb_id>` or `t=<title>` (+ optional `y=<year>`). Store full JSON in **movies**. **Multiple results:** when search returns several (e.g. same title, different years), **show results and let user pick** — do not auto-pick first. **No refresh:** once we add from OMDB we use DB only. **Missing Poster:** use **placeholder image** in poster component.
- **Implementation:** Get-or-fetch from DB; if missing, call OMDB (or return search for user to pick), then upsert. Env: `OMDB_API_KEY`. Poster URL or placeholder; RT from `Ratings` or imdbRating.

### 1.5 Search-triggered movie pipeline (no assumptions)

User **search** is the main entry for adding and preparing a movie. When a user types a movie name and selects a result (or we resolve one movie):

1. **OMDB** — Fetch by title/year; if multiple results, **show them and let user pick**. Add/update row in `movies` (no re-fetch later).
2. **IMDb user reviews** — Run the user-reviews scraper for that movie’s IMDb ID; **Use existing always:** check DB first; if we already have user_reviews for this movie_id, **skip scraper** and use existing. **Double-check with DB**; **no duplications**, keep **consistent and in sync**.
3. **Critic reviews** — Search `critic_reviews` by **movie title** (normalized, case-insensitive); attach matches (read-only). **Error handling:** if no critic reviews exist, **continue without failing**.
4. **Embed, chunk, vector** — Chunk **user_reviews and critic_reviews** (both); embeddings → Actian. If no critics, run on user_reviews only. **Cluster right after embedding** (dynamic, **max 7** clusters; frontend shows 5).
5. **Loading UX** — **Single long-running request** with progress. **Timeout: 5 minutes** for full pipeline. Clear, visible loading so the user never assumes the app is stuck. Backend may expose a status or job endpoint (e.g. “fetching movie”, “scraping reviews”, “embedding”, “ready”); frontend shows progress so the user knows work is in progress and does not assume the app is stuck.

**MVP catalog:** **25 movies** in `user_reviews`. Search required; use existing data when present.

### 1.6 Identity and community

- **Save ending / vote:** **Anonymous** — identify by session ID or device only; no user accounts.

### 1.7 Wikipedia plot scraper (in-depth — no POC exists)

**Purpose:** Retrieve only the **“Plot”** section from a movie’s Wikipedia article. Used as **primary** source for Gemini plot beats; fall back to OMDB Plot if no Wikipedia plot.

**Article discovery (agreed: title + year):**

- Resolve the correct Wikipedia page by **title and year** to avoid disambiguation (e.g. “Superman (2025 film)” or search “Superman” + year filter). Options to implement:
  - **Wikipedia API:** `action=opensearch` or `action=query&list=search` with query like `"<Title> (<Year> film)"` or `"<Title> film"`; then load the chosen page. Prefer the result that has “film” or “movie” in the title or that matches year.
  - **Alternative:** Search by title only and use the first result; if the response is a disambiguation page, parse it and pick the “(YYYY film)” link if year matches (from OMDB/critic_reviews).
- **Inputs:** Movie title and year from `movies` (OMDB) or from critic_reviews when no OMDB row yet.

**Section to scrape (agreed: Plot only):**

- Extract **only** the section whose heading is exactly **“Plot”** (case-sensitive match on en.wikipedia). Do not include “Synopsis”, “Premise”, “Reception”, etc.
- If there is no “Plot” section, treat as “no Wikipedia plot” and **fall back to OMDB Plot** for Gemini beats.

**Technical implementation (to decide):**

- **Option A — Wikipedia REST API / action=parse:** Request the page by title; use `prop=sections` to get section indices, find the section titled “Plot”, then `prop=text&section=<index>` to get that section’s HTML. Strip wiki markup and resolve internal links to plain text for Gemini. Pros: structured, no HTML scraping. Cons: need to handle section numbering and markup.
- **Chosen: Fetch HTML and parse (web scraping).** Get full page HTML (e.g. `action=parse`), find the heading `== Plot ==` (or `<h2>Plot</h2>` in parsed HTML), take content until the next same-level heading. Strip wiki markup (e.g. `[[link|text]]` → text, `''italic''` → plain). Pros: one request. Cons: need robust heading and markup parsing.
- **Rate limits / politeness:** Use a descriptive `User-Agent` (e.g. “DirectorsCut/1.0 ([contact@example.com](mailto:contact@example.com))”), and throttle requests (e.g. 1 req/sec) to respect Wikipedia guidelines.
- **Storage:** **Separate table `plot_summary`** keyed by `movie_id`; store plain-text Plot section. Create via migration/MCP during build. Use for Gemini; if missing, use OMDB Plot. **Plot length:** no max — be generous.

**Edge cases to handle:**

- **No Wikipedia page** (e.g. obscure or very new film): Return empty; fall back to OMDB Plot.
- **Disambiguation page:** If search returns a disambiguation page, use title+year to pick “(YYYY film)” or first film link; otherwise skip and use OMDB.
- **Plot section very long:** No max; be generous (do not truncate unless necessary).
- **Language:** **en.wikipedia.org** only for MVP unless you specify otherwise.
- **Wiki markup:** Strip `[[...]]`, `''...''`, `{{...}}`, etc., so Gemini receives plain text only.

**Open decisions to confirm:** (1) Prefer Wikipedia API (`action=parse` + sections) vs raw HTML fetch + parse? (2) Store wiki plot in `movies.wiki_plot` vs separate table? (3) Max plot length (chars) before truncation for Gemini?

### 1.8 Decisions locked (from clarifying answers)

- **Featured / home:** **All 25 movies**; sorted by **genre** (Netflix-like). Include poster and Rotten Tomatoes score.
- **Share button:** **Not functional** — show **Coming soon**.
- **Explore / leaderboard:** Sort by **votes**.
- **Scoring:** Do not use Sphinx; use **Gemini** for Theme Coverage or a simpler “addressed yes/no per cluster” for MVP?

### 1.2 Backend phases (high level)


| Phase                              | Focus                                                                                                                                                           | Outcomes                                                                                                                      |
| ---------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------- |
| **B1 — DB and scrapers**           | Align Supabase with PRD; **movies from OMDB API** (get-or-fetch by imdb_id or title, store full response); IMDb scraper → user_reviews; Wikipedia plot scraper. | movies table populated from OMDB (Poster, Ratings, Plot, etc.); POST scrape (IMDb), GET reviews; POST/GET plot (Wikipedia).   |
| **B2 — Embeddings and Actian**     | Chunk reviews (from user_reviews/critic_reviews), embed, upsert to Actian; idempotent “get or create.”                                                          | Ingest script + FastAPI route to trigger/refresh embeddings per movie; vector search by movie_id.                             |
| **B3 — Clustering and what-if**    | Offline/batch: cluster review chunks, label with Gemini, map to plot beats; generate what-if suggestions. Store in Supabase.                                    | complaint_clusters, cluster_examples, what_if_suggestions populated; routes to read clusters and what-if by movie_id.         |
| **B4 — Plot and beats (Gemini)**   | Wikipedia plot → Gemini: expanded plot + structured beats (LLM-friendly). Store in movies/plot_beats.                                                           | GET plot and expanded/structured beats by movie_id; rich context for story generation.                                        |
| **B5 — Story engine (Gemini)**     | On what-if selection: feed Gemini plot + structured beats + chosen what-if → strict JSON: 3 options, 3 steps (each 3 options), ending.                          | Route returns structured story (intro, step_1–3 with options, wrap-up/ending). Theme Coverage Score optional.                 |
| **B6 — Community and misc routes** | Save generation, shareable URL, vote, leaderboard.                                                                                                              | POST save ending, GET/POST vote, GET explore/leaderboard **sorted by votes**. **Share button:** Coming soon (not functional). |


**Testing (backend):**  

- Unit tests for scrapers (mocked HTTP), embedding pipeline (mocked Actian if needed), and story/scoring parsing.  
- Integration tests: DB connectivity (Supabase) — insert/select for user_reviews, critic_reviews, and one new table per phase; verify keys (movie_id) and joins.  
- Actian: integration test that runs ingest for one movie and runs a vector search filtered by movie_id (or use mock mode as in Actian doc).

---

## Part 2: Frontend

### 2.1 Frontend phases (high level)


| Phase                         | Focus                                                                                                                   | Outcomes                                                                                                                                              |
| ----------------------------- | ----------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------- |
| **F1 — Shell and design**     | App shell, routing, design system (refined elegance palette); **visible loading** for all backend-heavy flows.          | Layout, nav, search entry, theme; loading states so user sees progress (e.g. fetching movie, scraping, embedding) and never assumes the app is stuck. |
| **F2 — Discovery and search** | Home: **all 25 movies** sorted by **genre** (Netflix-like); poster + Rotten Tomatoes score; search page.                | User can open a movie from home or search and land on analysis.                                                                                       |
| **F3 — Analysis dashboard**   | Single movie view: poster hero, complaint clusters, example reviews, plot beats, what-if suggestions.                   | All data from backend (reviews, clusters, beats, what-if) displayed; user can select a what-if.                                                       |
| **F4 — Rewrite flow**         | Typing animation; set stage → twist → 3 choice rounds (lead-in + options + narration) → wrap-up → hand-off to ending.   | 3-step branching working; progress indicator; API calls for each story step.                                                                          |
| **F5 — Ending and score**     | Ending page: summary, Theme Coverage Score breakdown, evidence panel.                                                   | Score and per-cluster evidence from backend displayed.                                                                                                |
| **F6 — Community**            | Save ending, share link, vote, explore/leaderboard **sorted by votes**. **Share button:** Coming soon (not functional). | Save/share/vote and explore page wired to backend.                                                                                                    |


---

## Project tracker (project_tracker.md)

Create **project_tracker.md** at repo root with the structure below. Keep sections short and generic (no low-level task lists).

### Suggested structure for project_tracker.md

1. **Overview**
  - One paragraph: DirectorsCut backend (FastAPI, Supabase, Actian, Gemini) and frontend (refined elegance UI) with phases and mini milestones below.
2. **Backend**
  - **B1 — DB and scrapers:** Mini milestones: (1) Document user_reviews and critic_reviews schema and keys; (2) Add movies table (full OMDB response) and **plot_summary** table (Wikipedia plot text, keyed by movie_id) (Title, Year, Plot, Poster, Ratings, imdbID, etc.); (3) Implement OMDB API integration (get-or-fetch movie by imdb_id or title, store full JSON; env OMDB_API_KEY); (4) Add plot_beats, complaint_clusters, cluster_examples, what_if_suggestions, generations, votes; (5) IMDb scraper (POST scrape, GET reviews → user_reviews); (6) Wikipedia plot scraper (fetch HTML, parse Plot section only); store in plot_summary; (7) Integration tests for DB and scrapers.
  - **B2 — Embeddings and Actian:** Mini milestones: (1) Chunking and embedding pipeline from user_reviews/critic_reviews; (2) Actian ingest (get-or-create collection, batch upsert by movie_id); (3) FastAPI route(s) for “get or create” embeddings and vector search by movie; (4) Integration test for Actian (or mock).
  - **B3 — Clustering and what-if:** Mini milestones: (1) Batch clustering (e.g. 10–20 themes per movie); (2) Gemini cluster labeling; (3) Store clusters and examples in Supabase; (4) What-if suggestion generation and storage; (5) GET clusters and what-if by movie_id.
  - **B4 — Plot and beats (Gemini):** Mini milestones: (1) Feed Wikipedia plot to Gemini → expanded plot + structured beats (LLM-friendly); (2) Store and serve by movie_id.
  - **B5 — Story engine (Gemini):** Mini milestones: (1) On what-if selection, feed Gemini plot + structured beats + what-if; (2) Strict JSON output: 3 options, 3 steps (each 3 options), ending; (3) Route(s) returning structured story; (4) Optional Theme Coverage Score.
  - **B6 — Community:** Mini milestones: (1) Save generation and shareable URL; (2) Vote and leaderboard routes.
3. **Frontend**
  - **F1 — Shell and design:** Mini milestones: (1) App shell and routing; (2) Design system and movie poster component.
  - **F2 — Discovery and search:** Mini milestones: (1) Home with featured movies; (2) Search page and client-side movie match.
  - **F3 — Analysis dashboard:** Mini milestones: (1) Movie analysis view and cluster/review/beats/what-if UI.
  - **F4 — Rewrite flow:** Mini milestones: (1) Typing animation and 3-step choice flow; (2) Integration with story API.
  - **F5 — Ending and score:** Mini milestones: (1) Ending page and score breakdown; (2) Evidence panel.
  - **F6 — Community:** Mini milestones: (1) Save/share; (2) Vote and explore page.
4. **Testing**
  - Backend: Unit tests (scrapers, parsing); integration tests (Supabase connectivity, movie_id joins, Actian or mock).  
  - Frontend: Key flows (select movie → analysis → what-if → one full rewrite path → ending) once backend is stable.
5. **Definition of done (summary)**
  - 25 movies; search; poster component (placeholder if no Poster); 3-step branching; Theme Coverage via Gemini; save/vote/explore (share = Coming soon); leaderboard by votes; FastAPI and scrapers as in plan.

---

## Diagram: data and key flow

```mermaid
flowchart LR
  subgraph sources [Data Sources]
    IMDb[IMDb Scraper]
    Wiki[Wikipedia Plot]
    OMDB[OMDB API]
  end
  subgraph supabase [Supabase]
    user_reviews[user_reviews]
    critic_reviews[critic_reviews]
    movies[movies]
    plot_summary[plot_summary]
    plot_beats[plot_beats]
    clusters[complaint_clusters]
    whatif[what_if_suggestions]
    gens[generations]
    votes[votes]
  end
  subgraph actian [Actian Vector]
    review_chunks[review_chunks]
  end
  IMDb --> user_reviews
  Wiki --> plot_summary
  OMDB --> movies
  user_reviews --> review_chunks
  critic_reviews -.-> review_chunks
  review_chunks --> clusters
  movies --> plot_beats
  clusters --> whatif
  plot_beats --> whatif
  gens --> votes
  movies --- movie_id
  user_reviews --- movie_id
  critic_reviews --- movie_id
  plot_summary --- movie_id
  plot_beats --- movie_id
  clusters --- movie_id
  whatif --- movie_id
```



All movie-scoped data joins on `movie_id` (IMDb ID).

---

## Summary

- **Part 1 (Backend):** DB schema and keys (movie_id/title for critic_reviews); IMDb scraper → user_reviews only; critic_reviews read-only (lookup by imdb_id or title); embeddings from user_reviews; plot → Gemini expanded + structured beats; story from Gemini (strict JSON: 3 options, 3 steps × 3 options, ending); community routes; integration tests.
- **Part 2 (Frontend):** Shell and design; discovery and search; analysis dashboard; rewrite flow (typing, 3 steps); ending and score; community (save/share/vote/explore).
- **Deliverable:** Add **project_tracker.md** with the sections above so work is split into backend vs frontend with simple, generic mini milestones. After approval, implement backend first (including DB and tests), then frontend against the API.

