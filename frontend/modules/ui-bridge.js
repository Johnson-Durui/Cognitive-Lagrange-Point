/**
 * 认知拉格朗日点 · UI 桥接模块
 * 负责把模块化函数挂到 window，兼容现有 HTML onclick。
 */

import { state } from '../core/state.js';
import {
  requestJson,
  showToast,
  clearSavedSessionId,
  clearSavedDecisionId,
} from './utils.js';
import {
  clearCurrentDecision,
  restartCurrentDecision,
  returnToDecisionRecommendation,
  startDecisionFlow,
  upgradeCurrentDecision,
  startDecisionSimulator,
  submitCurrentDecisionAnswer,
} from './decision-engine.js';
import { showView, closeDetail, handleStartEngineB, startDetection } from './ui-handlers.js';
import {
  clearEngineBStatusPolling,
  submitCurrentB1Answer,
  startSimulatorFlow,
  submitCurrentSimAnswer,
  retrySimulator,
  returnToRecommendation,
} from './engine-b.js';

function hasDecisionContext() {
  return Boolean(state.currentDecisionId || state.currentDecision?.decision_id);
}

function getReportQuery(explicitOptions = {}) {
  const decisionId = explicitOptions.decision_id || state.currentDecision?.decision_id || '';
  const sessionId = explicitOptions.session_id || state.engineBSession?.session_id || '';
  const jobId = explicitOptions.job_id || state.detectionJobId || state.detectionJob?.job_id || '';
  const params = new URLSearchParams();
  if (decisionId) params.set('decision_id', decisionId);
  if (jobId) params.set('job_id', jobId);
  if (sessionId) params.set('session_id', sessionId);
  return params.toString();
}

function ensureCurrentClpBridge() {
  const descriptor = Object.getOwnPropertyDescriptor(window, 'currentCLP');
  if (descriptor && descriptor.get) return;
  Object.defineProperty(window, 'currentCLP', {
    configurable: true,
    enumerable: false,
    get() {
      return state.currentCLP;
    },
    set(value) {
      state.currentCLP = value;
    },
  });
}

ensureCurrentClpBridge();

window.showView = showView;
window.closeDetail = closeDetail;

window.goHome = () => {
  showView('home');
  window.refreshHomeSurface?.();
};

window.enterExploring = () => {
  showView('cosmos');
};

window.closeDetection = () => {
  clearEngineBStatusPolling();
  if (state.detectionEventSource) {
    state.detectionEventSource.close();
    state.detectionEventSource = null;
  }
  if (state.decisionEventSource) {
    state.decisionEventSource.close();
    state.decisionEventSource = null;
  }
  clearCurrentDecision(true);
  showView('home');
  window.refreshHomeSurface?.();
};

window.openForceAnalysis = (clp = null) => {
  if (clp) {
    state.currentCLP = clp;
  }
  showView('force');
};

window.startDetection = (question) => {
  const text = String(question || '').trim();
  if (!text) {
    showToast('请输入一个要检测的问题', 'warning');
    return;
  }
  startDetection(text);
};

window.startDecision = (question, tier = '') => {
  const text = String(question || '').trim();
  if (!text) {
    showToast('请输入一个要分析的问题', 'warning');
    return;
  }
  startDecisionFlow(text, tier);
};

window.upgradeDecision = (tier = '') => {
  upgradeCurrentDecision(tier);
};

window.startEngineB = (question, source = {}) => {
  const text = String(question || '').trim();
  if (!text) {
    showToast('缺少要进入决策突破的问题', 'warning');
    return;
  }
  handleStartEngineB(text, source);
};

window.resetEngineB = async () => {
  if (!confirm('确定要重置当前决策推演吗？所有进度将丢失。')) return;
  if (hasDecisionContext()) {
    clearSavedSessionId();
    clearSavedDecisionId();
    restartCurrentDecision();
    return;
  }
  try {
    await requestJson('/api/engineb/reset', { method: 'POST' });
    clearEngineBStatusPolling();
    clearSavedSessionId();
    state.engineBSession = null;
    state.decisionFlowView?.resetDetectionUi();
    showView('home');
    showToast('已重置当前决策推演', 'info');
  } catch (error) {
    showToast(`重置失败: ${error.message}`, 'error');
  }
};

window.startSimulator = () => {
  if (hasDecisionContext()) {
    startDecisionSimulator();
    return;
  }
  startSimulatorFlow();
};

window.retrySimulator = () => {
  if (hasDecisionContext()) {
    startDecisionSimulator();
    return;
  }
  retrySimulator();
};

window.returnToRecommendation = () => {
  if (hasDecisionContext()) {
    returnToDecisionRecommendation();
    return;
  }
  returnToRecommendation();
};

window.selectB1Option = (target) => {
  state.decisionFlowView?.selectB1Option(target);
};

window.submitB1Answer = () => {
  if (hasDecisionContext()) {
    submitCurrentDecisionAnswer();
    return;
  }
  submitCurrentB1Answer();
};

window.selectSimOption = (target) => {
  state.decisionFlowView?.selectSimOption(target);
};

window.submitSimAnswer = () => {
  if (hasDecisionContext()) {
    submitCurrentDecisionAnswer();
    return;
  }
  submitCurrentSimAnswer();
};

window.downloadFinalReportPdf = (options = {}) => {
  const normalizedOptions = typeof options === 'object' && options !== null ? options : {};
  const query = getReportQuery(normalizedOptions);
  const decisionId = state.currentDecisionId || state.currentDecision?.decision_id || '';
  if (decisionId && !normalizedOptions.job_id && !normalizedOptions.session_id) {
    window.open(`/api/decision/report?id=${encodeURIComponent(decisionId)}`, '_blank', 'noopener');
    return;
  }
  if (!query) {
    showToast('当前还没有可导出的报告数据', 'warning');
    return;
  }
  window.open(`/api/final-report/pdf?${query}`, '_blank', 'noopener');
};

window.downloadFinalSummaryPdf = (options = {}) => {
  const normalizedOptions = typeof options === 'object' && options !== null ? options : {};
  const query = getReportQuery(normalizedOptions);
  const decisionId = state.currentDecisionId || state.currentDecision?.decision_id || '';
  if (decisionId && !normalizedOptions.job_id && !normalizedOptions.session_id) {
    window.open(`/api/decision/summary-report?id=${encodeURIComponent(decisionId)}`, '_blank', 'noopener');
    return;
  }
  if (!query) {
    showToast('当前还没有可导出的摘要报告数据', 'warning');
    return;
  }
  window.open(`/api/final-report/summary-pdf?${query}`, '_blank', 'noopener');
};

window.downloadFinalReportTxt = window.downloadFinalReportPdf;
