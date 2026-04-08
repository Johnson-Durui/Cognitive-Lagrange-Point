import { chromium, webkit } from 'playwright';

const BASE_URL = 'http://127.0.0.1:4173';

async function main() {
  const decisionId = process.env.DECISION_ID || '';
  if (!decisionId) {
    throw new Error('Missing DECISION_ID');
  }
  const browserType = process.env.PW_BROWSER === 'webkit' ? webkit : chromium;
  const browser = await browserType.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1440, height: 1100 } });

  await page.addInitScript((decisionId) => {
    localStorage.setItem('clp_decision_session_id', decisionId);
    localStorage.removeItem('clp_engineb_session_id');
  }, decisionId);

  await page.goto(`${BASE_URL}/`, {
    waitUntil: 'domcontentloaded',
    timeout: 120000,
  });

  if (await page.locator('#title-enter').isVisible()) {
    await page.click('#title-enter');
  }

  await page.waitForFunction(() => {
    const card = document.getElementById('home-session-card');
    return Boolean(card && !card.classList.contains('hidden'));
  }, undefined, { timeout: 30000 });

  await page.evaluate(() => {
    document.getElementById('home-browse')?.click();
  });

  await page.waitForTimeout(3500);

  const metrics = await page.evaluate(() => {
    const hud = document.getElementById('cosmos-hud');
    const hudRect = hud?.getBoundingClientRect();
    const chips = Array.from(document.querySelectorAll('#cosmos-hud-chips .cosmos-hud-chip')).map((el) => el.textContent?.trim() || '');
    const debug = window.__CLP_DEBUG__;
    const appState = debug?.getState?.() || {};
    return {
      hudVisible: Boolean(hud && !hud.classList.contains('hidden')),
      hudWidth: Math.round(hudRect?.width || 0),
      hudTop: Math.round(hudRect?.top || 0),
      chips,
      balanceLabel: document.getElementById('cosmos-hud-balance-label')?.textContent?.trim() || '',
      phaseLabel: document.getElementById('cosmos-hud-phase-label')?.textContent?.trim() || '',
      phaseFill: document.getElementById('cosmos-hud-phase-fill')?.style.width || '',
      proFill: document.getElementById('cosmos-hud-pro-fill')?.style.width || '',
      conFill: document.getElementById('cosmos-hud-con-fill')?.style.width || '',
      labelCount: document.querySelectorAll('#system-labels .system-label').length,
      navVisible: document.getElementById('nav-hint')?.classList.contains('visible') || false,
      overlayNodeCount: appState.overlayNodeCount || 0,
      historyCount: appState.historyCount || 0,
    };
  });

  await page.screenshot({ path: '/tmp/clp-star-map-v3-smoke.png', fullPage: true });
  await browser.close();

  console.log(JSON.stringify({
    browser: process.env.PW_BROWSER === 'webkit' ? 'webkit' : 'chromium',
    decisionId,
    metrics,
    screenshot: '/tmp/clp-star-map-v3-smoke.png',
  }, null, 2));

  if (
    !metrics.hudVisible
    || !metrics.balanceLabel
    || !metrics.phaseLabel
    || metrics.overlayNodeCount < 1
  ) {
    process.exit(1);
  }
}

main().catch((error) => {
  console.error(error?.stack || String(error));
  process.exit(1);
});
