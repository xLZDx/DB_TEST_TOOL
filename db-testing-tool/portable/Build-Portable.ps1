<#
.SYNOPSIS
    Builds a portable, zero-install Windows distribution of DB Testing Tool.

.DESCRIPTION
    Downloads Python 3.11 embeddable package, installs pip + dependencies,
    copies application code, and produces a ready-to-run portable folder.

    The output folder can be copied to any Windows machine and launched
    by double-clicking Start.bat — no Python installation or admin rights needed.

.PARAMETER OutputDir
    Path for the output portable folder. Default: .\dist\DB-Testing-Tool-Portable

.PARAMETER PythonVersion
    Embedded Python version to download. Default: 3.11.9

.PARAMETER SkipDownload
    Skip downloading Python if the zip already exists in the temp cache.

.EXAMPLE
    .\Build-Portable.ps1
    .\Build-Portable.ps1 -OutputDir "C:\MyPortable" -PythonVersion "3.11.9"
#>

[CmdletBinding()]
param(
    [string]$OutputDir = (Join-Path $PSScriptRoot 'dist\DB-Testing-Tool-Portable'),
    [string]$PythonVersion = '3.11.9',
    [switch]$SkipDownload
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$repoRoot = Split-Path -Parent $PSScriptRoot   # parent of portable/ = repo root
$cacheDir = Join-Path $PSScriptRoot '.cache'
$pythonZip = "python-$PythonVersion-embed-amd64.zip"
$pythonUrl = "https://www.python.org/ftp/python/$PythonVersion/$pythonZip"
$getPipUrl = "https://bootstrap.pypa.io/get-pip.py"

# ── Helpers ──────────────────────────────────────────────────────────────────
function Write-Step([string]$msg) {
    Write-Host "`n►  $msg" -ForegroundColor Cyan
}

function Assert-ExitCode([string]$action) {
    if ($LASTEXITCODE -and $LASTEXITCODE -ne 0) {
        throw "$action failed with exit code $LASTEXITCODE"
    }
}

# ── 0. Clean previous build ─────────────────────────────────────────────────
if (Test-Path $OutputDir) {
    Write-Step "Removing previous build at $OutputDir"
    Remove-Item -Recurse -Force $OutputDir
}
New-Item -ItemType Directory -Path $OutputDir -Force | Out-Null
New-Item -ItemType Directory -Path $cacheDir -Force | Out-Null

# ── 1. Download Python embeddable package ────────────────────────────────────
$cachedZip = Join-Path $cacheDir $pythonZip
if ($SkipDownload -and (Test-Path $cachedZip)) {
    Write-Step "Using cached Python embeddable: $cachedZip"
} else {
    Write-Step "Downloading Python $PythonVersion embeddable package..."
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    Invoke-WebRequest -Uri $pythonUrl -OutFile $cachedZip -UseBasicParsing
    Write-Host "   Downloaded: $cachedZip"
}

# ── 2. Extract Python to output/python ───────────────────────────────────────
$pythonDir = Join-Path $OutputDir 'python'
Write-Step "Extracting Python to $pythonDir"
Expand-Archive -Path $cachedZip -DestinationPath $pythonDir -Force

# ── 3. Enable pip in embeddable Python ───────────────────────────────────────
#    The embeddable distribution ships with a ._pth file that restricts imports.
#    We need to uncomment "import site" so pip/setuptools work.
Write-Step "Configuring embedded Python for pip support"
$pthFile = Get-ChildItem -Path $pythonDir -Filter 'python*._pth' | Select-Object -First 1
if (-not $pthFile) { throw "Could not find ._pth file in $pythonDir" }

$pthContent = Get-Content $pthFile.FullName -Raw
# Uncomment "import site" line
$pthContent = $pthContent -replace '#\s*import site', 'import site'
# Add Lib\site-packages so pip-installed packages are importable
if ($pthContent -notmatch 'Lib\\site-packages') {
    $pthContent += "`nLib\site-packages`n"
}
# Add parent directory (..) so the app/ package is importable from the portable root
if ($pthContent -notmatch '^\.\.$') {
    $pthContent += "`n..`n"
}
Set-Content -Path $pthFile.FullName -Value $pthContent -NoNewline

# ── 4. Install pip ───────────────────────────────────────────────────────────
$getPipPath = Join-Path $cacheDir 'get-pip.py'
if (-not (Test-Path $getPipPath)) {
    Write-Step "Downloading get-pip.py..."
    Invoke-WebRequest -Uri $getPipUrl -OutFile $getPipPath -UseBasicParsing
}

$pythonExe = Join-Path $pythonDir 'python.exe'
Write-Step "Installing pip into embedded Python"
& $pythonExe $getPipPath --no-warn-script-location 2>&1 | Write-Host
Assert-ExitCode "pip installation"

# ── 5. Install application dependencies ──────────────────────────────────────
$reqFile = Join-Path $repoRoot 'requirements.txt'
Write-Step "Installing dependencies from $reqFile"
& $pythonExe -m pip install --no-warn-script-location -r $reqFile 2>&1 | Write-Host
Assert-ExitCode "pip install requirements"

# ── 6. Copy application code ────────────────────────────────────────────────
Write-Step "Copying application code"

# Copy app/ directory
$appSrc = Join-Path $repoRoot 'app'
$appDst = Join-Path $OutputDir 'app'
Copy-Item -Path $appSrc -Destination $appDst -Recurse -Force
# Remove __pycache__ directories
Get-ChildItem -Path $appDst -Recurse -Directory -Filter '__pycache__' |
    Remove-Item -Recurse -Force -ErrorAction SilentlyContinue

# Copy run.py
Copy-Item -Path (Join-Path $repoRoot 'run.py') -Destination $OutputDir

# Copy data/ templates (not the user's DB)
$dataSrc = Join-Path $repoRoot 'data'
$dataDst = Join-Path $OutputDir 'data'
New-Item -ItemType Directory -Path $dataDst -Force | Out-Null
Get-ChildItem -Path $dataSrc -Filter '*.xlsx' | ForEach-Object {
    Copy-Item $_.FullName -Destination $dataDst
}
# Create empty local_kb folder
New-Item -ItemType Directory -Path (Join-Path $dataDst 'local_kb') -Force | Out-Null

# Copy JDBC drivers if present
$jdbcSrc = Join-Path $repoRoot 'redshift-jdbc42-2.1.0.32'
if (Test-Path $jdbcSrc) {
    Copy-Item -Path $jdbcSrc -Destination (Join-Path $OutputDir 'redshift-jdbc42-2.1.0.32') -Recurse
}

# Copy certs folder if present
$certsSrc = Join-Path $repoRoot 'certs'
if (Test-Path $certsSrc) {
    Copy-Item -Path $certsSrc -Destination (Join-Path $OutputDir 'certs') -Recurse
}

# Create logs dir
New-Item -ItemType Directory -Path (Join-Path $OutputDir 'logs') -Force | Out-Null

# Create reports dir
New-Item -ItemType Directory -Path (Join-Path $OutputDir 'reports') -Force | Out-Null

# ── 7. Copy launcher scripts ────────────────────────────────────────────────
Write-Step "Copying launcher scripts"
$launcherDir = $PSScriptRoot   # portable/ folder in source

Copy-Item (Join-Path $launcherDir 'Start.bat')          -Destination $OutputDir
Copy-Item (Join-Path $launcherDir 'Start.ps1')          -Destination $OutputDir
Copy-Item (Join-Path $launcherDir 'Stop.bat')           -Destination $OutputDir
Copy-Item (Join-Path $launcherDir 'Stop.ps1')           -Destination $OutputDir

# ── 8. Create .env template ─────────────────────────────────────────────────
$envExample = Join-Path $repoRoot '.env.example'
$envDst = Join-Path $OutputDir '.env'
if (Test-Path $envExample) {
    Copy-Item $envExample -Destination $envDst
} else {
    # Create minimal .env
    @"
# DB Testing Tool - Portable Configuration
# ─────────────────────────────────────────
# Uncomment and set values as needed.

# AI_PROVIDER=githubcopilot
# GITHUBCOPILOT_BASE_URL=https://api.githubcopilot.com
# GITHUBCOPILOT_MODEL=gpt-5mini
# GITHUB_OAUTH_CLIENT_ID=

# TFS_BASE_URL=
# TFS_PAT=
# TFS_PROJECT=
# TFS_COLLECTION=DefaultCollection

# DATASOURCES_JSON=[]
"@ | Set-Content -Path $envDst
}

# ── 9. Copy README ──────────────────────────────────────────────────────────
Copy-Item (Join-Path $launcherDir 'README.txt') -Destination $OutputDir

# ── 10. Write version marker ────────────────────────────────────────────────
$buildInfo = @"
DB Testing Tool - Portable Build
Built: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')
Python: $PythonVersion
Source: $repoRoot
"@
Set-Content -Path (Join-Path $OutputDir 'BUILD_INFO.txt') -Value $buildInfo

# ── Done ─────────────────────────────────────────────────────────────────────
$sizeBytes = (Get-ChildItem -Path $OutputDir -Recurse | Measure-Object -Property Length -Sum).Sum
$sizeMb = [math]::Round($sizeBytes / 1MB, 1)

Write-Host "`n" -NoNewline
Write-Host "════════════════════════════════════════════════════════════" -ForegroundColor Green
Write-Host "  Portable build complete!" -ForegroundColor Green
Write-Host "  Location : $OutputDir" -ForegroundColor Green
Write-Host "  Size     : $sizeMb MB" -ForegroundColor Green
Write-Host "  To run   : Double-click Start.bat in the output folder" -ForegroundColor Green
Write-Host "════════════════════════════════════════════════════════════" -ForegroundColor Green
