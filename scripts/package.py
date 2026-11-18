"""Empacota o resultado do PyInstaller e gera o checksum SHA-256."""

from __future__ import annotations

import argparse
import hashlib
import platform
import shutil
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist"
ARTIFACTS = ROOT / "artifacts"
DOCS = (
    "README.md",
    "LICENSE",
    "SECURITY.md",
    "THIRD_PARTY_NOTICES.md",
    "CONTRIBUTING.md",
    "CODE_OF_CONDUCT.md",
    "SUPPORT.md",
    "CHANGELOG.md",
)


def platform_tag() -> str:
    return {"win32": "windows", "darwin": "macos", "linux": "linux"}.get(
        sys.platform, sys.platform
    )


def arch_tag() -> str:
    machine = platform.machine().lower()
    if machine in {"arm64", "aarch64"}:
        return "arm64"
    if machine in {"x86_64", "amd64"}:
        return "x64"
    return machine or "unknown"


def find_build(name: str) -> Path:
    candidates = (
        DIST / f"{name}.app",
        DIST / name,
        DIST / f"{name}.exe",
    )
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise SystemExit(
        f"Não encontrei {DIST / name}. Rode 'python build.py' antes de empacotar."
    )


def copy_docs(destination: Path) -> None:
    for name in DOCS:
        source = ROOT / name
        if source.is_file():
            shutil.copy2(source, destination / name)
    docs_dir = ROOT / "docs"
    if docs_dir.is_dir():
        shutil.copytree(docs_dir, destination / "docs")


def zip_folder(staging: Path, archive: Path) -> None:
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as handle:
        for path in sorted(staging.rglob("*")):
            if path.is_file():
                handle.write(path, path.relative_to(staging.parent))


def tar_folder(staging: Path, archive: Path) -> None:
    with tarfile.open(archive, "w:gz") as handle:
        handle.add(staging, arcname=staging.name)


def main() -> int:
    parser = argparse.ArgumentParser(description="Empacota o build do aplicativo.")
    parser.add_argument("--name", default="ColetaXMLNFSE")
    args = parser.parse_args()

    build = find_build(args.name)
    platform_name = platform_tag()
    architecture = arch_tag()
    staging = ARTIFACTS / f"{args.name}-{platform_name}-{architecture}"
    shutil.rmtree(staging, ignore_errors=True)
    staging.mkdir(parents=True)

    if build.is_dir():
        shutil.copytree(build, staging / build.name, symlinks=True)
    else:
        shutil.copy2(build, staging / build.name)
    copy_docs(staging)

    archive = Path(str(staging) + (".tar.gz" if platform_name == "linux" else ".zip"))
    if archive.exists():
        archive.unlink()

    if platform_name == "macos" and shutil.which("ditto"):
        subprocess.run(
            [
                "ditto",
                "-c",
                "-k",
                "--norsrc",
                "--keepParent",
                str(staging),
                str(archive),
            ],
            check=True,
        )
    elif platform_name == "linux":
        tar_folder(staging, archive)
    else:
        zip_folder(staging, archive)

    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    checksum = archive.with_name(archive.name + ".sha256")
    checksum.write_text(f"{digest}  {archive.name}\n", encoding="utf-8")
    print(f"Artefato: {archive}")
    print(f"SHA-256: {digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
