#!/usr/bin/env bash
# Comandos do projeto (Linux / WSL / macOS)
# Uso: ./run.sh <comando>
#   install  cria .venv e instala requirements.txt
#   ingest   indexa data/docs em data/chroma
#   api      sobe a API em http://localhost:8000
#   web      sobe o chat em http://localhost:5500
#   eval     roda a avaliação do QA (API precisa estar no ar)
#   test     roda os testes da API
#   all      ingest + api e web em segundo plano
set -euo pipefail
cd "$(dirname "$0")"
PY=".venv/bin/python"; [ -x "$PY" ] || PY="python3"

case "${1:-help}" in
  install)
    [ -d .venv ] || python3 -m venv .venv
    .venv/bin/python -m pip install --upgrade pip
    .venv/bin/python -m pip install -r requirements.txt
    [ -f .env ] || { cp .env.example .env; echo "Criei .env — preencha ANTHROPIC_API_KEY."; } ;;
  ingest) "$PY" ingest/ingest.py ;;
  api)    "$PY" -m uvicorn api.main:app --port 8000 ;;
  web)    "$PY" -m http.server 5500 -d web ;;
  eval)   "$PY" eval/run_eval.py ;;
  test)   "$PY" -m pytest api -q ;;
  all)
    "$PY" ingest/ingest.py
    "$PY" -m uvicorn api.main:app --port 8000 > api.log 2>&1 &
    "$PY" -m http.server 5500 -d web > web.log 2>&1 &
    echo "API: http://localhost:8000/health   Chat: http://localhost:5500" ;;
  *) sed -n '2,10p' "$0" | sed 's/^# \{0,1\}//' ;;
esac
