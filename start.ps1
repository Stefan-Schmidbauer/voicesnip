# Quickstrap - Generic Application Starter (Windows)
# Reads configuration from quickstrap/installation_profiles.ini

$ErrorActionPreference = "Stop"

# Function to read INI file values using Python (guaranteed available)
function Read-IniValue {
    param (
        [string]$File,
        [string]$Section,
        [string]$Key,
        [string]$Default = ""
    )

    $pythonCode = @"
from configparser import ConfigParser
config = ConfigParser()
config.read('$File')
print(config.get('$Section', '$Key', fallback='$Default'))
"@

    # Try 'python' first, then 'py' (Windows Python Launcher)
    try {
        $result = python -c $pythonCode 2>$null
        if ($LASTEXITCODE -eq 0 -and $result) {
            return $result.Trim()
        }
    }
    catch {}

    try {
        $result = py -c $pythonCode 2>$null
        if ($LASTEXITCODE -eq 0 -and $result) {
            return $result.Trim()
        }
    }
    catch {}

    return $Default
}

# Find the script directory and change to it
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

# Parse quickstrap/installation_profiles.ini
$AppName = Read-IniValue -File "quickstrap/installation_profiles.ini" -Section "metadata" -Key "app_name" -Default "Application"
$StartCmd = Read-IniValue -File "quickstrap/installation_profiles.ini" -Section "metadata" -Key "start_command" -Default "python main.py"

# App name lowercase for config filename
$AppNameLower = $AppName.ToLower()

# Convert python3 to python for Windows (python3 is not standard on Windows)
# After venv activation, 'python' should work from venv Scripts folder
$StartCmd = $StartCmd -replace "^python3\s", "python "
$StartCmd = $StartCmd -replace "\spython3\s", " python "

# Check if virtual environment exists
$VenvPath = Join-Path $ScriptDir "venv"
if (-not (Test-Path $VenvPath)) {
    Write-Host "Error: Virtual environment not found for $AppName." -ForegroundColor Red
    Write-Host ""
    Write-Host "Please run the installer first:"
    Write-Host "  python install.py"
    Write-Host ""
    exit 1
}

# Check if installation config exists (in project directory)
$ConfigFile = Join-Path $ScriptDir "${AppNameLower}_profile.ini"
if (-not (Test-Path $ConfigFile)) {
    Write-Host "Error: Installation configuration not found." -ForegroundColor Red
    Write-Host ""
    Write-Host "$AppName needs to be installed before use."
    Write-Host "Please run the installer:"
    Write-Host "  python install.py"
    Write-Host ""
    exit 1
}

# Activate virtual environment
$VenvActivate = Join-Path (Join-Path $VenvPath "Scripts") "Activate.ps1"
if (Test-Path $VenvActivate) {
    & $VenvActivate
}
else {
    Write-Host "Error: Virtual environment activation script not found." -ForegroundColor Red
    Write-Host "Expected: $VenvActivate"
    exit 1
}

# Start application with all provided arguments
Write-Host "Starting $AppName..." -ForegroundColor Green

# Parse the start command and execute with arguments
$cmdParts = $StartCmd -split '\s+', 2
$executable = $cmdParts[0]
$cmdArgs = if ($cmdParts.Length -gt 1) { $cmdParts[1] } else { "" }

# Combine command arguments with script arguments
if ($args.Length -gt 0) {
    $allArgs = "$cmdArgs $($args -join ' ')"
}
else {
    $allArgs = $cmdArgs
}

# Execute the start command
if ($allArgs) {
    Invoke-Expression "$executable $allArgs"
}
else {
    & $executable
}
