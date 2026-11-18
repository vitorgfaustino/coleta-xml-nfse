"""Núcleo local do Coleta XML NFSE.

Sem Tkinter, sem servidor próprio e sem dependência de Windows. O único
destino de rede é o ADN, via TLS mútuo com o certificado A1 do usuário.
"""

from __future__ import annotations

import base64
import gzip
import hashlib
import json
import os
import random
import re
import shutil
import sqlite3
import sys
import tempfile
import threading
import time
import zipfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import Any, Callable, Iterable, Iterator, Sequence
from xml.etree import ElementTree as ET

import requests
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    NoEncryption,
    PrivateFormat,
)
from cryptography.hazmat.primitives.serialization.pkcs12 import (
    load_key_and_certificates,
)

from .version import __version__ as APP_VERSION

APP_NAME = "ColetaXmlNFSE"
APP_DISPLAY_NAME = "Coleta XML NFSE"
LEGACY_APP_NAME = "NFSeXmlDownloader"

PRODUCTION = "https://adn.nfse.gov.br/contribuintes"
RESTRICTED = "https://adn.producaorestrita.nfse.gov.br/contribuintes"
ENVIRONMENTS = {"producao": PRODUCTION, "restrita": RESTRICTED}
FILTERS = ("Prestados", "Tomados", "Ambas")

NSU_KEYS = {
    "nsu",
    "ultnsu",
    "ultimonsu",
    "nsuultimo",
    "numerosequencialunico",
}
NO_DOCUMENT_CODES = {"E2220", "E2230"}
MAX_PAGES_DEFAULT = 10_000
PAGE_DELAY_DEFAULT = 0.25


class NfseError(RuntimeError):
    """Erro de domínio do coletor."""


class ApiError(NfseError):
    """A API respondeu de forma inesperada ou recusou a consulta."""


class NoDocuments(NfseError):
    """O ADN informou que não há mais documentos para o NSU consultado."""


class TransientApiError(ApiError):
    """Falha temporária de rede/limite que esgotou as tentativas."""


class CertificateError(NfseError):
    """O PFX/P12 não pôde ser aberto."""


class JobCancelled(NfseError):
    """O usuário cancelou a execução."""


# ---------------------------------------------------------------------------
# Diretórios e permissões
# ---------------------------------------------------------------------------


def _chmod(path: Path, mode: int) -> None:
    if os.name == "nt":
        return
    try:
        os.chmod(path, mode)
    except OSError:
        pass


def data_dir() -> Path:
    """Diretório de dados do app, por sistema operacional.

    ``NFSE_DATA_DIR`` permite isolar testes ou usar um volume específico.
    """

    override = os.environ.get("NFSE_DATA_DIR")
    if override:
        path = Path(override).expanduser()
    elif sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA") or (Path.home() / "AppData" / "Local"))
        path = base / APP_NAME
    elif sys.platform == "darwin":
        path = Path.home() / "Library" / "Application Support" / APP_NAME
    else:
        base = Path(os.environ.get("XDG_DATA_HOME") or (Path.home() / ".local" / "share"))
        path = base / APP_NAME
    path.mkdir(parents=True, exist_ok=True)
    _chmod(path, 0o700)
    return path


def _legacy_data_dirs() -> list[Path]:
    """Locais usados antes da renomeação para Coleta XML NFSE."""

    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA") or (Path.home() / "AppData" / "Local"))
        paths = [base / LEGACY_APP_NAME]
    elif sys.platform == "darwin":
        paths = [
            Path.home() / "Library" / "Application Support" / LEGACY_APP_NAME,
            Path.home() / LEGACY_APP_NAME,
        ]
    else:
        base = Path(os.environ.get("XDG_DATA_HOME") or (Path.home() / ".local" / "share"))
        paths = [base / LEGACY_APP_NAME, Path.home() / LEGACY_APP_NAME]
    unique: list[Path] = []
    for path in paths:
        if path not in unique:
            unique.append(path)
    return unique


def legacy_data_dir() -> Path | None:
    """Primeiro diretório antigo que ainda contém dados, se existir."""

    for old in _legacy_data_dirs():
        if old.is_dir() and (
            (old / "state.sqlite3").exists() or any((old / "xml_cache").glob("*"))
        ):
            return old
    return None


def migrate_legacy_data(log: Callable[[str], None] | None = None) -> str | None:
    """Copia cursor/cache do nome antigo para o novo, sem copiar segredos."""

    new = data_dir()
    if (new / "state.sqlite3").exists() or any((new / "xml_cache").glob("*")):
        return None

    for old in _legacy_data_dirs():
        if not old.is_dir() or old == new:
            continue
        old_state = old / "state.sqlite3"
        old_cache = old / "xml_cache"
        if not old_state.is_file() and not (old_cache.is_dir() and any(old_cache.glob("*"))):
            continue
        copied: list[str] = []
        if old_state.is_file():
            shutil.copy2(old_state, new / "state.sqlite3")
            _chmod(new / "state.sqlite3", 0o600)
            copied.append("cursor")
        if old_cache.is_dir():
            shutil.copytree(old_cache, new / "xml_cache", dirs_exist_ok=True)
            copied.append("cache")
        if copied and log:
            log("Dados da versão anterior importados: " + ", ".join(copied) + ".")
        return ", ".join(copied) or None
    return None


def _restrict_file(path: Path) -> None:
    _chmod(path, 0o600)


def cache_stats(root: Path | None = None) -> tuple[int, int]:
    root = root or data_dir() / "xml_cache"
    files = 0
    size = 0
    if not root.is_dir():
        return 0, 0
    for path in root.rglob("*.xml"):
        try:
            files += 1
            size += path.stat().st_size
        except OSError:
            continue
    return files, size


def cache_clients(root: Path | None = None) -> list[dict[str, Any]]:
    """Resumo da cópia local por CNPJ, sem abrir o banco de estado."""

    root = root or data_dir()
    cache_root = root / "xml_cache"
    clients: list[dict[str, Any]] = []
    if not cache_root.is_dir():
        return clients
    for folder in sorted(cache_root.iterdir(), key=lambda item: item.name):
        if not folder.is_dir() or folder.name.startswith("."):
            continue
        files = 0
        size = 0
        newest = 0.0
        for path in folder.rglob("*.xml"):
            try:
                stat = path.stat()
            except OSError:
                continue
            files += 1
            size += stat.st_size
            newest = max(newest, stat.st_mtime)
        clients.append(
            {
                "cnpj": folder.name,
                "files": files,
                "bytes": size,
                "updated_at": (
                    datetime.fromtimestamp(newest).isoformat(timespec="seconds")
                    if newest
                    else None
                ),
            }
        )
    return clients


def clear_cnpj_cache(cnpj: str, root: Path | None = None) -> dict[str, Any]:
    """Apaga XMLs, índice e cursor de um único CNPJ."""

    normalized = normalize_cnpj(cnpj)
    if len(normalized) != 14:
        raise ValueError("CNPJ inválido para limpeza do cache.")
    root = root or data_dir()
    folder = root / "xml_cache" / normalized
    removed_files = 0
    freed = 0
    if folder.is_dir():
        for path in folder.rglob("*.xml"):
            try:
                freed += path.stat().st_size
                removed_files += 1
            except OSError:
                pass
        shutil.rmtree(folder, ignore_errors=True)

    removed_rows = 0
    state = root / "state.sqlite3"
    if state.is_file():
        connection = connect_state(state)
        try:
            removed_rows = connection.execute(
                "SELECT COUNT(*) FROM documents WHERE cnpj = ?", (normalized,)
            ).fetchone()[0]
            connection.execute("DELETE FROM documents WHERE cnpj = ?", (normalized,))
            connection.execute("DELETE FROM cursors WHERE cnpj = ?", (normalized,))
            connection.commit()
        finally:
            connection.close()
    return {
        "cnpj": normalized,
        "files": removed_files,
        "bytes": freed,
        "documents": int(removed_rows or 0),
    }


def create_cache_backup(root: Path | None = None) -> Path:
    """Cria um ZIP consistente com estado e XMLs para backup local."""

    root = root or data_dir()
    state = root / "state.sqlite3"
    staging = Path(tempfile.mkdtemp(prefix="coleta_backup_"))
    try:
        state_copy = staging / "state.sqlite3"
        source = connect_state(state)
        target = sqlite3.connect(str(state_copy))
        try:
            source.backup(target)
        finally:
            target.close()
            source.close()
        _restrict_file(state_copy)

        clients = cache_clients(root)
        manifest = {
            "app": APP_DISPLAY_NAME,
            "app_name": APP_NAME,
            "version": APP_VERSION,
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "clients": clients,
            "files": sum(item["files"] for item in clients),
            "bytes": sum(item["bytes"] for item in clients),
        }
        archive = staging / (
            "coleta-xml-nfse-backup-" + datetime.now().strftime("%Y%m%d-%H%M%S") + ".zip"
        )
        with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as bundle:
            bundle.writestr(
                "manifest.json",
                json.dumps(manifest, ensure_ascii=False, indent=2),
            )
            bundle.write(state_copy, "state.sqlite3")
            cache_root = root / "xml_cache"
            if cache_root.is_dir():
                for path in sorted(cache_root.rglob("*.xml")):
                    if path.is_file():
                        arcname = (Path("xml_cache") / path.relative_to(cache_root)).as_posix()
                        bundle.write(path, arcname)
        _restrict_file(archive)
        return archive
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise


def restore_cache_backup(archive: Path, root: Path | None = None) -> dict[str, Any]:
    """Restaura um backup gerado por ``create_cache_backup``.

    O ZIP é validado antes de substituir o estado atual. Um backup do estado
    anterior fica temporariamente ao lado dos dados e é removido após sucesso.
    """

    root = root or data_dir()
    if not zipfile.is_zipfile(archive):
        raise ValueError("O arquivo não é um ZIP de backup válido.")

    max_files = 50_000
    max_bytes = 5 * 1024 * 1024 * 1024
    with zipfile.ZipFile(archive) as bundle:
        infos = bundle.infolist()
        if len(infos) > max_files:
            raise ValueError("O backup tem arquivos demais.")
        total = 0
        seen: set[str] = set()
        for info in infos:
            if info.is_dir():
                continue
            name = info.filename.replace("\\", "/")
            parts = PurePosixPath(name).parts
            if not parts or name.startswith("/") or ".." in parts:
                raise ValueError("O backup contém caminho inválido.")
            if name in seen:
                raise ValueError("O backup contém arquivo duplicado.")
            seen.add(name)
            allowed = (
                name == "manifest.json"
                or name == "state.sqlite3"
                or (
                    parts[0] == "xml_cache"
                    and len(parts) >= 2
                    and name.lower().endswith(".xml")
                )
            )
            if not allowed:
                raise ValueError(f"Arquivo não permitido no backup: {name}")
            total += max(0, info.file_size)
            if total > max_bytes:
                raise ValueError("O backup descompactado é grande demais.")

        staging = Path(tempfile.mkdtemp(prefix="coleta_restore_"))
        written_total = 0
        try:
            for info in infos:
                if info.is_dir():
                    continue
                name = info.filename.replace("\\", "/")
                if ":" in name:
                    raise ValueError("O backup contém caminho inválido.")
                target = staging / name
                target.parent.mkdir(parents=True, exist_ok=True)
                with bundle.open(info) as source, target.open("wb") as destination:
                    while True:
                        chunk = source.read(1024 * 1024)
                        if not chunk:
                            break
                        written_total += len(chunk)
                        if written_total > max_bytes:
                            raise ValueError("O backup descompactado é grande demais.")
                        destination.write(chunk)

            restored_state = staging / "state.sqlite3"
            if not restored_state.is_file():
                raise ValueError("O backup não contém state.sqlite3.")
            check = sqlite3.connect(str(restored_state))
            try:
                tables = {
                    row[0]
                    for row in check.execute(
                        "SELECT name FROM sqlite_master WHERE type = 'table'"
                    )
                }
                if not {"cursors", "documents"}.issubset(tables):
                    raise ValueError("O banco do backup não tem o formato esperado.")
                integrity = check.execute("PRAGMA integrity_check").fetchone()[0]
                if integrity != "ok":
                    raise ValueError("O banco do backup está corrompido.")
                documents = int(
                    check.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
                )
            finally:
                check.close()

            stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            old_state = root / "state.sqlite3"
            old_cache = root / "xml_cache"
            old_parts = [
                old_state,
                root / "state.sqlite3-wal",
                root / "state.sqlite3-shm",
                old_cache,
            ]
            saved: list[tuple[Path, Path]] = []
            for old in old_parts:
                if old.exists():
                    backup = root / f".restore-old-{stamp}-{old.name}"
                    old.replace(backup)
                    saved.append((old, backup))
            try:
                shutil.copy2(restored_state, old_state)
                _restrict_file(old_state)
                restored_cache = staging / "xml_cache"
                if restored_cache.is_dir():
                    shutil.copytree(restored_cache, old_cache, dirs_exist_ok=True)
                else:
                    old_cache.mkdir(parents=True, exist_ok=True)
                _chmod(old_cache, 0o700)
            except Exception:
                for new in (old_state, old_cache):
                    if new.is_dir():
                        shutil.rmtree(new, ignore_errors=True)
                    elif new.exists():
                        try:
                            new.unlink()
                        except OSError:
                            pass
                for original, backup in reversed(saved):
                    if backup.exists():
                        backup.replace(original)
                raise
            else:
                for _original, backup in saved:
                    if backup.is_dir():
                        shutil.rmtree(backup, ignore_errors=True)
                    elif backup.exists():
                        try:
                            backup.unlink()
                        except OSError:
                            pass

            files, size = cache_stats(root / "xml_cache")
            return {"documents": documents, "files": files, "bytes": size}
        finally:
            shutil.rmtree(staging, ignore_errors=True)


def record_run(
    connection: sqlite3.Connection,
    *,
    started_at: str,
    finished_at: str,
    state: str,
    environment: str,
    document_filter: str,
    cnpj_count: int,
    new_documents: int = 0,
    exported: int = 0,
    ignored: int = 0,
    failures: int = 0,
    period_start: str | None = None,
    period_end: str | None = None,
    emission_start: str | None = None,
    emission_end: str | None = None,
    no_cache: bool = False,
    zip_name: str = "",
) -> None:
    connection.execute(
        """
        INSERT INTO runs(
            started_at, finished_at, state, environment, document_filter,
            cnpj_count, new_documents, exported, ignored, failures,
            period_start, period_end, emission_start, emission_end, no_cache, zip_name
        ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            started_at,
            finished_at,
            state,
            environment,
            document_filter,
            int(cnpj_count),
            int(new_documents),
            int(exported),
            int(ignored),
            int(failures),
            period_start,
            period_end,
            emission_start,
            emission_end,
            int(no_cache),
            zip_name,
        ),
    )
    connection.commit()


def list_runs(connection: sqlite3.Connection, limit: int = 20) -> list[dict[str, Any]]:
    limit = max(1, min(int(limit), 100))
    rows = connection.execute(
        """
        SELECT id, started_at, finished_at, state, environment, document_filter,
               cnpj_count, new_documents, exported, ignored, failures,
               period_start, period_end, emission_start, emission_end, no_cache, zip_name
        FROM runs
        ORDER BY id DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    return [dict(row) for row in rows]


def human_bytes(size: int) -> str:
    value = float(size)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if value < 1024 or unit == "TB":
            return f"{value:.1f} {unit}" if unit != "B" else f"{int(value)} B"
        value /= 1024
    return f"{size} B"


# ---------------------------------------------------------------------------
# CNPJ (numérico e alfanumérico)
# ---------------------------------------------------------------------------

_CNPJ_STRIP = re.compile(r"[^0-9A-Z]")
_CNPJ_CANDIDATE = re.compile(
    r"[0-9A-Z]{2}[.\s]?[0-9A-Z]{3}[.\s]?[0-9A-Z]{3}[/\s]?[0-9A-Z]{4}-?[0-9]{2}",
    re.IGNORECASE,
)


def normalize_cnpj(value: str) -> str:
    """Mantém letras: o CNPJ alfanumérico existe desde 31/07/2026."""

    return _CNPJ_STRIP.sub("", (value or "").upper())


def valid_cnpj(value: str) -> bool:
    value = normalize_cnpj(value)
    if len(value) != 14 or value == value[0] * 14 or not value[12:].isdigit():
        return False

    def char_value(ch: str) -> int:
        return ord(ch) - 48  # 0-9; A=17 ... Z=42

    for pos, weights in (
        (12, (5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2)),
        (13, (6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2)),
    ):
        remainder = sum(char_value(ch) * weight for ch, weight in zip(value[:pos], weights)) % 11
        check = 0 if remainder < 2 else 11 - remainder
        if int(value[pos]) != check:
            return False
    return True


def parse_cnpj_text(text: str) -> tuple[list[str], list[str]]:
    """Aceita um por linha, CSV, com pontuação e o novo formato alfanumérico."""

    valid: list[str] = []
    invalid: list[str] = []
    for chunk in re.split(r"[,;\n]+", text or ""):
        chunk = chunk.strip()
        if not chunk:
            continue
        matches = _CNPJ_CANDIDATE.findall(chunk)
        tokens = matches or [chunk]
        for token in tokens:
            candidate = normalize_cnpj(token)
            if len(candidate) > 14:
                candidate = candidate[-14:]
            if valid_cnpj(candidate):
                if candidate not in valid:
                    valid.append(candidate)
            else:
                label = token.strip()[:40]
                if label and label not in invalid:
                    invalid.append(label)
    return valid, invalid


def mask_cnpj(value: str) -> str:
    normalized = normalize_cnpj(value)
    return f"***{normalized[-4:]}" if len(normalized) >= 4 else "***"


_CNPJ_TEXT = re.compile(
    r"(?<![0-9A-Z])([0-9A-Z]{2}\.?[0-9A-Z]{3}\.?[0-9A-Z]{3}/?[0-9A-Z]{4}-?\d{2})(?![0-9A-Z])",
    re.IGNORECASE,
)


def redact_sensitive(text: str) -> str:
    """Mascara CNPJs que possam aparecer em mensagens de erro da API."""

    def replace(match: re.Match[str]) -> str:
        candidate = normalize_cnpj(match.group(1))
        return mask_cnpj(candidate) if len(candidate) == 14 else match.group(0)

    return _CNPJ_TEXT.sub(replace, text or "")


# ---------------------------------------------------------------------------
# XML: competência, papéis e extração de documentos
# ---------------------------------------------------------------------------


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].lower()


def find_first(node: ET.Element | None, names: Iterable[str]) -> ET.Element | None:
    if node is None:
        return None
    wanted = {name.lower() for name in names}
    for element in node.iter():
        if local_name(element.tag) in wanted:
            return element
    return None


def find_all(node: ET.Element | None, names: Iterable[str]) -> list[ET.Element]:
    if node is None:
        return []
    wanted = {name.lower() for name in names}
    return [element for element in node.iter() if local_name(element.tag) in wanted]


def text_of(node: ET.Element | None, names: Iterable[str]) -> str:
    element = find_first(node, names)
    return (element.text or "").strip() if element is not None else ""


def _parse_competence(raw: str) -> str:
    raw = (raw or "").strip()
    if not raw:
        return "SemCompetencia"
    for date_format in ("%Y-%m-%d", "%Y%m%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(raw[:10], date_format).strftime("%Y-%m")
        except ValueError:
            continue
    match = re.match(r"(\d{4})-(\d{2})", raw)
    if match:
        return f"{match.group(1)}-{match.group(2)}"
    return "SemCompetencia"


def _parse_date(raw: str) -> str | None:
    """Converte a data completa do XML para YYYY-MM-DD."""

    raw = (raw or "").strip()
    if not raw:
        return None
    for date_format in ("%Y-%m-%d", "%Y%m%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(raw[:10], date_format).strftime("%Y-%m-%d")
        except ValueError:
            continue
    match = re.match(r"(\d{4})-(\d{2})-(\d{2})", raw)
    if match:
        return match.group(0)
    return None


def _range_bound(value: str | None, end: bool = False) -> str | None:
    """Normaliza AAAA-MM para o primeiro/último dia do mês."""

    if not value:
        return None
    return f"{value}-31" if end and len(value) == 7 else f"{value}-01" if len(value) == 7 else value


def date_in_range(value: str | None, start: str | None, end: str | None) -> bool:
    """Compara uma data, aceitando também competência no formato AAAA-MM."""

    if not start and not end:
        return True
    if not value:
        return False
    if len(value) == 7:
        if start and value < start[:7]:
            return False
        if end and value > end[:7]:
            return False
        return True
    start_bound = _range_bound(start)
    end_bound = _range_bound(end, end=True)
    if start_bound and value < start_bound:
        return False
    if end_bound and value > end_bound:
        return False
    return True


@dataclass(frozen=True)
class DocumentInfo:
    prestado: bool = False
    tomado: bool = False
    intermediario: bool = False
    event: bool = False
    competence: str = "SemCompetencia"
    competence_date: str | None = None
    emission_date: str | None = None


def classify_document(xml_data: bytes, cnpj: str) -> DocumentInfo:
    """Classifica papéis e datas pelo bloco explícito do XML."""

    root = ET.fromstring(xml_data)
    target = normalize_cnpj(cnpj)
    competence_element = find_first(root, ("dcompet", "competencia"))
    emission_element = find_first(
        root,
        ("dhemi", "demi", "dataemissao", "dhevento"),
    )
    competence_raw = (
        (competence_element.text or "") if competence_element is not None else ""
    )
    emission_raw = (
        (emission_element.text or "") if emission_element is not None else ""
    )
    competence = _parse_competence(competence_raw or emission_raw)
    competence_date = _parse_date(competence_raw) or _parse_date(emission_raw)
    emission_date = _parse_date(emission_raw) or competence_date

    event = False
    provider = False
    recipient = False
    intermediary = False
    provider_tags = {"prest", "prestador", "emit", "emitente"}
    recipient_tags = {"toma", "tomador", "dest", "destinatario"}
    intermediary_tags = {"interm", "intermediario"}
    event_tags = {"evt", "evtnfse", "pedregevento", "infevento", "e101101"}

    for element in root.iter():
        name = local_name(element.tag)
        if "evento" in name or "event" in name or name in event_tags:
            event = True
        if name not in provider_tags | recipient_tags | intermediary_tags:
            continue
        identifiers = {
            normalize_cnpj(child.text or "")
            for child in element.iter()
            if local_name(child.tag) in {"cnpj", "cpf"} and child.text
        }
        if target not in identifiers:
            continue
        if name in provider_tags:
            provider = True
        elif name in recipient_tags:
            recipient = True
        elif name in intermediary_tags:
            intermediary = True

    return DocumentInfo(
        prestado=provider,
        tomado=recipient,
        intermediario=intermediary,
        event=event,
        competence=competence,
        competence_date=competence_date,
        emission_date=emission_date,
    )


@dataclass(frozen=True)
class ExtractedDocument:
    label: str
    nsu: int | None
    data: bytes
    digest: str


def _strip_xml_prefix(data: bytes) -> bytes:
    return data.lstrip(b"\xef\xbb\xbf\x00\r\n \t")


def _valid_xml(data: bytes) -> bool:
    try:
        ET.fromstring(data)
        return True
    except ET.ParseError:
        return False


def _decode_candidates(raw: Any) -> Iterator[bytes]:
    if isinstance(raw, bytes):
        yield raw
        try:
            yield gzip.decompress(raw)
        except (OSError, EOFError):
            pass
        return
    if not isinstance(raw, str):
        return
    text = raw.strip()
    if not text:
        return
    if text.startswith("<"):
        yield text.encode("utf-8")
        return
    compact = re.sub(r"\s+", "", text)
    try:
        decoded = base64.b64decode(compact, validate=True)
    except (ValueError, base64.binascii.Error):
        decoded = None
    if decoded is not None:
        yield decoded
        try:
            yield gzip.decompress(decoded)
        except (OSError, EOFError):
            pass
    try:
        yield text.encode("utf-8")
    except UnicodeEncodeError:
        return


def decode_document(raw: Any) -> bytes | None:
    for candidate in _decode_candidates(raw):
        data = _strip_xml_prefix(candidate)
        if data.startswith(b"<") and _valid_xml(data):
            return data
    return None


def _norm_key(key: str) -> str:
    return re.sub(r"[^a-z]", "", key.lower())


def extract_xml_documents(payload: object, default_label: str = "documento", default_nsu: int | None = None) -> list[ExtractedDocument]:
    """Fallback para envelopes JSON que não sejam o LoteDFe documentado."""

    found: list[ExtractedDocument] = []
    seen: set[str] = set()

    def consider(raw: Any, label: str, nsu: int | None) -> None:
        data = decode_document(raw)
        if data is None:
            return
        digest = hashlib.sha256(data).hexdigest()
        if digest in seen:
            return
        seen.add(digest)
        found.append(ExtractedDocument(label=label, nsu=nsu, data=data, digest=digest))

    def walk(node: object, label: str, nsu: int | None) -> None:
        if isinstance(node, dict):
            local_nsu = nsu
            for key, value in node.items():
                if _norm_key(str(key)) in NSU_KEYS and isinstance(value, (str, int)):
                    try:
                        local_nsu = int(value)
                    except (TypeError, ValueError):
                        pass
            for key, value in node.items():
                name = str(key)
                if isinstance(value, str):
                    consider(value, name, local_nsu)
                else:
                    walk(value, name, local_nsu)
        elif isinstance(node, list):
            for item in node:
                walk(item, label, nsu)
        elif isinstance(node, str):
            consider(node, label, nsu)

    walk(payload, default_label, default_nsu)
    return found


def nsu_values(payload: object) -> list[int]:
    values: list[int] = []

    def walk(node: object) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                if _norm_key(str(key)) in NSU_KEYS:
                    try:
                        values.append(int(value))
                    except (TypeError, ValueError):
                        pass
                walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(payload)
    return values


# ---------------------------------------------------------------------------
# Certificado e cliente ADN
# ---------------------------------------------------------------------------


def cleanup_stale_tls_dirs(max_age_seconds: int = 24 * 3600) -> None:
    root = Path(tempfile.gettempdir())
    cutoff = time.time() - max_age_seconds
    for path in root.glob("nfse_tls_*"):
        try:
            if path.is_dir() and path.stat().st_mtime < cutoff:
                shutil.rmtree(path, ignore_errors=True)
        except OSError:
            continue


class CertificatePair:
    """Mantém o PFX em memória e expõe um PEM temporário para o requests.

    O PFX nunca é gravado. O PEM com a chave existe apenas durante a
    chamada, em diretório 0700 e arquivo 0600, e é removido no finally.
    """

    def __init__(self, pfx_bytes: bytes, password: str):
        self.pfx_bytes = pfx_bytes
        self.password = password
        self.directory: Path | None = None
        self.path: str | None = None
        self.not_after: datetime | None = None

    def __enter__(self) -> str:
        try:
            key, cert, chain = load_key_and_certificates(
                self.pfx_bytes, self.password.encode("utf-8") or None
            )
        except Exception as exc:
            raise CertificateError(
                "Não foi possível abrir o PFX. Confira o arquivo e a senha."
            ) from exc
        if key is None or cert is None:
            raise CertificateError(
                "O PFX não contém certificado e chave privada utilizáveis."
            )
        # O material do PFX não é mais necessário; reduz a vida útil em memória.
        self.pfx_bytes = b""
        self.password = ""
        self.not_after = getattr(cert, "not_valid_after_utc", None) or getattr(
            cert, "not_valid_after", None
        )

        self.directory = Path(tempfile.mkdtemp(prefix="nfse_tls_"))
        _chmod(self.directory, 0o700)
        pem = self.directory / "client.pem"
        data = key.private_bytes(Encoding.PEM, PrivateFormat.PKCS8, NoEncryption())
        data += cert.public_bytes(Encoding.PEM)
        for item in chain or []:
            data += item.public_bytes(Encoding.PEM)

        try:
            fd = os.open(pem, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "wb") as handle:
                handle.write(data)
            _restrict_file(pem)
        except Exception:
            self._cleanup()
            raise
        self.path = str(pem)
        return self.path

    def __exit__(self, *_: object) -> None:
        self._cleanup()

    def _cleanup(self) -> None:
        if self.directory is not None:
            shutil.rmtree(self.directory, ignore_errors=True)
            self.directory = None


def _get_case_insensitive(payload: dict[str, Any], name: str) -> Any:
    wanted = name.lower()
    for key, value in payload.items():
        if str(key).lower() == wanted:
            return value
    return None


def _as_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if value is None:
        return []
    return [value]


def _truncate(text: str, limit: int = 500) -> str:
    text = re.sub(r"\s+", " ", text or "").strip()
    return text if len(text) <= limit else text[: limit - 1] + "…"


def describe_api_error(status_code: int, payload: Any = None, body: str = "") -> str:
    details = f"HTTP {status_code}"
    errors: list[str] = []

    def walk(node: object) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                name = str(key).lower()
                if name in {"erros", "error", "errors"}:
                    for item in _as_list(value):
                        if isinstance(item, dict):
                            code = item.get("Codigo", item.get("codigo", ""))
                            description = item.get(
                                "Descricao", item.get("descricao", item.get("Complemento", ""))
                            )
                            text = ": ".join(str(part) for part in (code, description) if part)
                            if text:
                                errors.append(text)
                        elif item:
                            errors.append(str(item))
                else:
                    walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(payload)
    if errors:
        details += ": " + "; ".join(dict.fromkeys(errors))
    elif body:
        details += ": " + _truncate(body)
    return details


@dataclass
class Batch:
    documents: list[ExtractedDocument]
    last_nsu: int
    status: str = ""
    alerts: list[str] = field(default_factory=list)
    query_type: str = ""


class NfseClient:
    def __init__(
        self,
        base_url: str,
        cert_path: str,
        log: Callable[[str], None],
        session: Any | None = None,
        timeout: tuple[int, int] = (20, 90),
        max_retries: int = 5,
        should_stop: Callable[[], bool] | None = None,
        delay: float = PAGE_DELAY_DEFAULT,
    ):
        self.base_url = base_url.rstrip("/")
        self.cert_path = cert_path
        self.log = log
        self.timeout = timeout
        self.max_retries = max_retries
        self.should_stop = should_stop
        self.delay = delay
        self._owns_session = session is None
        self.session = session or requests.Session()
        self.session.cert = cert_path
        headers = getattr(self.session, "headers", None)
        if headers is not None:
            headers.update(
                {
                    "Accept": "application/json, application/xml, */*",
                    "User-Agent": f"{APP_NAME}/{APP_VERSION}",
                }
            )

    def close(self) -> None:
        if self._owns_session:
            try:
                self.session.close()
            except Exception:
                pass

    def _check_cancelled(self) -> None:
        if self.should_stop and self.should_stop():
            raise JobCancelled("Execução cancelada pelo usuário.")

    def _sleep(self, seconds: float) -> None:
        deadline = time.monotonic() + max(0.0, seconds)
        while time.monotonic() < deadline:
            self._check_cancelled()
            time.sleep(min(0.5, max(0.0, deadline - time.monotonic())))

    def _request(self, url: str, params: dict[str, str]) -> requests.Response:
        last_error = ""
        for attempt in range(self.max_retries + 1):
            self._check_cancelled()
            try:
                response = self.session.get(url, params=params, timeout=self.timeout)
            except requests.RequestException as exc:
                last_error = str(exc)
                if attempt >= self.max_retries:
                    raise TransientApiError(
                        f"Falha de conexão com o ADN após {attempt + 1} tentativas: {last_error}"
                    ) from exc
                wait = min(30.0, (1.6 ** attempt) + random.uniform(0, 0.4))
                self.log(f"Falha de conexão; nova tentativa em {wait:.1f}s.")
                self._sleep(wait)
                continue

            if response.status_code in {408, 429, 500, 502, 503, 504}:
                retry_after = response.headers.get("Retry-After", "")
                try:
                    wait = min(60.0, float(retry_after))
                except (TypeError, ValueError):
                    wait = min(30.0, (1.6 ** attempt) + random.uniform(0, 0.4))
                if attempt >= self.max_retries:
                    response.close()
                    raise TransientApiError(
                        f"O ADN respondeu HTTP {response.status_code} após {attempt + 1} tentativas."
                    )
                self.log(
                    f"ADN respondeu HTTP {response.status_code}; nova tentativa em {wait:.1f}s."
                )
                response.close()
                self._sleep(wait)
                continue

            return response

        raise TransientApiError(last_error or "Falha temporária ao consultar o ADN.")

    def _payload(self, response: requests.Response) -> Any:
        content_type = response.headers.get("content-type", "").lower()
        if "json" in content_type or response.content.lstrip().startswith((b"{", b"[")):
            try:
                return response.json()
            except ValueError as exc:
                raise ApiError(
                    describe_api_error(response.status_code, None, response.text)
                    + " (JSON inválido)"
                ) from exc
        return response.content

    def _parse_lote(self, payload: dict[str, Any]) -> list[ExtractedDocument]:
        lote = _get_case_insensitive(payload, "LoteDFe")
        if isinstance(lote, dict):
            for key in ("Documentos", "documentos", "Lote", "lote"):
                if key in lote:
                    lote = lote[key]
                    break
        if not isinstance(lote, list):
            return []

        documents: list[ExtractedDocument] = []
        seen: set[str] = set()
        for item in lote:
            if not isinstance(item, dict):
                continue
            try:
                nsu = int(item.get("NSU", item.get("nsu")))
            except (TypeError, ValueError):
                nsu = None
            label = str(
                item.get("TipoDocumento")
                or item.get("tipoDocumento")
                or item.get("Tipo")
                or "documento"
            )
            raw = (
                item.get("ArquivoXml")
                or item.get("arquivoXml")
                or item.get("XML")
                or item.get("xml")
            )
            data = decode_document(raw) if raw is not None else None
            if data is None:
                nested = extract_xml_documents(item, label, nsu)
                for document in nested:
                    if document.digest not in seen:
                        seen.add(document.digest)
                        documents.append(document)
                continue
            digest = hashlib.sha256(data).hexdigest()
            if digest in seen:
                continue
            seen.add(digest)
            documents.append(ExtractedDocument(label=label, nsu=nsu, data=data, digest=digest))
        return documents

    def fetch_batch(self, cnpj: str, cursor: int) -> Batch:
        url = f"{self.base_url}/DFe/{cursor}"
        params = {"cnpjConsulta": cnpj, "lote": "true"}
        response = self._request(url, params)

        if response.status_code == 204:
            raise NoDocuments(f"Sem documentos a partir do NSU {cursor}.")

        payload = self._payload(response)
        if not isinstance(payload, dict):
            raise ApiError(
                describe_api_error(response.status_code, None, str(payload)[:500])
            )

        documents = self._parse_lote(payload)
        if not documents:
            documents = extract_xml_documents(payload)

        status = str(_get_case_insensitive(payload, "StatusProcessamento") or "").upper()
        errors = _as_list(_get_case_insensitive(payload, "Erros"))
        codes = {
            str(item.get("Codigo", item.get("codigo", ""))).upper()
            for item in errors
            if isinstance(item, dict)
        }
        no_documents = status == "NENHUM_DOCUMENTO_LOCALIZADO" and not documents
        known_no_document_codes = bool(codes) and codes <= NO_DOCUMENT_CODES

        if response.status_code == 404:
            only_known = not codes or codes <= NO_DOCUMENT_CODES
            if not documents and only_known and (no_documents or known_no_document_codes):
                raise NoDocuments(f"Sem documentos a partir do NSU {cursor}.")
            raise ApiError(
                describe_api_error(response.status_code, payload, response.text)
            )

        if response.status_code != 200:
            raise ApiError(
                describe_api_error(response.status_code, payload, response.text)
            )

        if errors:
            raise ApiError(describe_api_error(response.status_code, payload, response.text))

        if no_documents:
            raise NoDocuments(f"Sem documentos a partir do NSU {cursor}.")

        if not documents:
            if _get_case_insensitive(payload, "Erros") is not None:
                raise ApiError(
                    "A API retornou uma rejeição sem documentos e sem detalhes. "
                    "A execução foi interrompida para não fingir sucesso."
                )
            raise ApiError(
                "A API respondeu sem documentos e sem status de fim. "
                "A execução foi interrompida para não fingir sucesso."
            )

        last_nsu = max(
            [document.nsu for document in documents if document.nsu is not None]
            or [cursor + len(documents)]
        )
        if last_nsu <= cursor:
            raise ApiError(
                f"A API retornou um lote sem avanço de NSU (cursor {cursor}). "
                "Consulta interrompida para evitar loop."
            )

        alerts = [
            str(item.get("Descricao", item.get("descricao", item)))
            if isinstance(item, dict)
            else str(item)
            for item in _as_list(_get_case_insensitive(payload, "Alertas"))
        ]
        query_type = str(_get_case_insensitive(payload, "TipoConsulta") or "")
        return Batch(
            documents=documents,
            last_nsu=last_nsu,
            status=status,
            alerts=alerts,
            query_type=query_type,
        )


# ---------------------------------------------------------------------------
# Estado local, cache e exportação
# ---------------------------------------------------------------------------


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if os.name == "nt":
        try:
            import ctypes

            process_query_limited_information = 0x1000
            handle = ctypes.windll.kernel32.OpenProcess(
                process_query_limited_information, False, pid
            )
            if handle:
                ctypes.windll.kernel32.CloseHandle(handle)
                return True
            return False
        except Exception:
            return False
    try:
        os.kill(pid, 0)
        return True
    except (ProcessLookupError, OverflowError):
        return False
    except PermissionError:
        return True
    except OSError:
        return False


class RunLock:
    """Evita duas execuções simultâneas. Lock de processo morto é recuperado."""

    def __init__(self, path: Path | None = None):
        self.path = path or (data_dir() / "run.lock")
        self.acquired = False

    def _is_stale(self) -> bool:
        try:
            content = self.path.read_text(encoding="utf-8").split()
            pid = int(content[0])
            age = time.time() - self.path.stat().st_mtime
        except (OSError, ValueError, IndexError):
            return True
        if age > 24 * 3600:
            return True
        return not _pid_alive(pid)

    def __enter__(self) -> "RunLock":
        self.path.parent.mkdir(parents=True, exist_ok=True)
        for attempt in range(2):
            try:
                fd = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                with os.fdopen(fd, "w", encoding="utf-8") as handle:
                    handle.write(f"{os.getpid()} {time.time():.0f}\n")
                self.acquired = True
                return self
            except FileExistsError:
                if attempt == 0 and self._is_stale():
                    try:
                        self.path.unlink()
                    except OSError:
                        pass
                    continue
                raise NfseError(
                    "Já existe uma execução em andamento. Aguarde ou cancele a outra."
                )
        raise NfseError("Não foi possível adquirir o lock de execução.")

    def __exit__(self, *_: object) -> None:
        if self.acquired:
            try:
                self.path.unlink()
            except OSError:
                pass
            self.acquired = False


@dataclass
class RunPaths:
    root: Path
    cache: Path
    state: Path
    logs: Path
    exports: Path
    ephemeral: bool = False

    @classmethod
    def create(cls, ephemeral: bool = False) -> "RunPaths":
        if ephemeral:
            root = Path(tempfile.mkdtemp(prefix="nfse_run_"))
        else:
            root = data_dir()
        paths = cls(
            root=root,
            cache=root / "xml_cache",
            state=root / "state.sqlite3",
            logs=root / "logs",
            exports=root / "exports",
            ephemeral=ephemeral,
        )
        for directory in (paths.cache, paths.logs, paths.exports):
            directory.mkdir(parents=True, exist_ok=True)
            _chmod(directory, 0o700)
        return paths

    def cleanup(self) -> None:
        if self.ephemeral:
            shutil.rmtree(self.root, ignore_errors=True)


def connect_state(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(str(path), timeout=30)
    connection.row_factory = sqlite3.Row
    try:
        connection.execute("PRAGMA journal_mode=WAL")
    except sqlite3.DatabaseError:
        pass
    connection.execute("PRAGMA synchronous=NORMAL")
    connection.execute("PRAGMA busy_timeout=30000")
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS cursors (
            cnpj TEXT PRIMARY KEY,
            nsu INTEGER NOT NULL
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS documents (
            cnpj TEXT NOT NULL,
            digest TEXT NOT NULL,
            filename TEXT NOT NULL,
            nsu INTEGER,
            competence TEXT NOT NULL DEFAULT 'SemCompetencia',
            competence_date TEXT,
            emission_date TEXT,
            prestado INTEGER NOT NULL DEFAULT 0,
            tomado INTEGER NOT NULL DEFAULT 0,
            intermediario INTEGER NOT NULL DEFAULT 0,
            event INTEGER NOT NULL DEFAULT 0,
            first_seen TEXT NOT NULL,
            PRIMARY KEY (cnpj, digest)
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            started_at TEXT NOT NULL,
            finished_at TEXT NOT NULL,
            state TEXT NOT NULL,
            environment TEXT,
            document_filter TEXT,
            cnpj_count INTEGER NOT NULL DEFAULT 0,
            new_documents INTEGER NOT NULL DEFAULT 0,
            exported INTEGER NOT NULL DEFAULT 0,
            ignored INTEGER NOT NULL DEFAULT 0,
            failures INTEGER NOT NULL DEFAULT 0,
            period_start TEXT,
            period_end TEXT,
            emission_start TEXT,
            emission_end TEXT,
            no_cache INTEGER NOT NULL DEFAULT 0,
            zip_name TEXT
        )
        """
    )
    document_columns = {
        row[1] for row in connection.execute("PRAGMA table_info(documents)")
    }
    for column, definition in (
        ("competence_date", "TEXT"),
        ("emission_date", "TEXT"),
    ):
        if column not in document_columns:
            connection.execute(f"ALTER TABLE documents ADD COLUMN {column} {definition}")
    run_columns = {row[1] for row in connection.execute("PRAGMA table_info(runs)")}
    for column in ("emission_start", "emission_end"):
        if column not in run_columns:
            connection.execute(f"ALTER TABLE runs ADD COLUMN {column} TEXT")
    connection.commit()
    _restrict_file(path)
    return connection


def load_cursor(connection: sqlite3.Connection, cnpj: str) -> int:
    row = connection.execute(
        "SELECT nsu FROM cursors WHERE cnpj = ?", (cnpj,)
    ).fetchone()
    return int(row["nsu"]) if row else 0


def save_cursor(connection: sqlite3.Connection, cnpj: str, nsu: int) -> None:
    connection.execute(
        """
        INSERT INTO cursors(cnpj, nsu) VALUES(?, ?)
        ON CONFLICT(cnpj) DO UPDATE SET nsu = MAX(nsu, excluded.nsu)
        """,
        (cnpj, int(nsu)),
    )
    connection.commit()


def has_document(connection: sqlite3.Connection, cnpj: str, digest: str) -> bool:
    row = connection.execute(
        "SELECT 1 FROM documents WHERE cnpj = ? AND digest = ?", (cnpj, digest)
    ).fetchone()
    return row is not None


def record_document(
    connection: sqlite3.Connection,
    cnpj: str,
    digest: str,
    filename: str,
    nsu: int | None,
    info: DocumentInfo,
) -> None:
    connection.execute(
        """
        INSERT INTO documents(
            cnpj, digest, filename, nsu, competence, competence_date,
            emission_date, prestado, tomado, intermediario, event, first_seen
        ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(cnpj, digest) DO UPDATE SET
            filename = excluded.filename,
            nsu = COALESCE(excluded.nsu, documents.nsu),
            competence = excluded.competence,
            competence_date = COALESCE(excluded.competence_date, documents.competence_date),
            emission_date = COALESCE(excluded.emission_date, documents.emission_date),
            prestado = excluded.prestado,
            tomado = excluded.tomado,
            intermediario = excluded.intermediario,
            event = excluded.event
        """,
        (
            cnpj,
            digest,
            filename,
            nsu,
            info.competence,
            info.competence_date,
            info.emission_date,
            int(info.prestado),
            int(info.tomado),
            int(info.intermediario),
            int(info.event),
            datetime.now().isoformat(timespec="seconds"),
        ),
    )
    connection.commit()


def _safe_label(label: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_-]+", "_", label or "xml")[:24]
    return cleaned or "xml"


def document_filename(document: ExtractedDocument) -> str:
    if document.nsu is None:
        return f"{document.digest}.xml"
    return f"NSU_{document.nsu:015d}_{_safe_label(document.label)}_{document.digest[:12]}.xml"


def _write_atomic(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
        os.replace(temporary, path)
    finally:
        try:
            if temporary.exists():
                temporary.unlink()
        except OSError:
            pass
    _restrict_file(path)


def index_cache(
    connection: sqlite3.Connection,
    cache_root: Path,
    cnpjs: Sequence[str],
    log: Callable[[str], None] | None = None,
) -> int:
    """Importa XMLs antigos/novos que ainda não estejam no índice.

    Não relê arquivos já indexados; é o que evita a revarredura O(n) a cada
    execução que existia na versão anterior.
    """

    imported = 0
    for cnpj in cnpjs:
        folder = cache_root / cnpj
        if not folder.is_dir():
            continue
        existing = {
            row["filename"]
            for row in connection.execute(
                "SELECT filename FROM documents WHERE cnpj = ?", (cnpj,)
            )
        }
        for path in folder.glob("*.xml"):
            if path.name in existing:
                continue
            try:
                data = path.read_bytes()
                digest = hashlib.sha256(data).hexdigest()
                if has_document(connection, cnpj, digest):
                    continue
                try:
                    info = classify_document(data, cnpj)
                except (ET.ParseError, ValueError):
                    info = DocumentInfo()
                    if log:
                        log(f"XML inválido na cópia local: {path.name}")
                record_document(connection, cnpj, digest, path.name, None, info)
                imported += 1
            except OSError as exc:
                if log:
                    log(f"Não foi possível ler {path.name}: {exc}")
    return imported


@dataclass
class ClientResult:
    cnpj: str
    new_documents: int
    cursor: int
    error: str | None = None
    ignored: int = 0


def run_download(
    paths: RunPaths,
    client: NfseClient,
    cnpjs: Sequence[str],
    log: Callable[[str], None],
    should_stop: Callable[[], bool] | None = None,
    ephemeral: bool = False,
    max_pages: int = MAX_PAGES_DEFAULT,
    period_start: str | None = None,
    period_end: str | None = None,
    emission_start: str | None = None,
    emission_end: str | None = None,
    start_nsu: int = 0,
) -> list[ClientResult]:
    connection = connect_state(paths.state)
    results: list[ClientResult] = []
    try:
        for cnpj in cnpjs:
            if should_stop and should_stop():
                raise JobCancelled("Execução cancelada pelo usuário.")
            cursor = 0 if ephemeral else load_cursor(connection, cnpj)
            if cursor == 0 and start_nsu > 0:
                # O caminho /DFe/{NSU} é o último NSU processado; -1 inclui o inicial.
                cursor = max(0, start_nsu - 1)
                log(
                    f"Iniciando {mask_cnpj(cnpj)} pelo NSU inicial {start_nsu} "
                    "(documentos anteriores não serão consultados)."
                )
            new_documents = 0
            ignored = 0
            competence_active = bool(period_start or period_end)
            emission_active = bool(emission_start or emission_end)
            period_active = competence_active or emission_active
            if competence_active:
                log(
                    "Filtro de competência: "
                    f"{period_start or 'início'} a {period_end or 'fim'}."
                )
            if emission_active:
                log(
                    "Filtro de emissão: "
                    f"{emission_start or 'início'} a {emission_end or 'fim'}."
                )
            seen_cursors: set[int] = set()
            log(f"Iniciando {mask_cnpj(cnpj)} pelo NSU {cursor}.")
            try:
                for _ in range(max_pages):
                    if should_stop and should_stop():
                        raise JobCancelled("Execução cancelada pelo usuário.")
                    if cursor in seen_cursors:
                        log("A API repetiu o NSU; encerrando para evitar loop.")
                        break
                    seen_cursors.add(cursor)

                    try:
                        batch = client.fetch_batch(cnpj, cursor)
                    except NoDocuments:
                        log("Sem mais documentos a partir deste NSU.")
                        break

                    for alert in batch.alerts:
                        log(f"Alerta da API: {alert}")
                    if batch.query_type:
                        log(f"Tipo de autorização: {batch.query_type}")

                    documents = sorted(
                        batch.documents,
                        key=lambda item: (item.nsu is None, item.nsu or 0),
                    )
                    for document in documents:
                        if should_stop and should_stop():
                            raise JobCancelled("Execução cancelada pelo usuário.")
                        if document.nsu is not None and document.nsu <= cursor:
                            continue

                        try:
                            info = classify_document(document.data, cnpj)
                        except (ET.ParseError, ValueError):
                            info = DocumentInfo()
                            log(f"XML sem classificação: NSU {document.nsu or '?'}.")

                        outside_period = False
                        if competence_active:
                            outside_period = not date_in_range(
                                info.competence_date or info.competence,
                                period_start,
                                period_end,
                            )
                        if not outside_period and emission_active:
                            outside_period = not date_in_range(
                                info.emission_date,
                                emission_start,
                                emission_end,
                            )
                        if outside_period:
                            ignored += 1
                            if document.nsu is not None:
                                cursor = max(cursor, document.nsu)
                                if not ephemeral:
                                    save_cursor(connection, cnpj, cursor)
                            continue

                        filename = document_filename(document)
                        destination = paths.cache / cnpj / filename
                        is_new_file = not destination.exists()
                        if is_new_file:
                            _write_atomic(destination, document.data)
                        if not has_document(connection, cnpj, document.digest):
                            record_document(
                                connection,
                                cnpj,
                                document.digest,
                                filename,
                                document.nsu,
                                info,
                            )
                            new_documents += 1
                        if document.nsu is not None:
                            cursor = max(cursor, document.nsu)
                            if not ephemeral:
                                save_cursor(connection, cnpj, cursor)
                    if all(document.nsu is None for document in documents):
                        cursor = max(cursor, batch.last_nsu)
                        if not ephemeral:
                            save_cursor(connection, cnpj, cursor)
                    else:
                        cursor = max(cursor, batch.last_nsu)
                        if not ephemeral:
                            save_cursor(connection, cnpj, cursor)
                    log(
                        f"{mask_cnpj(cnpj)}: NSU {cursor}; "
                        f"{len(documents)} XML(s) nesta resposta; "
                        f"{ignored} fora do período (total)."
                    )
                    if not documents:
                        break
                    if batch.last_nsu <= cursor and not documents:
                        break
                    if client.delay:
                        time.sleep(client.delay)
                else:
                    log(
                        f"{mask_cnpj(cnpj)}: limite de {max_pages} páginas atingido; "
                        "execute novamente para continuar."
                    )
                log(
                    f"{mask_cnpj(cnpj)}: concluído; {new_documents} novo(s), "
                    f"{ignored} fora do período."
                )
                results.append(
                    ClientResult(
                        cnpj,
                        new_documents,
                        cursor,
                        ignored=ignored,
                    )
                )
            except JobCancelled:
                raise
            except Exception as exc:
                log(f"ERRO {mask_cnpj(cnpj)}: {exc}")
                results.append(
                    ClientResult(
                        cnpj,
                        new_documents,
                        cursor,
                        str(exc),
                        ignored,
                    )
                )
    finally:
        connection.close()
    return results


@dataclass
class ExportResult:
    zip_path: Path | None
    total: int
    categories: dict[str, int]
    clients: int

    @property
    def size(self) -> int:
        try:
            return self.zip_path.stat().st_size if self.zip_path else 0
        except OSError:
            return 0


def backfill_document_dates(
    connection: sqlite3.Connection,
    cache_root: Path,
    cnpjs: Sequence[str],
    log: Callable[[str], None] | None = None,
) -> int:
    """Preenche datas de XMLs indexados antes do filtro por emissão."""

    if not cnpjs:
        return 0
    placeholders = ",".join("?" for _ in cnpjs)
    rows = connection.execute(
        f"""
        SELECT cnpj, digest, filename
        FROM documents
        WHERE cnpj IN ({placeholders})
          AND (competence_date IS NULL OR emission_date IS NULL)
        """,
        tuple(cnpjs),
    ).fetchall()
    updated = 0
    for row in rows:
        cnpj = str(row["cnpj"])
        filename = str(row["filename"])
        path = cache_root / cnpj / filename
        try:
            data = path.read_bytes()
            info = classify_document(data, cnpj)
        except (OSError, ET.ParseError, ValueError):
            continue
        connection.execute(
            """
            UPDATE documents
            SET competence = ?, competence_date = ?, emission_date = ?
            WHERE cnpj = ? AND digest = ?
            """,
            (
                info.competence,
                info.competence_date,
                info.emission_date,
                cnpj,
                row["digest"],
            ),
        )
        updated += 1
    if updated:
        connection.commit()
        if log:
            log(f"{updated} XML(s) antigos atualizados com datas de competência/emissão.")
    return updated


def export_zip(
    connection: sqlite3.Connection,
    paths: RunPaths,
    cnpjs: Sequence[str],
    selected: str,
    zip_path: Path,
    log: Callable[[str], None] | None = None,
    period_start: str | None = None,
    period_end: str | None = None,
    emission_start: str | None = None,
    emission_end: str | None = None,
) -> ExportResult:
    if selected not in FILTERS:
        raise NfseError(f"Filtro inválido: {selected}")
    imported = index_cache(connection, paths.cache, cnpjs, log)
    if imported and log:
        log(f"{imported} XML(s) antigos indexados na cópia local.")
    if not cnpjs:
        return ExportResult(None, 0, {}, 0)
    if period_start or period_end or emission_start or emission_end:
        backfill_document_dates(connection, paths.cache, cnpjs, log)
    if log and (period_start or period_end):
        log(
            "Exportando competência de "
            f"{period_start or 'início'} a {period_end or 'fim'}."
        )
    if log and (emission_start or emission_end):
        log(
            "Exportando emissão de "
            f"{emission_start or 'início'} a {emission_end or 'fim'}."
        )

    placeholders = ",".join("?" for _ in cnpjs)
    rows = connection.execute(
        f"""
        SELECT cnpj, filename, competence, competence_date, emission_date,
               prestado, tomado, intermediario, event
        FROM documents
        WHERE cnpj IN ({placeholders})
        ORDER BY cnpj, competence, filename
        """,
        tuple(cnpjs),
    ).fetchall()

    categories: dict[str, int] = {}
    entries: list[tuple[Path, str]] = []
    for row in rows:
        if not date_in_range(
            row["competence_date"] or row["competence"],
            period_start,
            period_end,
        ):
            continue
        if not date_in_range(row["emission_date"], emission_start, emission_end):
            continue
        cnpj = str(row["cnpj"])
        filename = str(row["filename"])
        competence = re.sub(r"[^0-9A-Za-z_-]+", "_", str(row["competence"])) or "SemCompetencia"
        wanted: list[str] = []
        if row["event"]:
            wanted.append("Eventos")
        else:
            if row["prestado"] and selected in {"Prestados", "Ambas"}:
                wanted.append("Prestados")
            if row["tomado"] and selected in {"Tomados", "Ambas"}:
                wanted.append("Tomados")
            if selected == "Ambas" and not row["prestado"] and not row["tomado"]:
                wanted.append("Outros")
        source = paths.cache / cnpj / filename
        if not source.is_file():
            if log:
                log(f"XML ausente na cópia local: {cnpj}/{filename}")
            continue
        for category in wanted:
            entries.append((source, f"{cnpj}/{competence}/{category}/{filename}"))
            categories[category] = categories.get(category, 0) + 1

    if not entries:
        return ExportResult(None, 0, {}, 0)

    zip_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = zip_path.with_name(zip_path.name + ".tmp")
    try:
        with zipfile.ZipFile(temporary, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
            for source, arcname in entries:
                archive.write(source, arcname)
        os.replace(temporary, zip_path)
        _restrict_file(zip_path)
    finally:
        try:
            if temporary.exists():
                temporary.unlink()
        except OSError:
            pass

    return ExportResult(
        zip_path=zip_path,
        total=len(entries),
        categories=categories,
        clients=len({row["cnpj"] for row in rows}),
    )


def wipe_data(root: Path | None = None) -> tuple[int, int]:
    """Apaga cópia local, histórico, logs, ZIPs e configurações antigas."""

    root = root or data_dir()
    freed = 0
    removed = 0
    targets = [
        root / "xml_cache",
        root / "logs",
        root / "exports",
        root / "state.sqlite3",
        root / "state.sqlite3-wal",
        root / "state.sqlite3-shm",
        root / "settings.json",
    ]
    if not os.environ.get("NFSE_DATA_DIR") and root == data_dir():
        for old in _legacy_data_dirs():
            if old == root:
                continue
            targets.extend(
                [
                    old / "xml_cache",
                    old / "logs",
                    old / "exports",
                    old / "state.sqlite3",
                    old / "state.sqlite3-wal",
                    old / "state.sqlite3-shm",
                    old / "settings.json",
                ]
            )
    for target in targets:
        try:
            if target.is_dir():
                freed += sum(path.stat().st_size for path in target.rglob("*") if path.is_file())
                shutil.rmtree(target, ignore_errors=True)
                removed += 1
            elif target.exists():
                freed += target.stat().st_size
                target.unlink()
                removed += 1
        except OSError:
            continue
    return removed, freed


class RunLogger:
    def __init__(
        self,
        path: Path | None,
        callback: Callable[[str], None] | None = None,
    ):
        self.path = path
        self.callback = callback
        self.lock = threading.Lock()
        self.handle = None
        if path is not None:
            path.parent.mkdir(parents=True, exist_ok=True)
            self.handle = path.open("a", encoding="utf-8")
            _restrict_file(path)

    def log(self, message: str) -> None:
        line = f"{datetime.now():%Y-%m-%d %H:%M:%S} {redact_sensitive(message)}"
        with self.lock:
            if self.handle is not None:
                try:
                    self.handle.write(line + "\n")
                    self.handle.flush()
                except OSError:
                    pass
        if self.callback is not None:
            try:
                self.callback(line)
            except Exception:
                pass

    def close(self) -> None:
        if self.handle is not None:
            try:
                self.handle.close()
            except OSError:
                pass
            self.handle = None
