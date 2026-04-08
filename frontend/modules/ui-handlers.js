/**
 * 认知拉格朗日点 · UI 调度模块 (UI Handlers)
 */

import { state } from '../core/state.js';
import { requestJson, showToast, saveSessionId } from './utils.js';
import { clearEngineBStatusPolling, renderEngineBSession } from './engine-b.js';

function escapeHtml(text) {
  return String(text || '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function formatBodyText(text) {
  return escapeHtml(text).replace(/\n/g, '<br>');
}

export function showView(view) {
  const stateMap = {
    title: 'title',
    home: 'home',
    cosmos: 'exploring',
    detection: 'detection',
    force: 'force',
  };

  state.appView = view;
  state.appState = stateMap[view] || view;
  const views = {
    cosmos: document.getElementById('cosmos'),
    home: document.getElementById('home-entry'),
    detection: document.getElementById('detection-screen'),
    force: document.getElementById('force-analysis-view'),
    title: document.getElementById('title-screen')
  };

  Object.entries(views).forEach(([key, el]) => {
    if (!el) return;
    if (key === 'cosmos') {
      el.style.display = view === 'cosmos' ? 'block' : 'none';
    } else {
      el.classList.toggle('hidden', key !== view);
    }
  });

  // Toggle hints
  document.getElementById('nav-hint')?.classList.toggle('visible', view === 'cosmos');
}

export function openDetail(node) {
  state.selectedNode = node;
  state.appState = 'detail';
  
  const p = document.getElementById('detail-panel');
  const d = node.data;
  const s = node.system;
  const detailForce = document.getElementById('detail-force');
  const detailEngineB = document.getElementById('detail-engineb');
  const isDecisionNode = Boolean(d?.decision_id);

  p.querySelector('.detail-system').textContent = s.name;
  p.querySelector('.detail-system').style.color = `rgb(${s.color.join(',')})`;
  p.querySelector('.detail-title').textContent = d.name;
  p.querySelector('.detail-subtitle').textContent = d.subtitle;
  p.querySelector('.detail-question').innerHTML = formatBodyText(d.question || d.name);
  p.querySelector('.detail-body').innerHTML = d.bodyText
    ? formatBodyText(d.bodyText)
    : (d.body || '');
  
  const [leftT, rightT] = d.tension || ['正方', '反方'];
  p.querySelector('.tension-left').textContent = leftT;
  p.querySelector('.tension-right').textContent = rightT;

  if (detailForce) {
    detailForce.textContent = isDecisionNode ? '📄 导出本次报告' : '🔬 进入力量解剖';
    detailForce.classList.toggle('hidden', false);
  }

  if (detailEngineB) {
    detailEngineB.textContent = isDecisionNode
      ? (d.status === 'completed' ? '👁 打开关联结果' : '🔁 回到这次推演')
      : '🧠 开启深度推演';
  }

  p.classList.add('open');
  document.getElementById('overlay').classList.add('visible');
}

export function closeDetail() {
  state.selectedNode = null;
  state.appState = 'exploring';
  document.getElementById('detail-panel').classList.remove('open');
  document.getElementById('overlay').classList.remove('visible');
  const detailForce = document.getElementById('detail-force');
  const detailEngineB = document.getElementById('detail-engineb');
  if (detailForce) detailForce.textContent = '🔬 进入力量解剖';
  if (detailEngineB) detailEngineB.textContent = '🧠 开启深度推演';
}

export async function startDetection(question) {
  clearEngineBStatusPolling();
  if (state.detectionEventSource) {
    state.detectionEventSource.close();
    state.detectionEventSource = null;
  }

  showView('detection');
  state.decisionFlowView.resetDetectionUi();
  state.decisionFlowView.setDetectionTitle('🔬 双引擎检测');
  state.decisionFlowView.activateDetectionStep(1);
  state.decisionFlowView.setQuestionPreview(question);
  state.detectionJob = null;
  state.detectionJobId = '';
  state.currentCLP = null;

  try {
    const payload = await requestJson('/api/detect/start', {
      method: 'POST',
      body: JSON.stringify({ question })
    });
    const jobId = payload.job?.job_id || payload.job_id || '';
    if (jobId) {
      startDetectionEvents(jobId, question);
    } else {
      showToast('后端没有返回有效的检测任务 ID', 'error');
    }
  } catch (err) {
    showToast('启动检测失败: ' + err.message, 'error');
  }
}

export function startDetectionEvents(jobId, question) {
  if (state.detectionEventSource) {
    state.detectionEventSource.close();
  }
  const eventSource = new EventSource(`/api/detect/events?job_id=${encodeURIComponent(jobId)}`);
  state.detectionEventSource = eventSource;
  
  eventSource.onmessage = (e) => {
    try {
      const data = JSON.parse(e.data);
      const job = data.job;
      if (!job) return;
      state.detectionJob = job;
      state.detectionJobId = job.job_id || jobId;

      // Update Thinking Logs
      if (job.logs) {
        state.decisionFlowView.renderThinkingLogs(job.logs, { phase: job.phase || '' });
      }

      // Update analysis stage
      if (job.analysis) {
        state.decisionFlowView.renderDetectionAnalysis(job.analysis, job.status === 'completed');
      }

      // Update filter stage
      if (job.filters) {
        state.decisionFlowView.activateDetectionStep(2);
        state.decisionFlowView.renderDetectionFilters(job);
      }

      // Check for completion/failure
      if (job.status === 'completed' || job.status === 'failed') {
        eventSource.close();
        state.detectionEventSource = null;
        state.decisionFlowView.activateDetectionStep(3);
        state.decisionFlowView.renderDetectionResult({
          detectionJob: job,
          question,
          setCurrentClp: (clp) => {
            state.currentCLP = clp;
            return clp;
          }
        });
      }
    } catch (err) {
      console.error('SSE Error:', err);
    }
  };

  eventSource.onerror = () => {
    eventSource.close();
    state.detectionEventSource = null;
  };
}

export async function handleStartEngineB(question, source = {}) {
  clearEngineBStatusPolling();
  if (state.detectionEventSource) {
    state.detectionEventSource.close();
    state.detectionEventSource = null;
  }
  closeDetail();
  showView('detection');
  state.decisionFlowView.resetDetectionUi();
  state.decisionFlowView.setDetectionTitle('🧭 决策突破');
  state.decisionFlowView.activateDetectionStep(0);
  state.decisionFlowView.setQuestionPreview(question);

  try {
    const payload = await requestJson('/api/engineb/start', {
      method: 'POST',
      body: JSON.stringify({ question, ...source })
    });
    state.engineBSession = payload.session;
    saveSessionId(payload.session.session_id);
    renderEngineBSession(payload.session);
  } catch (err) {
    showToast('启动决策突破失败: ' + err.message, 'error');
  }
}
