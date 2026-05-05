Write-Host "🚀 Starting ARIA Development Environment..." -ForegroundColor Cyan

# Step 1: Start Docker services
Write-Host "[1/4] Starting SurrealDB and Elyra..." -ForegroundColor Yellow
docker compose -f docker-compose.dev.yml up -d surrealdb elyra
if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] Failed to start Docker services. Is Docker Desktop running?" -ForegroundColor Red
    exit 1
}

# Step 2: Start API backend in background
Write-Host "[2/4] Starting API backend..." -ForegroundColor Yellow
$apiJob = Start-Process -FilePath "uv" -ArgumentList "run run_api.py" -PassThru -NoNewWindow
Write-Host "      API started (PID: $($apiJob.Id))"

# Poll API health until it's ready
Write-Host "      Waiting for API health check..." -NoNewline
for ($i = 0; $i -lt 30; $i++) {
    try {
        $response = Invoke-WebRequest -Uri "http://localhost:5055/health" -UseBasicParsing -ErrorAction SilentlyContinue
        if ($response.StatusCode -eq 200) {
            Write-Host " Ready!" -ForegroundColor Green
            break
        }
    } catch {}
    Write-Host "." -NoNewline
    Start-Sleep -Seconds 1
}

# Step 3: Start background worker in background
Write-Host "[3/4] Starting background worker..." -ForegroundColor Yellow
$workerJob = Start-Process -FilePath "uv" -ArgumentList "run --env-file .env surreal-commands-worker --import-modules commands" -PassThru -NoNewWindow
Write-Host "      Worker started (PID: $($workerJob.Id))"
Start-Sleep -Seconds 1

# Step 4: Start Next.js frontend (foreground)
Write-Host "" 
Write-Host "[OK] All services started!" -ForegroundColor Green
Write-Host "     Frontend: http://localhost:3000" -ForegroundColor Cyan
Write-Host "     API:      http://localhost:5055" -ForegroundColor Cyan
Write-Host "     API Docs: http://localhost:5055/docs" -ForegroundColor Cyan
Write-Host "     Elyra:    http://localhost:8888/elyra/lab" -ForegroundColor Cyan
Write-Host ""
Write-Host "[4/4] Starting Next.js frontend (press Ctrl+C to stop)..." -ForegroundColor Yellow
Write-Host ""

Set-Location aria-frontend

# Run dev server using bun if available, otherwise npm
if (Get-Command bun -ErrorAction SilentlyContinue) {
    bun run dev
} else {
    npm run dev
}
