import {
  enhanceSimulatorVisuals,
  renderActionMaps,
  renderCrossroads,
  renderSimulatorSummary,
  renderSurvivalPlan,
  renderTimelineColumn,
} from './timeline-view.js';
import {
  buildLoadingNarrative,
  buildThinkingFeed,
  buildThinkingHeadline,
  compressThinkingLogs,
} from './thinking-log-utils.js';

export function createDecisionFlowView({ document, escapeHtml, shouldIgnoreEnterSubmit }) {
  const dom = {
    detectionQuestionPreview: document.getElementById('detection-question-preview'),
    step1Tensions: document.getElementById('step1-tensions'),
    step1Classifications: document.getElementById('step1-classifications'),
    step1Start: document.getElementById('step1-start'),
    filter1Card: document.getElementById('filter1-card'),
    filter2Card: document.getElementById('filter2-card'),
    filter3Card: document.getElementById('filter3-card'),
    filter1Log: document.getElementById('filter1-log'),
    filter2Log: document.getElementById('filter2-log'),
    filter3Log: document.getElementById('filter3-log'),
    agentsPanel: document.getElementById('agents-panel'),
    agentsGrid: document.getElementById('agents-grid'),
    balanceDisplay: document.getElementById('balance-display'),
    proMoment: document.getElementById('pro-moment'),
    conMoment: document.getElementById('con-moment'),
    balanceDiffValue: document.getElementById('balance-diff-value'),
    detectionResult: document.getElementById('detection-result'),
    abLoopStatus: document.getElementById('ab-loop-status'),
    b1Loading: document.getElementById('b1-loading'),
    b1LoadingStream: document.getElementById('b1-loading-stream'),
    b1CurrentQuestion: document.getElementById('b1-current-question'),
    b1ProgressText: document.getElementById('b1-progress-text'),
    b1Fill: document.getElementById('b1-fill'),
    b1QuestionText: document.getElementById('b1-question-text'),
    b1Options: document.getElementById('b1-options'),
    b1OpenInput: document.getElementById('b1-open-input'),
    b1Submit: document.getElementById('b1-submit'),
    simQuestions: document.getElementById('sim-questions'),
    simLoading: document.getElementById('sim-loading'),
    simLoadingStream: document.getElementById('sim-loading-stream'),
    simResults: document.getElementById('sim-results'),
    simError: document.getElementById('sim-error'),
    simProgressText: document.getElementById('sim-progress-text'),
    simQuestionText: document.getElementById('sim-question-text'),
    simOptions: document.getElementById('sim-options'),
    simOpenInput: document.getElementById('sim-open-input'),
    simSubmit: document.getElementById('sim-submit'),
    simInsight: document.getElementById('sim-insight'),
    simChoiceA: document.getElementById('sim-choice-a'),
    simChoiceB: document.getElementById('sim-choice-b'),
    simActionMaps: document.getElementById('sim-action-maps'),
    simCrossroads: document.getElementById('sim-crossroads'),
    simSurvival: document.getElementById('sim-survival'),
    b2InfoPanel: document.getElementById('b2-info-panel'),
    b2InfoList: document.getElementById('b2-info-list'),
    b3Panel: document.getElementById('b3-panel'),
    b3List: document.getElementById('b3-list'),
    b4Panel: document.getElementById('b4-panel'),
    b4List: document.getElementById('b4-list'),
    b5Panel: document.getElementById('b5-panel'),
    b5Content: document.getElementById('b5-content'),
    c1ProBar: document.getElementById('c1-pro-bar'),
    c1ConBar: document.getElementById('c1-con-bar'),
    c1ProValue: document.getElementById('c1-pro-value'),
    c1ConValue: document.getElementById('c1-con-value'),
    c1Recommendation: document.getElementById('c1-recommendation'),
    c1ActionPlan: document.getElementById('c1-action-plan'),
    c1Reasoning: document.getElementById('c1-reasoning'),
    thinkingSection: document.getElementById('thinking-process-section'),
    thinkingToggle: document.getElementById('thinking-toggle'),
    thinkingTitle: document.getElementById('thinking-title'),
    thinkingCurrent: document.getElementById('thinking-current'),
    thinkingArrow: document.getElementById('thinking-arrow'),
    thinkingLogs: document.getElementById('thinking-logs'),
  };

  let selectedB1Option = '';
  let selectedSimOption = '';
  let simulatorPanelState = '';
  let b1InputComposing = false;
  let simInputComposing = false;
  const renderCache = {
    activeStep: null,
    analysisSignature: '',
    thinkingLogCount: 0,
    thinkingLastEntry: '',
    filterSignatures: {},
    detectionResultSignature: '',
    flashResultSignature: '',
    b1QuestionSignature: '',
    b1ProcessingSignature: '',
    c1Signature: '',
    simQuestionSignature: '',
    simProcessingSignature: '',
    simErrorSignature: '',
    simResultsSignature: '',
  };

  function getDetectionTitle() {
    return document.getElementById('detection-title');
  }

  function getQuestionPreview() {
    return dom.detectionQuestionPreview ? dom.detectionQuestionPreview.textContent || '' : '';
  }

  function setQuestionPreview(text) {
    if (dom.detectionQuestionPreview) {
      dom.detectionQuestionPreview.textContent = text || '';
    }
  }

  function setDetectionTitle(text) {
    const title = getDetectionTitle();
    if (title) title.textContent = text;
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

  function renderUltraBudgetStatus(session, decision) {
    const tier = String(decision?.tier || session?.tier || '').toLowerCase();
    const tierConfig = decision?.tier_config || {};
    const enabled = tier === 'ultra' || tierConfig.enable_ultra_monte_carlo;
    if (!enabled) return '';

    const totalBudget = Number(tierConfig.estimated_tokens || 0);
    const monteBudget = Number(tierConfig.ultra_mc_estimated_tokens || 0);
    const conventionalBudget = totalBudget && monteBudget ? Math.max(0, totalBudget - monteBudget) : 0;
    const monte = session?.simulator_output?.monte_carlo || {};
    const hasMonte = Boolean(monte && typeof monte === 'object' && monte.sample_count);
    const llmCalls = Number(monte.actual_llm_calls || 0);
    const statusText = hasMonte
      ? `已完成：${formatTokenValue(monte.sample_count).replace(' tokens', '')} 次分支采样 / ${monte.persona_count || '--'} 个代理 / LLM委员会成功 ${llmCalls} 次`
      : '尚未生成：需要进入第三幕并完成 B9 最终对比后才会写入 Monte Carlo 结果';

    return `
      <div class="c1-inline-block c1-ultra-budget">
        <div class="c1-inline-title">Ultra 预算状态</div>
        <div class="c1-inline-value">常规链路：${escapeHtml(formatTokenValue(conventionalBudget))} tokens</div>
        <div class="c1-inline-value">Monte Carlo 预算口径（非实耗）：${escapeHtml(formatTokenValue(monteBudget))} tokens</div>
        <div class="c1-inline-value">${escapeHtml(statusText)}</div>
        <div class="c1-inline-value">Ultra 默认会跑真实 LLM 委员会；如果把 CLP_ULTRA_MC_LLM_PANELS 设为 0，才会退成 Pro 式省 token 本地采样。</div>
      </div>
    `;
  }

  function activateDetectionStep(step) {
    if (renderCache.activeStep === step) return;
    document.querySelectorAll('.detection-step').forEach(el => el.classList.remove('active'));
    const stepEl = document.getElementById(`detection-step${step}`);
    if (stepEl) stepEl.classList.add('active');
    renderCache.activeStep = step;
  }

  function resetAnalysisPanel() {
    renderCache.analysisSignature = '';
    if (dom.step1Tensions) {
      dom.step1Tensions.innerHTML = '<div class="tension-analyzing">🧠 系统正在分析问题结构...</div>';
    }
    if (dom.step1Classifications) {
      dom.step1Classifications.querySelectorAll('.classification-fill').forEach(el => {
        el.style.width = '0%';
      });
      dom.step1Classifications.querySelectorAll('.classification-percent').forEach(el => {
        el.textContent = '--';
      });
    }
    if (dom.step1Start) {
      dom.step1Start.disabled = true;
      dom.step1Start.textContent = '分析中...';
    }
    if (dom.thinkingSection) {
      dom.thinkingSection.classList.add('hidden');
      dom.thinkingSection.classList.remove('open');
      dom.thinkingSection.dataset.userCollapsed = '0';
    }
    if (dom.thinkingLogs) {
      dom.thinkingLogs.innerHTML = '';
      dom.thinkingLogs.classList.add('closed');
    }
    if (dom.thinkingTitle) {
      dom.thinkingTitle.textContent = '实时思考流';
    }
    if (dom.thinkingCurrent) {
      dom.thinkingCurrent.textContent = '系统正在拆解这个问题…';
    }
    if (dom.thinkingArrow) {
      dom.thinkingArrow.textContent = '折叠';
    }
    renderCache.thinkingLogCount = 0;
    renderCache.thinkingLastEntry = '';
  }

  function clearRenderCache() {
    renderCache.analysisSignature = '';
    renderCache.filterSignatures = {};
    renderCache.detectionResultSignature = '';
    renderCache.flashResultSignature = '';
    renderCache.b1QuestionSignature = '';
    renderCache.b1ProcessingSignature = '';
    renderCache.c1Signature = '';
    renderCache.simQuestionSignature = '';
    renderCache.simProcessingSignature = '';
    renderCache.simErrorSignature = '';
    renderCache.simResultsSignature = '';
  }

  function toggleThinkingProcess() {
    if (dom.thinkingSection && dom.thinkingLogs) {
      const isOpen = dom.thinkingSection.classList.toggle('open');
      dom.thinkingLogs.classList.toggle('closed', !isOpen);
      dom.thinkingSection.dataset.userCollapsed = isOpen ? '0' : '1';
      if (dom.thinkingToggle) {
        dom.thinkingToggle.setAttribute('aria-expanded', isOpen ? 'true' : 'false');
      }
      if (dom.thinkingArrow) {
        dom.thinkingArrow.textContent = isOpen ? '折叠' : '展开';
      }
    }
  }

  function selectB1Option(target) {
    const optionButton = target && target.closest ? target.closest('.b1-option-btn') : null;
    if (!optionButton) return;
    selectedB1Option = optionButton.dataset.value || '';
    if (dom.b1Options) {
      dom.b1Options.querySelectorAll('.b1-option-btn').forEach(btn => {
        btn.classList.toggle('selected', btn === optionButton);
      });
    }
  }

  function selectSimOption(target) {
    const optionButton = target && target.closest ? target.closest('.sim-option-btn') : null;
    if (!optionButton) return;
    selectedSimOption = optionButton.dataset.value || '';
    if (dom.simOptions) {
      dom.simOptions.querySelectorAll('.sim-option-btn').forEach(btn => {
        btn.classList.toggle('selected', btn === optionButton);
      });
    }
  }

  function getSelectedB1Option() {
    return selectedB1Option;
  }

  function getSelectedSimOption() {
    return selectedSimOption;
  }

  function bindInteractiveInputs({ onB1Submit, onSimSubmit, onB1SubmitCurrent, onSimSubmitCurrent }) {
    if (dom.thinkingToggle && !dom.thinkingToggle.dataset.bound) {
      dom.thinkingToggle.addEventListener('click', toggleThinkingProcess);
      dom.thinkingToggle.dataset.bound = '1';
    }
    if (dom.b1OpenInput && !dom.b1OpenInput.dataset.boundSubmit) {
      dom.b1OpenInput.addEventListener('keydown', (event) => {
        if (event.key === 'Enter' && !shouldIgnoreEnterSubmit(event, b1InputComposing)) {
          onB1Submit(dom.b1OpenInput.value);
        }
      });
      dom.b1OpenInput.addEventListener('compositionstart', () => {
        b1InputComposing = true;
      });
      dom.b1OpenInput.addEventListener('compositionend', () => {
        b1InputComposing = false;
      });
      dom.b1OpenInput.dataset.boundSubmit = '1';
    }

    if (dom.b1Submit && !dom.b1Submit.dataset.boundDirectSubmit) {
      dom.b1Submit.addEventListener('click', () => {
        if (typeof onB1SubmitCurrent === 'function') {
          onB1SubmitCurrent();
        }
      });
      dom.b1Submit.dataset.boundDirectSubmit = '1';
    }

    if (dom.simOpenInput && !dom.simOpenInput.dataset.boundSubmit) {
      dom.simOpenInput.addEventListener('keydown', (event) => {
        if (event.key === 'Enter' && !shouldIgnoreEnterSubmit(event, simInputComposing)) {
          onSimSubmit(dom.simOpenInput.value);
        }
      });
      dom.simOpenInput.addEventListener('compositionstart', () => {
        simInputComposing = true;
      });
      dom.simOpenInput.addEventListener('compositionend', () => {
        simInputComposing = false;
      });
      dom.simOpenInput.dataset.boundSubmit = '1';
    }

    if (dom.simSubmit && !dom.simSubmit.dataset.boundDirectSubmit) {
      dom.simSubmit.addEventListener('click', () => {
        if (typeof onSimSubmitCurrent === 'function') {
          onSimSubmitCurrent();
        }
      });
      dom.simSubmit.dataset.boundDirectSubmit = '1';
    }

  }

  function renderDetectionAnalysis(analysis, hasResult) {
    if (!analysis || !dom.step1Tensions || !dom.step1Classifications || !dom.step1Start) return;
    const tensions = Array.isArray(analysis.tensions) ? analysis.tensions : [];
    const classifications = analysis.classifications || {};
    const classes = [
      Number(classifications.dilemma || 0),
      Number(classifications.info_gap || 0),
      Number(classifications.clp || 0),
    ];
    const signature = JSON.stringify({
      tensions,
      classes,
      summary: analysis.analysis_summary || '',
      hasResult: Boolean(hasResult),
    });
    if (renderCache.analysisSignature === signature) return;
    renderCache.analysisSignature = signature;

    dom.step1Tensions.innerHTML = tensions.map(item => `
      <div class="tension-pair">
        <div class="tension-box pro">${escapeHtml(item.pro || '')}</div>
        <div class="tension-arrow">⚡</div>
        <div class="tension-box con">${escapeHtml(item.con || '')}</div>
      </div>
    `).join('') + (
      analysis.analysis_summary
        ? `<div class="tension-analyzing" style="margin-top:16px;">${escapeHtml(analysis.analysis_summary)}</div>`
        : ''
    );

    dom.step1Classifications.querySelectorAll('.classification-bar').forEach((bar, index) => {
      const fill = bar.querySelector('.classification-fill');
      const percent = bar.querySelector('.classification-percent');
      if (fill) fill.style.width = `${classes[index]}%`;
      if (percent) percent.textContent = `${classes[index]}%`;
    });

    dom.step1Start.disabled = false;
    dom.step1Start.textContent = hasResult ? '查看检测结果' : '开始深度检测';
  }

  function renderThinkingLogs(logs, options = {}) {
    if (!dom.thinkingLogs || !dom.thinkingSection) return;

    const trace = Array.isArray(options?.trace) ? options.trace : [];
    const phase = options?.phase || '';
    const mergedLogs = buildThinkingFeed(logs, trace, { limit: 48 });
    if (!mergedLogs.length) return;

    const groupedLogs = compressThinkingLogs(mergedLogs);
    if (!groupedLogs.length) return;

    dom.thinkingSection.classList.remove('hidden');
    const lastGroup = groupedLogs[groupedLogs.length - 1];
    const lastEntry = `${lastGroup.text}|${lastGroup.count}`;
    if (renderCache.thinkingLogCount === mergedLogs.length && renderCache.thinkingLastEntry === lastEntry) {
      return;
    }
    renderCache.thinkingLogCount = mergedLogs.length;
    renderCache.thinkingLastEntry = lastEntry;

    if (dom.thinkingCurrent) {
      const headline = buildThinkingHeadline(logs, trace, { phase });
      dom.thinkingCurrent.textContent = lastGroup.count > 1
        ? `${headline} · 已重复 ${lastGroup.count} 次`
        : headline;
    }

    // Auto-open on first update if not already open
    if (
      groupedLogs.length > 0
      && !dom.thinkingSection.classList.contains('open')
      && dom.thinkingSection.dataset.userCollapsed !== '1'
    ) {
      toggleThinkingProcess();
    }

    dom.thinkingLogs.innerHTML = '';
    groupedLogs.forEach((item) => {
      const entry = document.createElement('div');
      entry.className = `log-entry is-${item.tone}`;

      const text = document.createElement('span');
      text.className = 'log-entry-text';
      text.textContent = item.text;
      entry.appendChild(text);

      if (item.count > 1) {
        const count = document.createElement('span');
        count.className = 'log-entry-count';
        count.textContent = `×${item.count}`;
        entry.appendChild(count);
      }

      dom.thinkingLogs.appendChild(entry);
    });

    if (!dom.thinkingLogs.classList.contains('closed')) {
      dom.thinkingLogs.scrollTo({
        top: dom.thinkingLogs.scrollHeight,
        behavior: 'smooth',
      });
    }
  }

  function renderLoadingStream(container, trace, phase, fallbackText) {
    if (!container) return;
    const lines = buildLoadingNarrative(trace, phase, { limit: 4 });
    const items = lines.length ? lines : [fallbackText].filter(Boolean);
    container.innerHTML = items.map((line, index) => `
      <div class="loading-stream-line ${index === items.length - 1 ? 'is-current' : ''}">
        ${escapeHtml(line)}
      </div>
    `).join('');
  }

  function renderAgentsEvaluation(details, balanceScore) {
    if (!dom.agentsGrid || !dom.balanceDisplay || !dom.proMoment || !dom.conMoment || !dom.balanceDiffValue) return;
    const agents = dom.agentsGrid.querySelectorAll('.agent-row');
    let proTotal = 0;
    let conTotal = 0;
    const detailMap = new Map((details || []).map(item => [item.stance, item]));

    agents.forEach(agent => {
      const stance = agent.dataset.agent;
      const bar = agent.querySelector('.agent-bar-fill');
      const result = agent.querySelector('.agent-result');
      const detail = detailMap.get(stance);

      if (bar) {
        bar.classList.remove('pro', 'con');
        bar.style.width = '0%';
      }
      if (result) result.textContent = '--';

      if (!detail || !bar || !result) return;

      const direction = detail.lean_direction === '正方' ? 'pro' : 'con';
      const strength = Number(detail.lean_strength || 0);
      bar.classList.add(direction);
      bar.style.width = `${strength}%`;
      result.textContent = `倾向${detail.lean_direction || ''} ${strength}%`;

      if (direction === 'pro') proTotal += strength;
      else conTotal += strength;
    });

    const diff = Number.isFinite(Number(balanceScore)) ? Number(balanceScore) : 0;
    dom.proMoment.textContent = String(proTotal);
    dom.conMoment.textContent = String(conTotal);
    dom.balanceDiffValue.textContent = diff.toFixed(1);
    dom.balanceDisplay.classList.add('active');
  }

  function resetAgentsPanel() {
    if (dom.agentsPanel) dom.agentsPanel.classList.remove('active');
    if (dom.balanceDisplay) dom.balanceDisplay.classList.remove('active');
    if (dom.proMoment) dom.proMoment.textContent = '0';
    if (dom.conMoment) dom.conMoment.textContent = '0';
    if (dom.balanceDiffValue) dom.balanceDiffValue.textContent = '--';
    if (dom.agentsGrid) {
      dom.agentsGrid.querySelectorAll('.agent-row').forEach(agent => {
        const bar = agent.querySelector('.agent-bar-fill');
        const result = agent.querySelector('.agent-result');
        if (bar) {
          bar.classList.remove('pro', 'con');
          bar.style.width = '0%';
        }
        if (result) result.textContent = '--';
      });
    }
  }

  function renderFilterCard(card, logEl, filterState, options = {}) {
    if (!card || !logEl) return;
    const { runningLabel = '运行中...', pendingLabel = '等待中' } = options;
    const progress = card.querySelector('.filter-progress-bar');
    const status = card.querySelector('.filter-status');
    const cacheKey = logEl.id || card.id || Math.random().toString(16).slice(2);
    const signature = JSON.stringify({
      state: filterState || null,
      runningLabel,
      pendingLabel,
    });
    if (renderCache.filterSignatures[cacheKey] === signature) {
      return;
    }
    renderCache.filterSignatures[cacheKey] = signature;

    card.classList.remove('active', 'passed', 'failed');
    if (progress) progress.style.width = '0%';
    if (status) status.textContent = pendingLabel;

    if (!filterState) {
      logEl.innerHTML = '';
      return;
    }

    if (filterState.status === 'running') {
      card.classList.add('active');
      if (progress) progress.style.width = '55%';
      if (status) status.textContent = runningLabel;
    } else if (filterState.status === 'passed') {
      card.classList.add('passed');
      if (progress) progress.style.width = '100%';
      if (status) status.textContent = '✅ 通过';
    } else if (filterState.status === 'failed') {
      card.classList.add('failed');
      if (progress) progress.style.width = '100%';
      if (status) status.textContent = '✗ 淘汰';
    }

    const lines = [];
    if (filterState.summary) lines.push(filterState.summary);
    (filterState.details || []).forEach(item => {
      if (item.label && item.delta !== undefined) {
        lines.push(`${item.label}: 正方${item.pro_strength} vs 反方${item.con_strength} (差值 ${item.delta})`);
      } else if (item.stance) {
        lines.push(`${item.stance}: ${item.lean_direction} ${item.lean_strength}%`);
      } else if (item.variant_id) {
        const suffix = item.balance_passed === true ? '保持平衡' : (item.balance_passed === false ? '失稳' : '处理中');
        lines.push(`${item.label}: ${item.distribution || '--'} / Δ${item.balance_score ?? '--'} / ${suffix}`);
      }
    });
    logEl.innerHTML = lines.map(line => escapeHtml(line)).join('<br>');
  }

  function renderDetectionFilters(detectionJob) {
    const filters = detectionJob && detectionJob.filters ? detectionJob.filters : {};

    renderFilterCard(dom.filter1Card, dom.filter1Log, filters.filter1, { runningLabel: '真实 API 检测中...' });
    renderFilterCard(dom.filter2Card, dom.filter2Log, filters.filter2, { runningLabel: '7 个框架正在并行评估...' });
    renderFilterCard(dom.filter3Card, dom.filter3Log, filters.filter3, { runningLabel: '问题重述稳定性测试中...' });

    const filter2 = filters.filter2 || {};
    const details = Array.isArray(filter2.details) ? filter2.details : [];
    if (detectionJob && (detectionJob.phase === 'filter2' || details.length > 0)) {
      if (dom.agentsPanel) dom.agentsPanel.classList.add('active');
      renderAgentsEvaluation(details, filter2.balance_score);
    } else {
      resetAgentsPanel();
    }
  }

  function renderDetectionResult({ detectionJob, question, setCurrentClp }) {
    if (!dom.detectionResult) return;
    const signature = JSON.stringify({
      status: detectionJob?.status || '',
      error: detectionJob?.error || '',
      result: detectionJob?.result || null,
      question: question || '',
      filters: detectionJob?.filters || null,
    });
    if (renderCache.detectionResultSignature === signature) return;
    renderCache.detectionResultSignature = signature;

    const result = detectionJob && detectionJob.result ? detectionJob.result : null;
    if (!detectionJob) {
      dom.detectionResult.innerHTML = '<div class="tension-analyzing">正在准备检测结果...</div>';
      return;
    }

    if (detectionJob.status === 'failed') {
      dom.detectionResult.innerHTML = `
        <div class="result-passed" style="border-color: rgba(248,102,102,0.35);">
          <div class="result-badge fail">⚠ 检测失败</div>
          <div class="result-title">这次真实检测没有顺利跑完</div>
          <div class="result-question">${escapeHtml(question)}</div>
          <div class="result-meaning">
            <p>${escapeHtml(detectionJob.error || '后端检测发生未知错误')}</p>
          </div>
          <div class="result-actions">
            <button class="result-action" id="detect-report-btn" onclick="downloadFinalReportPdf('detect-report-btn')">📕 完整版 PDF</button>
            <button class="result-action" id="detect-summary-report-btn" onclick="downloadFinalSummaryPdf('detect-summary-report-btn')">📘 AI 总结版 PDF</button>
            <button class="result-action" onclick="startDetection('${escapeHtml(question)}')">🔄 重新检测</button>
            <button class="result-action" onclick="showView('cosmos'); enterExploring();">📚 返回星图</button>
          </div>
        </div>
      `;
      return;
    }

    if (!result) {
      dom.detectionResult.innerHTML = '<div class="tension-analyzing">真实检测仍在运行，请稍候…</div>';
      return;
    }

    if (result.is_lagrange_point) {
      const clp = setCurrentClp(result.clp || {});
      dom.detectionResult.innerHTML = `
        <div class="result-passed">
          <div class="result-badge pass">🔴 确认为认知拉格朗日点</div>
          <div class="result-title">${escapeHtml(clp && clp.id ? clp.id : 'CLP')}</div>
          <div class="result-question">${escapeHtml(question)}</div>
          <div class="result-filters">
            <span class="filter-chip pass">✅ 筛子1：${escapeHtml(detectionJob.filters?.filter1?.summary || '通过')}</span>
            <span class="filter-chip pass">✅ 筛子2：${escapeHtml(detectionJob.filters?.filter2?.summary || '通过')}</span>
            <span class="filter-chip pass">✅ 筛子3：${escapeHtml(detectionJob.filters?.filter3?.summary || '通过')}</span>
          </div>
          <div class="result-meaning">
            <p>${escapeHtml(result.summary || '三层真实筛选后，这个问题仍保持结构性平衡。')}</p>
            <p><strong>平衡精度 ${escapeHtml(String(clp?.balance_precision ?? '--'))}%</strong>。这说明它不是“资料没查够”，而是两边都握有难以被彻底击败的力量。</p>
          </div>
          <div class="result-actions">
            <button class="result-action" id="detect-report-btn" onclick="downloadFinalReportPdf('detect-report-btn')">📕 完整版 PDF</button>
            <button class="result-action" id="detect-summary-report-btn" onclick="downloadFinalSummaryPdf('detect-summary-report-btn')">📘 AI 总结版 PDF</button>
            <button class="result-action" onclick="openForceAnalysis(currentCLP)">🔬 查看力量解剖</button>
            <button class="result-action" onclick="showView('cosmos'); enterExploring();">📚 浏览星图</button>
          </div>
        </div>
      `;
      return;
    }

    const failedAt = result.failed_at || 'filter2';
    const stageLabel = failedAt === 'filter1'
      ? '筛子1'
      : failedAt === 'filter3'
        ? '筛子3'
        : '筛子2';
    const stageSummary = failedAt === 'filter1'
      ? detectionJob.filters?.filter1?.summary
      : failedAt === 'filter3'
        ? detectionJob.filters?.filter3?.summary
        : detectionJob.filters?.filter2?.summary;

    dom.detectionResult.innerHTML = `
      <div class="result-passed" style="border-color: rgba(138,184,255,0.3);">
        <div class="result-badge fail" style="background: var(--console-run);">🟢 不是认知拉格朗日点</div>
        <div class="result-title">这个问题更像“困难但有方向”的问题</div>
        <div class="result-question">${escapeHtml(question)}</div>
        <div class="result-meaning">
          <p>你的问题在<strong>${escapeHtml(stageLabel)}</strong>被真实筛子淘汰。</p>
          <p>${escapeHtml(stageSummary || result.summary || '它没有通过真实筛选。')}</p>
          <p>${escapeHtml(result.summary || '这意味着它更像需要继续拆解的信息型/决策型问题，而不是结构性的永恒僵局。')}</p>
        </div>
        <div class="result-actions">
          <button class="result-action" id="detect-report-btn" onclick="downloadFinalReportPdf('detect-report-btn')">📕 完整版 PDF</button>
          <button class="result-action" id="detect-summary-report-btn" onclick="downloadFinalSummaryPdf('detect-summary-report-btn')">📘 AI 总结版 PDF</button>
          <button class="result-action engine-b-btn" onclick="startEngineB('${escapeHtml(question)}')">🧭 进入决策突破</button>
          <button class="result-action" onclick="startDetection('${escapeHtml(question)}')">🔄 补充条件重新检测</button>
          <button class="result-action" onclick="showView('cosmos'); enterExploring();">📚 浏览星图</button>
        </div>
      </div>
    `;
  }

  function renderFlashDecisionResult(decision) {
    if (!dom.detectionResult) return;
    const signature = JSON.stringify({
      status: decision?.status || '',
      question: decision?.question || '',
      analysis: decision?.analysis || null,
      result: decision?.result || null,
      error: decision?.error || '',
    });
    if (renderCache.flashResultSignature === signature) return;
    renderCache.flashResultSignature = signature;
    const result = decision?.result || {};
    const analysis = decision?.analysis || {};
    const question = decision?.question || getQuestionPreview();
    const typeLabel = {
      dilemma: '困难但可选择',
      info_gap: '信息缺口型',
      clp: '结构性平衡型',
    }[result.decision_type] || '快速判断';

    const confidence = Number(result.confidence || 0);
    const classes = result.classifications || analysis.classifications || {};
    const chips = [
      `两难 ${Number(classes.dilemma || 0)}%`,
      `信息缺口 ${Number(classes.info_gap || 0)}%`,
      `平衡无解 ${Number(classes.clp || 0)}%`,
    ];

    if (decision?.status === 'failed') {
      dom.detectionResult.innerHTML = `
          <div class="result-passed" style="border-color: rgba(248,102,102,0.35);">
          <div class="result-badge fail">⚠ 快速判断失败</div>
          <div class="result-title">这次快速判断没有顺利完成</div>
          <div class="result-question">${escapeHtml(question)}</div>
          <div class="result-meaning">
            <p>${escapeHtml(decision?.error || '后端处理失败')}</p>
          </div>
          <div class="result-actions">
            <button class="result-action" onclick="startDecision('${escapeHtml(question)}', 'quick')">🔄 重试快速判断</button>
            <button class="result-action" onclick="upgradeDecision('deep')">💡 升级到沉思</button>
            <button class="result-action" onclick="showView('cosmos'); enterExploring();">📚 返回星图</button>
          </div>
        </div>
      `;
      return;
    }

    dom.detectionResult.innerHTML = `
      <div class="result-passed" style="border-color: rgba(138,184,255,0.32);">
        <div class="result-badge fail" style="background: rgba(138,184,255,0.16); color: #b7d0ff;">⚡ 快速完成</div>
        <div class="result-title">${escapeHtml(result.recommendation_title || '快速判断已生成')}</div>
        <div class="result-question">${escapeHtml(question)}</div>
        <div class="result-filters">
          <span class="filter-chip pass">${escapeHtml(typeLabel)}</span>
          <span class="filter-chip pass">置信度 ${escapeHtml(String(confidence))}%</span>
          ${chips.map((chip) => `<span class="filter-chip">${escapeHtml(chip)}</span>`).join('')}
        </div>
        <div class="result-meaning">
          <p>${escapeHtml(result.recommendation || analysis.analysis_summary || '系统已经给出一个快速方向判断。')}</p>
          ${result.why ? `<p><strong>为什么：</strong>${escapeHtml(result.why)}</p>` : ''}
          ${result.next_step ? `<p><strong>下一步：</strong>${escapeHtml(result.next_step)}</p>` : ''}
        </div>
        <div class="result-actions">
          <button class="result-action" onclick="upgradeDecision('deep')">💡 升级到沉思</button>
          <button class="result-action" onclick="upgradeDecision('pro')">🔥 升级到 Pro</button>
          <button class="result-action" onclick="showView('cosmos'); enterExploring();">📚 返回星图</button>
        </div>
      </div>
    `;
  }

  function renderB1Questions(session, { setButtonLoading } = {}) {
    const questions = Array.isArray(session?.diagnosis_questions) ? session.diagnosis_questions : [];
    const answers = session?.diagnosis_answers || {};
    const currentIndex = Object.keys(answers).length;
    const total = questions.length;
    if (setButtonLoading) setButtonLoading(dom.b1Submit, false);

    if (dom.b1Loading) dom.b1Loading.style.display = 'none';
    if (dom.b1CurrentQuestion) dom.b1CurrentQuestion.style.display = 'block';

    if (currentIndex >= total) {
      renderCache.b1QuestionSignature = '';
      return { completed: true, currentIndex, total };
    }

    const question = questions[currentIndex];
    const signature = JSON.stringify({
      phase: session?.phase || '',
      index: currentIndex,
      total,
      questionId: question?.id || '',
      prompt: question?.question_text || '',
      options: question?.options || [],
    });
    if (renderCache.b1QuestionSignature === signature) {
      return { completed: false, currentIndex, total };
    }
    renderCache.b1QuestionSignature = signature;
    renderCache.b1ProcessingSignature = '';
    selectedB1Option = '';
    if (dom.b1ProgressText) dom.b1ProgressText.textContent = `问题 ${currentIndex + 1}/${total}`;
    if (dom.b1Fill) dom.b1Fill.style.width = `${(currentIndex / Math.max(total, 1)) * 100}%`;
    if (dom.b1QuestionText) dom.b1QuestionText.textContent = question.question_text || '';

    if (question.options && question.options.length > 0) {
      if (dom.b1Options) {
        dom.b1Options.innerHTML = question.options.map(option => (
          `<button type="button" class="b1-option-btn" data-value="${escapeHtml(option)}" onclick="selectB1Option(this)" onpointerdown="selectB1Option(this)">${escapeHtml(option)}</button>`
        )).join('');
        dom.b1Options.style.display = 'block';
      }
      if (dom.b1OpenInput) {
        dom.b1OpenInput.classList.add('hidden');
        dom.b1OpenInput.value = '';
      }
    } else {
      if (dom.b1Options) {
        dom.b1Options.innerHTML = '';
        dom.b1Options.style.display = 'none';
      }
      if (dom.b1OpenInput) {
        dom.b1OpenInput.classList.remove('hidden');
        dom.b1OpenInput.value = '';
        dom.b1OpenInput.focus();
      }
    }

    if (dom.b1Submit) {
      dom.b1Submit.disabled = false;
      dom.b1Submit.classList.remove('loading');
      if (dom.b1Submit.dataset.origText) {
        dom.b1Submit.textContent = dom.b1Submit.dataset.origText;
      }
      dom.b1Submit.dataset.questionId = question.id || '';
    }
    return { completed: false, currentIndex, total };
  }

  function getProcessingMeta(phase, mode = 'b1') {
    const fallback = mode === 'sim'
      ? { title: '正在生成未来预演...', detail: '请稍候，我正在继续推演两条路径。' }
      : { title: '正在分析你的回答...', detail: '请稍候，我正在梳理卡点与建议。' };

    return {
      b2_info_fill: {
        title: '信息侦探正在补关键事实',
        detail: '我在先补最影响判断的缺口，再继续往下推进。',
      },
      b3_cognitive_unlock: {
        title: '正在切换判断框架',
        detail: '我在尝试从新的视角重新理解这个问题。',
      },
      b4_experience_sim: {
        title: '正在构造经验对照',
        detail: '我在补足“如果换成别人，会怎么选”的参考。',
      },
      b5_emotional_mirror: {
        title: '正在识别情绪干扰',
        detail: '我在看当前的情绪张力如何影响判断。',
      },
      b5_5_alternative: {
        title: '正在寻找第三条路',
        detail: '我在尝试把这个二选一问题拆成一个更可逆的过渡方案。',
      },
      c1_reevaluation: {
        title: '正在汇总结论',
        detail: '我在把前面的线索收拢成建议与行动方案。',
      },
      b7_sim_timelines: {
        title: '正在生成未来时间线',
        detail: '我在推演两个选项各自的顺风局、平稳局和逆风局。',
      },
      b8_sim_coping: {
        title: '正在设计十字路口预案',
        detail: '我在提炼关键检查点和信号灯。',
      },
      b9_sim_comparison: {
        title: '正在生成最终洞察',
        detail: '我在把两条路径压缩成能直接执行的建议。',
      },
      abandoned: {
        title: '这次处理没有顺利完成',
        detail: '上游模型或结构化输出出现异常，这一轮被中断了。',
      },
    }[phase] || fallback;
  }

  function showB1Processing(session) {
    const signature = JSON.stringify({
      phase: session?.phase || '',
      error: session?.last_error || '',
      traceCount: Array.isArray(session?.processing_trace) ? session.processing_trace.length : 0,
    });
    if (renderCache.b1ProcessingSignature === signature) return;
    renderCache.b1ProcessingSignature = signature;
    renderCache.b1QuestionSignature = '';
    const meta = getProcessingMeta(session?.phase || '', 'b1');
    const title = document.getElementById('b1-loading-title');
    const status = document.getElementById('b1-loading-status');
    if (dom.b1Loading) dom.b1Loading.style.display = 'flex';
    if (dom.b1CurrentQuestion) dom.b1CurrentQuestion.style.display = 'none';
    if (title) title.textContent = meta.title;
    if (status) {
      status.textContent = session?.last_error
        || buildThinkingHeadline([], session?.processing_trace || [], { phase: session?.phase || '' })
        || meta.detail;
    }
    renderLoadingStream(
      dom.b1LoadingStream,
      session?.processing_trace || [],
      session?.phase || '',
      meta.detail,
    );
  }

  function renderC1Result(session, { updateTrace, decision } = {}) {
    if (!session) return;
    const signature = JSON.stringify({
      tier: decision?.tier || session?.tier || '',
      tierConfig: decision?.tier_config || {},
      phase: session.phase || '',
      missingInfo: session.missing_info_items || [],
      frames: session.cognitive_frames || [],
      cases: session.experience_cases || [],
      emotional: session.emotional_insight || {},
      valueProfile: session.value_profile || {},
      biases: session.decision_biases || [],
      biasReminder: session.bias_reminder || '',
      alternativePath: session.alternative_path || {},
      pro: session.updated_pro_total ?? '',
      con: session.updated_con_total ?? '',
      recommendation: session.recommendation || '',
      actionPlan: session.action_plan || '',
      reasoning: session.reasoning || '',
      recheckStatus: session.recheck?.status || '',
      recheckResult: session.recheck?.job?.result || null,
      monteCarlo: session.simulator_output?.monte_carlo || null,
    });
    if (renderCache.c1Signature === signature) {
      if (typeof updateTrace === 'function') {
        updateTrace('b1', session);
      }
      return;
    }
    renderCache.c1Signature = signature;
    renderCache.simQuestionSignature = '';
    renderCache.simProcessingSignature = '';
    renderCache.simErrorSignature = '';
    renderCache.simResultsSignature = '';

    const startSimBtn = document.getElementById('engineb-start-sim-btn');
    const resetBtn = document.getElementById('engineb-reset-btn');
    const recheck = session.recheck || {};
    const recheckJob = recheck.job || {};
    const recheckResult = recheckJob.result || {};
    if (startSimBtn) {
      startSimBtn.style.display = '';
      startSimBtn.disabled = false;
      startSimBtn.removeAttribute('title');
      startSimBtn.textContent = '🔮 启动选择模拟器';
      if (recheck.status === 'pending' || recheck.status === 'running') {
        startSimBtn.disabled = true;
        startSimBtn.textContent = '⏳ 二次检测中…';
        startSimBtn.title = '二次检测结束后，你可以手动决定是否进入第三幕';
      } else if (recheck.status === 'completed' && recheckResult.is_lagrange_point === true) {
        startSimBtn.disabled = true;
        startSimBtn.textContent = '🔴 已确认拉格朗日点';
        startSimBtn.title = '这个问题已被确认属于结构性平衡，不需要再启动模拟器';
      }
    }
    if (resetBtn) resetBtn.textContent = '🔄 重新诊断';

    const renderCardLines = (lines) => lines.map(line => `
      <div class="engineb-card-line"><strong>${escapeHtml(line.label)}：</strong>${escapeHtml(line.value || '暂无')}</div>
    `).join('');

    if (session.missing_info_items && session.missing_info_items.length > 0 && dom.b2InfoPanel && dom.b2InfoList) {
      dom.b2InfoPanel.style.display = 'block';
      dom.b2InfoList.innerHTML = session.missing_info_items.map(item => `
        <div class="b2-info-item">
          <div class="b2-info-title">${escapeHtml(item.title || '')}</div>
          <div class="b2-info-content">${escapeHtml(item.content || '')}</div>
          <div class="b2-info-impact">影响力: ${escapeHtml(item.impact || 'medium')}</div>
          ${item.why_critical ? `<div class="b2-info-content">为什么重要：${escapeHtml(item.why_critical)}</div>` : ''}
          ${item.source_suggestion ? `<div class="b2-info-content">建议获取：${escapeHtml(item.source_suggestion)}</div>` : ''}
        </div>
      `).join('');
    } else if (dom.b2InfoPanel && dom.b2InfoList) {
      dom.b2InfoPanel.style.display = 'none';
      dom.b2InfoList.innerHTML = '';
    }

    if (session.cognitive_frames && session.cognitive_frames.length > 0 && dom.b3Panel && dom.b3List) {
      dom.b3Panel.style.display = 'block';
      dom.b3List.innerHTML = session.cognitive_frames.map(frame => `
        <div class="engineb-card">
          <div class="engineb-card-head">
            <div class="engineb-card-title">${escapeHtml(frame.title || '未命名框架')}</div>
            <div class="engineb-card-tag">B3</div>
          </div>
          <div class="engineb-card-body">
            ${renderCardLines([
              { label: '核心洞察', value: frame.core_insight || '' },
              { label: '为什么有用', value: frame.why_it_matters || '' },
              { label: '换个问法', value: frame.reframe_question || '' },
              { label: '现在就做', value: frame.try_now || '' },
              { label: '偏差提醒', value: frame.bias_alert || '' },
            ])}
          </div>
        </div>
      `).join('');
    } else if (dom.b3Panel && dom.b3List) {
      dom.b3Panel.style.display = 'none';
      dom.b3List.innerHTML = '';
    }

    if (session.experience_cases && session.experience_cases.length > 0 && dom.b4Panel && dom.b4List) {
      dom.b4Panel.style.display = 'block';
      dom.b4List.innerHTML = session.experience_cases.map((item, index) => `
        <div class="engineb-card">
          <div class="engineb-card-head">
            <div class="engineb-card-title">${escapeHtml(item.title || `案例 ${index + 1}`)}</div>
            <div class="engineb-card-tag">B4</div>
          </div>
          <div class="engineb-card-body">
            ${renderCardLines([
              { label: '起点处境', value: item.starting_point || '' },
              { label: '当时怎么选', value: item.choice_made || '' },
              { label: '后来发生了什么', value: item.outcome || '' },
              { label: '真正提醒', value: item.lesson || '' },
              { label: '你该怎么借鉴', value: item.transfer_hint || '' },
            ])}
          </div>
        </div>
      `).join('');
    } else if (dom.b4Panel && dom.b4List) {
      dom.b4Panel.style.display = 'none';
      dom.b4List.innerHTML = '';
    }

    const emotional = session.emotional_insight || {};
    const emotions = Array.isArray(emotional.dominant_emotions) ? emotional.dominant_emotions : [];
    if ((emotions.length > 0 || emotional.hidden_need || emotional.decision_distortion || emotional.grounding_prompt || emotional.gentle_reminder) && dom.b5Panel && dom.b5Content) {
      dom.b5Panel.style.display = 'block';
      dom.b5Content.innerHTML = `
        ${emotions.length > 0 ? `
          <div class="engineb-emotion-tags">
            ${emotions.map(item => `
              <span class="engineb-emotion-tag">
                ${escapeHtml(item.emotion || '未命名情绪')}
                ${item.intensity ? ` · ${escapeHtml(item.intensity)}` : ''}
              </span>
            `).join('')}
          </div>
        ` : ''}
        <div class="engineb-emotion-copy">
          ${emotions.map(item => `
            <div class="engineb-card-line"><strong>${escapeHtml(item.emotion || '情绪')}：</strong>${escapeHtml(item.evidence || '暂无依据说明')}</div>
          `).join('')}
          ${emotional.hidden_need ? `<div class="engineb-card-line"><strong>它在保护什么：</strong>${escapeHtml(emotional.hidden_need)}</div>` : ''}
          ${emotional.decision_distortion ? `<div class="engineb-card-line"><strong>可能带来的偏差：</strong>${escapeHtml(emotional.decision_distortion)}</div>` : ''}
          ${emotional.grounding_prompt ? `<div class="engineb-card-line"><strong>稳住自己的提醒：</strong>${escapeHtml(emotional.grounding_prompt)}</div>` : ''}
          ${emotional.gentle_reminder ? `<div class="engineb-card-line"><strong>镜像结论：</strong>${escapeHtml(emotional.gentle_reminder)}</div>` : ''}
          ${emotional.bias_reminder ? `<div class="engineb-card-line"><strong>心理偏差提醒：</strong>${escapeHtml(emotional.bias_reminder)}</div>` : ''}
        </div>
      `;
    } else if (dom.b5Panel && dom.b5Content) {
      dom.b5Panel.style.display = 'none';
      dom.b5Content.innerHTML = '';
    }

    const valueProfile = session.value_profile || {};
    const topValues = Array.isArray(valueProfile.top_values) ? valueProfile.top_values : [];
    const decisionBiases = Array.isArray(session.decision_biases) ? session.decision_biases : [];
    const alternativePath = session.alternative_path || {};

    const parsedPro = Number(session.updated_pro_total);
    const parsedCon = Number(session.updated_con_total);
    const pro = Number.isFinite(parsedPro) && parsedPro >= 0 ? parsedPro : 50;
    const con = Number.isFinite(parsedCon) && parsedCon >= 0 ? parsedCon : 50;
    const placeholderBalance = (
      pro === con
      && (
        String(session.recommendation || '').includes('仍需更多信息')
        || String(session.recommendation || '').includes('先不要把它当成 50:50')
        || String(session.reasoning || '').includes('不代表这个问题天然完全平衡')
        || String(session.reasoning || '').includes('还没形成可靠力矩')
      )
    );

    if (dom.c1ProBar) dom.c1ProBar.style.width = `${pro}%`;
    if (dom.c1ConBar) dom.c1ConBar.style.width = `${con}%`;
    if (dom.c1ProValue) dom.c1ProValue.textContent = placeholderBalance ? '—' : String(pro);
    if (dom.c1ConValue) dom.c1ConValue.textContent = placeholderBalance ? '—' : String(con);
    if (dom.c1Recommendation) {
      dom.c1Recommendation.innerHTML = `
        <div class="c1-rec-label">建议方向</div>
        <div class="c1-rec-value">${escapeHtml(session.recommendation || '分析中...')}</div>
        ${placeholderBalance ? '<div class="c1-rec-helper">当前没有形成可靠力矩，先显示未定状态，不代表它真的永远 50:50。</div>' : ''}
        ${topValues.length > 0 ? `
          <div class="c1-inline-block">
            <div class="c1-inline-title">价值排序</div>
            <div class="c1-inline-value">${escapeHtml(valueProfile.summary || '')}</div>
          </div>
        ` : ''}
      `;
    }
    if (dom.c1ActionPlan) {
      dom.c1ActionPlan.innerHTML = `
        <div class="c1-plan-label">行动方案</div>
        <div class="c1-plan-value">${escapeHtml(session.action_plan || '待分析...')}</div>
      `;
    }
    if (dom.c1Reasoning) {
      dom.c1Reasoning.innerHTML = `
        <div class="c1-reasoning-label">推理过程</div>
        <div class="c1-reasoning-value">${escapeHtml(session.reasoning || '')}</div>
        ${decisionBiases.length > 0 ? `
          <div class="c1-inline-block">
            <div class="c1-inline-title">决策心理偏差</div>
            <div class="c1-bias-chips">
              ${decisionBiases.map((item) => `<span class="c1-bias-chip">${escapeHtml(item.label || item.key || '')}</span>`).join('')}
            </div>
            ${session.bias_reminder ? `<div class="c1-inline-value">${escapeHtml(session.bias_reminder)}</div>` : ''}
          </div>
        ` : ''}
        ${alternativePath.title || alternativePath.summary ? `
          <div class="c1-inline-block c1-third-path">
            <div class="c1-inline-title">第三条路</div>
            ${alternativePath.title ? `<div class="c1-inline-value"><strong>${escapeHtml(alternativePath.title)}</strong></div>` : ''}
            ${alternativePath.summary ? `<div class="c1-inline-value">${escapeHtml(alternativePath.summary)}</div>` : ''}
            ${alternativePath.first_step ? `<div class="c1-inline-value">先做：${escapeHtml(alternativePath.first_step)}</div>` : ''}
          </div>
        ` : ''}
        ${renderUltraBudgetStatus(session, decision)}
      `;
    }

    if (typeof updateTrace === 'function') {
      updateTrace('b1', session);
    }
  }

  function setSimulatorPanelState(nextState) {
    if (simulatorPanelState === nextState) return;
    simulatorPanelState = nextState;
    const panels = {
      loading: dom.simLoading,
      questions: dom.simQuestions,
      results: dom.simResults,
      error: dom.simError,
    };
    Object.entries(panels).forEach(([name, panel]) => {
      if (!panel) return;
      if (name === nextState) {
        panel.style.display = name === 'loading' ? 'flex' : 'block';
      } else {
        panel.style.display = 'none';
      }
    });
  }

  function renderSimulatorQuestionStep(session, { setButtonLoading } = {}) {
    const questions = Array.isArray(session?.sim_questions) ? session.sim_questions : [];
    const answers = session?.sim_answers || {};
    const currentIndex = Object.keys(answers).length;
    const total = questions.length;
    if (setButtonLoading) setButtonLoading(dom.simSubmit, false);

    if (currentIndex >= total) {
      renderCache.simQuestionSignature = '';
      return { completed: true, currentIndex, total };
    }

    const question = questions[currentIndex];
    const signature = JSON.stringify({
      phase: session?.phase || '',
      index: currentIndex,
      total,
      questionId: question?.id || '',
      prompt: question?.question_text || '',
      options: question?.options || [],
    });
    if (renderCache.simQuestionSignature === signature) {
      return { completed: false, currentIndex, total };
    }
    renderCache.simQuestionSignature = signature;
    renderCache.simProcessingSignature = '';
    renderCache.simErrorSignature = '';
    renderCache.simResultsSignature = '';
    selectedSimOption = '';
    setSimulatorPanelState('questions');
    if (dom.simProgressText) dom.simProgressText.textContent = `参数收集 ${currentIndex + 1}/${total}`;
    if (dom.simQuestionText) dom.simQuestionText.textContent = question.question_text || '';

    if (question.options && question.options.length > 0) {
      if (dom.simOptions) {
        dom.simOptions.innerHTML = question.options.map(option => (
          `<button type="button" class="sim-option-btn" data-value="${escapeHtml(option)}" onclick="selectSimOption(this)" onpointerdown="selectSimOption(this)">${escapeHtml(option)}</button>`
        )).join('');
        dom.simOptions.style.display = 'block';
      }
      if (dom.simOpenInput) {
        dom.simOpenInput.classList.add('hidden');
        dom.simOpenInput.value = '';
      }
    } else {
      if (dom.simOptions) {
        dom.simOptions.innerHTML = '';
        dom.simOptions.style.display = 'none';
      }
      if (dom.simOpenInput) {
        dom.simOpenInput.classList.remove('hidden');
        dom.simOpenInput.value = '';
        dom.simOpenInput.focus();
      }
    }

    if (dom.simSubmit) {
      dom.simSubmit.disabled = false;
      dom.simSubmit.classList.remove('loading');
      if (dom.simSubmit.dataset.origText) {
        dom.simSubmit.textContent = dom.simSubmit.dataset.origText;
      }
      dom.simSubmit.dataset.questionId = question.id || '';
    }
    return { completed: false, currentIndex, total };
  }

  function showSimulatorProcessing(session) {
    const signature = JSON.stringify({
      phase: session?.phase || '',
      error: session?.last_error || '',
      traceCount: Array.isArray(session?.processing_trace) ? session.processing_trace.length : 0,
    });
    if (renderCache.simProcessingSignature === signature) return;
    renderCache.simProcessingSignature = signature;
    renderCache.simQuestionSignature = '';
    const meta = getProcessingMeta(session?.phase || '', 'sim');
    setSimulatorPanelState('loading');
    const title = document.getElementById('sim-loading-title');
    const status = document.getElementById('sim-loading-status');
    if (title) title.textContent = meta.title;
    if (status) {
      status.textContent = session?.last_error
        || buildThinkingHeadline([], session?.processing_trace || [], { phase: session?.phase || '' })
        || meta.detail;
    }
    renderLoadingStream(
      dom.simLoadingStream,
      session?.processing_trace || [],
      session?.phase || '',
      meta.detail,
    );
  }

  function showSimulatorError(session) {
    const signature = JSON.stringify({
      phase: session?.phase || '',
      error: session?.last_error || '',
    });
    if (renderCache.simErrorSignature === signature) return;
    renderCache.simErrorSignature = signature;
    renderCache.simQuestionSignature = '';
    renderCache.simProcessingSignature = '';
    setSimulatorPanelState('error');
    const title = document.getElementById('sim-error-title');
    const message = document.getElementById('sim-error-message');
    if (title) title.textContent = '这次处理没有顺利完成';
    if (message) {
      message.textContent = session?.last_error || '这一轮在生成未来预演时中断了，请稍后重试。';
    }
  }

  function renderSimulatorResults(session, { updateTrace, setButtonLoading } = {}) {
    const output = session?.simulator_output;
    if (!output) return;
    const signature = JSON.stringify(output);
    if (renderCache.simResultsSignature === signature) {
      if (typeof updateTrace === 'function') {
        updateTrace('sim', session);
      }
      return;
    }
    renderCache.simResultsSignature = signature;
    renderCache.simQuestionSignature = '';
    renderCache.simProcessingSignature = '';
    renderCache.simErrorSignature = '';
    if (setButtonLoading) setButtonLoading(dom.simSubmit, false);
    setSimulatorPanelState('results');

    if (dom.simInsight) {
      dom.simInsight.innerHTML = renderSimulatorSummary(output, escapeHtml);
    }

    if (dom.simChoiceA) {
      dom.simChoiceA.innerHTML = renderTimelineColumn(output.choice_a, '选项A', escapeHtml);
    }
    if (dom.simChoiceB) {
      dom.simChoiceB.innerHTML = renderTimelineColumn(output.choice_b, '选项B', escapeHtml);
    }

    if (dom.simActionMaps) {
      dom.simActionMaps.innerHTML = renderActionMaps(output, escapeHtml);
    }

    const crossroads = output.crossroads || [];
    if (dom.simCrossroads) {
      dom.simCrossroads.innerHTML = renderCrossroads(crossroads, escapeHtml);
    }

    const survival = output.worst_case_survival_plan;
    if (dom.simSurvival) {
      dom.simSurvival.innerHTML = renderSurvivalPlan(survival, escapeHtml);
    }

    enhanceSimulatorVisuals(output);

    if (typeof updateTrace === 'function') {
      updateTrace('sim', session);
    }
  }

  function resetDetectionUi({ setButtonLoading } = {}) {
    selectedB1Option = '';
    selectedSimOption = '';
    simulatorPanelState = '';
    b1InputComposing = false;
    simInputComposing = false;
    renderCache.activeStep = null;
    renderCache.analysisSignature = '';
    renderCache.thinkingLogCount = 0;
    renderCache.thinkingLastEntry = '';
    renderCache.filterSignatures = {};
    renderCache.detectionResultSignature = '';
    renderCache.flashResultSignature = '';
    renderCache.b1QuestionSignature = '';
    renderCache.b1ProcessingSignature = '';
    renderCache.c1Signature = '';
    renderCache.simQuestionSignature = '';
    renderCache.simProcessingSignature = '';
    renderCache.simErrorSignature = '';
    renderCache.simResultsSignature = '';

    setDetectionTitle('🔬 深度检测');
    setQuestionPreview('');
    if (dom.detectionResult) dom.detectionResult.innerHTML = '';
    resetAnalysisPanel();

    [dom.filter1Card, dom.filter2Card, dom.filter3Card].forEach(card => {
      if (!card) return;
      card.classList.remove('active', 'passed', 'failed');
      const progress = card.querySelector('.filter-progress-bar');
      const status = card.querySelector('.filter-status');
      if (progress) progress.style.width = '0%';
      if (status) status.textContent = '等待中';
    });

    if (dom.filter1Log) dom.filter1Log.innerHTML = '';
    if (dom.filter2Log) dom.filter2Log.innerHTML = '';
    if (dom.filter3Log) dom.filter3Log.innerHTML = '';
    resetAgentsPanel();
    document.querySelectorAll('.detection-step').forEach(el => el.classList.remove('active'));

    if (dom.b1Loading) dom.b1Loading.style.display = 'none';
    if (dom.b1LoadingStream) dom.b1LoadingStream.innerHTML = '';
    if (dom.b1CurrentQuestion) dom.b1CurrentQuestion.style.display = 'block';
    if (dom.b1ProgressText) dom.b1ProgressText.textContent = '问题 1/3';
    if (dom.b1Fill) dom.b1Fill.style.width = '0%';
    if (dom.b1QuestionText) dom.b1QuestionText.textContent = '正在生成追问...';
    if (dom.b1Options) {
      dom.b1Options.innerHTML = '';
      dom.b1Options.style.display = 'block';
    }
    if (dom.b1OpenInput) {
      dom.b1OpenInput.value = '';
      dom.b1OpenInput.classList.add('hidden');
    }
    if (dom.b1Submit) {
      dom.b1Submit.disabled = false;
      dom.b1Submit.classList.remove('loading');
      if (dom.b1Submit.dataset.origText) {
        dom.b1Submit.textContent = dom.b1Submit.dataset.origText;
      }
      dom.b1Submit.dataset.questionId = '';
    }
    if (setButtonLoading) setButtonLoading(dom.b1Submit, false);

    if (dom.simQuestions) dom.simQuestions.style.display = 'none';
    if (dom.simLoading) dom.simLoading.style.display = 'none';
    if (dom.simLoadingStream) dom.simLoadingStream.innerHTML = '';
    if (dom.simResults) dom.simResults.style.display = 'none';
    if (dom.simError) dom.simError.style.display = 'none';
    if (dom.simOpenInput) {
      dom.simOpenInput.value = '';
      dom.simOpenInput.classList.add('hidden');
    }
    if (dom.simSubmit) {
      dom.simSubmit.disabled = false;
      dom.simSubmit.classList.remove('loading');
      if (dom.simSubmit.dataset.origText) {
        dom.simSubmit.textContent = dom.simSubmit.dataset.origText;
      }
      dom.simSubmit.dataset.questionId = '';
    }
    if (setButtonLoading) setButtonLoading(dom.simSubmit, false);

    ['b2-info-list', 'b3-list', 'b4-list', 'b5-content', 'c1-recommendation', 'c1-action-plan', 'c1-reasoning'].forEach(id => {
      const element = document.getElementById(id);
      if (element) element.innerHTML = '';
    });
    if (dom.abLoopStatus) {
      dom.abLoopStatus.innerHTML = '';
      dom.abLoopStatus.classList.add('hidden');
    }
    ['b2-info-panel', 'b3-panel', 'b4-panel', 'b5-panel'].forEach(id => {
      const element = document.getElementById(id);
      if (element) element.style.display = 'none';
    });
    if (dom.thinkingSection) {
      dom.thinkingSection.classList.add('hidden');
      dom.thinkingSection.classList.remove('open');
      dom.thinkingSection.dataset.userCollapsed = '0';
    }
    if (dom.thinkingLogs) {
      dom.thinkingLogs.classList.add('closed');
      dom.thinkingLogs.innerHTML = '';
    }
    if (dom.thinkingTitle) {
      dom.thinkingTitle.textContent = '实时思考流';
    }
    if (dom.thinkingCurrent) {
      dom.thinkingCurrent.textContent = '系统正在拆解这个问题…';
    }
    if (dom.thinkingArrow) {
      dom.thinkingArrow.textContent = '折叠';
    }
  }

  return {
    activateDetectionStep,
    bindInteractiveInputs,
    clearRenderCache,
    getQuestionPreview,
    getSelectedB1Option,
    getSelectedSimOption,
    renderB1Questions,
    showB1Processing,
    renderC1Result,
    renderDetectionAnalysis,
    renderDetectionFilters,
    renderDetectionResult,
    renderFlashDecisionResult,
    renderThinkingLogs,
    renderSimulatorQuestionStep,
    showSimulatorError,
    showSimulatorProcessing,
    renderSimulatorResults,
    resetAnalysisPanel,
    resetDetectionUi,
    selectB1Option,
    selectSimOption,
    setDetectionTitle,
    setQuestionPreview,
    setSimulatorPanelState,
  };
}
