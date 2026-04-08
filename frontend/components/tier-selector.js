import { state } from '../core/state.js';

const FALLBACK_TIERS = {
  quick: { key: 'quick', label: '⚡ 快速', tagline: '5秒 · 一个直觉' },
  deep: { key: 'deep', label: '💡 沉思', tagline: '30秒 · 完整分析' },
  pro: { key: 'pro', label: '🔥 Pro', tagline: '5分钟 · 出版级推演' },
  ultra: { key: 'ultra', label: '🌌 Ultra', tagline: '高烧 · Monte Carlo 多代理碰撞' },
};

function getTierMap() {
  return Object.keys(state.decisionTiers || {}).length ? state.decisionTiers : FALLBACK_TIERS;
}

function formatTokenValue(value) {
  const number = Number(value || 0);
  if (!Number.isFinite(number) || number <= 0) return '--';
  if (number >= 100000000) return `约 ${(number / 100000000).toFixed(number >= 1000000000 ? 0 : 1)} 亿`;
  if (number >= 100000) return `约 ${(number / 10000).toFixed(number >= 300000 ? 0 : 1)} 万`;
  if (number >= 10000) return `约 ${(number / 10000).toFixed(1)} 万`;
  if (number >= 1000) return `约 ${(number / 1000).toFixed(number >= 10000 ? 0 : 1)}k`;
  return String(number);
}

function renderTierBudgetPanel() {
  const root = document.getElementById('home-tier-budget');
  if (!root) return;

  const tiers = getTierMap();
  const tier = tiers[state.selectedTier] || tiers.deep || FALLBACK_TIERS.deep;
  const breakdown = Array.isArray(tier?.budget_breakdown) ? tier.budget_breakdown : [];
  const focus = String(tier?.budget_focus || '').trim();

  if (!tier) {
    root.innerHTML = '';
    return;
  }

  root.innerHTML = `
    <div class="home-tier-budget-head">
      <div class="home-tier-budget-pill">${tier.label}</div>
      <div class="home-tier-budget-total">整轮预算上限 ${formatTokenValue(tier.estimated_tokens)} tokens</div>
    </div>
    <div class="home-tier-budget-note">
      ${focus || '预算显示的是系统的上限配置，不是每次都稳定打满的实耗。'}
    </div>
    <div class="home-tier-budget-grid">
      ${breakdown.map((item) => `
        <div class="home-tier-budget-item">
          <div class="home-tier-budget-label">${item.label}</div>
          <div class="home-tier-budget-value">${formatTokenValue(item.tokens)} tokens</div>
          <div class="home-tier-budget-desc">${item.note || ''}</div>
        </div>
      `).join('')}
    </div>
  `;
}

export function renderTierSelector() {
  const root = document.getElementById('home-tier-selector');
  if (!root) return;

  const tiers = getTierMap();
  root.innerHTML = Object.values(tiers).map((tier) => `
    <button
      type="button"
      class="tier-option ${state.selectedTier === tier.key ? 'active' : ''}"
      data-tier="${tier.key}"
    >
      <span class="tier-option-label">${tier.label}</span>
      <span class="tier-option-meta">${tier.tagline || ''}</span>
    </button>
  `).join('');
  renderTierBudgetPanel();
}

export function bindTierSelector() {
  const root = document.getElementById('home-tier-selector');
  if (!root || root.dataset.boundTierSelector) return;
  root.dataset.boundTierSelector = '1';

  root.addEventListener('click', (event) => {
    const button = event.target.closest('.tier-option');
    if (!button) return;
    state.selectedTier = button.dataset.tier || 'deep';
    renderTierSelector();
  });
}

export function setSelectedTier(tier) {
  state.selectedTier = tier || 'deep';
  renderTierSelector();
}
