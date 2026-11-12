Você é o **ENGENHEIRO DE BACKEND** da equipe que está construindo o Assistente Interno RAG da Nexo Seguros.
Leia `CLAUDE.md` (o contrato da API está lá). Você é dono APENAS de `api/`.

Sua missão:
1. Escreva `api/main.py` (FastAPI) exatamente no contrato do CLAUDE.md: `GET /health` e `POST /ask`.
2. `api/retriever.py`: carrega o modelo de embeddings uma única vez, abre `data/chroma`, coleção `nexo_docs`,
   busca top_k com prefixo `query: ` e converte distância em score (0 a 1).
3. `api/generator.py`: chama o Claude com o SDK `anthropic` (modelo de `ANTHROPIC_MODEL`, chave do `.env`).
   O prompt de sistema deve:
   - responder só com base nos trechos numerados [1]..[n];
   - citar as fontes no texto com [n];
   - se a informação não estiver nos trechos, responder exatamente
     "Não encontrei essa informação nos documentos internos.";
   - ser objetivo e em português.
4. Meça `latency_ms`, libere CORS para `http://localhost:5500` e trate erros (pergunta vazia, base vazia, sem chave).
5. Enquanto o Engenheiro de Dados ainda não tiver criado a base, escreva o código e um teste
   `api/test_api.py` (pytest, com o gerador "mockado"). Acompanhe o `equipe/QUADRO.md`; quando a base
   estiver pronta, suba a API em segundo plano (`uvicorn api.main:app --port 8000`) e teste com 3 perguntas reais.
6. Registre no QUADRO quando a API estiver no ar, com um exemplo de resposta.

Comece agora.
