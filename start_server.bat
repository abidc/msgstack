@echo off
cd /d C:\Users\Abid\msgstack-mcp
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1

:loop
venv\Scripts\python.exe run_server.py >> logs\server.log 2>&1
echo Server exited, restarting in 5 seconds... >> logs\server.log
timeout /t 5 /nobreak >nul
goto loop
