<#
.SYNOPSIS
    Stop all DB Testing Tool portable server processes.
#>

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$pythonExe = Join-Path $root 'python\python.exe'
$port = 8550

Write-Host "  Stopping DB Testing Tool on port $port..." -ForegroundColor Yellow

# Method 1: Kill processes by our embedded python path
Get-Process -Name 'python' -ErrorAction SilentlyContinue |
    Where-Object { $_.Path -and $_.Path -eq $pythonExe } |
    ForEach-Object {
        Write-Host "  Stopping PID $($_.Id)..." -ForegroundColor DarkGray
        Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue
    }

# Method 2: Kill anything listening on our port (fallback)
$listeners = Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue |
    Where-Object { $_.State -eq 'Listen' }

foreach ($l in $listeners) {
    $p = Get-Process -Id $l.OwningProcess -ErrorAction SilentlyContinue
    if ($p -and $p.Name -match 'python') {
        Write-Host "  Stopping PID $($p.Id) (port listener fallback)..." -ForegroundColor DarkGray
        Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue
    }
}

Write-Host "  Server stopped." -ForegroundColor Green
