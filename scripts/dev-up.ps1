# Starts postgres/redis, waits for 5432, launches backend and frontend.
$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)

Write-Host "==> docker compose up postgres redis"
docker compose up -d postgres redis
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "==> Wait for PostgreSQL on :5432..."
$ready = $false
for ($i = 0; $i -lt 120; $i++) {
  try {
    $t = Test-NetConnection -ComputerName 127.0.0.1 -Port 5432 -WarningAction SilentlyContinue
    if ($t.TcpTestSucceeded) { $ready = $true; break }
  } catch { }
  Start-Sleep -Seconds 1
}
if (-not $ready) {
  Write-Error "PostgreSQL unreachable on 127.0.0.1:5432 after 120s"
  exit 1
}

Write-Host "==> backend uvicorn :8000"
$backend = "cd `"$PWD\backend`"; .\venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000"
Start-Process powershell -ArgumentList @("-NoExit", "-Command", $backend) -WindowStyle Normal

Start-Sleep -Seconds 2

Write-Host "==> frontend Vite :5173"
$frontend = "cd `"$PWD\frontend`"; npm run dev"
Start-Process powershell -ArgumentList @("-NoExit", "-Command", $frontend) -WindowStyle Normal

Write-Host "Done. Windows popped up for backend (8000), frontend (5173). Web: http://localhost:5173/"
