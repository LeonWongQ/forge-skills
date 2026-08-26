import fs from 'node:fs';
import path from 'node:path';
import process from 'node:process';
import { performance } from 'node:perf_hooks';
import { fileURLToPath } from 'node:url';
import { chromium } from 'playwright-core';

function parseArgs(argv) {
  const options = { inventory: false, timeout: 30_000 };
  for (let index = 0; index < argv.length; index += 1) {
    const argument = argv[index];
    if (argument === '--inventory') {
      options.inventory = true;
    } else if (argument === '--url') {
      options.url = argv[++index];
    } else if (argument === '--selector') {
      options.selector = argv[++index];
    } else if (argument === '--browser') {
      options.browser = argv[++index];
    } else if (argument === '--timeout') {
      options.timeout = Number(argv[++index]);
    } else {
      throw new Error(`Unknown argument: ${argument}`);
    }
  }
  if (!Number.isFinite(options.timeout) || options.timeout <= 0) {
    throw new Error('--timeout must be a positive number of milliseconds');
  }
  return options;
}

function existingFile(filePath) {
  return filePath && fs.existsSync(filePath) && fs.statSync(filePath).isFile();
}

function pathExecutables(names) {
  const directories = (process.env.PATH || '').split(path.delimiter).filter(Boolean);
  return directories.flatMap((directory) => names.map((name) => path.join(directory, name)));
}

function browserCandidates() {
  if (process.platform === 'win32') {
    const programFiles = process.env.ProgramFiles;
    const programFilesX86 = process.env['ProgramFiles(x86)'];
    const localAppData = process.env.LOCALAPPDATA;
    return [
      ['chrome', programFiles && path.join(programFiles, 'Google/Chrome/Application/chrome.exe')],
      ['chrome', programFilesX86 && path.join(programFilesX86, 'Google/Chrome/Application/chrome.exe')],
      ['chrome', localAppData && path.join(localAppData, 'Google/Chrome/Application/chrome.exe')],
      ['edge', programFiles && path.join(programFiles, 'Microsoft/Edge/Application/msedge.exe')],
      ['edge', programFilesX86 && path.join(programFilesX86, 'Microsoft/Edge/Application/msedge.exe')],
      ['edge', localAppData && path.join(localAppData, 'Microsoft/Edge/Application/msedge.exe')],
      ...pathExecutables(['chrome.exe', 'msedge.exe', 'chromium.exe']).map((filePath) => ['chromium', filePath]),
    ];
  }

  if (process.platform === 'darwin') {
    return [
      ['chrome', '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'],
      ['edge', '/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge'],
      ['chromium', '/Applications/Chromium.app/Contents/MacOS/Chromium'],
      ...pathExecutables(['google-chrome', 'microsoft-edge', 'chromium']).map((filePath) => ['chromium', filePath]),
    ];
  }

  return pathExecutables([
    'google-chrome-stable',
    'google-chrome',
    'microsoft-edge-stable',
    'microsoft-edge',
    'chromium',
    'chromium-browser',
  ]).map((filePath) => ['chromium', filePath]);
}

function inventory(explicitBrowser) {
  if (explicitBrowser) {
    return existingFile(explicitBrowser)
      ? [{ name: 'explicit', executablePath: path.resolve(explicitBrowser) }]
      : [];
  }

  const seen = new Set();
  return browserCandidates()
    .filter(([, executablePath]) => existingFile(executablePath))
    .filter(([, executablePath]) => {
      const normalized = path.resolve(executablePath).toLowerCase();
      if (seen.has(normalized)) return false;
      seen.add(normalized);
      return true;
    })
    .map(([name, executablePath]) => ({ name, executablePath: path.resolve(executablePath) }));
}

function output(value) {
  process.stdout.write(`${JSON.stringify(value, null, 2)}\n`);
}

async function waitForContentSelector(page, selectors, timeout) {
  const handle = await page.waitForFunction((candidateSelectors) => {
    for (const selector of candidateSelectors) {
      const element = document.querySelector(selector);
      if (!element) continue;
      const style = window.getComputedStyle(element);
      const visible = style.visibility !== 'hidden'
        && style.display !== 'none'
        && element.getClientRects().length > 0;
      if (visible && element.innerText.trim()) return selector;
    }
    return null;
  }, selectors, { timeout });
  return handle.jsonValue();
}

export async function extractContent(page, selectors, timeout = 30_000) {
  const startedAt = performance.now();
  const fallbackIndex = selectors.indexOf('body');
  const primarySelectors = fallbackIndex === -1 ? selectors : selectors.slice(0, fallbackIndex);
  let selector;

  if (primarySelectors.length) {
    const primaryTimeout = fallbackIndex === -1 ? timeout : Math.min(timeout, 3_000);
    try {
      selector = await waitForContentSelector(page, primarySelectors, primaryTimeout);
    } catch (error) {
      if (fallbackIndex === -1 || error?.name !== 'TimeoutError') throw error;
    }
  }
  if (!selector && fallbackIndex !== -1) {
    const remaining = Math.max(1, timeout - (performance.now() - startedAt));
    selector = await waitForContentSelector(page, ['body'], remaining);
  }
  if (!selector) {
    throw new Error(`No visible, non-empty content found for selector(s): ${selectors.join(', ')}`);
  }
  const content = (await page.locator(selector).first().innerText()).trim();
  return { content, selector };
}

async function main() {
  const options = parseArgs(process.argv.slice(2));
  const browsers = inventory(options.browser);

  if (options.inventory) {
    output({ browsers, browserInstallationAttempted: false });
    return;
  }

  if (!options.url) throw new Error('--url is required unless --inventory is used');
  if (browsers.length === 0) {
    output({
      error: 'BROWSER_NOT_FOUND',
      message: 'No supported local Chrome, Edge, or Chromium executable was found.',
      browserInstallationAttempted: false,
    });
    process.exitCode = 2;
    return;
  }

  const startedAt = performance.now();
  const launchStartedAt = performance.now();
  const selectedBrowser = browsers[0];
  const browser = await chromium.launch({
    executablePath: selectedBrowser.executablePath,
    headless: true,
  });
  const launchMs = performance.now() - launchStartedAt;

  try {
    const page = await browser.newPage();
    const navigationStartedAt = performance.now();
    await page.goto(options.url, { waitUntil: 'domcontentloaded', timeout: options.timeout });
    const navigationMs = performance.now() - navigationStartedAt;

    const extractionStartedAt = performance.now();
    const selectors = options.selector
      ? [options.selector]
      : ['main', 'article', '[role="main"]', '.markdown-body', 'body'];
    const { content } = await extractContent(page, selectors, options.timeout);
    const extractionMs = performance.now() - extractionStartedAt;

    output({
      url: options.url,
      finalUrl: page.url(),
      title: await page.title(),
      browser: selectedBrowser,
      content,
      timingsMs: {
        launch: Math.round(launchMs),
        navigation: Math.round(navigationMs),
        extraction: Math.round(extractionMs),
        total: Math.round(performance.now() - startedAt),
      },
      browserInstallationAttempted: false,
    });
  } finally {
    await browser.close();
  }
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  main().catch((error) => {
    output({
      error: error.code || error.name || 'PAGE_READ_FAILED',
      message: error.message,
      browserInstallationAttempted: false,
    });
    process.exitCode = 1;
  });
}
