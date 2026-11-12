"""Constantes e helpers compartilhados pela ingestão e pela busca (contrato do CLAUDE.md)."""
from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("ANONYMIZED_TELEMETRY", "False")

ROOT = Path(__file__).resolve().parent.parent
DOCS_DIR = ROOT / "data" / "docs"
CHROMA_DIR = ROOT / "data" / "chroma"
COLLECTION = "nexo_docs"
EMBED_MODEL = "intfloat/multilingual-e5-small"
PASSAGE_PREFIX = "passage: "
QUERY_PREFIX = "query: "


def get_client():
    import chromadb
    from chromadb.config import Settings

    CHROMA_DIR.mkdir(parents=True, exist_ok=True)
    return chromadb.PersistentClient(path=str(CHROMA_DIR), settings=Settings(anonymized_telemetry=False))


def get_model():
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(EMBED_MODEL)
