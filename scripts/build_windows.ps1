$ErrorActionPreference = "Stop"

$RootDir = Split-Path -Parent $PSScriptRoot
$VenvDir = Join-Path $RootDir ".venv"
Set-Location $RootDir

if (-not (Test-Path (Join-Path $VenvDir "Scripts\\python.exe"))) {
    python -m venv $VenvDir
}

$PythonExe = Join-Path $VenvDir "Scripts\\python.exe"

& $PythonExe -m pip install -r requirements.txt pyinstaller
& $PythonExe -m PyInstaller --noconfirm --clean work_tracker.spec

Write-Host "Windows bundle ready in: $RootDir\\dist\\WorkTracker"
