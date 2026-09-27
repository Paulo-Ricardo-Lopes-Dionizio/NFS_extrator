@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo ERRO: .venv\Scripts\python.exe nao encontrado.
    pause
    exit /b 1
)

if not exist "logs" mkdir "logs"

:inicio
".venv\Scripts\python.exe" "bot_telegram.py" >> "logs\bot_execucao.log" 2>&1
timeout /t 10 /nobreak >nul
goto inicio
