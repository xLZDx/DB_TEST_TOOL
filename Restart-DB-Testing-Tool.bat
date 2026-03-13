@echo off
setlocal

set "RESTART_PS1=C:\GIT_Repo\db-testing-tool\Restart-DB-Testing-Tool.ps1"
powershell -NoProfile -ExecutionPolicy Bypass -File "%RESTART_PS1%"

endlocal
