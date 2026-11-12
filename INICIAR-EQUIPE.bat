@echo off
cd /d "%~dp0"
start "Tech Lead" cmd /k "%~dp0agentes\rodar-01.cmd"
echo Tech Lead iniciado. Esperando 60 s para ele publicar o plano...
timeout /t 60 /nobreak >nul
start "Eng. Dados" cmd /k "%~dp0agentes\rodar-02.cmd"
start "Eng. Backend" cmd /k "%~dp0agentes\rodar-03.cmd"
start "Eng. Frontend" cmd /k "%~dp0agentes\rodar-04.cmd"
start "Eng. QA" cmd /k "%~dp0agentes\rodar-05.cmd"
echo Equipe iniciada.
pause
