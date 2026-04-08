import { chromium } from 'playwright';

const BASE_URL = 'http://127.0.0.1:4173';

async function request(path, options = {}) {
  const response = await fetch(`${BASE_URL}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok || payload.ok === false) {
    throw new Error(payload.error || payload.detail || `HTTP ${response.status}`);
  }
  return payload;
}

async function pickDecisionForCosmos() {
  const payload = await request('/api/decision/history');
  const decisions = Array.isArray(payload.decisions) ? payload.decisions : [];
  const ranked = decisions
    .filter((item) => item?.decision_id)
    .sort((a, b) => String(b.updated_at || '').localeCompare(String(a.updated_at || '')));

  let fallback = null;
  for (const item of ranked.slice(0, 12)) {
    const statusPayload = await request(`/api/decision/status?id=${encodeURIComponent(item.decision_id)}`);
    const decision = statusPayload.decision || null;
    if (!decision?.decision_id) continue;
    if (!fallback) fallback = decision;
    if (decision.engineb_session?.simulator_output) {
      return { decision, hasSimulator: true };
    }
  }

  if (fallback) {
    return { decision: fallback, hasSimulator: false };
  }

  throw new Error('没有找到可用于星图验证的决策记录');
}

async function main() {
  const { decision, hasSimulator } = await pickDecisionForCosmos();
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1440, height: 1100 } });
  const browserLogs = [];

  page.on('console', (msg) => {
    browserLogs.push(`console:${msg.type()}: ${msg.text()}`);
  });
  page.on('pageerror', (err) => {
    browserLogs.push(`pageerror: ${err.stack || err.message}`);
  });
  page.on('requestfailed', (req) => {
    browserLogs.push(`requestfailed: ${req.method()} ${req.url()} :: ${req.failure()?.errorText || ''}`);
  });

  await page.addInitScript((decisionId) => {
    localStorage.setItem('clp_decision_session_id', decisionId);
    localStorage.removeItem('clp_engineb_session_id');
  }, decision.decision_id);

  await page.goto(`${BASE_URL}/`, {
    waitUntil: 'domcontentloaded',
    timeout: 120000,
  });

  if (await page.locator('#title-enter').isVisible()) {
    await page.click('#title-enter');
  }

  await page.waitForFunction(() => {
    window.refreshHomeSurface?.();
    const card = document.getElementById('home-session-card');
    return Boolean(card && !card.classList.contains('hidden'));
  }, undefined, { timeout: 30000 });

  await page.click('#home-session-continue');

  await page.waitForFunction(() => {
    const title = document.getElementById('detection-title')?.textContent || '';
    const question = document.getElementById('detection-question-preview')?.textContent || '';
    return title.trim().length > 0 || question.trim().length > 0;
  }, undefined, { timeout: 120000 });

  await page.evaluate(() => {
    window.showView?.('cosmos');
    window.enterExploring?.();
  });

  await page.waitForFunction(() => {
    const root = document.getElementById('system-labels');
    const center = root?.querySelector('.center-label');
    const left = root?.querySelector('.left-well-label');
    const right = root?.querySelector('.right-well-label');
    return Boolean(
      root
      && root.classList.contains('visible')
      && center
      && left
      && right
      && getComputedStyle(root).opacity !== '0'
    );
  }, undefined, { timeout: 20000 });

  await page.waitForTimeout(1200);

  const metrics = await page.evaluate(() => {
    const root = document.getElementById('system-labels');
    const pickText = (selector) => root?.querySelector(selector)?.textContent?.trim() || '';
    return {
      appViewVisible: getComputedStyle(document.getElementById('cosmos') || document.body).display,
      labelCount: root?.querySelectorAll('.system-label').length || 0,
      decisionLabelCount: root?.querySelectorAll('.system-label.decision-label').length || 0,
      centerLabel: pickText('.center-label .system-label-name'),
      leftLabel: pickText('.left-well-label .system-label-name'),
      rightLabel: pickText('.right-well-label .system-label-name'),
      centerSubtitle: pickText('.center-label .system-label-en'),
      leftSubtitle: pickText('.left-well-label .system-label-en'),
      rightSubtitle: pickText('.right-well-label .system-label-en'),
      navVisible: document.getElementById('nav-hint')?.classList.contains('visible') || false,
      detailOpen: document.getElementById('detail-panel')?.classList.contains('open') || false,
    };
  });

  await page.screenshot({ path: '/tmp/clp-star-map-v2-smoke.png', fullPage: true });
  await browser.close();

  console.log(JSON.stringify({
    decisionId: decision.decision_id,
    hasSimulator,
    metrics,
    browserLogs,
    screenshot: '/tmp/clp-star-map-v2-smoke.png',
  }, null, 2));

  if (metrics.decisionLabelCount < 3 || !metrics.centerLabel || !metrics.leftLabel || !metrics.rightLabel) {
    process.exit(1);
  }
}

main().catch((error) => {
  console.error(error?.stack || String(error));
  process.exit(1);
});
