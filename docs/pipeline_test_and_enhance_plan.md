# Pipeline Test, Harden & Enhance Plan

**Goal:** (1) Test each pipeline step in isolation with full visibility into inputs/outputs and DB writes; fix bugs and make the pipeline robust. (2) Then expand data (character profiles, richer plot, scripts, knowledge graph) so Gemini has deep movie understanding and outputs are grounded and reasonable.

---

## Phase 1: Test Current Pipeline & Gain Visibility

### 1.1 Pipeline step map (what to test)

| Step | Component | Input | Output / DB | Risk |
|------|-----------|--------|-------------|------|
| 1 | OMDB | `movie_id` or search `(query, year)` | Movie row → `movies` | Wrong movie, missing fields |
| 2 | IMDb scraper | `movie_id`, `max_reviews` | `List[ScrapedReview]` → `user_reviews` | HTML change, pagination break, 0 reviews |
| 3 | Critic reviews | `movie_id`, `title` | Read from `critic_reviews` (no fetch) | Empty if not seeded |
| 4 | Chunking | User + critic review text | `chunks[]` (in-memory) | Empty chunks, bad sentence split |
| 5 | Embedding | `chunks[].text` | `vectors[]` + Actian upsert | Model missing, dimension mismatch |
| 6 | Clustering | `chunks`, `vectors`, `gemini` | `clusters`, `examples` → `complaint_clusters`, `cluster_examples` | K=0, Gemini JSON fail |
| 7 | Wikipedia | `title`, `year` | `(plot_text, page_title)` → `plot_summary` | Wrong page, no Plot section |
| 8 | Plot beats (Gemini) | `title`, `plot_text` | `beats`, `expanded_plot` → `plot_beats`, `movies.expanded_plot` | Invalid JSON, empty beats |
| 9 | What-if (Gemini) | `title`, top cluster labels, plot | 3 suggestions → `what_if_suggestions` | Wrong count, generic text |

### 1.2 Step-by-step test harness (recommended)

- **Add a CLI/script** (e.g. `backend/scripts/run_pipeline_step.py`) that:
  - Takes `--step <name>` and `--movie-id <tt...>` (and optional `--query`, `--year` for step 1).
  - Loads settings and the same service stack as the app (DataStore, OMDB, Wiki, Gemini, Embedder, VectorStore).
  - Runs **only** that step with real or fixture inputs.
  - **Prints or saves**:
    - Inputs (e.g. movie_id, title, sample of text, counts).
    - Outputs (e.g. raw API response, parsed struct, row count).
    - For DB steps: before/after row counts or sample rows (e.g. from Supabase) for the affected tables.
  - Does **not** run the full pipeline (so you can test one step and see exactly what was requested and what was stored).

- **Example usage:**
  - `python -m scripts.run_pipeline_step --step omdb --movie-id tt1375666`
  - `python -m scripts.run_pipeline_step --step imdb_scraper --movie-id tt1375666 --max-reviews 50`
  - `python -m scripts.run_pipeline_step --step wikipedia --movie-id tt1375666` (uses movie title from DB or OMDB)
  - `python -m scripts.run_pipeline_step --step plot_beats --movie-id tt1375666`
  - etc.

- **Optional:** `--save-response <path>` to write raw responses (e.g. JSON) for debugging and for building fixtures.

### 1.3 Per-component tests and visibility

- **OMDB**
  - Test: `fetch_by_imdb_id(tt1375666)` and `search_by_title("Inception", "2010")`.
  - Assert: non-null payload, required keys (`Title`, `Plot`, `imdbID`), and that `upsert_movie` writes the expected columns (e.g. `plot`, `imdb_rating`) to Supabase.
  - Visibility: log or print `omdb_payload` (or redact API key) and one row from `movies` after upsert.

- **Wikipedia**
  - Existing: `test_wikipedia_parser.py` for `_extract_plot_from_html`.
  - Add: integration test or harness step that calls `fetch_plot("Inception", "2010")` and checks:
    - Non-null `(plot_text, page_title)`.
    - `plot_text` contains expected keywords (e.g. "Cobb", "dream").
  - Visibility: print `page_title`, length of `plot_text`, and first 500 chars. Optionally save full plot to a file.

- **IMDb scraper**
  - Test: `scrape_imdb_reviews(tt1375666, max_reviews=50)`.
  - Assert: list of `ScrapedReview`, each with `text`, `review_id`; no duplicate `review_id`.
  - Visibility: print count, 2–3 sample reviews (title + snippet). Then run pipeline step that writes to DB and verify `user_reviews` count increased by expected amount (and sample one row from Supabase).

- **Chunking**
  - Test: `split_into_review_chunks(long_review, max_sentences=3)`.
  - Assert: non-empty list, no empty strings, total character count reasonable vs input.
  - Visibility: in harness, for one movie show chunk count and distribution (e.g. chunks per review).

- **Embedding**
  - Test: `embedder.encode([short_text])` → one vector of length `embedding_dimension`.
  - If Actian enabled: after pipeline step, query Actian (or your vector API) to confirm count of vectors for that `movie_id`.
  - Visibility: print dimension, count of vectors, and optionally first vector (truncated).

- **Clustering**
  - Test: with fixture `chunks` + `vectors` (e.g. 20 chunks, 20 vectors), call `cluster_review_chunks(...)`.
  - Assert: `clusters` and `examples` same length as expected, each cluster has `cluster_id`, `label`, `review_count`; examples reference valid `cluster_id`.
  - Visibility: print cluster labels and review counts; then after DB write, query `complaint_clusters` and `cluster_examples` for that movie and show counts + sample.

- **Gemini (plot package, what-if)**
  - Test: with mock or real Gemini, call `generate_plot_package`, `generate_what_if`.
  - Assert: valid JSON shape, correct array lengths (e.g. 5–8 beats, 3 what-ifs).
  - Visibility: in harness, print full JSON (or summary) and then what was written to `plot_beats` / `what_if_suggestions` (count + one row each).

- **Datastore**
  - For each step that writes: after running the step, run a small Supabase query (e.g. via MCP or script) to show row counts and one sample row for the affected table(s). This confirms “we are posting the right data.”

### 1.4 Logging and traceability

- Add a **request/correlation id** (e.g. `job_id` or `run_id`) to pipeline runs and log it at each step.
- Log at **INFO**: step name, movie_id, input sizes (e.g. review count, chunk count), output sizes (e.g. clusters count, beats count), and DB write result (e.g. “inserted N rows into complaint_clusters”).
- Optional: **structured logs** (JSON) so you can grep by step or movie_id later.

### 1.5 Bug-fix checklist (while testing)

- [ ] OMDB: handle `Response == "False"` and missing `Plot`; don’t overwrite good `plot_summary` with empty OMDB plot.
- [ ] Wikipedia: handle alternate section names (e.g. “Plot” vs “Plot summary”), disambiguation pages, and rate limiting (already has sleep).
- [ ] IMDb: robust to HTML structure changes (e.g. class names); handle 0 reviews (pipeline should not assume non-empty).
- [ ] Clustering: when `chunks` or `vectors` is empty, return [] and do not write empty clusters; pipeline should handle “no clusters” without crashing.
- [ ] Gemini: validate and retry on malformed JSON; fallbacks should always match expected schema so downstream code doesn’t break.
- [ ] DB: `replace_*` methods (e.g. replace_plot_beats, replace_clusters) should be atomic where possible (e.g. delete then insert in same transaction if you add transactions later).

---

## Phase 2: Richer Data for Deeper Movie Understanding

### 2.1 Better plot summaries

- **Current:** Single “Plot” section from Wikipedia (or OMDB fallback).
- **Improvements:**
  - Prefer Wikipedia and store `source_page` (already in `plot_summary`); use OMDB only as fallback.
  - Optionally fetch multiple sections (e.g. “Plot”, “Plot summary”, “Synopsis”) and merge or store separately for Gemini context.
  - Store a “long” vs “short” version (e.g. Wikipedia full plot vs OMDB short) and pass the long one to Gemini for beats and story.

### 2.2 Character profiles (new)

- **Goal:** Give Gemini a clear list of characters and traits so rewrites stay in character.
- **Sources (pick one or combine):**
  - **Wikipedia:** Parse “Cast” or “Characters” section from the same movie page (or subpages) to get character names and short descriptions.
  - **TMDB:** Use TMDB movie credits + character name; optional: person bio for “voice”.
  - **Scripts (if added):** Extract character names and key lines to infer role (protagonist, antagonist, mentor).
- **Schema (new table or columns):**
  - e.g. `movie_characters(movie_id, character_name, role_type, description, source)`.
- **Use:** Include in Gemini prompts for plot beats, what-if, and story steps (e.g. “Characters: …” so outputs respect who the characters are).

### 2.3 Full movie scripts (optional, high value, legal caveats)

- **Value:** Best possible understanding of dialogue, tone, and exact plot progression.
- **Sources:** Script sites (e.g. IMSDb, Script Slug) often have scripts; licensing varies. Prefer sources that allow non-commercial or educational use; document source and usage.
- **Storage:** New table e.g. `movie_scripts(movie_id, script_text, source_url, language)` or store path to file; optionally chunk by scene for retrieval.
- **Use:** Pass script chunks (or scene-level summaries) to Gemini for beat extraction and story generation; optionally use for character line analysis.

### 2.4 Richer plot beats and structure

- **Current:** 5–8 beats from Gemini from a single plot text.
- **Improvements:**
  - **Act structure:** Ask Gemini to tag beats with act (1/2/3) or sequence (setup / confrontation / resolution).
  - **Character–beat link:** For each beat, optionally list which characters are involved (from character profile).
  - **Branch points:** Explicitly mark which beats are “branchable” (e.g. climax, key decision) for the rewrite UI.
  - Store in DB: e.g. `plot_beats` add columns `act`, `character_ids[]`, `is_branch_point`.

### 2.5 Knowledge graph (plot / segments)

- **Goal:** Visualize and query the movie as a graph: entities (characters, locations, events) and relations (appears_in, causes, conflicts_with).
- **Data:**
  - **Nodes:** Characters (from 2.2), key events (from plot beats or script scenes), optionally locations if extracted.
  - **Edges:** e.g. “Character A –[in_beat]– Beat 3”, “Beat 2 –[leads_to]– Beat 3”, “Character A –[conflicts_with]– Character B”.
- **Extraction:** Use Gemini to parse plot summary + beats (and optionally script) and output structured JSON: `{ "entities": [...], "relations": [...] }`.
- **Storage:** Either dedicated tables (e.g. `movie_entities`, `movie_relations`) or a JSON column on `movies` (e.g. `knowledge_graph`).
- **Visualization:** Simple UI (e.g. D3, Cytoscape.js, or a graph notebook) to render nodes and edges; filter by movie, by type (character vs event).

### 2.6 Feeding Gemini “everything useful”

- **Single context bundle per movie (for story/scoring):**
  - Plot summary (long)
  - Expanded plot
  - Plot beats (with act and branch points)
  - Character profiles (name, role, short description)
  - Top complaint clusters + labels + 1–2 example reviews each
  - What-if suggestions linked to clusters
- **Prompt design:** System prompt should say “You have: plot, beats, characters, and audience complaints. Keep rewrites consistent with this world and these characters.”
- **Token budget:** If context is large, summarize or retrieve only relevant beats/characters per request (e.g. by branch point).

---

## Implementation order

1. **Phase 1a – Visibility**
   - Add `run_pipeline_step.py` (or equivalent) with `--step` and `--movie-id`, printing inputs/outputs and DB state.
   - Add logging (with optional run_id) for each step.

2. **Phase 1b – Test each step**
   - Implement and run: OMDB, Wikipedia, IMDb scraper, chunking, embedding, clustering, Gemini (plot package, what-if), and DB writes.
   - Fix bugs found (empty handling, JSON validation, HTML changes).

3. **Phase 1c – Regression**
   - Add or extend unit tests for parsers and chunking; add at least one integration test per integration (Wikipedia, IMDb, OMDB) that hits real API (or use saved fixtures).
   - Optionally: one end-to-end test that runs full pipeline for one movie and asserts final DB state (counts + schema).

4. **Phase 2a – Data model**
   - Add tables/columns for characters, optional script storage, and beat metadata (act, branch_point).
   - Add knowledge graph storage (table or JSON).

5. **Phase 2b – Data population**
   - Wikipedia (or TMDB) character extraction and store.
   - Optional script ingestion pipeline (with source/legal note).
   - Gemini prompts updated to produce act/branch_point and, if desired, entity/relation list for the graph.

6. **Phase 2c – Gemini and product**
   - Update all Gemini prompts to include character profiles and richer beats.
   - Build a simple knowledge graph visualization (read from DB, render graph).

7. **Phase 2d – Tuning**
   - Improve plot summary quality (multi-section, long/short); refine character descriptions; add more examples to prompts if needed.

---

## Deliverables summary

| Deliverable | Phase |
|-------------|--------|
| CLI/script to run and inspect one pipeline step at a time | 1a |
| Logging with run_id and step-level visibility | 1a |
| Tests and harness for OMDB, Wiki, IMDb, chunking, embedding, clustering, Gemini, DB | 1b–1c |
| Bug fixes for empty data, JSON, HTML, and DB writes | 1b |
| Character profile source + schema + storage | 2a–2b |
| Richer plot beats (act, branch_point, optional character link) | 2a–2b |
| Optional script ingestion and storage | 2b |
| Knowledge graph extraction + storage + visualization | 2a–2c |
| Gemini prompts updated to use characters + richer context | 2c |
| Documentation of what data is pulled and where it is stored | 1a + 2 |

Once Phase 1 is in place, you can run any step in isolation, see exactly what was pulled and what was posted to the DB, and then layer in richer data and the knowledge graph in Phase 2.
