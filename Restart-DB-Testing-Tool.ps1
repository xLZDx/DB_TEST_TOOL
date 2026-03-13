$ErrorActionPreference = 'SilentlyContinue'

$appDir = 'C:\GIT_Repo\db-testing-tool'
$pyExe = 'C:\GIT_Repo\.venv\Scripts\python.exe'
$appUrl = 'http://127.0.0.1:8550/'

Get-Process | Where-Object { $_.ProcessName -eq 'python' -or $_.ProcessName -eq 'uvicorn' } | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 1

Start-Process -FilePath $pyExe `
    -ArgumentList @('-m','uvicorn','app.main:app','--host','127.0.0.1','--port','8550','--reload','--app-dir',$appDir) `
    -WorkingDirectory $appDir `
    -WindowStyle Minimized

$started = $false
for ($i = 0; $i -lt 20; $i++) {
    Start-Sleep -Milliseconds 750
    try {
        $r = Invoke-WebRequest -Uri $appUrl -UseBasicParsing -TimeoutSec 2
        if ($r.StatusCode -eq 200) {
            $started = $true
            break
        }
    } catch {}
}

if ($started) {
    Start-Process $appUrl
    exit 0
}

Write-Host 'Failed to restart DB Testing Tool on http://127.0.0.1:8550/'
exit 1
