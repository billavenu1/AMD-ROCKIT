Write-Host "🚀 Bootstrapping ARIA Development Environment..." -ForegroundColor Cyan

# 1. Start Docker Pull in the background
Write-Host "[1/3] Pulling Docker images in background..." -ForegroundColor Yellow
$dockerJob = Start-Process -FilePath "docker" -ArgumentList "compose -f docker-compose.dev.yml pull" -PassThru -NoNewWindow

# 2. Install Frontend Dependencies
Write-Host "[2/3] Installing frontend dependencies..." -ForegroundColor Yellow
Set-Location aria-frontend

if (Get-Command bun -ErrorAction SilentlyContinue) {
    Write-Host "      Using Bun (Superfast ⚡)" -ForegroundColor Green
    bun install
} else {
    Write-Host "      ⚠️ BUN NOT DETECTED! Falling back to npm (Slower 🐢)." -ForegroundColor Red
    Write-Host "      Highly recommend installing Bun for future speed: https://bun.sh/docs/installation" -ForegroundColor Yellow
    npm install
}
Set-Location ..

# Wait for docker pull to finish
Write-Host "      Waiting for Docker images to finish pulling..." -ForegroundColor Yellow
$dockerJob | Wait-Process

# 3. Sync backend dependencies
Write-Host "[3/3] Syncing Python dependencies (uv)..." -ForegroundColor Yellow
uv sync

Write-Host ""
Write-Host "✅ Setup Complete! All dependencies and images are ready." -ForegroundColor Green
Write-Host "👉 Run '.\dev.ps1' to start the application." -ForegroundColor Cyan
