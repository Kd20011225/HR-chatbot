import os
import json
import shutil
import requests
import pandas as pd
from typing import Optional, List
from functools import lru_cache
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

# LangChain (Data Q&A)
from langchain_openai import OpenAI
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.docstore.document import Document
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from langchain.chains import RetrievalQA
from langchain_community.retrievers import BM25Retriever
from langchain.retrievers.ensemble import EnsembleRetriever
from langchain_experimental.agents import create_pandas_dataframe_agent

# LlamaIndex (Drive KB)
from llama_index.core import (
    VectorStoreIndex,
    SimpleDirectoryReader,
    StorageContext,
    load_index_from_storage,
)
from llama_index.readers.google import GoogleDriveReader
from llama_index.readers.file import PDFReader, DocxReader

# --------------------------
# Env & App setup
# --------------------------
HERE = Path(__file__).resolve().parent
ENV_PATH = HERE / ".env"
load_dotenv(dotenv_path=ENV_PATH, override=True)

app = FastAPI(
    title="HR Assistant Backend (Drive KB + Data + Maps)",
    version="3.1.1",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten for prod
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --------------------------
# Environment variables
# --------------------------
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_ORG = os.getenv("OPENAI_ORG", None)

GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")

# Google Drive (Service Account + Folder)
GDRIVE_SA_JSON = os.getenv("GDRIVE_SA_JSON", str(HERE / "credentials.json"))
GDRIVE_FOLDER_ID = os.getenv("GDRIVE_FOLDER_ID")

# LlamaIndex persistence
LIM_PERSIST_DIR = os.getenv("LIM_PERSIST_DIR", str(HERE / "llamaindex_store"))

# CSV location for Data Q&A
CSV_PATH = os.getenv("HR_CSV_PATH", str(HERE / "data" / "hr_data.csv"))

os.makedirs(LIM_PERSIST_DIR, exist_ok=True)

# --------------------------
# LLM helper (LangChain)
# --------------------------
def _llm():
    if not OPENAI_API_KEY:
        raise HTTPException(500, "OPENAI_API_KEY not set")
    return OpenAI(api_key=OPENAI_API_KEY, organization=OPENAI_ORG)

# --------------------------
# LlamaIndex (Drive KB)
# --------------------------
_index = None  # global KB index

def _have_persisted_index() -> bool:
    try:
        return any(Path(LIM_PERSIST_DIR).iterdir())
    except FileNotFoundError:
        return False

def _load_index_from_disk():
    storage_context = StorageContext.from_defaults(persist_dir=LIM_PERSIST_DIR)
    return load_index_from_storage(storage_context)

def _build_index_from_docs(docs):
    # sanitize metadata so it doesn't leak into prompts/embeddings
    for d in docs:
        src = (
            (d.metadata or {}).get("file_name")
            or (d.metadata or {}).get("display_name")
            or (d.metadata or {}).get("file_path")
            or "drive_doc"
        )
        d.metadata = {"source": os.path.basename(str(src))}
        d.excluded_llm_metadata_keys = list(d.metadata.keys())
        d.excluded_embed_metadata_keys = list(d.metadata.keys())
    idx = VectorStoreIndex.from_documents(docs)
    idx.storage_context.persist(persist_dir=LIM_PERSIST_DIR)
    return idx

def _load_drive_docs_compat(sa: dict, folder_id: str):
    """
    Load Google Drive docs across multiple LlamaIndex versions by trying
    several supported signatures. No 'download_dir' or 'recursive' used.
    """
    # Pattern A: pass folder_id at call time
    try:
        reader = GoogleDriveReader(
            service_account_key=sa,
            file_extractor={".pdf": PDFReader(), ".docx": DocxReader()},
        )
        return reader.load_data(folder_id=folder_id)
    except TypeError:
        pass

    # Pattern B: set folder_id in the constructor
    try:
        reader = GoogleDriveReader(
            service_account_key=sa,
            folder_id=folder_id,
            file_extractor={".pdf": PDFReader(), ".docx": DocxReader()},
        )
        return reader.load_data()
    except TypeError:
        pass

    # Pattern C: set folder_ids (list) in the constructor
    try:
        reader = GoogleDriveReader(
            service_account_key=sa,
            folder_ids=[folder_id],
            file_extractor={".pdf": PDFReader(), ".docx": DocxReader()},
        )
        return reader.load_data()
    except TypeError:
        pass

    raise RuntimeError(
        "GoogleDriveReader.load_data signature not supported by your llama_index build. "
        "Upgrade 'llama-index' and 'llama-index-readers-google' to a recent version."
    )

def _sync_index_from_drive_if_missing():
    """Build index from Drive only if it's not already persisted."""
    if _have_persisted_index():
        return  # already exists
    if not GDRIVE_FOLDER_ID:
        raise RuntimeError("GDRIVE_FOLDER_ID not set")
    if not os.path.exists(GDRIVE_SA_JSON):
        raise RuntimeError(f"Service account JSON not found at {GDRIVE_SA_JSON}")

    with open(GDRIVE_SA_JSON, "r", encoding="utf-8") as f:
        sa = json.load(f)
    if sa.get("type") != "service_account":
        raise RuntimeError("GDRIVE_SA_JSON is not a service account key (expected type=service_account)")

    docs = _load_drive_docs_compat(sa, GDRIVE_FOLDER_ID)
    idx = _build_index_from_docs(docs)
    return idx

# --------------------------
# API models
# --------------------------
class HRQuestion(BaseModel):
    question: str

class HRAnswer(BaseModel):
    answer: str
    sources: Optional[List[str]] = None

class KBQuestion(BaseModel):
    question: str

class DataQuestion(BaseModel):
    question: str

class Location(BaseModel):
    lat: float
    lng: float

class PlacesSearchRequest(BaseModel):
    query: Optional[str] = None
    type: Optional[str] = None
    location: Optional[Location] = None
    radius: Optional[int] = 2000
    open_now: Optional[bool] = False
    min_rating: Optional[float] = 0.0

class PlaceCard(BaseModel):
    name: str
    address: str
    rating: Optional[float] = None
    user_ratings_total: Optional[int] = None
    price_level: Optional[int] = None
    open_now: Optional[bool] = None
    location: Location
    place_id: str
    maps_url: str
    photo_url: Optional[str] = None

class PlacesSearchResponse(BaseModel):
    results: List[PlaceCard]

class PlaceDetailsResponse(BaseModel):
    name: str
    phone: Optional[str] = None
    website: Optional[str] = None
    opening_hours: Optional[List[str]] = None
    formatted_address: Optional[str] = None
    maps_url: str

# --------------------------
# Drive KB endpoints
# --------------------------
@app.post("/gdrive/sync")
def gdrive_sync():
    """Force a sync from Drive and rebuild the KB index."""
    global _index
    try:
        if not GDRIVE_FOLDER_ID:
            raise HTTPException(400, "GDRIVE_FOLDER_ID not set in env")
        if not os.path.exists(GDRIVE_SA_JSON):
            raise HTTPException(400, f"Service account JSON not found at {GDRIVE_SA_JSON}")

        with open(GDRIVE_SA_JSON, "r", encoding="utf-8") as f:
            sa = json.load(f)
        if sa.get("type") != "service_account":
            raise HTTPException(400, "GDRIVE_SA_JSON is not a service account key (expected type=service_account)")

        docs = _load_drive_docs_compat(sa, GDRIVE_FOLDER_ID)
        _index = _build_index_from_docs(docs)
        return {"status": "ok", "persist_dir": LIM_PERSIST_DIR}
    except HTTPException:
        raise
    except Exception as e:
        import traceback; traceback.print_exc()
        raise HTTPException(500, f"Drive sync failed: {e}")

@app.get("/gdrive/status")
def gdrive_status():
    return {"persisted": _have_persisted_index(), "persist_dir": LIM_PERSIST_DIR}

@app.post("/gdrive/query")
def gdrive_query(payload: KBQuestion):
    """Direct query against the KB (debug/testing)."""
    global _index
    if _index is None:
        if _have_persisted_index():
            _index = _load_index_from_disk()
        else:
            raise HTTPException(400, "Index not loaded. Run /gdrive/sync first.")
    qe = _index.as_query_engine(similarity_top_k=10)
    resp = qe.query(payload.question)

    # Extract answer + sources
    answer = str(resp)
    sources = []
    try:
        if hasattr(resp, "source_nodes"):
            for n in resp.source_nodes or []:
                node = getattr(n, "node", None)
                if node and getattr(node, "metadata", None):
                    src = node.metadata.get("source")
                    if src:
                        sources.append(src)
    except Exception:
        pass
    return {"answer": answer, "sources": sources or None}

# --------------------------
# Policy Q&A (uses KB)
# --------------------------
@app.post("/ask-question", response_model=HRAnswer)
def ask_question(payload: HRQuestion):
    global _index
    if _index is None:
        if _have_persisted_index():
            _index = _load_index_from_disk()
        else:
            raise HTTPException(400, "No KB loaded. Upload PDFs to Drive, then POST /gdrive/sync.")
    qe = _index.as_query_engine(similarity_top_k=10)
    resp = qe.query(payload.question)

    answer = str(resp)
    sources = []
    try:
        if hasattr(resp, "source_nodes"):
            for n in resp.source_nodes or []:
                node = getattr(n, "node", None)
                if node and getattr(node, "metadata", None):
                    src = node.metadata.get("source")
                    if src:
                        sources.append(src)
    except Exception:
        pass

    return HRAnswer(answer=answer, sources=sources or None)

# --------------------------
# CSV Data Q&A (LangChain)
# --------------------------
@lru_cache(maxsize=1)
def _load_hr_df() -> pd.DataFrame:
    path = Path(CSV_PATH)
    if path.suffix.lower() == ".xlsx":
        df = pd.read_excel(path)
    else:
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            pd.DataFrame([{"EmpID": 1, "Name": "Demo", "Department": "HR"}]).to_csv(path, index=False)
        df = pd.read_csv(path, encoding="cp1252")
    return df

def _setup_data_agent():
    df = _load_hr_df()
    return create_pandas_dataframe_agent(
        llm=_llm(),
        df=df,
        verbose=False,
        agent_type="zero-shot-react-description",
        allow_dangerous_code=True,
    )

def _build_csv_qa_chain():
    df = _load_hr_df()
    json_text = df.to_json(orient="records")
    splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
    docs = [Document(page_content=t) for t in splitter.split_text(json_text)]
    embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
    vect = FAISS.from_documents(docs, embeddings)

    sim_r = vect.as_retriever(search_type="similarity", search_kwargs={"k": 5})
    mmr_r = vect.as_retriever(search_type="mmr", search_kwargs={"k": 2, "fetch_k": 20, "lambda_mult": 0.5})
    bm25 = BM25Retriever.from_documents(docs); bm25.k = 2

    ensemble = EnsembleRetriever(retrievers=[sim_r, mmr_r, bm25], weights=[0.2, 0.5, 0.3])

    return RetrievalQA.from_chain_type(
        llm=_llm(),
        chain_type="stuff",
        retriever=ensemble,
        return_source_documents=True,
    )

data_agent = None
csv_qa_chain = None

@app.post("/ask-data")
def ask_data(q: DataQuestion):
    if csv_qa_chain is None:
        raise HTTPException(500, "HR data not loaded.")
    result = csv_qa_chain({"query": q.question})
    return {"answer": result["result"]}

# --------------------------
# Google Maps helpers
# --------------------------
def _gmaps_key() -> str:
    if not GOOGLE_MAPS_API_KEY:
        raise HTTPException(500, "GOOGLE_MAPS_API_KEY not set")
    return GOOGLE_MAPS_API_KEY

def _photo_url(photo_ref: str, maxwidth: int = 600) -> str:
    return ("https://maps.googleapis.com/maps/api/place/photo"
            f"?maxwidth={maxwidth}&photo_reference={photo_ref}&key={_gmaps_key()}")

def _maps_place_url(place_id: str) -> str:
    return f"https://www.google.com/maps/place/?q=place_id:{place_id}"

class PlacesSearchRequest(BaseModel):
    query: Optional[str] = None
    type: Optional[str] = None
    location: Optional[Location] = None
    radius: Optional[int] = 2000
    open_now: Optional[bool] = False
    min_rating: Optional[float] = 0.0

@app.post("/places-search", response_model=PlacesSearchResponse)
def places_search(payload: PlacesSearchRequest):
    key = _gmaps_key()
    if payload.location is None:
        raise HTTPException(400, "location (lat/lng) is required")

    base_params = {
        "key": key,
        "location": f"{payload.location.lat},{payload.location.lng}",
        "radius": payload.radius or 2000,
        "opennow": "true" if payload.open_now else None,
    }

    try:
        if payload.query:
            url = "https://maps.googleapis.com/maps/api/place/textsearch/json"
            params = {**base_params, "query": payload.query, "type": payload.type or None}
        else:
            if not payload.type:
                raise HTTPException(400, "Either query or type must be provided.")
            url = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
            params = {**base_params, "type": payload.type}

        params = {k: v for k, v in params.items() if v is not None}
        r = requests.get(url, params=params, timeout=12)
        data = r.json()

        if data.get("status") not in ("OK", "ZERO_RESULTS"):
            raise HTTPException(502, f"Places API error: {data.get('status')}")

        out: List[PlaceCard] = []
        for p in data.get("results", []):
            rating = p.get("rating")
            if payload.min_rating and rating and rating < payload.min_rating:
                continue

            photos = p.get("photos") or []
            photo_ref = photos[0]["photo_reference"] if photos else None

            out.append(PlaceCard(
                name=p.get("name"),
                address=p.get("formatted_address") or p.get("vicinity") or "",
                rating=rating,
                user_ratings_total=p.get("user_ratings_total"),
                price_level=p.get("price_level"),
                open_now=p.get("opening_hours", {}).get("open_now") if p.get("opening_hours") else None,
                location=Location(
                    lat=p["geometry"]["location"]["lat"],
                    lng=p["geometry"]["location"]["lng"],
                ),
                place_id=p.get("place_id"),
                maps_url=_maps_place_url(p.get("place_id")),
                photo_url=_photo_url(photo_ref) if photo_ref else None,
            ))
        return PlacesSearchResponse(results=out)

    except requests.Timeout:
        raise HTTPException(504, "Places API timeout")
    except Exception as e:
        raise HTTPException(500, f"Places search failed: {e}")

@app.get("/place-details", response_model=PlaceDetailsResponse)
def place_details(place_id: str):
    key = _gmaps_key()
    url = "https://maps.googleapis.com/maps/api/place/details/json"
    params = {
        "key": key,
        "place_id": place_id,
        "fields": "name,formatted_address,formatted_phone_number,website,opening_hours/weekday_text,place_id",
    }
    try:
        r = requests.get(url, params=params, timeout=12)
        data = r.json()
        if data.get("status") != "OK":
            raise HTTPException(502, f"Place Details error: {data.get('status')}")
        res = data["result"]
        return PlaceDetailsResponse(
            name=res.get("name"),
            phone=res.get("formatted_phone_number"),
            website=res.get("website"),
            opening_hours=res.get("opening_hours", {}).get("weekday_text"),
            formatted_address=res.get("formatted_address"),
            maps_url=_maps_place_url(res.get("place_id")),
        )
    except requests.Timeout:
        raise HTTPException(504, "Place Details timeout")
    except Exception as e:
        raise HTTPException(500, f"Place Details failed: {e}")

@app.get("/directions")
def directions(origin_lat: float, origin_lng: float, dest_lat: float, dest_lng: float, mode: str = "driving"):
    key = _gmaps_key()
    url = "https://maps.googleapis.com/maps/api/directions/json"
    params = {
        "key": key,
        "origin": f"{origin_lat},{origin_lng}",
        "destination": f"{dest_lat},{dest_lng}",
        "mode": mode,
        "alternatives": "false",
    }
    try:
        r = requests.get(url, params=params, timeout=12)
        data = r.json()
        if data.get("status") != "OK":
            raise HTTPException(502, f"Directions error: {data.get('status')}")
        route = data["routes"][0]
        leg = route["legs"][0]
        return {
            "distance_text": leg["distance"]["text"],
            "duration_text": leg["duration"]["text"],
            "polyline": route["overview_polyline"]["points"],
        }
    except requests.Timeout:
        raise HTTPException(504, "Directions timeout")
    except Exception as e:
        raise HTTPException(500, f"Directions failed: {e}")

# --------------------------
# Health + startup
# --------------------------
@app.get("/health")
def health():
    return {"status": "ok"}

@app.on_event("startup")
def on_startup():
    global data_agent, csv_qa_chain, _index
    # data stack
    data_agent = _setup_data_agent()
    csv_qa_chain = _build_csv_qa_chain()
    # KB stack
    try:
        if _have_persisted_index():
            _index = _load_index_from_disk()
        else:
            _index = _sync_index_from_drive_if_missing()
    except Exception as e:
        print(f"[startup] KB not ready: {e}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main_integrated:app", host="127.0.0.1", port=8000, reload=True)
