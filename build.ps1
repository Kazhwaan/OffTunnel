# OffTunnel build script (Windows 10/11, PowerShell 5.1+)
# Builds a portable folder exe and a single-file exe with PyInstaller.
# Run from the repository root:
#   powershell -NoProfile -ExecutionPolicy Bypass -File .\build.ps1
# Requires: Python 3.12+ with tkinter, internet (first run, for PyInstaller).
# Building and testing never change Windows routes.

$ErrorActionPreference = "Stop"
$AppName = "OffTunnel"
$Version = "0.1.0"

if (-not (Get-Command py -ErrorAction SilentlyContinue)) {
    throw "Python launcher 'py' not found. Install Python 3.12+ with tkinter and re-run."
}

if (-not (Test-Path .venv)) {
    Write-Host "Creating virtual environment .venv ..."
    py -3 -m venv .venv
}
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements-build.txt

# Portable (folder) build
Write-Host "Building portable $AppName $Version ..."
pyinstaller --noconfirm --clean --noconsole --name $AppName `
    --add-data "data;data" `
    offtunnel.pyw

# Single-file build
Write-Host "Building single-file $AppName $Version ..."
pyinstaller --noconfirm --clean --noconsole --onefile --name $AppName `
    --add-data "data;data" `
    offtunnel.pyw

Write-Host ""
Write-Host "Done."
Write-Host "  Portable:    dist\$AppName\$AppName.exe"
Write-Host "  Single-file: dist\$AppName.exe  (starts more slowly)"
Write-Host "Run as Administrator to change Windows routes."
Write-Host "Tests: py -3 -m unittest discover -s tests -v"
