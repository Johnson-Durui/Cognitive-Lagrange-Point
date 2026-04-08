import { PixiStarMap } from '../components/pixi-star-map.js';
import { state } from './state.js';

let canvas;
let ctx;
let pixiApp;
let stars = [];
let gravityParticles = [];
let decisionEventBursts = [];
let lastRenderTime = 0;

const overlayNodeMap = new Map();
const systemLabelMap = new Map();

const STAR_COUNT = 800;
const DECISION_FIELD = {
  center: { x: 0, y: 120 },
  leftWell: { x: -340, y: 40 },
  rightWell: { x: 340, y: 40 },
};

const TIER_STAR_STYLE = {
  quick: { radius: 3.4, color: [120, 186, 255] },
  deep: { radius: 5.1, color: [214, 180, 106] },
  pro: { radius: 6.3, color: [255, 128, 92] },
  ultra: { radius: 7.7, color: [112, 219, 197] },
};

const STATUS_RING_STYLE = {
  running: [138, 184, 255],
  completed: [244, 232, 204],
  failed: [230, 128, 105],
};

const DECISION_PHASE_LABELS = {
  act1: '第一幕 · 结构判断',
  act1_complete: '第一幕完成',
  act2: '第二幕 · 决策突破',
  act2_complete: '第二幕完成',
  act3: '第三幕 · 未来模拟',
  completed: '已完成',
  failed: '已中断',
};

export function initRenderer(canvasElement, useWebGL = false) {
  canvas = canvasElement;
  gravityParticles = [];
  decisionEventBursts = [];
  lastRenderTime = 0;

  if (useWebGL && window.PIXI) {
    pixiApp = new PixiStarMap(canvas);
    state.useWebGL = true;
  } else {
    ctx = canvas.getContext('2d');
    state.useWebGL = false;
    resize();
    initStars();
  }
  window.addEventListener('resize', resize);
}

export function resize() {
  if (!canvas) return;
  canvas.width = window.innerWidth;
  canvas.height = window.innerHeight;
}

function getDecisionEventTarget(anchor = 'center') {
  const layout = getDecisionFieldLayout();
  if (anchor === 'left') return worldToScreen(layout.leftWell.x, layout.leftWell.y);
  if (anchor === 'right') return worldToScreen(layout.rightWell.x, layout.rightWell.y);
  return worldToScreen(layout.center.x, layout.center.y);
}

function queueDecisionEventBurst(detail = {}) {
  const infoType = String(detail.infoType || 'info');
  const anchor = String(detail.anchor || 'center');
  const count = Math.max(8, Math.min(48, Number(detail.count || 24)));
  const target = getDecisionEventTarget(anchor);
  const color = {
    pro: [74, 222, 128],
    con: [248, 113, 113],
    info: [96, 165, 250],
    regret: [250, 204, 21],
  }[infoType] || [255, 255, 255];

  for (let i = 0; i < count; i += 1) {
    decisionEventBursts.push({
      x: target.x + (Math.random() - 0.5) * 18,
      y: target.y + (Math.random() - 0.5) * 18,
      vx: (Math.random() - 0.5) * 3.2,
      vy: (Math.random() - 0.5) * 3.2 - 0.4,
      alpha: 1,
      decay: 0.018 + Math.random() * 0.02,
      size: 1.8 + Math.random() * 2.8,
      color,
    });
  }
  if (decisionEventBursts.length > 320) {
    decisionEventBursts = decisionEventBursts.slice(decisionEventBursts.length - 320);
  }
}

function updateAndDrawDecisionEventBursts() {
  if (!ctx || !decisionEventBursts.length) return;
  decisionEventBursts = decisionEventBursts.filter((particle) => particle.alpha > 0);
  decisionEventBursts.forEach((particle) => {
    particle.x += particle.vx;
    particle.y += particle.vy;
    particle.alpha -= particle.decay;

    const glow = ctx.createRadialGradient(particle.x, particle.y, 0, particle.x, particle.y, particle.size * 5);
    glow.addColorStop(0, `rgba(${particle.color.join(',')},${Math.max(particle.alpha, 0)})`);
    glow.addColorStop(1, `rgba(${particle.color.join(',')},0)`);
    ctx.fillStyle = glow;
    ctx.beginPath();
    ctx.arc(particle.x, particle.y, particle.size * 5, 0, Math.PI * 2);
    ctx.fill();

    ctx.fillStyle = `rgba(${particle.color.join(',')},${Math.max(particle.alpha, 0)})`;
    ctx.beginPath();
    ctx.arc(particle.x, particle.y, particle.size, 0, Math.PI * 2);
    ctx.fill();
  });
}

export function emitDecisionStarEvent(detail = {}) {
  if (state.useWebGL && pixiApp?.emitParticleBurst) {
    const target = getDecisionEventTarget(String(detail.anchor || 'center'));
    pixiApp.emitParticleBurst({
      infoType: detail.infoType || 'info',
      targetX: target.x,
      targetY: target.y,
      count: detail.count || 24,
    });
    return;
  }
  queueDecisionEventBurst(detail);
}

export function initStars() {
  stars = [];
  for (let i = 0; i < STAR_COUNT; i += 1) {
    stars.push({
      x: (Math.random() - 0.5) * 4000,
      y: (Math.random() - 0.5) * 4000,
      size: Math.random() * 1.5 + 0.3,
      brightness: Math.random(),
      twinklePhase: Math.random() * Math.PI * 2,
      twinkleSpeed: 0.005 + Math.random() * 0.02,
      depth: 0.2 + Math.random() * 0.8,
    });
  }
}

export function worldToScreen(wx, wy) {
  const { camera } = state;
  return {
    x: (wx - camera.x) * camera.zoom + window.innerWidth / 2,
    y: (wy - camera.y) * camera.zoom + window.innerHeight / 2,
  };
}

export function screenToWorld(sx, sy) {
  const { camera } = state;
  return {
    x: (sx - window.innerWidth / 2) / camera.zoom + camera.x,
    y: (sy - window.innerHeight / 2) / camera.zoom + camera.y,
  };
}

function clamp(value, min, max) {
  return Math.max(min, Math.min(max, value));
}

function hashString(input) {
  const text = String(input || '');
  let hash = 2166136261;
  for (let i = 0; i < text.length; i += 1) {
    hash ^= text.charCodeAt(i);
    hash = Math.imul(hash, 16777619);
  }
  return Math.abs(hash >>> 0);
}

function getCurrentSession() {
  return state.currentDecision?.engineb_session || state.engineBSession || null;
}

function getCurrentSimulatorOutput() {
  return getCurrentSession()?.simulator_output || null;
}

function getCurrentBalance() {
  const session = getCurrentSession();
  const pro = Number(session?.updated_pro_total);
  const con = Number(session?.updated_con_total);
  if (Number.isFinite(pro) && Number.isFinite(con) && (pro > 0 || con > 0)) {
    return { pro, con };
  }
  return { pro: 50, con: 50 };
}

function getTierLabel(tier) {
  return {
    quick: '⚡ 快速',
    deep: '💡 沉思',
    pro: '🔥 Pro',
    ultra: '🌌 Ultra',
  }[tier] || tier || '未命名档位';
}

function getPhaseLabel(phase) {
  return DECISION_PHASE_LABELS[phase] || phase || '进行中';
}

function formatTimeLabel(value) {
  const raw = String(value || '').trim();
  if (!raw) return '刚刚';
  return raw.replace('T', ' ').slice(0, 16);
}

function truncateText(text, maxLength = 18) {
  const raw = String(text || '').trim();
  if (!raw) return '';
  return raw.length > maxLength ? `${raw.slice(0, maxLength - 1)}…` : raw;
}

function drawRoundedRectPath(x, y, width, height, radius) {
  const r = Math.min(radius, width / 2, height / 2);
  ctx.beginPath();
  if (typeof ctx.roundRect === 'function') {
    ctx.roundRect(x, y, width, height, r);
    return;
  }
  ctx.moveTo(x + r, y);
  ctx.arcTo(x + width, y, x + width, y + height, r);
  ctx.arcTo(x + width, y + height, x, y + height, r);
  ctx.arcTo(x, y + height, x, y, r);
  ctx.arcTo(x, y, x + width, y, r);
}

function getSystemLabelsRoot() {
  return document.getElementById('system-labels');
}

function getCosmosHudRoot() {
  return document.getElementById('cosmos-hud');
}

function clearSystemLabels() {
  const root = getSystemLabelsRoot();
  if (!root) return;
  root.classList.remove('visible');
  root.style.display = 'none';
  systemLabelMap.forEach((element) => {
    element.style.opacity = '0';
  });
}

function upsertSystemLabel(id, config) {
  const root = getSystemLabelsRoot();
  if (!root) return;

  let element = systemLabelMap.get(id);
  if (!element) {
    element = document.createElement('div');
    element.className = 'system-label';
    element.innerHTML = `
      <div class="system-label-name"></div>
      <div class="system-label-en"></div>
    `;
    root.appendChild(element);
    systemLabelMap.set(id, element);
  }

  const nameEl = element.querySelector('.system-label-name');
  const subEl = element.querySelector('.system-label-en');
  if (nameEl) nameEl.textContent = config.name || '';
  if (subEl) subEl.textContent = config.subtitle || '';
  element.className = `system-label ${config.className || ''}`.trim();
  element.style.left = `${config.x}px`;
  element.style.top = `${config.y}px`;
  element.style.opacity = String(config.opacity ?? 1);
  element.style.display = config.visible === false ? 'none' : 'block';
  element.style.color = config.color || '';
}

function normalizeTierForHud(tier) {
  if (tier === 'flash') return 'quick';
  if (tier === 'panorama') return 'ultra';
  if (tier === 'quick' || tier === 'deep' || tier === 'pro' || tier === 'ultra') return tier;
  return 'deep';
}

function renderCosmosHud() {
  const root = getCosmosHudRoot();
  if (!root) return;

  const allowHud = ['exploring', 'detail'].includes(state.appState);
  if (!allowHud) {
    root.classList.add('hidden');
    return;
  }

  const titleEl = document.getElementById('cosmos-hud-title');
  const metaEl = document.getElementById('cosmos-hud-meta');
  const chipsEl = document.getElementById('cosmos-hud-chips');
  const balanceLabelEl = document.getElementById('cosmos-hud-balance-label');
  const proFillEl = document.getElementById('cosmos-hud-pro-fill');
  const conFillEl = document.getElementById('cosmos-hud-con-fill');
  const phaseLabelEl = document.getElementById('cosmos-hud-phase-label');
  const phaseFillEl = document.getElementById('cosmos-hud-phase-fill');
  if (!titleEl || !metaEl || !chipsEl || !balanceLabelEl || !proFillEl || !conFillEl || !phaseLabelEl || !phaseFillEl) return;

  const currentQuestion = getCurrentDecisionQuestion();
  const current = state.currentDecision || null;
  const history = Array.isArray(state.decisionHistory) ? state.decisionHistory : [];
  if (!currentQuestion && history.length === 0) {
    root.classList.add('hidden');
    return;
  }

  const counts = { quick: 0, deep: 0, pro: 0, ultra: 0 };
  const seenIds = new Set();
  history.forEach((item) => {
    if (!item?.decision_id || seenIds.has(item.decision_id)) return;
    seenIds.add(item.decision_id);
    counts[normalizeTierForHud(item.tier)] += 1;
  });
  if (current?.decision_id && !seenIds.has(current.decision_id)) {
    counts[normalizeTierForHud(current.tier)] += 1;
  }

  const summary = getCurrentDecisionSummary();
  const { pro, con } = getCurrentBalance();
  const total = Math.max(1, pro + con);
  const proPercent = clamp((pro / total) * 100, 0, 100);
  const conPercent = clamp((con / total) * 100, 0, 100);
  const leanGap = Math.abs(Math.round(proPercent - conPercent));
  const leanText = leanGap <= 6
    ? '结构平衡'
    : (proPercent > conPercent ? '更偏正向' : '更偏反向');
  const phaseProgress = {
    act1: 18,
    act1_complete: 32,
    act2: 54,
    act2_complete: 68,
    act3: 86,
    completed: 100,
    failed: 100,
  }[current?.phase || 'act1'] || 24;
  const simulatorOutput = getCurrentSimulatorOutput();
  const simulatorCopy = simulatorOutput
    ? `${getChoiceName(simulatorOutput, 'choice_a', '选项 A')} / ${getChoiceName(simulatorOutput, 'choice_b', '选项 B')}`
    : '未来模拟未激活';

  titleEl.textContent = truncateText(currentQuestion || '个人决策星图', 26);
  metaEl.textContent = `${current ? getPhaseLabel(current.phase) : '历史轨迹'} · ${truncateText(summary || '拖拽查看历史决策轨迹，点击节点继续或回看。', 48)}`;
  balanceLabelEl.textContent = `力量平衡 · ${leanText} · 正 ${Math.round(pro)} / 反 ${Math.round(con)}`;
  proFillEl.style.width = `${proPercent}%`;
  conFillEl.style.width = `${conPercent}%`;
  phaseLabelEl.textContent = current ? getPhaseLabel(current.phase) : '历史轨迹整理中';
  phaseFillEl.style.width = `${phaseProgress}%`;
  chipsEl.innerHTML = [
    current ? `<span class="cosmos-hud-chip ${normalizeTierForHud(current.tier)}"><strong>${getTierLabel(current.tier)}</strong></span>` : '',
    `<span class="cosmos-hud-chip phase"><strong>历史</strong>${history.length} 条</span>`,
    `<span class="cosmos-hud-chip quick"><strong>快速</strong>${counts.quick}</span>`,
    `<span class="cosmos-hud-chip deep"><strong>沉思</strong>${counts.deep}</span>`,
    `<span class="cosmos-hud-chip pro"><strong>Pro</strong>${counts.pro}</span>`,
    `<span class="cosmos-hud-chip ultra"><strong>Ultra</strong>${counts.ultra}</span>`,
    `<span class="cosmos-hud-chip phase"><strong>模拟</strong>${truncateText(simulatorCopy, 16)}</span>`,
  ].filter(Boolean).join('');

  root.classList.remove('hidden');
}

function renderSystemLabels() {
  const root = getSystemLabelsRoot();
  if (!root) return;

  const canvasVisible = canvas && canvas.style.display !== 'none';
  const allowLabels = canvasVisible && ['exploring', 'detail'].includes(state.appState);
  if (!allowLabels) {
    clearSystemLabels();
    return;
  }

  root.style.display = 'block';
  root.classList.add('visible');

  const activeIds = new Set();
  const labelOpacity = clamp((state.camera.zoom - 0.22) * 1.35, 0, 0.9);

  state.systems.forEach((system) => {
    if (!system?.position) return;
    const screen = worldToScreen(system.position.x, system.position.y - 240);
    const onscreen = screen.x > -180 && screen.x < window.innerWidth + 180 && screen.y > -80 && screen.y < window.innerHeight + 80;
    if (!onscreen) return;
    const id = `system:${system.id}`;
    activeIds.add(id);
    upsertSystemLabel(id, {
      name: system.name || '',
      subtitle: system.nameEn || '',
      x: screen.x,
      y: screen.y,
      opacity: labelOpacity,
      className: 'constellation-system-label',
      color: `rgba(${(system.color || [255, 255, 255]).join(',')},0.88)`,
    });
  });

  const layout = getDecisionFieldLayout();
  const currentQuestion = getCurrentDecisionQuestion();
  if (currentQuestion || (state.decisionHistory || []).length) {
    const center = worldToScreen(layout.center.x, layout.center.y - 168);
    const left = worldToScreen(layout.leftWell.x - 126, layout.leftWell.y - 82);
    const right = worldToScreen(layout.rightWell.x + 126, layout.rightWell.y - 82);
    const output = getCurrentSimulatorOutput();
    const choiceAName = output?.choice_a?.choice_name || '正向路径';
    const choiceBName = output?.choice_b?.choice_name || '反向路径';
    const choiceASummary = output?.choice_a
      ? truncateText(summarizeProbabilities(output.choice_a?.probability_distribution), 22)
      : '力量锚点';
    const choiceBSummary = output?.choice_b
      ? truncateText(summarizeProbabilities(output.choice_b?.probability_distribution), 22)
      : '力量锚点';

    [
      {
        id: 'decision:center',
        name: truncateText(currentQuestion || '决策星座', 14),
        subtitle: getCurrentDecisionSummary() ? truncateText(getCurrentDecisionSummary(), 18) : '当前推演',
        x: center.x,
        y: center.y,
        className: 'decision-label center-label',
        color: 'rgba(244,232,204,0.9)',
      },
      {
        id: 'decision:left',
        name: truncateText(choiceAName, 12),
        subtitle: output ? `选项 A · ${choiceASummary}` : '力量锚点',
        x: left.x,
        y: left.y,
        className: 'decision-label well-label left-well-label',
        color: 'rgba(214,180,106,0.88)',
      },
      {
        id: 'decision:right',
        name: truncateText(choiceBName, 12),
        subtitle: output ? `选项 B · ${choiceBSummary}` : '力量锚点',
        x: right.x,
        y: right.y,
        className: 'decision-label well-label right-well-label',
        color: 'rgba(138,184,255,0.88)',
      },
    ].forEach((label) => {
      activeIds.add(label.id);
      upsertSystemLabel(label.id, {
        ...label,
        opacity: clamp(labelOpacity * 1.05, 0.18, 0.95),
      });
    });
  }

  systemLabelMap.forEach((element, id) => {
    if (!activeIds.has(id)) {
      element.style.display = 'none';
      element.style.opacity = '0';
    }
  });
}

function getDecisionFieldLayout() {
  return DECISION_FIELD;
}

function getTierStyle(tier) {
  return TIER_STAR_STYLE[normalizeTierForHud(tier)] || TIER_STAR_STYLE.deep;
}

function getStatusRing(status) {
  return STATUS_RING_STYLE[status] || [188, 198, 225];
}

function getCurrentDecisionQuestion() {
  return String(
    state.currentDecision?.question
      || getCurrentSession()?.original_question
      || state.decisionHistory?.[0]?.question
      || ''
  ).trim();
}

function getCurrentDecisionSummary() {
  const current = state.currentDecision || {};
  const session = current.engineb_session || {};
  const result = current.result || {};
  return String(
    session.recommendation
      || result.summary
      || current.status_text
      || ''
  ).trim();
}

function getDecisionBodyText(item, { isCurrent = false } = {}) {
  const lines = [];
  lines.push(`思考深度：${getTierLabel(item.tier)}`);
  lines.push(`当前阶段：${getPhaseLabel(item.phase)}`);
  lines.push(`任务状态：${item.status === 'completed' ? '已完成' : item.status === 'failed' ? '已失败' : '进行中'}`);
  if (item.updated_at || item.created_at) {
    lines.push(`最近更新时间：${formatTimeLabel(item.updated_at || item.created_at)}`);
  }
  if (item.linked_detection_job_id) {
    lines.push(`检测任务：${item.linked_detection_job_id}`);
  }
  if (item.linked_engineb_session_id) {
    lines.push(`关联决策会话：${item.linked_engineb_session_id}`);
  }
  const summary = isCurrent ? getCurrentDecisionSummary() : '';
  if (summary) {
    lines.push('');
    lines.push(`当前摘要：${summary}`);
  }
  return lines.join('\n');
}

function getChoiceName(output, key, fallback) {
  return String(output?.[key]?.choice_name || fallback || '').trim() || fallback;
}

function summarizeProbabilities(probabilityDistribution) {
  const distribution = probabilityDistribution || {};
  const pieces = [
    ['顺风', distribution.tailwind?.percent],
    ['平稳', distribution.steady?.percent],
    ['逆风', distribution.headwind?.percent],
  ].filter((item) => Number.isFinite(Number(item[1])));

  if (!pieces.length) return '概率分布仍在生成';
  return pieces.map(([label, percent]) => `${label} ${percent}%`).join(' / ');
}

function getTimelineByType(choiceData, preferredType = 'steady') {
  const timelines = choiceData?.timelines || {};
  return timelines[preferredType]
    || timelines.steady
    || timelines.tailwind
    || timelines.headwind
    || null;
}

function quadraticPoint(sourceX, sourceY, direction, trackIndex, t) {
  const spread = 120 + trackIndex * 48;
  const endX = sourceX + direction * (220 + trackIndex * 44);
  const endY = sourceY - 90 + trackIndex * 80;
  const controlX = sourceX + direction * spread;
  const controlY = sourceY - 124 - trackIndex * 24;
  return {
    x: (1 - t) * (1 - t) * sourceX + 2 * (1 - t) * t * controlX + t * t * endX,
    y: (1 - t) * (1 - t) * sourceY + 2 * (1 - t) * t * controlY + t * t * endY,
  };
}

function ensureOverlayNode(id) {
  if (!overlayNodeMap.has(id)) {
    overlayNodeMap.set(id, {
      id,
      system: {
        id: 'decision_constellation',
        name: '决策星座',
        color: [214, 180, 106],
      },
      data: {},
      wx: 0,
      wy: 0,
      sx: 0,
      sy: 0,
      hovered: false,
      glowIntensity: 0,
      pulsePhase: Math.random() * Math.PI * 2,
      hitRadius: 18,
      visualRadius: 6,
      visualColor: [214, 180, 106],
      statusColor: [244, 232, 204],
      isOverlay: true,
    });
  }
  return overlayNodeMap.get(id);
}

function updateOverlayNodePosition(node, wx, wy) {
  node.wx = wx;
  node.wy = wy;
  const screen = worldToScreen(wx, wy);
  node.sx = screen.x;
  node.sy = screen.y;
  return screen;
}

function appendChoiceOverlayNodes({ nodes, links, activeIds, layout }) {
  const output = getCurrentSimulatorOutput();
  const decisionId = state.currentDecisionId || state.currentDecision?.decision_id || '';
  if (!output || !decisionId) return;

  const entries = [
    {
      key: 'choice_a',
      side: 'left',
      labelFallback: '选项 A',
      color: [214, 180, 106],
      source: layout.leftWell,
      direction: -1,
    },
    {
      key: 'choice_b',
      side: 'right',
      labelFallback: '选项 B',
      color: [138, 184, 255],
      source: layout.rightWell,
      direction: 1,
    },
  ];

  entries.forEach((entry) => {
    const choiceData = output?.[entry.key];
    if (!choiceData) return;
    const choiceName = getChoiceName(output, entry.key, entry.labelFallback);
    const choiceId = `choice-anchor:${decisionId}:${entry.key}`;
    const anchorNode = ensureOverlayNode(choiceId);
    const steadyTimeline = getTimelineByType(choiceData, 'steady');
    const summary = summarizeProbabilities(choiceData.probability_distribution);
    const steadyReason = String(choiceData?.probability_distribution?.steady?.reason || '').trim();

    anchorNode.system = {
      id: 'decision_future',
      name: '未来锚点',
      color: entry.color,
    };
    anchorNode.data = {
      name: truncateText(choiceName, 16),
      subtitle: '未来锚点',
      question: `${choiceName} 这条路的未来轮廓`,
      bodyText: [
        `主线：${steadyTimeline?.title || '平稳局'}`,
        `概率：${summary}`,
        steadyReason ? `理由：${steadyReason}` : '',
      ].filter(Boolean).join('\n'),
      tension: [choiceName, '未来锚点'],
      decision_id: decisionId,
      detailType: 'choice-anchor',
      status: state.currentDecision?.status || 'running',
      tooltipSubtitle: `${entry.side === 'left' ? '左侧' : '右侧'}未来锚点`,
    };
    anchorNode.visualRadius = 7.2;
    anchorNode.hitRadius = 20;
    anchorNode.visualColor = entry.color;
    anchorNode.statusColor = entry.color;
    anchorNode.isCurrent = false;
    updateOverlayNodePosition(anchorNode, entry.source.x, entry.source.y - 54);
    nodes.push(anchorNode);
    activeIds.add(choiceId);

    const milestoneNodes = Array.isArray(steadyTimeline?.nodes) ? steadyTimeline.nodes.slice(0, 6) : [];
    let previousNode = anchorNode;
    milestoneNodes.forEach((milestone, index) => {
      const t = (index + 1) / (milestoneNodes.length + 1);
      const point = quadraticPoint(entry.source.x, layout.center.y + 12, entry.direction, 1, t);
      const milestoneId = `timeline-milestone:${decisionId}:${entry.key}:${index}`;
      const milestoneNode = ensureOverlayNode(milestoneId);
      milestoneNode.system = {
        id: 'decision_timeline',
        name: choiceName,
        color: entry.color,
      };
      milestoneNode.data = {
        name: milestone?.time || `节点 ${index + 1}`,
        subtitle: `${choiceName} · 平稳局`,
        question: `${choiceName} 在 ${milestone?.time || `节点 ${index + 1}`} 会发生什么？`,
        bodyText: [
          milestone?.external_state ? `外部：${milestone.external_state}` : '',
          milestone?.inner_feeling ? `感受：${milestone.inner_feeling}` : '',
          milestone?.key_action ? `动作：${milestone.key_action}` : '',
          milestone?.signal ? `信号：${milestone.signal}` : '',
        ].filter(Boolean).join('\n'),
        tension: [choiceName, milestone?.time || `节点 ${index + 1}`],
        decision_id: decisionId,
        detailType: 'timeline-milestone',
        status: state.currentDecision?.status || 'running',
        tooltipSubtitle: `${choiceName} · ${milestone?.time || `节点 ${index + 1}`}`,
      };
      milestoneNode.visualRadius = 4 + index * 0.28;
      milestoneNode.hitRadius = 18;
      milestoneNode.visualColor = entry.color;
      milestoneNode.statusColor = [244, 232, 204];
      milestoneNode.isCurrent = false;
      updateOverlayNodePosition(milestoneNode, point.x, point.y);
      nodes.push(milestoneNode);
      activeIds.add(milestoneId);

      links.push({
        from: previousNode,
        to: milestoneNode,
        alpha: 0.12,
      });
      previousNode = milestoneNode;
    });
  });
}

function buildDecisionConstellation(time) {
  const layout = getDecisionFieldLayout();
  const nodes = [];
  const links = [];
  const activeIds = new Set();
  const seenHistory = new Set();
  const historyRows = Array.isArray(state.decisionHistory) ? state.decisionHistory.slice(0, 10) : [];
  const current = state.currentDecision && state.currentDecision.decision_id
    ? state.currentDecision
    : null;
  if (current?.decision_id) {
    seenHistory.add(current.decision_id);
  }

  if (current) {
    const id = `decision-current:${current.decision_id}`;
    const node = ensureOverlayNode(id);
    const tierStyle = getTierStyle(current.tier);
    node.system = {
      id: 'decision_constellation',
      name: '当前推演',
      color: tierStyle.color,
    };
    node.data = {
      name: truncateText(current.question || '当前推演', 22),
      subtitle: `${getTierLabel(current.tier)} · ${getPhaseLabel(current.phase)}`,
      question: current.question || '当前推演',
      bodyText: getDecisionBodyText(current, { isCurrent: true }),
      tension: ['当前推演', getPhaseLabel(current.phase)],
      decision_id: current.decision_id,
      detailType: 'current-decision',
      tier: current.tier,
      status: current.status,
      phase: current.phase,
      tooltipSubtitle: '当前推演',
    };
    node.visualRadius = tierStyle.radius * 2.15;
    node.hitRadius = 28;
    node.visualColor = tierStyle.color;
    node.statusColor = getStatusRing(current.status);
    node.isCurrent = true;
    updateOverlayNodePosition(node, layout.center.x, layout.center.y);
    nodes.push(node);
    activeIds.add(id);
  }

  historyRows.forEach((item, index) => {
    if (!item?.decision_id || seenHistory.has(item.decision_id)) return;
    seenHistory.add(item.decision_id);

    const id = `decision-history:${item.decision_id}`;
    const node = ensureOverlayNode(id);
    const tierStyle = getTierStyle(item.tier);
    const hash = hashString(item.decision_id || item.question || index);
    const orbit = 250
      + Math.floor(index / 4) * 84
      + (normalizeTierForHud(item.tier) === 'ultra' ? 46 : normalizeTierForHud(item.tier) === 'pro' ? 28 : normalizeTierForHud(item.tier) === 'deep' ? 18 : 0);
    const ellipseY = 0.62 + ((hash % 7) * 0.03);
    const angle = ((hash % 360) / 180) * Math.PI + time * (0.026 + (hash % 9) * 0.0015) * (hash % 2 === 0 ? 1 : -1);
    const wobble = Math.sin(time * 0.7 + index * 0.8) * (8 + (hash % 5));
    const wx = layout.center.x + Math.cos(angle) * orbit;
    const wy = layout.center.y + Math.sin(angle) * orbit * ellipseY + wobble;

    node.system = {
      id: 'decision_constellation',
      name: '决策星座',
      color: tierStyle.color,
    };
    node.data = {
      name: truncateText(item.question || `决策 ${index + 1}`, 18),
      subtitle: `${getTierLabel(item.tier)} · ${getPhaseLabel(item.phase)}`,
      question: item.question || '未命名问题',
      bodyText: getDecisionBodyText(item),
      tension: [getTierLabel(item.tier), getPhaseLabel(item.phase)],
      decision_id: item.decision_id,
      detailType: 'decision-history',
      tier: item.tier,
      status: item.status,
      phase: item.phase,
      tooltipSubtitle: item.status === 'completed' ? '已完成的决策' : '可恢复的决策',
    };
    node.visualRadius = tierStyle.radius + (item.status === 'completed' ? 1.4 : 0.5);
    node.hitRadius = Math.max(18, node.visualRadius * 3.1);
    node.visualColor = tierStyle.color;
    node.statusColor = getStatusRing(item.status);
    node.isCurrent = false;
    updateOverlayNodePosition(node, wx, wy);
    nodes.push(node);
    activeIds.add(id);
  });

  const currentNode = nodes.find((node) => node.isCurrent);
  const historyNodes = nodes.filter((node) => !node.isCurrent);
  if (currentNode) {
    historyNodes.slice(0, 6).forEach((node) => {
      links.push({
        from: currentNode,
        to: node,
        alpha: node.data.status === 'completed' ? 0.16 : 0.26,
      });
    });
  }

  for (let index = 1; index < historyNodes.length; index += 1) {
    links.push({
      from: historyNodes[index - 1],
      to: historyNodes[index],
      alpha: 0.1,
    });
  }

  for (let index = 0; index < historyNodes.length; index += 1) {
    const node = historyNodes[index];
    const match = historyNodes.slice(index + 1).find((candidate) => candidate.data.tier === node.data.tier);
    if (match) {
      links.push({ from: node, to: match, alpha: 0.06 });
    }
  }

  appendChoiceOverlayNodes({ nodes, links, activeIds, layout });

  state.cosmosOverlayNodes = nodes;

  overlayNodeMap.forEach((node, id) => {
    if (!activeIds.has(id)) {
      if (state.hoveredNode === node) {
        state.hoveredNode = null;
      }
      overlayNodeMap.delete(id);
    }
  });

  return { nodes, links, layout };
}

function drawBackgroundGradient(W, H) {
  ctx.fillStyle = '#06060f';
  ctx.fillRect(0, 0, W, H);

  const vignette = ctx.createRadialGradient(W / 2, H / 2, W * 0.2, W / 2, H / 2, W * 0.8);
  vignette.addColorStop(0, 'rgba(6,6,15,0)');
  vignette.addColorStop(1, 'rgba(0,0,0,0.46)');
  ctx.fillStyle = vignette;
  ctx.fillRect(0, 0, W, H);
}

function drawStars(W, H, camera) {
  stars.forEach((star) => {
    star.twinklePhase += star.twinkleSpeed;
    const twinkle = 0.3 + 0.7 * (0.5 + 0.5 * Math.sin(star.twinklePhase));
    const alpha = star.brightness * twinkle;
    const parallaxFactor = star.depth * 0.6;
    const sx = (star.x - camera.x * parallaxFactor) * camera.zoom + W / 2;
    const sy = (star.y - camera.y * parallaxFactor) * camera.zoom + H / 2;
    if (sx < -10 || sx > W + 10 || sy < -10 || sy > H + 10) return;
    ctx.fillStyle = `rgba(200, 210, 255, ${alpha})`;
    ctx.beginPath();
    ctx.arc(sx, sy, star.size * camera.zoom, 0, Math.PI * 2);
    ctx.fill();
  });
}

function drawConnections(positionedSystems) {
  ctx.save();
  ctx.globalAlpha = 0.03;
  ctx.strokeStyle = 'rgba(255,255,255,1)';
  ctx.lineWidth = 0.5;
  for (let i = 0; i < positionedSystems.length; i += 1) {
    for (let j = i + 1; j < positionedSystems.length; j += 1) {
      const a = worldToScreen(positionedSystems[i].position.x, positionedSystems[i].position.y);
      const b = worldToScreen(positionedSystems[j].position.x, positionedSystems[j].position.y);
      ctx.beginPath();
      ctx.moveTo(a.x, a.y);
      ctx.lineTo(b.x, b.y);
      ctx.stroke();
    }
  }
  ctx.restore();
}

function drawSystemOrbit(system) {
  const center = worldToScreen(system.position.x, system.position.y);
  const [r, g, b] = system.color;
  const avgDist = 185 * state.camera.zoom;
  ctx.strokeStyle = `rgba(${r},${g},${b},0.06)`;
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.arc(center.x, center.y, avgDist, 0, Math.PI * 2);
  ctx.stroke();
  const grad = ctx.createRadialGradient(center.x, center.y, 0, center.x, center.y, 60 * state.camera.zoom);
  grad.addColorStop(0, `rgba(${r},${g},${b},0.08)`);
  grad.addColorStop(1, `rgba(${r},${g},${b},0)`);
  ctx.fillStyle = grad;
  ctx.beginPath();
  ctx.arc(center.x, center.y, 60 * state.camera.zoom, 0, Math.PI * 2);
  ctx.fill();
}

function drawNode(nodeObj, time, W, H) {
  const d = nodeObj.data;
  const s = nodeObj.system;
  const [r, g, b] = s.color;
  const angle = (d.angle || 0) + time * (d.orbitSpeed || 0.05);
  nodeObj.wx = s.position.x + Math.cos(angle) * (d.distance || 150);
  nodeObj.wy = s.position.y + Math.sin(angle) * (d.distance || 150);
  const screen = worldToScreen(nodeObj.wx, nodeObj.wy);
  nodeObj.sx = screen.x;
  nodeObj.sy = screen.y;
  if (screen.x < -100 || screen.x > W + 100 || screen.y < -100 || screen.y > H + 100) return;
  nodeObj.pulsePhase = (nodeObj.pulsePhase || 0) + 0.02;
  const pulse = 0.7 + 0.3 * Math.sin(nodeObj.pulsePhase);
  const targetGlow = nodeObj.hovered ? 1 : 0;
  nodeObj.glowIntensity = (nodeObj.glowIntensity || 0) + (targetGlow - (nodeObj.glowIntensity || 0)) * 0.1;
  const baseRadius = 4 * state.camera.zoom;
  const glowRadius = (30 + 20 * nodeObj.glowIntensity) * state.camera.zoom;
  const innerAlpha = (0.3 + 0.4 * nodeObj.glowIntensity) * pulse;
  const grad = ctx.createRadialGradient(screen.x, screen.y, 0, screen.x, screen.y, glowRadius);
  grad.addColorStop(0, `rgba(${r},${g},${b},${innerAlpha})`);
  grad.addColorStop(1, `rgba(${r},${g},${b},0)`);
  ctx.fillStyle = grad;
  ctx.beginPath();
  ctx.arc(screen.x, screen.y, glowRadius, 0, Math.PI * 2);
  ctx.fill();
  ctx.fillStyle = `rgba(${r},${g},${b},${0.8 + 0.2 * pulse})`;
  ctx.beginPath();
  ctx.arc(screen.x, screen.y, baseRadius, 0, Math.PI * 2);
  ctx.fill();
  ctx.fillStyle = `rgba(255,255,255,${0.6 + 0.3 * pulse + 0.1 * nodeObj.glowIntensity})`;
  ctx.beginPath();
  ctx.arc(screen.x, screen.y, baseRadius * 0.5, 0, Math.PI * 2);
  ctx.fill();
}

function drawFaultLineConnections(allNodes, systems) {
  const discoveredSystem = systems.find((system) => system.id === 'discovered');
  if (!discoveredSystem) return;
  const flConnections = discoveredSystem.fault_line_connections || [];
  const nodeByIndex = {};
  allNodes.forEach((node) => {
    if (node.data.node_index !== undefined) nodeByIndex[node.data.node_index] = node;
  });
  ctx.save();
  ctx.strokeStyle = 'rgba(214, 180, 106, 0.25)';
  ctx.lineWidth = 1.5;
  flConnections.forEach((connection) => {
    const nodes = Array.isArray(connection.nodes) ? connection.nodes : [];
    for (let i = 0; i < nodes.length - 1; i += 1) {
      const fromNode = nodeByIndex[nodes[i]];
      const toNode = nodeByIndex[nodes[i + 1]];
      if (fromNode && toNode) {
        ctx.beginPath();
        ctx.moveTo(fromNode.sx, fromNode.sy);
        ctx.lineTo(toNode.sx, toNode.sy);
        ctx.stroke();
      }
    }
  });
  ctx.restore();
}

function spawnGravityParticle(side) {
  const layout = getDecisionFieldLayout();
  const sideDrift = side === 'left' ? -1 : 1;
  gravityParticles.push({
    x: layout.center.x + (Math.random() - 0.5) * 70,
    y: layout.center.y + (Math.random() - 0.5) * 54,
    prevX: layout.center.x,
    prevY: layout.center.y,
    vx: sideDrift * (0.7 + Math.random() * 1.6),
    vy: (Math.random() - 0.5) * 1.1 - 0.1,
    age: 0,
    life: 1.8 + Math.random() * 1.4,
    side,
    size: 1.4 + Math.random() * 2.2,
  });
}

function updateGravityParticles(delta, leftWeight, rightWeight, intensity) {
  const layout = getDecisionFieldLayout();
  const desired = Math.round(18 + intensity * 70);
  while (gravityParticles.length < desired) {
    spawnGravityParticle(Math.random() < leftWeight ? 'left' : 'right');
  }
  if (gravityParticles.length > desired * 1.5) {
    gravityParticles = gravityParticles.slice(gravityParticles.length - Math.round(desired * 1.3));
  }

  gravityParticles = gravityParticles.filter((particle) => {
    const target = particle.side === 'left' ? layout.leftWell : layout.rightWell;
    const dx = target.x - particle.x;
    const dy = target.y - particle.y;
    const dist = Math.max(12, Math.hypot(dx, dy));
    particle.prevX = particle.x;
    particle.prevY = particle.y;
    particle.vx += (dx / dist) * 18 * delta;
    particle.vy += (dy / dist) * 18 * delta;
    particle.x += particle.vx * 46 * delta;
    particle.y += particle.vy * 46 * delta;
    particle.age += delta;
    return particle.age < particle.life && dist > 18;
  });
}

function drawGravityParticles() {
  gravityParticles.forEach((particle) => {
    const color = particle.side === 'left' ? [214, 180, 106] : [124, 166, 255];
    const alpha = clamp(1 - particle.age / particle.life, 0, 1) * 0.72;
    const from = worldToScreen(particle.prevX, particle.prevY);
    const to = worldToScreen(particle.x, particle.y);
    ctx.strokeStyle = `rgba(${color.join(',')},${alpha * 0.5})`;
    ctx.lineWidth = particle.size * 0.85;
    ctx.beginPath();
    ctx.moveTo(from.x, from.y);
    ctx.lineTo(to.x, to.y);
    ctx.stroke();

    const glow = ctx.createRadialGradient(to.x, to.y, 0, to.x, to.y, particle.size * 5);
    glow.addColorStop(0, `rgba(${color.join(',')},${alpha})`);
    glow.addColorStop(1, `rgba(${color.join(',')},0)`);
    ctx.fillStyle = glow;
    ctx.beginPath();
    ctx.arc(to.x, to.y, particle.size * 5, 0, Math.PI * 2);
    ctx.fill();

    ctx.fillStyle = `rgba(${color.join(',')},${alpha})`;
    ctx.beginPath();
    ctx.arc(to.x, to.y, particle.size, 0, Math.PI * 2);
    ctx.fill();
  });
}

function drawScenarioSatellites(screen, choiceData, time) {
  const distribution = choiceData?.probability_distribution || {};
  const buckets = [
    { key: 'tailwind', label: '顺风', color: [74, 153, 119] },
    { key: 'steady', label: '平稳', color: [242, 182, 79] },
    { key: 'headwind', label: '逆风', color: [230, 128, 105] },
  ];

  buckets.forEach((bucket, index) => {
    const percent = Number(distribution?.[bucket.key]?.percent || 0);
    if (!percent) return;
    const angle = time * (0.5 + index * 0.18) + index * ((Math.PI * 2) / 3);
    const orbit = 28 + index * 18 + percent * 0.25;
    const x = screen.x + Math.cos(angle) * orbit;
    const y = screen.y + Math.sin(angle) * orbit * 0.72;
    const radius = 2.5 + percent * 0.035;

    ctx.fillStyle = `rgba(${bucket.color.join(',')},0.86)`;
    ctx.beginPath();
    ctx.arc(x, y, radius, 0, Math.PI * 2);
    ctx.fill();

    ctx.strokeStyle = `rgba(${bucket.color.join(',')},0.18)`;
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.arc(screen.x, screen.y, orbit, 0, Math.PI * 2);
    ctx.stroke();
  });
}

function drawDecisionAnchorLabel(screen, title, subtitle, alpha) {
  const width = 220;
  const height = 56;
  const x = screen.x - width / 2;
  const y = screen.y - 92;

  ctx.save();
  ctx.fillStyle = `rgba(7, 11, 20, ${0.72 * alpha})`;
  ctx.strokeStyle = `rgba(255,255,255,${0.08 * alpha})`;
  ctx.lineWidth = 1;
  drawRoundedRectPath(x, y, width, height, 18);
  ctx.fill();
  ctx.stroke();

  ctx.fillStyle = `rgba(255,255,255,${0.92 * alpha})`;
  ctx.font = '600 14px "Noto Serif SC", serif';
  ctx.fillText(truncateText(title, 18), x + 16, y + 22);

  ctx.fillStyle = `rgba(244,232,204,${0.82 * alpha})`;
  ctx.font = '12px "PingFang SC", "Helvetica Neue", sans-serif';
  ctx.fillText(truncateText(subtitle, 28), x + 16, y + 42);
  ctx.restore();
}

function drawDecisionOrbitBands(layout, currentTier) {
  const centerScreen = worldToScreen(layout.center.x, layout.center.y);
  const zoom = clamp(state.camera.zoom, 0.42, 1.15);
  const bands = [
    { tier: 'quick', label: '快速带', radius: 210, color: [120, 186, 255] },
    { tier: 'deep', label: '沉思带', radius: 286, color: [214, 180, 106] },
    { tier: 'pro', label: 'Pro 带', radius: 360, color: [255, 128, 92] },
    { tier: 'ultra', label: 'Ultra 带', radius: 432, color: [112, 219, 197] },
  ];
  const counts = { quick: 0, deep: 0, pro: 0, ultra: 0 };
  const seen = new Set();

  (state.decisionHistory || []).forEach((item) => {
    if (!item?.decision_id || seen.has(item.decision_id)) return;
    seen.add(item.decision_id);
    counts[normalizeTierForHud(item.tier)] += 1;
  });
  if (state.currentDecision?.decision_id && !seen.has(state.currentDecision.decision_id)) {
    counts[normalizeTierForHud(state.currentDecision.tier)] += 1;
  }

  ctx.save();
  bands.forEach((band, index) => {
    const active = currentTier === band.tier;
    const radius = band.radius * zoom;
    ctx.fillStyle = `rgba(${band.color.join(',')},${active ? 0.045 : 0.02})`;
    ctx.beginPath();
    ctx.ellipse(centerScreen.x, centerScreen.y, radius, radius * 0.66, 0, 0, Math.PI * 2);
    ctx.fill();

    ctx.strokeStyle = `rgba(${band.color.join(',')},${active ? 0.18 : 0.08})`;
    ctx.lineWidth = active ? 1.6 : 1;
    ctx.setLineDash(index === 1 ? [10, 12] : [6, 10]);
    ctx.beginPath();
    ctx.ellipse(centerScreen.x, centerScreen.y, radius, radius * 0.66, 0, 0, Math.PI * 2);
    ctx.stroke();

    ctx.setLineDash([]);
    const labelX = centerScreen.x + radius - 92;
    const labelY = centerScreen.y - radius * 0.66 - 18;
    ctx.fillStyle = `rgba(8, 13, 24, ${active ? 0.82 : 0.62})`;
    drawRoundedRectPath(labelX, labelY, 86, 22, 10);
    ctx.fill();
    ctx.fillStyle = `rgba(${band.color.join(',')},${active ? 0.82 : 0.6})`;
    ctx.font = '11px "PingFang SC", "Helvetica Neue", sans-serif';
    ctx.fillText(`${band.label} · ${counts[band.tier]}`, labelX + 10, labelY + 14);
  });
  ctx.restore();
}

function drawDecisionTierMesh(nodes, time) {
  const historyNodes = nodes.filter((node) => !node.isCurrent && node.data?.decision_id);
  const groups = new Map();
  historyNodes.forEach((node) => {
    const tier = node.data?.tier || 'deep';
    if (!groups.has(tier)) {
      groups.set(tier, []);
    }
    groups.get(tier).push(node);
  });

  ctx.save();
  groups.forEach((groupNodes, tier) => {
    if (groupNodes.length < 2) return;
    const color = getTierStyle(tier).color;
    const sorted = [...groupNodes].sort((a, b) => a.sx - b.sx);

    sorted.forEach((node, index) => {
      const next = sorted[(index + 1) % sorted.length];
      if (!next || next === node) return;
      const controlX = (node.sx + next.sx) / 2 + Math.sin(time * 0.45 + index) * 24;
      const controlY = (node.sy + next.sy) / 2 - 20 - Math.cos(time * 0.52 + index) * 14;
      ctx.strokeStyle = `rgba(${color.join(',')},${sorted.length > 2 ? 0.12 : 0.08})`;
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(node.sx, node.sy);
      ctx.quadraticCurveTo(controlX, controlY, next.sx, next.sy);
      ctx.stroke();
    });

    const centroid = sorted.reduce((acc, node) => ({
      x: acc.x + node.sx,
      y: acc.y + node.sy,
    }), { x: 0, y: 0 });
    const cx = centroid.x / sorted.length;
    const cy = centroid.y / sorted.length;
    const glow = ctx.createRadialGradient(cx, cy, 0, cx, cy, 90);
    glow.addColorStop(0, `rgba(${color.join(',')},0.08)`);
    glow.addColorStop(1, `rgba(${color.join(',')},0)`);
    ctx.fillStyle = glow;
    ctx.beginPath();
    ctx.arc(cx, cy, 90, 0, Math.PI * 2);
    ctx.fill();
  });
  ctx.restore();
}

function drawDecisionEchoBeacons(nodes, time) {
  const completedNodes = nodes.filter((node) => !node.isCurrent && node.data?.status === 'completed').slice(0, 8);
  ctx.save();
  completedNodes.forEach((node, index) => {
    const radius = node.visualRadius * (2.8 + 0.32 * Math.sin(time * 1.2 + index));
    ctx.strokeStyle = `rgba(${node.visualColor.join(',')},0.14)`;
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.arc(node.sx, node.sy, radius, 0, Math.PI * 2);
    ctx.stroke();
  });
  ctx.restore();
}

function drawFocusedNodeBeacon(time) {
  const node = state.selectedNode || state.hoveredNode;
  if (!node || !Number.isFinite(node.sx) || !Number.isFinite(node.sy)) return;

  const pulse = 0.5 + 0.5 * Math.sin(time * 2.1);
  const baseRadius = Math.max(node.visualRadius || 6, 6);
  ctx.save();
  ctx.strokeStyle = `rgba(${(node.visualColor || [244, 232, 204]).join(',')},${0.24 + pulse * 0.12})`;
  ctx.lineWidth = 1.2;
  ctx.beginPath();
  ctx.arc(node.sx, node.sy, baseRadius * 3.3, 0, Math.PI * 2);
  ctx.stroke();

  ctx.beginPath();
  ctx.arc(node.sx, node.sy, baseRadius * 4.8 + pulse * 4, 0, Math.PI * 2);
  ctx.stroke();

  ctx.strokeStyle = 'rgba(255,255,255,0.16)';
  ctx.setLineDash([4, 6]);
  ctx.beginPath();
  ctx.moveTo(node.sx + baseRadius * 4.8, node.sy - baseRadius * 4.8);
  ctx.lineTo(node.sx + baseRadius * 8.4, node.sy - baseRadius * 8.4);
  ctx.stroke();
  ctx.restore();
}

function drawDecisionConstellation(time) {
  const { nodes, links, layout } = buildDecisionConstellation(time);
  if (!nodes.length) return;

  const centerScreen = worldToScreen(layout.center.x, layout.center.y);
  drawDecisionOrbitBands(layout, normalizeTierForHud(state.currentDecision?.tier));
  drawDecisionTierMesh(nodes, time);
  drawDecisionEchoBeacons(nodes, time);
  ctx.save();
  ctx.strokeStyle = 'rgba(255,255,255,0.06)';
  ctx.lineWidth = 1;
  ctx.setLineDash([4, 10]);
  ctx.beginPath();
  ctx.moveTo(centerScreen.x, centerScreen.y - 440 * state.camera.zoom);
  ctx.lineTo(centerScreen.x, centerScreen.y + 440 * state.camera.zoom);
  ctx.stroke();
  ctx.beginPath();
  ctx.moveTo(centerScreen.x - 460 * state.camera.zoom, centerScreen.y);
  ctx.lineTo(centerScreen.x + 460 * state.camera.zoom, centerScreen.y);
  ctx.stroke();
  ctx.restore();

  const clusterGlow = ctx.createRadialGradient(centerScreen.x, centerScreen.y, 0, centerScreen.x, centerScreen.y, 320 * state.camera.zoom);
  clusterGlow.addColorStop(0, 'rgba(214, 180, 106, 0.08)');
  clusterGlow.addColorStop(0.55, 'rgba(86, 146, 226, 0.06)');
  clusterGlow.addColorStop(1, 'rgba(86, 146, 226, 0)');
  ctx.fillStyle = clusterGlow;
  ctx.beginPath();
  ctx.arc(centerScreen.x, centerScreen.y, 320 * state.camera.zoom, 0, Math.PI * 2);
  ctx.fill();

  ctx.save();
  links.forEach((link) => {
    ctx.strokeStyle = `rgba(255,255,255,${link.alpha})`;
    ctx.lineWidth = link.from.isCurrent || link.to.isCurrent ? 1.2 : 0.8;
    ctx.setLineDash(link.from.isCurrent || link.to.isCurrent ? [5, 6] : [3, 8]);
    ctx.beginPath();
    ctx.moveTo(link.from.sx, link.from.sy);
    ctx.lineTo(link.to.sx, link.to.sy);
    ctx.stroke();
  });
  ctx.restore();

  nodes.forEach((node) => {
    const pulseSpeed = node.isCurrent ? 1.8 : 1.1;
    node.pulsePhase = (node.pulsePhase || 0) + 0.02 * pulseSpeed;
    const pulse = 0.86 + Math.sin(node.pulsePhase) * 0.12;
    const hoverTarget = node.hovered ? 1 : 0;
    node.glowIntensity = (node.glowIntensity || 0) + (hoverTarget - (node.glowIntensity || 0)) * 0.12;
    const scale = node.isCurrent ? 1.4 : 1;
    const radius = node.visualRadius * scale * (pulse + node.glowIntensity * 0.08);
    const glowRadius = radius * (4.6 + node.glowIntensity * 1.3);

    const glow = ctx.createRadialGradient(node.sx, node.sy, 0, node.sx, node.sy, glowRadius);
    glow.addColorStop(0, `rgba(${node.visualColor.join(',')},${0.32 + node.glowIntensity * 0.16})`);
    glow.addColorStop(1, `rgba(${node.visualColor.join(',')},0)`);
    ctx.fillStyle = glow;
    ctx.beginPath();
    ctx.arc(node.sx, node.sy, glowRadius, 0, Math.PI * 2);
    ctx.fill();

    ctx.strokeStyle = `rgba(${node.statusColor.join(',')},${node.isCurrent ? 0.56 : 0.36})`;
    ctx.lineWidth = node.isCurrent ? 2.2 : 1.4;
    ctx.beginPath();
    ctx.arc(node.sx, node.sy, radius * 1.85, 0, Math.PI * 2);
    ctx.stroke();

    ctx.fillStyle = `rgba(${node.visualColor.join(',')},0.95)`;
    ctx.beginPath();
    ctx.arc(node.sx, node.sy, radius, 0, Math.PI * 2);
    ctx.fill();

    ctx.fillStyle = `rgba(255,255,255,${node.isCurrent ? 0.92 : 0.72})`;
    ctx.beginPath();
    ctx.arc(node.sx, node.sy, radius * (node.isCurrent ? 0.45 : 0.4), 0, Math.PI * 2);
    ctx.fill();

    if (node.isCurrent) {
      ctx.save();
      ctx.strokeStyle = 'rgba(244,232,204,0.22)';
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.arc(node.sx, node.sy, radius * 3.3, time * 0.3, time * 0.3 + Math.PI * 1.3);
      ctx.stroke();
      ctx.restore();
      drawDecisionAnchorLabel(
        { x: node.sx, y: node.sy },
        getCurrentDecisionQuestion() || '决策星座',
        node.data.subtitle || '当前推演',
        1
      );
    }
  });

  ctx.fillStyle = 'rgba(255,255,255,0.46)';
  ctx.font = '12px "Noto Serif SC", serif';
  ctx.fillText('决策星座', centerScreen.x - 28, centerScreen.y + 122);
  drawFocusedNodeBeacon(time);
}

function drawDecisionGravity(time, delta) {
  if (state.appState === 'title') return;
  const hasDecisionContext = Boolean(getCurrentDecisionQuestion() || state.decisionHistory?.length);
  if (!hasDecisionContext) {
    gravityParticles = [];
    decisionEventBursts = [];
    return;
  }

  const layout = getDecisionFieldLayout();
  const leftWell = worldToScreen(layout.leftWell.x, layout.leftWell.y);
  const rightWell = worldToScreen(layout.rightWell.x, layout.rightWell.y);
  const center = worldToScreen(layout.center.x, layout.center.y);
  const { pro, con } = getCurrentBalance();
  const total = Math.max(1, pro + con);
  const leftWeight = clamp(pro / total, 0.08, 0.92);
  const rightWeight = clamp(con / total, 0.08, 0.92);
  const pulse = 0.92 + 0.08 * Math.sin(time * 1.3);
  const fieldRadius = Math.max(160, 260 * state.camera.zoom);
  const output = getCurrentSimulatorOutput();

  updateGravityParticles(delta, leftWeight, rightWeight, 1);

  const leftField = ctx.createRadialGradient(leftWell.x, leftWell.y, 0, leftWell.x, leftWell.y, fieldRadius);
  leftField.addColorStop(0, `rgba(214, 180, 106, ${0.18 * pulse})`);
  leftField.addColorStop(1, 'rgba(214, 180, 106, 0)');
  ctx.fillStyle = leftField;
  ctx.beginPath();
  ctx.arc(leftWell.x, leftWell.y, fieldRadius, 0, Math.PI * 2);
  ctx.fill();

  const rightField = ctx.createRadialGradient(rightWell.x, rightWell.y, 0, rightWell.x, rightWell.y, fieldRadius);
  rightField.addColorStop(0, `rgba(124, 166, 255, ${0.18 * pulse})`);
  rightField.addColorStop(1, 'rgba(124, 166, 255, 0)');
  ctx.fillStyle = rightField;
  ctx.beginPath();
  ctx.arc(rightWell.x, rightWell.y, fieldRadius, 0, Math.PI * 2);
  ctx.fill();

  const centerGlow = ctx.createRadialGradient(center.x, center.y, 0, center.x, center.y, fieldRadius * 0.9);
  centerGlow.addColorStop(0, 'rgba(244,232,204,0.08)');
  centerGlow.addColorStop(0.55, 'rgba(112,219,197,0.06)');
  centerGlow.addColorStop(1, 'rgba(112,219,197,0)');
  ctx.fillStyle = centerGlow;
  ctx.beginPath();
  ctx.arc(center.x, center.y, fieldRadius * 0.9, 0, Math.PI * 2);
  ctx.fill();

  drawGravityParticles();
  updateAndDrawDecisionEventBursts();

  [0, 1, 2].forEach((ringIndex) => {
    const radius = 74 + ringIndex * 30 + Math.sin(time * 0.9 + ringIndex) * 4;
    ctx.strokeStyle = `rgba(255,255,255,${0.08 - ringIndex * 0.018})`;
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.arc(center.x, center.y, radius, 0, Math.PI * 2);
    ctx.stroke();
  });

  ctx.save();
  ctx.strokeStyle = 'rgba(255,255,255,0.12)';
  ctx.lineWidth = 1.6;
  ctx.setLineDash([10, 12]);
  ctx.beginPath();
  ctx.moveTo(leftWell.x, leftWell.y);
  ctx.quadraticCurveTo(center.x, center.y - 64, rightWell.x, rightWell.y);
  ctx.stroke();
  ctx.restore();

  const tilt = (rightWeight - leftWeight) * 54;
  ctx.save();
  ctx.translate(center.x, center.y - 28);
  ctx.rotate((tilt / 180) * Math.PI);
  ctx.strokeStyle = 'rgba(255,255,255,0.18)';
  ctx.lineWidth = 2;
  ctx.beginPath();
  ctx.moveTo(-120, 0);
  ctx.lineTo(120, 0);
  ctx.stroke();
  ctx.restore();

  [
    {
      screen: leftWell,
      label: '正向引力',
      weight: leftWeight,
      color: [214, 180, 106],
      choiceData: output?.choice_a,
    },
    {
      screen: rightWell,
      label: '反向引力',
      weight: rightWeight,
      color: [124, 166, 255],
      choiceData: output?.choice_b,
    },
  ].forEach((well) => {
    const radius = 10 + well.weight * 16;
    ctx.fillStyle = `rgba(${well.color.join(',')},0.92)`;
    ctx.beginPath();
    ctx.arc(well.screen.x, well.screen.y, radius, 0, Math.PI * 2);
    ctx.fill();

    ctx.strokeStyle = `rgba(${well.color.join(',')},0.28)`;
    ctx.lineWidth = 1.2;
    ctx.beginPath();
    ctx.arc(well.screen.x, well.screen.y, radius * 2.4, 0, Math.PI * 2);
    ctx.stroke();

    ctx.fillStyle = 'rgba(255,255,255,0.52)';
    ctx.font = '12px "PingFang SC", "Helvetica Neue", sans-serif';
    ctx.fillText(well.label, well.screen.x - 22, well.screen.y - 26);

    ctx.fillStyle = 'rgba(244,232,204,0.76)';
    ctx.font = '600 12px "JetBrains Mono", "Courier New", monospace';
    ctx.fillText(`${Math.round(well.weight * 100)}%`, well.screen.x - 15, well.screen.y + 33);

    if (well.choiceData) {
      drawScenarioSatellites(well.screen, well.choiceData, time);
    }
  });
}

function drawTimelineCurve(sourceX, sourceY, direction, trackIndex, color, alpha) {
  const spread = 120 + trackIndex * 48;
  const endX = sourceX + direction * (220 + trackIndex * 44);
  const endY = sourceY - 90 + trackIndex * 80;
  const controlX = sourceX + direction * spread;
  const controlY = sourceY - 124 - trackIndex * 24;

  ctx.strokeStyle = `rgba(${color.join(',')},${alpha})`;
  ctx.lineWidth = 1.4;
  ctx.beginPath();
  ctx.moveTo(sourceX, sourceY);
  ctx.quadraticCurveTo(controlX, controlY, endX, endY);
  ctx.stroke();

  for (let step = 1; step <= 6; step += 1) {
    const t = step / 6;
    const px = (1 - t) * (1 - t) * sourceX + 2 * (1 - t) * t * controlX + t * t * endX;
    const py = (1 - t) * (1 - t) * sourceY + 2 * (1 - t) * t * controlY + t * t * endY;
    ctx.fillStyle = `rgba(${color.join(',')},${Math.max(alpha, 0.24)})`;
    ctx.beginPath();
    ctx.arc(px, py, 2.2 + t * 1.8, 0, Math.PI * 2);
    ctx.fill();
  }
}

function drawTimelineTrajectories() {
  const output = getCurrentSimulatorOutput();
  if (!output || state.appState === 'title') return;

  const layout = getDecisionFieldLayout();
  const left = worldToScreen(layout.leftWell.x, layout.leftWell.y);
  const right = worldToScreen(layout.rightWell.x, layout.rightWell.y);
  const baseY = worldToScreen(layout.center.x, layout.center.y + 12).y;
  const colors = {
    tailwind: [74, 153, 119],
    steady: [242, 182, 79],
    headwind: [230, 128, 105],
  };
  const order = ['tailwind', 'steady', 'headwind'];

  order.forEach((type, index) => {
    const leftPercent = Number(output.choice_a?.probability_distribution?.[type]?.percent || 0);
    const rightPercent = Number(output.choice_b?.probability_distribution?.[type]?.percent || 0);
    drawTimelineCurve(left.x, baseY, -1, index, colors[type], 0.16 + leftPercent / 260);
    drawTimelineCurve(right.x, baseY, 1, index, colors[type], 0.16 + rightPercent / 260);
  });
}

export function render(time) {
  if (state.useWebGL || !ctx) {
    if (pixiApp?.renderFuturePaths) {
      pixiApp.renderFuturePaths(getCurrentSimulatorOutput(), {
        title: state.currentDecision?.question || getCurrentSession()?.original_question || '当前决策',
      });
    }
    renderSystemLabels();
    renderCosmosHud();
    return;
  }

  const W = window.innerWidth;
  const H = window.innerHeight;
  const { camera, systems, allNodes, appState } = state;
  const delta = lastRenderTime ? clamp(time - lastRenderTime, 0.008, 0.04) : 0.016;
  lastRenderTime = time;

  drawBackgroundGradient(W, H);
  drawStars(W, H, camera);

  if (appState !== 'title') {
    const positionedSystems = systems.filter((system) => system && system.position);
    drawConnections(positionedSystems);
    positionedSystems.forEach((system) => drawSystemOrbit(system));
    allNodes.forEach((node) => drawNode(node, time, W, H));
    drawFaultLineConnections(allNodes, systems);
    drawDecisionConstellation(time);
    drawDecisionGravity(time, delta);
    drawTimelineTrajectories();
  } else {
    state.cosmosOverlayNodes = [];
    gravityParticles = [];
    decisionEventBursts = [];
  }

  renderSystemLabels();
  renderCosmosHud();
}
