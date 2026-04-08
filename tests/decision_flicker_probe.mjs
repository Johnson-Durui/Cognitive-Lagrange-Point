import { chromium, webkit } from 'playwright';

const BASE_URL = 'http://127.0.0.1:4173';
const DECISION_ID = process.env.DECISION_ID || '';
const TEST_QUESTION = process.env.TEST_QUESTION || '我该不该开Claude';

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
  if (DECISION_ID) {
    return DECISION_ID;
  }

  const payload = await request('/api/decision/history');
  const decisions = Array.isArray(payload.decisions) ? payload.decisions : [];
  const ranked = decisions.filter((item) => item && item.status === 'running');
  ranked.sort((a, b) => String(b.updated_at || '').localeCompare(String(a.updated_at || '')));
  return ranked[0]?.decision_id || '';
}

async function main() {
  const decisionId = await resolveDecisionId();
  const browserType = process.env.PW_BROWSER === 'webkit' ? webkit : chromium;
  const browser = await browserType.launch({ headless: true });
  const page = await browser.newPage();

  if (decisionId) {
    await page.addInitScript((activeDecisionId) => {
      localStorage.setItem('clp_decision_session_id', activeDecisionId);
    }, decisionId);
  }

  await page.goto(BASE_URL, { waitUntil: 'networkidle' });
  await page.waitForTimeout(1500);

  const restored = await page.evaluate(() => {
    return {
      currentDecisionId: window.localStorage.getItem('clp_decision_session_id') || '',
      activeStep: Array.from(document.querySelectorAll('.detection-step'))
        .findIndex((el) => el.classList.contains('active')),
      questionText: document.getElementById('b1-question-text')?.textContent || '',
      simQuestion: document.getElementById('sim-question-text')?.textContent || '',
      recommendation: document.getElementById('c1-recommendation')?.textContent || '',
      hasStartDecision: typeof window.startDecision === 'function',
    };
  });

  const hasUsableRestoredView = restored.activeStep >= 0 && (
    (restored.questionText && restored.questionText !== '正在生成追问...')
    || restored.simQuestion.trim().length > 0
    || restored.recommendation.trim().length > 0
  );

  if (!hasUsableRestoredView && restored.hasStartDecision) {
    await page.evaluate((question) => {
      window.startDecision(question, 'deep');
    }, TEST_QUESTION);
  }

  await page.waitForFunction(() => {
    const activeStep = Array.from(document.querySelectorAll('.detection-step'))
      .findIndex((el) => el.classList.contains('active'));
    const questionText = document.getElementById('b1-question-text')?.textContent || '';
    const hasRecommendation = (document.getElementById('c1-recommendation')?.textContent || '').trim().length > 0;
    const hasSimQuestion = (document.getElementById('sim-question-text')?.textContent || '').trim().length > 0;
    return activeStep >= 0 && (
      hasRecommendation
      || hasSimQuestion
      || (questionText && questionText !== '正在生成追问...')
    );
  }, null, { timeout: 120000 });

  await page.waitForTimeout(1200);

  const metrics = await page.evaluate(async () => {
    const root = document.getElementById('detection-screen');
    if (!root) {
      return { ok: false, reason: 'missing detection screen' };
    }

    const initialHtml = root.innerHTML;
    let mutations = 0;
    let characterChanges = 0;
    let childListChanges = 0;
    let attributeChanges = 0;
    const attributeSamples = [];

    const observer = new MutationObserver((records) => {
      mutations += records.length;
      for (const record of records) {
        if (record.type === 'characterData') characterChanges += 1;
        if (record.type === 'childList') childListChanges += 1;
        if (record.type === 'attributes') {
          attributeChanges += 1;
          if (attributeSamples.length < 12) {
            const target = record.target;
            attributeSamples.push({
              tag: target?.tagName || '',
              id: target?.id || '',
              className: target?.className || '',
              attribute: record.attributeName || '',
              oldValue: record.oldValue || '',
            });
          }
        }
      }
    });

    observer.observe(root, {
      subtree: true,
      childList: true,
      characterData: true,
      attributes: true,
      attributeOldValue: true,
    });

    await new Promise((resolve) => setTimeout(resolve, 4000));
    observer.disconnect();

    return {
      ok: true,
      mutations,
      characterChanges,
      childListChanges,
      attributeChanges,
      attributeSamples,
      htmlChanged: root.innerHTML !== initialHtml,
      decisionId: localStorage.getItem('clp_decision_session_id') || '',
      activeStep: Array.from(document.querySelectorAll('.detection-step'))
        .findIndex((el) => el.classList.contains('active')),
      b1Question: document.getElementById('b1-question-text')?.textContent || '',
      simQuestion: document.getElementById('sim-question-text')?.textContent || '',
      recommendation: document.getElementById('c1-recommendation')?.textContent || '',
    };
  });

  console.log(JSON.stringify(metrics, null, 2));
  await browser.close();

  if (!metrics.ok) {
    process.exit(1);
  }
}

main().catch((error) => {
  console.error(error?.stack || String(error));
  process.exit(1);
});
