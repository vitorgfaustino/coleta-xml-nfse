# CI no Gitea

## Workflow

`.gitea/workflows/ci.yml` roda:

- checkout;
- Python 3.12;
- instalação de dependências;
- testes unitários;
- compilação Python;
- checagem de JavaScript quando Node está disponível;
- geração do leitor estático.

O workflow usa `runs-on: ubuntu-latest`, não publica releases e não usa secrets.

## Branches

- Trabalho: `agents/**` ou `feature/**`.
- Integração: `develop`.
- Publicação: `main` ou `beta`, conforme aprovação do mantenedor.
- Pull requests para `develop`, `main` e `beta` também executam o CI.

## Requisitos do runner

- Label `ubuntu-latest`.
- Acesso ao espelho/proxy de Actions do Gitea para
  `actions/checkout@v4` e `actions/setup-python@v5`.
- Acesso ao PyPI para instalar as dependências.
- Node é opcional; a checagem de JS é pulada se ele não existir.

Se o firewall bloquear o espelho de Actions, configure um mirror interno ou
substitua as actions por passos equivalentes aprovados pela infraestrutura.

## Sem build de executáveis

O projeto é distribuído como código Python. Este workflow não gera `.exe` ou
`.app`, não assina artefatos e não cria release no Gitea.

A release é feita no GitHub pelo workflow `.github/workflows/release.yml` após a
sincronização da branch `main`.
