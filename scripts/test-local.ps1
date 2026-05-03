$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

docker compose -f docker-compose.local.yml up -d postgres
docker compose -f docker-compose.local.yml run --rm backend python -m unittest discover tests
