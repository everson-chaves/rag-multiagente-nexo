# Como rodar o projeto e gravar para o LinkedIn

Tempo total: ~1h30 (15 min de setup + 45–60 min dos agentes trabalhando + gravação).

## 1. Coloque a pasta no lugar
Extraia o zip em:
`D:\ARMAZENAMENTO FACILITA PROJETOS\000 - PROJETOS NOVOS\rag-multiagente-nexo`

## 2. Instale o Habblaud (uma vez só)
1. Abra o terminal e rode `claude`.
2. Em https://habblaud.com, copie o **prompt de instalação** e cole no Claude Code.
3. Aprove o que ele pedir. Leva de 3 a 10 minutos; no Windows ele instala o WSL2 sozinho e pode pedir para reiniciar uma vez.
4. Abra **http://habblaud.localhost** (ou http://localhost:4747). Para testar o visual antes, use `http://localhost:4747/?mock=1`.

> Repositório: https://github.com/marmottajr/habblaud

## 3. Prepare o ambiente do projeto (no WSL / Ubuntu)
```bash
cd "/mnt/d/ARMAZENAMENTO FACILITA PROJETOS/000 - PROJETOS NOVOS/rag-multiagente-nexo"
git init && git add . && git commit -m "projeto inicial"
cp .env.example .env
nano .env              # cole sua ANTHROPIC_API_KEY (console.anthropic.com)
python3 -m venv .venv && source .venv/bin/activate
```
Confirme que o Claude Code está instalado **dentro do WSL** (`claude --version`). Se não estiver:
`npm install -g @anthropic-ai/claude-code`.

## 4. Coloque a equipe para trabalhar
**Opção A (automática):** no Windows, execute `iniciar-equipe.ps1`. Ele abre 5 abas do Windows Terminal, uma por agente.

**Opção B (manual):** abra 5 terminais WSL na pasta do projeto e rode em cada um:
```bash
./iniciar-agente.sh 1   # Tech Lead   (comece por este e espere ~1 min)
./iniciar-agente.sh 2   # Engenheiro de Dados
./iniciar-agente.sh 3   # Engenheiro de Backend
./iniciar-agente.sh 4   # Engenheiro de Frontend
./iniciar-agente.sh 5   # Engenheiro de QA
```

Dica: inicie o Tech Lead primeiro e espere ele publicar o plano em `equipe/QUADRO.md`. Depois solte os outros 4 de uma vez — o escritório "enche" na hora, e esse é o melhor momento do vídeo.

## 5. O que gravar (roteiro do vídeo)
Use **Win + Alt + R** (Xbox Game Bar) ou o OBS. Depois acelere o vídeo de 10× a 20× no CapCut.

| Cena | Duração final | O que mostrar |
|---|---|---|
| 1. Gancho | 3 s | Escritório do Habblaud vazio → 5 personagens entram |
| 2. Trabalho | 15 s | Timelapse dos agentes trabalhando, balões de status |
| 3. Aprovação | 5 s | Você aprovando um pedido de permissão direto no escritório |
| 4. O quadro | 4 s | `equipe/QUADRO.md` com os agentes conversando entre si |
| 5. O resultado | 15 s | Chat da Nexo respondendo com citações das fontes |
| 6. A prova | 5 s | `eval/relatorio.md` com acurácia e taxa de alucinação |
| 7. O custo | 3 s | Painel "My Day" do Habblaud com tokens e custo |

Prints extras para o carrossel: o diagrama de `docs/arquitetura.md`, a tabela de métricas e o painel "My Day".

## 6. Rodar o produto final (para a demo)
```bash
python ingest/ingest.py                         # cria a base vetorial
uvicorn api.main:app --port 8000 &              # API
python -m http.server 5500 -d web &             # chat → http://localhost:5500
python eval/run_eval.py                         # métricas
```
(Os nomes exatos podem variar um pouco; o README final do Tech Lead terá os comandos certos.)

## 7. Publicar
- Suba no GitHub como `everson-chaves/rag-multiagente-nexo` (confira se o `.env` NÃO foi junto).
- Poste o vídeo + o texto de `POST-LINKEDIN.md` + o link do repositório no primeiro comentário.

## Se algo travar
- Agente parado esperando você: o personagem fica sinalizado no Habblaud — clique nele e responda.
- Dois agentes brigando pelo mesmo arquivo: peça ao Tech Lead para resolver pelo QUADRO.
- Acurácia baixa: deixe o QA e o Backend iterarem — o "antes × depois" rende um ótimo post.
