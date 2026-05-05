Write-Host "[*] Starting Open Notebook (Database + Elyra + API + Worker + Frontend)..." -ForegroundColor Cyan

# Step 0: Check for FFmpeg (required for video intelligence)
if (!(Get-Command ffmpeg -ErrorAction SilentlyContinue)) {
    Write-Host "[!] FFmpeg not found. This is required for video processing." -ForegroundColor Yellow
    Write-Host "    Attempting to install via winget..." -ForegroundColor Yellow
    if (Get-Command winget -ErrorAction SilentlyContinue) {
        winget install --id=Gyan.FFmpeg -e --source winget --accept-package-agreements --accept-source-agreements
        if ($LASTEXITCODE -eq 0) {
            Write-Host "[OK] FFmpeg installation triggered. Note: You might need to restart your terminal for PATH changes." -ForegroundColor Green
        } else {
            Write-Host "[ERROR] winget installation failed. Please install FFmpeg manually." -ForegroundColor Red
        }
    } else {
        Write-Host "[ERROR] winget not found. Please install FFmpeg manually from https://ffmpeg.org/" -ForegroundColor Red
    }
}

# Step 1: Start Docker services
Write-Host "[1/4] Starting SurrealDB and Elyra..." -ForegroundColor Yellow
docker compose -f docker-compose.dev.yml up -d surrealdb elyra
if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] Failed to start Docker services. Is Docker Desktop running?" -ForegroundColor Red
    exit 1
}
Start-Sleep -Seconds 3

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

# Install dependencies if node_modules is missing
if (!(Test-Path "node_modules")) {
    Write-Host "Installing frontend dependencies..." -ForegroundColor Yellow
    if (Get-Command bun -ErrorAction SilentlyContinue) {
        bun install
    } else {
        npm install
    }
}

# Run dev server using bun if available, otherwise npm
if (Get-Command bun -ErrorAction SilentlyContinue) {
    bun run dev
} else {
    npm run dev
}
