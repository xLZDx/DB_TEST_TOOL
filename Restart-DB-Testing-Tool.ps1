$delegateScript = 'C:\GIT_Repo\db-testing-tool\Restart-DB-Testing-Tool.ps1'

if (-not (Test-Path $delegateScript)) {
    Write-Error "Delegate restart script not found: $delegateScript"
    exit 1
}

& $delegateScript
exit $LASTEXITCODE
