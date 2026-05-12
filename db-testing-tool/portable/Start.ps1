<#
.SYNOPSIS
    Start DB Testing Tool from the portable folder.
.DESCRIPTION
    Uses the embedded Python in the python/ subfolder.
    No system Python or admin rights required.
#>
[CmdletBinding()]
param(
    [int]$Port = 8550,
    [switch]$NoBrowser
)

$ErrorActionPreference = 'Stop'

$root      = Split-Path -Parent $MyInvocation.MyCommand.Path
$pythonExe = Join-Path $root 'python\python.exe'
$runPy     = Join-Path $root 'run.py'
$logDir    = Join-Path $root 'logs'
$appUrl    = "http://127.0.0.1:$Port"

# Validate prerequisites
if (-not (Test-Path $pythonExe)) {
    Write-Host "`n  ERROR: Embedded Python not found at $pythonExe" -ForegroundColor Red
    Write-Host "  Make sure you run this from the portable folder.`n" -ForegroundColor Red
    exit 1
}

# Set portable environment variables
$env:DB_TESTING_TOOL_DATA_DIR = Join-Path $root 'data'
$env:DB_TESTING_TOOL_ENV      = 'portable'

# Ensure directories exist
New-Item -ItemType Directory -Path $logDir -Force | Out-Null
New-Item -ItemType Directory -Path (Join-Path $root 'data') -Force | Out-Null

# Check if already running
function Test-ServerUp {
    try {
        $r = Invoke-WebRequest -Uri $appUrl -UseBasicParsing -TimeoutSec 2
        return ($r.StatusCode -eq 200)
    } catch { return $false }
}

if (Test-ServerUp) {
    Write-Host "`n  DB Testing Tool is already running at $appUrl" -ForegroundColor Yellow
    if (-not $NoBrowser) { Start-Process $appUrl }
    exit 0
}

Write-Host ""
Write-Host "  ══════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "   DB Testing Tool - Portable Edition" -ForegroundColor Cyan
Write-Host "   Starting on $appUrl ..." -ForegroundColor Cyan
Write-Host "  ══════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host ""

# Override port in run.py via environment variable
$env:DBTOOL_PORT = $Port

# Launch server process (minimised)
$stdOut = Join-Path $logDir 'db-testing-tool.log'
$stdErr = Join-Path $logDir 'db-testing-tool.err.log'

$proc = Start-Process -FilePath $pythonExe `
    -ArgumentList @('-u', $runPy) `
    -WorkingDirectory $root `
    -WindowStyle Minimized `
    -RedirectStandardOutput $stdOut `
    -RedirectStandardError  $stdErr `
    -PassThru

# Wait for startup (max 30 seconds)
$waited = 0
while ($waited -lt 30) {
    Start-Sleep -Seconds 1
    $waited++
    if (Test-ServerUp) {
        Write-Host "  Server started in ${waited}s (PID: $($proc.Id))" -ForegroundColor Green
        if (-not $NoBrowser) {
            Start-Process $appUrl
        }
        Write-Host "  Logs: $stdOut" -ForegroundColor DarkGray
        Write-Host "  To stop: run Stop.bat or Stop.ps1`n" -ForegroundColor DarkGray
        exit 0
    }
    Write-Host "  Waiting for server... (${waited}s)" -ForegroundColor DarkGray
}

Write-Host "`n  Server did not start within 30s. Check logs:`n   $stdErr" -ForegroundColor Red
exit 1
