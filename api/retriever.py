"""Recuperação de trechos na base vetorial (ChromaDB + e5).

- O modelo de embeddings e o cliente Chroma são carregados UMA vez (singleton).
- A coleção é reaberta a cada busca: o Engenheiro de Dados recria `nexo_docs`
  a cada ingestão, e um handle antigo ficaria apontando para uma coleção apagada.
"""
from __future__ import annotations

import threading
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHROMA_PATH = ROOT / "data" / "chroma"
COLLECTION = "nexo_docs"
EMBED_MODEL = "intfloat/multilingual-e5-small"


@dataclass
class Hit:
    doc_id: str
    titulo: str
    area: str
    chunk_idx: int
    trecho: str
    score: float


def distance_to_score(distance: float, space: str = "cosine") -> float:
    """Converte a distância do Chroma em similaridade de 0 a 1.

    - cosine: d = 1 - cos  -> score = 1 - d
    - l2 (vetores normalizados): d = ||a-b||^2 = 2 - 2cos -> score = 1 - d/2
    - ip: d = 1 - <a,b>    -> score = 1 - d
    """
    if space == "l2":
        sim = 1.0 - distance / 2.0
    else:
        sim = 1.0 - distance
    return round(max(0.0, min(1.0, sim)), 4)


class Retriever:
    def __init__(self, chroma_path: Path = CHROMA_PATH, collection: str = COLLECTION,
                 model_name: str = EMBED_MODEL):
        self.chroma_path = Path(chroma_path)
        self.collection_name = collection
        self.model_name = model_name
        self._model = None
        self._client = None
        self._lock = threading.Lock()

    # ---------- carregamento único ----------
    def _get_model(self):
        if self._model is None:
            with self._lock:
                if self._model is None:
                    from sentence_transformers import SentenceTransformer
                    self._model = SentenceTransformer(self.model_name)
        return self._model

    def _get_client(self):
        if self._client is None:
            with self._lock:
                if self._client is None:
                    import chromadb
                    self.chroma_path.mkdir(parents=True, exist_ok=True)
                    self._client = chromadb.PersistentClient(path=str(self.chroma_path))
        return self._client

    def warmup(self) -> None:
        """Chamado no startup da API: carrega modelo e cliente antes da 1ª requisição."""
        self._get_client()
        self._get_model()

    def _collection(self):
        try:
            return self._get_client().get_collection(self.collection_name)
        except Exception:  # coleção ainda não existe (ingestão não rodou)
            return None

    # ---------- API pública ----------
    def count(self) -> int:
        col = self._collection()
        return col.count() if col is not None else 0

    def search(self, question: str, top_k: int = 4) -> list[Hit]:
        col = self._collection()
        if col is None:
            return []
        total = col.count()
        if total == 0:
            return []

        emb = self._get_model().encode(
            [f"query: {question}"], normalize_embeddings=True
        ).tolist()
        res = col.query(
            query_embeddings=emb,
            n_results=min(top_k, total),
            include=["documents", "metadatas", "distances"],
        )
        space = (col.metadata or {}).get("hnsw:space", "l2")

        hits: list[Hit] = []
        for doc, meta, dist in zip(res["documents"][0], res["metadatas"][0], res["distances"][0]):
            meta = meta or {}
            hits.append(Hit(
                doc_id=str(meta.get("doc_id", "")),
                titulo=str(meta.get("titulo", "")),
                area=str(meta.get("area", "")),
                chunk_idx=int(meta.get("chunk_idx", 0) or 0),
                trecho=doc or "",
                score=distance_to_score(float(dist), space),
            ))
        hits.sort(key=lambda h: h.score, reverse=True)
        return hits


_retriever: Retriever | None = None


def get_retriever() -> Retriever:
    global _retriever
    if _retriever is None:
        _retriever = Retriever()
    return _retriever
