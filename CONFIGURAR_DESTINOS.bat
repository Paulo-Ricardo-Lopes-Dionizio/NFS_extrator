@echo off
setlocal
cd /d "%~dp0"

if exist ".venv\Scripts\pythonw.exe" (
    ".venv\Scripts\pythonw.exe" "configurar_destinos.py"
    exit /b %ERRORLEVEL%
)

where py >nul 2>&1
if not errorlevel 1 (
    pyw "configurar_destinos.py"
    exit /b %ERRORLEVEL%
)

echo ERRO: Python nao encontrado. Execute configurar.bat primeiro.
pause
exit /b 1
