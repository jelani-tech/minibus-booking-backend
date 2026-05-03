$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

Write-Host "Starting local PostgreSQL mirror..."
docker compose -f docker-compose.local.yml up -d postgres

Write-Host ""
Write-Host "DATABASE_URL=postgresql://user:password@localhost:5432/minibus_db"
Write-Host "If running Flask outside Docker, copy .env.development.example to .env.development and run:"
Write-Host '$env:APP_ENV="development"; python app.py'
