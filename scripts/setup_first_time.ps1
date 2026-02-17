param(
    [switch]$RunTests = $true
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $projectRoot

if (-not (Test-Path ".venv")) {
    python -m venv .venv
}

. .\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e .[dev]

if ($RunTests) {
    pytest
}

Write-Host "Setup complete."
Write-Host "Run the app with: .\\scripts\\start_ui.ps1"
