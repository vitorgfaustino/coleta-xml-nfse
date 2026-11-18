#!/bin/bash
set -u
cd "$(dirname "$0")" || exit 1

open_python_page() {
  printf "Abrir a pagina oficial de instalacao do Python agora? [s/N] "
  read -r OPEN_PY
  case "$OPEN_PY" in
    s|S) open "https://www.python.org/downloads/macos/" ;;
  esac
}


pause_and_exit() {
  echo
  read -n 1 -s -r -p "Pressione qualquer tecla para fechar..."
  echo
  exit "${1:-1}"
}

PYTHON="${PYTHON:-python3}"
if ! command -v "$PYTHON" >/dev/null 2>&1; then
  echo "Python 3 nao encontrado."
  echo "Instale em https://www.python.org/downloads/macos/ e tente novamente."
  open_python_page
  pause_and_exit 1
fi

if ! "$PYTHON" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3,10) else 1)' >/dev/null 2>&1; then
  echo "E necessario Python 3.10 ou superior."
  echo "A versao encontrada e $("$PYTHON" --version 2>&1)."
  echo "Instale a versao atual em https://www.python.org/downloads/macos/"
  open_python_page
  pause_and_exit 1
fi

if [ ! -x ".venv/bin/python" ]; then
  echo "Preparando o ambiente local..."
  rm -rf .venv
  "$PYTHON" -m venv .venv || pause_and_exit 1
fi

VPY=".venv/bin/python"
if ! "$VPY" -c "import requests, cryptography" >/dev/null 2>&1; then
  echo "Instalando dependencias necessarias..."
  "$VPY" -m pip install --disable-pip-version-check -r requirements.txt || pause_and_exit 1
fi

"$VPY" nfse_app.py
STATUS=$?
if [ "$STATUS" -ne 0 ]; then
  echo
  echo "O aplicativo terminou com codigo $STATUS."
  pause_and_exit "$STATUS"
fi
