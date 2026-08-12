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
REM DOWNLOAD DO FFMPEG PELO WINGET
REM ==========================================================

echo.
echo Baixando FFmpeg pelo winget...
echo.

winget download Gyan.FFmpeg ^
    --accept-source-agreements ^
    --accept-package-agreements ^
    --silent ^
    --download-directory "%APP_DIR%tools\ffmpeg_download"

if errorlevel 1 (
    echo.
    echo ERRO: nao foi possivel baixar o FFmpeg pelo winget.
    echo.
    pause
    exit /b 1
)

REM ==========================================================
REM LOCALIZA O ARQUIVO BAIXADO
REM ==========================================================

echo.
echo Procurando pacote do FFmpeg...

set "FFMPEG_ARCHIVE="

for /r "%APP_DIR%tools\ffmpeg_download" %%F in (*.zip) do (
    set "FFMPEG_ARCHIVE=%%F"
)

if not defined FFMPEG_ARCHIVE (
    echo.
    echo ERRO: arquivo ZIP do FFmpeg nao encontrado.
    echo.
    pause
    exit /b 1
)

echo Pacote encontrado:
echo !FFMPEG_ARCHIVE!

REM ==========================================================
REM EXTRAI FFMPEG
REM ==========================================================

echo.
echo Extraindo FFmpeg...

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
    "Expand-Archive -LiteralPath '!FFMPEG_ARCHIVE!' -DestinationPath '%FFMPEG_DIR%\_extract' -Force"

if errorlevel 1 (
    echo.
    echo ERRO ao extrair o FFmpeg.
    echo.
    pause
    exit /b 1
)

REM ==========================================================
REM LOCALIZA FFMPEG.EXE DENTRO DO PACOTE
REM ==========================================================

set "FFMPEG_EXE="

for /r "%FFMPEG_DIR%\_extract" %%F in (ffmpeg.exe) do (
    set "FFMPEG_EXE=%%F"
    goto FOUND_FFMPEG_EXE
)

:FOUND_FFMPEG_EXE

if not defined FFMPEG_EXE (
    echo.
    echo ERRO: ffmpeg.exe nao encontrado dentro do pacote.
    echo.
    pause
    exit /b 1
)

echo.
echo FFmpeg encontrado em:
echo !FFMPEG_EXE!

REM ==========================================================
REM COPIA ESTRUTURA BIN
REM ==========================================================

for %%F in ("!FFMPEG_EXE!") do (
    set "FFMPEG_SOURCE_DIR=%%~dpF"
)

echo.
echo Instalando FFmpeg localmente...

if not exist "%FFMPEG_BIN%" (
    mkdir "%FFMPEG_BIN%"
)

copy /Y "!FFMPEG_SOURCE_DIR!ffmpeg.exe" "%FFMPEG_BIN%\ffmpeg.exe" >nul
copy /Y "!FFMPEG_SOURCE_DIR!ffprobe.exe" "%FFMPEG_BIN%\ffprobe.exe" >nul 2>nul
copy /Y "!FFMPEG_SOURCE_DIR!ffplay.exe" "%FFMPEG_BIN%\ffplay.exe" >nul 2>nul

if not exist "%FFMPEG_BIN%\ffmpeg.exe" (
    echo.
    echo ERRO: nao foi possivel instalar ffmpeg.exe.
    echo.
    pause
    exit /b 1
)

REM ==========================================================
REM LIMPA DOWNLOAD
REM ==========================================================

echo.
echo Limpando arquivos temporarios...

rmdir /S /Q "%APP_DIR%tools\ffmpeg_download" >nul 2>&1
rmdir /S /Q "%FFMPEG_DIR%\_extract" >nul 2>&1

REM ==========================================================
REM ADICIONA FFMPEG AO PATH DA SESSAO
REM ==========================================================

:ADD_FFMPEG_PATH

set "PATH=%FFMPEG_BIN%;%PATH%"

echo.
echo FFmpeg configurado.

:FFMPEG_READY

REM ==========================================================
REM TESTA FFMPEG
REM ==========================================================

ffmpeg -version >nul 2>&1

if errorlevel 1 (
    echo.
    echo ERRO: FFmpeg nao pode ser executado.
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

REM ==========================================================
REM ATUALIZA PIP
REM ==========================================================

echo.
echo Atualizando pip...

.venv\Scripts\python.exe -m pip install --upgrade pip

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