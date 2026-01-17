# Build Windows EXE using PyInstaller
#
# This script creates a standalone Windows executable from your Python application.
# The resulting EXE can be distributed to Windows users without requiring Python installation.
#
# Usage:
#   .\quickstrap\scripts\build_windows_exe.ps1
#
# Requirements:
#   - PyInstaller must be installed in your virtual environment
#   - Run this after installing your application with python install.py
#
# Output:
#   - EXE file will be in dist\ directory
#   - Build artifacts in build\ directory

$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "======================================" -ForegroundColor Blue
Write-Host "  Windows EXE Build Script" -ForegroundColor Blue
Write-Host "======================================" -ForegroundColor Blue
Write-Host ""

# Find the script directory and project root
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = (Get-Item $ScriptDir).Parent.Parent.FullName
Set-Location $ProjectRoot

# Check if venv exists
if (-not (Test-Path "venv")) {
    Write-Host "✗ Error: Virtual environment not found" -ForegroundColor Red
    Write-Host ""
    Write-Host "Please run the installer first:"
    Write-Host "  python install.py"
    exit 1
}

# Activate virtual environment
$VenvActivate = "venv\Scripts\Activate.ps1"
if (Test-Path $VenvActivate) {
    & $VenvActivate
} else {
    Write-Host "✗ Error: Virtual environment activation script not found" -ForegroundColor Red
    exit 1
}

# Check if PyInstaller is installed
try {
    python -c "import PyInstaller" 2>$null
} catch {
    Write-Host "⚠ PyInstaller not found in virtual environment" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Installing PyInstaller..."
    pip install pyinstaller
    Write-Host ""
}

# Read configuration from installation_profiles.ini
$ConfigFile = "quickstrap\installation_profiles.ini"

if (-not (Test-Path $ConfigFile)) {
    Write-Host "✗ Error: Configuration file not found: $ConfigFile" -ForegroundColor Red
    exit 1
}

# Parse INI file using Python
$AppName = python -c @"
from configparser import ConfigParser
config = ConfigParser()
config.read('$ConfigFile')
print(config.get('metadata', 'app_name', fallback='Application'))
"@

$StartCommand = python -c @"
from configparser import ConfigParser
config = ConfigParser()
config.read('$ConfigFile')
print(config.get('metadata', 'start_command', fallback='python main.py'))
"@

# Extract main script from start_command
$MainScript = $StartCommand -replace '^python3?\s+', '' -split '\s+' | Select-Object -First 1

if (-not (Test-Path $MainScript)) {
    Write-Host "✗ Error: Main script not found: $MainScript" -ForegroundColor Red
    Write-Host ""
    Write-Host "Please verify the 'start_command' in $ConfigFile"
    Write-Host "Current start_command: $StartCommand"
    exit 1
}

Write-Host "✓ Configuration loaded" -ForegroundColor Green
Write-Host "  Application: $AppName"
Write-Host "  Main script: $MainScript"
Write-Host ""

# Check for PyInstaller spec file
$SpecFile = "quickstrap\pyinstaller.spec"

if (Test-Path $SpecFile) {
    Write-Host "ℹ Using existing PyInstaller spec file: $SpecFile" -ForegroundColor Cyan
    Write-Host ""

    # Build using spec file
    Write-Host "Building EXE with custom configuration..."
    pyinstaller --clean --noconfirm $SpecFile
} else {
    Write-Host "ℹ No spec file found, using automatic build" -ForegroundColor Cyan
    Write-Host ""

    # Auto-detect common patterns for additional data
    $AddDataArgs = @()

    # Check for common directories that should be included
    $CommonDirs = @('config', 'templates', 'static', 'data', 'resources')
    foreach ($dir in $CommonDirs) {
        if (Test-Path $dir) {
            Write-Host "✓ Found directory: $dir (will be included)" -ForegroundColor Green
            $AddDataArgs += "--add-data"
            $AddDataArgs += "$dir;$dir"
        }
    }

    # Check for icon file
    $IconArg = $null
    $IconFiles = @('app.ico', 'icon.ico', 'application.ico')
    foreach ($icon in $IconFiles) {
        if (Test-Path $icon) {
            Write-Host "✓ Found icon: $icon" -ForegroundColor Green
            $IconArg = "--icon=$icon"
            break
        }
    }

    Write-Host ""
    Write-Host "Building EXE..."

    # Build command
    $PyInstallerArgs = @(
        '--onefile',
        '--name', $AppName
    )

    if ($IconArg) {
        $PyInstallerArgs += $IconArg
    }

    $PyInstallerArgs += $AddDataArgs
    $PyInstallerArgs += $MainScript

    pyinstaller @PyInstallerArgs
}

# Check if build was successful
$ExeName = "$AppName.exe"
$ExePath = "dist\$ExeName"

if (Test-Path $ExePath) {
    Write-Host ""
    Write-Host "======================================" -ForegroundColor Blue
    Write-Host "✓ Build successful!" -ForegroundColor Green
    Write-Host "======================================" -ForegroundColor Blue
    Write-Host ""
    Write-Host "EXE location: dist\"
    Write-Host ""
    Get-ChildItem dist\*.exe | Format-Table Name, Length, LastWriteTime
    Write-Host ""
    Write-Host "You can now distribute the EXE to Windows users."
    Write-Host "No Python installation required on their systems."
    Write-Host ""
    Write-Host "Note: The EXE is platform-specific. For other platforms:"
    Write-Host "  - Linux: Run ./quickstrap/scripts/build_linux_binary.sh"
} else {
    Write-Host ""
    Write-Host "✗ Build failed" -ForegroundColor Red
    Write-Host ""
    Write-Host "Check the output above for errors."
    exit 1
}
