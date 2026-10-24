@echo off
setlocal
title Eclipse Legends Bot

cd /d "%~dp0"

set "PYTHON_CMD=py -3.10"
%PYTHON_CMD% --version >nul 2>&1
if errorlevel 1 (
    set "PYTHON_CMD=python"
    python --version >nul 2>&1
    if errorlevel 1 (
        echo Python 3.10 ou superior nao encontrado.
        echo Instale o Python e tente novamente.
        pause
        exit /b 1
    )
)

set "VENV_PYTHON=%~dp0.venv\Scripts\python.exe"
if not exist "%VENV_PYTHON%" (
    echo ===============================
    echo Preparando ambiente do bot...
    echo ===============================
    %PYTHON_CMD% -m venv "%~dp0.venv"
    if errorlevel 1 (
        echo.
        echo Nao foi possivel criar o ambiente virtual.
        pause
        exit /b 1
    )
    "%VENV_PYTHON%" -m pip install --upgrade pip setuptools wheel
    if errorlevel 1 (
        echo.
        echo Nao foi possivel preparar o instalador de dependencias.
        pause
        exit /b 1
    )
)

echo Verificando dependencias...
"%VENV_PYTHON%" -m pip install --disable-pip-version-check --quiet --only-binary=:all: -r "%~dp0requirements.txt"
if errorlevel 1 (
    echo.
    echo Falha ao instalar as dependencias do bot.
    pause
    exit /b 1
)

if not exist ".env" (
    if not exist ".env.local" (
        echo.
        echo ===============================
        echo Token nao encontrado
        echo ===============================
        echo Crie um arquivo .env.local nesta pasta com:
        echo DISCORD_TOKEN=seu_token_do_discord
        echo.
        pause
        exit /b 1
    )
)

echo.
echo ===============================
echo Iniciando Eclipse Legends...
echo Servidor local: http://127.0.0.1:8080/
echo Feche esta janela para desligar o bot e o servidor.
echo ===============================

"%VENV_PYTHON%" "%~dp0bot.py"
set "BOT_EXIT_CODE=%ERRORLEVEL%"

echo.
echo Bot e servidor local encerrados.
pause
exit /b %BOT_EXIT_CODE%
