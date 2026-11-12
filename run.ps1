# Comandos do projeto (Windows / PowerShell)
# Uso: .\run.ps1 <comando>
#   install  cria .venv e instala requirements.txt
#   ingest   indexa data/docs em data/chroma
#   api      sobe a API em http://localhost:8000
#   web      sobe o chat em http://localhost:5500
#   eval     roda a avaliacao do QA (API precisa estar no ar)
#   test     roda os testes da API
#   all      ingest + api e web em janelas separadas
# (arquivo mantido em ASCII puro: o PowerShell 5.1 le .ps1 sem BOM como ANSI)
param([Parameter(Position = 0)][string]$Cmd = "help")

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
$env:PYTHONUTF8 = "1"
$py = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $py)) { $py = "python" }

switch ($Cmd) {
    "install" {
        if (-not (Test-Path ".venv")) { python -m venv .venv }
        & ".venv\Scripts\python.exe" -m pip install --upgrade pip
        & ".venv\Scripts\python.exe" -m pip install -r requirements.txt
        if (-not (Test-Path ".env")) {
            Copy-Item ".env.example" ".env"
            Write-Host "Criei .env - preencha ANTHROPIC_API_KEY."
        }
    }
    "ingest" { & $py ingest/ingest.py }
    "api"    { & $py -m uvicorn api.main:app --port 8000 }
    "web"    { & $py -m http.server 5500 -d web }
    "eval"   { & $py eval/run_eval.py }
    "test"   { & $py -m pytest api -q }
    "all" {
        & $py ingest/ingest.py
        $apiCmd = "& '$py' -m uvicorn api.main:app --port 8000"
        $webCmd = "& '$py' -m http.server 5500 -d web"
        Start-Process powershell -ArgumentList "-NoExit", "-Command", $apiCmd -WorkingDirectory $PSScriptRoot
        Start-Process powershell -ArgumentList "-NoExit", "-Command", $webCmd -WorkingDirectory $PSScriptRoot
        Write-Host "API: http://localhost:8000/health   Chat: http://localhost:5500"
    }
    default {
        Get-Content $PSCommandPath | Select-Object -Skip 1 -First 8 | ForEach-Object { $_ -replace '^# ?', '' }
    }
}
