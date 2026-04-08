import { chromium, webkit } from 'playwright';

const BASE_URL = 'http://127.0.0.1:4173';

async function main() {
  const browserType = process.env.PW_BROWSER === 'webkit' ? webkit : chromium;
  const browser = await browserType.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 390, height: 844 } });

  await page.goto(`${BASE_URL}/`, {
    waitUntil: 'domcontentloaded',
    timeout: 120000,
  });

  if (await page.locator('#title-enter').isVisible()) {
    await page.click('#title-enter');
  }

  await page.waitForFunction(() => {
    const home = document.getElementById('home-entry');
    return Boolean(home && !home.classList.contains('hidden'));
  }, undefined, { timeout: 30000 });

  const metrics = await page.evaluate(() => {
    const title = document.querySelector('.home-title')?.getBoundingClientRect();
    const tiers = Array.from(document.querySelectorAll('.tier-option')).map((node) => node.getBoundingClientRect());
    const links = Array.from(document.querySelectorAll('.home-link')).map((node) => node.getBoundingClientRect());
    return {
      titleVisible: Boolean(title && title.top >= 12 && title.left >= 12 && title.right <= window.innerWidth - 12),
      tierCount: tiers.length,
      tierSingleColumn: tiers.length > 1
        ? tiers.every((rect, index, arr) => index === 0 || Math.abs(rect.left - arr[0].left) <= 2)
        : true,
      linksSingleColumn: links.length > 1
        ? links.every((rect, index, arr) => index === 0 || Math.abs(rect.left - arr[0].left) <= 2)
        : true,
      scrollFits: document.documentElement.scrollWidth <= window.innerWidth + 2,
    };
  });

  await page.screenshot({ path: '/tmp/clp-home-mobile-surface.png', fullPage: true });
  await browser.close();

  console.log(JSON.stringify({
    browser: process.env.PW_BROWSER === 'webkit' ? 'webkit' : 'chromium',
    screenshot: '/tmp/clp-home-mobile-surface.png',
    metrics,
  }, null, 2));

  if (!metrics.titleVisible || !metrics.tierSingleColumn || !metrics.linksSingleColumn || !metrics.scrollFits) {
    process.exit(1);
  }
}

main().catch((error) => {
  console.error(error?.stack || String(error));
  process.exit(1);
});
