function timelineLabel(type) {
  return {
    tailwind: '顺风局',
    steady: '平稳局',
    headwind: '逆风局',
  }[type] || '时间线';
}

function getChoiceDistribution(choiceData, type) {
  return Number(choiceData?.probability_distribution?.[type]?.percent || 0);
}

function renderTimelineNode(node, escapeHtml) {
  return `
    <div class="timeline-node-card">
      <div class="timeline-node-time">${escapeHtml(node.time || '')}</div>
      ${node.external_state ? `<div class="timeline-node-copy"><strong>外部</strong>${escapeHtml(node.external_state)}</div>` : ''}
      ${node.inner_feeling ? `<div class="timeline-node-copy"><strong>感受</strong>${escapeHtml(node.inner_feeling)}</div>` : ''}
      ${node.key_action ? `<div class="timeline-node-copy"><strong>动作</strong>${escapeHtml(node.key_action)}</div>` : ''}
      ${node.signal ? `<div class="timeline-node-signal">${escapeHtml(node.signal)}</div>` : ''}
    </div>
  `;
}

function renderTimelineTrack(type, timeline, probability, reason, escapeHtml) {
  const nodes = Array.isArray(timeline?.nodes) ? timeline.nodes : [];
  return `
    <article class="timeline-track ${type}">
      <header class="timeline-track-header">
        <div>
          <div class="timeline-track-kicker">${escapeHtml(timelineLabel(type))}</div>
          <div class="timeline-track-title">${escapeHtml(timeline?.title || timelineLabel(type))}</div>
        </div>
        ${Number.isFinite(probability) ? `<div class="timeline-track-probability">${probability}%</div>` : ''}
      </header>
      ${reason ? `<div class="timeline-track-reason">${escapeHtml(reason)}</div>` : ''}
      <div class="timeline-track-line"></div>
      <div class="timeline-track-nodes">
        ${nodes.map((node) => renderTimelineNode(node, escapeHtml)).join('')}
      </div>
    </article>
  `;
}

function renderProbabilityRibbon(choiceData, escapeHtml) {
  const buckets = [
    { key: 'tailwind', label: '顺风', className: 'tailwind' },
    { key: 'steady', label: '平稳', className: 'steady' },
    { key: 'headwind', label: '逆风', className: 'headwind' },
  ];

  return `
    <div class="timeline-probability-ribbon">
      ${buckets.map((bucket) => {
        const value = getChoiceDistribution(choiceData, bucket.key);
        return `
          <div class="timeline-probability-pill ${bucket.className}">
            <span>${escapeHtml(bucket.label)}</span>
            <strong>${value}%</strong>
          </div>
        `;
      }).join('')}
    </div>
  `;
}

function renderMonteCarloSummary(output, escapeHtml) {
  const monte = output?.monte_carlo;
  if (!monte || typeof monte !== 'object') return '';
  const smooth = monte.smooth_prob || {};
  const intervals = monte.confidence_interval || {};
  const heatmap = Array.isArray(monte.disagreement_heatmap) ? monte.disagreement_heatmap.slice(0, 5) : [];
  const branches = Number(monte.sample_count || 0);
  const personas = Number(monte.persona_count || 0);
  const llmCalls = Number(monte.actual_llm_calls || 0);
  const llmPanels = Number(monte.llm_panels_requested || 0);

  const intervalText = (key) => {
    const value = intervals[key];
    return Array.isArray(value) && value.length >= 2 ? `${value[0]}-${value[1]}%` : '--';
  };

  return `
    <section class="sim-summary-card monte-carlo">
      <div class="sim-summary-kicker">Ultra Monte Carlo</div>
      <div class="sim-monte-headline">
        ${branches ? `${branches} 次分支采样` : '分支采样'} · ${personas ? `${personas} 个代理` : '多代理碰撞'}
      </div>
      <div class="sim-prior-pills">
        <div class="sim-prior-pill tailwind"><span>顺风平滑</span><strong>${Number(smooth.optimistic || 0)}%</strong><em>${escapeHtml(intervalText('optimistic'))}</em></div>
        <div class="sim-prior-pill steady"><span>平稳平滑</span><strong>${Number(smooth.baseline || 0)}%</strong><em>${escapeHtml(intervalText('baseline'))}</em></div>
        <div class="sim-prior-pill headwind"><span>逆风平滑</span><strong>${Number(smooth.pessimistic || 0)}%</strong><em>${escapeHtml(intervalText('pessimistic'))}</em></div>
      </div>
      ${heatmap.length ? `
        <div class="sim-monte-heatmap">
          ${heatmap.map((item) => `
            <div class="sim-monte-heat-row">
              <span>${escapeHtml(item.label || item.key || '分歧因子')}</span>
              <strong>${Number(item.avg_score || 0).toFixed(2)}</strong>
            </div>
          `).join('')}
        </div>
      ` : ''}
      <div class="sim-bias-note">
        ${llmCalls > 0
          ? `本轮发起 ${monte.llm_calls_attempted || llmCalls} 次 LLM 委员会调用，成功返回 ${llmCalls} 次。`
          : `本轮没有成功返回 LLM 委员会调用${llmPanels > 0 ? '，已回退为本地采样结果。' : '，因为 CLP_ULTRA_MC_LLM_PANELS=0。'}`}
      </div>
      ${monte.llm_collision_summary ? `<div class="sim-bias-note">${escapeHtml(monte.llm_collision_summary)}</div>` : ''}
      ${Array.isArray(monte.decision_guardrails) && monte.decision_guardrails.length ? `
        <div class="sim-monte-heatmap">
          ${monte.decision_guardrails.slice(0, 4).map((item) => `
            <div class="sim-monte-heat-row">
              <span>${escapeHtml(item)}</span>
              <strong>护栏</strong>
            </div>
          `).join('')}
        </div>
      ` : ''}
    </section>
  `;
}

export function renderTimelineColumn(choiceData, labelFallback, escapeHtml) {
  const choiceName = escapeHtml(choiceData?.choice_name || labelFallback);
  const timelines = choiceData?.timelines || {};
  const probabilityDistribution = choiceData?.probability_distribution || {};
  const order = ['tailwind', 'steady', 'headwind'];

  return `
    <div class="timeline-column-shell">
      <div class="timeline-column-header">
        <div class="timeline-column-label">${choiceName}</div>
        <div class="timeline-column-subtitle">把这条路在脑子里先走一遍</div>
      </div>
      <div class="timeline-column-body">
        ${renderProbabilityRibbon(choiceData, escapeHtml)}
        ${order.map((type) => {
          const timeline = timelines[type];
          if (!timeline) return '';
          const bucket = probabilityDistribution[type] || {};
          const probability = Number(bucket.percent);
          const reason = bucket.reason || '';
          return renderTimelineTrack(type, timeline, probability, reason, escapeHtml);
        }).join('')}
      </div>
    </div>
  `;
}

export function renderSimulatorSummary(output, escapeHtml) {
  const biases = Array.isArray(output?.decision_biases) ? output.decision_biases : [];
  const thirdPath = output?.third_path || {};
  const marketSignals = Array.isArray(output?.market_signals) ? output.market_signals : [];
  const priors = [
    { label: '顺风基线', value: Number(output?.probability_optimistic || 0), className: 'tailwind' },
    { label: '平稳基线', value: Number(output?.probability_baseline || 0), className: 'steady' },
    { label: '逆风基线', value: Number(output?.probability_pessimistic || 0), className: 'headwind' },
  ];

  return `
    <div class="sim-summary-shell">
      <div class="sim-summary-grid">
        <section class="sim-summary-card narrative">
          <div class="sim-summary-kicker">第三幕总览</div>
          ${output?.comparison_summary ? `<div class="sim-compare-summary">${escapeHtml(output.comparison_summary)}</div>` : ''}
          ${output?.final_insight ? `<div class="sim-insight-text">${escapeHtml(output.final_insight)}</div>` : ''}
        </section>
        <section class="sim-summary-card priors">
          <div class="sim-summary-kicker">模拟基线</div>
          <div class="sim-prior-pills">
            ${priors.map((item) => `
              <div class="sim-prior-pill ${item.className}">
                <span>${escapeHtml(item.label)}</span>
                <strong>${item.value}%</strong>
              </div>
            `).join('')}
          </div>
          <div class="sim-regret-grid">
            <div class="sim-regret-card">
              <span>选项 A 后悔分</span>
              <strong>${Number(output?.regret_score_a || 0)}</strong>
            </div>
            <div class="sim-regret-card">
              <span>选项 B 后悔分</span>
              <strong>${Number(output?.regret_score_b || 0)}</strong>
            </div>
          </div>
        </section>
        ${renderMonteCarloSummary(output, escapeHtml)}
        ${biases.length > 0 || output?.bias_reminder ? `
          <section class="sim-summary-card psychology">
            <div class="sim-summary-kicker">心理偏差提醒</div>
            ${biases.length > 0 ? `
              <div class="sim-bias-chips">
                ${biases.map((item) => `<span class="sim-bias-chip">${escapeHtml(item.label || item.key || '')}</span>`).join('')}
              </div>
            ` : ''}
            ${output?.bias_reminder ? `<div class="sim-bias-note">${escapeHtml(output.bias_reminder)}</div>` : ''}
          </section>
        ` : ''}
        ${thirdPath?.title || thirdPath?.summary ? `
          <section class="sim-summary-card third-path">
            <div class="sim-summary-kicker">第三条路</div>
            ${thirdPath.title ? `<div class="sim-third-title">${escapeHtml(thirdPath.title)}</div>` : ''}
            ${thirdPath.summary ? `<div class="sim-third-copy">${escapeHtml(thirdPath.summary)}</div>` : ''}
            ${thirdPath.first_step ? `<div class="sim-third-copy">先做：${escapeHtml(thirdPath.first_step)}</div>` : ''}
          </section>
        ` : ''}
        ${marketSignals.length > 0 ? `
          <section class="sim-summary-card market-signals">
            <div class="sim-summary-kicker">近期市场声音</div>
            <div class="sim-signal-list">
              ${marketSignals.map((item) => `
                <article class="sim-signal-item">
                  <div class="sim-signal-meta">
                    <span class="sim-signal-stance ${escapeHtml(item.stance || 'neutral')}">${escapeHtml(item.stance || 'neutral')}</span>
                    ${item.time || item.captured_at ? `<span>${escapeHtml(item.time || item.captured_at || '')}</span>` : ''}
                  </div>
                  <div class="sim-signal-copy">${escapeHtml(item.summary || '')}</div>
                </article>
              `).join('')}
            </div>
          </section>
        ` : ''}
      </div>
      <div class="sim-chart-shell">
        <div class="sim-summary-kicker">后悔与走势雷达</div>
        <div class="sim-chart-canvas-shell">
          <canvas id="sim-regret-radar" height="220"></canvas>
        </div>
        <div id="sim-regret-fallback" class="sim-regret-fallback"></div>
      </div>
    </div>
  `;
}

export function renderActionMaps(output, escapeHtml) {
  return `
    <div class="timeline-action-map">
      <div class="timeline-section-title">行动地图</div>
      <div class="timeline-action-grid">
        <section class="timeline-action-column">
          <div class="timeline-action-header">${escapeHtml(output.choice_a?.choice_name || '选项A')}</div>
          <ul>${(output.action_map_a || []).map((item) => `<li>${escapeHtml(item)}</li>`).join('')}</ul>
        </section>
        <section class="timeline-action-column">
          <div class="timeline-action-header">${escapeHtml(output.choice_b?.choice_name || '选项B')}</div>
          <ul>${(output.action_map_b || []).map((item) => `<li>${escapeHtml(item)}</li>`).join('')}</ul>
        </section>
      </div>
    </div>
  `;
}

export function renderCrossroads(crossroads, escapeHtml) {
  if (!Array.isArray(crossroads) || crossroads.length === 0) return '';
  return `
    <div class="timeline-crossroads-shell">
      <div class="timeline-section-title">关键岔路口</div>
      <div class="timeline-crossroads-grid">
        ${crossroads.map((item) => `
          <article class="timeline-crossroad-card">
            <div class="timeline-crossroad-time">${escapeHtml(item.time || '')}</div>
            <div class="timeline-crossroad-desc">${escapeHtml(item.description || '')}</div>
            <div class="timeline-crossroad-signals">
              <span class="timeline-signal green">绿灯: ${escapeHtml(item.signals?.green?.signal || '')}</span>
              <span class="timeline-signal yellow">黄灯: ${escapeHtml(item.signals?.yellow?.signal || '')}</span>
              <span class="timeline-signal red">红灯: ${escapeHtml(item.signals?.red?.signal || '')}</span>
            </div>
          </article>
        `).join('')}
      </div>
    </div>
  `;
}

export function renderSurvivalPlan(survival, escapeHtml) {
  if (!survival) return '';
  return `
    <div class="timeline-survival-shell">
      <div class="timeline-section-title">最坏情况生存方案</div>
      <div class="timeline-survival-trigger">触发条件：${escapeHtml(survival.trigger || '')}</div>
      <div class="timeline-survival-grid">
        <div><strong>第1天</strong>${escapeHtml(survival.day_1 || '')}</div>
        <div><strong>第1周</strong>${escapeHtml(survival.week_1 || '')}</div>
        <div><strong>第1个月</strong>${escapeHtml(survival.month_1 || '')}</div>
      </div>
      ${survival.safety_runway ? `<div class="timeline-survival-runway">安全垫：${escapeHtml(survival.safety_runway)}</div>` : ''}
      ${survival.emotional_note ? `<div class="timeline-survival-note">${escapeHtml(survival.emotional_note)}</div>` : ''}
    </div>
  `;
}

function renderRadarFallback(output) {
  const metrics = [
    {
      label: '顺风',
      a: getChoiceDistribution(output?.choice_a, 'tailwind'),
      b: getChoiceDistribution(output?.choice_b, 'tailwind'),
    },
    {
      label: '平稳',
      a: getChoiceDistribution(output?.choice_a, 'steady'),
      b: getChoiceDistribution(output?.choice_b, 'steady'),
    },
    {
      label: '逆风承压',
      a: 100 - getChoiceDistribution(output?.choice_a, 'headwind'),
      b: 100 - getChoiceDistribution(output?.choice_b, 'headwind'),
    },
    {
      label: '后悔可控',
      a: 100 - Number(output?.regret_score_a || 0),
      b: 100 - Number(output?.regret_score_b || 0),
    },
  ];
  return metrics.map((metric) => `
    <div class="sim-regret-fallback-row">
      <div class="sim-regret-fallback-label">${metric.label}</div>
      <div class="sim-regret-fallback-bars">
        <span class="sim-regret-fallback-bar a" style="width:${Math.max(6, metric.a)}%"></span>
        <span class="sim-regret-fallback-bar b" style="width:${Math.max(6, metric.b)}%"></span>
      </div>
    </div>
  `).join('');
}

export function enhanceSimulatorVisuals(output) {
  const canvas = document.getElementById('sim-regret-radar');
  const fallback = document.getElementById('sim-regret-fallback');
  if (!canvas || !fallback) return;

  fallback.innerHTML = renderRadarFallback(output);

  if (!window.Chart || typeof window.Chart !== 'function') {
    canvas.style.display = 'none';
    fallback.style.display = 'grid';
    return;
  }

  canvas.style.display = 'block';
  fallback.style.display = 'none';

  const labels = ['顺风', '平稳', '逆风承压', '后悔可控'];
  const datasetA = [
    getChoiceDistribution(output?.choice_a, 'tailwind'),
    getChoiceDistribution(output?.choice_a, 'steady'),
    100 - getChoiceDistribution(output?.choice_a, 'headwind'),
    100 - Number(output?.regret_score_a || 0),
  ];
  const datasetB = [
    getChoiceDistribution(output?.choice_b, 'tailwind'),
    getChoiceDistribution(output?.choice_b, 'steady'),
    100 - getChoiceDistribution(output?.choice_b, 'headwind'),
    100 - Number(output?.regret_score_b || 0),
  ];

  if (window.__CLP_SIM_RADAR__) {
    window.__CLP_SIM_RADAR__.destroy();
  }

  window.__CLP_SIM_RADAR__ = new window.Chart(canvas, {
    type: 'radar',
    data: {
      labels,
      datasets: [
        {
          label: output?.choice_a?.choice_name || '选项A',
          data: datasetA,
          borderColor: 'rgba(214, 180, 106, 0.95)',
          backgroundColor: 'rgba(214, 180, 106, 0.16)',
          pointBackgroundColor: 'rgba(214, 180, 106, 1)',
          pointRadius: 3,
        },
        {
          label: output?.choice_b?.choice_name || '选项B',
          data: datasetB,
          borderColor: 'rgba(138, 184, 255, 0.95)',
          backgroundColor: 'rgba(138, 184, 255, 0.14)',
          pointBackgroundColor: 'rgba(138, 184, 255, 1)',
          pointRadius: 3,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      animation: false,
      plugins: {
        legend: {
          labels: {
            color: 'rgba(255,255,255,0.82)',
          },
        },
      },
      scales: {
        r: {
          suggestedMin: 0,
          suggestedMax: 100,
          angleLines: { color: 'rgba(255,255,255,0.12)' },
          grid: { color: 'rgba(255,255,255,0.1)' },
          pointLabels: { color: 'rgba(255,255,255,0.72)' },
          ticks: { display: false, backdropColor: 'transparent' },
        },
      },
    },
  });
}
