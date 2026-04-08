/**
 * 认知拉格朗日点 · Engine B (决策) 模块
 */

import { state } from '../core/state.js';
import { requestJson, showToast, getSavedSessionId, clearSavedSessionId, saveSessionId, setButtonLoading } from './utils.js';

let engineBStatusPollTimer = null;
let engineBStatusEventSource = null;
let engineBStatusPollMode = '';

function getDecisionView() {
  return state.decisionFlowView;
}

function getAnsweredCount(session, key) {
  return Object.keys(session?.[key] || {}).length;
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

function isInsightPhase(phase) {
  return [
    'b2_info_fill',
    'b3_cognitive_unlock',
    'b4_experience_sim',
    'b5_emotional_mirror',
    'c1_reevaluation',
    'a_recheck',
  ].includes(phase);
}

function isSimulatorPhase(phase) {
  return [
    'b6_sim_params',
    'b7_sim_timelines',
    'b8_sim_coping',
    'b9_sim_comparison',
    'simulator_complete',
  ].includes(phase);
}

function getCurrentB1Question(session = state.engineBSession) {
  const questions = Array.isArray(session?.diagnosis_questions) ? session.diagnosis_questions : [];
  const currentIndex = getAnsweredCount(session, 'diagnosis_answers');
  return {
    question: questions[currentIndex] || null,
    currentIndex,
    total: questions.length,
  };
}

function getCurrentSimQuestion(session = state.engineBSession) {
  const questions = Array.isArray(session?.sim_questions) ? session.sim_questions : [];
  const currentIndex = getAnsweredCount(session, 'sim_answers');
  return {
    question: questions[currentIndex] || null,
    currentIndex,
    total: questions.length,
  };
}

export async function restoreEngineBSession() {
  const savedSessionId = getSavedSessionId();
  if (!savedSessionId) return null;

  try {
    const status = await requestJson(`/api/engineb/status?session_id=${encodeURIComponent(savedSessionId)}`);
    if (status.active && status.session && status.session.session_id === savedSessionId) {
      return status.session;
    }
  } catch (error) {
    console.warn('Failed to restore session:', error);
  }

  clearSavedSessionId();
  return null;
}

export function clearEngineBStatusPolling(resetMode = true) {
  if (engineBStatusPollTimer) {
    clearTimeout(engineBStatusPollTimer);
    engineBStatusPollTimer = null;
  }
  if (engineBStatusEventSource) {
    engineBStatusEventSource.close();
    engineBStatusEventSource = null;
  }
  if (resetMode) {
    engineBStatusPollMode = '';
  }
}

function scheduleEngineBStatusPoll(delay = 1200) {
  if (engineBStatusPollTimer) {
    clearTimeout(engineBStatusPollTimer);
  }
  engineBStatusPollTimer = setTimeout(() => {
    pollEngineBSessionStatus();
  }, delay);
}

export function renderEngineBSession(session = state.engineBSession) {
  const view = getDecisionView();
  if (!view || !session) return;

  state.engineBSession = session;
  const phase = session.phase || '';
  const b1 = getCurrentB1Question(session);

  if (phase === 'b1_diagnosis' && b1.currentIndex < b1.total) {
    view.activateDetectionStep(0);
    view.renderB1Questions(session, { setButtonLoading });
    return;
  }

  if (phase === 'abandoned') {
    if (session.sim_questions?.length || isSimulatorPhase(phase) || hasSimulatorResult(session)) {
      view.activateDetectionStep(5);
      view.showSimulatorError(session);
      return;
    }
    view.activateDetectionStep(0);
    view.showB1Processing(session);
    return;
  }

  if (phase === 'b6_sim_params') {
    view.activateDetectionStep(5);
    view.renderSimulatorQuestionStep(session, { setButtonLoading });
    return;
  }

  if (phase === 'simulator_complete' || hasSimulatorResult(session)) {
    view.activateDetectionStep(5);
    view.renderSimulatorResults(session, { setButtonLoading });
    return;
  }

  if (isSimulatorPhase(phase)) {
    view.activateDetectionStep(5);
    view.showSimulatorProcessing(session);
    return;
  }

  if (hasInsightResult(session)) {
    view.activateDetectionStep(4);
    view.renderC1Result(session);
    return;
  }

  if (isInsightPhase(phase) || (b1.total > 0 && b1.currentIndex >= b1.total)) {
    view.activateDetectionStep(0);
    view.showB1Processing(session);
    return;
  }
}

function applyEngineBStatusPayload(payload) {
  if (!engineBStatusPollMode) return;

  if (!payload.active || !payload.session) {
    clearEngineBStatusPolling();
    return;
  }

  state.engineBSession = payload.session;
  renderEngineBSession(payload.session);

  const phase = payload.session.phase || '';
  if (engineBStatusPollMode === 'sim') {
    if (phase === 'abandoned' || phase === 'simulator_complete' || hasSimulatorResult(payload.session)) {
      clearEngineBStatusPolling();
    }
    return;
  }

  if (phase === 'abandoned' || hasInsightResult(payload.session)) {
    clearEngineBStatusPolling();
  }
}

function openEngineBStatusStream() {
  if (!window.EventSource || !engineBStatusPollMode || !state.engineBSession?.session_id) {
    return false;
  }

  if (engineBStatusEventSource) {
    engineBStatusEventSource.close();
    engineBStatusEventSource = null;
  }

  const url = `/api/engineb/events?session_id=${encodeURIComponent(state.engineBSession.session_id)}&mode=${encodeURIComponent(engineBStatusPollMode)}`;
  const source = new EventSource(url);
  engineBStatusEventSource = source;

  source.onmessage = (event) => {
    try {
      const payload = JSON.parse(event.data);
      applyEngineBStatusPayload(payload);
    } catch (error) {
      console.warn('Engine B stream payload parse failed:', error);
    }
  };

  source.onerror = () => {
    source.close();
    engineBStatusEventSource = null;
    if (engineBStatusPollMode) {
      scheduleEngineBStatusPoll(900);
    }
  };

  return true;
}

async function pollEngineBSessionStatus() {
  if (!engineBStatusPollMode) return;

  try {
    const sessionId = state.engineBSession?.session_id || '';
    const query = sessionId ? `?session_id=${encodeURIComponent(sessionId)}` : '';
    const payload = await requestJson(`/api/engineb/status${query}`);
    applyEngineBStatusPayload(payload);
    if (engineBStatusPollMode) {
      scheduleEngineBStatusPoll(1200);
    }
  } catch (error) {
    if (engineBStatusPollMode) {
      scheduleEngineBStatusPoll(1600);
    }
  }
}

export function startEngineBStatusPolling(mode, session) {
  clearEngineBStatusPolling(false);
  engineBStatusPollMode = mode;
  state.engineBSession = session || state.engineBSession;
  renderEngineBSession(state.engineBSession);

  if (!openEngineBStatusStream()) {
    scheduleEngineBStatusPoll(300);
  }
}

export async function submitCurrentB1Answer() {
  const session = state.engineBSession;
  const view = getDecisionView();
  if (!session || !view) return;

  const { question, currentIndex, total } = getCurrentB1Question(session);
  if (!question) return;

  const openInput = document.getElementById('b1-open-input');
  const answer = openInput && !openInput.classList.contains('hidden')
    ? openInput.value.trim()
    : String(view.getSelectedB1Option() || '').trim();

  if (!answer) {
    showToast('请先输入或选择一个回答', 'warning');
    return;
  }

  const submitButton = document.getElementById('b1-submit');
  const isLastQuestion = currentIndex >= total - 1;
  setButtonLoading(submitButton, true, isLastQuestion ? '正在分析…' : '提交中…');

  if (isLastQuestion) {
    view.showB1Processing({
      ...session,
      phase: 'b2_info_fill',
      last_error: '',
    });
  }

  try {
    const payload = await requestJson('/api/engineb/answer', {
      method: 'POST',
      body: JSON.stringify({
        session_id: session.session_id,
        question_id: question.id,
        answer,
      }),
    });

    state.engineBSession = payload.session;
    saveSessionId(payload.session.session_id);

    if (isLastQuestion) {
      startEngineBStatusPolling('b1', payload.session);
    } else {
      renderEngineBSession(payload.session);
    }
  } catch (error) {
    setButtonLoading(submitButton, false);
    showToast(`提交失败: ${error.message}`, 'error');
    renderEngineBSession(session);
  }
}

export async function startSimulatorFlow() {
  if (!state.engineBSession?.session_id) {
    showToast('请先完成决策突破诊断', 'warning');
    return;
  }

  const recheckStatus = String(state.engineBSession?.recheck?.status || '').trim();
  const recheckResult = state.engineBSession?.recheck?.job?.result || {};
  if (['pending', 'running'].includes(recheckStatus)) {
    showToast('Engine A 二次检测还在进行，等最终结论出来后再进入未来模拟。', 'info');
    return;
  }
  if (recheckStatus === 'completed' && recheckResult.is_lagrange_point === true) {
    showToast('二次检测已经确认这是认知拉格朗日点，不需要再启动未来模拟。', 'warning');
    return;
  }

  const view = getDecisionView();
  if (view) {
    view.activateDetectionStep(5);
    view.showSimulatorProcessing({ phase: 'b7_sim_timelines' });
  }

  try {
    const payload = await requestJson('/api/engineb/simulate/start', {
      method: 'POST',
      body: JSON.stringify({ session_id: state.engineBSession.session_id }),
    });
    state.engineBSession = payload.session;
    saveSessionId(payload.session.session_id);
    renderEngineBSession(payload.session);
  } catch (error) {
    showToast(`启动模拟器失败: ${error.message}`, 'error');
    if (view) {
      view.activateDetectionStep(4);
    }
  }
}

export async function submitCurrentSimAnswer() {
  const session = state.engineBSession;
  const view = getDecisionView();
  if (!session || !view) return;

  const { question, currentIndex, total } = getCurrentSimQuestion(session);
  if (!question) return;

  const openInput = document.getElementById('sim-open-input');
  const answer = openInput && !openInput.classList.contains('hidden')
    ? openInput.value.trim()
    : String(view.getSelectedSimOption() || '').trim();

  if (!answer) {
    showToast('请先输入或选择一个回答', 'warning');
    return;
  }

  const submitButton = document.getElementById('sim-submit');
  const isLastQuestion = currentIndex >= total - 1;
  setButtonLoading(submitButton, true, isLastQuestion ? '正在推演…' : '提交中…');

  if (isLastQuestion) {
    view.showSimulatorProcessing({
      ...session,
      phase: 'b7_sim_timelines',
      last_error: '',
    });
  }

  try {
    const payload = await requestJson('/api/engineb/simulate/answer', {
      method: 'POST',
      body: JSON.stringify({
        session_id: session.session_id,
        question_id: question.id,
        answer,
      }),
    });

    state.engineBSession = payload.session;
    saveSessionId(payload.session.session_id);
    if (isLastQuestion) {
      startEngineBStatusPolling('sim', payload.session);
    } else {
      renderEngineBSession(payload.session);
    }
  } catch (error) {
    setButtonLoading(submitButton, false);
    showToast(`提交失败: ${error.message}`, 'error');
    renderEngineBSession(session);
  }
}

export function retrySimulator() {
  clearEngineBStatusPolling();
  return startSimulatorFlow();
}

export function returnToRecommendation() {
  clearEngineBStatusPolling();
  const view = getDecisionView();
  if (!view || !state.engineBSession) return;
  view.activateDetectionStep(4);
  view.renderC1Result(state.engineBSession);
}
