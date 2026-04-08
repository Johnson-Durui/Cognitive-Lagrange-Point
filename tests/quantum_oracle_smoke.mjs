import { chromium } from 'playwright';

const baseUrl = process.env.CLP_TEST_URL || 'http://127.0.0.1:4174/?webgl=1';
const browser = await chromium.launch({ headless: true });
const page = await browser.newPage();
const errors = [];

page.on('console', (message) => {
  if (['error', 'warning'].includes(message.type())) {
    errors.push(`${message.type()}: ${message.text()}`);
  }
});
page.on('pageerror', (error) => errors.push(`pageerror: ${error.message}`));

await page.goto(baseUrl, { waitUntil: 'networkidle' });
await page.evaluate(async () => {
  window.decisionData = {
    decision_id: 'quantum-smoke',
    question: '我该直接找工作、边工作边二战，还是全脱产二战？',
    tier: 'ultra',
    engineb_session: {
      recommendation: '推荐双轨路径',
      value_profile: { summary: '稳定现金流与长期成长并重' },
      emotional_mirror: { summary: '焦虑主要来自不可逆承诺' },
      simulator_output: {
        probability_optimistic: 30,
        probability_baseline: 50,
        probability_pessimistic: 20,
        monte_carlo: {
          smooth_prob: { optimistic: 30, baseline: 50, pessimistic: 20 },
          decision_guardrails: ['保留现金缓冲', '每周复盘学习时长', '模考不达标则降风险'],
        },
      },
    },
  };
  await window.openQuantumVibeOracle(window.decisionData);
});

await page.waitForSelector('.qvo-root', { timeout: 10000 });
const result = await page.evaluate(() => ({
  root: Boolean(document.querySelector('.qvo-root')),
  buttons: document.querySelectorAll('[data-qvo-universe]').length,
  hasBio: Boolean(document.querySelector('[data-qvo-bio-enable]')),
  hasAudio: Boolean(document.querySelector('[data-qvo-audio-toggle]')),
  renderer: document.querySelector('[data-qvo-renderer]')?.textContent || '',
}));

await browser.close();
console.log(JSON.stringify({ result, errors }, null, 2));

if (!result.root || result.buttons !== 3 || !result.hasBio || !result.hasAudio) {
  process.exit(1);
}
