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
## How to Get API Keys & Credentials

This project needs a few external credentials. Here’s a concise, step‑by‑step guide for each.

### 1) OpenAI API Key
1. Sign in at <https://platform.openai.com/> (create an account if needed).
2. Go to **Dashboard → API keys** and click **Create new secret key**.
3. Copy the key (starts with `sk-...`) and store it in your password manager.
4. Set it in your backend `.env`:
   ```ini
   OPENAI_API_KEY=sk-...
   ```

---

### 2) Google Maps API Key (Places/Details/Directions)
1. Go to **Google Cloud Console**: <https://console.cloud.google.com/>
2. Create or select a **Project**.
3. Enable APIs (**APIs & Services → Library**):
   - **Places API**
   - **Maps JavaScript API** (if you later render maps in frontend)
   - **Directions API**
4. Go to **APIs & Services → Credentials → + Create credentials → API key**.
5. Copy the key and **restrict it** (**VERY IMPORTANT**):
   - Click the key → **Key restrictions**:
     - If calling **from backend only**: set **IP address** restrictions to your server IP(s).
     - If calling **from browser**: set **HTTP referrers (websites)** to your domain(s).
     - Under **API restrictions**, allow only the APIs you enabled.
6. Add to backend `.env`:
   ```ini
   GOOGLE_MAPS_API_KEY=YOUR_KEY
   ```

> Billing must be enabled on the GCP project to use Maps APIs.

---

### 3) Google Drive – Service Account & Folder ID (for the HR KB)
This project reads HR PDFs/DOCX from a specific Drive folder using a **Service Account**.

**A) Enable API and create Service Account**
1. In **Google Cloud Console**, open your project.
2. **APIs & Services → Library** → enable **Google Drive API**.
3. Go to **IAM & Admin → Service Accounts → Create service account**.
4. After creation, **Keys → Add key → Create new key → JSON**. A file like `credentials.json` downloads.
5. Put it in `backend/` and **do not commit to git**. Set in `.env`:
   ```ini
   GDRIVE_SA_JSON=credentials.json
   ```

**B) Share the Drive folder with the service account**
1. In Google Drive, right‑click your HR folder → **Share**.
2. Share it with the **service account email** (looks like `name@project-id.iam.gserviceaccount.com`) and give **Viewer** or **Editor** access.
3. Copy the **Folder ID** from the folder URL (between `/folders/` and the next slash). Example:
   - `https://drive.google.com/drive/folders/1AbCDefGh...` → `GDRIVE_FOLDER_ID=1AbCDefGh...`
4. Add to `.env`:
   ```ini
   GDRIVE_FOLDER_ID=your_folder_id
   ```

**C) (CI-friendly) Use Base64 instead of a file (optional)**
If you deploy with GitHub Actions or a platform where you’d rather not store a file:
1. Base64‑encode `credentials.json` locally:
   - **Windows PowerShell**:
     ```powershell
     [Convert]::ToBase64String([IO.File]::ReadAllBytes("backend\credentials.json")) | Set-Content sa.b64
     ```
2. Put the contents of `sa.b64` into a secret named `GDRIVE_SA_JSON_B64`.
3. On startup (or in CI), decode it to `backend/credentials.json` and set `GDRIVE_SA_JSON=credentials.json`.

---

=======
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

