<#
  Levanta TODA la app de una, EN SEGUNDO PLANO (sin ventanas): backend (FastAPI/uvicorn :8000) + frontend (Vite :5173).
  Cada uno escribe sus logs a un archivo en .run\ y deja su PID en .run\pids.txt.
  Ver logs en vivo:   Get-Content .run\backend.log -Wait     (o frontend.log)
  Parar todo con:     .\stop.ps1
  Uso:                .\start.ps1   (si PowerShell bloquea:  powershell -ExecutionPolicy Bypass -File .\start.ps1)
#>
$ErrorActionPreference = "Stop"
$root     = $PSScriptRoot
$runDir   = Join-Path $root ".run"
$pidFile  = Join-Path $runDir "pids.txt"
$logBack  = Join-Path $runDir "backend.log"
$logFront = Join-Path $runDir "frontend.log"
New-Item -ItemType Directory -Force -Path $runDir | Out-Null

if (Test-Path $pidFile) {
    Write-Host "Ya parece levantado (.run\pids.txt existe). Primero corre:  .\stop.ps1" -ForegroundColor Yellow
    exit 1
}

function Test-Port($port) {
    [bool](Get-NetTCPConnection -State Listen -LocalPort $port -ErrorAction SilentlyContinue)
}
foreach ($p in 8000, 5173) {
    if (Test-Port $p) {
        Write-Host "El puerto $p ya esta en uso. Corre  .\stop.ps1  o libera el puerto." -ForegroundColor Yellow
        exit 1
    }
}

# Cada servicio corre dentro de un cmd OCULTO que redirige stdout+stderr (2>&1) a su .log.
Write-Host "-> Backend  (uvicorn :8000)  ->  .run\backend.log" -ForegroundColor Cyan
$back = Start-Process cmd -PassThru -WindowStyle Hidden -WorkingDirectory $root -ArgumentList @(
    "/c", "uv run uvicorn api.main:app --reload --port 8000 > `"$logBack`" 2>&1"
)

Write-Host "-> Frontend (vite :5173)     ->  .run\frontend.log" -ForegroundColor Cyan
$front = Start-Process cmd -PassThru -WindowStyle Hidden -WorkingDirectory (Join-Path $root "frontend") -ArgumentList @(
    "/c", "npm run dev > `"$logFront`" 2>&1"
)

Set-Content -Path $pidFile -Encoding ascii -Value @($back.Id, $front.Id)

Write-Host ""
Write-Host "  Listo (en segundo plano, sin ventanas)." -ForegroundColor Green
Write-Host "  Backend : http://127.0.0.1:8000/docs"
Write-Host "  Frontend: http://localhost:5173"
Write-Host "  Logs    : Get-Content .run\backend.log -Wait   |   Get-Content .run\frontend.log -Wait" -ForegroundColor DarkGray
Write-Host "  Parar todo con:  .\stop.ps1" -ForegroundColor DarkGray
