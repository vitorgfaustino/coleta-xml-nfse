"""Atualiza a versão em nfse/version.py e pyproject.toml.

Uso no CI:
    python scripts/set_version.py v0.3.0
    python scripts/set_version.py 0.3.0
"""

from __future__ import annotations

import argparse
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SEMVER = re.compile(r"\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?")


def main() -> int:
    parser = argparse.ArgumentParser(description="Define a versão do build.")
    parser.add_argument("version", help="versão SemVer, com ou sem o prefixo v")
    args = parser.parse_args()
    version = args.version.strip().lstrip("v")
    if not SEMVER.fullmatch(version):
        raise SystemExit("Versão inválida. Use SemVer, por exemplo 0.3.0.")

    version_file = ROOT / "nfse" / "version.py"
    version_file.write_text(
        '"""Versão do aplicativo. O CI atualiza este arquivo antes do build."""\n\n'
        f'__version__ = "{version}"\n',
        encoding="utf-8",
    )

    pyproject = ROOT / "pyproject.toml"
    text = pyproject.read_text(encoding="utf-8")
    text, count = re.subn(
        r'(?m)^version = ".*"$', f'version = "{version}"', text, count=1
    )
    if count != 1:
        raise SystemExit("Não encontrei a linha version no pyproject.toml.")
    pyproject.write_text(text, encoding="utf-8")
    # Evita .pyc antigo com o mesmo tamanho e mtime na mesma resolução.
    shutil.rmtree(ROOT / "nfse" / "__pycache__", ignore_errors=True)
    print(version)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
