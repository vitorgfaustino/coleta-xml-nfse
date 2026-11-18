# Contribuição

Obrigado por contribuir. Leia o [Código de conduta](CODE_OF_CONDUCT.md) e o [modelo de segurança](SECURITY.md).

## Ambiente

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m unittest discover -s tests -v
```

No Windows, use `.venv\Scripts\python.exe` no lugar de `.venv/bin/python`.

## Verificações antes do pull request

```bash
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python -m compileall -q nfse nfse_app.py scripts build.py
node --check web/app.js
python3 scripts/build_pages.py
```

Se você alterou o leitor, teste com XML de NFS-e, NFe, evento de cancelamento e ZIP.

## Execução

O fluxo oficial é Python, sem `.exe`/`.app`:

```bash
.venv/bin/python nfse_app.py
```

Leia [docs/USO.md](docs/USO.md) para instalação e uso e
[docs/GITEA_CI.md](docs/GITEA_CI.md) antes de mexer nos workflows. Builds com
PyInstaller são opcionais/locais e não fazem parte da distribuição atual.

## Dados reais

Não inclua PFX, senhas, CNPJs reais, CPFs, chaves de acesso ou XMLs em issues, testes, commits ou capturas de tela. Use dados sintéticos.

## Código

- Python 3.10+.
- Type hints quando ajudam a leitura.
- Quatro espaços, sem tabs.
- Sem novas dependências de runtime sem discussão prévia.
- Erros em português, com mensagens que expliquem a ação.
- Não ignore erros da API para “fingir sucesso”. 404 genérico é erro.

## UI e texto

- Textos em português do Brasil.
- Sem jargão desnecessário. Prefira “cópia local” a “cache” e “histórico da última consulta” a “cursor” na interface.
- Sem em dash. Use vírgula, ponto, dois-pontos ou parênteses.
- Sem números, depoimentos ou promessas sem fonte.
- Toda ação precisa funcionar. Não envie botão ou link morto.
- Verifique contraste, foco de teclado, rótulos e os estados vazio, carregando e erro.

## Pull requests

- Um assunto por PR.
- Explique o problema e a solução.
- Inclua testes para mudanças de comportamento.
- Para mudanças de UI, inclua uma captura sem dados reais.
- Atualize o `CHANGELOG.md` quando a mudança for visível ao usuário.

## Commits

Use mensagens curtas no imperativo:

```text
corrige retomada de NSU após erro 429
adiciona leitor de ZIP no navegador
```

## Licença

Ao contribuir, você concorda em licenciar sua contribuição sob a licença MIT deste repositório.
