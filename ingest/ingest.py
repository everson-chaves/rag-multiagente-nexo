"""Pipeline de ingestão: data/docs/*.md -> chunks -> embeddings e5 -> Chroma (data/chroma, coleção nexo_docs).

Uso:  python ingest/ingest.py
A coleção é apagada e recriada a cada execução (idempotente).
"""
from __future__ import annotations

import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import COLLECTION, DOCS_DIR, PASSAGE_PREFIX, get_client, get_model  # noqa: E402

MAX_CHARS = 800
OVERLAP = 120

# Fallback de área pelo nome do arquivo (usado se o doc não tiver a linha "Área: ...").
AREA_POR_ARQUIVO = {
    "politica-ferias": "RH",
    "politica-home-office": "RH",
    "beneficios": "RH",
    "faq-novos-colaboradores": "RH",
    "manual-sinistro-auto": "Sinistros",
    "manual-sinistro-residencial": "Sinistros",
    "tabela-coberturas-auto": "Produtos",
    "guia-atendimento": "Atendimento",
    "politica-seguranca-informacao": "TI",
    "politica-uso-ia": "TI",
    "politica-privacidade-lgpd": "Compliance",
    "politica-brindes": "Compliance",
    "codigo-de-conduta": "Compliance",
    "organograma-areas": "Institucional",
}

HEADING_RE = re.compile(r"^(#{2,6})\s+(.*)$")
AREA_RE = re.compile(r"^\s*[ÁA]rea:\s*(.+?)\s*$", re.IGNORECASE)
META_RE = re.compile(r"^\s*([ÁA]rea|Vers[ãa]o|Respons[áa]vel):", re.IGNORECASE)


@dataclass
class Doc:
    doc_id: str
    titulo: str
    area: str
    body: str


@dataclass
class Chunk:
    doc: Doc
    secao: str
    texto: str


def load_doc(path: Path) -> Doc:
    lines = path.read_text(encoding="utf-8").splitlines()
    doc_id = path.stem
    titulo = doc_id
    if lines and lines[0].startswith("# "):
        titulo = lines[0][2:].strip()
        lines = lines[1:]
    area = None
    for ln in lines[:8]:
        m = AREA_RE.match(ln)
        if m:
            area = m.group(1)
            break
    if area is None:
        area = AREA_POR_ARQUIVO.get(doc_id, "Geral")
    # Linhas de cabeçalho administrativo (Área/Versão/Responsável) não viram chunk: são ruído na busca.
    lines = [ln for ln in lines if not META_RE.match(ln)]
    return Doc(doc_id=doc_id, titulo=titulo, area=area, body="\n".join(lines).strip())


def split_sections(body: str) -> list[tuple[str, str]]:
    """Divide pelo cabeçalho Markdown (##+). Texto antes do 1º cabeçalho vira a seção 'Introdução'."""
    sections: list[tuple[str, str]] = []
    current, buf = "Introdução", []
    for ln in body.splitlines():
        m = HEADING_RE.match(ln)
        if m:
            if "\n".join(buf).strip():
                sections.append((current, "\n".join(buf).strip()))
            current, buf = m.group(2).strip(), []
        else:
            buf.append(ln)
    if "\n".join(buf).strip():
        sections.append((current, "\n".join(buf).strip()))
    return sections


def _blocks(text: str) -> list[str]:
    """Blocos = parágrafos/listas/tabelas (separados por linha em branco). Blocos grandes demais são
    quebrados por linha, para nunca cortar no meio de um item de lista."""
    out: list[str] = []
    for block in re.split(r"\n\s*\n", text):
        block = block.strip()
        if not block:
            continue
        if len(block) <= MAX_CHARS:
            out.append(block)
            continue
        cur = ""
        for ln in block.splitlines():
            if cur and len(cur) + 1 + len(ln) > MAX_CHARS:
                out.append(cur)
                cur = ln
            else:
                cur = f"{cur}\n{ln}" if cur else ln
        if cur:
            out.append(cur)
    return out


def _tail(text: str, n: int) -> str:
    """Últimos ~n caracteres, começando numa fronteira de linha/palavra."""
    if len(text) <= n:
        return text
    tail = text[-n:]
    for sep in ("\n", " "):
        i = tail.find(sep)
        if 0 <= i < n // 2:
            return tail[i + 1 :]
    return tail


def chunk_section(text: str, header_len: int) -> list[str]:
    budget = MAX_CHARS - header_len
    chunks: list[str] = []
    cur = ""
    for block in _blocks(text):
        if cur and len(cur) + 2 + len(block) > budget:
            chunks.append(cur)
            overlap = _tail(cur, OVERLAP)
            cur = f"{overlap}\n\n{block}" if len(overlap) + 2 + len(block) <= budget else block
        else:
            cur = f"{cur}\n\n{block}" if cur else block
    if cur:
        chunks.append(cur)
    return chunks


def chunk_doc(doc: Doc) -> list[Chunk]:
    chunks: list[Chunk] = []
    for secao, text in split_sections(doc.body):
        header = f"{doc.titulo} — {secao}\n"
        for piece in chunk_section(text, len(header)):
            chunks.append(Chunk(doc=doc, secao=secao, texto=header + piece))
    return chunks


def main() -> None:
    t0 = time.perf_counter()
    paths = sorted(DOCS_DIR.glob("*.md"))
    if not paths:
        sys.exit(f"Nenhum documento encontrado em {DOCS_DIR}")
    docs = [load_doc(p) for p in paths]
    chunks = [c for d in docs for c in chunk_doc(d)]

    print(f"Carregando modelo de embeddings... ({len(docs)} docs, {len(chunks)} chunks)")
    model = get_model()
    embeddings = model.encode(
        [PASSAGE_PREFIX + c.texto for c in chunks],
        normalize_embeddings=True,
        batch_size=32,
        show_progress_bar=False,
    )

    client = get_client()
    try:
        client.delete_collection(COLLECTION)
    except Exception:
        pass  # coleção ainda não existia
    col = client.create_collection(COLLECTION, metadata={"hnsw:space": "cosine"})

    counters: dict[str, int] = {}
    ids, metas = [], []
    for c in chunks:
        idx = counters.get(c.doc.doc_id, 0)
        counters[c.doc.doc_id] = idx + 1
        ids.append(f"{c.doc.doc_id}::{idx}")
        metas.append(
            {"doc_id": c.doc.doc_id, "titulo": c.doc.titulo, "area": c.doc.area, "chunk_idx": idx, "secao": c.secao}
        )
    col.add(ids=ids, documents=[c.texto for c in chunks], embeddings=embeddings.tolist(), metadatas=metas)

    dt = time.perf_counter() - t0
    sizes = [len(c.texto) for c in chunks]
    print("=" * 60)
    print(f"Documentos: {len(docs)}")
    print(f"Chunks:     {col.count()}  (tam. médio {sum(sizes) // len(sizes)} / máx {max(sizes)} caracteres)")
    print(f"Coleção:    {COLLECTION} em data/chroma")
    print(f"Tempo:      {dt:.1f}s")
    for d in docs:
        print(f"  - {d.doc_id:32s} [{d.area:13s}] {counters.get(d.doc_id, 0):3d} chunks")


if __name__ == "__main__":
    main()
