import { chromium, webkit } from 'playwright';

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

async function resolveDecisionId() {
  const explicit = String(process.env.DECISION_ID || '').trim();
  if (explicit) return explicit;

  const payload = await request('/api/decision/history');
  const decisions = Array.isArray(payload.decisions) ? payload.decisions : [];
  decisions.sort((a, b) => String(b.updated_at || '').localeCompare(String(a.updated_at || '')));
  return decisions[0]?.decision_id || '';
}

async function main() {
  const decisionId = await resolveDecisionId();
  if (!decisionId) {
    throw new Error('没有找到可用于星图命中测试的决策记录');
  }

  const browserType = process.env.PW_BROWSER === 'webkit' ? webkit : chromium;
  const browser = await browserType.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1440, height: 1024 } });

  await page.addInitScript((id) => {
    localStorage.setItem('clp_decision_session_id', id);
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

  await page.waitForFunction(() => {
    const debug = window.__CLP_DEBUG__;
    if (!debug) return false;
    const interaction = debug.getInteraction?.();
    return Array.isArray(interaction?.nodes) && interaction.nodes.length >= 2;
  }, undefined, { timeout: 20000 });

  const before = await page.evaluate(() => {
    const debug = window.__CLP_DEBUG__;
    const interaction = debug.getInteraction();
    const current = interaction.nodes.find((node) => node.isCurrent) || interaction.nodes[0] || null;
    const alternate = interaction.nodes.find((node) => node.id !== current?.id) || null;
    return {
      appState: debug.getState().appState,
      current,
      alternate,
      currentHit: current ? debug.hitTest(current.x, current.y) : null,
      alternateHit: alternate ? debug.hitTest(alternate.x, alternate.y) : null,
    };
  });

  if (!before.current || !before.currentHit) {
    throw new Error(`当前节点命中失败: ${JSON.stringify(before, null, 2)}`);
  }

  await page.evaluate(({ x, y }) => {
    const canvas = document.getElementById('cosmos');
    canvas?.dispatchEvent(new MouseEvent('mousemove', { clientX: x, clientY: y, bubbles: true }));
    canvas?.dispatchEvent(new MouseEvent('mousedown', { clientX: x, clientY: y, bubbles: true }));
    window.dispatchEvent(new MouseEvent('mouseup', { clientX: x, clientY: y, bubbles: true }));
  }, { x: before.current.x, y: before.current.y });

  await page.waitForFunction(() => {
    const panel = document.getElementById('detail-panel');
    return Boolean(panel && panel.classList.contains('open'));
  }, undefined, { timeout: 10000 });

  const currentDetail = await page.evaluate(() => ({
    title: document.querySelector('#detail-panel .detail-title')?.textContent?.trim() || '',
    subtitle: document.querySelector('#detail-panel .detail-subtitle')?.textContent?.trim() || '',
    body: document.querySelector('#detail-panel .detail-body')?.textContent?.trim() || '',
  }));

  let alternateDetail = null;
  if (before.alternate && before.alternateHit) {
    await page.evaluate(() => window.closeDetail?.());
    await page.evaluate(({ x, y }) => {
      const canvas = document.getElementById('cosmos');
      canvas?.dispatchEvent(new MouseEvent('mousemove', { clientX: x, clientY: y, bubbles: true }));
      canvas?.dispatchEvent(new MouseEvent('mousedown', { clientX: x, clientY: y, bubbles: true }));
      window.dispatchEvent(new MouseEvent('mouseup', { clientX: x, clientY: y, bubbles: true }));
    }, { x: before.alternate.x, y: before.alternate.y });
    await page.waitForFunction(() => {
      const panel = document.getElementById('detail-panel');
      return Boolean(panel && panel.classList.contains('open'));
    }, undefined, { timeout: 10000 });
    alternateDetail = await page.evaluate(() => ({
      title: document.querySelector('#detail-panel .detail-title')?.textContent?.trim() || '',
      subtitle: document.querySelector('#detail-panel .detail-subtitle')?.textContent?.trim() || '',
      body: document.querySelector('#detail-panel .detail-body')?.textContent?.trim() || '',
    }));
  }

  await page.screenshot({ path: '/tmp/clp-star-map-hit-e2e.png', fullPage: true });
  await browser.close();

  const result = {
    browser: process.env.PW_BROWSER === 'webkit' ? 'webkit' : 'chromium',
    decisionId,
    before,
    currentDetail,
    alternateDetail,
    screenshot: '/tmp/clp-star-map-hit-e2e.png',
  };
  console.log(JSON.stringify(result, null, 2));

  if (before.appState !== 'exploring' || !currentDetail.title || !currentDetail.body) {
    process.exit(1);
  }
  if (before.alternate && before.alternateHit && !alternateDetail?.title) {
    process.exit(1);
  }
}

main().catch((error) => {
  console.error(error?.stack || String(error));
  process.exit(1);
});
