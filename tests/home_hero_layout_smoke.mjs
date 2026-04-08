import { chromium, webkit } from 'playwright';

const BASE_URL = 'http://127.0.0.1:4173';

async function main() {
  const browserType = process.env.PW_BROWSER === 'webkit' ? webkit : chromium;
  const browser = await browserType.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1280, height: 820 } });

  await page.goto(`${BASE_URL}/`, {
    waitUntil: 'domcontentloaded',
    timeout: 120000,
  });

  if (await page.locator('#title-enter').isVisible()) {
    await page.click('#title-enter');
  }

  await page.waitForFunction(() => {
    const home = document.getElementById('home-entry');
    const title = document.querySelector('.home-title');
    return Boolean(home && !home.classList.contains('hidden') && title);
  }, undefined, { timeout: 30000 });

  const metrics = await page.evaluate(() => {
    const title = document.querySelector('.home-title');
    const content = document.querySelector('.home-content');
    const note = document.querySelector('.home-hero-note');
    const titleRect = title?.getBoundingClientRect();
    const contentRect = content?.getBoundingClientRect();
    const noteRect = note?.getBoundingClientRect();
    const titleStyle = title ? window.getComputedStyle(title) : null;

    return {
      text: title?.textContent?.trim() || '',
      titleTop: Math.round(titleRect?.top || 0),
      titleBottom: Math.round(titleRect?.bottom || 0),
      titleLeft: Math.round(titleRect?.left || 0),
      titleRight: Math.round(titleRect?.right || 0),
      titleHeight: Math.round(titleRect?.height || 0),
      contentTop: Math.round(contentRect?.top || 0),
      contentBottom: Math.round(contentRect?.bottom || 0),
      noteTop: Math.round(noteRect?.top || 0),
      viewportWidth: window.innerWidth,
      viewportHeight: window.innerHeight,
      hasVerticalOverflow: document.getElementById('home-entry')?.scrollHeight > window.innerHeight + 2,
      lineHeight: titleStyle?.lineHeight || '',
      fontSize: titleStyle?.fontSize || '',
      visibleEnough: Boolean(
        titleRect
        && titleRect.top >= 12
        && titleRect.left >= 12
        && titleRect.right <= window.innerWidth - 12
        && titleRect.bottom <= Math.max(window.innerHeight - 12, titleRect.bottom)
      ),
      insideCard: Boolean(
        titleRect
        && contentRect
        && titleRect.top >= contentRect.top + 20
        && titleRect.left >= contentRect.left + 20
      ),
    };
  });

  await page.screenshot({ path: '/tmp/clp-home-hero-layout.png', fullPage: true });
  await browser.close();

  console.log(JSON.stringify({
    browser: process.env.PW_BROWSER === 'webkit' ? 'webkit' : 'chromium',
    screenshot: '/tmp/clp-home-hero-layout.png',
    metrics,
  }, null, 2));

  if (!metrics.text || !metrics.visibleEnough || !metrics.insideCard) {
    process.exit(1);
  }
}

main().catch((error) => {
  console.error(error?.stack || String(error));
  process.exit(1);
});
