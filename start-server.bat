@echo off
REM MsgStack MCP Server Startup Script

cd /d "%~dp0"

echo Starting MsgStack MCP Server on http://localhost:8001/mcp
echo.

REM Check if venv exists
if not exist "venv" (
    echo Creating virtual environment...
    python -m venv venv
)

REM Activate venv
call venv\Scripts\activate.bat

REM Install dependencies if needed
pip install -r requirements.txt --quiet 2>nul

REM Run the server
python -m src.server --transport http --port 8001

pause
