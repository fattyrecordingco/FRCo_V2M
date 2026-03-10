$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$repoRoot = Split-Path -Parent $PSScriptRoot
$frontendDir = Join-Path $repoRoot "frontend"
$tauriDir = Join-Path $frontendDir "src-tauri"
$releaseExe = Join-Path $tauriDir "target\release\vins-desktop.exe"
$releaseBackend = Join-Path $tauriDir "target\release\_up_\_up_\backend"
$msiDir = Join-Path $tauriDir "target\release\bundle\msi"
$installRoot = Join-Path $env:LOCALAPPDATA "Programs\VINS"
$installBackend = Join-Path $installRoot "_up_\_up_\backend"
$backupRoot = Join-Path $env:LOCALAPPDATA ("Programs\VINS_backup_{0}" -f (Get-Date -Format "yyyyMMdd_HHmmss"))

Write-Host "Building packaged desktop release..."
Push-Location $frontendDir
try {
  & cmd /c npx tauri build --bundles msi
} finally {
  Pop-Location
}

if (-not (Test-Path $releaseExe)) {
  throw "Missing desktop executable: $releaseExe"
}
if (-not (Test-Path $releaseBackend)) {
  throw "Missing built backend resources: $releaseBackend"
}

if (Test-Path $installRoot) {
  Write-Host "Backing up current install to $backupRoot"
  New-Item -ItemType Directory -Path $backupRoot | Out-Null
  & robocopy $installRoot $backupRoot /E /NFL /NDL /NJH /NJS /NP | Out-Null
}

Write-Host "Installing desktop executable by direct copy..."
New-Item -ItemType Directory -Force -Path $installRoot | Out-Null
Copy-Item $releaseExe (Join-Path $installRoot "vins-desktop.exe") -Force

Write-Host "Installing backend resources by direct copy..."
New-Item -ItemType Directory -Force -Path (Split-Path -Parent $installBackend) | Out-Null
& robocopy $releaseBackend $installBackend /MIR /NFL /NDL /NJH /NJS /NP | Out-Null
$robocopyExit = $LASTEXITCODE
if ($robocopyExit -gt 7) {
  throw "Robocopy failed with exit code $robocopyExit"
}

Write-Host "Installed VINS desktop build."
Write-Host "Desktop: $(Join-Path $installRoot 'vins-desktop.exe')"
if (Test-Path $msiDir) {
  $msiPath = Get-ChildItem $msiDir -Filter *.msi -File | Sort-Object LastWriteTime -Descending | Select-Object -First 1 -ExpandProperty FullName
  if ($msiPath) {
    Write-Host "MSI:     $msiPath"
  }
}
if (Test-Path $backupRoot) {
  Write-Host "Backup:  $backupRoot"
}
