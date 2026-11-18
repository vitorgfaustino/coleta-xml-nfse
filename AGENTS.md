# AGENTS.md

Guia para agentes que trabalharem no **Coleta XML NFSE**.

## Produto

Aplicativo local para baixar XMLs da NFS-e no ADN e analisá-los no navegador.
O certificado A1, a senha e os XMLs não saem da máquina do usuário.

- Interface: `127.0.0.1`, sem CDN, sem telemetria e sem backend remoto.
- Coletor: Python + TLS mútuo com o ADN.
- Leitor: HTML/CSS/JavaScript, processamento no navegador.
- Distribuição: código Python; sem `.exe`/`.app` por decisão atual.
- PyInstaller/build.py: ferramenta local opcional, fora do fluxo oficial.
- Licença: MIT.
- Autor: Vitor Faustino.
- Repositório: <https://github.com/vitorgfaustino/coleta-xml-nfse>.

## Estratégia de branches

- Trabalho dos agentes: `agents/**` ou `feature/**`.
- Integração: `develop`.
- `main` e `beta`: somente com aprovação humana.
- Não faça commit, push, merge, tag, release ou deploy sem pedido explícito.

## Ambiente

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

Windows:

```powershell
py -3.12 -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
```

## Comandos de validação

```bash
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python -m compileall -q nfse nfse_app.py scripts build.py
node --check web/app.js
python3 scripts/build_pages.py
```

E2E:

```bash
cd tests/e2e
npm install
npx playwright install chromium
PYTHON=../../.venv/bin/python npm test
```

Execução oficial:

```bash
.venv/bin/python nfse_app.py
.venv/bin/python scripts/export_source_zip.py  # ZIP para compartilhar
```

Não configure build/release de `.exe`/`.app` sem autorização explícita,
orçamento de certificado e runners nativos. PyInstaller não faz cross-compile.

## Estrutura

```text
nfse/core.py       ADN, NSU, CNPJ, XML, cache, datas, exportação
nfse/web.py        servidor loopback, API, jobs, cache, histórico
nfse/cli.py        web/run/doctor/wipe
web/index.html     coletor
web/app.js         fluxo em 4 etapas e ferramentas locais
web/leitor.html    leitor e exportações
web/styles.css     estilos do coletor
tests/             testes Python
tests/e2e/         Playwright
.gitea/workflows/  CI do Gitea
.github/workflows/ CI/E2E do GitHub
tools/             instalar opcional
docs/              uso, privacidade, arquitetura, releases e Gitea
scripts/           páginas e ZIP de distribuição
```

## Regras de dados e segurança

- Nunca grave PFX, senha ou chave privada.
- Nunca coloque CNPJ real, XML, chave de acesso ou dado de cliente em issue,
  teste, screenshot, commit ou log.
- Logs devem mascarar CNPJs.
- O leitor não pode fazer `fetch`, XHR, WebSocket, upload ou telemetria.
- A API local exige `X-NFSE-Token`; preserve a validação de `Host` e `Origin`.
- Prefira CSP restritiva e nenhuma dependência de CDN.
- O `state.sqlite3` e o `xml_cache` são dados do usuário: mudanças de schema
  precisam de migração compatível.
- A pasta de dados atual é `ColetaXmlNFSE`; dados antigos de
  `NFSeXmlDownloader` são migrados automaticamente.

## Filtros de data

- O ADN distribui por NSU. O filtro de data é aplicado localmente.
- Competência e emissão são filtros independentes; quando os dois estão
  preenchidos, o XML precisa satisfazer ambos.
- A competência é armazenada também como mês para a pasta do ZIP.
- Datas completas são `AAAA-MM-DD`; `AAAA-MM` ainda é aceito por
  compatibilidade na API/CLI de competência.
- Ao mudar o filtro, preserve o comportamento de avançar o cursor — XMLs
  ignorados não devem ser rebaixados depois.

## UI

- Idioma: português do Brasil.
- Fluxo do coletor: Certificado → Empresas → Consulta → Revisão.
- A etapa de revisão é a última; o botão principal é **Confirmar e baixar**.
- Não reintroduza rolagem automática agressiva ao trocar de etapa.
- O leitor deve esconder a área grande de upload quando já houver ZIP carregado
  e oferecer **Novo ZIP/XML** ou **Nova pasta**.
- A exportação PDF usa A4 paisagem e deve manter todas as colunas e totais.
- Preserve o rodapé com MIT, Vitor Faustino e link do GitHub.
- Não adicione campos de digitação individuais ao leitor; use a busca universal
  e filtros do tipo seletor.

## CI/CD

- Gitea: CI com `runs-on: ubuntu-latest`, sem secrets.
- CI: testes, compilação, JS quando disponível e leitor estático.
- Não há build de `.exe`/`.app`, release de binário ou assinatura configurada.
- Não configure publicação automática no Gitea.
- GitHub: CI, E2E e release do ZIP Python na `main`; sem executáveis.
- Actions externas dependem do espelho/proxy do Gitea e de firewall liberado.
- Windows/macOS exigiriam runners nativos e certificados; não configurar sem
  decisão explícita.
- Não coloque secrets em YAML, logs ou artefatos.
- Documente qualquer novo requisito em `docs/GITEA_CI.md`.

## Critério de conclusão

- Testes Python e E2E passando quando aplicável.
- `node --check web/app.js` e YAML válidos.
- Sem regressão de privacidade, cache/cursor ou leitor.
- README/docs atualizados.
- Sem commit/push/publicação sem autorização.
