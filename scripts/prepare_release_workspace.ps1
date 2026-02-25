param(
  [string]$Root = (Resolve-Path (Join-Path $PSScriptRoot ".."))
)

$ErrorActionPreference = "Stop"
Set-Location $Root

Write-Host "Cleaning local cache/build folders..."
$pathsToRemove = @(
  ".pytest_cache",
  ".mypy_cache",
  ".ruff_cache",
  ".venv",
  "out",
  "frontend/src-tauri/target",
  "frontend/design-iterations"
)

foreach ($path in $pathsToRemove) {
  if (Test-Path $path) {
    Remove-Item -Recurse -Force $path
    Write-Host "Removed $path"
  }
}

Write-Host "Staging latest Windows installer..."
$releaseDir = Join-Path $Root "releases/windows"
New-Item -ItemType Directory -Force -Path $releaseDir | Out-Null

$msiCandidates = @()
if (Test-Path "frontend/src-tauri/target/release/bundle/msi") {
  $msiCandidates += Get-ChildItem "frontend/src-tauri/target/release/bundle/msi" -Filter *.msi -File
}
if (Test-Path "out/release") {
  $msiCandidates += Get-ChildItem "out/release" -Filter *.msi -File
}

if ($msiCandidates.Count -gt 0) {
  $latest = $msiCandidates | Sort-Object LastWriteTime -Descending | Select-Object -First 1
  Copy-Item -Force $latest.FullName $releaseDir
  Write-Host "Copied $($latest.Name) -> releases/windows"
}
else {
  Write-Warning "No MSI installers found. Build one first using: cd frontend; npx tauri build --bundles msi"
}

Write-Host "Workspace cleanup complete."
