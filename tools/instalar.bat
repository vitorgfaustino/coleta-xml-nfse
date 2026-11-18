@echo off
setlocal EnableDelayedExpansion
cd /d "%~dp0.."

set "PY=py -3"
%PY% --version >nul 2>&1
if errorlevel 1 set "PY=python"
%PY% --version >nul 2>&1
if errorlevel 1 (
  echo Python 3 nao encontrado.
  echo Instale em https://www.python.org/downloads/windows/ e marque "Add python.exe to PATH".
  if /i not "%~1"=="/quiet" (
    set /p "OPEN_PY=ABRIR A PAGINA OFICIAL DE INSTALACAO AGORA? [S/N]: "
    if /i "!OPEN_PY!"=="S" start "" "https://www.python.org/downloads/windows/"
    pause
  )
  exit /b 1
)

%PY% -c "import sys; raise SystemExit(0 if sys.version_info >= (3,10) else 1)" >nul 2>&1
if errorlevel 1 (
  echo E necessario Python 3.10 ou superior.
  echo Instale a versao atual em https://www.python.org/downloads/windows/
  if /i not "%~1"=="/quiet" (
    set /p "OPEN_PY=ABRIR A PAGINA OFICIAL DE INSTALACAO AGORA? [S/N]: "
    if /i "!OPEN_PY!"=="S" start "" "https://www.python.org/downloads/windows/"
    pause
  )
  exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
  echo Criando o ambiente local...
  if exist ".venv" rmdir /s /q ".venv" >nul 2>&1
  %PY% -m venv .venv
  if errorlevel 1 goto fail
)

".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -r requirements.txt
if errorlevel 1 goto fail

".venv\Scripts\python.exe" -c "import requests, cryptography" >nul 2>&1
if errorlevel 1 goto fail

echo.
echo Dependencias instaladas. Agora execute iniciar.bat.
if /i not "%~1"=="/quiet" pause
exit /b 0

:fail
echo.
echo Nao foi possivel instalar as dependencias.
echo Verifique a conexao com a internet, proxy ou permissao do pip.
if /i not "%~1"=="/quiet" pause
exit /b 1
