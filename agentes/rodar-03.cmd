@echo off
chcp 65001 >nul
cd /d "%~dp0.."
set "PATH=%USERPROFILE%\.local\bin;%PATH%"
title Eng. Backend
claude --permission-mode auto "Leia o arquivo agentes/03-engenheiro-backend.md e siga as instrucoes dele: voce e esse agente da equipe."
