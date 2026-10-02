"""FastAPI app: tiny UI and stateless POST /chat."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from app.catalog import SCHEMES
from app.config import ANTHROPIC_API_KEY, STATIC_DIR
from app.pipeline import answer_question
from app.rag.retrieve import index_chunk_counts

logger = logging.getLogger("uvicorn.error")


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Fail loudly (log only) if the demo would run on an empty index or no key."""
    counts = index_chunk_counts()
    missing = [s.scheme_id for s in SCHEMES if not counts.get(s.scheme_id)]
    if not counts:
        logger.error("Document index is empty or missing; run: python scripts/ingest.py")
    elif missing:
        logger.error("Index has no chunks for: %s; re-run scripts/ingest.py", ", ".join(missing))
    if not ANTHROPIC_API_KEY:
        logger.error("ANTHROPIC_API_KEY is not set; factual answers will show 'Service busy'")
    yield


app = FastAPI(title="HDFC MF facts-only FAQ", version="0.3.0", lifespan=lifespan)


class ChatRequest(BaseModel):
    question: str = Field(default="", max_length=4000)


class ChatResponse(BaseModel):
    type: str
    answer: str
    source_url: str
    last_updated: str
    scheme_id: str | None


@app.get("/health")
def health() -> dict[str, bool]:
    return {"ok": True}


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.post("/chat", response_model=ChatResponse)
def chat(body: ChatRequest) -> dict:
    return answer_question(body.question)
