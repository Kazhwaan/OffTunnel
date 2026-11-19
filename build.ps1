# OffTunnel build script (Windows 10/11, PowerShell 5.1+)
# Builds a portable folder exe and a single-file exe with PyInstaller.
# Run from the repository root:
#   powershell -NoProfile -ExecutionPolicy Bypass -File .\build.ps1
# Requires: Python 3.12+ with tkinter, internet (first run, for PyInstaller).
# Building and testing never change Windows routes.
#
# v0.1.1: the exe now embeds the app icon (assets/logo.ico) and
# requests Administrator at launch (--uac-admin, i.e. a
# requireAdministrator manifest). Without admin the app cannot
# change Windows routes, so the exe must ask for it up front
# instead of opening unprivileged and failing silently.

$ErrorActionPreference = "Stop"
$AppName = "OffTunnel"
$Version = "0.1.1"

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

# Binary icons are stored as base64 text in the repo (see
# scripts/generate_icons.py); decode them before building.
python scripts/generate_icons.py

$IconArgs = @()
if (Test-Path assets\logo.ico) { $IconArgs += "--icon", "assets\logo.ico" }

# Portable (folder) build
Write-Host "Building portable $AppName $Version ..."
pyinstaller --noconfirm --clean --noconsole --name $AppName --uac-admin `
    --add-data "data;data" --add-data "assets;assets" @IconArgs `
    offtunnel.pyw

# Single-file build
Write-Host "Building single-file $AppName $Version ..."
pyinstaller --noconfirm --clean --noconsole --onefile --name $AppName --uac-admin `
    --add-data "data;data" --add-data "assets;assets" @IconArgs `
    offtunnel.pyw

Write-Host ""
Write-Host "Done."
Write-Host "  Portable:    dist\$AppName\$AppName.exe"
Write-Host "  Single-file: dist\$AppName.exe  (starts more slowly)"
Write-Host "The exe requests Administrator (UAC) when you double-click it."
Write-Host "Tests: py -3 -m unittest discover -s tests -v"
