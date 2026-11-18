# Comece aqui

O **Coleta XML NFSE** roda no seu computador. Não há `.exe` ou `.app` para
baixar: o aplicativo usa Python 3.10 ou superior.

Se você recebeu este projeto como um ZIP de release, ele já é o pacote de uso.
Não é necessário clonar o repositório. Se veio do GitHub/Gitea, prefira baixar
o ZIP da release atual em:
<https://github.com/vitorgfaustino/coleta-xml-nfse/releases/latest>.

## O que você precisa

- Windows 10/11 ou macOS 13+.
- Python 3.10 ou superior.
- Certificado A1 em `.pfx` ou `.p12`.
- Procuração vigente para cada CNPJ consultado.
- Internet para consultar o ADN.

## Instalar o Python

### Windows

1. Baixe em <https://www.python.org/downloads/windows/>.
2. Na primeira tela, marque **Add python.exe to PATH**.
3. Conclua a instalação.

### macOS

1. Baixe em <https://www.python.org/downloads/macos/> ou use
   `brew install python@3.12`.
2. Conclua a instalação.

## Executar

1. Extraia a pasta do projeto.
2. **Windows:** dê duplo clique em `iniciar.bat`.
3. **macOS:** dê duplo clique em `iniciar.command`.
4. O navegador abre em `http://127.0.0.1:8765`.

`iniciar` faz tudo na primeira vez: verifica o Python, cria o ambiente local,
instala as dependências e abre o aplicativo.

`tools/instalar.bat` e `tools/instalar.command` são opcionais; apenas preparam
o ambiente sem abrir a interface.

## Primeiro uso

1. Selecione o certificado A1 e digite a senha.
2. Informe os CNPJs.
3. Escolha a consulta. Você pode filtrar por **Competência** e/ou **Emissão**,
   usando datas completas e intervalos de dias.
4. Confira a revisão e clique em **Confirmar e baixar**.
5. Ao final, use **Abrir no leitor** ou baixe o ZIP.

O guia completo está em [docs/USO.md](docs/USO.md).

## Privacidade

O certificado, a senha e os XMLs não passam por servidores do projeto. A única
conexão externa é com o ADN. O leitor processa os arquivos no navegador.

## Problemas comuns

- **Python não encontrado:** instale a versão atual e reabra o launcher.
- **Gatekeeper/SmartScreen:** permita a execução do `.command`/`.bat` se confiar
  na origem.
- **Porta ocupada:** feche a instância anterior ou use a URL mostrada no terminal.
- **Certificado recusado:** confira o arquivo, a senha e a validade.
