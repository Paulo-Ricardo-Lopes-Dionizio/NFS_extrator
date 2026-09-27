@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title Configurar Bot Fiscal Unificado

echo ================================================
echo  CONFIGURACAO DO BOT FISCAL UNIFICADO
echo ================================================
echo.

if exist ".venv\Scripts\python.exe" (
    echo [OK] Ambiente virtual existente encontrado.
    goto instalar
)

echo [1/4] Criando o ambiente virtual .venv...
where py >nul 2>&1
if not errorlevel 1 (
    py -3 -m venv ".venv"
) else (
    where python >nul 2>&1
    if errorlevel 1 (
        echo [ERRO] Python nao foi encontrado no PATH.
        echo Instale o Python e marque a opcao Add Python to PATH.
        goto erro
    )
    python -m venv ".venv"
)

if not exist ".venv\Scripts\python.exe" (
    echo [ERRO] Nao foi possivel criar a .venv.
    goto erro
)

:instalar
set "PYTHON_VENV=.venv\Scripts\python.exe"

echo.
echo [2/4] Atualizando pip, setuptools e wheel...
"%PYTHON_VENV%" -m pip install --upgrade pip setuptools wheel
if errorlevel 1 goto erro

echo.
echo [3/4] Instalando requirements.txt...
"%PYTHON_VENV%" -m pip install -r "requirements.txt"
if errorlevel 1 goto erro

echo.
echo [4/4] Preparando configuracao e executando testes...
if not exist ".env" (
    copy /Y ".env.example" ".env" >nul
    echo [ATENCAO] Arquivo .env criado. Preencha tokens, certificados e caminhos.
) else (
    echo [OK] O arquivo .env existente foi preservado.
)

if not exist "empresas_certificadas.json" if exist "empresas_certificadas.example.json" (
    copy /Y "empresas_certificadas.example.json" "empresas_certificadas.json" >nul
)

"%PYTHON_VENV%" -m unittest discover -s tests -v
if errorlevel 1 goto erro

echo.
echo ================================================
echo  CONFIGURACAO CONCLUIDA
echo ================================================
echo.
echo Proximos passos:
echo 1. Abra o arquivo .env e preencha as configuracoes.
echo 2. Escolha DESTINO_NFE e DESTINO_NFSE.
echo 3. Instale o Tesseract OCR e ajuste TESSERACT_EXE, se necessario.
echo 4. Para NF-e, instale PHP/Composer e execute: composer install
echo 5. Execute confi.bat para validar a configuracao.
echo 6. Execute INICIAR_BOT.bat.
echo.
pause
exit /b 0

:erro
echo.
echo ================================================
echo  A CONFIGURACAO FALHOU
echo ================================================
echo Confira a mensagem acima e tente novamente.
echo.
pause
exit /b 1
