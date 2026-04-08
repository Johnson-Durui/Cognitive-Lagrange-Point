import { chromium, webkit } from 'playwright';

const BASE_URL = 'http://127.0.0.1:4173';

async function main() {
  const browserType = process.env.PW_BROWSER === 'webkit' ? webkit : chromium;
  const browser = await browserType.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1365, height: 960 } });
  const captured = [];

  await page.route(`${BASE_URL}/api/decision/start`, async (route) => {
    const payload = JSON.parse(route.request().postData() || '{}');
    captured.push(payload);
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        ok: true,
        active: false,
        decision: {
          decision_id: `mock-${payload.tier}`,
          question: payload.question,
          tier: payload.tier,
          status: 'completed',
          phase: 'completed',
          status_text: `${payload.tier} mocked`,
          result: {
            summary: `${payload.tier} mocked`,
          },
        },
      }),
    });
  });

  await page.goto(`${BASE_URL}/`, { waitUntil: 'domcontentloaded', timeout: 120000 });

  if (await page.locator('#title-enter').isVisible()) {
    await page.click('#title-enter');
  }

  await page.waitForSelector('#home-tier-selector .tier-option', { timeout: 20000 });

  const tierKeys = ['quick', 'deep', 'pro', 'ultra'];
  const labels = await page.locator('#home-tier-selector .tier-option').evaluateAll((nodes) => (
    nodes.map((node) => ({
      tier: node.getAttribute('data-tier') || '',
      text: (node.textContent || '').trim(),
    }))
  ));

  for (const tier of tierKeys) {
    await page.click(`#home-tier-selector .tier-option[data-tier="${tier}"]`);
    await page.fill('#home-question', `测试 ${tier} 档位是否正常`);
    await page.click('#home-start');
    await page.waitForTimeout(300);
    await page.evaluate(() => {
      window.closeDetection?.();
      const input = document.getElementById('home-question');
      if (input) input.value = '';
      localStorage.removeItem('clp_decision_session_id');
    });
    await page.waitForTimeout(150);
  }

  await browser.close();

  console.log(JSON.stringify({
    browser: process.env.PW_BROWSER === 'webkit' ? 'webkit' : 'chromium',
    labels,
    captured,
  }, null, 2));

  const capturedTiers = captured.map((item) => item.tier);
  const labelTiers = labels.map((item) => item.tier);
  if (
    labelTiers.length !== 4
    || tierKeys.some((tier) => !labelTiers.includes(tier))
    || capturedTiers.join(',') !== tierKeys.join(',')
  ) {
    process.exit(1);
  }
}

main().catch((error) => {
  console.error(error?.stack || String(error));
  process.exit(1);
});
