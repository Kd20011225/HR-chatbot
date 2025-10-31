# HR Assistant — Backend (FastAPI) + Frontend (Next.js)

A full-stack HR assistant with three modes:

- **Policy** — Ask questions over HR docs stored in **Google Drive**, powered by **LlamaIndex**.
- **Data** — Ask questions over an **HR CSV** with a **LangChain** DataFrame agent.
- **Nearby** — Search **Google Maps Places** and show details with photos and directions.

## Tech Stack

- **Backend:** FastAPI, Uvicorn, Requests  
- **LLM / RAG:** LangChain (OpenAI, FAISS, BM25, HuggingFaceEmbeddings), LlamaIndex (Google Drive reader)  
- **Data:** pandas (CSV)  
- **Frontend:** Next.js (app router, client component), shadcn/ui `Button`, Heroicons  
- **Auth/Keys:** Environment variables via `.env` (never commit secrets)

---

## Monorepo Layout

```
repo/
  backend/
    main_integrated.py         # FastAPI app (this file)
                               # sample or your CSV (optional)
    llamaindex_store/          # persisted index (auto-created)
    credentials.json           # (local) GCP service account (DO NOT COMMIT)
    .env                       # local secrets (DO NOT COMMIT)
  frontend/
    (Next.js app)
```

---
## Setup

### Backend

```bash
cd backend
# create venv (recommended)
python -m venv .venv
# activate
#   Windows PowerShell: .\.venv\Scripts\Activate.ps1
#   macOS/Linux:        source .venv/bin/activate

pip install --upgrade pip
pip install fastapi uvicorn python-dotenv requests pandas
pip install langchain langchain-community langchain-openai langchain-huggingface faiss-cpu
pip install llama-index llama-index-readers-google llama-index-readers-file
```

Place your `credentials.json` (Google **Service Account** key) in `backend/` and set `GDRIVE_SA_JSON=credentials.json` in `.env`.

### Frontend

```bash
cd frontend
npm install
# or: pnpm i / yarn
```

---

## Running

### 1) Start the backend (FastAPI)

```bash
cd backend
uvicorn main_integrated:app --host 127.0.0.1 --port 8000 --reload
```

Health check: open http://127.0.0.1:8000/health → `{"status":"ok"}`

### 2) Build the Knowledge Base (only needed once or when Drive changes)

```bash
# POST /gdrive/sync
curl -X POST http://127.0.0.1:8000/gdrive/sync
```

- This reads files from the Google Drive **folder** (`GDRIVE_FOLDER_ID`) using the service account JSON.
- A local index is persisted to `LIM_PERSIST_DIR` (defaults to `llamaindex_store/`).

You can check status:

```bash
curl http://127.0.0.1:8000/gdrive/status
```

### 3) Start the frontend (Next.js)

```bash
cd frontend
npm run dev
# Next opens http://localhost:3000
```

The UI has three modes:
- **Policy** → queries `/ask-question`
- **Data** → queries `/ask-data`
- **Nearby** → queries `/places-search` & `/place-details`

---

## API Endpoints (Backend)

Base URL: `http://127.0.0.1:8000`

### Health

- `GET /health` → `{"status":"ok"}`

### Google Drive KB (LlamaIndex)

- `POST /gdrive/sync`  
  Force a sync from Drive and rebuild the KB index.  
  **Requires:** `GDRIVE_SA_JSON` and `GDRIVE_FOLDER_ID`.

- `GET /gdrive/status`  
  Returns whether a persisted index exists.

- `POST /gdrive/query`  
  ```json
  { "question": "What is our PTO policy?" }
  ```
  Returns a direct answer + sources (debug/testing).

### Policy Q&A

- `POST /ask-question`  
  ```json
  { "question": "Summarize the parental leave policy." }
  ```
  **Response**:
  ```json
  { "answer": "...", "sources": ["Policy.pdf", "Benefits.docx"] }
  ```

### Data Q&A (CSV agent)

- `POST /ask-data`  
  ```json
  { "question": "Average tenure by department?" }
  ```
  **Response**:
  ```json
  { "answer": "..." }
  ```
  > Uses LangChain DataFrame agent over `HR_CSV_PATH`.

### Google Maps

- `POST /places-search`  
  **Body**:
  ```json
  {
    "query": "coffee",
    "type": null,
    "location": { "lat": 29.7604, "lng": -95.3698 },
    "radius": 2000,
    "open_now": false,
    "min_rating": 0.0
  }
  ```
  **Response**: list of place cards (name, address, rating, photo_url, etc.)

- `GET /place-details?place_id=...`  
  Returns name, phone, website, address, hours.

- `GET /directions?origin_lat=..&origin_lng=..&dest_lat=..&dest_lng=..&mode=driving`  
  Returns distance, duration, and polyline.

