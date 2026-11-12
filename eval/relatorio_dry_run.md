# Relatório de Avaliação — Assistente RAG Nexo Seguros

> **DRY-RUN** — respostas simuladas (perfeitas) para validar o dataset e o avaliador. Os números abaixo NÃO medem o assistente.

- Rodada: **dry-run** — 2026-11-12 19:55
- Dataset: `eval/dataset.jsonl` — 50 perguntas (40 respondíveis, 10 fora do escopo)
- `top_k` = 4 · erros de chamada: 0

## Métricas

| Métrica | Valor | Meta |
|---|---|---|
| Acurácia (fatos-chave na resposta) | 100.0% | ≥ 85% |
| Recuperação (hit@k) | 100.0% | ≥ 90% |
| Recusa correta (fora do escopo) | 100.0% | 100% |
| Alucinação (fora do escopo) | 0.0% | 0% |
| Recusa indevida (respondíveis) | 0.0% | ≤ 5% |
| Latência média | 0 ms | — |
| Latência p95 | 0 ms | — |

Meta de acurácia (85%): **✅ atingida**.

### Acurácia por estilo de pergunta

| Estilo | Perguntas | Acurácia |
|---|---|---|
| erro_digitacao | 5 | 100.0% |
| formal | 22 | 100.0% |
| informal | 13 | 100.0% |

## 5 piores casos

Nenhum caso com falha. 🎉

## Recomendações

- Nenhuma falha relevante. Próximos passos: ampliar o dataset com perguntas multi-documento e perguntas ambíguas, e rodar a avaliação a cada mudança de prompt/chunking (regressão).

## Metodologia

- **Acurácia**: a resposta precisa conter *todos* os `fatos_chave` (comparação sem acento/caixa; alternativas separadas por `|`, ex.: `7 dias|sete dias`).
- **hit@k**: algum `doc_esperado` aparece em `sources[].doc_id`.
- **Recusa**: a resposta contém "Não encontrei essa informação nos documentos internos.". **Alucinação** = pergunta fora do escopo sem recusa.
- **Latência**: `latency_ms` devolvido pela API (média e p95 por *nearest-rank*).
- Detalhe por pergunta: `eval/resultados.csv`.
