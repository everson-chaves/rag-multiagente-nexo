@echo off
chcp 65001 >nul
title Instalando Habblaud
set "PATH=%USERPROFILE%\.local\bin;%PATH%"
set "PROJ=%~dp0"
cd /d "%USERPROFILE%"
claude "Leia o arquivo %PROJ%habblaud-prompt.md e continue a instalacao do Habblaud nesta maquina. Situacao atual: Claude Code nativo do Windows ja instalado; Docker Desktop instalado e rodando; Ubuntu no WSL ja instalado (usuario evers). Falta clonar o Habblaud em ~/habblaud no Ubuntu, instalar Node 22+ se faltar, subir com npm run docker:up, rodar npm run mod:install apontando para a pasta do Claude Code do Windows e testar http://localhost:4747/api/health. Evite comandos do tipo baixar-e-executar no PowerShell (irm | iex), porque o antivirus Kaspersky bloqueia; faca as instalacoes dentro do WSL."
