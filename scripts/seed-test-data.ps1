$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host " Injection du jeu de données de tests (JELANI Backend & Mobile)" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

docker exec -i minibus_local_db psql -U user -d minibus_db -f /docker-entrypoint-initdb.d/03_test_dataset.sql

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host " Jeu de données injecté avec succès !" -ForegroundColor Green
    Write-Host " Comptes de tests disponibles (Mot de passe universel : Password123!) :" -ForegroundColor Yellow
    Write-Host "   - Client Principal (+ solde 50 000 FCFA) : +2250101010101 (Jean Kouassi)" -ForegroundColor White
    Write-Host "   - Client Sans Solde (0 FCFA)             : +2250202020202 (Marie Amani)" -ForegroundColor White
    Write-Host "   - Opérateur Contrôleur / Scanner Billet  : +2250303030303 (Seydou Contrôleur)" -ForegroundColor White
} else {
    Write-Host " Erreur lors de l'injection du jeu de données." -ForegroundColor Red
}
