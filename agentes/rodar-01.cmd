@echo off
chcp 65001 >nul
cd /d "%~dp0.."
set "PATH=%USERPROFILE%\.local\bin;%PATH%"
title Tech Lead
claude --permission-mode auto "Leia o arquivo agentes/01-tech-lead.md e siga as instrucoes dele: voce e esse agente da equipe."
