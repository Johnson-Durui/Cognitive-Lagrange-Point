import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { chromium } from 'playwright';

const BASE_URL = process.env.CLP_TEST_URL || 'http://127.0.0.1:4173';

const [appSource, builtIndex] = await Promise.all([
  readFile('app.js', 'utf8'),
  readFile('dist/index.html', 'utf8'),
]);

assert.doesNotMatch(
  appSource,
  /import\s+\{\s*registerDivineSoulTopology\s*\}\s+from\s+['"]\.\/frontend\/modules\/divine-soul-topology/,
  'app.js should not statically import the Divine module',
);
assert.match(
  appSource,
  /import\('\.\/frontend\/modules\/divine-soul-topology\/index\.js'\)/,
  'app.js should dynamically import the Divine module entry',
);
assert.doesNotMatch(
  builtIndex,
  /divine-soul-topology-[^"']+\.js/,
  'dist/index.html should not preload the Divine chunk on initial HTML load',
);

const browser = await chromium.launch({ headless: true });
const page = await browser.newPage();

await page.goto(BASE_URL, { waitUntil: 'networkidle', timeout: 120000 });
const before = await page.evaluate(() => ({
  hasRoot: Boolean(document.querySelector('.dst-root')),
}));

await page.evaluate(async () => {
  await window.openDivineSoulTopology?.({
    question: '我该直接工作还是继续深造',
    engineb_session: {
      value_profile: { summary: '你更看重长期成长与选择权', top_values: ['成长', '选择权', '稳定感'] },
      emotional_insight: { gentle_reminder: '你更怕太早把自己定型。' },
      simulator_output: {
        final_insight: '你怕的不是辛苦，而是失去未来的弹性。',
      },
    },
  });
});

await page.waitForSelector('.dst-root', { timeout: 15000 });
const after = await page.evaluate(() => ({
  hasRoot: Boolean(document.querySelector('.dst-root')),
}));

await browser.close();

console.log(JSON.stringify({ before, after }, null, 2));

if (before.hasRoot || !after.hasRoot) process.exit(1);
