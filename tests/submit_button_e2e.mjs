import { chromium, webkit } from 'playwright';
import http from 'node:http';
import https from 'node:https';

async function requestJson(url, attempts = 3) {
  const requestOnce = () => new Promise((resolve, reject) => {
    const client = url.startsWith('https:') ? https : http;
    const req = client.get(url, (response) => {
      let raw = '';
      response.setEncoding('utf8');
      response.on('data', (chunk) => {
        raw += chunk;
      });
      response.on('end', () => {
        if ((response.statusCode || 500) >= 400) {
          reject(new Error(`HTTP ${response.statusCode || 500}`));
          return;
        }
        try {
          resolve(JSON.parse(raw || '{}'));
        } catch (error) {
          reject(error);
        }
      });
    });
    req.on('error', reject);
  });

  let lastError = null;
  for (let index = 0; index < attempts; index += 1) {
    try {
      return await requestOnce();
    } catch (error) {
      lastError = error;
      if (index < attempts - 1) {
        await new Promise((resolve) => setTimeout(resolve, 250 * (index + 1)));
      }
    }
  }
  throw lastError || new Error(`Request failed: ${url}`);
}

async function waitForQuestion(page, timeout = 180000) {
  await page.waitForFunction(() => {
    const active = document.querySelector('#detection-step0.active');
    const options = document.querySelectorAll('#b1-options .b1-option-btn').length;
    const openInput = document.querySelector('#b1-open-input:not(.hidden)');
    return Boolean(active && (options > 0 || openInput));
  }, undefined, { timeout });
}

async function pickExistingDecision() {
  const payload = await requestJson('http://127.0.0.1:4173/api/decision/history');
  const rows = Array.isArray(payload.decisions) ? payload.decisions : [];
  const act2Rows = rows.filter((item) => item.phase === 'act2' && item.linked_engineb_session_id);
  for (const item of act2Rows) {
    let detailPayload = {};
    try {
      detailPayload = await requestJson(`http://127.0.0.1:4173/api/decision/status?id=${encodeURIComponent(item.decision_id)}`);
    } catch (_error) {
      continue;
    }
    const decision = detailPayload.decision || {};
    const session = decision.engineb_session || {};
    const questions = Array.isArray(session.diagnosis_questions) ? session.diagnosis_questions : [];
    if (questions.length > 0) {
      return item;
    }
  }
  return null;
}

async function main() {
  const existingDecision = await pickExistingDecision();
  if (!existingDecision?.decision_id) {
    throw new Error('没有找到可恢复到 Engine B 提问阶段的决策记录');
  }

  const browserType = process.env.PW_BROWSER === 'webkit' ? webkit : chromium;
  const browser = await browserType.launch({ headless: true });
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
  page.on('response', (res) => {
    const url = res.url();
    if (
      url.includes('/api/decision/answer')
      || url.includes('/api/decision/status')
      || url.includes('/api/decision/history')
    ) {
      browserLogs.push(`response: ${res.status()} ${url}`);
    }
  });

  await page.addInitScript((decisionId) => {
    localStorage.setItem('clp_decision_session_id', decisionId);
    localStorage.removeItem('clp_engineb_session_id');
  }, existingDecision.decision_id);
  await page.goto('http://127.0.0.1:4173/', {
    waitUntil: 'domcontentloaded',
    timeout: 120000,
  });

  if (await page.locator('#title-enter').isVisible()) {
    await page.evaluate(() => {
      document.getElementById('title-enter')?.click();
    });
  }

  await page.waitForFunction(() => {
    window.refreshHomeSurface?.();
    const card = document.getElementById('home-session-card');
    return Boolean(card && !card.classList.contains('hidden'));
  }, undefined, { timeout: 30000 });
  await page.click('#home-session-continue');

  await waitForQuestion(page);
  await page.evaluate(() => {
    const button = document.getElementById('b1-submit');
    if (button && !button.dataset.e2eClickDebug) {
      button.addEventListener('click', () => console.log('E2E_BUTTON_CLICK'));
      button.dataset.e2eClickDebug = '1';
    }
    if (typeof window.submitB1Answer === 'function' && !window.__e2eWrappedSubmit) {
      const original = window.submitB1Answer;
      window.submitB1Answer = (...args) => {
        console.log('E2E_INLINE_HANDLER', localStorage.getItem('clp_decision_session_id') || '');
        return original(...args);
      };
      window.__e2eWrappedSubmit = true;
    }
  });

  const firstOption = page.locator('#b1-options .b1-option-btn').first();
  if (await firstOption.count()) {
    await firstOption.click();
  } else {
    await page.fill('#b1-open-input', '测试输入');
  }

  const before = await page.evaluate(() => ({
    currentDecisionId: window.localStorage.getItem('clp_decision_session_id'),
    b1Text: document.getElementById('b1-submit')?.textContent || '',
    b1Disabled: document.getElementById('b1-submit')?.disabled || false,
    questionText: document.getElementById('b1-question-text')?.textContent || '',
    progressText: document.getElementById('b1-progress-text')?.textContent || '',
    selected: Array.from(document.querySelectorAll('#b1-options .b1-option-btn.selected')).map((el) => el.textContent?.trim() || ''),
  }));

  await page.click('#b1-submit');
  await page.waitForTimeout(3500);

  const after = await page.evaluate(() => ({
    b1Text: document.getElementById('b1-submit')?.textContent || '',
    b1Disabled: document.getElementById('b1-submit')?.disabled || false,
    questionText: document.getElementById('b1-question-text')?.textContent || '',
    progressText: document.getElementById('b1-progress-text')?.textContent || '',
    toasts: Array.from(document.querySelectorAll('#toast-container .toast')).map((el) => el.textContent?.trim() || ''),
    activeStep0: document.getElementById('detection-step0')?.classList.contains('active') || false,
    activeStep4: document.getElementById('detection-step4')?.classList.contains('active') || false,
    activeStep5: document.getElementById('detection-step5')?.classList.contains('active') || false,
  }));

  await page.screenshot({ path: '/tmp/clp-submit-e2e.png', fullPage: true });
  await browser.close();

  console.log(JSON.stringify({
    browser: process.env.PW_BROWSER === 'webkit' ? 'webkit' : 'chromium',
    decisionId: existingDecision.decision_id,
    before,
    after,
    browserLogs,
    screenshot: '/tmp/clp-submit-e2e.png',
  }, null, 2));
}

main().catch(async (error) => {
  console.error(error?.stack || String(error));
  process.exit(1);
});
