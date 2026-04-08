import { chromium, webkit } from 'playwright';

const BASE_URL = 'http://127.0.0.1:4173';

function makeDecision(sessionPhase, answers = {}, extra = {}) {
  return {
    decision_id: 'stale-ui-test',
    question: '我该不该开 Claude Pro',
    tier: 'deep',
    status: 'running',
    phase: sessionPhase === 'b1_diagnosis' ? 'act2' : 'act2',
    step: sessionPhase,
    status_text: sessionPhase,
    logs: [],
    engineb_session: {
      session_id: 'stale-session',
      original_question: '我该不该开 Claude Pro',
      phase: sessionPhase,
      diagnosis_questions: [
        { id: 'b1q1', question_text: '你最卡的是哪一类问题？', options: ['不了解差异', '担心花钱'] },
        { id: 'b1q2', question_text: '你最担心什么？', options: ['浪费钱', '用不上'] },
        { id: 'b1q3', question_text: '你希望它帮你解决什么？', options: ['写代码', '做研究'] },
      ],
      diagnosis_answers: answers,
      processing_trace: [
        { phase: sessionPhase, title: '阶段推进', detail: `当前阶段 ${sessionPhase}` },
      ],
      ...extra,
    },
  };
}

async function main() {
  const browserType = process.env.PW_BROWSER === 'webkit' ? webkit : chromium;
  const browser = await browserType.launch({ headless: true });
  const page = await browser.newPage();

  await page.goto(BASE_URL, { waitUntil: 'networkidle' });
  await page.waitForFunction(() => Boolean(window.__CLP_DECISION_DEBUG__?.renderDecisionSession), null, { timeout: 15000 });

  const result = await page.evaluate(async ({ advanced, stale }) => {
    window.showView?.('detection');
    const module = window.__CLP_DECISION_DEBUG__;
    module.renderDecisionSession(advanced, { force: true, clearCache: true });
    const afterAdvanced = {
      activeStep: Array.from(document.querySelectorAll('.detection-step'))
        .findIndex((el) => el.classList.contains('active')),
      loadingTitle: document.getElementById('b1-loading-title')?.textContent || '',
      b1Question: document.getElementById('b1-question-text')?.textContent || '',
    };

    module.renderDecisionSession(stale);
    const afterStale = {
      activeStep: Array.from(document.querySelectorAll('.detection-step'))
        .findIndex((el) => el.classList.contains('active')),
      loadingTitle: document.getElementById('b1-loading-title')?.textContent || '',
      b1Question: document.getElementById('b1-question-text')?.textContent || '',
    };

    return { afterAdvanced, afterStale };
  }, {
    advanced: makeDecision('b3_cognitive_unlock', {
      b1q1: '不了解差异',
      b1q2: '浪费钱',
      b1q3: '写代码',
    }),
    stale: makeDecision('b1_diagnosis', {}),
  });

  console.log(JSON.stringify(result, null, 2));
  await browser.close();

  if (result.afterStale.activeStep !== 0) {
    throw new Error(`Expected B1 processing step to remain active, got step ${result.afterStale.activeStep}`);
  }
  if (/你最卡的是哪一类问题/.test(result.afterStale.b1Question)) {
    throw new Error('Stale B1 snapshot overwrote the advanced processing view');
  }
  if (!/判断框架|切换|阶段/.test(result.afterStale.loadingTitle)) {
    throw new Error(`Expected advanced processing title to remain visible, got "${result.afterStale.loadingTitle}"`);
  }
}

main().catch((error) => {
  console.error(error?.stack || String(error));
  process.exit(1);
});
