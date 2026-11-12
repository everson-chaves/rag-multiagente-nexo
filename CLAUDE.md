# Projeto: Assistente Interno RAG — Nexo Seguros (empresa fictícia)

Você faz parte de uma **equipe de 5 agentes** construindo, em paralelo, um assistente interno com RAG
(Retrieval-Augmented Generation) para a Nexo Seguros. Cada agente roda em uma sessão própria do Claude Code
e é dono de **uma pasta**. Não edite pastas de outros agentes — se precisar de algo deles, escreva em
`equipe/QUADRO.md` (o quadro de comunicação da equipe).

## Equipe e donos de pasta

| Agente | Pasta que é dono | Entrega |
|---|---|---|
| Tech Lead | `README.md`, `docs/arquitetura.md`, `equipe/` | Arquitetura, integração, README final |
| Engenheiro de Dados | `ingest/`, `data/` | Documentos da empresa + pipeline de ingestão + base vetorial |
| Engenheiro de Backend | `api/` | API FastAPI de busca + geração com Claude |
| Engenheiro de Frontend | `web/` | Chat web com fontes citadas |
| Engenheiro de QA | `eval/` | Dataset de perguntas + avaliação + relatório de métricas |

## Contratos (todos devem respeitar — NÃO mude sem registrar no QUADRO)

**Stack:** Python 3.11+, FastAPI, ChromaDB (persistente), sentence-transformers, SDK `anthropic`. Front em HTML/CSS/JS puro (sem build).

**Base vetorial**
- Caminho: `data/chroma`
- Coleção: `nexo_docs`
- Modelo de embeddings (local, gratuito): `intfloat/multilingual-e5-small`
  - Prefixo `passage: ` ao indexar e `query: ` ao buscar (exigência do e5).
- Metadados de cada chunk: `doc_id`, `titulo`, `area`, `chunk_idx`

**Documentos-fonte:** `data/docs/*.md` (um arquivo por documento, com título na 1ª linha `# ...`).

**API** (porta 8000)
- `GET /health` → `{"status": "ok", "chunks": <int>}`
- `POST /ask` com `{"question": str, "top_k": int = 4}` →
  ```json
  {
    "answer": "texto com citações [1], [2]",
    "sources": [{"n": 1, "doc_id": "...", "titulo": "...", "trecho": "...", "score": 0.83}],
    "latency_ms": 1234
  }
  ```
- Se a resposta não estiver nos documentos, o assistente deve dizer **"Não encontrei essa informação nos documentos internos."** (isso é medido pelo QA).
- CORS liberado para `http://localhost:5500`.

**LLM:** modelo lido de `ANTHROPIC_MODEL` (padrão `claude-sonnet-5-5`), chave em `ANTHROPIC_API_KEY` (arquivo `.env` na raiz; use `.env.example` como modelo). Nunca commite a chave.

**Front:** `web/index.html` servido em `http://localhost:5500` (`python -m http.server 5500 -d web`).

## Regras da equipe
- Escreva em português (código pode ter nomes em inglês).
- Ao concluir uma etapa, registre uma linha em `equipe/QUADRO.md`: `- [HH:MM] <Agente>: <o que fez / o que precisa>`.
- Leia o QUADRO antes de começar e sempre que travar.
- Comandos de longa duração (servidores) devem ser rodados em segundo plano ou apenas documentados.
- Faça commits pequenos com prefixo do agente, ex.: `dados: pipeline de chunking`.
