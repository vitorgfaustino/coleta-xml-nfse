const fs = require('fs');
const os = require('os');
const path = require('path');
const { defineConfig } = require('@playwright/test');

const dataDir = fs.mkdtempSync(path.join(os.tmpdir(), 'coleta-xml-nfse-e2e-'));
const root = path.resolve(__dirname, '../..');
const configuredPython = process.env.PYTHON || 'python3';
const python = configuredPython.includes('/') || configuredPython.includes('\\')
  ? path.resolve(root, configuredPython)
  : configuredPython;

module.exports = defineConfig({
  testDir: '.',
  testMatch: '*.spec.js',
  timeout: 30_000,
  expect: { timeout: 7_000 },
  fullyParallel: false,
  workers: 1,
  reporter: [['list']],
  use: {
    baseURL: 'http://127.0.0.1:8773',
    acceptDownloads: true,
    trace: 'retain-on-failure',
  },
  webServer: {
    command: `"${python}" nfse_app.py web --port 8773 --no-browser`,
    cwd: root,
    url: 'http://127.0.0.1:8773/api/health',
    reuseExistingServer: false,
    timeout: 120_000,
    env: {
      NFSE_DATA_DIR: dataDir,
    },
  },
});
