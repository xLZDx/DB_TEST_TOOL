@echo off
:: Launcher for timezone_adjuster.py - requests admin elevation automatically
:: Create a shortcut to this file for easy access

:: Check for admin privileges
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo Requesting administrator privileges...
    powershell -Command "Start-Process '%~f0' -Verb RunAs"
    exit /b
)

:: Run the Python script from the same directory as this batch file
cd /d "%~dp0"
python "%~dp0timezone_adjuster.py"
pause
