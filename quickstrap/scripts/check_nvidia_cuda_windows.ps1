# VoiceSnip Windows NVIDIA CUDA Check
# Verifies NVIDIA drivers and CUDA availability for GPU-accelerated transcription

$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "======================================" -ForegroundColor Cyan
Write-Host "NVIDIA GPU & CUDA Requirements Check" -ForegroundColor Cyan
Write-Host "======================================" -ForegroundColor Cyan
Write-Host ""

# Check if nvidia-smi is available
Write-Host "Checking for NVIDIA drivers..." -ForegroundColor White

$nvidiaSmi = Get-Command nvidia-smi -ErrorAction SilentlyContinue

if (-not $nvidiaSmi) {
    Write-Host ""
    Write-Host "✗ Error: NVIDIA driver not found (nvidia-smi not available)" -ForegroundColor Red
    Write-Host ""
    Write-Host "The CUDA profile requires NVIDIA GPU drivers." -ForegroundColor Yellow
    Write-Host ""
    Write-Host "To install NVIDIA drivers:" -ForegroundColor White
    Write-Host "  1. Visit: https://www.nvidia.com/Download/index.aspx" -ForegroundColor White
    Write-Host "  2. Select your GPU model and Windows version" -ForegroundColor White
    Write-Host "  3. Download and install the latest Game Ready or Studio driver" -ForegroundColor White
    Write-Host "  4. Reboot your system" -ForegroundColor White
    Write-Host "  5. Verify installation with: nvidia-smi" -ForegroundColor White
    Write-Host ""
    Write-Host "Alternatively, install via GeForce Experience (for gaming GPUs)" -ForegroundColor White
    Write-Host ""
    exit 1
}

Write-Host "  ✓ nvidia-smi found: $($nvidiaSmi.Path)" -ForegroundColor Green
Write-Host ""

# Run nvidia-smi to check GPU accessibility
Write-Host "Querying GPU information..." -ForegroundColor White

try {
    $gpuInfo = nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv,noheader 2>&1

    if ($LASTEXITCODE -ne 0) {
        throw "nvidia-smi returned error code $LASTEXITCODE"
    }

    # Parse GPU information (supports multiple GPUs)
    $gpuLines = $gpuInfo -split "`n" | Where-Object { $_ -match '\S' }

    if ($gpuLines.Count -eq 0) {
        throw "No GPU information returned from nvidia-smi"
    }

    Write-Host ""
    Write-Host "✓ NVIDIA driver detected successfully!" -ForegroundColor Green
    Write-Host ""
    Write-Host "GPU Information:" -ForegroundColor Cyan
    Write-Host "--------------------------------------" -ForegroundColor Cyan

    $gpuCount = 0
    foreach ($line in $gpuLines) {
        $parts = $line -split ',\s*'
        if ($parts.Count -ge 3) {
            $gpuCount++
            Write-Host ""
            Write-Host "GPU #$($gpuCount):" -ForegroundColor White
            Write-Host "  Model:          $($parts[0].Trim())" -ForegroundColor White
            Write-Host "  Driver Version: $($parts[1].Trim())" -ForegroundColor White
            Write-Host "  GPU Memory:     $($parts[2].Trim())" -ForegroundColor White
        }
    }

    Write-Host ""
    Write-Host "--------------------------------------" -ForegroundColor Cyan
    Write-Host ""

    # Optional: Check CUDA version
    Write-Host "Checking CUDA version..." -ForegroundColor White
    $cudaVersion = nvidia-smi --query-gpu=compute_cap --format=csv,noheader 2>&1

    if ($LASTEXITCODE -eq 0) {
        $computeCap = ($cudaVersion -split "`n")[0].Trim()
        Write-Host "  ✓ Compute Capability: $computeCap" -ForegroundColor Green
        Write-Host ""
    }

    Write-Host "✓ CUDA requirements check passed!" -ForegroundColor Green
    Write-Host ""
    Write-Host "Your system is ready for GPU-accelerated transcription." -ForegroundColor Green
    Write-Host ""

    exit 0

} catch {
    Write-Host ""
    Write-Host "✗ Error: nvidia-smi found but unable to communicate with GPU" -ForegroundColor Red
    Write-Host ""
    Write-Host "Error details: $_" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "This may indicate:" -ForegroundColor Yellow
    Write-Host "  • Driver installation incomplete" -ForegroundColor White
    Write-Host "  • System needs a reboot" -ForegroundColor White
    Write-Host "  • GPU not properly detected by Windows" -ForegroundColor White
    Write-Host "  • Incompatible or corrupted driver installation" -ForegroundColor White
    Write-Host ""
    Write-Host "Recommended actions:" -ForegroundColor White
    Write-Host "  1. Reboot your system" -ForegroundColor White
    Write-Host "  2. Reinstall NVIDIA drivers from nvidia.com" -ForegroundColor White
    Write-Host "  3. Check Device Manager for GPU errors" -ForegroundColor White
    Write-Host ""
    exit 1
}
