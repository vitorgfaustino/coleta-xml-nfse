# Como usar e executar

## Escolha o modo

O projeto é distribuído **como código Python**, sem `.exe` ou `.app`. Isso evita
a necessidade de certificado de assinatura pago e mantém o app transparente.

| Perfil | Caminho |
|---|---|
| Usuário final, contador ou procurador | Instalar Python 3.10+ e usar `iniciar.bat`/`iniciar.command` |
| Desenvolvedor | Código-fonte + `.venv` |
| Uso interno | Código-fonte + `.venv` |

A primeira execução via `iniciar` cria o ambiente virtual e instala as
dependências. As execuções seguintes são rápidas. `tools/instalar.bat`/`tools/instalar.command` existem apenas para
preparar o ambiente sem iniciar a interface.

### O que o app precisa

- Windows 10/11 ou macOS 13+.
- Python 3.10 ou superior.
- Certificado A1 em `.pfx` ou `.p12`.
- Procuração vigente para cada CNPJ consultado.
- Conexão HTTPS com o ADN.

### Verificação do Python

Os launchers verificam a versão e mostram instruções se o Python não estiver
instalado ou for antigo. Eles **não instalam software silenciosamente**; abrem
a página oficial ou orientam a instalação. Isso evita executar instaladores sem
o consentimento do usuário.

## Instalar o Python

### Windows

1. Baixe Python 3.12 em <https://www.python.org/downloads/windows/>.
2. Marque **Add python.exe to PATH** na primeira tela do instalador.
3. Confirme em um terminal:

```powershell
py -3.12 --version
```

4. Extraia o projeto e dê duplo clique em `iniciar.bat`. Ele cria o `.venv`,
   instala as dependências e abre o app na primeira execução.
5. `tools/instalar.bat` é opcional: prepara o ambiente sem abrir o app, útil para
   manutenção ou agendamento.

### macOS

1. Baixe Python 3.12 em <https://www.python.org/downloads/macos/> ou use
   `brew install python@3.12`.
2. Confirme:

```bash
python3 --version
```

3. Dê duplo clique em `iniciar.command`. Ele cria o `.venv`, instala as
   dependências e abre o app na primeira execução.
4. `tools/instalar.command` é opcional: prepara o ambiente sem abrir o app.

Se o macOS bloquear o `.command`, clique com o botão direito e escolha **Abrir**.

### Terminal, qualquer sistema

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python nfse_app.py
```

No Windows, use `.venv\Scripts\python.exe`.

## Usando o coletor

1. **Certificado:** selecione o A1 e digite a senha.
2. **Empresas:** informe um CNPJ por linha.
3. **Consulta:**
   - escolha o ambiente;
   - escolha prestados, tomados ou ambos;
   - escolha **Todo o período** ou **Selecionar período**;
   - no período selecionado, preencha **Competência** e/ou **Emissão** com
     datas completas. Os intervalos são por dia e podem ser combinados;
   - se quiser pular histórico antigo no primeiro download, informe um NSU
     inicial em **Opções avançadas**;
4. **Revisão:** confira o resumo e clique em **Confirmar e baixar**.

Observações importantes:

- O ADN distribui por NSU, não por período. O filtro de datas decide o que é
  **salvo e exportado**; ele não reduz a quantidade de requisições.
- Quando competência e emissão estão preenchidas, o XML precisa atender aos
  dois intervalos.
- XMLs fora do filtro não são guardados, mas o cursor avança. Para consultar
  um período anterior depois, use um NSU inicial ou apague a cópia local.
- Ao final, **Abrir no leitor** é o botão principal.

## Usando o leitor

- Arraste XMLs, uma pasta ou o ZIP do coletor.
- Com um ZIP carregado, a área grande é substituída por uma barra compacta com
  o nome do ZIP e as opções **Novo ZIP/XML** e **Nova pasta**.
- A busca é universal; os outros filtros são seletores.
- Exporte o filtro em CSV, Excel, XML ZIP ou use **Imprimir / PDF**. O PDF é
  gerado em A4 paisagem.
- O leitor não envia arquivos para servidor.

## Gerar um ZIP para outra pessoa

Quem clona o repositório para desenvolver pode gerar um pacote de execução:

```bash
python scripts/export_source_zip.py
python scripts/export_source_zip.py --output export.zip
```

Sem `--output`, o arquivo sai em `dist/ColetaXMLNFSE-<versao>.zip`. Com
`--output`, ele sai no caminho escolhido, por exemplo `export.zip`. Em ambos os
casos é gerado um `.sha256` ao lado.
Ele inclui o guia `COMECE-AQUI.md`, `iniciar.bat`/`iniciar.command`, o código
Python, o leitor web, requirements, licença e documentação de uso. Não inclui
testes, workflows, `.venv`, caches, builds ou artefatos.

Quem receber o ZIP precisa de Python 3.10+; não é um `.exe`/`.app`.

## Dados locais

- Windows: `%LOCALAPPDATA%\ColetaXmlNFSE`
- macOS: `~/Library/Application Support/ColetaXmlNFSE`
- Linux: `~/.local/share/ColetaXmlNFSE`

A tela do coletor mostra a pasta, a cópia local, a última execução e as opções
de backup/restauração e diagnóstico.

## Problemas comuns

- **Certificado recusado:** confira o arquivo, a senha e a validade.
- **Erro de procuração:** confirme a autorização do CNPJ no serviço da NFS-e.
- **Nenhum XML:** o filtro pode estar restritivo ou o CNPJ não tem documentos
  no NSU atual.
- **Aba do leitor não abriu:** permita pop-up ou baixe o ZIP e arraste no leitor.
- **Gatekeeper bloqueou o `.command`:** clique com o botão direito e escolha
  **Abrir**. Se necessário, libere em **Privacidade e Segurança**.
- **SmartScreen avisou sobre o `.bat`:** use **Mais informações → Executar
  assim mesmo** apenas se confiar na origem.
