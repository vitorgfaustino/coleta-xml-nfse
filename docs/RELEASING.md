# Distribuição

## Decisão atual

O projeto é distribuído **como código Python**, sem `.exe` ou `.app`.

Motivo: um executável público sem assinatura mostra avisos de segurança, e a
assinatura exige custos recorrentes:

- Windows: certificado de assinatura de código OV/EV ou Azure Trusted Signing.
- macOS: Apple Developer Program, Developer ID e notarização.

Para o escopo atual, a exigência de Python é aceitável e evita esses custos.
Não há release de binários, workflow de build nativo ou secrets de assinatura.

## Como outras pessoas usam

1. Baixam o ZIP da release pública no GitHub.
2. Instalam Python 3.10 ou superior.
3. Extraem o ZIP e executam `iniciar.bat`/`iniciar.command`.

O `iniciar` cria o ambiente e instala as dependências na primeira execução.
`tools/instalar` é opcional. Desenvolvedores clonam o repositório; usuários finais
não precisam clonar.

A release é criada no **GitHub** pelo workflow `.github/workflows/release.yml`
quando a `main` sincronizada chega ao repositório. O Gitea não publica uma
release separada.

O guia completo está em [USO.md](USO.md).

## O que não é publicado

- `.exe` Windows.
- `.app`/DMG macOS.
- ZIP de executável.
- Release de binário.
- Release no Gitea.
- Atualização automática.

`build.py` e `scripts/package.py` continuam no repositório apenas como
ferramenta local opcional. Eles não fazem parte do fluxo oficial.

## Se um dia houver binários assinados

Só faça isso com decisão explícita e orçamento aprovado. Seria necessário:

1. Registrar runners nativos Windows e macOS (ou usar os runners nativos do
   GitHub).
2. Comprar/obter o certificado Windows e a assinatura Apple.
3. Configurar secrets de assinatura fora do repositório.
4. Assinar e notarizar antes de publicar.
5. Testar em máquina limpa, sem Python.
6. Publicar checksum SHA-256 e instruções de verificação.

Um runner Linux não gera `.exe` nem `.app`; PyInstaller não faz cross-compile.
A release oficial deste projeto é o ZIP Python, sem binários.

## Python

- Windows: Python 3.12 do python.org, com **Add python.exe to PATH**.
- macOS: python.org ou `brew install python@3.12`.
- Os launchers verificam a versão e orientam a instalação; não instalam
  software silenciosamente.

## Segurança

- Não coloque PFX, senha, chave privada, token ou certificado no repositório.
- Não publique XMLs, CNPJs reais, CPFs ou chaves de acesso.
- Se builds assinados forem criados no futuro, use secrets e runners
  protegidos.
