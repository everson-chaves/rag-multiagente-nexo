"""API FastAPI do Assistente Interno RAG — Nexo Seguros.

Rodar (na raiz do projeto):  uvicorn api.main:app --port 8000
"""
from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager
from typing import Callable

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from api import generator
from api.retriever import Retriever, get_retriever

log = logging.getLogger("nexo.api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Carrega modelo de embeddings + cliente Chroma uma única vez, no startup.
    try:
        get_retriever().warmup()
        log.info("Retriever pronto (%d chunks).", get_retriever().count())
    except Exception:  # não derruba a API; /health e /ask reportam o problema
        log.exception("Falha ao aquecer o retriever")
    yield


app = FastAPI(title="Nexo Seguros — Assistente Interno RAG", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5500", "http://127.0.0.1:5500"],
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


class AskRequest(BaseModel):
    question: str
    top_k: int = Field(4, ge=1, le=20)


class Source(BaseModel):
    n: int
    doc_id: str
    titulo: str
    trecho: str
    score: float


class AskResponse(BaseModel):
    answer: str
    sources: list[Source]
    latency_ms: int


def get_generator() -> Callable[[str, list[dict]], str]:
    return generator.generate


@app.get("/health")
def health(retriever: Retriever = Depends(get_retriever)):
    try:
        chunks = retriever.count()
    except Exception:
        log.exception("Erro ao contar chunks")
        chunks = 0
    return {"status": "ok", "chunks": chunks}


@app.post("/ask", response_model=AskResponse)
def ask(req: AskRequest,
        retriever: Retriever = Depends(get_retriever),
        generate: Callable = Depends(get_generator)):
    t0 = time.perf_counter()

    question = req.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="A pergunta não pode ser vazia.")

    try:
        if retriever.count() == 0:
            raise HTTPException(
                status_code=503,
                detail="Base vetorial vazia. Rode a ingestão (python ingest/ingest.py) antes de perguntar.",
            )
        hits = retriever.search(question, req.top_k)
    except HTTPException:
        raise
    except Exception as e:
        log.exception("Erro na busca")
        raise HTTPException(status_code=500, detail=f"Erro na busca vetorial: {e}") from e

    sources = [
        {"n": i, "doc_id": h.doc_id, "titulo": h.titulo, "trecho": h.trecho, "score": h.score}
        for i, h in enumerate(hits, start=1)
    ]

    try:
        answer = generate(question, sources)
    except generator.MissingAPIKeyError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    except Exception as e:
        log.exception("Erro ao gerar resposta")
        raise HTTPException(status_code=502, detail=f"Erro ao consultar o Claude: {type(e).__name__}: {e}") from e

    latency_ms = int((time.perf_counter() - t0) * 1000)
    return {"answer": answer, "sources": sources, "latency_ms": latency_ms}
