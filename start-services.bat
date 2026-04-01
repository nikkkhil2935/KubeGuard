@echo off
echo ========================================
echo Starting KubeGuard Services
echo ========================================

:: Start backend server in a new window
echo Starting Backend Server on port 9001...
start "KubeGuard Backend" cmd /k "cd /d %~dp0dashboard && pip install -r requirements.txt && python live_server.py"

:: Wait a bit for backend to start
timeout /t 3 /nobreak > nul

:: Start frontend in a new window
echo Starting Frontend on port 3000...
start "KubeGuard Frontend" cmd /k "cd /d %~dp0frontend && npm install && npm run dev"

echo ========================================
echo Services Starting...
echo Backend: http://localhost:9001
echo Frontend: http://localhost:3000
echo ========================================
echo.
echo Press any key to exit this window...
pause > nul
