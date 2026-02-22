# DirectorsCut

DirectorsCut is a full-stack movie rewrite app with a FastAPI backend and React frontend. It lets you search films, analyze what audiences hated, and generate alternate endings with AI.

## Features

- **Movie search & preparation pipeline**: OMDB → IMDb user reviews → critic join → embeddings (Supabase pgvector) → complaint clustering → what-if suggestions
- **Analysis dashboard**: Poster hero, complaint clusters (with taglines), plot beats, character analysis, review evidence, and an interactive **knowledge graph** (Neo4j + Cytoscape)
- **3-step rewrite flow**: Typing narrative with Gemini-backed generation; choose a what-if and branch through story options
- **Ending score & community**: Theme coverage scoring, anonymous save, voting, and explore leaderboard
- **Optional TTS**: ElevenLabs text-to-speech for endings

## Repository Layout

- `backend/`: FastAPI API, Supabase datastore, Neo4j knowledge graph, pipeline, integrations (OMDB, Wikipedia, Gemini, ElevenLabs), tests
- `frontend/`: React 18 + Vite 6 + TypeScript; pages: Home, Analysis, Rewrite, Ending, Explore
- `docs/`: Pipeline notes, Actian/vector DB docs
- `start.sh`: One-command startup for backend + frontend

## Quick Start

From the project root:

```bash
./start.sh
```

This starts:
- **Backend**: http://localhost:8000
- **Frontend**: http://localhost:5173
- **API docs**: http://localhost:8000/docs

The script runs `uvicorn app.main:app` in `backend/` and `npm run dev` in `frontend/`.

## Backend Setup

1. Create and activate a Python 3.11 virtualenv:
```bash
cd backend
python3.11 -m venv .venv
source .venv/bin/activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Configure environment:
```bash
cp .env.example .env
```

4. Required variables:
- `SUPABASE_URL` – Supabase project URL
- `SUPABASE_SERVICE_ROLE_KEY` – Service role key (for DB + RPC)
- `OMDB_API_KEY` – [OMDB API](https://www.omdbapi.com/) key

5. Optional but recommended:
- `GEMINI_API_KEY` – For story generation, plot expansion, character analysis
- `USE_SUPABASE_VECTOR=true` – Use pgvector for embeddings (falls back to in-memory if disabled/unavailable)
- `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD` – For knowledge graph (gracefully disabled if not configured)
- `ELEVENLABS_API_KEY`, `ELEVENLABS_VOICE_ID` – For TTS (optional)

6. Run API:
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## Frontend Setup

1. Install packages:
```bash
cd frontend
npm install
```

2. Optional env (`frontend/.env`):
```bash
VITE_API_BASE=http://localhost:8000/api
```

3. Run dev server:
```bash
npm run dev
```

## Supabase Migrations (Required)

Run these SQL files in order in the Supabase SQL Editor (enable the `vector` extension first if needed):

1. `backend/app/migrations/0001_directorscut_schema.sql` – Core tables
2. `backend/app/migrations/0002_add_cluster_tagline.sql` – Tagline column for clusters
3. `backend/app/migrations/0002_review_embeddings_pgvector.sql` – pgvector extension + `review_embeddings` table + `match_review_embeddings` RPC
4. `backend/app/migrations/0003_movie_characters.sql` – `movie_characters` table

Core tables: `movies`, `plot_summary`, `plot_beats`, `complaint_clusters`, `cluster_examples`, `what_if_suggestions`, `movie_characters`, `generations`, `votes`, `user_reviews`, `critic_reviews`, `review_embeddings`.

## API Highlights

| Endpoint | Description |
|----------|-------------|
| `GET /api/health` | Status (store, vector, embedding, Neo4j) |
| `GET /api/movies/featured` | Featured movies for home carousel |
| `GET /api/movies/search?q=` | Search movies (local + OMDB) |
| `POST /api/pipeline/search` | Start preparation job |
| `GET /api/pipeline/jobs/{job_id}` | Poll job status |
| `POST /api/movies/{id}/prepare` | Prepare movie by ID |
| `POST /api/movies/{id}/refresh-plot` | Re-scrape Wikipedia, regenerate plot beats |
| `GET /api/movies/{id}/analysis` | Full analysis (plot, beats, characters, clusters, what-ifs, reviews) |
| `GET /api/movies/{id}/graph` | Knowledge graph for Cytoscape |
| `GET /api/movies/{id}/reviews` | Paginated reviews |
| `GET /api/movies/{id}/plot` | Plot summary + expanded plot |
| `POST /api/embeddings/index` | Index review embeddings for a movie |
| `POST /api/search/vector` | Vector similarity search over reviews |
| `POST /api/story/start` | Start rewrite session |
| `POST /api/story/step` | Advance story (choose option) |
| `POST /api/story/coverage` | Theme coverage score |
| `POST /api/generations` | Save generation |
| `GET /api/generations/{id}` | Generation details |
| `POST /api/generations/{id}/vote` | Vote on generation |
| `GET /api/explore/leaderboard` | Leaderboard |
| `POST /api/tts/generate` | ElevenLabs TTS (when configured) |

## Testing

From `backend/`:
```bash
pytest app/tests -q
```

## Notes

- Search is the primary entry point and supports multi-match selection.
- If no critic reviews are found, the pipeline continues with user reviews only.
- If Wikipedia plot extraction fails, the pipeline falls back to OMDB plot.
- Vector store uses Supabase pgvector when `USE_SUPABASE_VECTOR=true`; otherwise in-memory fallback.
- Neo4j knowledge graph is optional; the app works without it.
- Share button is intentionally non-functional in this MVP and shown as "Coming soon".
