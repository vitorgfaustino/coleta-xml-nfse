## Resumo

Descreva o problema e a mudança em uma ou duas frases.

## Tipo

- [ ] Correção
- [ ] Recurso
- [ ] Documentação
- [ ] Build ou CI
- [ ] Refatoração sem mudança de comportamento

## Testes

- [ ] `python -m unittest discover -s tests -v`
- [ ] `python -m compileall -q nfse nfse_app.py scripts build.py`
- [ ] `node --check web/app.js`
- [ ] `python scripts/build_pages.py`
- [ ] Teste manual no Windows
- [ ] Teste manual no macOS

Descreva o teste manual, se houver.

## Interface

Se alterou a UI, descreva o antes e o depois e anexe uma captura sem dados reais.

- [ ] Verifiquei contraste, foco de teclado, rótulos e os estados vazio, carregando e erro.
- [ ] Não incluí PFX, senha, CNPJ real, CPF, chave de acesso ou XML.

## Segurança

- [ ] Não adicionei segredo, certificado ou dado fiscal ao repositório.
- [ ] A mudança mantém o servidor em loopback e a validação de token, Host e Origin.
- [ ] Revisei o impacto no ciclo de vida do PFX e do PEM temporário.

## Changelog

- [ ] Atualizei o `CHANGELOG.md` para mudanças visíveis ao usuário.
