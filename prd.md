# DirectorsCut — Product Requirements Document (PRD)
**Track:** Entertainment (Primary) + Pure Imagination (Bonus)  
**Sponsor Targets:** Actian VectorAI DB, Sphinx, Databricks Raffle  
**LLM Provider:** Gemini API  
**Backend:** FastAPI  
**Theme:** Refined elegance (luxury branding palette)  
**Hackathon Scope:** 36-hour MVP  
**Team Size:** 4  

---

# 1. Executive Summary

## 1.1 One-Line Vision
**DirectorsCut** is a data-driven, interactive storytelling platform that lets movie fans explore alternate plot paths and endings grounded in real audience complaints — with explainable scoring and transparent evidence.

## 1.2 Why This Matters
Movie fans frequently feel disappointed by endings, rushed resolutions, plot holes, or broken character arcs. Existing AI story generators create alternate endings without grounding in real audience data or narrative structure.

DirectorsCut solves this by:
- Analyzing thousands of real reviews
- Clustering complaint themes
- Mapping complaints to plot beats
- Generating interactive branching alternatives
- Providing a transparent "Theme Coverage Score" with evidence

This is not a generic AI story tool. It is a **data-grounded narrative engine.**

---

# 2. Problem Statement

## 2.1 Core Problem
Movie fans often feel:

- "The ending ruined the whole movie."
- "The character arc made no sense."
- "I wish they had done X instead."

There is no structured, interactive way to:
- Explore alternate story paths
- Understand what audiences actually disliked
- Generate improvements grounded in real sentiment
- Share alternate endings with others

## 2.2 Opportunity
By combining:
- Review analysis
- Semantic clustering
- Structured plot understanding
- Interactive AI generation
- Explainable scoring

We create a platform that turns passive movie critique into participatory storytelling.

---

# 3. Goals & Non-Goals

## 3.1 Goals (MVP)

G1 — Generate alternate endings grounded in real audience complaints  
G2 — Provide interactive branching story experience (3 steps max)  
G3 — Deliver explainable Theme Coverage Score  
G4 — Show transparent evidence (reviews + cluster mapping)  
G5 — Enable save + share + vote functionality  
G6 — Use Actian Vector DB meaningfully  
G7 — Use Sphinx for structured reasoning  
G8 — Demonstrate reproducible data pipeline via Databricks  

## 3.2 Non-Goals

- Full movie script ingestion
- Real-time clustering during user sessions
- Complex authentication system
- Large-scale moderation system
- More than 3 movies in MVP
- More than 3 branching steps per story

---

# 4. Target Users

## 4.1 Primary Users
- Casual movie fans
- Reddit discussion participants
- Film students
- Aspiring writers

## 4.2 Secondary Users
- Community browsers exploring alternate endings
- Content creators

---

# 5. User Stories

## 5.1 Discovery & Search

- As a user, I want to **search by movie name** so I can find a specific title instead of browsing a fixed list.
- As a user, I want to type (or select) a movie and **go straight to that movie’s analysis** (ratings, complaint clusters, plot beats, what-if suggestions).

## 5.2 Analysis Stage

- As a fan, I want to see what audiences complained about.
- As a fan, I want to see example reviews backing those complaints.
- As a user, I want to understand how those complaints map to the movie's plot.

## 5.3 Branching Experience (Rewrite Flow)

- As a fan, I want to select a data-driven "what-if" suggestion (e.g. "What if the hero never died").
- As a user, I want the app to set the stage with a typing animation so I’m reminded of the story and the branch point.
- As a user, I want to see the twist (“But what if…”) narrated with typing, then be asked to choose option 1, 2, or 3.
- As a user, I want to make exactly 3 structured choices, with the story narrating what happens after each choice (typing), then the next question.
- As a user, I want the story to wrap up with a final typing passage after my third choice, then land on the ending + score page.

## 5.4 Evaluation

- As a user, I want to see how well my new ending fixed complaints.
- As a user, I want proof and explanation.
- As a user, I want a clear score breakdown.

## 5.5 Community

- As a user, I want to save my ending.
- As a user, I want to view other users’ endings.
- As a user, I want to vote on the best endings.
- As a user, I want to explore top endings across movies.

---

# 6. Core Product Flow

1. **Entry:** User either **selects one of the featured movies** on the home page (each shown as a **poster with bottom overlay**: Rotten Tomatoes + audience scores) **or** uses **Search** (see §6.2): types a movie name, sees results, and opens a movie.
2. **Analysis Dashboard** loads for the chosen movie:
   - **Movie poster** as the hero (full poster with bottom overlay showing Rotten Tomatoes + audience scores)
   - Complaint clusters
   - Example reviews
   - Plot beats
   - Branchable moments
3. User selects a "What-if" suggestion (e.g. "What if the hero never died").
4. **Rewrite experience** (see §6.1): typing animation sets the stage, presents the twist, then 3 choice rounds with narration between each; after the 3rd choice, a wrap-up is narrated and the user is taken to the ending page.
5. Final alternate ending and Theme Coverage Score displayed; evidence panel shown.
6. User can save, share, and browse community endings.

---

## 6.1 Rewrite Experience (Detailed User Flow)

The Rewrite is the core interactive story. It uses a **typing animation** throughout so the user feels the story is being told in real time. The flow is **phased**: set stage → twist → choice → narrate (repeated 3 times) → wrap-up.

**Connection to data:** Each what-if suggestion is tied to one or more complaint clusters (e.g. "Rushed Ending", "Character Arc Inconsistency"). The narrative copy sets the stage using that context and branches from a defined plot beat.

### Phases in order

| Phase | What the user sees |
|-------|--------------------|
| **1. Set the stage** | Typing animation: reminder of the story and complaint context, then the plot **right up until the branch point** (e.g. "In the original, the hero snapped and died…"). |
| **2. Twist** | Typing continues: "But what if [the hero never died]? He snapped and stayed alive and did XYZ…" — the alternate premise is laid out. |
| **3. Choice 1** | Typing plays a short lead-in (e.g. "So the question is: how does the hero’s story end?"). Then **three options** appear (e.g. option 1, 2, 3). User picks one. |
| **4. Narrate 1** | Typing narrates what happens **based on that choice** — the story continues. |
| **5. Choice 2** | Typing plays the second lead-in. Three options appear. User picks one. |
| **6. Narrate 2** | Typing narrates the consequence of choice 2. |
| **7. Choice 3** | Typing plays the third lead-in. Three options appear. User picks one. |
| **8. Narrate 3** | Typing narrates the consequence of choice 3. |
| **9. Wrap-up** | Typing narrates a **final paragraph** that ties the alternate ending together. |
| **10. Hand-off** | User is navigated to the **Ending** page (summary, Theme Coverage Score, evidence panel, save/share). |

**Design notes:**

- **Typing only:** All narrative (stage, twist, lead-ins, narrations, wrap-up) is shown via the same typing component so the experience feels continuous.
- **Exactly 3 choices:** Each choice round has 2–3 options (typically 3). There are exactly 3 rounds; after the 3rd, the story wraps and does not offer more choices.
- **Clusters → what-if:** What-if suggestions are generated from complaint clusters (e.g. "What if the ending had room to breathe" from "Rushed Ending"). The stage/twist copy can reference that cluster so the user sees the link.
- **Progress:** The UI can show "Choice 1 of 3", "Choice 2 of 3", "Choice 3 of 3", and a progress indicator so the user knows how many choices remain.

---

## 6.2 Search Feature / Search Page

Users can find a movie by name and go directly to its analysis instead of browsing a fixed list.

### Behavior

- **Search page or search input:** A dedicated **Search** entry point (e.g. nav link to `/search`, or a search field in the header).
- **User types a movie name** (e.g. "Inception", "Game of Thrones"). Search can be **as-you-type** (suggestions) or **on submit** (e.g. button or Enter).
- **Results:** Show matching movies from the catalog (MVP: the 3 supported movies; later: expanded catalog). Each result uses the **movie poster component**: poster image as the card with a bottom overlay showing Rotten Tomatoes and audience scores (and optionally title).
- **Open movie:** User clicks a result (or selects the only match). The app **navigates to that movie’s Analysis Dashboard** (same view as when opening a movie from the home page): ratings, complaint clusters, example reviews, plot beats, what-if suggestions. From there the user can start a Rewrite or explore as usual.

### User flow (search path)

1. User goes to Search (e.g. clicks "Search" in nav or focuses search field).
2. User types (e.g. "incep" or "Inception").
3. User sees one or more matching movies.
4. User selects a movie → **Analysis Dashboard** for that movie loads.
5. User continues with What-if → Rewrite → Ending as in the main flow.

### Scope (MVP)

- Search is **client-side** over the current movie catalog (e.g. the 3 MVP movies). Matching can be by substring or normalized title (case-insensitive, trim).
- If no movie matches, show an empty state or message (e.g. "No movies found. Try another name or browse featured movies.") with a link back to home or featured list.

---

# 7. Functional Requirements

## 7.1 Review Ingestion & Clustering

FR-1 Ingest 500–2000 reviews per movie  
FR-2 Clean + chunk into 1–3 sentence units  
FR-3 Generate embeddings  
FR-4 Cluster into 10–20 complaint themes  
FR-5 Label clusters using Gemini  
FR-6 Store cluster metadata in Supabase  
FR-7 Store embeddings in Actian Vector DB  

---

## 7.2 Plot Structuring

FR-8 Generate structured plot beats from Wikipedia/TMDB  
FR-9 Identify 3–6 branchable beats  
FR-10 Store beats in Supabase  
FR-11 Embed beats into Actian  

---

## 7.3 Complaint → Plot Mapping

FR-12 Map complaint clusters to plot beats  
FR-13 Generate "What-if" suggestions targeting top clusters  

---

## 7.4 Interactive Story Engine (Rewrite)

FR-14 Start story from selected branch point (driven by what-if suggestion and its cluster(s)).  
FR-15 Present narrative in order: set stage (typing) → twist (typing) → lead-in (typing) → 2–3 choices → narration (typing); repeat for 3 choice rounds.  
FR-16 Use a typing animation for all narrative segments so the user experiences the story as it’s “told.”  
FR-17 Maintain structured story state (choices 1–3); cap at exactly 3 steps.  
FR-18 After the 3rd choice, narrate wrap-up (typing), then generate/display final ending and hand off to Ending page.  

---

## 7.5 Scoring & Reasoning (Sphinx)

FR-19 Compute Complaint Coverage Score  
FR-20 Compute Preference Satisfaction Score  
FR-21 Compute Coherence Score  
FR-22 Produce structured explanation report  
FR-23 Display per-cluster evidence  

---

## 7.6 Community Features

FR-24 Save ending under movie  
FR-25 Generate shareable URL  
FR-26 Display movie-specific ending list  
FR-27 Enable voting  
FR-28 Display global explore leaderboard  

---

## 7.7 Search

FR-29 Provide a Search entry point (dedicated page and/or header search) where the user can type a movie name.  
FR-30 Match user input against the movie catalog (e.g. by title substring, case-insensitive); return matching movies.  
FR-31 On selection of a search result, navigate to that movie’s Analysis Dashboard (same content as opening the movie from home).  
FR-32 Handle no-results: show empty state and option to go back to home or featured movies.  

---

## 7.8 Scrapers & data ingestion

FR-33 **IMDb scraper (built):** Scrape IMDb for user reviews per movie; store/use for clustering and evidence.  
FR-34 **Wikipedia plot scraper:** Scrape the **Plot** section of a movie’s Wikipedia page; store as the canonical movie plot (for plot beats, context in story generation, and display).  
FR-35 Persist scraped plot (e.g. in `movies` or a dedicated store) so it can be served by the backend and used by Gemini/session logic.

---

## 7.9 Backend routes (FastAPI)

All backend logic is implemented as **FastAPI** routes. Key routes:

| Route / area | Purpose |
|--------------|--------|
| **Reviews** | Get reviews for a movie (from DB/cache after IMDb scrape). Used by frontend for analysis and evidence. |
| **Plot** | Get (or trigger fetch of) movie plot — from stored Wikipedia Plot section. Used for analysis dashboard and as context for story generation. |
| **Embeddings (Actian)** | Get or create embeddings in Actian Vector AI DB: e.g. embed review chunks or plot units; support semantic search / retrieval for story and scoring. Idempotent “get or create” so we don’t duplicate vectors. |
| **Story generation (Gemini)** | Generate story content using a **strong system prompt** for Gemini: define role, tone (refined / narrative, on-brand), structure (intro, twist, lead-ins, narrations, wrap-up), and output format (e.g. plain text or JSON). Use one consistent system prompt across all story steps so output is structured, on-theme, and safe. |
| **Ending / scoring** | Generate final alternate ending and (where applicable) call Sphinx for Theme Coverage Score; return score + per-cluster evidence. |

Additional routes as needed: movies list, complaint clusters, plot beats, what-if suggestions, save ending, vote, explore leaderboard — all implemented in FastAPI.

---

# 8. System Architecture

**Backend:** The entire backend is **FastAPI**. All server-side tasks (reviews, plot, embeddings, story generation, scoring, persistence) are exposed as FastAPI routes. See §7.9 for the main routes.

## 8.1 Data ingestion (scrapers)

- **IMDb scraper (built):** Scrapes IMDb for user reviews per movie. Output is stored and used for clustering, evidence, and the “get reviews” route.
- **Wikipedia plot scraper:** Scrapes the **Plot** section of a movie’s Wikipedia article. That text is stored as the movie’s plot (e.g. in Supabase `movies` or a plot store) and used for the plot route, analysis UI, and as context in story generation (Gemini).

Scraped data flows into Supabase (and optionally into Actian after embedding). Databricks may still be used for batch processing (clean, chunk, cluster); the API can also trigger or consume that pipeline.

## 8.2 Offline / batch pipeline (precompute)

Databricks (optional batch path):
- Ingest reviews (e.g. from scraper output)
- Clean & chunk
- Generate embeddings
- Cluster embeddings
- Export cluster artifacts

Gemini:
- Label clusters
- Generate structured plot beats
- Map clusters to beats

Storage:
- Supabase (structured data: movies, plot, reviews metadata, clusters, beats, generations, votes)
- Actian Vector DB (embeddings for review chunks / plot units; used for retrieval)

## 8.3 Online runtime (FastAPI)

User → Frontend → **FastAPI backend** (routes in §7.9)

Backend responsibilities:
- **Reviews route:** Return reviews for a movie (from DB/cache populated by IMDb scraper).
- **Plot route:** Return or fetch movie plot (Wikipedia Plot section, stored after scrape).
- **Embeddings route:** Get or create embeddings in **Actian Vector AI DB** (e.g. for review chunks or plot); idempotent so vectors aren’t duplicated.
- **Story generation route(s):** Call **Gemini** with a **strong system prompt** to generate intro, twist, lead-ins, narrations, and wrap-up; return structured content for the Rewrite flow.
- **Ending / scoring:** Generate final ending (Gemini); call Sphinx for Theme Coverage Score; return score + per-cluster evidence.
- Persist generations, votes, and serve movies/clusters/beats/what-if data as needed.

---

# 9. Database Schema

## 9.1 Supabase Tables

movies (includes or references stored **plot** from Wikipedia Plot scraper)  
plot_beats  
complaint_clusters  
cluster_examples  
what_if_suggestions  
generations  
votes  
(reviews / review metadata as needed for “get reviews” route and clustering)

## 9.2 Actian Collections

review_chunks  
plot_units  
cluster_exemplars  

---

# 10. Theme Coverage Score

## 10.1 Score Components

Total Score = Weighted sum of:

- Complaint Coverage (50%)
- Preference Satisfaction (25%)
- Coherence (25%)

## 10.2 Output Structure

{
  "score_total": 82,
  "breakdown": {
    "complaint_coverage": 88,
    "preference_satisfaction": 75,
    "coherence": 83
  },
  "per_cluster": [
    {
      "cluster_label": "Rushed Ending",
      "addressed": true,
      "evidence_excerpt": "...",
      "review_reference": "..."
    }
  ]
}

---

# 11. UI / Design System

## Theme: Refined elegance palette (luxury branding)

Color system:

| Role | Color name | Hex |
|------|------------|-----|
| **Background** | Eerie Black | #1B1B1B |
| **Surface / panels** | Sophisticated Sage | #C4C5BA |
| **Primary text** | Ethereal Ivory | #E4E4DE |
| **Accent / emphasis** | Muted Moss | #595f39 |

- **Ethereal Ivory** (#E4E4DE) — Light cream; primary text and key UI copy.  
- **Sophisticated Sage** (#C4C5BA) — Light green-gray; surfaces, cards, secondary backgrounds.  
- **Eerie Black** (#1B1B1B) — Deep black; page and section backgrounds.  
- **Muted Moss** (#595f39) — Olive-green; accents, CTAs, score highlights, links.

Design principles:
- High contrast (Ethereal Ivory on Eerie Black; Muted Moss for emphasis).
- Minimalist, refined elegance.
- Use Muted Moss sparingly for accents and data (e.g. scores, buttons).
- Structured data panels on Sophisticated Sage or Eerie Black.

### Movie poster component

- **Primary component:** The movie is represented by its **poster image** as the whole component (e.g. on the home grid, search results, and at the top of the Analysis Dashboard). The poster is the main visual—not a small thumbnail beside text.
- **Bottom overlay:** A **gradient or solid overlay** at the bottom of the poster shows:
  - **Rotten Tomatoes** (tomatometer) score (e.g. percentage and/or Fresh/Rotten).
  - **Audience** score (e.g. percentage).
- Overlay should stay readable on any poster (e.g. dark gradient, semi-opaque Eerie Black or Sophisticated Sage, with Muted Moss for score values). Use Ethereal Ivory for score labels and Muted Moss (#595f39) for the score values as needed.
- Where the full poster is the card (e.g. home, search), the movie title can sit on the overlay or below the poster; clicking the card opens that movie’s analysis.

### Search

- **Search page or header search:** Users can open Search (e.g. via nav link to `/search` or a search field in the header). The search UI shows an input for movie name and, on input/submit, a list of matching movies.
- **Results:** Each result uses the movie poster component (poster image with bottom overlay for Rotten Tomatoes + audience). Each result is clickable and opens the selected movie's Analysis Dashboard. Design aligns with the refined elegance palette (Sophisticated Sage surface, Muted Moss accent, high contrast).
- **Empty state:** When there are no matches, show a clear message and a link to the home/featured list.

### Rewrite / Story UX

- **Typing animation:** Narrative in the Rewrite flow (stage, twist, lead-ins, post-choice narrations, wrap-up) is revealed via a character-by-character typing animation with a visible cursor. Speed is configurable (e.g. ~18–25 ms per character). This creates a “story being told” feel and keeps focus on one passage at a time.
- **Single narrative panel:** One main content area shows either the typing text or the current choice options (lead-in text remains visible above the options).
- **Progress:** Show “Choice 1 of 3” (etc.) and a step indicator so users know where they are in the 3-choice flow.

---

# 13. Risks & Mitigations

Risk: Story incoherence  
Mitigation: Structured plot beats + retrieval constraints  

Risk: LLM JSON failures  
Mitigation: Strict schema validation + retries  

Risk: Data pipeline delays  
Mitigation: Use reduced review sample  

Risk: Scope creep  
Mitigation: Strict 3-movie, 3-step cap  

---

# 14. Definition of Done

✔ 3 movies fully functional  
✔ **Search:** user can type a movie name and open that movie’s analysis  
✔ **Movie poster component:** poster as whole component with bottom overlay (Rotten Tomatoes + audience) on home, search, and Analysis hero  
✔ Complaint clusters visible  
✔ Plot beats visible  
✔ 3-step branching working  
✔ Final ending generated  
✔ Theme Coverage Score shown  
✔ Evidence panel displayed  
✔ Save + vote enabled  
✔ Explore page working  
✔ **Backend:** FastAPI with routes for reviews, plot, embeddings (Actian), story generation (Gemini), ending/scoring  
✔ **Scrapers:** IMDb user-review scraper (built); Wikipedia Plot-section scraper for movie plot storage  
✔ **Actian:** Route to get or create embeddings in Actian Vector AI DB  
✔ **Gemini:** Story generation route(s) with strong system prompt for intro/twist/narrations/wrap-up  
✔ Databricks notebook reproducible (optional batch path)  

---

# 15. Positioning Statement

DirectorsCut is a data-driven narrative engine that transforms passive movie critique into interactive, evidence-backed storytelling.

It merges:
- AI creativity
- Audience intelligence
- Explainable reasoning
- Community participation

---

End of PRD.