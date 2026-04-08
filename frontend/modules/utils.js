/**
 * 认知拉格朗日点 · 工具函数
 */

export function escapeHtml(text) {
  return String(text || '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

export async function requestJson(url, options = {}) {
  const response = await fetch(url, {
    headers: { 'Content-Type': 'application/json' },
    ...options
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok || payload.ok === false) {
    throw new Error(payload.error || `请求失败: ${response.status}`);
  }
  return payload;
}

export function showToast(message, type = 'info', duration = 4000) {
  let container = document.getElementById('toast-container');
  if (!container) {
    container = document.createElement('div');
    container.id = 'toast-container';
    document.body.appendChild(container);
  }
  const toast = document.createElement('div');
  toast.className = `toast toast-${type}`;
  toast.textContent = message;
  container.appendChild(toast);
  requestAnimationFrame(() => {
    requestAnimationFrame(() => toast.classList.add('visible'));
  });
  setTimeout(() => {
    toast.classList.remove('visible');
    setTimeout(() => toast.remove(), 400);
  }, duration);
}

export function setButtonLoading(button, loading, loadingText) {
  if (!button) return;
  if (loading) {
    button.dataset.origText = button.textContent;
    button.textContent = loadingText || '处理中...';
    button.disabled = true;
    button.classList.add('loading');
  } else {
    button.textContent = button.dataset.origText || button.textContent;
    button.disabled = false;
    button.classList.remove('loading');
  }
}

export function toSafeCount(value, fallback = 0) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}

// Session Persistence
const SESSION_STORAGE_KEY = 'clp_engineb_session_id';
const DECISION_STORAGE_KEY = 'clp_decision_session_id';

export function saveSessionId(sessionId) {
  try {
    localStorage.setItem(SESSION_STORAGE_KEY, sessionId);
  } catch (e) {
    console.warn('localStorage not available:', e);
  }
}

export function getSavedSessionId() {
  try {
    return localStorage.getItem(SESSION_STORAGE_KEY);
  } catch (e) {
    return null;
  }
}

export function clearSavedSessionId() {
  try {
    localStorage.removeItem(SESSION_STORAGE_KEY);
  } catch (e) {
    console.warn('localStorage not available:', e);
  }
}

export function saveDecisionId(decisionId) {
  try {
    localStorage.setItem(DECISION_STORAGE_KEY, decisionId);
  } catch (e) {
    console.warn('localStorage not available:', e);
  }
}

export function getSavedDecisionId() {
  try {
    return localStorage.getItem(DECISION_STORAGE_KEY);
  } catch (e) {
    return null;
  }
}

export function clearSavedDecisionId() {
  try {
    localStorage.removeItem(DECISION_STORAGE_KEY);
  } catch (e) {
    console.warn('localStorage not available:', e);
  }
}
