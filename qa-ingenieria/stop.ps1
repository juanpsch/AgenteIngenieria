<#
  Para TODA la app (backend + frontend) que levanto start.ps1.
  Mata los PIDs de .run\pids.txt con todo su arbol de hijos; si no hay registro, cae a liberar los puertos 8000/5173.
  Uso:  .\stop.ps1
#>
$ErrorActionPreference = "Continue"
$root    = $PSScriptRoot
$pidFile = Join-Path $root ".run\pids.txt"

function Stop-Tree($procId) {
    if ($procId) { taskkill /PID $procId /T /F 2>$null | Out-Null }
}

$paro = $false
if (Test-Path $pidFile) {
    foreach ($line in Get-Content $pidFile) {
        if ($line -match '^\d+$') {
            Write-Host "Parando PID $line y sus hijos ..." -ForegroundColor Cyan
            Stop-Tree([int]$line)
            $paro = $true
        }
    }
    Remove-Item $pidFile -Force
}

# Fallback: por si quedo algo escuchando en los puertos (arranques manuales, etc.)
foreach ($port in 8000, 5173) {
    $conns = Get-NetTCPConnection -State Listen -LocalPort $port -ErrorAction SilentlyContinue
    foreach ($c in $conns) {
        Write-Host "Liberando puerto $port (PID $($c.OwningProcess)) ..." -ForegroundColor Cyan
        Stop-Tree($c.OwningProcess)
        $paro = $true
    }
}

if ($paro) { Write-Host "Todo parado." -ForegroundColor Green }
else { Write-Host "No habia nada corriendo." -ForegroundColor Yellow }
