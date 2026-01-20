# VoiceSnip Windows System Check
# Verifies Python version and optional components for VoiceSnip installation

$ErrorActionPreference = "SilentlyContinue"

Write-Host "Checking VoiceSnip system requirements on Windows..." -ForegroundColor Cyan
Write-Host ""

$installed = @()
$missing = @()
$warnings = @()

# Check Python version (REQUIRED)
Write-Host "Checking Python installation..." -ForegroundColor White

# Try 'python' first, then 'py' (Windows Python Launcher)
$pythonCmd = $null
$pythonVersion = python --version 2>&1
if ($pythonVersion -match "Python") {
    $pythonCmd = "python"
} else {
    $pythonVersion = py --version 2>&1
    if ($pythonVersion -match "Python") {
        $pythonCmd = "py"
    }
}

if ($pythonVersion -match "Python (\d+)\.(\d+)\.(\d+)") {
    $major = [int]$Matches[1]
    $minor = [int]$Matches[2]
    $patch = [int]$Matches[3]

    if ($major -eq 3 -and $minor -ge 8) {
        Write-Host "  [OK] Python $major.$minor.$patch" -ForegroundColor Green
        $installed += "Python $major.$minor.$patch (required: Python 3.8+)"
    } else {
        Write-Host "  [X] Python $major.$minor.$patch (too old)" -ForegroundColor Red
        $missing += "Python 3.8+ (found: Python $major.$minor.$patch)"
    }
} else {
    Write-Host "  [X] Python not found or not in PATH" -ForegroundColor Red
    $missing += "Python 3.8+"
}

# Check for Visual C++ Redistributables (OPTIONAL - helpful for native extensions)
Write-Host "Checking Visual C++ Redistributables (optional)..." -ForegroundColor White

$vcRedist = Get-ItemProperty "HKLM:\Software\Microsoft\VisualStudio\*\VC\Runtimes\*" -ErrorAction SilentlyContinue
if ($vcRedist) {
    Write-Host "  [OK] Visual C++ Redistributables found" -ForegroundColor Green
    $installed += "Visual C++ Redistributables (optional - improves native extensions)"
} else {
    Write-Host "  [!] Visual C++ Redistributables not found (optional)" -ForegroundColor Yellow
    $warnings += "Visual C++ Redistributables recommended for optimal performance"
    $warnings += "  Download from: https://learn.microsoft.com/en-us/cpp/windows/latest-supported-vc-redist"
}

# Check for pip (REQUIRED for Python package installation)
Write-Host "Checking pip..." -ForegroundColor White
if ($pythonCmd) {
    $pipVersion = & $pythonCmd -m pip --version 2>&1
} else {
    $pipVersion = $null
}

if ($pipVersion -match "pip (\d+\.\d+\.\d+)") {
    Write-Host "  [OK] pip $($Matches[1])" -ForegroundColor Green
    $installed += "pip $($Matches[1])"
} else {
    Write-Host "  [X] pip not found" -ForegroundColor Red
    $missing += "pip (Python package manager)"
}

# Summary
Write-Host ""
Write-Host "======================================" -ForegroundColor Cyan
Write-Host "System Check Summary" -ForegroundColor Cyan
Write-Host "======================================" -ForegroundColor Cyan

if ($installed.Count -gt 0) {
    Write-Host ""
    Write-Host "Installed Requirements:" -ForegroundColor Green
    foreach ($item in $installed) {
        Write-Host "  [OK] $item" -ForegroundColor Green
    }
}

if ($warnings.Count -gt 0) {
    Write-Host ""
    Write-Host "Optional Components (Warnings):" -ForegroundColor Yellow
    foreach ($warning in $warnings) {
        Write-Host "  [!] $warning" -ForegroundColor Yellow
    }
}

if ($missing.Count -gt 0) {
    Write-Host ""
    Write-Host "Missing Requirements:" -ForegroundColor Red
    foreach ($item in $missing) {
        Write-Host "  [X] $item" -ForegroundColor Red
    }
    Write-Host ""
    Write-Host "Please install missing requirements before continuing." -ForegroundColor Red
    Write-Host ""
    exit 1
}

Write-Host ""
Write-Host "[OK] All required components are installed!" -ForegroundColor Green
Write-Host ""

exit 0
