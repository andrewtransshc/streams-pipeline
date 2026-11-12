# One-time setup for the Streams pipeline on Windows 10/11.
# Run from the Streams folder (PowerShell or Git Bash):
#   powershell -ExecutionPolicy Bypass -File setup-windows.ps1            (core: transcription + editing)
#   powershell -ExecutionPolicy Bypass -File setup-windows.ps1 -Extras    (also speaker detection + thumbnail cutouts)
# Installs Python 3.11 and ffmpeg with winget if they're missing (this accepts winget's package agreements).
param([switch]$Extras)
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
Write-Host "== Streams setup (Windows) =="

function Have($cmd) { $null -ne (Get-Command $cmd -ErrorAction SilentlyContinue) }
function Refresh-Path {
    $env:Path = [Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [Environment]::GetEnvironmentVariable("Path", "User")
}
function Winget-Install($id) {
    winget install --id $id -e --silent --accept-source-agreements --accept-package-agreements
    Refresh-Path
}

if (-not (Have winget)) {
    throw "winget was not found. Open the Microsoft Store, update 'App Installer', then run this script again."
}

if (-not (Have ffmpeg) -and -not (Test-Path "bin\ffmpeg.exe")) {
    Write-Host "Installing ffmpeg..."
    Winget-Install "Gyan.FFmpeg"
}

$py311 = $false
if (Have py) { & py -3.11 --version *> $null; $py311 = ($LASTEXITCODE -eq 0) }
if (-not $py311) {
    Write-Host "Installing Python 3.11..."
    Winget-Install "Python.Python.3.11"
}

# Python reads/writes UTF-8 by default (captions contain curly quotes and other non-ASCII characters)
[Environment]::SetEnvironmentVariable("PYTHONUTF8", "1", "User")
$env:PYTHONUTF8 = "1"

$hasNvidia = Have nvidia-smi
function Make-Venv($dir, $req) {
    if (-not (Test-Path $dir)) { & py -3.11 -m venv $dir }
    $python = Join-Path $dir "Scripts\python.exe"
    & $python -m pip install --upgrade pip -q
    if ($hasNvidia) {
        Write-Host "NVIDIA GPU found: installing the CUDA build of PyTorch (faster transcription)..."
        & $python -m pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu126
    }
    & $python -m pip install -r $req
}

Make-Venv ".venv" "requirements.txt"
if ($Extras) { Make-Venv ".venv-voice" "requirements-extras.txt" }

New-Item -ItemType Directory -Force -Path Raw, Ouput, work | Out-Null
Write-Host ""
& ".venv\Scripts\python.exe" check_setup.py
Write-Host ""
Write-Host "If ffmpeg or Python was just installed, restart the Claude app so it picks up the new PATH."
