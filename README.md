# DirectorsCut

DirectorsCut is a full-stack movie rewrite app with a FastAPI backend and React frontend. It supports:
- Movie search and preparation pipeline (OMDB -> IMDb user reviews -> critic join -> embeddings -> clusters -> what-if suggestions)
- Analysis dashboard (poster hero, complaint clusters, plot beats, review evidence)
- 3-step interactive rewrite flow with typing narrative and Gemini-backed generation
- Ending score/evidence, anonymous save, voting, and explore leaderboard

## Repository Layout

- `backend/`: FastAPI API, integrations, pipeline, tests, SQL migration
- `frontend/`: React + Vite client UI
- `project_tracker.md`: phase tracker

## Backend Setup

1. Create and activate a Python 3.11 virtualenv:
```bash
cd backend
python3.11 -m venv .venv
source .venv/bin/activate
```

2. Install dependencies:
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

3. Configure environment:
```bash
cp .env.example .env
```

4. Set at minimum:
- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY`
- `OMDB_API_KEY`
- `GEMINI_API_KEY` (optional but recommended)
- `ENABLE_ACTIAN=true` (optional if Actian is installed and reachable)

5. Run API:
```bash
uvicorn main:app --reload --port 8000
```

### Actian Notes

The backend automatically falls back to in-memory vector search if Actian is unavailable or disabled.
To use Actian:
- run your Actian VectorAI DB container on `ACTIAN_ADDRESS` (default `127.0.0.1:50051`)
- install the Actian cortex Python wheel in your environment
- set `ENABLE_ACTIAN=true`

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

## Supabase Migration (Required)

Run the SQL migration in Supabase SQL Editor:
- `backend/app/migrations/0001_directorscut_schema.sql`

This migration creates:
- `movies`
- `plot_summary`
- `plot_beats`
- `complaint_clusters`
- `cluster_examples`
- `what_if_suggestions`
- `generations`
- `votes`

and adds useful indexes plus optional `user_reviews.review_id` dedupe index.

## API Highlights

- `POST /api/pipeline/search` starts preparation job
- `GET /api/pipeline/jobs/{job_id}` polls progress
- `GET /api/movies/{movie_id}/analysis` returns full analysis payload
- `POST /api/story/start` / `POST /api/story/step` powers rewrite flow
- `POST /api/story/coverage` computes theme coverage
- `POST /api/generations` + `POST /api/generations/{id}/vote`
- `GET /api/explore/leaderboard`

## Testing

From `backend/`:
```bash
pytest app/tests -q
```

## Notes

- Search is designed as the primary entry point and supports multi-match selection.
- If no critic reviews are found, the pipeline continues with user reviews only.
- If Wikipedia Plot extraction fails, the pipeline falls back to OMDB plot.
- Share button is intentionally non-functional in this MVP and shown as "Coming soon".
