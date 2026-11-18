# Privacidade

Este documento descreve o fluxo de dados do aplicativo. Ele não é aconselhamento jurídico.

## Resumo

- O projeto não opera backend, conta de usuário ou telemetria.
- O certificado e os XMLs ficam na máquina do usuário.
- O navegador conversa apenas com o processo local em `127.0.0.1`.
- A única conexão externa do coletor é com o ADN, por TLS mútuo.
- O leitor processa XMLs no navegador e não envia arquivos para servidor.

## Mapa de dados

| Dado | Onde fica | Persistência | Como apagar |
|---|---|---|---|
| PFX | Memória do navegador e do processo | Não persiste | Fechar a execução |
| Senha | Memória do processo | Não persiste | Fechar a execução |
| Lista de CNPJs e opções | `localStorage` do navegador | Sim, até limpar | Botão **Limpar** na etapa Empresas |
| XMLs baixados | Pasta do app | Sim, por padrão | Apagar dados do app ou `wipe --yes` |
| Índice dos XMLs | `state.sqlite3` | Sim, por padrão | Apagar dados do app ou `wipe --yes` |
| Posição da última consulta | `state.sqlite3` | Sim, por padrão | Apagar dados do app ou `wipe --yes` |
| Histórico de execuções | `state.sqlite3` | Sim, por padrão | Apagar dados do app ou `wipe --yes` |
| Logs | Pasta do app | Sim, por padrão | Apagar dados do app ou `wipe --yes` |
| ZIP exportado | `exports/` ou pasta escolhida | Sim, até você apagar | Apagar o arquivo |
| CSV, Excel, XML ZIP ou PDF | `Downloads` | Sim, até você apagar | Apagar o arquivo |
| Backup local | ZIP baixado por você | Sim, até você apagar | Apagar o arquivo |

Pastas:

- Windows: `%LOCALAPPDATA%\ColetaXmlNFSE`
- macOS: `~/Library/Application Support/ColetaXmlNFSE`
- Linux: `~/.local/share/ColetaXmlNFSE`

Na primeira execução, dados de cursor e cache do nome antigo `NFSeXmlDownloader` são copiados para a nova pasta.

## Ciclo do certificado

1. O navegador lê o PFX selecionado.
2. O PFX é enviado por HTTP em loopback ao processo local.
3. O processo abre o PFX em memória.
4. Um PEM temporário com a chave e a cadeia é criado para o `requests`.
5. O PEM fica em diretório `0700` e arquivo `0600` no diretório temporário do usuário.
6. O PEM é removido no `finally`.
7. O PFX não é gravado.

Se o processo for morto durante a chamada, o diretório `nfse_tls_*` pode permanecer até a próxima inicialização. O app remove resíduos com mais de 24 horas.

No Windows, a proteção do diretório temporário depende da ACL do perfil do usuário. No macOS e no Linux, dependem das permissões `0700` e `0600`.

## Servidor local

- Escuta apenas `127.0.0.1`.
- Gera um token aleatório por processo.
- Exige o token na API.
- Valida `Host` e `Origin`.
- Não envia CORS aberto.
- Aplica CSP no coletor e no leitor.
- Não registra a senha nem o PFX.

A conexão é HTTP em loopback. Em uma máquina compartilhada, outro processo com privilégios de rede poderia observar essa conexão. Use uma conta de usuário confiável.

## Leitor de XML

- Lê XML e ZIP no navegador.
- Não usa `fetch`, XHR, WebSocket ou beacon.
- Não usa cookies, `localStorage` ou `IndexedDB` para XMLs. O coletor usa `localStorage` apenas para a lista de CNPJs e opções de consulta.
- Não envia arquivos para servidor.
- As exportações CSV, Excel, XML ZIP e impressão/PDF são criadas no navegador e baixadas por ação do usuário.
- O botão **Abrir no leitor** transfere o ZIP entre abas por `postMessage` same-origin; não há upload nem request de rede do leitor.
- Recarregar o leitor mantém apenas a lista de notas em memória; não há persistência de XMLs no navegador.

## Filtros de data

Com um período selecionado, o app guarda e exporta apenas XMLs que atendam aos
intervalos de **competência** e/ou **emissão** escolhidos. Os dois filtros são
independentes; se ambos estiverem preenchidos, o XML precisa atender aos dois.
As datas são comparadas por dia.

XMLs fora dos filtros são ignorados e não entram na cópia local. O cursor avança
mesmo assim, então mudar o período depois exige um NSU inicial ou uma nova carga.
O filtro de data não reduz a quantidade de consultas ao ADN: a distribuição é
por NSU e o filtro é aplicado localmente.

O campo avançado **NSU inicial** permite pular histórico antigo no primeiro download de cada CNPJ. Ele não altera downloads que já têm cursor salvo.

## Modo sem cópia local

A opção **Não guardar cópia local** usa um diretório temporário, não salva a posição da última consulta, não registra histórico e apaga XMLs, histórico e logs ao final. O ZIP final é mantido apenas para download e removido na próxima execução ou ao encerrar.

## Backup e restauração

O backup baixa um ZIP com `state.sqlite3` e os XMLs da cópia local. A restauração valida o ZIP, o banco e os caminhos antes de substituir os dados atuais. O backup contém dados fiscais; guarde-o com o mesmo cuidado dos XMLs originais.

## Cloudflare Pages

Se o leitor for publicado no Cloudflare Pages:

- o site é estático;
- não há Functions, D1, R2, KV, cookies ou analytics;
- nenhum XML é enviado;
- a Cloudflare pode registrar metadados de acesso, como IP e user agent, conforme a política dela;
- o conteúdo fiscal nunca chega ao Pages.

## Pastas sincronizadas

Não coloque o PFX em OneDrive, iCloud, Dropbox ou outro serviço de sincronização. O app não copia o PFX, mas o arquivo original continua onde você o guardou.

A pasta do app fica em um diretório local por padrão. Se você mudar a pasta de exportação para uma pasta sincronizada, os XMLs e o ZIP podem sair da máquina.

## LGPD

O projeto não opera um serviço central que receba dados fiscais. Quem usa o app controla os arquivos na própria máquina. Se você distribuir o app para terceiros, avalie o seu papel como controlador ou operador e mantenha uma política de retenção adequada.

## Exclusão

Use **Apagar dados do app** na interface ou:

```bash
python nfse_app.py wipe --yes
```

A ação remove a cópia local dos XMLs, o índice, a posição da última consulta e os logs. Ela não remove arquivos que você já baixou para `Downloads` ou para outra pasta.
