/**
 * 认知拉格朗日点 · 新决策协议入口
 */

import { bindTierSelector, renderTierSelector, setSelectedTier } from '../components/tier-selector.js';
import { state } from '../core/state.js';
import { clearEngineBStatusPolling } from './engine-b.js';
import { emitDecisionStarEvent } from '../core/renderer.js';
import {
  clearSavedDecisionId,
  requestJson,
  saveDecisionId,
  getSavedDecisionId,
  setButtonLoading,
  showToast,
} from './utils.js';
import { showView } from './ui-handlers.js';

function getDecisionView() {
  return state.decisionFlowView;
}

async function syncCurrentDecisionState() {
  const decisionId = state.currentDecisionId || state.currentDecision?.decision_id || '';
  if (!decisionId) return state.currentDecision;

  const payload = await requestJson(`/api/decision/status?id=${encodeURIComponent(decisionId)}`);
  if (payload.decision) {
    renderDecisionSession(payload.decision);
    return payload.decision;
  }
  return state.currentDecision;
}

function escapeHtml(text) {
  return String(text || '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function closeDecisionStream() {
  if (state.decisionEventSource) {
    state.decisionEventSource.close();
    state.decisionEventSource = null;
  }
  if (state.decisionEventRetryTimer) {
    clearTimeout(state.decisionEventRetryTimer);
    state.decisionEventRetryTimer = null;
  }
}

function isSafariBrowser() {
  const userAgent = navigator?.userAgent || '';
  return /Safari/i.test(userAgent) && !/Chrome|Chromium|Android/i.test(userAgent);
}

const TIER_FALLBACKS = {
  quick: { key: 'quick', label: '⚡ 快速', enable_simulation: false, allow_manual_simulation: false },
  deep: { key: 'deep', label: '💡 沉思', enable_simulation: false, allow_manual_simulation: true },
  pro: { key: 'pro', label: '🔥 Pro', tagline: '5分钟 · 出版级推演', enable_simulation: true, allow_manual_simulation: true },
  ultra: { key: 'ultra', label: '🌌 Ultra', tagline: '高烧 · Monte Carlo 多代理碰撞', enable_simulation: true, allow_manual_simulation: true },
};

function getTierConfig(tier) {
  const normalized = String(tier || '').trim().toLowerCase();
  return (
    state.decisionTiers?.[normalized]
    || state.decisionTiers?.deep
    || TIER_FALLBACKS[normalized]
    || TIER_FALLBACKS.deep
    || null
  );
}

function getTierTitle(tier) {
  const config = getTierConfig(tier);
  if (!config) return '🧭 决策分析';
  return `${config.label} · 决策分析`;
}

function canEnterSimulationForTier(tier) {
  const config = getTierConfig(tier);
  return Boolean(config?.enable_simulation || config?.allow_manual_simulation);
}

function hasPendingQuestions(session, questionsKey, answersKey) {
  const questions = Array.isArray(session?.[questionsKey]) ? session[questionsKey] : [];
  const answers = session?.[answersKey] || {};
  return questions.length > 0 && Object.keys(answers).length < questions.length;
}

function hasInsightResult(session) {
  return Boolean(
    session?.recommendation ||
    session?.action_plan ||
    session?.reasoning ||
    Number(session?.updated_pro_total) > 0 ||
    Number(session?.updated_con_total) > 0
  );
}

function hasSimulatorResult(session) {
  return Boolean(session?.simulator_output);
}

const ENGINEB_PHASE_PROGRESS = {
  b1_diagnosis: 200,
  b2_info_fill: 320,
  b3_cognitive_unlock: 340,
  b4_experience_sim: 360,
  b5_emotional_mirror: 380,
  b5_5_alternative: 390,
  c1_reevaluation: 430,
  a_recheck: 460,
  b6_sim_params: 520,
  b7_sim_timelines: 620,
  b8_sim_coping: 640,
  b9_sim_comparison: 660,
  simulator_complete: 760,
  completed: 780,
  abandoned: 900,
};

const DECISION_PHASE_PROGRESS = {
  act1: 60,
  act1_complete: 120,
  act2: 200,
  act2_complete: 480,
  act3: 520,
  completed: 820,
  failed: 900,
};

function getAnsweredCount(session, answersKey) {
  const answers = session?.[answersKey];
  return answers && typeof answers === 'object' ? Object.keys(answers).length : 0;
}

function getQuestionCount(session, questionsKey) {
  const questions = Array.isArray(session?.[questionsKey]) ? session[questionsKey] : [];
  return questions.length;
}

function getDecisionProgressRank(decision) {
  if (!decision) return 0;

  const session = decision.engineb_session || null;
  let rank = DECISION_PHASE_PROGRESS[decision.phase] || 0;

  const detectStatus = decision.detection_job?.status || '';
  if (!session && detectStatus === 'completed') {
    rank = Math.max(rank, 120);
  } else if (!session && detectStatus === 'running') {
    rank = Math.max(rank, 60);
  }

  if (session) {
    const sessionPhase = String(session.phase || '').trim();
    const phaseRank = ENGINEB_PHASE_PROGRESS[sessionPhase] || 260;
    rank = Math.max(rank, phaseRank);

    if (sessionPhase === 'b1_diagnosis') {
      rank += Math.min(getAnsweredCount(session, 'diagnosis_answers'), 20);
      if (
        getQuestionCount(session, 'diagnosis_questions') > 0
        && getAnsweredCount(session, 'diagnosis_answers') >= getQuestionCount(session, 'diagnosis_questions')
      ) {
        rank = Math.max(rank, 300);
      }
    }

    if (hasInsightResult(session)) {
      rank = Math.max(rank, 480);
    }

    if (sessionPhase === 'b6_sim_params') {
      rank += Math.min(getAnsweredCount(session, 'sim_answers'), 20);
    }

    if (hasSimulatorResult(session)) {
      rank = Math.max(rank, 780);
    }

    const recheck = session.recheck || {};
    const recheckResult = recheck.job?.result || {};
    if (recheck.status === 'running' || recheck.status === 'pending') {
      rank = Math.max(rank, 470);
    } else if (recheck.status === 'completed') {
      rank = Math.max(rank, recheckResult.is_lagrange_point === true ? 820 : 500);
    }
  }

  if (decision.status === 'completed') {
    rank = Math.max(rank, hasSimulatorResult(session) ? 850 : 500);
  } else if (decision.status === 'failed') {
    rank = Math.max(rank, 900);
  }

  return rank;
}

function shouldIgnoreStaleDecisionSnapshot(decision, { force = false } = {}) {
  if (!decision?.decision_id || force) return false;

  const incomingId = decision.decision_id;
  const activeId = state.currentDecisionId || state.currentDecision?.decision_id || '';
  if (activeId && activeId !== incomingId) {
    console.warn('Ignoring stale decision snapshot from inactive decision', { incomingId, activeId });
    return true;
  }

  const nextRank = getDecisionProgressRank(decision);
  const previousRank = Number(state.decisionProgressRankById?.[incomingId] || 0);
  if (nextRank < previousRank) {
    console.warn('Ignoring stale decision snapshot', {
      decisionId: incomingId,
      previousRank,
      nextRank,
      phase: decision.phase,
      step: decision.step,
      sessionPhase: decision.engineb_session?.phase || '',
    });
    return true;
  }

  return false;
}

function rememberDecisionProgress(decision) {
  if (!decision?.decision_id) return;
  const nextRank = getDecisionProgressRank(decision);
  state.decisionProgressRankById = state.decisionProgressRankById || {};
  state.decisionProgressRankById[decision.decision_id] = nextRank;
}

function buildDecisionRenderSignature(decision) {
  if (!decision) return '';
  const detect = decision.detection_job || {};
  const detectFilters = detect.filters || {};
  const detectResult = detect.result || {};
  const session = decision.engineb_session || {};
  const recheck = session.recheck || {};
  const recheckJob = recheck.job || {};
  const recheckResult = recheckJob.result || {};
  const simulatorOutput = session.simulator_output || {};

  return JSON.stringify({
    id: decision.decision_id || '',
    tier: decision.tier || '',
    status: decision.status || '',
    phase: decision.phase || '',
    statusText: decision.status_text || '',
    detectStatus: detect.status || '',
    detectPhase: detect.phase || '',
    detectFilter1: detectFilters.filter1?.status || '',
    detectFilter1Summary: detectFilters.filter1?.summary || '',
    detectFilter2: detectFilters.filter2?.status || '',
    detectFilter2Summary: detectFilters.filter2?.summary || '',
    detectFilter3: detectFilters.filter3?.status || '',
    detectFilter3Summary: detectFilters.filter3?.summary || '',
    detectResultMode: detectResult.is_lagrange_point === true ? 'lagrange' : (detectResult.failed_at || ''),
    sessionId: session.session_id || '',
    sessionPhase: session.phase || '',
    diagAnswered: Object.keys(session.diagnosis_answers || {}).length,
    diagTotal: Array.isArray(session.diagnosis_questions) ? session.diagnosis_questions.length : 0,
    simAnswered: Object.keys(session.sim_answers || {}).length,
    simTotal: Array.isArray(session.sim_questions) ? session.sim_questions.length : 0,
    recommendation: session.recommendation || '',
    actionPlan: session.action_plan || '',
    reasoning: session.reasoning || '',
    updatedPro: session.updated_pro_total ?? '',
    updatedCon: session.updated_con_total ?? '',
    recheckStatus: recheck.status || '',
    recheckMode: recheckResult.is_lagrange_point === true ? 'lagrange' : (recheckResult.failed_at || ''),
    simulatorDone: Boolean(session.simulator_output),
    simulatorInsight: simulatorOutput.final_insight || '',
    simulatorSummary: simulatorOutput.comparison_summary || '',
  });
}

function updateTracePanel(detailsId, logId, entries) {
  const details = document.getElementById(detailsId);
  const log = document.getElementById(logId);
  if (!details || !log) return;

  const rows = Array.isArray(entries) ? entries : [];
  if (!rows.length) {
    if (!details.classList.contains('hidden')) {
      details.classList.add('hidden');
    }
    if (log.innerHTML) {
      log.innerHTML = '';
    }
    log.dataset.traceSignature = '';
    return;
  }

  const signature = JSON.stringify(rows.map((item) => ({
    phase: String(item?.phase || ''),
    title: String(item?.title || ''),
    detail: String(item?.detail || ''),
    at: String(item?.at || ''),
  })));
  if (log.dataset.traceSignature === signature) {
    if (details.classList.contains('hidden')) {
      details.classList.remove('hidden');
    }
    return;
  }

  if (details.classList.contains('hidden')) {
    details.classList.remove('hidden');
  }
  log.innerHTML = rows.map((item) => {
    const title = String(item?.title || '').trim();
    const detail = String(item?.detail || '').trim();
    const phase = String(item?.phase || '').trim();
    const at = String(item?.at || '').trim();
    const header = [phase, title].filter(Boolean).join(' · ');
    return `
      <div class="log-entry">
        ${header ? `<strong>${escapeHtml(header)}</strong>` : ''}
        ${detail ? `<div>${escapeHtml(detail)}</div>` : ''}
        ${at ? `<div class="thinking-at">${escapeHtml(at)}</div>` : ''}
      </div>
    `;
  }).join('');
  log.dataset.traceSignature = signature;
}

function updateDecisionTrace(kind, session) {
  const entries = Array.isArray(session?.processing_trace) ? session.processing_trace : [];
  if (kind === 'b1') {
    updateTracePanel('c1-trace-details', 'c1-trace-log', entries);
    updateTracePanel('b1-thinking-details', 'b1-thinking-log', entries);
    return;
  }
  if (kind === 'sim') {
    updateTracePanel('sim-trace-details', 'sim-trace-log', entries);
    updateTracePanel('sim-thinking-details', 'sim-thinking-log', entries);
    updateTracePanel('sim-error-trace-details', 'sim-error-trace-log', entries);
  }
}

function hideLegacyEnginebButtonsForDecision(decision) {
  const startSimBtn = document.getElementById('engineb-start-sim-btn');
  const resetBtn = document.getElementById('engineb-reset-btn');
  if (startSimBtn) {
    const tier = String(decision?.tier || '').trim().toLowerCase();
    const session = decision?.engineb_session || {};
    const simulationEnabled = Boolean(tier && canEnterSimulationForTier(tier));
    const simulatorAlreadyInPlay = Boolean(
      session?.simulator_output
      || (Array.isArray(session?.sim_questions) && session.sim_questions.length > 0)
      || ['b6_sim_params', 'b7_sim_timelines', 'b8_sim_coping', 'b9_sim_comparison', 'simulator_complete'].includes(session?.phase)
    );
    const shouldHide = !(simulationEnabled || simulatorAlreadyInPlay);
    startSimBtn.style.display = shouldHide ? 'none' : '';
  }
  if (resetBtn) {
    resetBtn.textContent = '🔄 重新开始';
  }
}

export async function bootstrapDecisionProtocol() {
  try {
    const payload = await requestJson('/api/decision/tiers');
    state.decisionTiers = payload.tiers || {};
  } catch (error) {
    state.decisionTiers = {};
  }

  renderTierSelector();
  bindTierSelector();
  if (state.currentDecision) {
    renderDecisionSession(state.currentDecision, { force: true });
  }
}

export async function restoreDecisionSession() {
  const savedDecisionId = getSavedDecisionId();
  if (!savedDecisionId) return null;

  try {
    const payload = await requestJson(`/api/decision/status?id=${encodeURIComponent(savedDecisionId)}`);
    if (payload.decision?.decision_id === savedDecisionId) {
      showView('detection');
      renderDecisionSession(payload.decision);
      if (payload.active) {
        startDecisionEvents(savedDecisionId);
      }
      return payload.decision;
    }
  } catch (error) {
    console.warn('Failed to restore decision session:', error);
  }

  clearSavedDecisionId();
  return null;
}

export function renderDecisionSession(decision, { force = false, clearCache = false } = {}) {
  const view = getDecisionView();
  if (!view || !decision) return;

  if (shouldIgnoreStaleDecisionSnapshot(decision, { force })) {
    return;
  }

  if (clearCache || (force && isSafariBrowser())) {
    state.lastDecisionRenderSignature = '';
    view.clearRenderCache?.();
  }

  rememberDecisionProgress(decision);
  state.currentDecision = decision;
  state.currentDecisionId = decision.decision_id || '';
  saveDecisionId(state.currentDecisionId);
  state.engineBSession = decision.engineb_session || null;

  if (
    (Array.isArray(decision.logs) && decision.logs.length > 0)
    || (Array.isArray(decision.engineb_session?.processing_trace) && decision.engineb_session.processing_trace.length > 0)
  ) {
    view.renderThinkingLogs(decision.logs, {
      trace: decision.engineb_session?.processing_trace || [],
      phase: decision.engineb_session?.phase || decision.step || '',
    });
  }

  const renderSignature = buildDecisionRenderSignature(decision);
  if (!force && state.lastDecisionRenderSignature === renderSignature) {
    const session = decision.engineb_session || null;
    if (session) {
      if (
        hasPendingQuestions(session, 'sim_questions', 'sim_answers')
        || hasSimulatorResult(session)
        || ['b6_sim_params', 'b7_sim_timelines', 'b8_sim_coping', 'b9_sim_comparison', 'simulator_complete'].includes(session.phase)
      ) {
        updateDecisionTrace('sim', session);
      } else {
        updateDecisionTrace('b1', session);
      }
    }
    return;
  }
  state.lastDecisionRenderSignature = renderSignature;

  view.setDetectionTitle(getTierTitle(decision.tier));
  view.setQuestionPreview(decision.question || '');

  if (decision.analysis) {
    view.renderDetectionAnalysis(decision.analysis, decision.status !== 'running');
  }

  if (decision.tier === 'quick') {
    if (decision.status === 'running') {
      view.activateDetectionStep(1);
      return;
    }
    view.activateDetectionStep(3);
    view.renderFlashDecisionResult(decision);
    return;
  }

  const detectJob = decision.detection_job;
  if (detectJob?.analysis) {
    view.renderDetectionAnalysis(detectJob.analysis, detectJob.status === 'completed');
  }
  if (detectJob?.filters) {
    view.renderDetectionFilters(detectJob);
  }

  const session = decision.engineb_session;
  if (!session) {
    if (detectJob?.status === 'completed' || detectJob?.status === 'failed') {
      view.activateDetectionStep(3);
      view.renderDetectionResult({
        detectionJob: detectJob,
        question: decision.question,
        setCurrentClp: (clp) => {
          state.currentCLP = clp;
          return clp;
        },
      });
      return;
    }
    view.activateDetectionStep(detectJob?.filters ? 2 : 1);
    return;
  }

  const recheck = session.recheck || {};
  const recheckJob = recheck.job || {};
  const recheckResult = recheckJob.result || {};
  if (recheck.status === 'completed' && recheckResult.is_lagrange_point === true) {
    view.activateDetectionStep(3);
    view.renderDetectionResult({
      detectionJob: recheckJob,
      question: decision.question,
      setCurrentClp: (clp) => {
        state.currentCLP = clp;
        return clp;
      },
    });
    return;
  }

  if (session.phase === 'b1_diagnosis' && hasPendingQuestions(session, 'diagnosis_questions', 'diagnosis_answers')) {
    view.activateDetectionStep(0);
    view.renderB1Questions(session, {});
    updateDecisionTrace('b1', session);
    return;
  }

  if (session.phase === 'abandoned') {
    if (hasPendingQuestions(session, 'sim_questions', 'sim_answers') || hasSimulatorResult(session)) {
      view.activateDetectionStep(5);
      view.showSimulatorError(session);
      updateDecisionTrace('sim', session);
      return;
    }
    view.activateDetectionStep(0);
    view.showB1Processing(session);
    updateDecisionTrace('b1', session);
    return;
  }

  if (hasPendingQuestions(session, 'sim_questions', 'sim_answers') || session.phase === 'b6_sim_params') {
    view.activateDetectionStep(5);
    view.renderSimulatorQuestionStep(session, {});
    updateDecisionTrace('sim', session);
    return;
  }

  if (hasSimulatorResult(session) || session.phase === 'simulator_complete') {
    view.activateDetectionStep(5);
    view.renderSimulatorResults(session, { updateTrace: updateDecisionTrace });
    return;
  }

  if (['b7_sim_timelines', 'b8_sim_coping', 'b9_sim_comparison'].includes(session.phase)) {
    view.activateDetectionStep(5);
    view.showSimulatorProcessing(session);
    updateDecisionTrace('sim', session);
    return;
  }

  if (hasInsightResult(session)) {
    view.activateDetectionStep(4);
    view.renderC1Result(session, { updateTrace: updateDecisionTrace, decision });
    hideLegacyEnginebButtonsForDecision(decision);
    return;
  }

  view.activateDetectionStep(0);
  view.showB1Processing(session);
  updateDecisionTrace('b1', session);
}

export function startDecisionEvents(decisionId, { preserveRetry = false } = {}) {
  closeDecisionStream();
  if (!preserveRetry) {
    state.decisionEventRetryCount = 0;
  }
  const source = new EventSource(`/api/decision/events?id=${encodeURIComponent(decisionId)}`);
  state.decisionEventSource = source;

  source.onmessage = (event) => {
    try {
      const payload = JSON.parse(event.data);
      const decision = payload.decision;
      if (!decision) return;
      state.decisionEventRetryCount = 0;
      renderDecisionSession(decision);
      if (decision.status === 'completed' || decision.status === 'failed') {
        closeDecisionStream();
      }
    } catch (error) {
      console.error('Decision SSE parse failed', error);
    }
  };

  source.addEventListener('star_event', (event) => {
    try {
      const payload = JSON.parse(event.data || '{}');
      emitDecisionStarEvent(payload);
    } catch (error) {
      console.warn('Decision star_event parse failed', error);
    }
  });

  source.onerror = () => {
    if (state.decisionEventSource === source) {
      source.close();
      state.decisionEventSource = null;
    }

    const currentId = state.currentDecisionId || state.currentDecision?.decision_id || decisionId;
    const currentStatus = state.currentDecision?.status || '';
    if (!currentId || currentStatus === 'completed' || currentStatus === 'failed') {
      closeDecisionStream();
      return;
    }

    const retryCount = Number(state.decisionEventRetryCount || 0);
    if (retryCount >= 5) {
      showToast('实时更新已断开，请刷新页面或稍后重试。', 'warning', 2600);
      return;
    }

    const delay = Math.min(1000 * (2 ** retryCount), 8000);
    state.decisionEventRetryCount = retryCount + 1;
    state.decisionEventRetryTimer = window.setTimeout(() => {
      state.decisionEventRetryTimer = null;
      requestJson(`/api/decision/status?id=${encodeURIComponent(currentId)}`)
        .then((payload) => {
          const latest = payload.decision;
          if (latest) {
            renderDecisionSession(latest, { force: true });
            if (latest.status === 'completed' || latest.status === 'failed') {
              closeDecisionStream();
              return;
            }
          }
          startDecisionEvents(currentId, { preserveRetry: true });
        })
        .catch(() => {
          startDecisionEvents(currentId, { preserveRetry: true });
        });
    }, delay);
  };
}

function prepareDecisionScreen(question, tier) {
  const view = getDecisionView();
  clearEngineBStatusPolling();
  clearSavedDecisionId();
  state.pendingDecisionAnswer = false;

  if (state.detectionEventSource) {
    state.detectionEventSource.close();
    state.detectionEventSource = null;
  }
  closeDecisionStream();

  showView('detection');
  view?.resetDetectionUi();
  view?.setDetectionTitle(getTierTitle(tier));
  view?.setQuestionPreview(question);
  view?.activateDetectionStep(1);

  state.currentDecision = null;
  state.currentDecisionId = '';
  state.lastDecisionRenderSignature = '';
  state.decisionProgressRankById = {};
  state.engineBSession = null;
  state.detectionJob = null;
  state.detectionJobId = '';
  state.currentCLP = null;
  setSelectedTier(tier);
}

export async function startDecisionFlow(question, explicitTier = '') {
  const text = String(question || '').trim();
  if (!text) {
    showToast('请输入你正在纠结的问题', 'warning');
    return;
  }

  const tier = explicitTier || state.selectedTier || 'deep';
  prepareDecisionScreen(text, tier);

  try {
    const payload = await requestJson('/api/decision/start', {
      method: 'POST',
      body: JSON.stringify({ question: text, tier }),
    });
    const decision = payload.decision;
    if (!decision?.decision_id) {
      throw new Error('后端没有返回有效的决策 ID');
    }
    renderDecisionSession(decision);
    startDecisionEvents(decision.decision_id);
  } catch (error) {
    showToast(`启动决策失败: ${error.message}`, 'error');
  }
}

export async function upgradeCurrentDecision(targetTier = '') {
  const decision = state.currentDecision;
  const tier = String(targetTier || '').trim().toLowerCase();
  if (!decision?.decision_id) {
    showToast('当前没有可升级的决策流程', 'warning');
    return;
  }
  if (!tier) {
    showToast('缺少目标思考档位', 'warning');
    return;
  }
  if (decision.tier === tier) {
    showToast('当前已经在这个档位了', 'info', 1600);
    return;
  }

  closeDecisionStream();
  state.lastDecisionRenderSignature = '';
  setSelectedTier(tier);

  try {
    const payload = await requestJson('/api/decision/upgrade', {
      method: 'POST',
      body: JSON.stringify({
        decision_id: decision.decision_id,
        tier,
      }),
    });
    renderDecisionSession(payload.decision, { force: true });
    if (payload.active) startDecisionEvents(decision.decision_id);
  } catch (error) {
    showToast(`升级失败: ${error.message}`, 'error');
  }
}

export async function submitCurrentDecisionAnswer() {
  if (state.pendingDecisionAnswer) {
    showToast('上一条回答还在提交中，请稍等', 'info', 1600);
    return;
  }

  const view = getDecisionView();
  let decision = state.currentDecision;
  if ((!decision?.engineb_session || !decision?.decision_id) && state.currentDecisionId) {
    try {
      decision = await syncCurrentDecisionState();
    } catch (error) {
      showToast(`同步当前问题状态失败: ${error.message}`, 'error');
    }
  }

  if (!decision || !view) {
    showToast('当前问题状态还没准备好，请刷新页面后重试', 'warning');
    return;
  }

  const session = decision.engineb_session;
  if (!session) {
    showToast('当前会话还在同步中，请稍等一秒再试', 'warning');
    return;
  }

  if (hasPendingQuestions(session, 'diagnosis_questions', 'diagnosis_answers')) {
    const questions = Array.isArray(session.diagnosis_questions) ? session.diagnosis_questions : [];
    const currentIndex = Object.keys(session.diagnosis_answers || {}).length;
    const question = questions[currentIndex];
    if (!question) {
      showToast('当前没有可提交的追问，请稍后重试', 'warning');
      return;
    }
    const openInput = document.getElementById('b1-open-input');
    const answer = openInput && !openInput.classList.contains('hidden')
      ? openInput.value.trim()
      : String(view.getSelectedB1Option() || '').trim();
    if (!answer) {
      showToast('请先输入或选择一个回答', 'warning');
      return;
    }

    const submitButton = document.getElementById('b1-submit');
    state.pendingDecisionAnswer = true;
    setButtonLoading(submitButton, true, currentIndex >= questions.length - 1 ? '正在分析…' : '提交中…');

    try {
      const payload = await requestJson('/api/decision/answer', {
        method: 'POST',
        body: JSON.stringify({
          decision_id: decision.decision_id,
          question_id: question.id,
          answer,
        }),
      });
      renderDecisionSession(payload.decision, { force: true, clearCache: true });
      if (payload.active) startDecisionEvents(decision.decision_id);
    } catch (error) {
      setButtonLoading(submitButton, false);
      showToast(`提交失败: ${error.message}`, 'error');
    } finally {
      state.pendingDecisionAnswer = false;
    }
    return;
  }

  if (hasPendingQuestions(session, 'sim_questions', 'sim_answers')) {
    const questions = Array.isArray(session.sim_questions) ? session.sim_questions : [];
    const currentIndex = Object.keys(session.sim_answers || {}).length;
    const question = questions[currentIndex];
    if (!question) {
      showToast('当前没有可提交的模拟器问题，请稍后重试', 'warning');
      return;
    }
    const openInput = document.getElementById('sim-open-input');
    const answer = openInput && !openInput.classList.contains('hidden')
      ? openInput.value.trim()
      : String(view.getSelectedSimOption() || '').trim();
    if (!answer) {
      showToast('请先输入或选择一个回答', 'warning');
      return;
    }

    const submitButton = document.getElementById('sim-submit');
    state.pendingDecisionAnswer = true;
    setButtonLoading(submitButton, true, currentIndex >= questions.length - 1 ? '正在推演…' : '提交中…');

    try {
      const payload = await requestJson('/api/decision/answer', {
        method: 'POST',
        body: JSON.stringify({
          decision_id: decision.decision_id,
          question_id: question.id,
          answer,
        }),
      });
      renderDecisionSession(payload.decision, { force: true, clearCache: true });
      if (payload.active) startDecisionEvents(decision.decision_id);
    } catch (error) {
      setButtonLoading(submitButton, false);
      showToast(`提交失败: ${error.message}`, 'error');
    } finally {
      state.pendingDecisionAnswer = false;
    }
    return;
  }

  showToast('当前没有待提交的问题，页面可能已经推进到下一步了', 'info');
}

export async function startDecisionSimulator() {
  const decision = state.currentDecision;
  if (!decision?.decision_id) {
    showToast('当前没有可继续的决策流程', 'warning');
    return;
  }

  const session = decision.engineb_session || {};
  const recheck = session.recheck || {};
  const recheckJob = recheck.job || {};
  const recheckResult = recheckJob.result || {};
  if (recheck.status === 'pending' || recheck.status === 'running') {
    showToast('二次检测还在进行，结束后你可以手动进入第三幕', 'info', 2200);
    return;
  }
  if (recheck.status === 'completed' && recheckResult.is_lagrange_point === true) {
    showToast('二次检测已确认这是认知拉格朗日点，不需要再启动模拟器', 'info', 2600);
    renderDecisionSession(decision, { force: true });
    return;
  }
  const simulatorHasPendingQuestions = hasPendingQuestions(session, 'sim_questions', 'sim_answers');
  const simulatorHasResult = hasSimulatorResult(session) || session.phase === 'simulator_complete';
  const simulatorHasActivePhase = ['b6_sim_params', 'b7_sim_timelines', 'b8_sim_coping', 'b9_sim_comparison'].includes(session.phase);

  if (simulatorHasResult) {
    renderDecisionSession(decision, { force: true });
    return;
  }
  if ((simulatorHasPendingQuestions || simulatorHasActivePhase) && decision.status === 'running') {
    renderDecisionSession(decision, { force: true });
    return;
  }

  try {
    const payload = await requestJson('/api/decision/simulate/start', {
      method: 'POST',
      body: JSON.stringify({ decision_id: decision.decision_id }),
    });
    renderDecisionSession(payload.decision, { force: true, clearCache: true });
    if (payload.active) startDecisionEvents(decision.decision_id);
  } catch (error) {
    showToast(`启动模拟器失败: ${error.message}`, 'error');
  }
}

export function restartCurrentDecision() {
  const decision = state.currentDecision;
  if (!decision?.question) {
    showToast('当前没有可重启的决策流程', 'warning');
    return;
  }
  startDecisionFlow(decision.question, decision.tier || state.selectedTier || 'deep');
}

export function returnToDecisionRecommendation() {
  const decision = state.currentDecision;
  const view = getDecisionView();
  if (!decision?.engineb_session || !view) return;
  view.activateDetectionStep(4);
  view.renderC1Result(decision.engineb_session, { updateTrace: updateDecisionTrace, decision });
  hideLegacyEnginebButtonsForDecision(decision);
}

export function clearCurrentDecision(preserveSavedId = false) {
  closeDecisionStream();
  if (!preserveSavedId) {
    clearSavedDecisionId();
  }
  state.pendingDecisionAnswer = false;
  state.currentDecision = null;
  state.currentDecisionId = '';
  state.decisionEventRetryCount = 0;
  state.lastDecisionRenderSignature = '';
  state.decisionProgressRankById = {};
  state.engineBSession = null;
}

if (typeof window !== 'undefined') {
  window.__CLP_DECISION_DEBUG__ = {
    renderDecisionSession,
    getDecisionProgressRank,
  };
}
