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

Write-Host "Staging latest installer bundles..."
$releaseDir = Join-Path $Root "releases/windows"
$macReleaseDir = Join-Path $Root "releases/macos"
New-Item -ItemType Directory -Force -Path $releaseDir | Out-Null
New-Item -ItemType Directory -Force -Path $macReleaseDir | Out-Null

$msiCandidates = @()
if (Test-Path "frontend/src-tauri/target/release/bundle/msi") {
  $msiCandidates += Get-ChildItem "frontend/src-tauri/target/release/bundle/msi" -Filter *.msi -File
}
if (Test-Path "out/release") {
  $msiCandidates += Get-ChildItem "out/release" -Filter *.msi -File
}

if ($msiCandidates.Count -gt 0) {
  Get-ChildItem $releaseDir -Filter *.msi -File -ErrorAction SilentlyContinue | Remove-Item -Force
  $latest = $msiCandidates | Sort-Object LastWriteTime -Descending | Select-Object -First 1
  Copy-Item -Force $latest.FullName $releaseDir
  Write-Host "Copied $($latest.Name) -> releases/windows"
}
else {
  Write-Warning "No MSI installers found. Build one first using: cd frontend; npx tauri build --bundles msi"
}

$dmgCandidates = @()
$zipCandidates = @()
if (Test-Path "frontend/src-tauri/target/release/bundle/dmg") {
  $dmgCandidates += Get-ChildItem "frontend/src-tauri/target/release/bundle/dmg" -Filter *.dmg -File
}
if (Test-Path "frontend/src-tauri/target/release/bundle/macos-zip") {
  $zipCandidates += Get-ChildItem "frontend/src-tauri/target/release/bundle/macos-zip" -Filter *.zip -File
}
if (Test-Path "out/release") {
  $dmgCandidates += Get-ChildItem "out/release" -Filter *.dmg -File
  $zipCandidates += Get-ChildItem "out/release" -Filter *.zip -File
}

Get-ChildItem $macReleaseDir -File -ErrorAction SilentlyContinue |
  Where-Object { $_.Extension -in @(".dmg", ".zip") } |
  Remove-Item -Force

if ($dmgCandidates.Count -gt 0) {
  $latestDmg = $dmgCandidates | Sort-Object LastWriteTime -Descending | Select-Object -First 1
  Copy-Item -Force $latestDmg.FullName $macReleaseDir
  Write-Host "Copied $($latestDmg.Name) -> releases/macos"
}
else {
  Write-Warning "No DMG installers found. Build one on macOS: cd frontend; npx tauri build --bundles app,dmg"
}

if ($zipCandidates.Count -gt 0) {
  $latestZip = $zipCandidates | Sort-Object LastWriteTime -Descending | Select-Object -First 1
  Copy-Item -Force $latestZip.FullName $macReleaseDir
  Write-Host "Copied $($latestZip.Name) -> releases/macos"
}
else {
  Write-Warning "No macOS app ZIP found. If needed, zip the .app bundle from frontend/src-tauri/target/release/bundle/macos"
}

Write-Host "Workspace cleanup complete."
