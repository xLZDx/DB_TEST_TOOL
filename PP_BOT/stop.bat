@echo off
setlocal
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":8001" ^| findstr "LISTENING"') do (
  taskkill /PID %%p /F
)
endlocal
