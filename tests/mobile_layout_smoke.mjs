import { chromium, webkit } from 'playwright';

const BASE_URL = 'http://127.0.0.1:4173';

async function main() {
  const decisionId = process.env.DECISION_ID || '';
  if (!decisionId) {
    throw new Error('Missing DECISION_ID');
  }
  const browserType = process.env.PW_BROWSER === 'webkit' ? webkit : chromium;
  const browser = await browserType.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 390, height: 844 } });

  await page.addInitScript((id) => {
    localStorage.setItem('clp_decision_session_id', id);
    localStorage.removeItem('clp_engineb_session_id');
  }, decisionId);

  await page.goto(`${BASE_URL}/`, { waitUntil: 'domcontentloaded', timeout: 120000 });

  if (await page.locator('#title-enter').isVisible()) {
    await page.click('#title-enter');
  }

  await page.waitForFunction(() => {
    const card = document.getElementById('home-session-card');
    return Boolean(card && !card.classList.contains('hidden'));
  }, undefined, { timeout: 30000 });

  const homeMetrics = await page.evaluate(() => {
    const question = document.getElementById('home-question')?.getBoundingClientRect();
    const start = document.getElementById('home-start')?.getBoundingClientRect();
    return {
      scrollFits: document.documentElement.scrollWidth <= window.innerWidth + 2,
      questionWidth: Math.round(question?.width || 0),
      startWidth: Math.round(start?.width || 0),
      startBottom: Math.round(start?.bottom || 0),
    };
  });

  await page.click('#home-session-continue');

  await page.waitForFunction(() => {
    const title = document.getElementById('detection-title')?.textContent || '';
    return title.trim().length > 0;
  }, undefined, { timeout: 120000 });

  const detectionMetrics = await page.evaluate(() => {
    const closeBtn = document.getElementById('detection-close')?.getBoundingClientRect();
    const historyBtn = document.getElementById('engineb-history-toggle')?.getBoundingClientRect();
    const detectionTitle = document.getElementById('detection-title')?.textContent?.trim() || '';
    return {
      scrollFits: document.documentElement.scrollWidth <= window.innerWidth + 2,
      closeVisible: Boolean(closeBtn && closeBtn.right <= window.innerWidth + 1),
      historyVisible: Boolean(historyBtn && historyBtn.right <= window.innerWidth + 1),
      titleVisible: detectionTitle.length > 0,
      activeStep: Array.from(document.querySelectorAll('.detection-step'))
        .findIndex((el) => el.classList.contains('active')),
    };
  });

  await page.evaluate(() => {
    window.closeDetection?.();
  });
  await page.waitForTimeout(400);
  await page.evaluate(() => {
    document.getElementById('home-browse')?.click();
  });
  await page.waitForTimeout(2500);

  const cosmosMetrics = await page.evaluate(() => {
    const hud = document.getElementById('cosmos-hud')?.getBoundingClientRect();
    const debug = window.__CLP_DEBUG__;
    const appState = debug?.getState?.() || {};
    return {
      scrollFits: document.documentElement.scrollWidth <= window.innerWidth + 2,
      hudVisible: Boolean(hud && !document.getElementById('cosmos-hud')?.classList.contains('hidden')),
      hudFits: Boolean(hud && hud.left >= -1 && hud.right <= window.innerWidth + 1),
      hudTop: Math.round(hud?.top || 0),
      chips: document.querySelectorAll('#cosmos-hud-chips .cosmos-hud-chip').length,
      navVisible: document.getElementById('nav-hint')?.classList.contains('visible') || false,
      overlayNodeCount: appState.overlayNodeCount || 0,
    };
  });

  await page.screenshot({ path: '/tmp/clp-mobile-layout-smoke.png', fullPage: true });
  await browser.close();

  console.log(JSON.stringify({
    browser: process.env.PW_BROWSER === 'webkit' ? 'webkit' : 'chromium',
    decisionId,
    homeMetrics,
    detectionMetrics,
    cosmosMetrics,
    screenshot: '/tmp/clp-mobile-layout-smoke.png',
  }, null, 2));

  if (
    !homeMetrics.scrollFits
    || !detectionMetrics.scrollFits
    || !detectionMetrics.closeVisible
    || !detectionMetrics.historyVisible
    || !detectionMetrics.titleVisible
    || !cosmosMetrics.scrollFits
    || !cosmosMetrics.hudVisible
    || !cosmosMetrics.hudFits
    || !cosmosMetrics.navVisible
    || cosmosMetrics.overlayNodeCount < 1
  ) {
    process.exit(1);
  }
}

main().catch((error) => {
  console.error(error?.stack || String(error));
  process.exit(1);
});
