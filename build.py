"""Build do executável com PyInstaller.

Exemplos:
    python build.py
    python build.py --windowed        # .app no macOS, sem console
    python build.py --onefile         # um único arquivo, mais lento
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def main() -> int:
    parser = argparse.ArgumentParser(description="Gera o executável do Coleta XML NFSE.")
    parser.add_argument("--onefile", action="store_true", help="gera um único arquivo")
    parser.add_argument("--windowed", action="store_true", help="sem janela de console")
    parser.add_argument("--name", default="ColetaXMLNFSE", help="nome do executável")
    args = parser.parse_args()

    try:
        import PyInstaller.__main__
    except ImportError as exc:
        raise SystemExit(
            "PyInstaller não está instalado. Use "
            "'python -m pip install -r requirements-build.txt'."
        ) from exc

    separator = ";" if sys.platform == "win32" else ":"
    command = [
        str(ROOT / "nfse_app.py"),
        "--name",
        args.name,
        "--noconfirm",
        "--clean",
        "--add-data",
        f"{ROOT / 'web'}{separator}web",
        "--distpath",
        str(ROOT / "dist"),
        "--workpath",
        str(ROOT / "build"),
        "--specpath",
        str(ROOT / "build"),
        "--onefile" if args.onefile else "--onedir",
        "--windowed" if args.windowed else "--console",
    ]

    icon = ROOT / "assets" / ("icon.ico" if sys.platform == "win32" else "icon.icns")
    if icon.is_file():
        command += ["--icon", str(icon)]

    if sys.platform == "darwin":
        command += ["--osx-bundle-identifier", "br.com.coleta-xml-nfse"]

    PyInstaller.__main__.run(command)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
