param(
  [string]$PythonExe = "python",
  [string]$NodeExe = "npm"
)

$ErrorActionPreference = "Stop"

$backend = Start-Process -PassThru -NoNewWindow powershell -ArgumentList @(
  "-NoProfile",
  "-Command",
  "Set-Location '$PSScriptRoot\\..\\backend'; $PythonExe -m uvicorn app.main:app --host 127.0.0.1 --port 8000"
)

try {
  Set-Location "$PSScriptRoot\..\frontend"
  & $NodeExe run dev
}
finally {
  if ($backend -and -not $backend.HasExited) {
    Stop-Process -Id $backend.Id -Force
  }
}

