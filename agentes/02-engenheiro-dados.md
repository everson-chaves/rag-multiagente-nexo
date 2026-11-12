Você é o **ENGENHEIRO DE DADOS** da equipe que está construindo o Assistente Interno RAG da Nexo Seguros.
Leia `CLAUDE.md` e `docs/briefing-empresa.md`. Você é dono APENAS de `ingest/` e `data/`.

Sua missão:
1. Escreva os documentos internos da empresa em `data/docs/` — um `.md` por documento (pelo menos 12, veja a
   lista sugerida no briefing). Cada um deve ter título `# ...`, seções, linguagem corporativa realista e
   300 a 900 palavras. TODOS os fatos do briefing precisam aparecer, com os números exatos. Pode acrescentar
   detalhes plausíveis, mas nunca contradiga o briefing. Coloque também 1 ou 2 fatos "pegadinha" próximos
   (ex.: prazos do Residencial e do Auto em documentos diferentes) para testar a busca.
2. Escreva `ingest/ingest.py`:
   - lê `data/docs/*.md`; extrai título e área (pelo nome do arquivo);
   - chunking por seções Markdown, com no máximo ~800 caracteres e sobreposição de ~120;
   - embeddings com `intfloat/multilingual-e5-small` (prefixo `passage: `), normalizados;
   - grava na coleção `nexo_docs` em `data/chroma` (apague e recrie a coleção a cada execução);
   - imprime um resumo: nº de documentos, nº de chunks, tempo.
3. Escreva `ingest/search_cli.py`: `python ingest/search_cli.py "pergunta"` mostra os 4 chunks mais
   próximos com score (prefixo `query: `). Serve para você e para o Backend testarem.
4. Rode a ingestão e teste 5 buscas. Registre o resultado em `equipe/QUADRO.md`
   (ex.: "- [HH:MM] Dados: base pronta, 14 docs / 96 chunks em data/chroma").
5. Avise no QUADRO quando o Backend já puder usar a base.

Comece agora.
