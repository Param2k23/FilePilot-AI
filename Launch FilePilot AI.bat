@echo off
title FilePilot AI
echo.
echo  ==========================================
echo    ✈  FilePilot AI — Starting up...
echo  ==========================================
echo.
echo  [1/3] Activating environment...
call "%~dp0.venv\Scripts\activate.bat"

echo  [2/3] Launching FilePilot AI...
start /b "" "%~dp0.venv\Scripts\python.exe" -m streamlit run "%~dp0Python_Scripts\app.py" --server.headless true --browser.gatherUsageStats false

echo  [3/3] Opening browser in 4 seconds...
timeout /t 4 /nobreak >nul
start "" http://localhost:8501

echo.
echo  FilePilot AI is running at http://localhost:8501
echo  Close this window to stop the app.
echo.
pause
