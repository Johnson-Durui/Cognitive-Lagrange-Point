import { chromium, webkit } from 'playwright';

const BASE_URL = 'http://127.0.0.1:4173';

async function openDecision(browser, decisionId) {
  const page = await browser.newPage({ viewport: { width: 1440, height: 1100 } });
  await page.addInitScript((storedDecisionId) => {
    localStorage.setItem('clp_decision_session_id', storedDecisionId);
    localStorage.removeItem('clp_engineb_session_id');
  }, decisionId);

  await page.goto(`${BASE_URL}/`, {
    waitUntil: 'domcontentloaded',
    timeout: 120000,
  });

  if (await page.locator('#title-enter').isVisible().catch(() => false)) {
    await page.click('#title-enter');
  }

  await page.waitForFunction(() => (
    Boolean(document.getElementById('home-session-continue'))
    || Boolean(document.querySelector('#detection-step0.active, #detection-step4.active, #detection-step5.active'))
  ), undefined, { timeout: 30000 });

  if (await page.locator('#home-session-continue').isVisible().catch(() => false)) {
    await page.click('#home-session-continue');
  }

  await page.waitForFunction(() => typeof window.returnToRecommendation === 'function', undefined, {
    timeout: 30000,
  });
  await page.waitForFunction((targetDecisionId) => {
    const debug = window.__CLP_DEBUG__;
    if (!debug || typeof debug.getState !== 'function') return false;
    return debug.getState().currentDecisionId === targetDecisionId;
  }, decisionId, {
    timeout: 30000,
  });
  await page.evaluate(() => {
    window.returnToRecommendation?.();
  });
  await page.waitForFunction(() => document.getElementById('detection-step4')?.classList.contains('active'), undefined, {
    timeout: 30000,
  });

  return page;
}

async function readButtonState(page) {
  return page.evaluate(() => {
    const button = document.getElementById('engineb-start-sim-btn');
    if (!button) {
      return { exists: false };
    }
    const style = window.getComputedStyle(button);
    return {
      exists: true,
      display: style.display,
      visibility: style.visibility,
      disabled: Boolean(button.disabled),
      text: button.textContent?.trim() || '',
      title: button.title || '',
    };
  });
}

async function main() {
  const deepDecisionId = String(process.env.DEEP_DECISION_ID || '').trim();
  const ultraDecisionId = String(process.env.ULTRA_DECISION_ID || '').trim();
  if (!deepDecisionId) {
    throw new Error('缺少 DEEP_DECISION_ID');
  }

  const browserType = process.env.PW_BROWSER === 'webkit' ? webkit : chromium;
  const browser = await browserType.launch({ headless: true });

  const deepPage = await openDecision(browser, deepDecisionId);
  const deepBefore = await readButtonState(deepPage);
  if (!deepBefore.exists || deepBefore.display === 'none' || deepBefore.disabled) {
    throw new Error(`deep 按钮状态异常: ${JSON.stringify(deepBefore)}`);
  }
  await deepPage.click('#engineb-start-sim-btn');
  await deepPage.waitForFunction(() => (
    document.getElementById('detection-step5')?.classList.contains('active')
  ), undefined, { timeout: 30000 });
  const deepAfter = await deepPage.evaluate(() => ({
    step5Active: document.getElementById('detection-step5')?.classList.contains('active') || false,
    simQuestionVisible: Boolean(document.getElementById('sim-question-text')?.textContent?.trim()),
    simLoadingVisible: getComputedStyle(document.getElementById('sim-loading') || document.body).display !== 'none',
  }));

  let ultraBefore = null;
  let ultraAfter = null;
  if (ultraDecisionId) {
    const ultraPage = await openDecision(browser, ultraDecisionId);
    ultraBefore = await readButtonState(ultraPage);
    if (!ultraBefore.exists || ultraBefore.display === 'none' || ultraBefore.disabled) {
      throw new Error(`ultra 按钮状态异常: ${JSON.stringify(ultraBefore)}`);
    }
    await ultraPage.click('#engineb-start-sim-btn');
    await ultraPage.waitForFunction(() => (
      document.getElementById('detection-step5')?.classList.contains('active')
    ), undefined, { timeout: 30000 });
    ultraAfter = await ultraPage.evaluate(() => ({
      step5Active: document.getElementById('detection-step5')?.classList.contains('active') || false,
      reportTitle: document.getElementById('sim-comparison-summary')?.textContent?.trim() || '',
    }));
  }

  await browser.close();

  console.log(JSON.stringify({
    ok: true,
    browser: process.env.PW_BROWSER === 'webkit' ? 'webkit' : 'chromium',
    deepDecision: deepDecisionId,
    ultraDecision: ultraDecisionId || '',
    deepBefore,
    deepAfter,
    ultraBefore,
    ultraAfter,
  }, null, 2));
}

main().catch((error) => {
  console.error(error?.stack || String(error));
  process.exit(1);
});
