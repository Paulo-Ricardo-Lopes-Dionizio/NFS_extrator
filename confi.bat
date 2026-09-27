@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo ERRO: .venv nao encontrada. Execute configurar.bat primeiro.
    pause
    exit /b 1
)

".venv\Scripts\python.exe" "verificar_configuracao.py"
set "CODIGO=%ERRORLEVEL%"
echo.
pause
exit /b %CODIGO%
