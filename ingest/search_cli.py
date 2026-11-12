"""Busca semântica na base nexo_docs (para testes do Dados e do Backend).

Uso:  python ingest/search_cli.py "qual o prazo para avisar sinistro do carro?" [-k 4]
score = similaridade cosseno (1 - distância), mesma fórmula do contrato da API.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import COLLECTION, QUERY_PREFIX, get_client, get_model  # noqa: E402


def search(question: str, k: int = 4, model=None, col=None) -> list[dict]:
    model = model or get_model()
    col = col or get_client().get_collection(COLLECTION)
    emb = model.encode([QUERY_PREFIX + question], normalize_embeddings=True).tolist()
    res = col.query(query_embeddings=emb, n_results=k, include=["documents", "metadatas", "distances"])
    return [
        {**meta, "trecho": doc, "score": round(1 - dist, 4)}
        for doc, meta, dist in zip(res["documents"][0], res["metadatas"][0], res["distances"][0])
    ]


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("pergunta", nargs="+")
    ap.add_argument("-k", type=int, default=4)
    args = ap.parse_args()
    question = " ".join(args.pergunta)
    print(f'Pergunta: "{question}"\n')
    for i, r in enumerate(search(question, args.k), 1):
        print(f"[{i}] score={r['score']:.3f}  {r['doc_id']} #{r['chunk_idx']}  ({r['area']}) — {r.get('secao', '')}")
        trecho = r["trecho"].replace("\n", " ")
        print(f"    {trecho[:300]}{'...' if len(trecho) > 300 else ''}\n")


if __name__ == "__main__":
    main()
