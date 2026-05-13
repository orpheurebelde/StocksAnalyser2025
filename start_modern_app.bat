@echo off
echo ===================================================
echo   Starting StocksAnalyser2025 Modern Architecture
echo ===================================================

echo Starting FastAPI Backend...
start "Backend API" cmd /k "cd backend && .\.venv\Scripts\uvicorn main:app --reload"

echo Starting React Frontend...
start "React Frontend" cmd /k "cd frontend && npm run dev"

echo.
echo Both servers have been launched in separate windows!
echo - The New Frontend UI will be available at: http://localhost:5173
echo - The Backend API is running at: http://localhost:8000
echo.
pause
