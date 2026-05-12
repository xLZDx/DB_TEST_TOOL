@echo off
setlocal

set "RESTART_PS1=C:\GIT_Repo\db-testing-tool\Restart-DB-Testing-Tool.ps1"
powershell -NoProfile -ExecutionPolicy Bypass -Command "& '%RESTART_PS1%'"
exit /b %errorlevel%

endlocal
