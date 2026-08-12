@echo off
setlocal EnableExtensions EnableDelayedExpansion

title Audio Editor Local

REM ==========================================================
REM DIRETORIO DO APLICATIVO
REM ==========================================================

cd /d "%~dp0"

set "APP_DIR=%~dp0"
set "FFMPEG_DIR=%APP_DIR%tools\ffmpeg"
set "FFMPEG_BIN=%FFMPEG_DIR%\bin"

echo.
echo ==========================================
echo        AUDIO EDITOR LOCAL
echo ==========================================
echo.
echo Diretorio:
echo %APP_DIR%
echo.

REM ==========================================================
REM VERIFICA PYTHON
REM ==========================================================

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

echo Python encontrado.

REM ==========================================================
REM VERIFICA FFmpeg
REM ==========================================================

where ffmpeg >nul 2>&1

if not errorlevel 1 (
    echo FFmpeg encontrado no sistema.
    goto FFMPEG_READY
)

REM ==========================================================
REM VERIFICA FFmpeg LOCAL
REM ==========================================================

if exist "%FFMPEG_BIN%\ffmpeg.exe" (
    echo FFmpeg local encontrado.
    goto ADD_FFMPEG_PATH
)

echo.
echo FFmpeg nao foi encontrado.
echo.

REM ==========================================================
REM VERIFICA WINGET
REM ==========================================================

where winget >nul 2>&1

if errorlevel 1 (
    echo ERRO: winget nao esta disponivel neste computador.
    echo.
    echo Instale o App Installer da Microsoft Store
    echo ou instale o FFmpeg manualmente.
    echo.
    pause
    exit /b 1
)

echo Winget encontrado.

REM ==========================================================
REM CRIA DIRETORIO TOOLS
REM ==========================================================

if not exist "%APP_DIR%tools" (
    mkdir "%APP_DIR%tools"
)

if not exist "%FFMPEG_DIR%" (
    mkdir "%FFMPEG_DIR%"
)

REM ==========================================================
REM INSTALL DO FFMPEG PELO WINGET
REM ==========================================================

echo.
echo Baixando FFmpeg pelo winget...
echo.

winget install ffmpeg

:FFMPEG_READY

REM ==========================================================
REM TESTA FFMPEG
REM ==========================================================

ffmpeg -version >nul 2>&1

if errorlevel 1 (
    echo.
    echo ERRO: FFmpeg nao pode ser executado. Se acabou de instalar, execute o run.bat novamente.
    echo.
    pause
    exit /b 1
)

echo FFmpeg OK.

REM ==========================================================
REM CRIA AMBIENTE VIRTUAL
REM ==========================================================

if not exist ".venv\Scripts\python.exe" (
    echo.
    echo Criando ambiente virtual...
    
    python -m venv .venv

    if errorlevel 1 (
        echo.
        echo ERRO ao criar ambiente virtual.
        pause
        exit /b 1
    )
)
echo.
echo Verificando compatibilidade do Python...

for /f "tokens=2" %%V in ('.venv\Scripts\python.exe --version') do set "PYTHON_VERSION=%%V"

echo Python utilizado: !PYTHON_VERSION!

.venv\Scripts\python.exe -c "import sys; print('Python', sys.version)"

REM ==========================================================
REM ATUALIZA PIP
REM ==========================================================

echo.
echo Atualizando pip...

.venv\Scripts\python.exe -m pip install --upgrade pip

.venv\Scripts\python.exe -c "import audioop" >nul 2>&1

if errorlevel 1 (
    echo.
    echo audioop nao encontrado.
    echo Instalando compatibilidade para Python 3.13+...
    
    .venv\Scripts\python.exe -m pip install audioop-lts

    if errorlevel 1 (
        echo.
        echo ERRO: nao foi possivel instalar audioop-lts.
        pause
        exit /b 1
    )
)

REM ==========================================================
REM INSTALA DEPENDENCIAS
REM ==========================================================

echo.
echo Instalando dependencias Python...

.venv\Scripts\python.exe -m pip install -r requirements.txt

if errorlevel 1 (
    echo.
    echo ERRO ao instalar dependencias.
    pause
    exit /b 1
)

REM ==========================================================
REM INICIA APLICACAO
REM ==========================================================

echo.
echo ==========================================
echo      INICIANDO AUDIO EDITOR LOCAL
echo ==========================================
echo.

start "" /b .venv\Scripts\python.exe app.py

REM ==========================================================
REM AGUARDA FLASK
REM ==========================================================

echo Aguardando servidor...

:WAIT_SERVER

timeout /t 1 /nobreak >nul

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
    "try { $r=Invoke-WebRequest -Uri 'http://127.0.0.1:5000' -UseBasicParsing -TimeoutSec 1; exit 0 } catch { exit 1 }"

if errorlevel 1 goto WAIT_SERVER

REM ==========================================================
REM ABRE NAVEGADOR
REM ==========================================================

echo.
echo Aplicacao iniciada!
echo.
echo Abrindo navegador...

start "" "http://127.0.0.1:5000"

echo.
echo ==========================================
echo       AUDIO EDITOR EM EXECUCAO
echo ==========================================
echo.
echo Endereco:
echo http://127.0.0.1:5000
echo.
echo Feche esta janela para encerrar o aplicativo.
echo.

pause