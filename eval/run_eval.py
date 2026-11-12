"""Avaliação do Assistente Interno RAG — Nexo Seguros.

Uso:
    python eval/run_eval.py --dry-run              # valida o dataset e testa o avaliador (sem API)
    python eval/run_eval.py --rotulo antes         # roda contra http://localhost:8000/ask
    python eval/run_eval.py --rotulo depois        # nova rodada; o relatório mostra antes × depois

Métricas:
    Acurácia        % das respondíveis em que TODOS os fatos_chave aparecem na resposta
    Recuperação     hit@k: % das respondíveis em que algum doc_esperado está nas sources
    Recusa correta  % das não respondíveis em que o assistente usou a frase de recusa
    Alucinação      % das não respondíveis em que ele respondeu algo em vez de recusar
    Latência        média e p95 (latency_ms da API; fallback: tempo medido no cliente)

Saídas: eval/resultados.csv, eval/relatorio.md, eval/historico/<rotulo>.json
Somente biblioteca padrão (urllib) — não exige dependências extras.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

EVAL_DIR = Path(__file__).resolve().parent
ROOT = EVAL_DIR.parent
DATASET = EVAL_DIR / "dataset.jsonl"
BRIEFING = ROOT / "docs" / "briefing-empresa.md"
DOCS_DIR = ROOT / "data" / "docs"
HIST_DIR = EVAL_DIR / "historico"
NOTAS_QA = EVAL_DIR / "notas_qa.md"

FRASE_RECUSA = "Não encontrei essa informação nos documentos internos."
META_ACURACIA = 0.85

try:
    sys.stdout.reconfigure(encoding="utf-8")  # console do Windows
except Exception:
    pass


# --------------------------------------------------------------------------- texto
def norm(texto: str) -> str:
    """minúsculas, sem acentos, espaços colapsados."""
    t = unicodedata.normalize("NFKD", texto or "")
    t = "".join(c for c in t if not unicodedata.combining(c)).lower()
    return re.sub(r"\s+", " ", t).strip()


def contem_fato(fato: str, texto: str) -> bool:
    """Um fato pode ter alternativas separadas por '|'. Basta uma aparecer.

    - comparação sem acento/caixa;
    - fronteira de palavra no início (evita "3 dias" casar com "13 dias");
    - fatos só com dígitos (ex.: telefone) são comparados ignorando espaços/pontuação.
    """
    tn = norm(texto)
    so_digitos = re.sub(r"\D", "", tn)
    for alt in fato.split("|"):
        a = norm(alt)
        if not a:
            continue
        if a.isdigit() and len(a) >= 6 and a in so_digitos:
            return True
        padrao = re.escape(a).replace(r"\ ", r"\s*")
        if a[0].isalnum():
            padrao = r"(?<![0-9a-z])" + padrao
        if re.search(padrao, tn):
            return True
    return False


def recusou(resposta: str) -> bool:
    return norm(FRASE_RECUSA).rstrip(".") in norm(resposta)


def norm_doc(doc_id: str) -> str:
    d = norm(str(doc_id)).replace("\\", "/").split("/")[-1]
    return d[:-3] if d.endswith(".md") else d


# --------------------------------------------------------------------------- dataset
def carregar_dataset(caminho: Path) -> list[dict]:
    itens = []
    with caminho.open(encoding="utf-8") as f:
        for n, linha in enumerate(f, 1):
            if linha.strip():
                try:
                    itens.append(json.loads(linha))
                except json.JSONDecodeError as e:
                    raise SystemExit(f"[ERRO] {caminho.name} linha {n}: JSON inválido ({e})")
    return itens


def validar_dataset(itens: list[dict]) -> list[str]:
    """Retorna lista de problemas (vazia = ok). Valida estrutura e fatos contra o briefing."""
    probs: list[str] = []
    briefing = BRIEFING.read_text(encoding="utf-8") if BRIEFING.exists() else ""
    if not briefing:
        probs.append(f"briefing não encontrado em {BRIEFING}")

    ids = [i.get("id") for i in itens]
    if len(ids) != len(set(ids)):
        probs.append("ids duplicados no dataset")
    resp = [i for i in itens if i.get("tipo") == "respondivel"]
    nresp = [i for i in itens if i.get("tipo") == "nao_respondivel"]
    if len(itens) != 50 or len(resp) != 40 or len(nresp) != 10:
        probs.append(f"esperado 50 itens (40+10); encontrado {len(itens)} ({len(resp)}+{len(nresp)})")

    for i in itens:
        for campo in ("id", "tipo", "estilo", "pergunta", "resposta_esperada", "fatos_chave", "doc_esperado"):
            if campo not in i:
                probs.append(f"{i.get('id')}: campo ausente '{campo}'")
    for i in resp:
        if not i.get("fatos_chave"):
            probs.append(f"{i['id']}: respondível sem fatos_chave")
        if not i.get("doc_esperado"):
            probs.append(f"{i['id']}: respondível sem doc_esperado")
        for fato in i.get("fatos_chave", []):
            # o fato precisa existir no briefing (fonte da verdade) ...
            if briefing and not contem_fato(fato, briefing):
                probs.append(f"{i['id']}: fato '{fato}' não aparece no briefing")
            # ... e a resposta esperada precisa satisfazê-lo (coerência interna)
            if not contem_fato(fato, i["resposta_esperada"]):
                probs.append(f"{i['id']}: resposta_esperada não contém o fato '{fato}'")
    for i in nresp:
        if i.get("resposta_esperada") != FRASE_RECUSA:
            probs.append(f"{i['id']}: resposta_esperada deve ser exatamente a frase de recusa")
    return probs


def checar_doc_ids(itens: list[dict]) -> list[str]:
    """Avisa se doc_esperado não existe em data/docs (quando a base já existir)."""
    if not DOCS_DIR.exists():
        return [f"(info) {DOCS_DIR.relative_to(ROOT)} ainda não existe — doc_ids não conferidos"]
    textos = {norm_doc(p.stem): p.read_text(encoding="utf-8") for p in DOCS_DIR.glob("*.md")}
    avisos = []
    for i in itens:
        docs = i.get("doc_esperado") or []
        if docs and not any(norm_doc(d) in textos for d in docs):
            avisos.append(f"{i['id']}: nenhum doc_esperado {docs} existe em data/docs")
            continue
        # cada fato-chave precisa estar escrito em algum doc_esperado (senão é problema de DOCUMENTO)
        for fato in i.get("fatos_chave", []):
            if not any(contem_fato(fato, textos.get(norm_doc(d), "")) for d in docs):
                avisos.append(f"{i['id']}: fato '{fato}' não está em {docs}")
    return avisos


# --------------------------------------------------------------------------- API
def http_json(url: str, payload: dict | None = None, timeout: float = 120) -> dict:
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"},
                                 method="POST" if payload is not None else "GET")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def perguntar(api: str, pergunta: str, top_k: int, timeout: float) -> tuple[dict, float]:
    t0 = time.perf_counter()
    resp = http_json(f"{api}/ask", {"question": pergunta, "top_k": top_k}, timeout)
    return resp, (time.perf_counter() - t0) * 1000


def resposta_simulada(item: dict) -> dict:
    """Usado no --dry-run: resposta 'perfeita' para testar o próprio avaliador."""
    if item["tipo"] == "nao_respondivel":
        return {"answer": FRASE_RECUSA, "sources": [], "latency_ms": 0}
    fontes = [{"n": 1, "doc_id": d, "titulo": d, "trecho": "", "score": 0.9} for d in item["doc_esperado"][:1]]
    return {"answer": item["resposta_esperada"] + " [1]", "sources": fontes, "latency_ms": 0}


# --------------------------------------------------------------------------- avaliação
def avaliar_item(item: dict, resp: dict | None, lat_cliente: float, erro: str = "") -> dict:
    r = {
        "id": item["id"], "tipo": item["tipo"], "estilo": item["estilo"], "pergunta": item["pergunta"],
        "resposta_esperada": item["resposta_esperada"], "doc_esperado": ";".join(item.get("doc_esperado") or []),
        "resposta": "", "fontes": "", "fatos_ok": "", "fatos_faltando": "", "acertou": "", "hit": "",
        "recusou": "", "alucinou": "", "latency_ms": "", "erro": erro, "gravidade": 0, "diagnostico": "",
    }
    if resp is None:
        r["gravidade"], r["diagnostico"] = 3, f"erro na chamada: {erro}"
        return r

    answer = resp.get("answer", "") or ""
    fontes = [norm_doc(s.get("doc_id", "")) for s in resp.get("sources", []) or []]
    lat = resp.get("latency_ms")
    r.update(resposta=answer, fontes=";".join(fontes),
             latency_ms=round(float(lat if isinstance(lat, (int, float)) and lat > 0 else lat_cliente)),
             recusou=recusou(answer))

    if item["tipo"] == "respondivel":
        fatos = item["fatos_chave"]
        faltando = [f for f in fatos if not contem_fato(f, answer)]
        hit = any(norm_doc(d) in fontes for d in item["doc_esperado"])
        r.update(fatos_ok=f"{len(fatos) - len(faltando)}/{len(fatos)}", fatos_faltando=" ; ".join(faltando),
                 acertou=not faltando, hit=hit)
        if not faltando:
            r["gravidade"] = 0 if hit else 1
            r["diagnostico"] = "ok" if hit else "acertou, mas doc_esperado fora das fontes (citação/recuperação)"
        elif r["recusou"]:
            r["gravidade"] = 3 if not hit else 2
            r["diagnostico"] = ("recusa indevida — BUSCA não trouxe o documento certo" if not hit else
                                "recusa indevida com o documento certo nas fontes — PROMPT restritivo demais ou chunk sem o fato")
        elif not hit:
            r["gravidade"] = 3
            r["diagnostico"] = "BUSCA: doc_esperado não recuperado e resposta sem o fato (possível alucinação)"
        else:
            r["gravidade"] = 2 if len(faltando) == len(fatos) else 1
            r["diagnostico"] = ("GERAÇÃO/DOCUMENTO: doc certo nas fontes mas fato ausente da resposta "
                                "(chunk incompleto, documento sem o número exato ou prompt)")
    else:
        r["alucinou"] = not r["recusou"]
        r["gravidade"] = 3 if r["alucinou"] else 0
        r["diagnostico"] = "ALUCINAÇÃO: respondeu pergunta fora dos documentos (PROMPT)" if r["alucinou"] else "ok"
    return r


def pct(num: int, den: int) -> float | None:
    return None if den == 0 else num / den


def p95(valores: list[float]) -> float | None:
    if not valores:
        return None
    v = sorted(valores)
    return v[max(0, math.ceil(0.95 * len(v)) - 1)]


def calcular_metricas(res: list[dict], top_k: int) -> dict:
    resp = [r for r in res if r["tipo"] == "respondivel"]
    nresp = [r for r in res if r["tipo"] == "nao_respondivel"]
    resp_ok = [r for r in resp if not r["erro"]]
    nresp_ok = [r for r in nresp if not r["erro"]]
    lats = [float(r["latency_ms"]) for r in res if r["latency_ms"] != ""]
    por_estilo = {}
    for estilo in sorted({r["estilo"] for r in resp}):
        g = [r for r in resp if r["estilo"] == estilo]
        por_estilo[estilo] = {"n": len(g), "acuracia": pct(sum(r["acertou"] is True for r in g), len(g))}
    return {
        "top_k": top_k,
        "n_total": len(res), "n_respondiveis": len(resp), "n_nao_respondiveis": len(nresp),
        "erros_chamada": sum(bool(r["erro"]) for r in res),
        # denominador = todas as perguntas da categoria (erro de chamada conta como falha)
        "acuracia": pct(sum(r["acertou"] is True for r in resp), len(resp)),
        "hit_at_k": pct(sum(r["hit"] is True for r in resp), len(resp)),
        "recusa_indevida": pct(sum(r["recusou"] is True for r in resp_ok), len(resp)),
        "recusa_correta": pct(sum(r["recusou"] is True for r in nresp_ok), len(nresp)),
        "alucinacao": pct(sum(r["alucinou"] is True for r in nresp_ok), len(nresp)),
        "latencia_media_ms": (sum(lats) / len(lats)) if lats else None,
        "latencia_p95_ms": p95(lats),
        "acuracia_por_estilo": por_estilo,
    }


# --------------------------------------------------------------------------- saídas
def fmt_pct(v):
    return "—" if v is None else f"{v * 100:.1f}%"


def fmt_ms(v):
    return "—" if v is None else f"{v:,.0f} ms".replace(",", ".")


LINHAS_METRICAS = [
    ("Acurácia (fatos-chave na resposta)", "acuracia", fmt_pct, "≥ 85%"),
    ("Recuperação (hit@k)", "hit_at_k", fmt_pct, "≥ 90%"),
    ("Recusa correta (fora do escopo)", "recusa_correta", fmt_pct, "100%"),
    ("Alucinação (fora do escopo)", "alucinacao", fmt_pct, "0%"),
    ("Recusa indevida (respondíveis)", "recusa_indevida", fmt_pct, "≤ 5%"),
    ("Latência média", "latencia_media_ms", fmt_ms, "—"),
    ("Latência p95", "latencia_p95_ms", fmt_ms, "—"),
]


def salvar_csv(res: list[dict], caminho: Path) -> None:
    campos = ["id", "tipo", "estilo", "pergunta", "resposta_esperada", "resposta", "fatos_ok", "fatos_faltando",
              "acertou", "doc_esperado", "fontes", "hit", "recusou", "alucinou", "latency_ms", "gravidade",
              "diagnostico", "erro"]
    with caminho.open("w", encoding="utf-8-sig", newline="") as f:  # utf-8-sig: abre certo no Excel
        w = csv.DictWriter(f, fieldnames=campos, extrasaction="ignore")
        w.writeheader()
        w.writerows(res)


def recomendacoes(m: dict, res: list[dict]) -> list[str]:
    rec = []
    diag = [r["diagnostico"] for r in res if r["gravidade"] > 0]
    n_busca = sum("BUSCA" in d for d in diag)
    n_ger = sum("GERAÇÃO" in d or "PROMPT restritivo" in d for d in diag)
    n_aluc = sum("ALUCINAÇÃO" in d for d in diag)
    if m["erros_chamada"]:
        rec.append(f"**Estabilidade (Backend):** {m['erros_chamada']} chamada(s) falharam — verificar timeouts, "
                   "chave/modelo da Anthropic e logs da API.")
    if n_busca:
        rec.append(f"**Busca (Backend/Dados):** {n_busca} caso(s) sem o documento certo nas fontes. Conferir prefixo "
                   "`query: `/`passage: `, aumentar `top_k` para 5–6, e chunks com título do documento no texto "
                   "(o título ajuda o e5 a casar perguntas curtas/informais).")
    if n_ger:
        rec.append(f"**Geração/Documento (Backend/Dados):** {n_ger} caso(s) com o documento certo recuperado mas sem o "
                   "fato na resposta. Ver se o chunk contém o número exato do briefing; se sim, ajustar o prompt para "
                   "citar valores literalmente e não recusar quando o contexto tem a resposta.")
    if n_aluc:
        rec.append(f"**Prompt anti-alucinação (Backend):** {n_aluc} pergunta(s) fora do escopo respondidas. Reforçar: "
                   "responder SOMENTE com o contexto e devolver exatamente a frase de recusa. (Limiar de `score` NÃO "
                   "funciona aqui: os scores do e5 ficam comprimidos em 0,83–0,92, inclusive fora do escopo.)")
    estilos = {k: v["acuracia"] for k, v in m["acuracia_por_estilo"].items() if v["acuracia"] is not None}
    if estilos and min(estilos.values()) < (m["acuracia"] or 0) - 0.1:
        pior = min(estilos, key=estilos.get)
        rec.append(f"**Robustez de linguagem:** acurácia no estilo `{pior}` ({fmt_pct(estilos[pior])}) bem abaixo da "
                   "média — considerar normalizar a pergunta (minúsculas/acentos) ou reescrevê-la com o LLM antes da busca.")
    if m["latencia_p95_ms"] and m["latencia_p95_ms"] > 8000:
        rec.append("**Latência:** p95 acima de 8 s — reduzir `max_tokens`, usar contexto menor ou modelo mais rápido "
                   "(ex.: Haiku) para perguntas simples.")
    if not rec:
        rec.append("Nenhuma falha relevante. Próximos passos: ampliar o dataset com perguntas multi-documento e "
                   "perguntas ambíguas, e rodar a avaliação a cada mudança de prompt/chunking (regressão).")
    return rec


def gerar_relatorio(res: list[dict], m: dict, rotulo: str, caminho: Path, dry_run: bool) -> None:
    L = []
    L.append("# Relatório de Avaliação — Assistente RAG Nexo Seguros\n")
    if dry_run:
        L.append("> **DRY-RUN** — respostas simuladas (perfeitas) para validar o dataset e o avaliador. "
                 "Os números abaixo NÃO medem o assistente.\n")
    L.append(f"- Rodada: **{rotulo}** — {datetime.now():%Y-%m-%d %H:%M}")
    L.append(f"- Dataset: `eval/dataset.jsonl` — {m['n_total']} perguntas "
             f"({m['n_respondiveis']} respondíveis, {m['n_nao_respondiveis']} fora do escopo)")
    L.append(f"- `top_k` = {m['top_k']} · erros de chamada: {m['erros_chamada']}\n")

    L.append("## Métricas\n")
    L.append("| Métrica | Valor | Meta |\n|---|---|---|")
    for nome, chave, f, meta in LINHAS_METRICAS:
        L.append(f"| {nome} | {f(m[chave])} | {meta} |")
    status = "✅ atingida" if (m["acuracia"] or 0) >= META_ACURACIA else "❌ abaixo da meta"
    L.append(f"\nMeta de acurácia (85%): **{status}**.\n")

    L.append("### Acurácia por estilo de pergunta\n")
    L.append("| Estilo | Perguntas | Acurácia |\n|---|---|---|")
    for estilo, v in m["acuracia_por_estilo"].items():
        L.append(f"| {estilo} | {v['n']} | {fmt_pct(v['acuracia'])} |")
    L.append("")

    # antes × depois (histórico)
    hist = sorted(HIST_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime) if HIST_DIR.exists() else []
    if len(hist) >= 2 and not dry_run:
        rodadas = [json.loads(p.read_text(encoding="utf-8")) for p in hist]
        L.append("## Antes × depois\n")
        L.append("| Métrica | " + " | ".join(r["rotulo"] for r in rodadas) + " |")
        L.append("|---|" + "---|" * len(rodadas))
        for nome, chave, f, _ in LINHAS_METRICAS:
            L.append(f"| {nome} | " + " | ".join(f(r["metricas"].get(chave)) for r in rodadas) + " |")
        L.append("")

    L.append("## 5 piores casos\n")
    piores = sorted([r for r in res if r["gravidade"] > 0],
                    key=lambda r: (-r["gravidade"], -(float(r["latency_ms"] or 0))))[:5]
    if not piores:
        L.append("Nenhum caso com falha. 🎉\n")
    for r in piores:
        resposta = (r["resposta"] or r["erro"] or "").replace("\n", " ")
        if len(resposta) > 300:
            resposta = resposta[:300] + "…"
        L.append(f"**{r['id']}** ({r['tipo']}, {r['estilo']}) — gravidade {r['gravidade']}")
        L.append(f"- Pergunta: {r['pergunta']}")
        L.append(f"- Esperado: {r['resposta_esperada']}  (doc: `{r['doc_esperado'] or '—'}`)")
        L.append(f"- Obtido: {resposta}")
        L.append(f"- Fontes: `{r['fontes'] or '—'}`" + (f" · fatos faltando: {r['fatos_faltando']}" if r['fatos_faltando'] else ""))
        L.append(f"- Diagnóstico: {r['diagnostico']}\n")

    L.append("## Recomendações\n")
    for rec in recomendacoes(m, res):
        L.append(f"- {rec}")
    L.append("")

    if NOTAS_QA.exists() and not dry_run:
        L.append("## Notas do QA\n")
        L.append(NOTAS_QA.read_text(encoding="utf-8").strip() + "\n")

    L.append("## Metodologia\n")
    L.append("- **Acurácia**: a resposta precisa conter *todos* os `fatos_chave` (comparação sem acento/caixa; "
             "alternativas separadas por `|`, ex.: `7 dias|sete dias`).")
    L.append("- **hit@k**: algum `doc_esperado` aparece em `sources[].doc_id`.")
    L.append(f"- **Recusa**: a resposta contém \"{FRASE_RECUSA}\". **Alucinação** = pergunta fora do escopo sem recusa.")
    L.append("- **Latência**: `latency_ms` devolvido pela API (média e p95 por *nearest-rank*).")
    L.append("- Detalhe por pergunta: `eval/resultados.csv`.")
    caminho.write_text("\n".join(L) + "\n", encoding="utf-8")


# --------------------------------------------------------------------------- main
def imprimir_metricas(m: dict) -> None:
    print("\n=== Métricas ===")
    for nome, chave, f, meta in LINHAS_METRICAS:
        print(f"  {nome:<38} {f(m[chave]):>10}   (meta {meta})")


def main() -> int:
    ap = argparse.ArgumentParser(description="Avaliação do assistente RAG Nexo Seguros")
    ap.add_argument("--api", default="http://localhost:8000")
    ap.add_argument("--dataset", type=Path, default=DATASET)
    ap.add_argument("--top-k", type=int, default=4)
    ap.add_argument("--timeout", type=float, default=120)
    ap.add_argument("--rotulo", default=None, help="nome da rodada (ex.: antes, depois). Padrão: data/hora")
    ap.add_argument("--dry-run", action="store_true", help="valida dataset e avaliador sem chamar a API")
    ap.add_argument("--limite", type=int, default=0, help="avaliar só as N primeiras perguntas (debug)")
    args = ap.parse_args()

    itens = carregar_dataset(args.dataset)
    probs = validar_dataset(itens)
    print(f"Dataset: {len(itens)} perguntas")
    for p in probs:
        print(f"  [PROBLEMA] {p}")
    for a in checar_doc_ids(itens):
        print(f"  [AVISO] {a}")
    if probs:
        print("Dataset com problemas — corrija antes de avaliar.")
        return 2
    print("  dataset OK (estrutura + fatos conferidos contra o briefing)")
    if args.limite:
        itens = itens[: args.limite]

    rotulo = args.rotulo or datetime.now().strftime("%Y%m%d-%H%M")
    if args.dry_run:
        res = [avaliar_item(i, resposta_simulada(i), 0.0) for i in itens]
        m = calcular_metricas(res, args.top_k)
        imprimir_metricas(m)
        salvar_csv(res, EVAL_DIR / "resultados_dry_run.csv")
        gerar_relatorio(res, m, "dry-run", EVAL_DIR / "relatorio_dry_run.md", dry_run=True)
        perfeito = (m["acuracia"] == 1 and m["hit_at_k"] == 1 and m["recusa_correta"] == 1 and m["alucinacao"] == 0)
        print("\nAutoteste do avaliador:", "OK (respostas perfeitas → 100%)" if perfeito else "FALHOU")
        return 0 if perfeito else 1

    try:
        h = http_json(f"{args.api}/health", timeout=10)
        print(f"API: {h}")
    except Exception as e:
        print(f"[ERRO] API indisponível em {args.api}/health: {e}")
        return 3

    res = []
    for n, item in enumerate(itens, 1):
        try:
            resp, lat = perguntar(args.api, item["pergunta"], args.top_k, args.timeout)
            r = avaliar_item(item, resp, lat)
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as e:
            r = avaliar_item(item, None, 0.0, erro=str(e)[:200])
        marca = "✔" if r["gravidade"] == 0 else ("✖" if r["gravidade"] >= 2 else "~")
        print(f"[{n:02d}/{len(itens)}] {marca} {item['id']} {r['latency_ms']}ms  {r['diagnostico']}")
        res.append(r)

    m = calcular_metricas(res, args.top_k)
    imprimir_metricas(m)
    HIST_DIR.mkdir(exist_ok=True)
    (HIST_DIR / f"{rotulo}.json").write_text(
        json.dumps({"rotulo": rotulo, "data": datetime.now().isoformat(timespec="seconds"), "metricas": m},
                   ensure_ascii=False, indent=2), encoding="utf-8")
    salvar_csv(res, EVAL_DIR / "resultados.csv")
    gerar_relatorio(res, m, rotulo, EVAL_DIR / "relatorio.md", dry_run=False)
    print(f"\nGerados: eval/resultados.csv, eval/relatorio.md, eval/historico/{rotulo}.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
