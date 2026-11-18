"""Gera um ZIP de distribuição Python para usuários finais.

O ZIP contém somente o necessário para executar o aplicativo: launchers,
código Python, web, requirements, licença e guias. Não inclui testes, workflows,
cache, `.venv`, builds ou arquivos de desenvolvimento.
"""

from __future__ import annotations

import argparse
import hashlib
import re
import zipfile
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipInfo

ROOT = Path(__file__).resolve().parent.parent
PREFIX = "ColetaXMLNFSE"


def version() -> str:
    text = (ROOT / "nfse" / "version.py").read_text(encoding="utf-8")
    match = re.search(r'__version__\s*=\s*"([^"]+)"', text)
    return match.group(1) if match else "0.0.0"


def collect() -> list[Path]:
    files: list[Path] = [
        ROOT / "COMECE-AQUI.md",
        ROOT / "LICENSE",
        ROOT / "SECURITY.md",
        ROOT / "THIRD_PARTY_NOTICES.md",
        ROOT / "iniciar.bat",
        ROOT / "iniciar.command",
        ROOT / "nfse_app.py",
        ROOT / "requirements.txt",
        ROOT / "docs" / "USO.md",
        ROOT / "docs" / "PRIVACY.md",
        ROOT / "tools" / "README.md",
        ROOT / "tools" / "instalar.bat",
        ROOT / "tools" / "instalar.command",
    ]
    files.extend(sorted((ROOT / "nfse").glob("*.py")))
    files.extend(
        path
        for path in sorted((ROOT / "web").rglob("*"))
        if path.is_file() and "__pycache__" not in path.parts
    )
    missing = [str(path) for path in files if not path.is_file()]
    if missing:
        raise SystemExit("Arquivos ausentes para o pacote:\n" + "\n".join(missing))
    return files


def add_file(archive: zipfile.ZipFile, path: Path) -> None:
    relative = path.relative_to(ROOT).as_posix()
    info = ZipInfo(f"{PREFIX}/{relative}")
    info.date_time = (2026, 1, 1, 0, 0, 0)
    info.compress_type = ZIP_DEFLATED
    info.external_attr = (path.stat().st_mode & 0xFFFF) << 16
    archive.writestr(info, path.read_bytes())


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Gera o ZIP de distribuição Python do Coleta XML NFSE."
    )
    parser.add_argument(
        "--output",
        help="arquivo de saída (padrão: dist/ColetaXMLNFSE-<versao>.zip)",
    )
    args = parser.parse_args()

    output = (
        Path(args.output).expanduser()
        if args.output
        else ROOT / "dist" / f"{PREFIX}-{version()}.zip"
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(output.name + ".tmp")
    files = collect()
    try:
        with zipfile.ZipFile(temporary, "w", ZIP_DEFLATED, compresslevel=6) as archive:
            for path in files:
                add_file(archive, path)
        temporary.replace(output)
    finally:
        try:
            if temporary.exists():
                temporary.unlink()
        except OSError:
            pass

    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    checksum = output.with_name(output.name + ".sha256")
    checksum.write_text(f"{digest}  {output.name}\n", encoding="utf-8")
    print(f"Pacote: {output}")
    print(f"Arquivos: {len(files)}")
    print(f"SHA-256: {digest}")
    print(f"Checksum: {checksum}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
