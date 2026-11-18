const { test, expect } = require('@playwright/test');
const { AxeBuilder } = require('@axe-core/playwright');

const XML_A = `<NFSe><infNFSe Id="NFSe11111111111111111111111111111111111111111111111111"><nNFSe>123</nNFSe><serie>900</serie><dhEmi>2026-11-01T10:00:00-03:00</dhEmi><emit><CNPJ>11222333000181</CNPJ><xNome>Prestador A</xNome></emit><toma><CNPJ>00000000000191</CNPJ><xNome>Tomador A</xNome></toma><dCompet>2026-11-01</dCompet><vNF>100.00</vNF></infNFSe></NFSe>`;
const XML_B = `<NFSe><infNFSe Id="NFSe22222222222222222222222222222222222222222222222222"><nNFSe>456</nNFSe><serie>901</serie><dhEmi>2026-11-02T10:00:00-03:00</dhEmi><emit><CNPJ>33333333000191</CNPJ><xNome>Prestador B</xNome></emit><toma><CNPJ>11222333000181</CNPJ><xNome>Tomador B</xNome></toma><dCompet>2026-11-02</dCompet><vNF>150.00</vNF></infNFSe></NFSe>`;

test('coletor mantém o fluxo em 4 etapas e as ferramentas locais', async ({ page }) => {
  const errors = [];
  page.on('pageerror', (error) => errors.push(String(error)));
  await page.goto('/');
  await expect(page.locator('.top h1')).toHaveText('Coleta XML NFSE');
  await expect(page.locator('.stepper li')).toHaveCount(4);
  await expect(page.locator('.step-panel[data-step="0"]')).toBeVisible();
  await expect(page.locator('#wizardNext')).toHaveText('Continuar para empresas');
  await expect(page.locator('#cacheList')).toBeVisible();
  await expect(page.locator('#historyList')).toBeVisible();
  await expect(page.locator('#runDiagnostics')).toBeVisible();

  const intro = await page.locator('.intro').evaluate((element) => {
    const style = getComputedStyle(element);
    const paragraph = getComputedStyle(element.querySelector('p'));
    return {
      align: style.textAlign,
      paragraphAlign: paragraph.textAlign,
      height: element.querySelector('p').getBoundingClientRect().height,
      lineHeight: parseFloat(paragraph.lineHeight),
    };
  });
  expect(intro.align).toBe('center');
  expect(intro.paragraphAlign).toBe('center');
  expect(intro.height).toBeLessThan(intro.lineHeight * 2.4);

  await page.evaluate(() => {
    const cnpjs = document.querySelector('#cnpjs');
    cnpjs.value = '00.000.000/0001-91';
    cnpjs.dispatchEvent(new Event('input', { bubbles: true }));
  });
  await page.waitForTimeout(400);
  await page.reload();
  await expect(page.locator('#cnpjs')).toHaveValue(/00\.000\.000\/0001-91/);
  await page.evaluate(() => document.querySelector('#clearPrefs').click());

  await page.setInputFiles('#pfx', {
    name: 'teste.pfx',
    mimeType: 'application/x-pkcs12',
    buffer: Buffer.from('not a pfx'),
  });
  await expect(page.locator('#certLabel')).toContainText('teste.pfx');
  await page.fill('#password', 'x');
  await page.click('#wizardNext');
  await page.fill('#cnpjs', '00.000.000/0001-91');
  await page.click('#wizardNext');
  await page.selectOption('#periodMode', 'range');
  await expect(page.locator('#emissionStart')).toBeEnabled();
  await page.fill('#periodStart', '2026-01-01');
  await page.fill('#periodEnd', '2026-01-31');
  await page.fill('#emissionStart', '2026-01-10');
  await page.fill('#emissionEnd', '2026-01-20');
  await page.click('#wizardNext');
  await expect(page.locator('#reviewChips')).toContainText('Competência');
  await expect(page.locator('#reviewChips')).toContainText('Emissão');
  await page.waitForTimeout(350);

  const results = await new AxeBuilder({ page }).analyze();
  expect(results.violations.filter((item) => ['serious', 'critical'].includes(item.impact))).toEqual([]);
  expect(errors).toEqual([]);
});

test('leitor exporta o filtro em CSV, Excel, XML ZIP e PDF', async ({ page }) => {
  const errors = [];
  page.on('pageerror', (error) => errors.push(String(error)));
  await page.addInitScript(() => {
    window.__printed = 0;
    window.print = () => { window.__printed += 1; };
  });
  await page.goto('/leitor');
  await page.setInputFiles('#files', [
    { name: 'nota-a.xml', mimeType: 'application/xml', buffer: Buffer.from(XML_A) },
    { name: 'nota-b.xml', mimeType: 'application/xml', buffer: Buffer.from(XML_B) },
  ]);
  await expect(page.locator('#mCount')).toHaveText('2');
  await expect(page.locator('#rows')).toContainText('Prestador A');
  await expect(page.locator('#rows')).toContainText('Prestador B');

  await page.fill('#search', 'Prestador A');
  await expect(page.locator('#rows tr')).toHaveCount(1);

  const csv = page.waitForEvent('download');
  await page.click('#export');
  expect((await csv).suggestedFilename()).toBe('coleta-xml-nfse-notas.csv');

  const excel = page.waitForEvent('download');
  await page.click('#exportXlsx');
  expect((await excel).suggestedFilename()).toBe('coleta-xml-nfse-notas.xlsx');

  const zip = page.waitForEvent('download');
  await page.click('#exportZip');
  expect((await zip).suggestedFilename()).toBe('coleta-xml-nfse-xmls.zip');

  await page.click('#printReport');
  expect(await page.evaluate(() => window.__printed)).toBe(1);

  const results = await new AxeBuilder({ page }).analyze();
  expect(results.violations.filter((item) => ['serious', 'critical'].includes(item.impact))).toEqual([]);
  expect(errors).toEqual([]);
});

test('leitor continua utilizável no celular', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/leitor');
  await page.setInputFiles('#files', [
    { name: 'nota-a.xml', mimeType: 'application/xml', buffer: Buffer.from(XML_A) },
  ]);
  await expect(page.locator('#mCount')).toHaveText('1');
  const overflow = await page.evaluate(() => ({
    scroll: document.documentElement.scrollWidth,
    client: document.documentElement.clientWidth,
  }));
  expect(overflow.scroll).toBeLessThanOrEqual(overflow.client + 1);
  const filterColumns = await page.locator('.filter').evaluate((element) => (
    getComputedStyle(element).gridTemplateColumns.split(' ').length
  ));
  expect(filterColumns).toBe(1);
});
