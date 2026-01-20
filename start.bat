@echo off
:: Windows batch wrapper for start.ps1
:: Bypasses PowerShell execution policy to run the main startup script
powershell -ExecutionPolicy Bypass -File "%~dp0start.ps1" %*
