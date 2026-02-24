param(
  [string]$PythonExe = "python",
  [string]$NodeExe = "npm"
)

$ErrorActionPreference = "Stop"

Write-Host "Installing backend dependencies..."
Push-Location backend
& $PythonExe -m pip install --upgrade pip
& $PythonExe -m pip install -e ".[dev]"
Pop-Location

Write-Host "Installing frontend dependencies..."
Push-Location frontend
& $NodeExe install
Pop-Location

Write-Host "Setup complete."

