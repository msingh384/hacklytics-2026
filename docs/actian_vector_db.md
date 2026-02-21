## 1. Overview



**Demo flow:**
s
1. User selects a movie → backend returns top 5 review chunks (via vector search for a fixed critical query).

2. User selects one chunk → backend uses that chunk plus the top 3 similar chunks as evidence, calls Gemini to generate 3 alternate ending options, returns them.



**Architecture:**

- Python 3.11 backend with FastAPI

- Actian VectorAI DB (optional; falls back to mock mode if unreachable)

- Sentence-transformers for embeddings (384-dim, cosine)

- Google Gemini 2.5 Flash for alternate ending generation



---



## 2. Environment Requirements



| Requirement | Version / Details |

|-------------|-------------------|

| Python | 3.11 (use 3.11 venv; avoid 3.13 for sentence-transformers) |

| Actian VectorAI DB | Docker container, port 50051 |

| Embedding model | sentence-transformers/all-MiniLM-L6-v2 (384 dims, cosine similarity) |

| LLM | Google Gemini 2.5 Flash |



**Critical dependency constraints:**

- `numpy>=1.26,<2` (torch 2.2 + sentence-transformers need numpy 1.x; Actian prefers 2.x but works)

- `protobuf>=6.31` (Actian cortex requires this; google-generativeai may pull older version — upgrade after install)



---



## 3. File Structure



```

project-root/

├── backend/

│   ├── app.py              # FastAPI server

│   ├── ingest.py           # One-time ingestion script

│   ├── requirements.txt

│   ├── .env                # GEMINI_API_KEY (do not commit)

│   ├── .env.example        # Template for GEMINI_API_KEY

│   └── .gitignore          # .venv/, .env, __pycache__/

├── t25_critic_reviews.json # Source data (converted from CSV)

├── t25_critic_reviews.csv  # Original CSV (optional)

└── actian-vectorAI-db-beta/

    └── docker-compose.yml  # Actian container config

```



---



## 4. Data Format



### 4.1 t25_critic_reviews.json



Array of objects. Each object:



| Field | Type | Required | Description |

|-------|------|----------|-------------|

| chunk_id | int | Yes | Unique ID (0-indexed global) |

| movie_id | str | Yes | IMDb ID (e.g. tt0107290) |

| text | str | Yes | Review excerpt (embedded for search) |

| title | str | Optional | Movie title (for title-based lookup) |

| year | str | Optional | Release year |

| critic_name | str | Optional | Critic name |

| review_type | str | Optional | e.g. Fresh, Rotten |



**Conversion from CSV:**

- Columns: IMDb_ID → movie_id, Title → title, Year → year, review_content → text

- Skip rows with empty review_content

- chunk_id = row index in resulting array



---



## 5. Backend: app.py (Full Spec)



### 5.1 Imports



```

json, os, re, Path (pathlib)

dotenv.load_dotenv

contextlib.asynccontextmanager

fastapi: FastAPI, HTTPException

fastapi.middleware.cors: CORSMiddleware

pydantic: BaseModel

sentence_transformers: SentenceTransformer

cortex: CortexClient, DistanceMetric, Filter, Field

```



### 5.2 Configuration



| Constant | Value |

|----------|-------|

| ACTIAN_ADDRESS | 127.0.0.1:50051 |

| COLLECTION | review_chunks |

| DIMENSION | 384 |

| DATA_FILE | Path(__file__).parent.parent / "t25_critic_reviews.json" |

| FIXED_QUERY | "ending rushed plot holes unsatisfying resolution" |



### 5.3 Lifespan (Startup)



1. Load embedding model: `SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")`

2. Try connect to Actian at ACTIAN_ADDRESS

3. On success: set `client = CortexClient`; on failure: set `client = None`, load `mock_chunks` from DATA_FILE (JSON)

4. On shutdown: if client, call `client.close()`



### 5.4 CORS



Allow all origins, methods, headers.



### 5.5 Models



**GenerateRequest**

- chunk_id: int | None = None

- chunk_index: int | None = None  # 0–4, index into top 5 results



**ChunkResponse**

- chunk_id: int

- text: str

- score: float



**AlternateEnding**

- option: int

- ending: str

- based_on_chunk_id: int



**GenerateResponse**

- evidence_chunks: list[dict]  # [{chunk_id, text}, ...]

- alternate_endings: list[AlternateEnding]



### 5.6 GET /movies/{movie_id}/top-chunks



**Path param:** movie_id (IMDb ID like tt0107290, or movie title for partial match)



**Logic:**

- If Actian connected: embed FIXED_QUERY, search Actian with filter movie_id=…, top_k=5, return ChunkResponse[]

- If mock mode: filter chunks by _chunks_for_movie(movie_id), embed query and all chunks, compute cosine scores, return top 5 ChunkResponse

- 404 if no chunks for movie



**_chunks_for_movie(movie_id):**

- If movie_id matches IMDb pattern (tt + digits): filter by c["movie_id"] == movie_id

- Else: case-insensitive partial match on c["title"]



### 5.7 POST /movies/{movie_id}/generate-ending



**Body:** GenerateRequest (chunk_id and/or chunk_index)



**Logic:**

1. Resolve chunk:

   - If chunk_index in 0–4: get top 5 for movie, pick chunk at index

   - Else if chunk_id: fetch chunk from Actian or mock_chunks, validate it belongs to movie

2. Get top 3 similar chunks (seed = chosen chunk):

   - Mock: _get_top_3_chunks(movie_id, chunk) — embed seed text, rank all chunks for movie, take top 3

   - Actian: embed chunk text, search with filter movie_id, top_k=3

3. Call Gemini: prompt with 3 chunks, ask for "OPTION 1: … OPTION 2: … OPTION 3: …"

4. Parse response, map each option to based_on_chunk_id from chunks

5. Return GenerateResponse(evidence_chunks, alternate_endings)



**Gemini prompt (exact format):**

```

You are a creative screenwriter. Here are 3 critic review excerpts about a film:



Excerpt 1 (chunk_id=X): [text]

Excerpt 2 (chunk_id=Y): [text]

Excerpt 3 (chunk_id=Z): [text]



Generate exactly 3 SHORT alternate ending options (2-4 sentences each) that address these reviewers' concerns. Each ending should be grounded in the corresponding excerpt. Use this exact format:



OPTION 1: [your ending here]

OPTION 2: [your ending here]

OPTION 3: [your ending here]

```



**Gemini model:** gemini-2.5-flash  

**API key:** GEMINI_API_KEY env var (loaded from .env via python-dotenv)



---



## 6. Backend: ingest.py (Full Spec)



**Purpose:** One-time ingestion of JSON into Actian VectorAI DB.



**Data source:** t25_critic_reviews.json (same format as above)



**Steps:**

1. Load SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")

2. Load JSON chunks

3. Embed all texts with normalize_embeddings=True

4. Connect CortexClient(ACTIAN_ADDRESS)

5. get_or_create_collection(name=review_chunks, dimension=384, distance_metric=COSINE)

6. batch_upsert: ids=chunk_id[], vectors=embeddings.tolist(), payloads=[{movie_id, text}]

7. flush(collection)



---



## 7. Backend: requirements.txt



```

fastapi

uvicorn[standard]

numpy>=1.26,<2

sentence-transformers>=2.2,<4

google-generativeai

```



**Additional install (not in requirements.txt):**

- Actian wheel: `actiancortex-0.1.0b1-py3-none-any.whl` (from actian-vectorAI-db-beta/)

- After install: `pip install "protobuf>=6.31"` if protobuf version conflict



---



## 8. Actian VectorAI DB (Docker)



**docker-compose.yml:**

```yaml

version: "3.8"

services:

  vectoraidb:

    image: williamimoh/actian-vectorai-db:1.0b

    platform: linux/amd64   # For Mac Apple Silicon

    container_name: vectoraidb

    ports:

      - "50051:50051"

    volumes:

      - ./data:/data

    restart: unless-stopped

```



**Commands:** `docker compose up -d` / `docker compose down`



**Note:** On some Mac setups, gRPC may fail with "Connection reset by peer". The app supports mock mode when Actian is unreachable.



---



## 9. Environment Variables



| Variable | Required | Description |

|----------|----------|-------------|

| GEMINI_API_KEY | Yes (for generate-ending) | Google AI Studio API key |



**.env example:**

```

GEMINI_API_KEY=your_key_here

```



---



## 10. Setup Commands (Copy-Paste)



```bash

# 1. Python 3.11 venv

cd backend

python3.11 -m venv .venv

source .venv/bin/activate



# 2. Install

pip install --upgrade pip

pip install ../actian-vectorAI-db-beta/actiancortex-0.1.0b1-py3-none-any.whl

pip install -r requirements.txt

pip install "protobuf>=6.31"   # if needed



# 3. Actian (optional)

cd ../actian-vectorAI-db-beta

docker compose up -d



# 4. Ingest (if Actian running)

cd ../backend

python ingest.py



# 5. Run server

uvicorn app:app --host 0.0.0.0 --port 8000

```



---



## 11. API Examples



**GET /movies/tt0107290/top-chunks** → 200, list of 5 ChunkResponse  

**GET /movies/Jurassic%20Park/top-chunks** → 200 (title lookup)



**POST /movies/tt0107290/generate-ending**

```json

{"chunk_index": 0}

```

or

```json

{"chunk_id": 123}

```



**Response:**

```json

{

  "evidence_chunks": [{"chunk_id": 0, "text": "..."}, ...],

  "alternate_endings": [

    {"option": 1, "ending": "...", "based_on_chunk_id": 0},

    {"option": 2, "ending": "...", "based_on_chunk_id": 1},

    {"option": 3, "ending": "...", "based_on_chunk_id": 2}

  ]

}

```



---



## 12. Mock Mode Behavior



When Actian is unreachable at startup:

- mock_chunks = load DATA_FILE

- GET top-chunks: in-memory vector similarity (embed query, embed all chunks for movie, cosine, top 5)

- POST generate-ending: lookup in mock_chunks, _get_top_3_chunks in-memory, Gemini call unchanged



---



## 13. Key Design Decisions



1. **chunk_index vs chunk_id:** Frontends may send array index (0–4) instead of chunk_id; both supported.

2. **movie_id flexibility:** Accept IMDb ID or title (partial, case-insensitive) for mock mode.

3. **Actian graceful fallback:** Server starts even if Actian fails; endpoints return 503 only when Actian-specific ops are needed (or mock mode covers it).

4. **Use 127.0.0.1** for Actian address to avoid IPv6/localhost issues on some Macs.

5. **numpy 1.x:** Kept for torch/sentence-transformers; Actian may show a warning but works.