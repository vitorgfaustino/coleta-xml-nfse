"""Gera pages/ a partir do leitor local.

O Pages hospeda somente o leitor estático. O coletor continua local porque
o ADN exige TLS mútuo com o certificado A1.
"""

from __future__ import annotations

import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "web"
PAGES = ROOT / "pages"

HEADERS = """/*
  Content-Security-Policy: default-src 'none'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self'; connect-src 'none'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'
  Referrer-Policy: no-referrer
  X-Content-Type-Options: nosniff
  X-Frame-Options: DENY
  Permissions-Policy: camera=(), microphone=(), geolocation=(), payment=(), usb=()
  Cross-Origin-Opener-Policy: same-origin
  Cross-Origin-Resource-Policy: same-origin
  Cache-Control: no-cache
/vendor/*
  Cache-Control: public, max-age=31536000, immutable
"""

README = """# Leitor NFS-e no Cloudflare Pages

Gerado por `python3 scripts/build_pages.py`. Não edite os arquivos gerados à mão.

## O que é

Leitor 100% client-side para XMLs de NFS-e/NFe e eventos de cancelamento.
Aceita XML avulso, pasta de XMLs e o ZIP exportado pelo coletor local.

- Nenhum arquivo é enviado a servidor.
- Sem `fetch`/XHR/WebSocket; a CSP usa `connect-src 'none'`.
- Sem cookies, `localStorage`, `IndexedDB` ou analytics.
- O ZIP é descompactado no navegador com `fflate`.

## O que não é

O downloader. O ADN exige TLS mútuo com o certificado A1; isso precisa
acontecer na máquina do usuário. O Pages não recebe PFX, senha ou XML.

## Deploy

```bash
python3 scripts/build_pages.py
npx wrangler pages deploy pages --project-name coleta-xml-nfse
```

Sem Functions, D1, R2, KV ou Web Analytics.
"""


def main() -> None:
    PAGES.mkdir(exist_ok=True)
    (PAGES / "vendor").mkdir(exist_ok=True)

    html = (WEB / "leitor.html").read_text(encoding="utf-8")
    # O link para o coletor só existe no app local. A versão publicada não tem coletor.
    html = html.replace(
        '<nav class="topnav" aria-label="Navegação principal"><a href="/">Coletor</a><a href="/leitor" aria-current="page">Leitor de XML</a></nav>',
        '<nav class="topnav" aria-label="Navegação principal"><span class="current" aria-current="page">Leitor de XML</span></nav>',
    )
    (PAGES / "index.html").write_text(html, encoding="utf-8")
    shutil.copy2(WEB / "vendor" / "fflate.js", PAGES / "vendor" / "fflate.js")
    shutil.copy2(WEB / "vendor" / "fflate.LICENSE", PAGES / "vendor" / "fflate.LICENSE")
    shutil.copy2(WEB / "favicon.svg", PAGES / "favicon.svg")
    (PAGES / "_headers").write_text(HEADERS, encoding="utf-8")
    (PAGES / "README.md").write_text(README, encoding="utf-8")
    print(f"Pages gerado em {PAGES}")


if __name__ == "__main__":
    main()
