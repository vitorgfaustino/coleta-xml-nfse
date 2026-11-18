# Segurança

## Versões suportadas

| Versão | Suporte |
|---|---|
| 0.2.x | Sim |
| Anteriores | Não |

## Como relatar

Use o recurso **Security advisories** do repositório oficial (GitHub ou Gitea) para relatar uma vulnerabilidade em privado. Não abra uma issue pública com detalhes exploráveis.

Se o recurso não estiver disponível, abra uma issue sem detalhes pedindo um canal privado. Não inclua PFX, senha, CNPJ real, chave de acesso ou XML.

Inclua, quando possível:

- versão do app e do Python;
- sistema operacional;
- passos para reproduzir;
- impacto esperado;
- logs com CNPJs e dados pessoais removidos.

O projeto responde em regime de melhor esforço. Não há programa de recompensas nem prazo garantido.

## Escopo

Estão no escopo:

- servidor local em `127.0.0.1`;
- token, `Host`, `Origin` e CSP;
- ciclo de vida do PFX e do PEM temporário;
- cliente TLS do ADN;
- parser de XML e ZIP no leitor;
- permissões de arquivos e diretórios;
- dependências e artefatos de build.

Não estão no escopo:

- o serviço do ADN;
- o certificado A1, a senha ou a procuração do usuário;
- o sistema operacional, o navegador ou extensões instaladas;
- engenharia social e phishing;
- vulnerabilidades em dependências sem impacto demonstrável no app.

## Modelo de segurança

- O navegador envia o PFX e a senha apenas para o processo local.
- O PFX é lido em memória. Ele não é gravado no disco.
- Um PEM temporário com a chave é criado para o `requests`, em diretório `0700` e arquivo `0600`. Ele é removido no `finally`.
- O servidor escuta apenas `127.0.0.1`, exige token e valida `Host` e `Origin`.
- O app não tem telemetria, CDN, conta de usuário ou backend remoto.
- O leitor não usa `localStorage`, `IndexedDB` ou cookies para XMLs.
- Logs mascaram CNPJs, mas mensagens de erro podem conter outros dados. Revise antes de compartilhar.

A conexão navegador e processo é HTTP em loopback. Em máquina compartilhada, um processo local com privilégios de rede poderia observar essa conexão. Use uma conta de usuário confiável.

## Dados em issues e pull requests

Não publique:

- arquivos `.pfx` ou `.p12`;
- senhas;
- CNPJs, CPFs ou nomes de clientes;
- chaves de acesso;
- XMLs reais;
- capturas de tela com dados fiscais.

Use XMLs sintéticos, CNPJs de teste e um PFX descartável.

## Dependências e builds

- Dependabot e Renovate podem abrir atualizações. Revise o diff antes de mesclar.
- Artefatos de release trazem SHA-256. Confira o checksum antes de executar.
- Builds sem assinatura podem gerar aviso do SmartScreen ou do Gatekeeper. Veja [docs/RELEASING.md](docs/RELEASING.md).
