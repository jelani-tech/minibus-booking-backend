param (
    [Parameter(Position=0)]
    [ValidateSet("expire-bookings", "wallet-audit")]
    [string]$Task = "expire-bookings"
)

$ErrorActionPreference = "Stop"
$timestamp = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")

$pythonBin = "python"
if (Test-Path "$PSScriptRoot\..\.venv\Scripts\python.exe") {
    $pythonBin = "$PSScriptRoot\..\.venv\Scripts\python.exe"
}

switch ($Task) {
    "expire-bookings" {
        Write-Host "[$timestamp] Running expire-bookings..."
        & $pythonBin -m flask --app app expire-bookings
    }
    "wallet-audit" {
        Write-Host "[$timestamp] Running wallet-audit..."
        & $pythonBin -m flask --app app wallet-audit --expire-stale-topups
    }
}
