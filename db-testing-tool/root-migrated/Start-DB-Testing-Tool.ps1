$ErrorActionPreference = 'SilentlyContinue'

$appDir = 'C:\GIT_Repo\db-testing-tool'
$pyExe = 'C:\GIT_Repo\.venv\Scripts\python.exe'
$appUrl = 'http://127.0.0.1:8550/'

function Test-AppUp {
    try {
        $r = Invoke-WebRequest -Uri $appUrl -UseBasicParsing -TimeoutSec 2
        return ($r.StatusCode -eq 200)
    } catch {
        return $false
    }
}

if (Test-AppUp) {
    Start-Process $appUrl
    exit 0
}

Start-Process -FilePath $pyExe `
    -ArgumentList @('-m','uvicorn','app.main:app','--host','127.0.0.1','--port','8550','--reload','--app-dir',$appDir) `
    -WorkingDirectory $appDir `
    -WindowStyle Minimized

for ($i = 0; $i -lt 12; $i++) {
    Start-Sleep -Seconds 1
    if (Test-AppUp) { break }
}

if (Test-AppUp) {
    Start-Process $appUrl
    exit 0
}

Write-Host 'Failed to start DB Testing Tool on http://127.0.0.1:8550/'
exit 1
