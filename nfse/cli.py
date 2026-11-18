"""CLI e entrada do app local."""

from __future__ import annotations

import argparse
import getpass
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from . import core
from .web import run_web


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="nfse",
        description="Coletor local de XML da NFS-e Nacional (ADN), com certificado A1.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {core.APP_VERSION}")
    sub = parser.add_subparsers(dest="command")

    web = sub.add_parser("web", help="abre a interface local no navegador (padrão)")
    web.add_argument("--port", type=int, default=8765, help="porta local (padrão: 8765)")
    web.add_argument("--no-browser", action="store_true", help="não abre o navegador")

    run = sub.add_parser("run", help="executa sem interface, para agendamento")
    run.add_argument("--config", help="arquivo JSON de configuração da execução")
    run.add_argument("--pfx", help="caminho do certificado .pfx/.p12")
    run.add_argument("--password-file", help="arquivo 0600 com a senha do PFX")
    run.add_argument(
        "--password-env",
        default="NFSE_PFX_PASSWORD",
        help="nome da variável de ambiente com a senha (padrão: NFSE_PFX_PASSWORD)",
    )
    run.add_argument("--cnpj", action="append", default=[], help="CNPJ autorizado (repetível)")
    run.add_argument("--environment", choices=tuple(core.ENVIRONMENTS), default=None)
    run.add_argument("--filter", choices=core.FILTERS, default=None)
    run.add_argument("--output", help="pasta do ZIP exportado")
    run.add_argument(
        "--period-start",
        help="competência inicial no formato AAAA-MM ou AAAA-MM-DD",
    )
    run.add_argument(
        "--period-end",
        help="competência final no formato AAAA-MM ou AAAA-MM-DD",
    )
    run.add_argument(
        "--emission-start",
        help="data de emissão inicial no formato AAAA-MM-DD",
    )
    run.add_argument(
        "--emission-end",
        help="data de emissão final no formato AAAA-MM-DD",
    )
    run.add_argument(
        "--start-nsu",
        type=int,
        default=None,
        help="NSU inicial no primeiro download de cada CNPJ",
    )
    run.add_argument(
        "--no-cache",
        action="store_true",
        default=None,
        help="não guarda cópia local, histórico nem logs",
    )
    run.add_argument("--max-pages", type=int, default=None)

    sub.add_parser("doctor", help="mostra caminhos, cópia local e dependências")

    wipe = sub.add_parser("wipe", help="apaga cópia local, histórico, logs e ZIPs")
    wipe.add_argument("--yes", action="store_true", help="confirma a exclusão")

    return parser


def _load_config(args: argparse.Namespace) -> dict[str, Any]:
    config: dict[str, Any] = {}
    if args.config:
        path = Path(args.config).expanduser()
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
        except OSError as exc:
            raise SystemExit(f"Não foi possível ler {path}: {exc}") from exc
        except ValueError as exc:
            raise SystemExit(f"Configuração inválida em {path}: {exc}") from exc
        if not isinstance(loaded, dict):
            raise SystemExit("A configuração deve ser um objeto JSON.")
        config.update(loaded)

    overrides = {
        "pfx": args.pfx,
        "password_file": args.password_file,
        "environment": args.environment,
        "filter": args.filter,
        "output": args.output,
        "period_start": args.period_start,
        "period_end": args.period_end,
        "emission_start": args.emission_start,
        "emission_end": args.emission_end,
        "start_nsu": args.start_nsu,
        "no_cache": getattr(args, "no_cache", None),
        "max_pages": args.max_pages,
    }
    for key, value in overrides.items():
        if value is not None:
            config[key] = value
    if args.cnpj:
        config["cnpjs"] = args.cnpj
    config.setdefault("environment", "producao")
    config.setdefault("filter", "Ambas")
    config.setdefault("max_pages", core.MAX_PAGES_DEFAULT)
    config.setdefault("no_cache", False)
    return config


def _console(message: str) -> None:
    """print seguro para pythonw/Task Scheduler, onde stdout pode ser None."""

    try:
        print(message)
    except Exception:
        pass


def _period_value(value: Any) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    if re.fullmatch(r"\d{4}-\d{2}", text):
        try:
            datetime.strptime(text, "%Y-%m")
        except ValueError as exc:
            raise SystemExit("Competência inválida. Use AAAA-MM ou AAAA-MM-DD.") from exc
        return text
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
        try:
            datetime.strptime(text, "%Y-%m-%d")
        except ValueError as exc:
            raise SystemExit("Competência inválida. Use AAAA-MM-DD.") from exc
        return text
    raise SystemExit("Competência inválida. Use AAAA-MM ou AAAA-MM-DD.")


def _day_value(value: Any, label: str) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
        raise SystemExit(f"{label} inválida. Use AAAA-MM-DD.")
    try:
        datetime.strptime(text, "%Y-%m-%d")
    except ValueError as exc:
        raise SystemExit(f"{label} inválida. Use AAAA-MM-DD.") from exc
    return text


def _read_password(config: dict[str, Any], env_name: str) -> str:
    env_value = os.environ.get(env_name)
    if env_value:
        return env_value
    password_file = config.get("password_file")
    if password_file:
        path = Path(str(password_file)).expanduser()
        try:
            if os.name != "nt":
                mode = path.stat().st_mode & 0o777
                if mode & 0o077:
                    sys.stderr.write(
                        f"Aviso: {path} pode ser lido por outros usuários (permissão {mode:o}).\n"
                    )
            return path.read_text(encoding="utf-8").rstrip("\r\n")
        except OSError as exc:
            raise SystemExit(f"Não foi possível ler a senha em {path}: {exc}") from exc
    if sys.stdin.isatty():
        return getpass.getpass("Senha do certificado A1: ")
    raise SystemExit(
        "Senha não informada. Use --password-file, a variável "
        f"{env_name}, ou execute em um terminal interativo."
    )


def _run_command(args: argparse.Namespace) -> int:
    config = _load_config(args)
    pfx_value = config.get("pfx")
    if not pfx_value:
        raise SystemExit("Informe o certificado com --pfx ou no campo 'pfx' do --config.")
    pfx_path = Path(str(pfx_value)).expanduser()
    try:
        if pfx_path.stat().st_size > 5 * 1024 * 1024:
            raise SystemExit("O certificado é grande demais (limite de 5 MB).")
        pfx_bytes = pfx_path.read_bytes()
    except OSError as exc:
        raise SystemExit(f"Não foi possível ler o certificado {pfx_path}: {exc}") from exc

    raw_cnpjs = config.get("cnpjs")
    if isinstance(raw_cnpjs, list):
        cnpj_text = "\n".join(str(item) for item in raw_cnpjs)
    else:
        cnpj_text = str(raw_cnpjs or "")
    valid, invalid = core.parse_cnpj_text(cnpj_text)
    if invalid:
        raise SystemExit("CNPJs inválidos: " + ", ".join(invalid[:10]))
    if not valid:
        raise SystemExit("Informe ao menos um CNPJ válido.")

    environment = str(config.get("environment") or "producao")
    if environment not in core.ENVIRONMENTS:
        raise SystemExit("Ambiente inválido. Use 'producao' ou 'restrita'.")
    document_filter = str(config.get("filter") or "Ambas")
    if document_filter not in core.FILTERS:
        raise SystemExit("Filtro inválido. Use Prestados, Tomados ou Ambas.")
    ephemeral = bool(config.get("no_cache"))
    max_pages = int(config.get("max_pages") or core.MAX_PAGES_DEFAULT)
    period_start = _period_value(config.get("period_start"))
    period_end = _period_value(config.get("period_end"))
    emission_start = _day_value(config.get("emission_start"), "Emissão inicial")
    emission_end = _day_value(config.get("emission_end"), "Emissão final")
    if (period_start is None) != (period_end is None):
        raise SystemExit("Informe --period-start e --period-end juntos.")
    if period_start and period_end and period_start > period_end:
        raise SystemExit("A competência inicial não pode ser depois da final.")
    if (emission_start is None) != (emission_end is None):
        raise SystemExit("Informe --emission-start e --emission-end juntos.")
    if emission_start and emission_end and emission_start > emission_end:
        raise SystemExit("A emissão inicial não pode ser depois da final.")
    try:
        start_nsu = int(config.get("start_nsu") or 0)
    except (TypeError, ValueError) as exc:
        raise SystemExit("NSU inicial inválido.") from exc
    if start_nsu < 0:
        raise SystemExit("O NSU inicial não pode ser negativo.")
    password_env = str(config.get("password_env") or args.password_env)
    password = _read_password(config, password_env)

    core.migrate_legacy_data(_console)
    paths = core.RunPaths.create(ephemeral=ephemeral)
    if ephemeral and not config.get("output"):
        raise SystemExit("No modo sem cache, informe --output para salvar o ZIP final.")
    output = Path(str(config["output"])).expanduser() if config.get("output") else paths.exports
    output.mkdir(parents=True, exist_ok=True)

    log_path = None if ephemeral else paths.logs / f"execucao_{datetime.now():%Y%m%d_%H%M%S}.log"
    logger = core.RunLogger(log_path, callback=_console)
    exit_code = 0
    try:
        with core.RunLock(core.data_dir() / "run.lock"):
            with core.CertificatePair(pfx_bytes, password) as pem:
                client = core.NfseClient(
                    core.ENVIRONMENTS[environment],
                    pem,
                    logger.log,
                )
                try:
                    results = core.run_download(
                        paths,
                        client,
                        valid,
                        logger.log,
                        ephemeral=ephemeral,
                        max_pages=max_pages,
                        period_start=period_start,
                        period_end=period_end,
                        emission_start=emission_start,
                        emission_end=emission_end,
                        start_nsu=start_nsu,
                    )
                finally:
                    client.close()

            connection = core.connect_state(paths.state)
            try:
                zip_name = (
                    f"Coleta_XML_NFSE_{document_filter}_"
                    f"{datetime.now():%Y%m%d_%H%M%S}.zip"
                )
                export = core.export_zip(
                    connection,
                    paths,
                    valid,
                    document_filter,
                    output / zip_name,
                    logger.log,
                    period_start=period_start,
                    period_end=period_end,
                    emission_start=emission_start,
                    emission_end=emission_end,
                )
            finally:
                connection.close()

        failures = [item for item in results if item.error]
        logger.log(
            f"Concluído: {sum(item.new_documents for item in results)} novo(s); "
            f"{sum(item.ignored for item in results)} fora do período; "
            f"{export.total} XML(s) no filtro {document_filter}; "
            f"{len(failures)} cliente(s) com erro."
        )
        if export.zip_path is not None:
            logger.log(f"ZIP: {export.zip_path}")
        else:
            logger.log("Nenhum XML corresponde ao filtro selecionado.")
        if failures:
            exit_code = 1
        if ephemeral:
            logger.log("Sem cache: XMLs, histórico e logs temporários serão apagados.")
        return exit_code
    except core.NfseError as exc:
        logger.log(f"FALHA: {exc}")
        return 1
    except Exception as exc:
        logger.log(f"FALHA: {exc}")
        return 1
    finally:
        logger.close()
        paths.cleanup()


def _doctor() -> int:
    files, size = core.cache_stats()
    print(f"Coleta XML NFSE {core.APP_VERSION}")
    print(f"Python: {sys.version.split()[0]}")
    print(f"Plataforma: {sys.platform}")
    print(f"Pasta de dados: {core.data_dir()}")
    print(f"Cópia local: {files} XML(s), {core.human_bytes(size)}")
    print(f"Banco de estado: {core.data_dir() / 'state.sqlite3'}")
    try:
        import requests
        import cryptography
        print(f"requests: {requests.__version__}")
        print(f"cryptography: {cryptography.__version__}")
    except ImportError as exc:
        print(f"Dependência ausente: {exc}")
    legacy = core.legacy_data_dir()
    if legacy and legacy.is_dir():
        print(f"Dados da versão antiga: {legacy} (serão importados na próxima execução)")
    print("Interface local: execute 'python nfse_app.py' (ou 'nfse web' se instalado)")
    return 0


def _wipe(args: argparse.Namespace) -> int:
    if not args.yes:
        raise SystemExit("Use --yes para confirmar a exclusão de cópia local, histórico, logs e ZIPs.")
    removed, freed = core.wipe_data()
    print(f"{removed} item(ns) removido(s); {core.human_bytes(freed)} liberados.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.command is None:
        return run_web()
    if args.command == "web":
        return run_web(port=args.port, open_browser=not args.no_browser)
    if args.command == "run":
        return _run_command(args)
    if args.command == "doctor":
        return _doctor()
    if args.command == "wipe":
        return _wipe(args)
    parser.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
