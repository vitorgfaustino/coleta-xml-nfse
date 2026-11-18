#!/bin/bash
set -u
cd "$(dirname "$0")/.." || exit 1

open_python_page() {
  printf "Abrir a pagina oficial de instalacao do Python agora? [s/N] "
  read -r OPEN_PY
  case "$OPEN_PY" in
    s|S) open "https://www.python.org/downloads/macos/" ;;
  esac
}

PYTHON="${PYTHON:-python3}"

if ! command -v "$PYTHON" >/dev/null 2>&1; then
  echo "Python 3 nao encontrado. Instale em https://www.python.org/downloads/macos/"
  open_python_page
  read -n 1 -s -r -p "Pressione qualquer tecla para fechar..."
  exit 1
fi

if ! "$PYTHON" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3,10) else 1)' >/dev/null 2>&1; then
  echo "E necessario Python 3.10 ou superior."
  echo "Instale a versao atual em https://www.python.org/downloads/macos/"
  open_python_page
  read -n 1 -s -r -p "Pressione qualquer tecla para fechar..."
  exit 1
fi

rm -rf .venv
"$PYTHON" -m venv .venv || exit 1
".venv/bin/python" -m pip install --disable-pip-version-check -r requirements.txt || exit 1
echo
echo "Dependencias instaladas. Agora abra iniciar.command."
read -n 1 -s -r -p "Pressione qualquer tecla para fechar..."
