@echo off
setlocal

set "STARTER_PS1=C:\GIT_Repo\db-testing-tool\Start-DB-Testing-Tool.ps1"
powershell -NoProfile -ExecutionPolicy Bypass -File "%STARTER_PS1%"

endlocal
