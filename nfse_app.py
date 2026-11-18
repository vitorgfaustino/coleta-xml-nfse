#!/usr/bin/env python3
"""Entrada do Coleta XML NFSE local.

Uso:
    python nfse_app.py              # interface web em 127.0.0.1
    python nfse_app.py run --help   # modo agendado/headless
    python nfse_app.py doctor
"""

from __future__ import annotations

import subprocess
import sys

from nfse.cli import main


def _alert(message: str) -> None:
    """Mostra erro em build sem console, onde stderr pode ser invisível."""

    try:
        if sys.platform == "darwin":
            escaped = (
                message.replace("\\", "\\\\")
                .replace('"', '\\"')
                .replace("\n", "\\n")
            )
            subprocess.run(
                [
                    "osascript",
                    "-e",
                    f'display alert "Coleta XML NFSE" message "{escaped}" as critical',
                ],
                check=False,
            )
        elif sys.platform == "win32":
            import ctypes

            ctypes.windll.user32.MessageBoxW(
                0, message, "Coleta XML NFSE", 0x10
            )
        else:
            print(message, file=sys.stderr)
    except Exception:
        pass


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception as exc:
        _alert(f"Falha ao iniciar o aplicativo:\n{exc}")
        raise SystemExit(1)
