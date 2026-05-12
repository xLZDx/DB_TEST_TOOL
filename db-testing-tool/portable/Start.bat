@echo off
:: ═══════════════════════════════════════════════════════════
::  DB Testing Tool - Portable Launcher
::  Double-click this file to start the application.
::  No Python installation or admin rights required.
:: ═══════════════════════════════════════════════════════════
setlocal

set "ROOT=%~dp0"
set "PYTHON=%ROOT%python\python.exe"
set "PORT=8550"
set "URL=http://127.0.0.1:%PORT%"

:: Ensure we're running from the portable folder
if not exist "%PYTHON%" (
    echo.
    echo  ERROR: Embedded Python not found at %PYTHON%
    echo  Make sure you run Start.bat from the portable folder.
    echo.
    pause
    exit /b 1
)

:: Set environment so the app stores data in the portable folder
set "DB_TESTING_TOOL_DATA_DIR=%ROOT%data"
set "DB_TESTING_TOOL_ENV=portable"

:: Create logs directory if missing
if not exist "%ROOT%logs" mkdir "%ROOT%logs"

:: Check if already running
powershell -NoProfile -Command "try { $r = Invoke-WebRequest -Uri '%URL%' -UseBasicParsing -TimeoutSec 2; if($r.StatusCode -eq 200) { exit 0 } else { exit 1 } } catch { exit 1 }" >nul 2>&1
if %ERRORLEVEL% == 0 (
    echo  DB Testing Tool is already running at %URL%
    start "" "%URL%"
    timeout /t 3
    exit /b 0
)

echo.
echo  ══════════════════════════════════════════════════
echo   DB Testing Tool - Portable Edition
echo   Starting on %URL% ...
echo  ══════════════════════════════════════════════════
echo.

:: Launch the server in a minimised window
start "DB Testing Tool" /MIN "%PYTHON%" -u "%ROOT%run.py"

:: Wait for the server to come up (max 30 seconds)
set /a TRIES=0
:WAITLOOP
if %TRIES% GEQ 30 (
    echo.
    echo  Server did not start within 30 seconds.
    echo  Check logs\db-testing-tool.log for errors.
    pause
    exit /b 1
)
timeout /t 1 /nobreak >nul
set /a TRIES+=1

powershell -NoProfile -Command "try { $r = Invoke-WebRequest -Uri '%URL%' -UseBasicParsing -TimeoutSec 2; if($r.StatusCode -eq 200) { exit 0 } else { exit 1 } } catch { exit 1 }" >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo  Waiting for server... (%TRIES%s^)
    goto WAITLOOP
)

echo.
echo  Server is running! Opening browser...
start "" "%URL%"

echo.
echo  To stop the server, run Stop.bat or close the minimised window.
echo.
timeout /t 5

endlocal
