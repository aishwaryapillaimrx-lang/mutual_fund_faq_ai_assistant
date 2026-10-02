"""Runtime config. Secrets stay in .env."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

ROOT_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = ROOT_DIR / "static"
DATA_DIR = ROOT_DIR / "data"
MANIFEST_PATH = DATA_DIR / "manifest.json"
CORPUS_DIR = DATA_DIR / "corpus"
INDEX_DIR = DATA_DIR / "index"
COLLECTION_NAME = "official_docs"

CORPUS_SNAPSHOT_DATE = os.getenv("CORPUS_SNAPSHOT_DATE", "2026-09-27")

# Embeddings: empty EMBED_MODEL (or "local") uses Chroma's bundled
# all-MiniLM-L6-v2 on-device model, so ingest works without an API key.
# LLM_API_KEY / LLM_BASE_URL are only used for OpenAI-compatible embeddings.
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")
EMBED_MODEL = os.getenv("EMBED_MODEL", "local")

# Answer generation uses Claude first; Groq is the fallback.
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
CHAT_MODEL = os.getenv("CHAT_MODEL") or "claude-sonnet-5-5"

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_CHAT_MODEL = os.getenv("GROQ_CHAT_MODEL", "mixtral-8x7b-32768")
LLM_TIMEOUT_SECONDS = float(os.getenv("LLM_TIMEOUT_SECONDS", "30"))
RETRIEVAL_SCORE_THRESHOLD = float(os.getenv("RETRIEVAL_SCORE_THRESHOLD", "0.35"))

# Official hosts only; subdomains are allowed (e.g. files.hdfcfund.com).
ALLOWED_HOSTS = tuple(
    host.strip().lower()
    for host in os.getenv(
        "ALLOWED_HOSTS", "hdfcfund.com,amfiindia.com,sebi.gov.in"
    ).split(",")
    if host.strip()
)

# Chunking: sized for the local embedding model's 256-token input window.
CHUNK_WORDS = int(os.getenv("CHUNK_WORDS", "180"))
CHUNK_OVERLAP_WORDS = int(os.getenv("CHUNK_OVERLAP_WORDS", "40"))

# Official public pages only (allowlisted hosts).
SEBI_INVESTOR_URL = "https://investor.sebi.gov.in/"
AMFI_KNOWLEDGE_URL = (
    "https://www.amfiindia.com/investor/knowledge-center-info"
    "?zoneName=IntroductionMutualFunds"
)
HDFC_FUNDS_URL = "https://www.hdfcfund.com/"
