@echo off
setlocal

title Editor de Audio

echo ================================
echo        EDITOR AUDIO
echo ================================
echo.

REM --------------------------------------------------
REM Verifica Python
REM --------------------------------------------------

where python >nul 2>&1

if errorlevel 1 (
    echo ERRO: Python nao encontrado.
    echo.
    echo Instale o Python 3 e marque:
    echo "Add Python to PATH"
    echo.
    pause
    exit /b 1
)

REM --------------------------------------------------
REM Cria ambiente virtual
REM --------------------------------------------------

if not exist ".venv\Scripts\python.exe" (
    echo Criando ambiente virtual...
    python -m venv .venv

    if errorlevel 1 (
        echo ERRO ao criar o ambiente virtual.
        pause
        exit /b 1
    )
)

REM --------------------------------------------------
REM Atualiza pip
REM --------------------------------------------------

echo.
echo Atualizando pip...

.venv\Scripts\python.exe -m pip install --upgrade pip

REM --------------------------------------------------
REM Instala dependencias
REM --------------------------------------------------

echo.
echo Instalando dependencias...

.venv\Scripts\python.exe -m pip install -r requirements.txt

if errorlevel 1 (
    echo.
    echo ERRO ao instalar as dependencias.
    pause
    exit /b 1
)

REM --------------------------------------------------
REM Verifica FFmpeg
REM --------------------------------------------------

where ffmpeg >nul 2>&1

if errorlevel 1 (
    echo.
    echo AVISO: FFmpeg nao foi encontrado no PATH.
    echo O aplicativo podera iniciar, mas o processamento
    echo de audio nao funcionara ate que o FFmpeg seja instalado.
    echo.
    pause
)

REM --------------------------------------------------
REM Inicia aplicacao
REM --------------------------------------------------

echo.
echo Iniciando Audio Editor Local...
echo.

start "" /b .venv\Scripts\python.exe app.py

REM --------------------------------------------------
REM Aguarda o servidor
REM --------------------------------------------------

echo Aguardando servidor...

:WAIT_SERVER

timeout /t 1 /nobreak >nul

powershell -NoProfile -Command ^
    "try { $r=Invoke-WebRequest -Uri 'http://127.0.0.1:5000' -UseBasicParsing -TimeoutSec 1; exit 0 } catch { exit 1 }"

if errorlevel 1 goto WAIT_SERVER

REM --------------------------------------------------
REM Abre navegador
REM --------------------------------------------------

echo.
echo Aplicacao iniciada!
echo.
echo Abrindo navegador...

start "" "http://127.0.0.1:5000"

REM --------------------------------------------------
REM Mantem o BAT aberto
REM --------------------------------------------------

echo.
echo Audio Editor Local esta em execucao.
echo.
echo Feche esta janela para encerrar o aplicativo.
echo.

pause