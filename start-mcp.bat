@echo off
cd /d %~dp0
.\venv\Scripts\python.exe -c "from src.server import mcp; mcp.run(transport='streamable-http', host='0.0.0.0', port=8001)"