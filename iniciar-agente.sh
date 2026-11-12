#!/usr/bin/env bash
# Uso: ./iniciar-agente.sh 1   (1=Tech Lead, 2=Dados, 3=Backend, 4=Frontend, 5=QA)
# Abre uma sessão do Claude Code já com o prompt do agente.
set -e
cd "$(dirname "$0")"
PROMPT_FILE=$(ls agentes/0"$1"-*.md 2>/dev/null | head -n1)
if [ -z "$PROMPT_FILE" ]; then
  echo "Agente $1 não encontrado. Use 1 a 5."; exit 1
fi
echo ">> Iniciando $(basename "$PROMPT_FILE" .md)"
# acceptEdits: o agente edita arquivos sozinho, mas pede aprovação para comandos
# (as aprovações aparecem no Habblaud — ótimo para o vídeo).
exec claude --permission-mode acceptEdits "$(cat "$PROMPT_FILE")"
