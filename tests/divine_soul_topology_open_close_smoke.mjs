import { chromium } from 'playwright';

const BASE_URL = process.env.CLP_TEST_URL || 'http://127.0.0.1:4173';

const browser = await chromium.launch({ headless: true });
const page = await browser.newPage();

await page.goto(BASE_URL, { waitUntil: 'networkidle', timeout: 120000 });
await page.evaluate(async () => {
  await window.openDivineSoulTopology?.({
    question: '我要不要给自己一次重新开始的机会',
    engineb_session: {
      value_profile: { summary: '你更看重恢复秩序后的长期成长。' },
    },
  });
});

await page.waitForSelector('.dst-root', { timeout: 15000 });

const opened = await page.evaluate(() => ({
  root: Boolean(document.querySelector('.dst-root')),
  canvas: Boolean(document.querySelector('[data-dst-canvas]')),
  controls: Boolean(document.querySelector('[data-dst-flight-toggle]')),
}));

await page.evaluate(async () => {
  await window.closeDivineSoulTopology?.();
});

await page.waitForTimeout(400);

const closed = await page.evaluate(() => ({
  root: Boolean(document.querySelector('.dst-root')),
  bodyOverflow: document.body.style.overflow || '',
}));

await browser.close();

console.log(JSON.stringify({ opened, closed }, null, 2));

if (!opened.root || !opened.canvas || !opened.controls) process.exit(1);
if (closed.root) process.exit(1);
if (closed.bodyOverflow !== '') process.exit(1);
