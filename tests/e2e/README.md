# Testes E2E

Testes de interface com Playwright para o coletor e o leitor.

## Requisitos

- Python com as dependências do projeto (`requirements.txt`).
- Node.js 20 ou superior.
- Navegador Chromium do Playwright.

## Executar

```bash
cd tests/e2e
npm install
npx playwright install chromium
PYTHON=../../.venv/bin/python npm test
```

No Windows, use `PYTHON=..\..\.venv\Scripts\python.exe` no PowerShell:

```powershell
$env:PYTHON="..\..\.venv\Scripts\python.exe"
npm test
```

O `webServer` inicia o aplicativo em `127.0.0.1:8773` com um diretório de dados temporário. Nenhum PFX real é usado.
