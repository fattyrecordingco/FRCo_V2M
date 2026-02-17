$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $projectRoot

if (-not (Test-Path ".venv")) {
    Write-Host "Missing .venv. Run .\\scripts\\setup_first_time.ps1 first."
    exit 1
}

. .\.venv\Scripts\Activate.ps1
$env:STREAMLIT_SUPPRESS_EMAIL_PROMPT = "true"
$env:STREAMLIT_BROWSER_GATHER_USAGE_STATS = "false"
python -m streamlit run src/v2m/ui_app.py --server.headless true --server.port 8501 --browser.gatherUsageStats false
