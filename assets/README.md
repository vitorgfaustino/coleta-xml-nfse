# Ícones

`icon.svg` é um placeholder de documento, usado também no favicon. Substitua por uma marca própria antes de uma release pública.

O PyInstaller usa automaticamente:

- `assets/icon.ico` no Windows;
- `assets/icon.icns` no macOS.

Para gerar os arquivos:

- Windows: converta o SVG para ICO em 16, 32, 48, 128 e 256 px.
- macOS: crie um iconset e rode `iconutil -c icns`.

Não inclua marcas de terceiros sem permissão.
