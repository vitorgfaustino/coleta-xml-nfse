# Changelog

Formato baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/). Versionamento [SemVer](https://semver.org/lang/pt-BR/).

## [Não lançado]

### Adicionado

- CI para GitHub e Gitea, distribuição como código Python e launchers de instalação.
- Licença MIT e arquivos de contribuição, segurança e privacidade.
- Leitor com suporte a ZIP, busca, filtros, detalhes e CSV.
- Filtro de competência no coletor, com opção de NSU inicial no primeiro download.
- Resumo do leitor calculado sobre o filtro aplicado, com contagem e valor explícitos.
- Classificação automática de tomados e prestados pela pasta do ZIP exportado.
- Número da NFS-e exibido na coluna Número / Série.
- Coluna de documento do destinatário, pesquisável pela busca universal.
- Correção da coluna Emitente com fallback entre os nós de prestador e emitente.
- Botão **Abrir no leitor** que envia o ZIP local para o leitor em outra aba.
- Marca pública **Coleta XML NFSE** e repositório `coleta-xml-nfse`, com migração automática da pasta de dados antiga.
- Coletor em quatro etapas, com revisão final que confirma e inicia o download.
- Transição suave entre as etapas, com animação de entrada e destaque gradual no stepper.
- Seletor de mês/ano aberto ao clicar no campo ou no rótulo de competência.
- Introdução centralizada, com o texto de privacidade em duas linhas no desktop.
- Histórico das últimas execuções, com última sincronização e resumo por CNPJ.
- Cópia local por CNPJ, com remoção individual, backup e restauração validada.
- Diagnóstico de pasta, cache, proxy, DNS e TCP do ADN.
- Lista de CNPJs e opções de consulta lembradas no navegador, com botão para limpar.
- Exportação do leitor em CSV filtrado, Excel com abas, ZIP dos XMLs filtrados e impressão/Salvar como PDF.
- Validade do certificado exibida no resultado da execução.
- Filtro de consulta por competência e emissão, com intervalos por dia.
- Migração do banco para armazenar data completa de competência e emissão.
- AGENTS.md e guia de uso/instalação com Python.
- Orientação explícita para não gerar `.exe`/`.app` sem certificado e runners nativos.
- PDF da lista em A4 paisagem, sem corte das colunas e totais.
- Leitor com estado compacto “ZIP ... carregado” e opções de novo ZIP/pasta.
- Rodapé com licença MIT, autoria e link do repositório.
- **Abrir no leitor** como ação principal ao final do download; **Baixar ZIP** fica como ação secundária.
- Explicação do ADN no coletor e no rodapé do leitor.
- Cabeçalho unificado para coletor e leitor, com o menu **Coletor / Leitor de XML** no lugar da badge.
- Badge **Processamento local** movida para a introdução das duas telas.
- Colunas de etapas e de conteúdo do coletor com a mesma altura em cada etapa.
- Texto do convite ao leitor em uma linha no desktop.
- Redesign do cabeçalho, dos filtros com chips, da busca com ícone e da tabela com cabeçalho fixo.
- Modo sem cópia local, com remoção de XMLs, histórico e logs ao final.
- Testes de CNPJ alfanumérico, contrato do ADN, retry, exportação, permissões e servidor local.

### Alterado

- Interface web local em `127.0.0.1`, sem Tkinter.
- Copy da interface em linguagem mais direta.
- Leitor com mais destaque no coletor.
- Navegação entre coletor e leitor.
- Filtros do leitor em grade responsiva, com rótulos visíveis e sem cortes.
- Leitor com uma busca universal e apenas filtros de seleção; campos separados de empresa, destinatário e datas foram removidos.
- Estados vazio, carregando e erro do leitor mais claros.

### Removido

- Aplicativo Tkinter antigo.
- Leitor standalone duplicado na raiz do projeto.
- Documento antigo `LEIA-ME.md`.

### Segurança

- PFX mantido em memória, sem gravação.
- PEM temporário com permissões restritas e remoção no `finally`.
- Token, `Host`, `Origin` e CSP no servidor local.
- Logs com CNPJs mascarados.
- Lock de execução com recuperação de processo morto.

## [0.2.0] - 2026-11-17

Primeira versão da interface local.

### Adicionado

- Consulta ao ADN por NSU com certificado A1.
- Retomada por CNPJ.
- Classificação de prestados, tomados, eventos e outros.
- Exportação ZIP.
- Leitor local de XML e ZIP.
- CLI `web`, `run`, `doctor` e `wipe`.
- Testes automatizados.

### Segurança

- Servidor apenas em loopback.
- Validação de token, `Host` e `Origin`.
- CSP no coletor e no leitor.
