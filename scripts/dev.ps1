$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

Write-Host "Starting local PostgreSQL mirror and backend..."
docker compose -f docker-compose.local.yml up -d postgres backend

Write-Host ""
Write-Host "Backend: http://localhost:8000"
Write-Host "Trips:   http://localhost:8000/api/trips"
Write-Host "Lines:   http://localhost:8000/api/lines/"
