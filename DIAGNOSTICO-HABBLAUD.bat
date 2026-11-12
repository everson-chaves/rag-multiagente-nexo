@echo off
cd /d "%~dp0"
set OUT=%~dp0diagnostico.txt
echo === DATA === > "%OUT%"
date /t >> "%OUT%" & time /t >> "%OUT%"
echo === CLAUDE === >> "%OUT%"
"%USERPROFILE%\.local\bin\claude.exe" --version >> "%OUT%" 2>&1
dir "%USERPROFILE%\.claude" /b >> "%OUT%" 2>&1
echo === WSL LISTA === >> "%OUT%"
wsl -l -v >> "%OUT%" 2>&1
echo === DOCKER WINDOWS === >> "%OUT%"
docker version --format "{{.Server.Version}}" >> "%OUT%" 2>&1
docker ps -a >> "%OUT%" 2>&1
tasklist /FI "IMAGENAME eq Docker Desktop.exe" >> "%OUT%" 2>&1
echo === DENTRO DO WSL === >> "%OUT%"
wsl -d Ubuntu -- bash -lc "echo USER=$USER; ls -la ~/habblaud 2>&1 | head -20; node --version; docker ps -a 2>&1; cd ~/habblaud 2>/dev/null && git log -1 --oneline; cat ~/habblaud/.env 2>/dev/null | grep -v -i key; curl -s -m 5 http://localhost:4747/api/health || echo HEALTH_FALHOU" >> "%OUT%" 2>&1
echo === PORTA 4747 WINDOWS === >> "%OUT%"
netstat -ano | findstr 4747 >> "%OUT%" 2>&1
echo FIM >> "%OUT%"
