/**
 * 认知拉格朗日点 · 模块化入口
 */

import { createDecisionFlowView } from './frontend/components/decision-flow-view.js';
import { state, normalizeSystemRecord } from './frontend/core/state.js';
import { initRenderer, render, resize } from './frontend/core/renderer.js';
import {
  initInteraction,
  getCurrentInteractionDebug,
  hitTestInteractiveNode,
} from './frontend/core/interaction.js';
import { rebuildDiscoveredNodes } from './frontend/modules/engine-a.js';
import { SYSTEMS } from './data.js';
import { DISCOVERED_SYSTEMS } from './discovered-data.js';
import {
  bootstrapDecisionProtocol,
  renderDecisionSession,
  startDecisionEvents,
  startDecisionFlow,
  submitCurrentDecisionAnswer,
} from './frontend/modules/decision-engine.js';
import {
  requestJson,
  showToast,
  getSavedDecisionId,
  getSavedSessionId,
  clearSavedDecisionId,
  clearSavedSessionId,
} from './frontend/modules/utils.js';
import {
  renderEngineBSession,
  startEngineBStatusPolling,
  submitCurrentB1Answer,
  submitCurrentSimAnswer,
} from './frontend/modules/engine-b.js';
import './frontend/modules/ui-bridge.js';
import { showView, closeDetail } from './frontend/modules/ui-handlers.js';

const DECISION_PHASE_LABELS = {
  act1: '第一幕 · 结构判断',
  act1_complete: '第一幕完成',
  act2: '第二幕 · 决策突破',
  act2_complete: '第二幕完成',
  act3: '第三幕 · 未来模拟',
  completed: '已完成',
  failed: '已中断',
};

function escapeInlineHtml(text) {
  return String(text || '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function getTierLabel(tier) {
  return state.decisionTiers?.[tier]?.label
    || ({
      quick: '⚡ 快速',
      deep: '💡 沉思',
      pro: '🔥 Pro',
      ultra: '🌌 Ultra',
    }[tier] || tier || '未命名档位');
}

function getPhaseLabel(phase) {
  return DECISION_PHASE_LABELS[phase] || phase || '进行中';
}

function formatTimeLabel(value) {
  const raw = String(value || '').trim();
  if (!raw) return '刚刚';
  return raw.replace('T', ' ').slice(0, 16);
}

function getSessionSummary(resume) {
  if (!resume) return '';
  if (resume.kind === 'decision') {
    const decision = resume.decision || {};
    const result = decision.result || {};
    const analysis = decision.analysis || {};
    return String(
      decision.status_text
      || result.summary
      || result.recommendation
      || analysis.analysis_summary
      || '可以从上次中断的位置继续。'
    ).trim();
  }
  const session = resume.session || {};
  return String(
    session.last_error
    || session.recommendation
    || session.reasoning
    || '检测到一条历史恢复记录，可以继续回到上次的决策突破。'
  ).trim();
}

async function openDecisionSession(decisionId) {
  const payload = await requestJson(`/api/decision/status?id=${encodeURIComponent(decisionId)}`);
  const decision = payload.decision;
  if (!decision?.decision_id) {
    throw new Error('找不到这条决策记录');
  }
  showView('detection');
  renderDecisionSession(decision);
  if (payload.active) {
    startDecisionEvents(decision.decision_id);
  }
  return decision;
}

async function openHistoricalEngineBSession(sessionId) {
  const payload = await requestJson(`/api/engineb/status?session_id=${encodeURIComponent(sessionId)}`);
  const session = payload.session;
  if (!session?.session_id) {
    throw new Error('找不到这条历史恢复记录');
  }

  state.engineBSession = session;
  showView('detection');
  state.decisionFlowView?.resetDetectionUi();
  state.decisionFlowView?.setDetectionTitle('🧭 决策突破 · 历史恢复');
  state.decisionFlowView?.activateDetectionStep(0);
  state.decisionFlowView?.setQuestionPreview(session.original_question || '');
  renderEngineBSession(session);

  if (payload.active) {
    const phase = String(session.phase || '');
    const mode = phase.startsWith('b6_')
      || phase.startsWith('b7_')
      || phase.startsWith('b8_')
      || phase.startsWith('b9_')
      || phase === 'simulator_complete'
      ? 'sim'
      : 'b1';
    startEngineBStatusPolling(mode, session);
  }

  return session;
}

function renderHomeSessionCard(resume) {
  const card = document.getElementById('home-session-card');
  const meta = document.getElementById('home-session-meta');
  const question = document.getElementById('home-session-question');
  const summary = document.getElementById('home-session-summary');
  const continueBtn = document.getElementById('home-session-continue');
  const reportBtn = document.getElementById('home-session-report');
  if (!card || !meta || !question || !summary || !continueBtn || !reportBtn) return;

  if (!resume) {
    card.classList.add('hidden');
    card.dataset.kind = '';
    card.dataset.id = '';
    return;
  }

  const isDecision = resume.kind === 'decision';
  const source = isDecision ? (resume.decision || {}) : (resume.session || {});
  const sourceId = isDecision ? source.decision_id : source.session_id;
  const questionText = isDecision ? source.question : source.original_question;
  const tierText = isDecision ? getTierLabel(source.tier) : '历史恢复';
  const phaseText = isDecision ? getPhaseLabel(source.phase) : (source.phase || '决策突破恢复');
  const timeText = formatTimeLabel(source.updated_at || source.created_at);

  meta.textContent = `${tierText} · ${phaseText} · ${timeText}`;
  question.textContent = questionText || '未命名问题';
  summary.textContent = getSessionSummary(resume);
  continueBtn.textContent = isDecision ? '继续推演' : '继续恢复';
  reportBtn.disabled = !isDecision;
  reportBtn.title = isDecision ? '导出当前决策报告' : '历史恢复记录暂不支持这里直接导出';
  card.dataset.kind = resume.kind;
  card.dataset.id = sourceId || '';
  card.classList.remove('hidden');
}

function renderHomeHistory(decisions) {
  const list = document.getElementById('home-history-list');
  if (!list) return;

  const rows = Array.isArray(decisions) ? decisions.slice(0, 6) : [];
  if (!rows.length) {
    list.innerHTML = '<div class="home-history-empty">还没有保存的决策记录，先开始第一轮吧。</div>';
    return;
  }

  list.innerHTML = rows.map((item) => `
    <button type="button" class="home-history-item" data-decision-id="${escapeInlineHtml(item.decision_id || '')}">
      <div class="home-history-title">${escapeInlineHtml(item.question || '未命名问题')}</div>
      <div class="home-history-meta">${escapeInlineHtml(getTierLabel(item.tier))} · ${escapeInlineHtml(getPhaseLabel(item.phase))}</div>
      <div class="home-history-time">${escapeInlineHtml(formatTimeLabel(item.updated_at || item.created_at))}</div>
    </button>
  `).join('');
}

function renderHistoricalEngineBSessions(sessions) {
  const list = document.getElementById('engineb-sessions-list');
  if (!list) return;

  const rows = Array.isArray(sessions)
    ? [...sessions].sort((a, b) => String(b.updated_at || '').localeCompare(String(a.updated_at || '')))
    : [];

  if (!rows.length) {
    list.innerHTML = '<div class="history-empty">还没有可恢复的历史记录。</div>';
    return;
  }

  list.innerHTML = rows.slice(0, 12).map((item) => {
    const title = escapeInlineHtml(item.original_question || item.question || '未命名问题');
    const phase = escapeInlineHtml(item.phase || '处理中');
    const time = escapeInlineHtml(formatTimeLabel(item.updated_at || item.created_at));
    const sessionId = escapeInlineHtml(item.session_id || '');
    return `
      <button type="button" class="history-item-session" data-session-id="${sessionId}">
        <div class="session-title">${title}</div>
        <div class="session-meta">
          <span class="session-tag">${phase}</span>
          <span>${time}</span>
        </div>
      </button>
    `;
  }).join('');
}

async function loadHistoricalEngineBSessions() {
  const list = document.getElementById('engineb-sessions-list');
  if (!list) return;
  list.innerHTML = '<div class="history-empty">正在加载历史恢复记录...</div>';

  try {
    const payload = await requestJson('/api/engineb/sessions');
    renderHistoricalEngineBSessions(payload.sessions || []);
  } catch (error) {
    list.innerHTML = `<div class="history-empty">加载失败：${escapeInlineHtml(error.message || '未知错误')}</div>`;
  }
}

async function loadSavedResumeCandidate() {
  const decisionId = getSavedDecisionId();
  if (decisionId) {
    try {
      const payload = await requestJson(`/api/decision/status?id=${encodeURIComponent(decisionId)}`);
      if (payload.decision?.decision_id === decisionId) {
        return { kind: 'decision', active: Boolean(payload.active), decision: payload.decision };
      }
    } catch (error) {
      console.warn('Failed to hydrate saved decision session:', error);
    }
    clearSavedDecisionId();
  }

  const sessionId = getSavedSessionId();
  if (sessionId) {
    try {
      const payload = await requestJson(`/api/engineb/status?session_id=${encodeURIComponent(sessionId)}`);
      if (payload.session?.session_id === sessionId) {
        return { kind: 'engineb', active: Boolean(payload.active), session: payload.session };
      }
    } catch (error) {
      console.warn('Failed to hydrate historical engine-b session:', error);
    }
    clearSavedSessionId();
  }

  return null;
}

async function hydrateHomeSurface() {
  const [resumeResult, historyResult] = await Promise.allSettled([
    loadSavedResumeCandidate(),
    requestJson('/api/decision/history'),
  ]);

  renderHomeSessionCard(resumeResult.status === 'fulfilled' ? resumeResult.value : null);
  state.decisionHistory = historyResult.status === 'fulfilled' ? (historyResult.value.decisions || []) : [];
  renderHomeHistory(state.decisionHistory);
}

function init() {
  console.log('CLP System Initializing...');
  const canvas = document.getElementById('cosmos');
  document.body.dataset.frontendMode = window.location.port === '4174'
    ? 'Vite Dev'
    : (
      document.querySelector('script[type="module"][src*="assets/"]')
      || document.querySelector('link[rel="stylesheet"][href*="assets/"]')
        ? 'Vite Build'
        : 'Source'
    );

  if (canvas) {
    const useWebGL = Boolean(window.PIXI && new URLSearchParams(window.location.search).get('webgl') === '1');
    initRenderer(canvas, useWebGL);
    initInteraction(canvas);
  } else {
    console.warn('Canvas not found! Visuals may fail.');
  }

  window.__CLP_DEBUG__ = {
    getState: () => ({
      appState: state.appState,
      currentDecisionId: state.currentDecisionId || state.currentDecision?.decision_id || '',
      selectedTier: state.selectedTier,
      overlayNodeCount: Array.isArray(state.cosmosOverlayNodes) ? state.cosmosOverlayNodes.length : 0,
      historyCount: Array.isArray(state.decisionHistory) ? state.decisionHistory.length : 0,
    }),
    getInteraction: () => getCurrentInteractionDebug(),
    hitTest: (x, y) => hitTestInteractiveNode(x, y),
  };

  window.addEventListener('clp:future-path-selected', (event) => {
    const path = event.detail?.path || {};
    const label = path.label || '未来路径';
    const probability = Number(path.probability || 0);
    showToast(`已选中${label}：${Number.isFinite(probability) ? probability : '--'}%`, 'info', 2200);
  });

  try {
    state.decisionFlowView = createDecisionFlowView({
      document,
      escapeHtml: (str) => String(str).replace(/[&<>"']/g, (m) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[m])),
      shouldIgnoreEnterSubmit: (e, composing) => Boolean(e && (e.isComposing || e.keyCode === 229 || composing)),
    });
    state.decisionFlowView.bindInteractiveInputs({
      onB1Submit: () => (state.currentDecisionId ? submitCurrentDecisionAnswer() : submitCurrentB1Answer()),
      onSimSubmit: () => (state.currentDecisionId ? submitCurrentDecisionAnswer() : submitCurrentSimAnswer()),
      onB1SubmitCurrent: () => (state.currentDecisionId ? submitCurrentDecisionAnswer() : submitCurrentB1Answer()),
      onSimSubmitCurrent: () => (state.currentDecisionId ? submitCurrentDecisionAnswer() : submitCurrentSimAnswer()),
    });
  } catch (error) {
    console.error('DecisionFlowView Init Failed', error);
  }

  const initialSystems = [
    ...(Array.isArray(SYSTEMS) ? SYSTEMS : []),
    ...(Array.isArray(DISCOVERED_SYSTEMS) ? DISCOVERED_SYSTEMS : []),
  ].map((item, index) => normalizeSystemRecord(item, index));

  rebuildDiscoveredNodes(initialSystems);
  Promise.resolve(bootstrapDecisionProtocol()).finally(() => {
    hydrateHomeSurface();
  });
  window.refreshHomeSurface = hydrateHomeSurface;

  bindEvents();
  startTitleAnimation();

  console.log('Event binding complete.');
  requestAnimationFrame(loop);
}

function loop(time) {
  state.time = time / 1000;
  state.camera.x += (state.camera.targetX - state.camera.x) * 0.08;
  state.camera.y += (state.camera.targetY - state.camera.y) * 0.08;
  state.camera.zoom += (state.camera.targetZoom - state.camera.zoom) * 0.08;

  render(state.time);
  requestAnimationFrame(loop);
}

function bindEvents() {
  let homeInputComposing = false;
  const titleEnter = document.getElementById('title-enter');
  const homeStart = document.getElementById('home-start');
  const homeQuestion = document.getElementById('home-question');
  const homeBrowse = document.getElementById('home-browse');
  const homeMap = document.getElementById('home-map');
  const homeSessionCard = document.getElementById('home-session-card');
  const homeSessionContinue = document.getElementById('home-session-continue');
  const homeSessionReport = document.getElementById('home-session-report');
  const homeSessionDismiss = document.getElementById('home-session-dismiss');
  const homeHistoryList = document.getElementById('home-history-list');
  const detectionClose = document.getElementById('detection-close');
  const navBackHome = document.getElementById('nav-back-home');
  const historyToggle = document.getElementById('engineb-history-toggle');
  const historyPanel = document.getElementById('engineb-history-panel');
  const historyList = document.getElementById('engineb-sessions-list');
  const historyClose = document.getElementById('history-panel-close');
  const detailClose = document.getElementById('detail-close');
  const overlay = document.getElementById('overlay');
  const detailForce = document.getElementById('detail-force');
  const detailEngineB = document.getElementById('detail-engineb');

  if (titleEnter) {
    titleEnter.onclick = () => {
      showView('home');
      hydrateHomeSurface();
    };
  }

  if (homeStart && homeQuestion) {
    homeStart.onclick = () => {
      const question = homeQuestion.value.trim();
      if (question) startDecisionFlow(question);
      else showToast('请输入您想探索的认知问题', 'warning');
    };
    homeQuestion.addEventListener('compositionstart', () => {
      homeInputComposing = true;
    });
    homeQuestion.addEventListener('compositionend', () => {
      homeInputComposing = false;
    });
    homeQuestion.onkeydown = (event) => {
      if (event.key === 'Enter' && !event.isComposing && event.keyCode !== 229 && !homeInputComposing) {
        event.preventDefault();
        homeStart.click();
      }
    };
  }

  if (homeBrowse) homeBrowse.onclick = () => showView('cosmos');
  if (homeMap) {
    homeMap.onclick = () => {
      document.getElementById('home-history-list')?.scrollIntoView({
        behavior: 'smooth',
        block: 'start',
      });
    };
  }

  if (homeSessionContinue && homeSessionCard) {
    homeSessionContinue.onclick = async () => {
      const { kind, id } = homeSessionCard.dataset;
      if (!id) return;
      try {
        if (kind === 'decision') {
          await openDecisionSession(id);
        } else {
          await openHistoricalEngineBSession(id);
        }
      } catch (error) {
        showToast(`恢复失败: ${error.message}`, 'error');
        hydrateHomeSurface();
      }
    };
  }

  if (homeSessionReport && homeSessionCard) {
    homeSessionReport.onclick = () => {
      const { kind, id } = homeSessionCard.dataset;
      if (kind !== 'decision' || !id) {
        showToast('当前这条记录暂不支持直接导出', 'warning');
        return;
      }
      window.open(`/api/decision/report?id=${encodeURIComponent(id)}`, '_blank', 'noopener');
    };
  }

  if (homeSessionDismiss) {
    homeSessionDismiss.onclick = () => {
      clearSavedDecisionId();
      clearSavedSessionId();
      renderHomeSessionCard(null);
      showToast('已忽略本地恢复记录，你可以直接开始新的推演。', 'info');
    };
  }

  if (homeHistoryList && !homeHistoryList.dataset.boundHistory) {
    homeHistoryList.addEventListener('click', async (event) => {
      const trigger = event.target.closest('[data-decision-id]');
      if (!trigger) return;
      const decisionId = trigger.dataset.decisionId || '';
      if (!decisionId) return;
      try {
        await openDecisionSession(decisionId);
      } catch (error) {
        showToast(`打开历史决策失败: ${error.message}`, 'error');
      }
    });
    homeHistoryList.dataset.boundHistory = '1';
  }

  if (detectionClose) {
    detectionClose.onclick = () => {
      window.closeDetection?.();
    };
  }

  if (navBackHome) {
    navBackHome.onclick = () => {
      showView('home');
      hydrateHomeSurface();
    };
  }

  if (historyToggle && historyPanel) {
    historyToggle.onclick = async () => {
      const willOpen = historyPanel.classList.contains('hidden');
      historyPanel.classList.toggle('hidden');
      if (willOpen) {
        await loadHistoricalEngineBSessions();
      }
    };
  }
  if (historyClose && historyPanel) {
    historyClose.onclick = () => {
      historyPanel.classList.add('hidden');
    };
  }
  if (historyList && !historyList.dataset.boundHistorySessions) {
    historyList.addEventListener('click', async (event) => {
      const trigger = event.target.closest('[data-session-id]');
      if (!trigger) return;
      const sessionId = trigger.dataset.sessionId || '';
      if (!sessionId) return;
      try {
        await openHistoricalEngineBSession(sessionId);
        historyPanel?.classList.add('hidden');
      } catch (error) {
        showToast(`恢复历史记录失败: ${error.message}`, 'error');
      }
    });
    historyList.dataset.boundHistorySessions = '1';
  }

  if (detailClose) detailClose.onclick = () => closeDetail();
  if (overlay) overlay.onclick = () => closeDetail();
  if (detailForce) {
    detailForce.onclick = () => {
      const selected = state.selectedNode?.data || {};
      if (selected.decision_id) {
        if (!selected.decision_id) {
          showToast('这颗星点还没有可导出的报告', 'warning');
          return;
        }
        window.open(`/api/decision/report?id=${encodeURIComponent(selected.decision_id)}`, '_blank', 'noopener');
        return;
      }
      window.openForceAnalysis?.(state.currentCLP || null);
    };
  }
  if (detailEngineB) {
    detailEngineB.onclick = async () => {
      const selected = state.selectedNode?.data || {};
      if (selected.decision_id) {
        try {
          await openDecisionSession(selected.decision_id);
        } catch (error) {
          showToast(`打开这次推演失败: ${error.message}`, 'error');
        }
        return;
      }
      const question = String(
        state.selectedNode?.data?.question
        || state.selectedNode?.data?.name
        || document.querySelector('#detail-panel .detail-question')?.textContent
        || ''
      ).trim();
      if (!question) {
        showToast('缺少可用于深入推演的问题', 'warning');
        return;
      }
      startDecisionFlow(question, state.selectedTier || 'deep');
    };
  }
  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape') {
      if (state.appState === 'detail') closeDetail();
    }
  });

  window.addEventListener('resize', resize);
}

function startTitleAnimation() {
  const titleMain = document.getElementById('title-main');
  if (!titleMain) return;
  titleMain.innerHTML = '';
  const text = '认知拉格朗日点';
  text.split('').forEach((char, index) => {
    const span = document.createElement('span');
    span.className = 'char';
    span.textContent = char;
    span.style.animationDelay = `${0.8 + index * 0.12}s`;
    titleMain.appendChild(span);
  });
}

init();
