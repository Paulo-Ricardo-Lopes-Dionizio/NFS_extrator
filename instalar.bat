@echo off
cd /d "%~dp0"
echo ============================================
echo  INSTALANDO BOT FISCAL UNIFICADO
echo ============================================

if not exist ".venv\Scripts\python.exe" (
    py -m venv .venv
)

call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt

if not exist ".env" if exist ".env.example" copy /Y ".env.example" ".env" >nul

echo.
echo Instalacao Python concluida.
echo Para o fluxo de NF-e, execute tambem: composer install
pause
