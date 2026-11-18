# Coleta XML NFSE

Coletor local de XML da NFS-e Nacional (ADN) com certificado A1. Roda no Windows e no macOS, em `127.0.0.1`. Inclui um leitor de XML que processa tudo no navegador..

Repositório: <https://github.com/vitorgfaustino/coleta-xml-nfse>

Licença MIT · Criado por Vitor Faustino.

## Você quer usar ou desenvolver?

Este repositório é para quem deseja **desenvolver, auditar ou contribuir** com o
código. Se você só quer baixar e usar o aplicativo, não precisa clonar o projeto.

<p>
  <a href="https://github.com/vitorgfaustino/coleta-xml-nfse/releases/latest">
    <img alt="Baixar ZIP da versão atual" src="https://img.shields.io/badge/Baixar%20ZIP-da%20release%20atual-2859d8?style=for-the-badge">
  </a>
  <a href="docs/USO.md">
    <img alt="Abrir guia de uso" src="https://img.shields.io/badge/Guia-como%20usar-344054?style=for-the-badge">
  </a>
</p>

| Eu quero... | Caminho |
|---|---|
| Apenas usar o aplicativo | Baixe o **ZIP da release**, extraia e execute `iniciar.bat`/`iniciar.command` |
| Desenvolver ou contribuir | Clone este repositório e siga [docs/USO.md](docs/USO.md) |

O ZIP da release é uma distribuição **Python**: exige Python 3.10 ou superior e
não é um `.exe`/`.app`. Não é necessário comprar certificado de assinatura. O
ZIP contém apenas o runtime, o guia `COMECE-AQUI.md`, licença e dependências.

A release pública é gerada no **GitHub** depois que a `main` do Gitea é
sincronizada. O Gitea é o ambiente de desenvolvimento; ele não publica uma
release separada.

O certificado e os XMLs não passam por servidor do projeto. A única conexão externa é com o ADN.

**Licença MIT · Python 3.10+ · Windows e macOS**

## O que faz

- Baixa os XMLs distribuídos pelo ADN por NSU, com retomada automática.
- Aceita CNPJ numérico e alfanumérico.
- Organiza os documentos por empresa, competência e papel: prestados, tomados, eventos e outros.
- Exporta um ZIP.
- Abre um leitor local para XML avulso, pasta ou ZIP, com busca, filtros, detalhes de itens, CSV, Excel, XML filtrado e impressão em PDF.
- Mantém histórico de execuções, backup/restauração da cópia local e diagnóstico de rede.
- Lembra a lista de CNPJs e as opções de consulta apenas neste navegador.
- Permite não guardar cópia local, histórico ou logs.
- Roda sem Tkinter, sem CDN e sem telemetria.

## Para quem é

Para procuradores, contadores e empresas que precisam manter uma cópia dos XMLs da NFS-e e conferir os documentos sem enviar o certificado A1 para a nuvem.

## Como funciona

```text
Navegador (127.0.0.1)  <->  processo Python local  <->  TLS mútuo A1  <->  ADN
                                      |
                                      +-> cópia local + ZIP
```

1. O navegador envia o certificado e a senha apenas para o processo local.
2. O processo abre o PFX em memória e cria um PEM temporário para a chamada TLS.
3. O ADN devolve os XMLs. O app indexa, classifica e exporta o ZIP.
4. O leitor abre o ZIP ou os XMLs no navegador e não envia arquivos para servidor.

## Requisitos

- Windows 10 ou 11, ou macOS 13 ou superior.
- **Python 3.10 ou superior** na máquina.
- Certificado A1 em `.pfx` ou `.p12`.
- Procuração vigente para o serviço da NFS-e de cada CNPJ consultado.
- Não há `.exe`/`.app` para download; a execução é pelo código com Python.

## Início rápido

Guia completo: [docs/USO.md](docs/USO.md).

### Windows

1. Instale Python 3.10+ em <https://www.python.org/downloads/windows/> e marque **Add python.exe to PATH**.
2. Extraia a pasta do projeto.
3. Dê duplo clique em `iniciar.bat`.
4. O navegador abre em `http://127.0.0.1:8765`.

### macOS

1. Instale Python 3.10+ em <https://www.python.org/downloads/macos/>.
2. Dê duplo clique em `iniciar.command`.
3. Se o Gatekeeper bloquear, clique com o botão direito no arquivo e escolha **Abrir**.
4. O navegador abre em `http://127.0.0.1:8765`.

Pelo terminal:

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python nfse_app.py
```

### Primeira execução

O coletor segue quatro etapas. Cada etapa valida o que falta antes de liberar a próxima. O guia detalhado está em [docs/USO.md](docs/USO.md).

1. **Certificado:** selecione o A1 do procurador e digite a senha. Ela não é armazenada.
2. **Empresas:** cole um CNPJ por linha.
3. **Consulta:** escolha **Produção** ou **Produção restrita (homologação)**, **Prestados**, **Tomados** ou **Ambas** e **Todo o período** ou **Selecionar período**. No período, informe **Competência** e/ou **Emissão** com datas completas; os intervalos são por dia e podem ser combinados. XMLs fora deles não são guardados. Para pular histórico antigo no primeiro download, abra **Opções avançadas** e informe um NSU inicial.
4. **Revisão:** confira o resumo e clique em **Confirmar e baixar**.

Ao terminar, o botão em destaque é **Abrir no leitor**, que carrega o ZIP automaticamente. **Baixar ZIP** fica como ação secundária para arquivar o arquivo.

## Leitor de XML

O leitor fica no menu superior, na aba **Leitor de XML**, e no botão **Abrir leitor de XML**. Ele aceita XML avulso, uma pasta ou o ZIP exportado pelo coletor.

- Uma busca universal procura em qualquer coluna: emitente, nome fantasia, CNPJ, destinatário, documento do destinatário, número, série, emissão, competência, valor, situação, itens e arquivo.
- Filtros de seleção por ordenação e tipo de serviço. Não há campos separados de empresa, destinatário ou data.
- Tomados e Prestados são reconhecidos pela pasta do ZIP exportado pelo coletor. XMLs avulsos aparecem em **Outro**.
- Filtros ativos ficam visíveis em chips removíveis, com **Limpar filtros**.
- Coluna **Documento destinatário** com CNPJ ou CPF do tomador.
- Resumo de notas, valor, emitentes e itens sempre calculado sobre o filtro.
- Detalhes de cada nota e dos itens.
- Exportação CSV, Excel (notas, itens e resumo), XML filtrado em ZIP e impressão/Salvar como PDF.
- Nenhum arquivo é enviado para servidor.

Ao final de um download, use **Abrir no leitor**. O coletor abre o leitor em outra aba e envia o ZIP localmente, sem upload. Se o navegador bloquear a janela, baixe o ZIP e arraste no leitor.

O leitor também pode ser publicado no Cloudflare Pages como site estático. Veja a seção de build.

## O que fica salvo

| Dado | Onde fica | Observação |
|---|---|---|
| PFX | Memória do navegador e do processo | Nunca é gravado no disco |
| Senha | Memória do processo | Não é salva; o campo é limpo após o envio |
| Lista de CNPJs e opções | `localStorage` do navegador | Apenas preferências; há um botão para limpar |
| XMLs e índice | Pasta do app | Usado para não baixar tudo de novo |
| Posição da última consulta | `state.sqlite3` | Evita repetir a fila |
| Histórico de execuções | `state.sqlite3` | Últimas 20 execuções |
| Backup da cópia local | ZIP baixado por você | Inclui XMLs e `state.sqlite3` |
| Logs | Pasta do app | CNPJs mascarados |
| ZIP exportado | `exports/` ou pasta escolhida | Você controla o arquivo |

Pastas do app:

- **Windows:** `%LOCALAPPDATA%\ColetaXmlNFSE`
- **macOS:** `~/Library/Application Support/ColetaXmlNFSE`
- **Linux:** `~/.local/share/ColetaXmlNFSE` (a interface web funciona, mas o foco é Windows e macOS)

Na tela há **Abrir pasta do app** e **Apagar dados do app**. O CLI também expõe `wipe`.

### Sem cópia local

A opção **Não guardar cópia local** apaga os XMLs temporários, a posição da última consulta e os logs ao final. A próxima execução baixa tudo de novo. É o modo mais próximo de zero dados em repouso.

O ZIP que você baixa fica em `Downloads` por sua escolha. O app não controla essa pasta.

## Privacidade e segurança

- O servidor escuta somente `127.0.0.1`.
- Cada processo gera um token aleatório. A API exige o header `X-NFSE-Token`.
- `Host` e `Origin` são validados. Não há CORS aberto.
- CSP restritiva no coletor e `connect-src 'none'` no leitor.
- O PFX não é escrito. O PEM temporário fica em diretório `0700`, arquivo `0600`, e é removido no `finally`.
- Resíduos de execuções interrompidas em `nfse_tls_*` são limpos na próxima inicialização.
- Logs mascaram CNPJs. A senha e o PFX nunca entram no log.
- O navegador não usa `localStorage`, `IndexedDB` nem cookies para XMLs. O `localStorage` guarda apenas a lista de CNPJs e as opções de consulta, e pode ser limpo na interface.
- Limite de 5 MB para o PFX e 500 CNPJs por execução.

A conexão navegador e processo é HTTP em loopback. Em máquina compartilhada, use uma conta de usuário confiável. Um processo local com privilégios de rede poderia observar o loopback. O PFX e a senha não saem da máquina, mas o app não deve ser usado em computador com usuários não confiáveis.

Leia [SECURITY.md](SECURITY.md) para o modelo de segurança e o canal de relato.

## CLI e agendamento

```bash
# interface local
python nfse_app.py

# diagnóstico sem segredo
python nfse_app.py doctor

# apagar cópia local, histórico e logs
python nfse_app.py wipe --yes

# execução sem interface
python nfse_app.py run --config agendamento.json
```

Exemplo de `agendamento.json`:

```json
{
  "pfx": "C:\\caminho\\certificado.pfx",
  "password_file": "C:\\caminho\\senha.txt",
  "cnpjs": ["00.000.000/0001-91"],
  "environment": "producao",
  "filter": "Ambas",
  "output": "C:\\caminho\\exports",
  "period_start": "2026-01-01",
  "period_end": "2026-12-31",
  "emission_start": "2026-01-01",
  "emission_end": "2026-12-31",
  "start_nsu": 0,
  "no_cache": false,
  "max_pages": 10000
}
```

- `password_file` deve ter a senha em uma linha. Em macOS e Linux, use `chmod 600`.
- Alternativa: variável de ambiente `NFSE_PFX_PASSWORD`.
- Sem `password_file` nem variável, o CLI pede a senha no terminal.
- `period_start` e `period_end` são a competência; aceitam `AAAA-MM-DD` e, por compatibilidade, `AAAA-MM`. Informe os dois juntos ou nenhum.
- `emission_start` e `emission_end` são a emissão, em `AAAA-MM-DD`; informe os dois juntos ou nenhum.
- Competência e emissão são independentes; quando ambas existem, o XML precisa atender às duas.
- `start_nsu` é usado apenas no primeiro download de cada CNPJ, quando ainda não há histórico salvo.
- No modo `--no-cache`, informe `--output` para o ZIP final.

**Windows:** crie `agendamento.json` e execute `agendar.bat`. Ele registra a tarefa no Task Scheduler com o Python do `.venv`.

**macOS:** use `launchd` com `ProgramArguments` apontando para `.venv/bin/python` e `nfse_app.py run --config ...`. Rode quando a conta estiver logada, porque o certificado e o keychain dependem do usuário.

## Como o projeto é distribuído

Não geramos `.exe` ou `.app` porque um build público sem assinatura mostra avisos
de segurança, e assinatura exige certificado pago (Windows) ou Apple Developer
Program + notarização (macOS). O caminho oficial é **executar pelo código com
Python**, usando os launchers e o guia [docs/USO.md](docs/USO.md).

- `iniciar.bat` e `iniciar.command` verificam o Python, criam o `.venv` e instalam
  as dependências na primeira execução.
- A instalação do Python é feita pelo usuário com o instalador oficial. Os
  launchers não instalam software silenciosamente; eles explicam o que falta.
- Não há release de binários e não há secrets de assinatura configurados.
- `build.py` e `scripts/package.py` continuam no repositório apenas como
  ferramenta local opcional, fora do fluxo oficial. Não use esses artefatos para
  distribuição pública sem assinatura/notarização.

### GitHub Actions

- `CI` roda testes, compilação, JS e leitor estático.
- `E2E` roda os testes Playwright em pull request e por `workflow_dispatch`.
- `Release Python ZIP` roda quando a `main` é sincronizada e publica o ZIP
  Python com SHA-256 como release atual (`latest`). Não gera `.exe`/`.app`.

Testes E2E locais:

```bash
cd tests/e2e
npm install
npx playwright install chromium
PYTHON=../../.venv/bin/python npm test
```

### Gitea Actions

- `.gitea/workflows/ci.yml`: testes, compilação, JS e leitor estático.
- `runs-on: ubuntu-latest`, sem secrets e sem publicação.
- Não há workflow de build de `.exe`/`.app` no Gitea.
- O GitHub gera a release Python quando recebe a `main` sincronizada.
- O E2E continua no GitHub Actions.

### Gerar ZIP para compartilhar

O desenvolvedor pode gerar um pacote apenas com o necessário para executar:

```bash
python scripts/export_source_zip.py
python scripts/export_source_zip.py --output export.zip
```

Sem `--output`, a saída é versionada em `dist/`. Com `--output`, você escolhe
o nome e o local do ZIP:

Saída padrão:

```text
dist/ColetaXMLNFSE-0.2.0.zip
dist/ColetaXMLNFSE-0.2.0.zip.sha256
```

O ZIP contém `COMECE-AQUI.md`, launchers, `nfse/`, `web/`, requirements,
licença e guias. Não contém testes, workflows, `.venv`, caches, builds ou
artefatos. A pessoa que receber precisa apenas de Python 3.10+ para executar
`iniciar.bat`/`iniciar.command`.

### Cloudflare Pages


O leitor pode ser publicado como site estático:

```bash
python3 scripts/build_pages.py
npx wrangler pages deploy pages --project-name coleta-xml-nfse
```

A pasta `pages/` é gerada a partir de `web/leitor.html` e não é versionada. Ela não inclui o coletor, porque o download exige o certificado A1 na máquina do usuário.

## Solução de problemas

- **Python não encontrado ou versão antiga:** instale Python 3.10+ do python.org. No Windows, marque **Add python.exe to PATH**.
- **Porta 8765 ocupada:** o app tenta outra porta e imprime a URL no terminal.
- **“O aplicativo não está respondendo”:** o processo Python foi encerrado. Feche a aba e abra `iniciar.bat` ou `iniciar.command` de novo.
- **PFX recusado:** confira o arquivo e a senha. A3, token ou cartão não é suportado.
- **403 ou 404 do ADN:** 403 normalmente indica certificado ou procuração. 404 com `E2220` ou `E2230` é fim da fila. Qualquer outro 404 é erro.
- **Proxy corporativo:** o proxy precisa permitir TLS mútuo. Se necessário, inclua `adn.nfse.gov.br` e `adn.producaorestrita.nfse.gov.br` em `NO_PROXY`.
- **ZIP não aparece:** o filtro não encontrou XMLs. Veja o log e confira se o CNPJ tem documentos no NSU atual.
- **macOS bloqueou o `.command`:** clique com o botão direito e escolha **Abrir**.
- **Windows SmartScreen:** o `.bat` não é assinado. Use **Mais informações** e **Executar assim mesmo** apenas se confiar na origem.

## Limites

- Aceita A1. Token A3 e cartão não são suportados.
- A API do ADN distribui por NSU. A primeira carga completa pode demorar.
- Eventos são exportados em `Eventos` e preservados em todos os filtros.
- XML sem papel reconhecido vai para `Outros` quando o filtro é `Ambas`.
- XML sem `dCompet` usa a data de emissão ou do evento quando disponível; sem data vai para `SemCompetencia`.
- Um 404 genérico é tratado como erro, não como fim da fila. Só `E2220`, `E2230` e `NENHUM_DOCUMENTO_LOCALIZADO` encerram a consulta.
- A API pode mudar. Valide em Produção Restrita antes da rotina de produção.
- O agendamento no Windows roda quando a conta está logada. O computador precisa estar ligado.

## Estrutura

```text
nfse/
  core.py        # ADN, certificado, CNPJ, XML, cópia local, exportação
  web.py         # servidor local, token, jobs, CSP
  cli.py         # web, run, doctor, wipe
  version.py     # versão atualizada pelo CI
web/
  index.html     # coletor
  app.js
  styles.css
  leitor.html    # leitor
  vendor/fflate.js
scripts/
  build_pages.py
  export_source_zip.py
  set_version.py
  package.py       # opcional/local, fora do fluxo oficial
tests/
docs/
build.py          # opcional/local, fora do fluxo oficial
nfse_app.py
COMECE-AQUI.md
iniciar.bat
iniciar.command
tools/
  instalar.bat
  instalar.command
agendar.bat
agendar.ps1
```

`pages/`, `dist/`, `build/`, `artifacts/` e `.venv/` são gerados e ignorados pelo Git.

## Antes de publicar

- O repositório Gitea usa o mesmo slug `coleta-xml-nfse`; o workflow de CI está em `.gitea/workflows/`.
- Não configure assinatura de executáveis enquanto o projeto for distribuído apenas via Python.
- Revise a licença e o aviso de terceiros com quem for manter o projeto.

## Contribuição

Leia [CONTRIBUTING.md](CONTRIBUTING.md) e [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md). Não inclua PFX, senhas, CNPJs reais, chaves de acesso ou XMLs em issues e pull requests.

## Licença

MIT. Veja [LICENSE](LICENSE) e [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
