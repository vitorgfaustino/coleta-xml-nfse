@echo off
setlocal EnableDelayedExpansion
cd /d "%~dp0"

set "PY=py -3"
%PY% --version >nul 2>&1
if errorlevel 1 set "PY=python"
%PY% --version >nul 2>&1
if errorlevel 1 (
  echo Python 3 nao encontrado.
  echo Instale em https://www.python.org/downloads/windows/ e marque "Add python.exe to PATH".
  set /p "OPEN_PY=ABRIR A PAGINA OFICIAL DE INSTALACAO AGORA? [S/N]: "
  if /i "!OPEN_PY!"=="S" start "" "https://www.python.org/downloads/windows/"
  pause
  exit /b 1
)

%PY% -c "import sys; raise SystemExit(0 if sys.version_info >= (3,10) else 1)" >nul 2>&1
if errorlevel 1 (
  echo E necessario Python 3.10 ou superior.
  echo Instale a versao atual em https://www.python.org/downloads/windows/
  set /p "OPEN_PY=ABRIR A PAGINA OFICIAL DE INSTALACAO AGORA? [S/N]: "
  if /i "!OPEN_PY!"=="S" start "" "https://www.python.org/downloads/windows/"
  pause
  exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
  echo Preparando o ambiente local...
  if exist ".venv" rmdir /s /q ".venv" >nul 2>&1
  %PY% -m venv .venv
  if errorlevel 1 goto fail
)

set "VPY=.venv\Scripts\python.exe"
"%VPY%" -c "import requests, cryptography" >nul 2>&1
if errorlevel 1 (
  echo Instalando dependencias necessarias...
  "%VPY%" -m pip install --disable-pip-version-check -r requirements.txt
  if errorlevel 1 goto fail
)

"%VPY%" nfse_app.py
if errorlevel 1 pause
exit /b 0

:fail
echo.
echo Nao foi possivel preparar o ambiente.
echo Verifique a conexao com a internet e tente novamente.
pause
exit /b 1
