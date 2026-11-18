"""Servidor HTTP local (127.0.0.1) do Coleta XML NFSE.

Não há backend remoto, telemetria, CDN ou armazenamento de senha/PFX.
O servidor escuta apenas loopback e exige um token aleatório por processo.
"""

from __future__ import annotations

import base64
import html
import json
import os
import platform
import re
import secrets
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.parse
import webbrowser
from dataclasses import dataclass, field
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from . import core

MAX_BODY_BYTES = 12 * 1024 * 1024
MAX_PFX_BYTES = 5 * 1024 * 1024
MAX_CNPJS = 500
MAX_RESTORE_BYTES = 5 * 1024 * 1024 * 1024


def _safe_proxy(value: str) -> str:
    """Remove usuário e senha de uma URL de proxy exibida no diagnóstico."""

    if not value:
        return ""
    try:
        parsed = urllib.parse.urlsplit(value)
    except ValueError:
        return "(valor inválido)"
    if not parsed.username and not parsed.password:
        return value
    host = parsed.hostname or ""
    if parsed.port:
        host = f"{host}:{parsed.port}"
    return urllib.parse.urlunsplit(
        (parsed.scheme, host, parsed.path, parsed.query, parsed.fragment)
    )


def build_diagnostics() -> dict[str, Any]:
    cache_files, cache_bytes = core.cache_stats()
    state = core.data_dir() / "state.sqlite3"
    proxy = {
        name: _safe_proxy(os.environ.get(name, ""))
        for name in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "NO_PROXY")
    }
    adn_host = urllib.parse.urlsplit(core.PRODUCTION).hostname or "adn.nfse.gov.br"
    dns: dict[str, Any] = {"ok": False, "addresses": [], "error": ""}
    tcp: dict[str, Any] = {"ok": False, "ms": None, "error": ""}
    try:
        addresses = sorted(
            {
                item[4][0]
                for item in socket.getaddrinfo(adn_host, 443, type=socket.SOCK_STREAM)
            }
        )
        dns = {"ok": bool(addresses), "addresses": addresses, "error": ""}
    except OSError as exc:
        dns["error"] = str(exc)
    if dns["ok"]:
        started = time.monotonic()
        try:
            with socket.create_connection((adn_host, 443), timeout=4):
                tcp = {
                    "ok": True,
                    "ms": round((time.monotonic() - started) * 1000),
                    "error": "",
                }
        except OSError as exc:
            tcp["error"] = str(exc)
    dependencies: dict[str, str] = {}
    try:
        import requests

        dependencies["requests"] = requests.__version__
    except ImportError:
        dependencies["requests"] = "ausente"
    try:
        import cryptography

        dependencies["cryptography"] = cryptography.__version__
    except ImportError:
        dependencies["cryptography"] = "ausente"
    return {
        "app": core.APP_DISPLAY_NAME,
        "version": core.APP_VERSION,
        "python": platform.python_version(),
        "platform": platform.platform(),
        "data_dir": str(core.data_dir()),
        "state_bytes": state.stat().st_size if state.is_file() else 0,
        "cache_files": cache_files,
        "cache_bytes": cache_bytes,
        "dependencies": dependencies,
        "proxy": proxy,
        "adn": {"host": adn_host, "dns": dns, "tcp": tcp},
        "certificate": "Validado durante a execução com o PFX selecionado.",
    }

COLLECTOR_CSP = (
    "default-src 'none'; script-src 'self'; style-src 'self'; "
    "img-src 'self' data:; font-src 'self'; connect-src 'self'; "
    "worker-src 'self'; manifest-src 'self'; base-uri 'none'; "
    "form-action 'none'; frame-ancestors 'none'"
)
READER_CSP = (
    "default-src 'none'; script-src 'self' 'unsafe-inline'; "
    "style-src 'self' 'unsafe-inline'; img-src 'self' data:; "
    "font-src 'self'; connect-src 'none'; base-uri 'none'; "
    "form-action 'none'; frame-ancestors 'none'"
)


class BusyError(RuntimeError):
    pass


def web_dir() -> Path:
    if getattr(sys, "frozen", False):
        base = Path(getattr(sys, "_MEIPASS"))
        return base / "web"
    candidates = [
        Path(__file__).resolve().parent.parent / "web",
        Path.cwd() / "web",
    ]
    for candidate in candidates:
        if (candidate / "index.html").is_file():
            return candidate
    return candidates[0]


def _period_value(value: Any, label: str = "Competência") -> str | None:
    """Aceita AAAA-MM (compatibilidade) ou AAAA-MM-DD para competência."""

    text = str(value or "").strip()
    if not text:
        return None
    if re.fullmatch(r"\d{4}-\d{2}", text):
        try:
            datetime.strptime(text, "%Y-%m")
        except ValueError as exc:
            raise ValueError(f"{label} inválida. Use AAAA-MM ou AAAA-MM-DD.") from exc
        return text
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
        try:
            datetime.strptime(text, "%Y-%m-%d")
        except ValueError as exc:
            raise ValueError(f"{label} inválida. Use AAAA-MM-DD.") from exc
        return text
    raise ValueError(f"{label} inválida. Use AAAA-MM ou AAAA-MM-DD.")


def _day_value(value: Any, label: str = "Data de emissão") -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
        raise ValueError(f"{label} inválida. Use AAAA-MM-DD.")
    try:
        datetime.strptime(text, "%Y-%m-%d")
    except ValueError as exc:
        raise ValueError(f"{label} inválida. Use AAAA-MM-DD.") from exc
    return text


@dataclass
class WebRunConfig:
    pfx_bytes: bytes
    password: str
    cnpjs: list[str]
    environment: str
    document_filter: str
    ephemeral: bool
    period_start: str | None = None
    period_end: str | None = None
    emission_start: str | None = None
    emission_end: str | None = None
    start_nsu: int = 0

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "WebRunConfig":
        raw_pfx = payload.get("pfx_base64")
        if not isinstance(raw_pfx, str) or not raw_pfx.strip():
            raise ValueError("Selecione o certificado A1 (.pfx/.p12).")
        try:
            pfx_bytes = base64.b64decode(raw_pfx, validate=True)
        except (ValueError, base64.binascii.Error) as exc:
            raise ValueError("O certificado enviado não é um base64 válido.") from exc
        if not pfx_bytes or len(pfx_bytes) > MAX_PFX_BYTES:
            raise ValueError("O certificado está vazio ou é grande demais.")

        password = payload.get("password")
        if not isinstance(password, str) or not password:
            raise ValueError("Informe a senha do certificado.")
        if len(password) > 512:
            raise ValueError("Senha do certificado inválida.")

        raw_cnpjs = payload.get("cnpjs")
        if isinstance(raw_cnpjs, list):
            cnpj_text = "\n".join(str(item) for item in raw_cnpjs)
        else:
            cnpj_text = str(raw_cnpjs or "")
        valid, invalid = core.parse_cnpj_text(cnpj_text)
        if invalid:
            raise ValueError("CNPJs inválidos: " + ", ".join(invalid[:8]))
        if not valid:
            raise ValueError("Informe ao menos um CNPJ válido.")
        if len(valid) > MAX_CNPJS:
            raise ValueError(f"Informe no máximo {MAX_CNPJS} CNPJs por execução.")

        environment = str(payload.get("environment") or "producao")
        if environment not in core.ENVIRONMENTS:
            raise ValueError("Ambiente inválido.")
        document_filter = str(payload.get("document_filter") or "Ambas")
        if document_filter not in core.FILTERS:
            raise ValueError("Filtro de notas inválido.")
        no_cache_raw = payload.get("no_cache", False)
        if not isinstance(no_cache_raw, bool):
            raise ValueError("O campo 'no_cache' deve ser booleano.")
        ephemeral = no_cache_raw

        period_start = _period_value(payload.get("period_start"))
        period_end = _period_value(payload.get("period_end"))
        emission_start = _day_value(payload.get("emission_start"))
        emission_end = _day_value(payload.get("emission_end"))
        if (period_start is None) != (period_end is None):
            raise ValueError("Informe o início e o fim do período de competência.")
        if period_start and period_end and period_start > period_end:
            raise ValueError("A competência inicial não pode ser depois da final.")
        if (emission_start is None) != (emission_end is None):
            raise ValueError("Informe o início e o fim da emissão.")
        if emission_start and emission_end and emission_start > emission_end:
            raise ValueError("A emissão inicial não pode ser depois da final.")

        try:
            start_nsu = int(payload.get("start_nsu") or 0)
        except (TypeError, ValueError) as exc:
            raise ValueError("NSU inicial inválido.") from exc
        if start_nsu < 0:
            raise ValueError("O NSU inicial não pode ser negativo.")

        return cls(
            pfx_bytes=pfx_bytes,
            password=password,
            cnpjs=valid,
            environment=environment,
            document_filter=document_filter,
            ephemeral=ephemeral,
            period_start=period_start,
            period_end=period_end,
            emission_start=emission_start,
            emission_end=emission_end,
            start_nsu=start_nsu,
        )


@dataclass
class Job:
    id: str
    state: str = "running"
    logs: list[str] = field(default_factory=list)
    result: dict[str, Any] | None = None
    error: str | None = None
    started_at: float = field(default_factory=time.time)
    finished_at: float | None = None
    cancel_event: threading.Event = field(default_factory=threading.Event)
    zip_path: Path | None = None
    zip_name: str = ""
    lock: threading.Lock = field(default_factory=threading.Lock)

    def add_log(self, line: str) -> None:
        with self.lock:
            self.logs.append(line)
            if len(self.logs) > 2000:
                del self.logs[: len(self.logs) - 2000]

    def set_state(self, state: str) -> None:
        with self.lock:
            self.state = state

    def snapshot(self) -> dict[str, Any]:
        with self.lock:
            return {
                "id": self.id,
                "state": self.state,
                "logs": list(self.logs),
                "result": self.result,
                "error": self.error,
                "started_at": self.started_at,
                "finished_at": self.finished_at,
            }


class JobManager:
    def __init__(self):
        self._lock = threading.Lock()
        self.job: Job | None = None
        self.cache_files = 0
        self.cache_bytes = 0
        self._update_stats()

    def _update_stats(self) -> None:
        self.cache_files, self.cache_bytes = core.cache_stats()

    def current(self) -> Job | None:
        with self._lock:
            return self.job

    def start(self, config: WebRunConfig) -> Job:
        with self._lock:
            if self.job is not None and self.job.state == "running":
                raise BusyError("Já existe uma execução em andamento.")
            if (
                self.job is not None
                and self.job.zip_path is not None
                and self.job.result
                and self.job.result.get("no_cache")
            ):
                try:
                    self.job.zip_path.unlink()
                except OSError:
                    pass
            job = Job(id=secrets.token_hex(8))
            self.job = job
            thread = threading.Thread(target=self._run, args=(job, config), daemon=True)
            thread.start()
            return job

    def _run(self, job: Job, config: WebRunConfig) -> None:
        paths: core.RunPaths | None = None
        logger: core.RunLogger | None = None
        zip_path: Path | None = None
        try:
            core.cleanup_stale_tls_dirs()
            with core.RunLock(core.data_dir() / "run.lock"):
                paths = core.RunPaths.create(ephemeral=config.ephemeral)
                log_path = (
                    None
                    if config.ephemeral
                    else paths.logs / f"execucao_{datetime.now():%Y%m%d_%H%M%S}.log"
                )
                logger = core.RunLogger(log_path, job.add_log)
                logger.log(
                    "Iniciando execução local. "
                    f"Ambiente: {config.environment}; filtro: {config.document_filter}; "
                    f"CNPJs: {len(config.cnpjs)}; sem cópia local: {'sim' if config.ephemeral else 'não'}; "
                    f"competência: {config.period_start or 'todo o período'} a "
                    f"{config.period_end or 'fim'}; emissão: "
                    f"{config.emission_start or 'todo o período'} a "
                    f"{config.emission_end or 'fim'}; NSU inicial: "
                    f"{config.start_nsu or 'automático'}."
                )
                certificate = core.CertificatePair(config.pfx_bytes, config.password)
                with certificate as pem:
                    config.pfx_bytes = b""
                    config.password = ""
                    if certificate.not_after is not None:
                        logger.log(
                            "Certificado válido até "
                            f"{certificate.not_after.strftime('%d/%m/%Y')}."
                        )
                    client = core.NfseClient(
                        core.ENVIRONMENTS[config.environment],
                        pem,
                        logger.log,
                        should_stop=job.cancel_event.is_set,
                    )
                    try:
                        results = core.run_download(
                            paths,
                            client,
                            config.cnpjs,
                            logger.log,
                            should_stop=job.cancel_event.is_set,
                            ephemeral=config.ephemeral,
                            period_start=config.period_start,
                            period_end=config.period_end,
                            emission_start=config.emission_start,
                            emission_end=config.emission_end,
                            start_nsu=config.start_nsu,
                        )
                    finally:
                        client.close()

                connection = core.connect_state(paths.state)
                try:
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    zip_name = f"Coleta_XML_NFSE_{config.document_filter}_{timestamp}.zip"
                    if config.ephemeral:
                        fd, temp_name = tempfile.mkstemp(prefix="nfse_export_", suffix=".zip")
                        os.close(fd)
                        zip_path = Path(temp_name)
                    else:
                        zip_path = paths.exports / zip_name
                    export = core.export_zip(
                        connection,
                        paths,
                        config.cnpjs,
                        config.document_filter,
                        zip_path,
                        logger.log,
                        period_start=config.period_start,
                        period_end=config.period_end,
                        emission_start=config.emission_start,
                        emission_end=config.emission_end,
                    )
                finally:
                    connection.close()

                if export.zip_path is None:
                    try:
                        if zip_path is not None and zip_path.exists():
                            zip_path.unlink()
                    except OSError:
                        pass
                zip_path = export.zip_path
                job.zip_path = zip_path
                job.zip_name = zip_path.name if zip_path is not None else ""
                failures = [
                    {
                        "cnpj": core.mask_cnpj(item.cnpj),
                        "error": core.redact_sensitive(item.error or ""),
                    }
                    for item in results
                    if item.error
                ]
                ignored = sum(item.ignored for item in results)
                job.result = {
                    "new_documents": sum(item.new_documents for item in results),
                    "ignored": ignored,
                    "exported": export.total,
                    "categories": export.categories,
                    "clients": [
                        {
                            "cnpj": core.mask_cnpj(item.cnpj),
                            "new": item.new_documents,
                            "ignored": item.ignored,
                            "cursor": item.cursor,
                            "error": (
                                core.redact_sensitive(item.error)
                                if item.error
                                else None
                            ),
                        }
                        for item in results
                    ],
                    "failures": failures,
                    "has_zip": export.zip_path is not None,
                    "zip_name": job.zip_name,
                    "no_cache": config.ephemeral,
                    "period_start": config.period_start,
                    "period_end": config.period_end,
                    "emission_start": config.emission_start,
                    "emission_end": config.emission_end,
                    "start_nsu": config.start_nsu,
                    "certificate_not_after": (
                        certificate.not_after.date().isoformat()
                        if certificate.not_after is not None
                        else None
                    ),
                    "data_dir": str(core.data_dir())
                    if not config.ephemeral
                    else "temporário (apagado ao final)",
                }
                if job.cancel_event.is_set():
                    logger.log("Execução cancelada pelo usuário.")
                    job.set_state("cancelled")
                else:
                    logger.log(
                        f"Concluído: {job.result['new_documents']} novo(s); "
                        f"{ignored} fora do período; "
                        f"{export.total} XML(s) no filtro {config.document_filter}; "
                        f"{len(failures)} cliente(s) com erro."
                    )
                    job.set_state("done")
        except core.JobCancelled:
            job.set_state("cancelled")
            job.error = "Execução cancelada."
            job.add_log("Execução cancelada.")
        except Exception as exc:
            job.set_state("error")
            job.error = core.redact_sensitive(str(exc))
            job.add_log(f"ERRO: {job.error}")
        finally:
            if logger is not None:
                logger.close()
            if paths is not None:
                paths.cleanup()
            with job.lock:
                job.finished_at = time.time()
            if not config.ephemeral:
                self._record_run(job, config)
            self._update_stats()

    def _record_run(self, job: Job, config: WebRunConfig) -> None:
        result = job.result or {}
        try:
            connection = core.connect_state(core.data_dir() / "state.sqlite3")
            try:
                core.record_run(
                    connection,
                    started_at=datetime.fromtimestamp(job.started_at).isoformat(
                        timespec="seconds"
                    ),
                    finished_at=datetime.fromtimestamp(
                        job.finished_at or time.time()
                    ).isoformat(timespec="seconds"),
                    state=job.state,
                    environment=config.environment,
                    document_filter=config.document_filter,
                    cnpj_count=len(config.cnpjs),
                    new_documents=int(result.get("new_documents") or 0),
                    exported=int(result.get("exported") or 0),
                    ignored=int(result.get("ignored") or 0),
                    failures=len(result.get("failures") or []),
                    period_start=config.period_start,
                    period_end=config.period_end,
                    emission_start=config.emission_start,
                    emission_end=config.emission_end,
                    no_cache=config.ephemeral,
                    zip_name=job.zip_name,
                )
            finally:
                connection.close()
        except Exception as exc:
            job.add_log(f"Não foi possível registrar o histórico: {exc}")

    def cancel(self) -> bool:
        job = self.current()
        if job is None or job.state != "running":
            return False
        job.cancel_event.set()
        job.add_log("Cancelamento solicitado; aguardando a etapa atual terminar.")
        return True

    def _ensure_idle(self, action: str) -> None:
        with self._lock:
            if self.job is not None and self.job.state == "running":
                raise BusyError(f"Cancele a execução antes de {action}.")

    def history(self, limit: int = 20) -> list[dict[str, Any]]:
        connection = core.connect_state(core.data_dir() / "state.sqlite3")
        try:
            return core.list_runs(connection, limit)
        finally:
            connection.close()

    def cache(self) -> list[dict[str, Any]]:
        return core.cache_clients()

    def clear_cache(self, cnpj: str) -> dict[str, Any]:
        self._ensure_idle("apagar a cópia local.")
        result = core.clear_cnpj_cache(cnpj)
        self._update_stats()
        return result

    def create_backup(self) -> Path:
        self._ensure_idle("criar o backup.")
        return core.create_cache_backup()

    def restore_backup(self, archive: Path) -> dict[str, Any]:
        self._ensure_idle("restaurar o backup.")
        result = core.restore_cache_backup(archive)
        self._update_stats()
        return result

    def diagnostics(self) -> dict[str, Any]:
        return build_diagnostics()

    def wipe(self) -> dict[str, Any]:
        with self._lock:
            if self.job is not None and self.job.state == "running":
                raise BusyError("Cancele a execução antes de apagar os dados.")
            if self.job is not None and self.job.zip_path is not None:
                try:
                    self.job.zip_path.unlink()
                except OSError:
                    pass
            removed, freed = core.wipe_data()
            self.job = None
            self._update_stats()
            return {"removed": removed, "freed": freed}

    def reveal(self) -> None:
        _open_in_file_manager(core.data_dir())

    def status(self) -> dict[str, Any]:
        with self._lock:
            job = self.job
        payload: dict[str, Any] = {
            "state": "idle",
            "logs": [],
            "result": None,
            "error": None,
            "version": core.APP_VERSION,
            "data_dir": str(core.data_dir()),
            "cache_files": self.cache_files,
            "cache_bytes": self.cache_bytes,
            "platform": sys.platform,
        }
        if job is not None:
            payload.update(job.snapshot())
        return payload

    def download(self) -> tuple[Path, str] | None:
        job = self.current()
        if job is None or job.state == "running" or job.zip_path is None:
            return None
        if not job.zip_path.is_file():
            return None
        return job.zip_path, job.zip_name

    def close(self) -> None:
        """Remove o ZIP temporário do modo sem cópia local ao encerrar."""

        with self._lock:
            job = self.job
            if job is None or job.zip_path is None:
                return
            if job.result and job.result.get("no_cache"):
                try:
                    job.zip_path.unlink()
                except OSError:
                    pass


def _open_in_file_manager(path: Path) -> None:
    try:
        if sys.platform == "win32":
            os.startfile(path)  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(path)])
        else:
            subprocess.Popen(["xdg-open", str(path)])
    except Exception:
        pass


class NFSEHandler(BaseHTTPRequestHandler):
    app_token = ""
    job_manager: JobManager
    server_version = "NFSeLocal"
    sys_version = ""
    protocol_version = "HTTP/1.0"
    head_only = False

    # ---- utilidades -----------------------------------------------------

    def log_message(self, format: str, *args: Any) -> None:
        # O polling de status é frequente; não polui o terminal.
        path = urllib.parse.urlsplit(getattr(self, "path", "")).path
        if path in {"/api/status", "/api/health", "/api/download"}:
            return
        try:
            sys.stderr.write(f"[local] {getattr(self, 'command', '')} {path}\n")
        except Exception:
            pass

    def _server_port(self) -> int:
        return int(self.server.server_address[1])

    def _check_host(self) -> bool:
        host = self.headers.get("Host", "")
        port = self._server_port()
        allowed = {
            f"127.0.0.1:{port}",
            f"localhost:{port}",
            "127.0.0.1",
            "localhost",
        }
        if host not in allowed:
            self._send_json(403, {"error": "Host não autorizado."})
            return False
        return True

    def _check_origin(self) -> bool:
        origin = self.headers.get("Origin")
        if not origin:
            return True
        port = self._server_port()
        allowed = {
            f"http://127.0.0.1:{port}",
            f"http://localhost:{port}",
        }
        if origin not in allowed:
            self._send_json(403, {"error": "Origem não autorizada."})
            return False
        return True

    def _token_ok(self) -> bool:
        provided = self.headers.get("X-NFSE-Token", "")
        if not provided:
            query = urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)
            provided = (query.get("token") or [""])[0]
        if not self.app_token:
            return False
        try:
            return secrets.compare_digest(provided, self.app_token)
        except TypeError:
            return False

    def _common_headers(self, csp: str) -> None:
        self.send_header("Cache-Control", "no-store")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Content-Security-Policy", csp)
        self.send_header(
            "Permissions-Policy",
            "camera=(), microphone=(), geolocation=(), payment=(), usb=()",
        )
        self.send_header("Cross-Origin-Opener-Policy", "same-origin")
        self.send_header("Cross-Origin-Resource-Policy", "same-origin")

    def _send_bytes(
        self,
        data: bytes,
        content_type: str,
        csp: str,
        status: int = 200,
        download_name: str = "",
    ) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        if download_name:
            safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", download_name)
            self.send_header("Content-Disposition", f'attachment; filename="{safe}"')
        self._common_headers(csp)
        self.end_headers()
        if self.head_only:
            return
        try:
            self.wfile.write(data)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def _send_json(self, status: int, payload: dict[str, Any]) -> None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self._send_bytes(data, "application/json; charset=utf-8", "default-src 'none'", status)

    def _error(self, message: str, status: int = 400) -> None:
        self._send_json(status, {"error": message})

    def _read_json(self) -> dict[str, Any]:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError as exc:
            raise ValueError("Content-Length inválido.") from exc
        if length <= 0 or length > MAX_BODY_BYTES:
            raise ValueError("Corpo da requisição vazio ou grande demais.")
        content_type = self.headers.get("Content-Type", "")
        if "application/json" not in content_type.lower():
            raise ValueError("Envie a requisição como application/json.")
        raw = self.rfile.read(length)
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("JSON inválido.") from exc
        if not isinstance(payload, dict):
            raise ValueError("O corpo deve ser um objeto JSON.")
        return payload

    # ---- páginas --------------------------------------------------------

    def _serve_index(self) -> None:
        path = web_dir() / "index.html"
        try:
            page = path.read_text(encoding="utf-8")
        except OSError:
            self._error("Arquivo da interface não encontrado.", 500)
            return
        page = page.replace("__NFSE_TOKEN__", html.escape(self.app_token, quote=True))
        page = page.replace("__NFSE_VERSION__", core.APP_VERSION)
        self._send_bytes(page.encode("utf-8"), "text/html; charset=utf-8", COLLECTOR_CSP)

    def _serve_reader(self) -> None:
        path = web_dir() / "leitor.html"
        try:
            data = path.read_bytes()
        except OSError:
            self._error("Leitor não encontrado.", 500)
            return
        self._send_bytes(data, "text/html; charset=utf-8", READER_CSP)

    def _serve_static(self, request_path: str) -> None:
        mapping = {
            "/app.js": ("app.js", "text/javascript; charset=utf-8"),
            "/styles.css": ("styles.css", "text/css; charset=utf-8"),
            "/favicon.svg": ("favicon.svg", "image/svg+xml"),
            "/vendor/fflate.js": ("vendor/fflate.js", "text/javascript; charset=utf-8"),
        }
        item = mapping.get(request_path)
        if item is None:
            self._error("Não encontrado.", 404)
            return
        filename, content_type = item
        path = web_dir() / filename
        try:
            data = path.read_bytes()
        except OSError:
            self._error("Arquivo não encontrado.", 404)
            return
        csp = COLLECTOR_CSP if not filename.startswith("vendor/") else "default-src 'none'"
        self._send_bytes(data, content_type, csp)

    def _serve_path(self, path: Path, name: str, content_type: str) -> None:
        try:
            size = path.stat().st_size
            handle = path.open("rb")
        except OSError:
            self._error("Arquivo não encontrado.", 404)
            return
        with handle:
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(size))
            safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", name or "arquivo.bin")
            self.send_header("Content-Disposition", f'attachment; filename="{safe}"')
            self._common_headers("default-src 'none'")
            self.end_headers()
            if self.head_only:
                return
            try:
                shutil.copyfileobj(handle, self.wfile, length=64 * 1024)
            except (BrokenPipeError, ConnectionResetError):
                pass

    def _serve_download(self) -> None:
        item = self.job_manager.download()
        if item is None:
            self._error("Nenhum ZIP disponível.", 404)
            return
        path, name = item
        self._serve_path(path, name or "coleta-xml-nfse.zip", "application/zip")

    def _read_zip_file(self) -> Path:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError as exc:
            raise ValueError("Content-Length inválido.") from exc
        if length <= 0 or length > MAX_RESTORE_BYTES:
            raise ValueError("Backup vazio ou grande demais.")
        content_type = self.headers.get("Content-Type", "").lower()
        if "zip" not in content_type:
            raise ValueError("Envie o backup como application/zip.")
        fd, name = tempfile.mkstemp(prefix="coleta_restore_", suffix=".zip")
        path = Path(name)
        try:
            remaining = length
            with os.fdopen(fd, "wb") as handle:
                while remaining > 0:
                    chunk = self.rfile.read(min(1024 * 1024, remaining))
                    if not chunk:
                        raise ValueError("Backup incompleto.")
                    handle.write(chunk)
                    remaining -= len(chunk)
            core._restrict_file(path)
            return path
        except Exception:
            try:
                path.unlink()
            except OSError:
                pass
            raise

    # ---- rotas ----------------------------------------------------------

    def do_GET(self) -> None:  # noqa: N802
        if not self._check_host():
            return
        path = urllib.parse.urlsplit(self.path).path
        if path in ("/", "/index.html"):
            self._serve_index()
            return
        if path in ("/leitor", "/leitor.html"):
            self._serve_reader()
            return
        if path in ("/app.js", "/styles.css", "/favicon.svg", "/vendor/fflate.js"):
            self._serve_static(path)
            return
        if path == "/api/health":
            self._send_json(200, {"app": "nfse", "version": core.APP_VERSION})
            return
        if path == "/api/status":
            if not self._token_ok():
                self._error("Token inválido.", 403)
                return
            self._send_json(200, self.job_manager.status())
            return
        if path == "/api/history":
            if not self._token_ok():
                self._error("Token inválido.", 403)
                return
            self._send_json(200, {"runs": self.job_manager.history()})
            return
        if path == "/api/cache":
            if not self._token_ok():
                self._error("Token inválido.", 403)
                return
            self._send_json(200, {"clients": self.job_manager.cache()})
            return
        if path == "/api/cache/backup":
            if not self._token_ok():
                self._error("Token inválido.", 403)
                return
            archive = None
            try:
                archive = self.job_manager.create_backup()
                self._serve_path(
                    archive,
                    archive.name,
                    "application/zip",
                )
            except BusyError as exc:
                self._error(str(exc), 409)
            except Exception as exc:
                self._error(f"Não foi possível criar o backup: {exc}", 500)
            finally:
                if archive is not None:
                    shutil.rmtree(archive.parent, ignore_errors=True)
            return
        if path == "/api/diagnostics":
            if not self._token_ok():
                self._error("Token inválido.", 403)
                return
            self._send_json(200, self.job_manager.diagnostics())
            return
        if path == "/api/download":
            if not self._token_ok():
                self._error("Token inválido.", 403)
                return
            self._serve_download()
            return
        self._error("Não encontrado.", 404)

    def do_POST(self) -> None:  # noqa: N802
        if not self._check_host():
            return
        if not self._check_origin():
            return
        if not self._token_ok():
            self._error("Token inválido.", 403)
            return
        path = urllib.parse.urlsplit(self.path).path
        try:
            if path == "/api/run":
                payload = self._read_json()
                config = WebRunConfig.from_payload(payload)
                job = self.job_manager.start(config)
                self._send_json(202, {"job_id": job.id})
                return
            if path == "/api/cancel":
                cancelled = self.job_manager.cancel()
                self._send_json(200, {"ok": True, "cancelled": cancelled})
                return
            if path == "/api/cache/clear":
                payload = self._read_json()
                cnpj = payload.get("cnpj")
                if not isinstance(cnpj, str):
                    raise ValueError("Informe o CNPJ.")
                result = self.job_manager.clear_cache(cnpj)
                self._send_json(200, {"ok": True, **result})
                return
            if path == "/api/cache/restore":
                archive = self._read_zip_file()
                try:
                    result = self.job_manager.restore_backup(archive)
                finally:
                    try:
                        archive.unlink()
                    except OSError:
                        pass
                self._send_json(200, {"ok": True, **result})
                return
            if path == "/api/wipe":
                result = self.job_manager.wipe()
                self._send_json(200, {"ok": True, **result})
                return
            if path == "/api/reveal":
                self.job_manager.reveal()
                self._send_json(200, {"ok": True})
                return
            if path == "/api/quit":
                job = self.job_manager.current()
                if job is not None and job.state == "running":
                    self._error("Cancele a execução antes de encerrar.", 409)
                    return
                self._send_json(200, {"ok": True})
                threading.Thread(target=self.server.shutdown, daemon=True).start()
                return
            self._error("Não encontrado.", 404)
        except BusyError as exc:
            self._error(str(exc), 409)
        except ValueError as exc:
            self._error(str(exc), 400)
        except Exception as exc:
            try:
                sys.stderr.write(f"[local] erro interno: {type(exc).__name__}: {exc}\n")
            except Exception:
                pass
            self._error("Erro interno no coletor local.", 500)

    def do_HEAD(self) -> None:  # noqa: N802
        self.head_only = True
        self.do_GET()

    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(405)
        self.send_header("Allow", "GET, POST")
        self._common_headers("default-src 'none'")
        self.end_headers()


def create_server(
    host: str = "127.0.0.1", port: int = 8765
) -> tuple[ThreadingHTTPServer, str, str, JobManager]:
    token = secrets.token_urlsafe(32)
    manager = JobManager()
    handler = type(
        "BoundNFSEHandler",
        (NFSEHandler,),
        {"app_token": token, "job_manager": manager},
    )
    server = ThreadingHTTPServer((host, port), handler)
    server.daemon_threads = True
    actual_port = int(server.server_address[1])
    url = f"http://127.0.0.1:{actual_port}/"
    return server, token, url, manager


def _safe_print(message: str) -> None:
    try:
        print(message)
    except Exception:
        pass


def run_web(port: int = 8765, open_browser: bool = True) -> int:
    core.migrate_legacy_data()
    try:
        server, _token, url, manager = create_server(port=port)
    except OSError:
        server, _token, url, manager = create_server(port=0)
    _safe_print(f"Coleta XML NFSE {core.APP_VERSION}")
    _safe_print(f"Interface local: {url}")
    _safe_print("Escutando apenas em 127.0.0.1. Pressione Ctrl+C para encerrar.")
    if open_browser:
        threading.Timer(0.4, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        _safe_print("\nEncerrando...")
    finally:
        manager.close()
        server.server_close()
    return 0
