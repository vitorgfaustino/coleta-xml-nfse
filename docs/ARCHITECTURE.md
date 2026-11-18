# Arquitetura

## Visão geral

```text
Navegador
  |
  | HTTP em 127.0.0.1, token, Host e Origin validados
  v
Processo Python
  |-- nfse/core.py   ADN, PFX, CNPJ, XML, cópia local, ZIP
  |-- nfse/web.py    servidor local, jobs, CSP
  |-- nfse/cli.py    web, run, doctor, wipe
  |
  | TLS mútuo com o certificado A1
  v
ADN
```

O leitor não conversa com o processo Python. Ele abre XMLs e ZIPs no navegador e renderiza a tabela.

## Componentes

### `nfse/core.py`

- Normaliza CNPJ numérico e alfanumérico.
- Classifica XML por emitente, tomador, intermediário, evento e competência.
- Decodifica o `LoteDFe`, incluindo base64 e gzip.
- Trata 404 com `E2220` ou `E2230` como fim da fila.
- Trata 404 genérico e `Erros: []` como erro.
- Faz retry em 429, 5xx e falhas de rede.
- Mantém a cópia local endereçada por SHA-256.
- Salva a posição da última consulta após cada documento.
- Exporta ZIP por empresa, competência e categoria.
- Remove dados locais e aplica permissões.

### `nfse/web.py`

- Servidor `ThreadingHTTPServer` em `127.0.0.1`.
- Token aleatório por processo.
- Validação de `Host` e `Origin`.
- CSP, `Referrer-Policy`, `X-Content-Type-Options` e `Permissions-Policy`.
- Job assíncrono com log, cancelamento e status.
- Upload do PFX em JSON base64, sem gravar o PFX.
- Download do ZIP.
- Histórico de execuções e cache por CNPJ.
- Backup/restauração da cópia local, com validação de ZIP e SQLite.
- Diagnóstico de pasta, proxy, DNS e TCP do ADN.

### `nfse/cli.py`

- `web`: interface local.
- `run`: execução sem interface, com config JSON.
- `doctor`: caminhos, versão, cache e dependências.
- `wipe`: remoção de dados locais.

### `web/`

- `index.html` e `app.js`: coletor, preferências locais, histórico, cache e diagnóstico.
- `leitor.html`: leitor, busca, CSV/Excel/XML ZIP e impressão/PDF.
- `vendor/fflate.js`: ZIP no navegador.
- `styles.css`: estilos do coletor.

O coletor pode abrir o leitor em outra aba e enviar o ZIP por `postMessage` same-origin. O leitor processa o ZIP localmente; nenhum byte vai para servidor.

### `scripts/`

- `build_pages.py`: gera a versão estática do leitor para o Cloudflare Pages.
- `set_version.py`: atualiza a versão no build.
- `package.py`: empacota e calcula SHA-256.

## Fronteiras de confiança

1. **Navegador e processo local:** loopback, token, `Host`, `Origin` e CSP.
2. **Processo local e ADN:** TLS mútuo com o A1, validação normal do certificado do servidor.
3. **Leitor e arquivos do usuário:** processamento no navegador, sem rede.
4. **Distribuição:** código Python; PyInstaller é ferramenta local opcional, sem release de binários.

## Estado local

`state.sqlite3` contém:

- `cursors`: posição da última consulta por CNPJ.
- `documents`: hash, nome do arquivo, NSU, competência (mês e data), emissão, papéis e evento.
- `runs`: histórico resumido das últimas execuções, incluindo filtros de competência e emissão.

Os XMLs ficam em `xml_cache/<cnpj>/`. O índice evita reler arquivos já conhecidos. Quando há filtros de competência e/ou emissão, XMLs fora dos intervalos não são gravados, mas o cursor avança para não repetir a consulta. XMLs antigos já indexados têm as datas completas preenchidas sob demanda antes da exportação.

## Exportação

`export_zip` consulta o índice e monta:

```text
<cnpj>/<competencia>/Prestados/<arquivo>.xml
<cnpj>/<competencia>/Tomados/<arquivo>.xml
<cnpj>/<competencia>/Eventos/<arquivo>.xml
<cnpj>/<competencia>/Outros/<arquivo>.xml
```

Eventos entram em todos os filtros. XML sem papel reconhecido entra em `Outros` apenas no filtro `Ambas`.

## Build opcional/local

O fluxo oficial é executar via Python. `build.py` e `scripts/package.py` existem
apenas como ferramenta local opcional e não fazem parte do CI nem da
distribuição pública.

Se forem usados, `build.py` chama o PyInstaller com `nfse_app.py` como entrada,
`web/` em `_MEIPASS/web`, `--onedir` e console por padrão. `scripts/package.py`
gera arquivo final e `.sha256`. Windows/macOS exigem build nativo e, para
distribuição pública, assinatura/notarização.

## Por que o download é local

O ADN exige TLS mútuo com o certificado A1. O handshake acontece antes do HTTP. Um site estático não apresenta o certificado do usuário. O binding mTLS de um Worker usa um certificado fixo, não o PFX de cada visitante. Subir o PFX para um servidor quebraria o requisito de privacidade.

Por isso o Pages hospeda apenas o leitor. O coletor fica na máquina do usuário.
