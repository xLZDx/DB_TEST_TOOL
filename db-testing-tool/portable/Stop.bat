@echo off
:: ═══════════════════════════════════════════════════════════
::  DB Testing Tool - Stop Server
:: ═══════════════════════════════════════════════════════════
setlocal

set "ROOT=%~dp0"

echo.
echo  Stopping DB Testing Tool...

:: Kill python processes started from our portable folder
powershell -NoProfile -ExecutionPolicy Bypass -File "%ROOT%Stop.ps1"

echo.
echo  Done.
timeout /t 3

endlocal
