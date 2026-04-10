/**
 * Divine Soul Topology
 * 《神魂拓扑》: 基于现有量子艺术模块边界，新增独立、懒加载的灵魂雕塑体验层。
 *
 * 约束：
 * - 不修改决策引擎、PDF、理性报告、后端。
 * - 只读取当前 decisionData / state.currentDecision / state.engineBSession。
 * - Three / WebGPU / 导出器按需动态加载。
 */

import { state } from '../core/state.js';
import { escapeHtml, showToast } from './utils.js';

const DB_NAME = 'clp_quantum_vibe_oracle';
const DB_VERSION = 1;
const STORE_NAME = 'quantumStates';
const SOUL_PREFIX = 'divine-soul-topology:';

let activeTopology = null;
let threeStackPromise = null;

function clamp(value, min, max) {
  return Math.max(min, Math.min(max, value));
}

function safeNumber(value, fallback = 0) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}

function compactText(value, fallback = '') {
  const text = String(value || '').replace(/\s+/g, ' ').trim();
  return text || fallback;
}

function truncateText(value, limit = 42) {
  const text = compactText(value);
  if (!text) return '';
  return text.length > limit ? `${text.slice(0, limit)}...` : text;
}

function wait(ms) {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
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

function createSeededRandom(seedText) {
  let seed = hashString(seedText) || 1;
  return () => {
    seed += 0x6D2B79F5;
    let value = seed;
    value = Math.imul(value ^ (value >>> 15), value | 1);
    value ^= value + Math.imul(value ^ (value >>> 7), value | 61);
    return ((value ^ (value >>> 14)) >>> 0) / 4294967296;
  };
}

function listify(value, limit = 5) {
  if (!value) return [];
  if (Array.isArray(value)) {
    return value.flatMap((item) => listify(item, limit)).filter(Boolean).slice(0, limit);
  }
  if (value && typeof value === 'object') {
    const record = value;

    if (typeof record.summary === 'string') {
      return [compactText(record.summary)].filter(Boolean).slice(0, limit);
    }

    if (Array.isArray(record.top_values) && record.top_values.length) {
      return [`价值排序：${record.top_values.slice(0, 3).map((item) => compactText(item)).filter(Boolean).join(' / ')}`]
        .filter(Boolean)
        .slice(0, limit);
    }

    if (Array.isArray(record.dominant_emotions) || record.hidden_need || record.gentle_reminder || record.grounding_prompt) {
      const emotions = Array.isArray(record.dominant_emotions)
        ? record.dominant_emotions
          .map((item) => compactText(item?.emotion || item?.label || item))
          .filter(Boolean)
          .slice(0, 2)
        : [];
      return [
        emotions.length ? `情绪核心：${emotions.join(' / ')}` : '',
        record.hidden_need ? `它在保护：${compactText(record.hidden_need)}` : '',
        record.gentle_reminder ? `镜像结论：${compactText(record.gentle_reminder)}` : '',
        record.grounding_prompt ? `稳住提醒：${compactText(record.grounding_prompt)}` : '',
        record.bias_reminder ? `偏差提醒：${compactText(record.bias_reminder)}` : '',
      ].filter(Boolean).slice(0, limit);
    }

    if ((record.time || record.description) && record.signals) {
      return [
        `${compactText(record.time, '关键节点')}：${compactText(record.description, '查看当前信号')}`,
        compactText(record.signals?.green?.signal)
          ? `绿灯信号：${compactText(record.signals.green.signal)}`
          : '',
      ].filter(Boolean).slice(0, limit);
    }

    if (record.trigger || record.day_1 || record.week_1 || record.safety_runway) {
      return [
        record.trigger ? `最怕发生：${compactText(record.trigger)}` : '',
        record.safety_runway ? `安全垫：${compactText(record.safety_runway)}` : '',
        record.emotional_note ? `情绪预期：${compactText(record.emotional_note)}` : '',
      ].filter(Boolean).slice(0, limit);
    }

    const preferred = [
      record.title,
      record.label,
      record.description,
      record.check,
      record.signal,
      record.action,
      record.content,
      record.core_insight,
    ].map((item) => compactText(item)).filter(Boolean);
    return preferred.slice(0, limit);
  }
  return [compactText(value)].filter(Boolean).slice(0, limit);
}

function splitNarrative(text) {
  return Array.from(new Set(
    String(text || '')
      .split(/[\n。！？!?;；]+/)
      .map((item) => compactText(item))
      .filter(Boolean)
  ));
}

function getDeviceProfile() {
  const isCoarse = window.matchMedia?.('(pointer: coarse)').matches;
  const isSmall = window.matchMedia?.('(max-width: 760px)').matches;
  const memory = safeNumber(navigator.deviceMemory, 4);
  const cores = safeNumber(navigator.hardwareConcurrency, 4);
  const pixelRatio = window.devicePixelRatio || 1;
  const lowPower = isSmall || isCoarse || memory <= 4 || cores <= 4 || pixelRatio > 2.2;
  return {
    lowPower,
    pixelRatio: Math.min(pixelRatio, lowPower ? 1.25 : 1.75),
    particleBudget: lowPower ? 12000 : 22000,
  };
}

function getDecisionId(data) {
  return compactText(
    data?.decision_id
    || data?.id
    || data?.engineb_session?.session_id
    || data?.session_id
    || state.currentDecisionId
    || state.currentDecision?.decision_id
    || 'soul-local'
  );
}

function getCurrentDecisionData(explicitData) {
  const decision = explicitData
    || window.decisionData
    || state.currentDecision
    || (state.engineBSession ? { engineb_session: state.engineBSession } : null)
    || {};
  const session = decision.engineb_session || state.engineBSession || {};
  const simulator = session.simulator_output || decision.simulator_output || {};
  const monteCarlo = simulator.monte_carlo || decision.monte_carlo || {};
  return {
    ...decision,
    question: decision.question || session.original_question || state.currentDecision?.question || '当前决策',
    engineb_session: session,
    simulator_output: simulator,
    monte_carlo: monteCarlo,
  };
}

function extractProbabilities(data) {
  const monte = data.monte_carlo || {};
  const smooth = monte.smooth_prob || {};
  const optimistic = safeNumber(data.simulator_output?.probability_optimistic || smooth.optimistic, 30);
  const baseline = safeNumber(data.simulator_output?.probability_baseline || smooth.baseline, 50);
  const pessimistic = safeNumber(data.simulator_output?.probability_pessimistic || smooth.pessimistic, 20);
  const total = optimistic + baseline + pessimistic;
  if (total <= 0) return { a: 30, b: 50, c: 20 };
  return {
    a: Math.round((optimistic / total) * 1000) / 10,
    b: Math.round((baseline / total) * 1000) / 10,
    c: Math.round((pessimistic / total) * 1000) / 10,
  };
}

function extractValidationMetrics(data) {
  const simulator = data.simulator_output || {};
  const session = data.engineb_session || {};
  const raw = simulator.validation_metrics
    || simulator.ninety_day_validation
    || session.validation_metrics
    || data.ninety_day_validation
    || {};
  return {
    studyHours: safeNumber(raw.study_hours || raw.learning_hours || raw.studyHours, 0),
    income: safeNumber(raw.income || raw.cashflow || raw.monthly_income, 0),
    mockExam: safeNumber(raw.mock_exam || raw.mockExam || raw.score, 0),
    checkins: safeNumber(raw.checkins || raw.days || raw.completed_days, 0),
  };
}

function buildContextHighlights(data) {
  const session = data.engineb_session || {};
  const simulator = data.simulator_output || {};
  const emotional = session.emotional_insight || session.emotional_mirror || session.emotional_snapshot || session.b5_emotional_mirror || {};
  const highlights = [
    ...listify(session.value_profile || session.value_profile?.summary || session.value_profile?.top_values, 2),
    ...listify(emotional, 2),
    ...listify(simulator.final_insight, 1),
    ...listify(simulator.crossroads, 1),
    ...listify(simulator.worst_case_survival_plan, 2),
  ]
    .map((item) => truncateText(item, 40))
    .filter(Boolean);
  return Array.from(new Set(highlights)).slice(0, 4);
}

function buildCuratorialNotes(data, blueprint, input, filterLabel = '') {
  const session = data.engineb_session || {};
  const simulator = data.simulator_output || {};
  const emotional = session.emotional_insight || session.emotional_mirror || session.emotional_snapshot || session.b5_emotional_mirror || {};
  const survival = simulator.worst_case_survival_plan || {};
  const crossroads = Array.isArray(simulator.crossroads) ? simulator.crossroads : [];
  const firstCrossroad = crossroads.find((item) => item && typeof item === 'object') || {};
  const valueSummary = compactText(session.value_profile?.summary || '');
  const emotionSummary = compactText(
    emotional.gentle_reminder
    || emotional.hidden_need
    || emotional.grounding_prompt
    || emotional.summary
  );
  const finalInsight = compactText(simulator.final_insight || simulator.comparison_summary || '');
  const probabilities = extractProbabilities(data);
  const dominantProbability = Math.max(probabilities.a, probabilities.b, probabilities.c);
  const eventCount = blueprint?.events?.length || extractNarrativeEvents(data, input).length;
  const survivalLead = compactText(survival.trigger || survival.day_1 || '');
  const survivalSupport = compactText(survival.safety_runway || survival.emotional_note || survival.week_1 || '');
  const nodeLead = compactText(firstCrossroad.time || '');
  const nodeSummary = compactText(firstCrossroad.description || '');

  return [
    {
      eyebrow: '灵魂摘要',
      title: truncateText(
        valueSummary
        || emotionSummary
        || `这件雕塑由 ${eventCount} 条人生节点折叠而成`,
        24
      ),
      body: truncateText(
        emotionSummary
        || valueSummary
        || '它更像一张内在轮廓图，描述你真正不想失去的秩序。',
        84
      ),
    },
    {
      eyebrow: '命运张力',
      title: truncateText(
        finalInsight || `当前最强基线概率约 ${Math.round(dominantProbability)}%`,
        26
      ),
      body: truncateText(
        nodeLead || nodeSummary
          ? `${nodeLead || '关键节点'}：${nodeSummary || '那会是第一次验证这条路是否真的成立。'}`
          : `当前滤镜为${filterLabel || '灵魂本质'}，它会把命运结构解释成一套缓慢呼吸的几何关系。`,
        90
      ),
    },
    {
      eyebrow: '回撤预案',
      title: truncateText(
        survivalLead ? `如果${survivalLead}` : '先活下来，再决定值不值',
        24
      ),
      body: truncateText(
        survivalSupport
          || '这件作品保留了一条柔软的回撤路径，不把所有意义都压在一次出手上。',
        88
      ),
    },
  ];
}

function blendHex(a, b, ratio = 0.5) {
  const t = clamp(ratio, 0, 1);
  const ar = (a >> 16) & 0xff;
  const ag = (a >> 8) & 0xff;
  const ab = a & 0xff;
  const br = (b >> 16) & 0xff;
  const bg = (b >> 8) & 0xff;
  const bb = b & 0xff;
  const rr = Math.round(ar + (br - ar) * t);
  const rg = Math.round(ag + (bg - ag) * t);
  const rb = Math.round(ab + (bb - ab) * t);
  return (rr << 16) | (rg << 8) | rb;
}

function scoreKeywords(text, keywords) {
  return keywords.reduce((sum, keyword) => sum + (text.includes(keyword) ? 1 : 0), 0);
}

function classifyEventKind(text, index) {
  if (scoreKeywords(text, ['遗憾', '后悔', '失去', '错过', '亏欠']) > 0) return 'mobius';
  if (scoreKeywords(text, ['转折', '改变', '离开', '开始', '决定', '重新']) > 0) return 'helix';
  if (scoreKeywords(text, ['爱', '家庭', '朋友', '关系', '拥抱', '连接']) > 0) return 'torus';
  if (scoreKeywords(text, ['梦想', '未来', '信仰', '命运', '灵魂', '愿望']) > 0) return 'sphere';
  return ['helix', 'torus', 'mobius', 'sphere'][index % 4];
}

function summarizePhotos(photos = []) {
  if (!photos.length) {
    return { brightness: 0.42, contrast: 0.38, saturation: 0.35, warmth: 0.5, palette: [] };
  }
  const total = photos.length;
  return photos.reduce((acc, photo) => {
    const metrics = photo.metrics || {};
    acc.brightness += safeNumber(metrics.brightness, 0.42);
    acc.contrast += safeNumber(metrics.contrast, 0.35);
    acc.saturation += safeNumber(metrics.saturation, 0.35);
    acc.warmth += safeNumber(metrics.warmth, 0.5);
    acc.palette.push(...(Array.isArray(metrics.palette) ? metrics.palette : []));
    return acc;
  }, { brightness: 0, contrast: 0, saturation: 0, warmth: 0, palette: [], total });
}

function summarizeVoice(recordings = []) {
  if (!recordings.length) return { energy: 0.22, duration: 0 };
  return recordings.reduce((acc, item) => {
    acc.energy += safeNumber(item.energy, 0.25);
    acc.duration += safeNumber(item.duration, 0);
    return acc;
  }, { energy: 0, duration: 0 });
}

function normalizeAggregateProfile(profile, total) {
  if (!total) return profile;
  return {
    brightness: clamp(profile.brightness / total, 0, 1),
    contrast: clamp(profile.contrast / total, 0, 1),
    saturation: clamp(profile.saturation / total, 0, 1),
    warmth: clamp(profile.warmth / total, 0, 1),
    palette: Array.from(new Set(profile.palette)).slice(0, 6),
  };
}

function buildSoulPalette(input, contextSignals) {
  const photo = normalizeAggregateProfile(summarizePhotos(input.photos), input.photos.length || 1);
  const voice = summarizeVoice(input.voiceRecordings);
  const probabilities = contextSignals.probabilities;
  const uncertainty = 1 - Math.max(probabilities.a, probabilities.b, probabilities.c) / 100;
  const gold = blendHex(0xe7c875, 0xf6e4b5, photo.warmth * 0.45);
  const silver = blendHex(0xa8b3c7, 0xe4ebf5, uncertainty * 0.5 + photo.contrast * 0.16);
  const cyan = blendHex(0x29d6d7, 0x7bf1e5, photo.saturation * 0.34 + voice.energy * 0.14);
  const violet = blendHex(0x5d35d5, 0xa26cff, uncertainty * 0.42 + (1 - photo.brightness) * 0.16);
  const obsidian = blendHex(0x030304, 0x09070d, uncertainty * 0.24);
  const mist = blendHex(silver, cyan, 0.35);
  return {
    gold,
    silver,
    cyan,
    violet,
    obsidian,
    mist,
    orbit: blendHex(gold, violet, 0.46),
    surface: blendHex(silver, cyan, 0.28),
    spirit: blendHex(gold, cyan, 0.32),
  };
}

function extractNarrativeEvents(data, input) {
  const lines = [
    ...splitNarrative(input.storyText),
    ...splitNarrative(input.voiceTranscript),
  ];
  if (lines.length) return lines.slice(0, 10);
  return buildContextHighlights(data);
}

function buildEventBlueprints(data, input, palette, previousEvents = []) {
  const probabilities = extractProbabilities(data);
  const metrics = extractValidationMetrics(data);
  const photo = normalizeAggregateProfile(summarizePhotos(input.photos), input.photos.length || 1);
  const voice = summarizeVoice(input.voiceRecordings);
  const events = extractNarrativeEvents(data, input);
  const previousById = new Map((previousEvents || []).map((item) => [item.id, item]));
  const random = createSeededRandom(`${getDecisionId(data)}:${input.storyText}:${input.voiceTranscript}`);
  const baseColors = [palette.gold, palette.silver, palette.cyan, palette.violet, palette.spirit];
  const mapped = events.map((label, index) => {
    const id = `event-${hashString(`${label}:${index}`).toString(36)}`;
    const prior = previousById.get(id);
    const kind = prior?.kind || classifyEventKind(label, index);
    const intensity = clamp(
      0.48
      + label.length / 110
      + photo.contrast * 0.22
      + voice.energy * 0.12
      + (metrics.checkins / 100) * 0.08,
      0.42,
      1.32
    );
    const orbitRadius = 2.8 + index * 0.62 + intensity * 0.24;
    const angle = ((index / Math.max(events.length, 1)) * Math.PI * 2) + random() * 0.38;
    const color = prior?.color || baseColors[index % baseColors.length];
    return {
      id,
      label,
      shortLabel: label.length > 18 ? `${label.slice(0, 18)}...` : label,
      kind,
      intensity,
      color,
      accent: blendHex(color, palette.cyan, 0.35 + random() * 0.2),
      glow: blendHex(color, palette.gold, 0.24 + random() * 0.3),
      orbitRadius,
      orbitHeight: prior?.orbitHeight ?? ((index % 2 ? 1 : -1) * (0.3 + random() * 0.8)),
      angle,
      tubeRadius: 0.07 + intensity * 0.05,
      scale: 0.54 + intensity * 0.42,
      turns: 1.8 + random() * 2.6 + probabilities.b / 100,
      heightSpan: 1.5 + intensity * 1.8,
      spinSpeed: 0.0026 + random() * 0.0052,
      pulseSpeed: 0.7 + random() * 1.4,
      drift: 0.12 + random() * 0.28,
    };
  });
  return mapped.slice(0, 12);
}

function buildSoulBlueprint(data, input, previousBlueprint = null) {
  const contextSignals = {
    highlights: buildContextHighlights(data),
    probabilities: extractProbabilities(data),
    metrics: extractValidationMetrics(data),
  };
  const palette = buildSoulPalette(input, contextSignals);
  const events = buildEventBlueprints(data, input, palette, previousBlueprint?.events || []);
  const photo = normalizeAggregateProfile(summarizePhotos(input.photos), input.photos.length || 1);
  const voice = summarizeVoice(input.voiceRecordings);
  const probabilities = contextSignals.probabilities;
  const uncertainty = 1 - Math.max(probabilities.a, probabilities.b, probabilities.c) / 100;
  const seed = `${getDecisionId(data)}:${input.storyText}:${input.voiceTranscript}:${JSON.stringify(photo)}:${voice.energy}`;
  const random = createSeededRandom(seed);
  const topologyComplexity = clamp(
    0.74
    + uncertainty * 0.9
    + events.length * 0.05
    + photo.contrast * 0.26,
    0.8,
    1.7
  );
  return {
    version: 1,
    seed,
    generatedAt: new Date().toISOString(),
    question: data.question,
    palette,
    contextHighlights: contextSignals.highlights,
    probabilities,
    metrics: contextSignals.metrics,
    voiceEnergy: clamp(voice.energy / Math.max(input.voiceRecordings.length || 1, 1), 0.12, 0.96),
    photoProfile: photo,
    events,
    motion: {
      breath: 0.42 + random() * 0.35 + photo.brightness * 0.12,
      drift: 0.34 + random() * 0.42 + uncertainty * 0.3,
      bloom: 0.38 + random() * 0.28 + voice.energy * 0.1,
    },
    core: {
      radius: 1.22 + topologyComplexity * 0.36,
      shellRadius: 2.05 + topologyComplexity * 0.68,
      shellMinor: 0.68 + topologyComplexity * 0.14,
      lobes: 3 + Math.round(probabilities.b / 30),
      twist: 1.2 + uncertainty * 2.2 + photo.saturation * 0.45,
      stretch: 0.86 + photo.brightness * 0.32 + voice.energy * 0.08,
      ringCount: clamp(3 + Math.round(events.length / 2) + Math.round(probabilities.a / 40), 3, 8),
    },
    particles: {
      spread: 6 + events.length * 0.36 + uncertainty * 2,
      density: 0.42 + topologyComplexity * 0.28,
      sparkle: 0.28 + voice.energy * 0.24,
    },
  };
}

function openSoulDb() {
  return new Promise((resolve, reject) => {
    if (!window.indexedDB) {
      resolve(null);
      return;
    }
    const request = window.indexedDB.open(DB_NAME, DB_VERSION);
    request.onupgradeneeded = () => {
      const db = request.result;
      if (!db.objectStoreNames.contains(STORE_NAME)) {
        db.createObjectStore(STORE_NAME, { keyPath: 'decisionId' });
      }
    };
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

function getSoulStorageId(decisionId) {
  return `${SOUL_PREFIX}${decisionId}`;
}

async function loadPersistedSoulState(decisionId) {
  const db = await openSoulDb();
  if (!db) return null;
  return new Promise((resolve) => {
    const tx = db.transaction(STORE_NAME, 'readonly');
    const request = tx.objectStore(STORE_NAME).get(getSoulStorageId(decisionId));
    request.onsuccess = () => resolve(request.result || null);
    request.onerror = () => resolve(null);
  });
}

async function savePersistedSoulState(snapshot) {
  const db = await openSoulDb();
  if (!db) return;
  await new Promise((resolve) => {
    const tx = db.transaction(STORE_NAME, 'readwrite');
    tx.objectStore(STORE_NAME).put(snapshot);
    tx.oncomplete = () => resolve();
    tx.onerror = () => resolve();
  });
}

function formatExportTimestamp(date = new Date()) {
  const pad = (value) => String(value).padStart(2, '0');
  return `${date.getFullYear()}${pad(date.getMonth() + 1)}${pad(date.getDate())}-${pad(date.getHours())}${pad(date.getMinutes())}${pad(date.getSeconds())}`;
}

function sanitizeFilename(value) {
  return compactText(value, '神魂拓扑').replace(/[<>:"/\\|?*\u0000-\u001F]+/g, '-');
}

function getResolutionPreset(key) {
  return {
    '4k': { width: 3840, height: 2160, label: '4K' },
    '8k': { width: 7680, height: 4320, label: '8K' },
  }[key] || { width: 3840, height: 2160, label: '4K' };
}

function dataUrlToUint8Array(dataUrl) {
  const base64 = String(dataUrl).split(',')[1] || '';
  const binary = atob(base64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i += 1) bytes[i] = binary.charCodeAt(i);
  return bytes;
}

function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 1200);
}

function readFileAsDataUrl(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result || ''));
    reader.onerror = () => reject(reader.error || new Error('读取文件失败'));
    reader.readAsDataURL(file);
  });
}

function loadImage(dataUrl) {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => resolve(img);
    img.onerror = reject;
    img.src = dataUrl;
  });
}

async function processPhotoFile(file) {
  const dataUrl = await readFileAsDataUrl(file);
  const image = await loadImage(dataUrl);
  const maxEdge = 420;
  const scale = Math.min(1, maxEdge / Math.max(image.width, image.height));
  const width = Math.max(1, Math.round(image.width * scale));
  const height = Math.max(1, Math.round(image.height * scale));
  const canvas = document.createElement('canvas');
  canvas.width = width;
  canvas.height = height;
  const ctx = canvas.getContext('2d', { willReadFrequently: true });
  ctx.drawImage(image, 0, 0, width, height);
  const pixels = ctx.getImageData(0, 0, width, height).data;
  let brightness = 0;
  let variance = 0;
  let saturation = 0;
  let warmth = 0;
  const step = Math.max(4, Math.floor((width * height) / 2400));
  let count = 0;
  for (let i = 0; i < pixels.length; i += 4 * step) {
    const r = pixels[i];
    const g = pixels[i + 1];
    const b = pixels[i + 2];
    const max = Math.max(r, g, b);
    const min = Math.min(r, g, b);
    const lum = (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255;
    brightness += lum;
    variance += lum * lum;
    saturation += max === 0 ? 0 : (max - min) / max;
    warmth += (r - b + 255) / 510;
    count += 1;
  }
  const normalizedBrightness = count ? brightness / count : 0.5;
  const contrast = count ? Math.sqrt(Math.max((variance / count) - (normalizedBrightness ** 2), 0)) : 0.3;
  const normalizedSaturation = count ? saturation / count : 0.35;
  const normalizedWarmth = count ? warmth / count : 0.5;
  const samplePoints = [
    [0.18, 0.22],
    [0.8, 0.24],
    [0.5, 0.52],
    [0.26, 0.82],
    [0.76, 0.78],
  ];
  const palette = samplePoints.map(([x, y]) => {
    const px = clamp(Math.floor(width * x), 0, width - 1);
    const py = clamp(Math.floor(height * y), 0, height - 1);
    const idx = (py * width + px) * 4;
    const r = pixels[idx];
    const g = pixels[idx + 1];
    const b = pixels[idx + 2];
    return `#${[r, g, b].map((value) => value.toString(16).padStart(2, '0')).join('')}`;
  });
  return {
    id: `photo-${hashString(`${file.name}:${file.size}:${Date.now()}`).toString(36)}`,
    name: file.name,
    dataUrl: canvas.toDataURL('image/jpeg', 0.84),
    width,
    height,
    metrics: {
      brightness: clamp(normalizedBrightness, 0, 1),
      contrast: clamp(contrast * 2.8, 0, 1),
      saturation: clamp(normalizedSaturation, 0, 1),
      warmth: clamp(normalizedWarmth, 0, 1),
      palette,
    },
  };
}

async function loadThreeStack() {
  if (threeStackPromise) return threeStackPromise;
  threeStackPromise = (async () => {
    let THREE = await import('three');
    let WebGPURenderer = null;
    let rendererType = 'WebGL';
    if (navigator.gpu) {
      try {
        const webgpu = await import('three/webgpu');
        THREE = { ...THREE, ...webgpu };
        WebGPURenderer = webgpu.WebGPURenderer || null;
        rendererType = WebGPURenderer ? 'WebGPU' : 'WebGL';
      } catch (error) {
        console.warn('Divine Soul Topology: WebGPU unavailable, fallback to WebGL.', error);
      }
    }
    const [
      { OrbitControls },
      { GLTFExporter },
      { ParametricGeometry },
      { EffectComposer },
      { RenderPass },
      { UnrealBloomPass },
    ] = await Promise.all([
      import('three/addons/controls/OrbitControls.js'),
      import('three/addons/exporters/GLTFExporter.js'),
      import('three/addons/geometries/ParametricGeometry.js'),
      import('three/addons/postprocessing/EffectComposer.js'),
      import('three/addons/postprocessing/RenderPass.js'),
      import('three/addons/postprocessing/UnrealBloomPass.js'),
    ]);
    return {
      THREE,
      WebGPURenderer,
      OrbitControls,
      GLTFExporter,
      ParametricGeometry,
      EffectComposer,
      RenderPass,
      UnrealBloomPass,
      rendererType,
    };
  })();
  return threeStackPromise;
}

function createSoulSurfaceFunction(blueprint) {
  const { shellRadius, shellMinor, lobes, twist, stretch } = blueprint.core;
  return (u, v, target) => {
    const theta = u * Math.PI * 2;
    const phi = v * Math.PI * 2;
    const wave = 1 + 0.16 * Math.sin(phi * lobes + theta * twist) + 0.08 * Math.cos(theta * (lobes - 1));
    const minor = shellMinor * wave;
    const localTwist = phi + theta * twist * 0.34;
    const x = (shellRadius + minor * Math.cos(localTwist)) * Math.cos(theta);
    const y = (minor * Math.sin(localTwist) * stretch) + Math.sin(theta * (lobes * 0.55)) * shellRadius * 0.14;
    const z = (shellRadius + minor * Math.cos(localTwist)) * Math.sin(theta);
    target.set(x, y, z);
  };
}

function createMobiusFunction(event) {
  return (u, v, target) => {
    const theta = u * Math.PI * 2;
    const strip = (v - 0.5) * event.scale * 1.45;
    const radius = event.scale * 1.24;
    const half = (theta / 2) + event.drift;
    const x = (radius + strip * Math.cos(half)) * Math.cos(theta);
    const y = strip * Math.sin(half);
    const z = (radius + strip * Math.cos(half)) * Math.sin(theta);
    target.set(x, y, z);
  };
}

function createEventMaterial(THREE, event, transparent = false) {
  return new THREE.MeshPhysicalMaterial({
    color: event.color,
    emissive: event.glow,
    emissiveIntensity: transparent ? 0.42 : 0.3,
    metalness: transparent ? 0.88 : 0.68,
    roughness: transparent ? 0.18 : 0.26,
    transparent,
    opacity: transparent ? 0.4 : 0.92,
    clearcoat: 1,
    clearcoatRoughness: 0.16,
    side: transparent ? THREE.DoubleSide : THREE.FrontSide,
    reflectivity: 1,
  });
}

function createSoulParticleField(THREE, blueprint, { budget, rendererType }) {
  const random = createSeededRandom(`${blueprint.seed}:particles`);
  const count = Math.round(budget * clamp(blueprint.particles.density, 0.4, 0.95));
  const positions = new Float32Array(count * 3);
  const seeds = new Float32Array(count);
  const phases = new Float32Array(count);
  const scales = new Float32Array(count);
  const colors = new Float32Array(count * 3);
  const baseColors = [blueprint.palette.gold, blueprint.palette.silver, blueprint.palette.cyan, blueprint.palette.violet];
  for (let i = 0; i < count; i += 1) {
    const orbit = blueprint.events[i % Math.max(blueprint.events.length, 1)];
    const radius = (random() < 0.62)
      ? (blueprint.core.shellRadius * (0.74 + random() * 1.2))
      : ((orbit?.orbitRadius || blueprint.core.shellRadius) * (0.84 + random() * 0.62));
    const theta = random() * Math.PI * 2;
    const phi = Math.acos((random() * 2) - 1);
    positions[i * 3] = Math.sin(phi) * Math.cos(theta) * radius;
    positions[i * 3 + 1] = Math.cos(phi) * radius * (0.58 + random() * 0.7);
    positions[i * 3 + 2] = Math.sin(phi) * Math.sin(theta) * radius;
    seeds[i] = random();
    phases[i] = random() * Math.PI * 2;
    scales[i] = 0.55 + random() * 1.9;
    const hex = baseColors[i % baseColors.length];
    colors[i * 3] = ((hex >> 16) & 0xff) / 255;
    colors[i * 3 + 1] = ((hex >> 8) & 0xff) / 255;
    colors[i * 3 + 2] = (hex & 0xff) / 255;
  }
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
  geometry.setAttribute('aSeed', new THREE.BufferAttribute(seeds, 1));
  geometry.setAttribute('aPhase', new THREE.BufferAttribute(phases, 1));
  geometry.setAttribute('aScale', new THREE.BufferAttribute(scales, 1));
  geometry.setAttribute('color', new THREE.BufferAttribute(colors, 3));

  const uniforms = {
    uTime: { value: 0 },
    uFlow: { value: 0.5 },
    uPixelRatio: { value: Math.min(window.devicePixelRatio || 1, 1.75) },
  };

  const material = rendererType === 'WebGPU'
    ? new THREE.PointsMaterial({
      size: 0.06,
      vertexColors: true,
      transparent: true,
      opacity: 0.56,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    })
    : new THREE.ShaderMaterial({
      uniforms,
      transparent: true,
      depthWrite: false,
      blending: THREE.AdditiveBlending,
      vertexShader: `
        attribute float aSeed;
        attribute float aPhase;
        attribute float aScale;
        uniform float uTime;
        uniform float uFlow;
        uniform float uPixelRatio;
        varying float vSeed;
        varying vec3 vColor;
        void main() {
          vec3 p = position;
          float orbit = atan(p.z, p.x);
          float radius = length(p.xz);
          float swirl = sin(radius * 1.7 - uTime * (0.7 + uFlow) + aPhase) * 0.26;
          orbit += swirl * (0.3 + aSeed * 0.6);
          p.x = cos(orbit) * radius;
          p.z = sin(orbit) * radius;
          p.y += cos(uTime * 0.8 + aPhase + aSeed * 6.28318) * 0.22;
          vec4 mvPosition = modelViewMatrix * vec4(p, 1.0);
          gl_Position = projectionMatrix * mvPosition;
          gl_PointSize = aScale * (64.0 / max(0.45, -mvPosition.z)) * uPixelRatio;
          vSeed = aSeed;
          vColor = color;
        }
      `,
      fragmentShader: `
        varying float vSeed;
        varying vec3 vColor;
        void main() {
          vec2 uv = gl_PointCoord - vec2(0.5);
          float dist = length(uv);
          if (dist > 0.5) discard;
          float core = smoothstep(0.46, 0.06, dist);
          float halo = smoothstep(0.5, 0.14, dist) * 0.36;
          gl_FragColor = vec4(vColor, (core + halo) * (0.42 + vSeed * 0.4));
        }
      `,
    });
  const points = new THREE.Points(geometry, material);
  points.userData.dstRole = 'particles';
  points.userData.dstUniforms = uniforms;
  points.userData.spinSpeed = 0.0018;
  return points;
}

function createBackgroundStars(THREE, palette, lowPower) {
  const random = createSeededRandom(`dst-background:${palette.gold}`);
  const count = lowPower ? 480 : 920;
  const positions = new Float32Array(count * 3);
  const colors = new Float32Array(count * 3);
  const base = [palette.gold, palette.cyan, palette.violet];
  for (let i = 0; i < count; i += 1) {
    positions[i * 3] = (random() - 0.5) * 54;
    positions[i * 3 + 1] = (random() - 0.5) * 28;
    positions[i * 3 + 2] = (random() - 0.5) * 54;
    const hex = base[i % base.length];
    colors[i * 3] = ((hex >> 16) & 0xff) / 255;
    colors[i * 3 + 1] = ((hex >> 8) & 0xff) / 255;
    colors[i * 3 + 2] = (hex & 0xff) / 255;
  }
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
  geometry.setAttribute('color', new THREE.BufferAttribute(colors, 3));
  const material = new THREE.PointsMaterial({
    size: lowPower ? 0.06 : 0.08,
    vertexColors: true,
    transparent: true,
    opacity: 0.42,
    blending: THREE.AdditiveBlending,
    depthWrite: false,
  });
  const stars = new THREE.Points(geometry, material);
  stars.userData.dstRole = 'background-stars';
  return stars;
}

function createSoulSculpture(THREE, ParametricGeometry, blueprint, { device, rendererType, includeParticles = true }) {
  const group = new THREE.Group();
  const palette = blueprint.palette;

  const coreMaterial = new THREE.MeshPhysicalMaterial({
    color: palette.obsidian,
    emissive: palette.gold,
    emissiveIntensity: 0.42,
    metalness: 0.96,
    roughness: 0.12,
    clearcoat: 1,
    clearcoatRoughness: 0.08,
    reflectivity: 1,
  });
  const core = new THREE.Mesh(
    new THREE.IcosahedronGeometry(blueprint.core.radius, device.lowPower ? 3 : 5),
    coreMaterial
  );
  core.userData.dstRole = 'core';
  core.userData.pulseSpeed = 0.85 + blueprint.motion.breath;
  group.add(core);

  const shellMaterial = new THREE.MeshPhysicalMaterial({
    color: palette.surface,
    emissive: palette.cyan,
    emissiveIntensity: 0.16,
    metalness: 0.76,
    roughness: 0.14,
    transparent: true,
    opacity: 0.32,
    clearcoat: 1,
    side: THREE.DoubleSide,
  });
  const shell = new THREE.Mesh(
    new ParametricGeometry(createSoulSurfaceFunction(blueprint), device.lowPower ? 58 : 88, device.lowPower ? 28 : 44),
    shellMaterial
  );
  shell.userData.dstRole = 'topology-shell';
  shell.userData.spinSpeed = 0.0022;
  group.add(shell);

  const aura = new THREE.Mesh(
    new THREE.SphereGeometry(blueprint.core.shellRadius * 1.15, 40, 28),
    new THREE.MeshBasicMaterial({
      color: palette.spirit,
      transparent: true,
      opacity: 0.08,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    })
  );
  aura.userData.dstRole = 'aura';
  group.add(aura);

  for (let i = 0; i < blueprint.core.ringCount; i += 1) {
    const radius = blueprint.core.radius * 1.4 + i * 0.46;
    const ring = new THREE.Mesh(
      new THREE.TorusGeometry(radius, 0.018 + i * 0.006, 20, 220),
      new THREE.MeshBasicMaterial({
        color: i % 2 === 0 ? palette.gold : palette.violet,
        transparent: true,
        opacity: 0.22 + i * 0.03,
        blending: THREE.AdditiveBlending,
        depthWrite: false,
      })
    );
    ring.rotation.x = Math.PI / 2 + i * 0.32;
    ring.rotation.y = i * 0.44;
    ring.userData.dstRole = 'ring';
    ring.userData.waveSpeed = 0.8 + i * 0.14;
    group.add(ring);
  }

  blueprint.events.forEach((event) => {
    const eventGroup = new THREE.Group();
    eventGroup.userData.dstRole = 'event-group';
    eventGroup.userData.eventId = event.id;
    eventGroup.userData.orbitRadius = event.orbitRadius;
    eventGroup.userData.baseAngle = event.angle;
    eventGroup.userData.baseHeight = event.orbitHeight;
    eventGroup.userData.spinSpeed = event.spinSpeed;
    eventGroup.userData.growDelay = 0.65 + group.children.filter((child) => child.userData?.dstRole === 'event-group').length * 0.12;

    const anchor = new THREE.Mesh(
      new THREE.SphereGeometry(0.08 + event.intensity * 0.08, 20, 18),
      createEventMaterial(THREE, event)
    );
    anchor.position.set(event.orbitRadius, event.orbitHeight, 0);
    anchor.userData.dstRole = 'event-anchor';
    anchor.userData.pulseSpeed = event.pulseSpeed;
    eventGroup.add(anchor);

    const tetherCurve = new THREE.CatmullRomCurve3([
      new THREE.Vector3(0, 0, 0),
      new THREE.Vector3(event.orbitRadius * 0.28, event.orbitHeight * 0.8 + 0.6, -event.orbitRadius * 0.18),
      new THREE.Vector3(event.orbitRadius * 0.72, event.orbitHeight * 0.9, event.orbitRadius * 0.12),
      new THREE.Vector3(event.orbitRadius, event.orbitHeight, 0),
    ]);
    const tether = new THREE.Mesh(
      new THREE.TubeGeometry(tetherCurve, device.lowPower ? 32 : 64, 0.012 + event.intensity * 0.01, 8, false),
      new THREE.MeshBasicMaterial({
        color: event.accent,
        transparent: true,
        opacity: 0.3,
        blending: THREE.AdditiveBlending,
      })
    );
    tether.userData.dstRole = 'event-thread';
    eventGroup.add(tether);

    let artifact;
    if (event.kind === 'helix') {
      class SoulHelixCurve extends THREE.Curve {
        getPoint(t, target = new THREE.Vector3()) {
          const angle = t * Math.PI * 2 * event.turns;
          const radius = event.scale * (0.82 + Math.sin(t * Math.PI * 4) * 0.1);
          const x = Math.cos(angle) * radius;
          const y = (t - 0.5) * event.heightSpan;
          const z = Math.sin(angle) * radius;
          return target.set(x, y, z);
        }
      }
      artifact = new THREE.Mesh(
        new THREE.TubeGeometry(new SoulHelixCurve(), device.lowPower ? 64 : 120, event.tubeRadius, 14, false),
        createEventMaterial(THREE, event)
      );
      artifact.position.set(event.orbitRadius, event.orbitHeight, 0);
    } else if (event.kind === 'mobius') {
      artifact = new THREE.Mesh(
        new ParametricGeometry(createMobiusFunction(event), device.lowPower ? 46 : 72, device.lowPower ? 10 : 16),
        createEventMaterial(THREE, event, true)
      );
      artifact.position.set(event.orbitRadius, event.orbitHeight, 0);
      artifact.scale.setScalar(0.7 + event.intensity * 0.2);
    } else if (event.kind === 'torus') {
      artifact = new THREE.Mesh(
        new THREE.TorusGeometry(event.scale * 0.9, event.tubeRadius * 1.2, 18, 160),
        createEventMaterial(THREE, event)
      );
      artifact.position.set(event.orbitRadius, event.orbitHeight, 0);
      artifact.rotation.x = Math.PI / 2;
    } else {
      artifact = new THREE.Mesh(
        new THREE.SphereGeometry(event.scale * 0.82, 28, 24),
        createEventMaterial(THREE, event)
      );
      artifact.position.set(event.orbitRadius, event.orbitHeight, 0);
    }

    artifact.userData.dstRole = 'event-artifact';
    artifact.userData.spinSpeed = event.spinSpeed * 1.6;
    artifact.userData.pulseSpeed = event.pulseSpeed;
    eventGroup.add(artifact);
    eventGroup.rotation.y = event.angle;
    group.add(eventGroup);
  });

  if (includeParticles) {
    group.add(createSoulParticleField(THREE, blueprint, { budget: device.particleBudget, rendererType }));
  }

  return group;
}

function ensureStyles() {
  if (document.getElementById('dst-style')) return;
  const style = document.createElement('style');
  style.id = 'dst-style';
  style.textContent = `
    .dst-root {
      --dst-gold: #e5cb86;
      --dst-silver: #dde4ef;
      --dst-cyan: #64e8dd;
      --dst-violet: #9d71ff;
      position: fixed;
      inset: 0;
      z-index: 10000;
      color: #f4f2ee;
      font-family: "Noto Serif SC", "Iowan Old Style", "Songti SC", serif;
    }
    .dst-root.is-free-flight .dst-canvas {
      cursor: grab;
    }
    .dst-root.is-free-flight .dst-topbar,
    .dst-root.is-free-flight .dst-panel {
      filter: saturate(1.04);
    }
    .dst-root.is-free-flight .dst-panel {
      border-color: rgba(100, 232, 221, 0.16);
      box-shadow: 0 26px 80px rgba(0, 0, 0, 0.46), 0 0 32px rgba(100, 232, 221, 0.08);
    }
    .dst-shell {
      position: relative;
      width: 100%;
      height: 100%;
      overflow: hidden;
      background:
        radial-gradient(circle at 50% 40%, rgba(74, 52, 119, 0.24), transparent 42%),
        radial-gradient(circle at 15% 22%, rgba(229, 203, 134, 0.14), transparent 26%),
        radial-gradient(circle at 82% 18%, rgba(90, 234, 223, 0.16), transparent 24%),
        linear-gradient(180deg, #030304 0%, #000 100%);
      isolation: isolate;
    }
    .dst-shell::before {
      content: "";
      position: absolute;
      inset: 0;
      pointer-events: none;
      background:
        linear-gradient(135deg, rgba(255,255,255,0.04), transparent 42%),
        radial-gradient(circle at 50% 55%, rgba(157, 113, 255, 0.12), transparent 34%);
      mix-blend-mode: screen;
      opacity: 0.9;
    }
    .dst-canvas {
      position: absolute;
      inset: 0;
      width: 100%;
      height: 100%;
      display: block;
      touch-action: none;
    }
    .dst-topbar {
      position: absolute;
      z-index: 6;
      left: 24px;
      right: 24px;
      top: 22px;
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      gap: 20px;
      pointer-events: none;
    }
    .dst-kicker {
      color: var(--dst-gold);
      letter-spacing: 0.24em;
      font-size: 11px;
      text-transform: uppercase;
    }
    .dst-topbar h2 {
      margin: 6px 0 8px;
      font-size: clamp(30px, 4vw, 56px);
      line-height: 0.95;
      letter-spacing: 0.08em;
      text-shadow: 0 0 28px rgba(229, 203, 134, 0.22);
    }
    .dst-topbar p {
      margin: 0;
      max-width: min(640px, 60vw);
      color: rgba(244, 242, 238, 0.7);
      font-size: 13px;
      letter-spacing: 0.04em;
      line-height: 1.55;
    }
    .dst-mode-switch {
      pointer-events: auto;
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
      justify-content: flex-end;
      padding: 8px;
      border-radius: 999px;
      border: 1px solid rgba(255, 255, 255, 0.1);
      background: rgba(6, 8, 12, 0.66);
      backdrop-filter: blur(18px);
    }
    .dst-mode-switch button,
    .dst-primary,
    .dst-filter-button,
    .dst-tool-button,
    .dst-photo-trigger,
    .dst-voice-button,
    .dst-photo-remove {
      appearance: none;
      -webkit-appearance: none;
      border: 1px solid rgba(255, 255, 255, 0.12);
      border-radius: 999px;
      background: rgba(255, 255, 255, 0.04);
      color: #f4f2ee;
      font: inherit;
      cursor: pointer;
      transition: transform 0.18s ease, border-color 0.18s ease, background 0.18s ease, box-shadow 0.18s ease;
    }
    .dst-mode-switch button:hover,
    .dst-primary:hover,
    .dst-filter-button:hover,
    .dst-tool-button:hover,
    .dst-photo-trigger:hover,
    .dst-voice-button:hover,
    .dst-photo-remove:hover {
      transform: translateY(-1px);
      border-color: rgba(229, 203, 134, 0.46);
      background: rgba(255, 255, 255, 0.09);
    }
    .dst-mode-switch button {
      padding: 10px 14px;
    }
    .dst-mode-switch .is-active {
      background: linear-gradient(135deg, rgba(229, 203, 134, 0.18), rgba(100, 232, 221, 0.18));
      border-color: rgba(229, 203, 134, 0.44);
      box-shadow: 0 0 18px rgba(229, 203, 134, 0.14);
    }
    .dst-panel {
      position: absolute;
      z-index: 5;
      right: 18px;
      top: 136px;
      width: min(420px, calc(100vw - 32px));
      max-height: calc(100vh - 164px);
      overflow: auto;
      display: grid;
      gap: 12px;
      align-content: start;
      padding: 16px;
      border-radius: 26px;
      border: 1px solid rgba(255, 255, 255, 0.12);
      background: linear-gradient(180deg, rgba(8, 9, 13, 0.84), rgba(8, 8, 10, 0.72));
      box-shadow: 0 30px 90px rgba(0, 0, 0, 0.44);
      backdrop-filter: blur(18px);
      scrollbar-width: thin;
      scrollbar-color: rgba(229, 203, 134, 0.42) rgba(255,255,255,0.06);
    }
    .dst-panel::-webkit-scrollbar { width: 8px; }
    .dst-panel::-webkit-scrollbar-thumb { background: rgba(229, 203, 134, 0.42); border-radius: 999px; }
    .dst-section {
      display: grid;
      gap: 10px;
      padding: 14px;
      border-radius: 20px;
      border: 1px solid rgba(255, 255, 255, 0.08);
      background: rgba(255, 255, 255, 0.03);
    }
    .dst-section-head {
      display: flex;
      justify-content: space-between;
      gap: 10px;
      align-items: center;
      font-size: 12px;
      letter-spacing: 0.08em;
      text-transform: uppercase;
      color: var(--dst-gold);
    }
    .dst-section-head small {
      color: rgba(244, 242, 238, 0.56);
      letter-spacing: 0;
      text-transform: none;
      font-size: 11px;
    }
    .dst-story {
      min-height: 140px;
      resize: vertical;
      border-radius: 18px;
      border: 1px solid rgba(255, 255, 255, 0.08);
      background: rgba(255, 255, 255, 0.03);
      color: #f5f1ec;
      padding: 14px;
      font: inherit;
      line-height: 1.72;
      outline: none;
    }
    .dst-story:focus {
      border-color: rgba(229, 203, 134, 0.34);
      box-shadow: 0 0 0 1px rgba(229, 203, 134, 0.18);
    }
    .dst-context {
      display: grid;
      grid-template-columns: 1fr;
      gap: 8px;
    }
    .dst-context-chip {
      min-width: 0;
      padding: 10px 12px;
      border-radius: 14px;
      font-size: 11px;
      line-height: 1.55;
      color: rgba(244, 242, 238, 0.76);
      border: 1px solid rgba(255,255,255,0.08);
      background: rgba(255,255,255,0.03);
      display: -webkit-box;
      -webkit-line-clamp: 2;
      -webkit-box-orient: vertical;
      overflow: hidden;
    }
    .dst-curation-grid {
      display: grid;
      gap: 10px;
    }
    .dst-curation-card {
      padding: 12px 13px;
      border-radius: 16px;
      border: 1px solid rgba(255, 255, 255, 0.07);
      background:
        linear-gradient(135deg, rgba(255,255,255,0.04), rgba(255,255,255,0.02)),
        radial-gradient(circle at 100% 0%, rgba(229, 203, 134, 0.08), transparent 45%);
    }
    .dst-curation-eyebrow {
      color: rgba(229, 203, 134, 0.86);
      font-size: 10px;
      letter-spacing: 0.14em;
      text-transform: uppercase;
    }
    .dst-curation-title {
      margin-top: 6px;
      font-size: 14px;
      line-height: 1.45;
      color: #f9f5ef;
    }
    .dst-curation-body {
      margin-top: 5px;
      font-size: 12px;
      line-height: 1.62;
      color: rgba(244, 242, 238, 0.66);
    }
    .dst-voice-row,
    .dst-photo-row {
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
      align-items: center;
    }
    .dst-voice-button,
    .dst-photo-trigger,
    .dst-primary {
      padding: 10px 14px;
    }
    .dst-primary {
      background: linear-gradient(135deg, rgba(229, 203, 134, 0.24), rgba(100, 232, 221, 0.14));
      border-color: rgba(229, 203, 134, 0.4);
      box-shadow: 0 0 20px rgba(229, 203, 134, 0.12);
    }
    .dst-voice-meter {
      position: relative;
      width: 100%;
      height: 8px;
      border-radius: 999px;
      overflow: hidden;
      background: rgba(255, 255, 255, 0.06);
    }
    .dst-voice-meter span {
      display: block;
      height: 100%;
      width: 0%;
      background: linear-gradient(90deg, var(--dst-cyan), var(--dst-gold), var(--dst-violet));
      box-shadow: 0 0 16px rgba(100, 232, 221, 0.22);
      transition: width 0.12s linear;
    }
    .dst-voice-status,
    .dst-save-copy,
    .dst-renderer-copy {
      font-size: 12px;
      line-height: 1.5;
      color: rgba(244, 242, 238, 0.62);
    }
    .dst-transcript {
      min-height: 48px;
      padding: 12px;
      border-radius: 16px;
      background: rgba(255, 255, 255, 0.04);
      color: rgba(244, 242, 238, 0.82);
      font-size: 12px;
      line-height: 1.6;
    }
    .dst-photo-grid {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 10px;
    }
    .dst-photo-card {
      position: relative;
      overflow: hidden;
      border-radius: 18px;
      border: 1px solid rgba(255, 255, 255, 0.08);
      background: rgba(255, 255, 255, 0.03);
    }
    .dst-photo-card img {
      width: 100%;
      aspect-ratio: 1 / 1;
      object-fit: cover;
      display: block;
      filter: saturate(0.92) contrast(1.02);
    }
    .dst-photo-meta {
      padding: 9px 10px 11px;
      display: grid;
      gap: 4px;
      font-size: 11px;
      color: rgba(244, 242, 238, 0.7);
    }
    .dst-photo-remove {
      position: absolute;
      top: 8px;
      right: 8px;
      width: 30px;
      height: 30px;
      display: grid;
      place-items: center;
      border-radius: 999px;
      background: rgba(4, 4, 4, 0.6);
      backdrop-filter: blur(8px);
    }
    .dst-filter-list,
    .dst-tool-grid {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 8px;
    }
    .dst-filter-button,
    .dst-tool-button {
      min-height: 46px;
      padding: 11px 12px;
      border-radius: 16px;
      text-align: left;
      line-height: 1.4;
    }
    .dst-filter-button.is-active {
      background: linear-gradient(135deg, rgba(229, 203, 134, 0.2), rgba(157, 113, 255, 0.16));
      border-color: rgba(229, 203, 134, 0.36);
      box-shadow: 0 0 20px rgba(229, 203, 134, 0.08);
    }
    .dst-stats {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 8px;
    }
    .dst-stat {
      padding: 12px;
      border-radius: 16px;
      background: rgba(255, 255, 255, 0.03);
      border: 1px solid rgba(255, 255, 255, 0.06);
    }
    .dst-stat strong {
      display: block;
      margin-top: 4px;
      font-size: 18px;
      color: #fff;
    }
    .dst-empty-state {
      position: absolute;
      z-index: 4;
      left: 28px;
      bottom: 28px;
      max-width: min(460px, calc(100vw - 56px));
      padding: 16px 18px;
      display: grid;
      gap: 14px;
      border-radius: 22px;
      border: 1px solid rgba(255, 255, 255, 0.08);
      background: rgba(6, 8, 12, 0.62);
      backdrop-filter: blur(12px);
      color: rgba(244, 242, 238, 0.82);
      line-height: 1.72;
    }
    .dst-empty-state strong {
      display: block;
      color: var(--dst-gold);
      letter-spacing: 0.08em;
    }
    .dst-empty-copy {
      display: grid;
      gap: 6px;
    }
    .dst-empty-copy p {
      margin: 0;
    }
    .dst-empty-preview {
      position: relative;
      height: 132px;
      border-radius: 18px;
      overflow: hidden;
      border: 1px solid rgba(255, 255, 255, 0.06);
      background:
        radial-gradient(circle at 50% 50%, rgba(100, 232, 221, 0.14), transparent 24%),
        radial-gradient(circle at 50% 48%, rgba(229, 203, 134, 0.16), transparent 34%),
        linear-gradient(180deg, rgba(255,255,255,0.04), rgba(255,255,255,0.01));
      box-shadow: inset 0 0 40px rgba(0, 0, 0, 0.28);
    }
    .dst-empty-preview::before,
    .dst-empty-preview::after {
      content: "";
      position: absolute;
      inset: 14px;
      border-radius: 50%;
      border: 1px solid rgba(229, 203, 134, 0.08);
      filter: blur(0.3px);
    }
    .dst-empty-preview::after {
      inset: 28px 78px;
      border-color: rgba(100, 232, 221, 0.1);
    }
    .dst-preview-glow {
      position: absolute;
      left: 50%;
      top: 50%;
      width: 124px;
      height: 124px;
      transform: translate(-50%, -50%);
      border-radius: 50%;
      background: radial-gradient(circle, rgba(157, 113, 255, 0.26), rgba(100, 232, 221, 0.08) 42%, transparent 72%);
      filter: blur(16px);
      animation: dst-preview-glow 4.8s ease-in-out infinite;
    }
    .dst-preview-shell,
    .dst-preview-ring,
    .dst-preview-ring::before,
    .dst-preview-ring::after {
      position: absolute;
      left: 50%;
      top: 50%;
      transform: translate(-50%, -50%);
      border-radius: 50%;
    }
    .dst-preview-shell {
      width: 98px;
      height: 98px;
      border: 1px solid rgba(244, 242, 238, 0.08);
      box-shadow:
        inset 0 0 22px rgba(100, 232, 221, 0.08),
        0 0 28px rgba(157, 113, 255, 0.1);
      animation: dst-preview-shell 8s linear infinite;
    }
    .dst-preview-ring {
      width: 116px;
      height: 116px;
      border: 1px solid rgba(229, 203, 134, 0.18);
      animation: dst-preview-rotate 9s linear infinite;
    }
    .dst-preview-ring::before,
    .dst-preview-ring::after {
      content: "";
      inset: 0;
      border: inherit;
    }
    .dst-preview-ring::before {
      transform: translate(-50%, -50%) rotateX(72deg);
      opacity: 0.8;
    }
    .dst-preview-ring::after {
      transform: translate(-50%, -50%) rotateY(72deg);
      opacity: 0.56;
    }
    .dst-preview-core {
      position: absolute;
      left: 50%;
      top: 50%;
      width: 46px;
      height: 46px;
      transform: translate(-50%, -50%);
      border-radius: 50%;
      background: radial-gradient(circle, #fffdf7 0, #f1d18b 26%, #5f35d5 76%, rgba(95, 53, 213, 0.08) 100%);
      box-shadow:
        0 0 28px rgba(229, 203, 134, 0.34),
        0 0 46px rgba(100, 232, 221, 0.16);
      animation: dst-preview-core 3.4s ease-in-out infinite;
    }
    .dst-preview-breath {
      position: absolute;
      left: 50%;
      top: 50%;
      width: 76px;
      height: 76px;
      transform: translate(-50%, -50%);
      border-radius: 50%;
      border: 1px solid rgba(100, 232, 221, 0.18);
      animation: dst-preview-breath 3.4s ease-in-out infinite;
    }
    .dst-preview-helix {
      position: absolute;
      inset: 0;
      animation: dst-preview-rotate-reverse 10s linear infinite;
    }
    .dst-preview-node {
      position: absolute;
      left: 50%;
      top: 50%;
      width: 7px;
      height: 7px;
      margin: -3.5px;
      border-radius: 50%;
      background: radial-gradient(circle, #fffaf0 0, var(--dst-gold) 36%, rgba(255,255,255,0) 100%);
      box-shadow: 0 0 12px rgba(229, 203, 134, 0.28);
      animation: dst-preview-node 4.8s ease-in-out infinite;
    }
    .dst-preview-node:nth-child(1) { transform: translate(-42px, -18px) scale(0.9); animation-delay: -0.2s; }
    .dst-preview-node:nth-child(2) { transform: translate(38px, -12px) scale(0.72); animation-delay: -1.1s; background: radial-gradient(circle, #eefefc 0, var(--dst-cyan) 42%, rgba(255,255,255,0) 100%); }
    .dst-preview-node:nth-child(3) { transform: translate(-30px, 22px) scale(0.78); animation-delay: -2.1s; background: radial-gradient(circle, #f5efff 0, var(--dst-violet) 42%, rgba(255,255,255,0) 100%); }
    .dst-preview-node:nth-child(4) { transform: translate(26px, 24px) scale(1.02); animation-delay: -2.8s; }
    .dst-preview-node:nth-child(5) { transform: translate(0px, -36px) scale(0.64); animation-delay: -3.4s; background: radial-gradient(circle, #eefefc 0, var(--dst-cyan) 42%, rgba(255,255,255,0) 100%); }
    .dst-preview-node:nth-child(6) { transform: translate(2px, 38px) scale(0.82); animation-delay: -4.2s; background: radial-gradient(circle, #f5efff 0, var(--dst-violet) 42%, rgba(255,255,255,0) 100%); }
    .dst-empty-caption {
      position: absolute;
      left: 12px;
      right: 12px;
      bottom: 10px;
      display: flex;
      justify-content: space-between;
      gap: 10px;
      font-size: 10px;
      letter-spacing: 0.06em;
      text-transform: uppercase;
      color: rgba(244, 242, 238, 0.42);
    }
    @keyframes dst-preview-core {
      0%, 100% { transform: translate(-50%, -50%) scale(0.92); }
      45% { transform: translate(-50%, -50%) scale(1.08); }
      70% { transform: translate(-50%, -50%) scale(0.98); }
    }
    @keyframes dst-preview-breath {
      0% { transform: translate(-50%, -50%) scale(0.72); opacity: 0.78; }
      70% { transform: translate(-50%, -50%) scale(1.18); opacity: 0; }
      100% { opacity: 0; }
    }
    @keyframes dst-preview-rotate {
      from { transform: translate(-50%, -50%) rotate(0deg); }
      to { transform: translate(-50%, -50%) rotate(360deg); }
    }
    @keyframes dst-preview-rotate-reverse {
      from { transform: rotate(360deg); }
      to { transform: rotate(0deg); }
    }
    @keyframes dst-preview-shell {
      0%, 100% { transform: translate(-50%, -50%) scale(0.96) rotate(0deg); }
      50% { transform: translate(-50%, -50%) scale(1.04) rotate(180deg); }
    }
    @keyframes dst-preview-node {
      0%, 100% { opacity: 0.48; filter: blur(0px); }
      50% { opacity: 1; filter: blur(0.2px); }
    }
    @keyframes dst-preview-glow {
      0%, 100% { opacity: 0.72; transform: translate(-50%, -50%) scale(0.92); }
      50% { opacity: 1; transform: translate(-50%, -50%) scale(1.08); }
    }
    .dst-ritual[hidden] { display: none !important; }
    .dst-ritual {
      position: absolute;
      inset: 0;
      z-index: 7;
      display: grid;
      place-items: center;
      background:
        radial-gradient(circle at 50% 45%, rgba(229, 203, 134, 0.08), rgba(2, 3, 8, 0.92) 46%),
        rgba(3, 4, 8, 0.72);
      backdrop-filter: blur(10px);
    }
    .dst-ritual-card {
      width: min(460px, calc(100vw - 34px));
      padding: 22px 24px;
      border-radius: 24px;
      border: 1px solid rgba(255, 255, 255, 0.12);
      background: linear-gradient(180deg, rgba(8, 8, 11, 0.9), rgba(6, 8, 14, 0.74));
      box-shadow: 0 26px 84px rgba(0, 0, 0, 0.46);
    }
    .dst-ritual-kicker {
      color: var(--dst-gold);
      letter-spacing: 0.18em;
      font-size: 10px;
      text-transform: uppercase;
    }
    .dst-ritual-phase {
      margin-top: 10px;
      font-size: clamp(24px, 3vw, 34px);
      line-height: 1.1;
      color: #f9f5ef;
    }
    .dst-ritual-copy {
      margin-top: 10px;
      font-size: 13px;
      line-height: 1.75;
      color: rgba(244, 242, 238, 0.7);
    }
    .dst-ritual-track {
      margin-top: 16px;
      height: 6px;
      border-radius: 999px;
      overflow: hidden;
      background: rgba(255, 255, 255, 0.08);
    }
    .dst-ritual-fill {
      display: block;
      width: 8%;
      height: 100%;
      border-radius: inherit;
      background: linear-gradient(90deg, var(--dst-gold), var(--dst-cyan), var(--dst-violet));
      box-shadow: 0 0 20px rgba(229, 203, 134, 0.28);
      transition: width 0.45s ease;
    }
    .dst-ritual-meta {
      margin-top: 10px;
      display: flex;
      justify-content: space-between;
      gap: 12px;
      font-size: 11px;
      color: rgba(244, 242, 238, 0.48);
    }
    .dst-footer {
      position: absolute;
      left: 28px;
      right: 28px;
      bottom: 18px;
      display: flex;
      justify-content: space-between;
      gap: 12px;
      z-index: 5;
      color: rgba(244, 242, 238, 0.48);
      font-size: 12px;
      pointer-events: none;
    }
    .dst-root.dst-exporting .dst-topbar,
    .dst-root.dst-exporting .dst-panel,
    .dst-root.dst-exporting .dst-footer,
    .dst-root.dst-exporting .dst-empty-state {
      opacity: 0;
      pointer-events: none;
    }
    @media (max-width: 760px) {
      .dst-topbar {
        left: 14px;
        right: 14px;
        top: 14px;
        flex-direction: column;
      }
      .dst-topbar p { max-width: 100%; }
      .dst-panel {
        left: 12px;
        right: 12px;
        top: auto;
        bottom: 70px;
        width: auto;
        max-height: 48vh;
        border-radius: 22px;
      }
      .dst-empty-state {
        left: 12px;
        right: 12px;
        bottom: calc(48vh + 86px);
        max-width: none;
      }
      .dst-empty-preview {
        height: 108px;
      }
      .dst-footer {
        left: 14px;
        right: 14px;
        bottom: 10px;
        flex-direction: column;
        gap: 4px;
      }
    }
  `;
  document.head.appendChild(style);
}

class DivineSoulTopology {
  constructor(data, persistedState = null) {
    this.data = data;
    this.decisionId = getDecisionId(data);
    this.storageId = getSoulStorageId(this.decisionId);
    this.persistedState = persistedState || {};
    this.device = getDeviceProfile();
    this.root = null;
    this.scene = null;
    this.camera = null;
    this.renderer = null;
    this.composer = null;
    this.bloomPass = null;
    this.controls = null;
    this.THREE = null;
    this.ParametricGeometry = null;
    this.GLTFExporter = null;
    this.raf = 0;
    this.startedAt = performance.now();
    this.sceneTimeOffset = safeNumber(this.persistedState.topology?.evolutionClock, 0);
    this.storyText = compactText(this.persistedState.storyText, '');
    this.voiceTranscript = compactText(this.persistedState.voice?.transcript, '');
    this.voiceRecordings = Array.isArray(this.persistedState.voice?.recordings) ? this.persistedState.voice.recordings : [];
    this.photos = Array.isArray(this.persistedState.photos) ? this.persistedState.photos : [];
    this.filterMode = this.persistedState.filterMode || 'essence';
    this.blueprint = this.persistedState.topology?.blueprint || null;
    this.generationCount = safeNumber(this.persistedState.generationCount, this.blueprint ? 1 : 0);
    this.lastSavedAt = this.persistedState.updatedAt || '';
    this.freeFlightEnabled = Boolean(this.persistedState.freeFlightEnabled);
    this.cameraRestore = this.persistedState.camera || null;
    this.voiceRecorder = null;
    this.voiceChunks = [];
    this.voiceStream = null;
    this.voiceRecognition = null;
    this.voiceAudioContext = null;
    this.voiceAnalyser = null;
    this.voiceData = null;
    this.voiceFrame = 0;
    this.voiceStartedAt = 0;
    this.voiceMeterLevel = 0;
    this.voiceAccumulatedEnergy = 0;
    this.voiceSamples = 0;
    this.voiceActive = false;
    this.keyState = {};
    this.freeFlightLook = { yaw: 0, pitch: 0 };
    this.freeFlightPointer = { active: false, x: 0, y: 0 };
    this.lastOrbitTarget = null;
    this.saveTimer = 0;
    this.videoCapture = null;
    this.isExporting = false;
    this.sculptureGroup = null;
    this.backgroundStars = null;
    this.growthAnimation = null;
    this.filterProfiles = {
      essence: {
        label: '灵魂本质',
        lightA: 2.8,
        lightB: 1.7,
        lightC: 1.1,
        shellOpacity: 0.32,
        coreBoost: 1,
        particleFlow: 0.5,
        autoRotate: 0.34,
        fog: 0.028,
        bloomStrength: 0.92,
        bloomRadius: 0.72,
        bloomThreshold: 0.1,
      },
      destiny: {
        label: '命运拓扑',
        lightA: 2.1,
        lightB: 1.4,
        lightC: 1.9,
        shellOpacity: 0.42,
        coreBoost: 0.88,
        particleFlow: 0.86,
        autoRotate: 0.24,
        fog: 0.024,
        bloomStrength: 1.12,
        bloomRadius: 0.82,
        bloomThreshold: 0.08,
      },
      existential: {
        label: '存在主义模式',
        lightA: 1.4,
        lightB: 2.1,
        lightC: 2.3,
        shellOpacity: 0.2,
        coreBoost: 0.74,
        particleFlow: 1.18,
        autoRotate: 0.16,
        fog: 0.036,
        bloomStrength: 1.36,
        bloomRadius: 0.94,
        bloomThreshold: 0.04,
      },
    };
    this.onResize = this.onResize.bind(this);
    this.onKeyDown = this.onKeyDown.bind(this);
    this.onKeyUp = this.onKeyUp.bind(this);
    this.onCanvasPointerDown = this.onCanvasPointerDown.bind(this);
    this.onCanvasPointerMove = this.onCanvasPointerMove.bind(this);
    this.onCanvasPointerUp = this.onCanvasPointerUp.bind(this);
  }

  getSceneTime() {
    return this.sceneTimeOffset + ((performance.now() - this.startedAt) / 1000);
  }

  getFilterProfile(mode = this.filterMode) {
    return this.filterProfiles[mode] || this.filterProfiles.essence;
  }

  getStoryInputProfile() {
    return {
      storyText: this.storyText,
      voiceTranscript: this.voiceTranscript,
      voiceRecordings: this.voiceRecordings,
      photos: this.photos,
    };
  }

  buildTemplate() {
    return `
      <section class="dst-shell" role="dialog" aria-modal="true" aria-label="Divine Soul Topology">
        <canvas class="dst-canvas" data-dst-canvas></canvas>
        <header class="dst-topbar">
          <div>
            <div class="dst-kicker">Divine Soul Topology</div>
            <h2>神魂拓扑</h2>
            <p data-dst-question></p>
          </div>
          <div class="dst-mode-switch">
            <button type="button" data-dst-close>理性模式</button>
            <button type="button" data-dst-open-quantum>量子诗意模式</button>
            <button type="button" class="is-active" data-dst-current>神魂拓扑</button>
          </div>
        </header>
        <aside class="dst-panel">
          <section class="dst-section">
            <div class="dst-section-head">
              <span>灵魂输入</span>
              <small data-dst-save-copy>等待生成</small>
            </div>
            <textarea class="dst-story" data-dst-story placeholder="输入人生关键节点、遗憾、转折、声音片段、一个表情背后的故事，或任何你不曾说出口的私密叙事。"></textarea>
            <div class="dst-context" data-dst-context></div>
            <div class="dst-voice-row">
              <button type="button" class="dst-voice-button" data-dst-voice-toggle>开始语音录入</button>
              <button type="button" class="dst-voice-button" data-dst-voice-clear>清空语音</button>
            </div>
            <div class="dst-voice-meter"><span data-dst-voice-meter></span></div>
            <div class="dst-voice-status" data-dst-voice-status>浏览器支持时会本地转写语音，同时提取声纹能量，不上传音频。</div>
            <div class="dst-transcript" data-dst-transcript>还没有语音片段。</div>
            <input type="file" accept="image/*" multiple hidden data-dst-photo-input>
            <div class="dst-photo-row">
              <button type="button" class="dst-photo-trigger" data-dst-photo-trigger>上传照片</button>
              <div class="dst-renderer-copy" data-dst-photo-copy>还没有照片输入。</div>
            </div>
            <div class="dst-photo-grid" data-dst-photo-grid></div>
            <button type="button" class="dst-primary" data-dst-generate>生成神魂拓扑</button>
          </section>

          <section class="dst-section">
            <div class="dst-section-head">
              <span>策展说明</span>
              <small>把决策上下文翻译成可观看的人话</small>
            </div>
            <div class="dst-curation-grid" data-dst-curation></div>
          </section>

          <section class="dst-section">
            <div class="dst-section-head">
              <span>神性滤镜</span>
              <small>切换雕塑的光学人格</small>
            </div>
            <div class="dst-filter-list">
              <button type="button" class="dst-filter-button" data-dst-filter="essence">灵魂本质</button>
              <button type="button" class="dst-filter-button" data-dst-filter="destiny">命运拓扑</button>
              <button type="button" class="dst-filter-button" data-dst-filter="existential">存在主义模式</button>
            </div>
          </section>

          <section class="dst-section">
            <div class="dst-section-head">
              <span>交互与导出</span>
              <small data-dst-renderer-copy>准备渲染器...</small>
            </div>
            <div class="dst-tool-grid">
              <button type="button" class="dst-tool-button" data-dst-flight-toggle>开启自由飞行</button>
              <button type="button" class="dst-tool-button" data-dst-frame>回到雕塑中心</button>
              <button type="button" class="dst-tool-button" data-dst-export="4k">导出 4K 艺术图</button>
              <button type="button" class="dst-tool-button" data-dst-export="8k">导出 8K 艺术图</button>
              <button type="button" class="dst-tool-button" data-dst-export="video">导出 10 秒视频</button>
              <button type="button" class="dst-tool-button" data-dst-export="glb">导出 GLB</button>
            </div>
          </section>

          <section class="dst-section">
            <div class="dst-section-head">
              <span>演化状态</span>
              <small>IndexedDB 自动续写</small>
            </div>
            <div class="dst-stats" data-dst-stats></div>
          </section>
        </aside>

        <div class="dst-empty-state" data-dst-empty-state>
          <div class="dst-empty-preview" aria-hidden="true">
            <div class="dst-preview-glow"></div>
            <div class="dst-preview-shell"></div>
            <div class="dst-preview-ring"></div>
            <div class="dst-preview-core"></div>
            <div class="dst-preview-breath"></div>
            <div class="dst-preview-helix">
              <span class="dst-preview-node"></span>
              <span class="dst-preview-node"></span>
              <span class="dst-preview-node"></span>
              <span class="dst-preview-node"></span>
              <span class="dst-preview-node"></span>
              <span class="dst-preview-node"></span>
            </div>
            <div class="dst-empty-caption">
              <span>WARMING THE SCULPTURE</span>
              <span>GOLD / SILVER / CYAN / VIOLET</span>
            </div>
          </div>
          <div class="dst-empty-copy">
            <strong>神魂拓扑尚未显现</strong>
            <p>先输入一段关键人生叙事，或直接用当前决策上下文生成。</p>
            <p>预热中的几何体会先轻微呼吸，等你确认输入后，再长成真正的球体、环面、螺旋与拓扑曲面。</p>
          </div>
        </div>

        <div class="dst-ritual" data-dst-ritual hidden>
          <div class="dst-ritual-card">
            <div class="dst-ritual-kicker">Soul Generation Ritual</div>
            <div class="dst-ritual-phase" data-dst-ritual-phase>折叠叙事</div>
            <div class="dst-ritual-copy" data-dst-ritual-copy>把人生节点、照片光谱与声音起伏压缩成可生成的神性结构。</div>
            <div class="dst-ritual-track"><span class="dst-ritual-fill" data-dst-ritual-fill></span></div>
            <div class="dst-ritual-meta">
              <span data-dst-ritual-step>Phase 1 / 4</span>
              <span data-dst-ritual-mark>黑金展厅正在点亮</span>
            </div>
          </div>
        </div>

        <footer class="dst-footer">
          <span>拖拽旋转 · 滚轮缩放 · 右键平移 · F 键自由飞行</span>
          <span data-dst-footer-copy>黑金空间正在等待你的神性结构。</span>
        </footer>
      </section>
    `;
  }

  async mount() {
    ensureStyles();
    this.root = document.createElement('div');
    this.root.className = 'dst-root';
    this.root.innerHTML = this.buildTemplate();
    document.body.appendChild(this.root);
    document.body.style.overflow = 'hidden';

    this.root.querySelector('[data-dst-question]').textContent = this.data.question || '当前决策';
    this.root.querySelector('[data-dst-story]').value = this.storyText;
    this.renderContextHighlights();
    this.renderCuratorialNotes();
    this.renderVoiceTranscript();
    this.renderPhotoGrid();
    this.renderStats();
    this.updateSaveCopy(this.lastSavedAt ? `已恢复 ${new Date(this.lastSavedAt).toLocaleString('zh-CN')}` : '等待生成');

    this.bindUi();
    await this.setupThree();
    this.applyFilterMode(this.filterMode, { immediate: true });

    if (this.blueprint) {
      this.rebuildSculpture(this.blueprint, { persist: false, announce: false });
      this.root.querySelector('[data-dst-empty-state]').hidden = true;
      this.updateFooter('已恢复上次神魂拓扑，雕塑正在继续演化。');
    }

    this.saveTimer = window.setInterval(() => {
      this.saveState({ heartbeatAt: new Date().toISOString() });
    }, 10000);

    await this.saveState({
      openedAt: new Date().toISOString(),
      openCount: safeNumber(this.persistedState.openCount, 0) + 1,
    });
    this.animate();
  }

  bindUi() {
    this.root.querySelector('[data-dst-close]')?.addEventListener('click', () => this.close());
    this.root.querySelector('[data-dst-open-quantum]')?.addEventListener('click', () => this.switchToQuantumMode());
    this.root.querySelector('[data-dst-current]')?.addEventListener('click', () => showToast('当前已处于神魂拓扑模式。', 'info', 1400));
    this.root.querySelector('[data-dst-story]')?.addEventListener('input', (event) => {
      this.storyText = String(event.currentTarget.value || '');
      this.renderCuratorialNotes();
      this.renderStats();
    });
    this.root.querySelector('[data-dst-photo-trigger]')?.addEventListener('click', () => {
      this.root.querySelector('[data-dst-photo-input]')?.click();
    });
    this.root.querySelector('[data-dst-photo-input]')?.addEventListener('change', (event) => this.handlePhotoInput(event));
    this.root.querySelector('[data-dst-voice-toggle]')?.addEventListener('click', () => this.toggleVoiceCapture());
    this.root.querySelector('[data-dst-voice-clear]')?.addEventListener('click', () => this.clearVoiceInputs());
    this.root.querySelector('[data-dst-generate]')?.addEventListener('click', () => this.generateTopology());
    this.root.querySelectorAll('[data-dst-filter]').forEach((button) => {
      button.addEventListener('click', () => this.applyFilterMode(button.dataset.dstFilter || 'essence'));
    });
    this.root.querySelector('[data-dst-flight-toggle]')?.addEventListener('click', () => this.toggleFreeFlight());
    this.root.querySelector('[data-dst-frame]')?.addEventListener('click', () => this.frameSculpture(false));
    this.root.querySelectorAll('[data-dst-export]').forEach((button) => {
      button.addEventListener('click', () => this.handleExport(button.dataset.dstExport || '4k'));
    });
    const canvas = this.root.querySelector('[data-dst-canvas]');
    canvas?.addEventListener('pointerdown', this.onCanvasPointerDown);
    canvas?.addEventListener('pointermove', this.onCanvasPointerMove);
    canvas?.addEventListener('pointerup', this.onCanvasPointerUp);
    canvas?.addEventListener('pointercancel', this.onCanvasPointerUp);
    canvas?.addEventListener('pointerleave', this.onCanvasPointerUp);
    window.addEventListener('resize', this.onResize, { passive: true });
    window.addEventListener('keydown', this.onKeyDown);
    window.addEventListener('keyup', this.onKeyUp);
  }

  renderContextHighlights() {
    const mount = this.root?.querySelector('[data-dst-context]');
    if (!mount) return;
    const highlights = buildContextHighlights(this.data);
    mount.innerHTML = highlights.map((item) => `<span class="dst-context-chip">${escapeHtml(item)}</span>`).join('');
  }

  renderCuratorialNotes() {
    const mount = this.root?.querySelector('[data-dst-curation]');
    if (!mount) return;
    const notes = buildCuratorialNotes(this.data, this.blueprint, this.getStoryInputProfile(), this.getFilterProfile().label);
    mount.innerHTML = notes.map((item) => `
      <article class="dst-curation-card">
        <div class="dst-curation-eyebrow">${escapeHtml(item.eyebrow)}</div>
        <div class="dst-curation-title">${escapeHtml(item.title)}</div>
        <div class="dst-curation-body">${escapeHtml(item.body)}</div>
      </article>
    `).join('');
  }

  renderVoiceTranscript() {
    const transcript = this.root?.querySelector('[data-dst-transcript]');
    if (!transcript) return;
    const clipCount = this.voiceRecordings.length;
    const header = clipCount ? `语音片段 ${clipCount} 段` : '还没有语音片段。';
    const text = compactText(this.voiceTranscript);
    transcript.innerHTML = text
      ? `<strong>${escapeHtml(header)}</strong><br>${escapeHtml(text)}`
      : escapeHtml(header);
  }

  renderPhotoGrid() {
    const grid = this.root?.querySelector('[data-dst-photo-grid]');
    const copy = this.root?.querySelector('[data-dst-photo-copy]');
    if (!grid || !copy) return;
    copy.textContent = this.photos.length
      ? `已载入 ${this.photos.length} 张图像，照片色温与对比度会进入雕塑生成参数。`
      : '还没有照片输入。';
    if (!this.photos.length) {
      grid.innerHTML = '';
      return;
    }
    grid.innerHTML = this.photos.map((photo) => `
      <div class="dst-photo-card">
        <img src="${photo.dataUrl}" alt="${escapeHtml(photo.name || '神魂照片')}">
        <button type="button" class="dst-photo-remove" data-dst-remove-photo="${photo.id}" aria-label="移除照片">×</button>
        <div class="dst-photo-meta">
          <span>${escapeHtml(photo.name || '未命名照片')}</span>
          <span>亮度 ${Math.round(safeNumber(photo.metrics?.brightness, 0.5) * 100)} · 对比 ${Math.round(safeNumber(photo.metrics?.contrast, 0.3) * 100)}</span>
        </div>
      </div>
    `).join('');
    grid.querySelectorAll('[data-dst-remove-photo]').forEach((button) => {
      button.addEventListener('click', () => {
        this.photos = this.photos.filter((item) => item.id !== button.dataset.dstRemovePhoto);
        this.renderPhotoGrid();
        this.renderCuratorialNotes();
        this.renderStats();
      });
    });
  }

  renderStats() {
    const mount = this.root?.querySelector('[data-dst-stats]');
    if (!mount) return;
    const eventCount = this.blueprint?.events?.length || extractNarrativeEvents(this.data, this.getStoryInputProfile()).length;
    const photoCount = this.photos.length;
    const voiceCount = this.voiceRecordings.length;
    const modeLabel = this.getFilterProfile().label;
    const evolutionMinutes = Math.max(0, Math.round(this.getSceneTime() / 60));
    const inputLayers = [
      this.storyText ? '文字' : '',
      this.voiceRecordings.length ? '声音' : '',
      this.photos.length ? '图像' : '',
    ].filter(Boolean);
    mount.innerHTML = `
      <div class="dst-stat"><span>几何枝系</span><strong>${eventCount}</strong></div>
      <div class="dst-stat"><span>神性滤镜</span><strong>${escapeHtml(modeLabel)}</strong></div>
      <div class="dst-stat"><span>输入图层</span><strong>${escapeHtml(inputLayers.join(' / ') || '仅上下文')}</strong></div>
      <div class="dst-stat"><span>照片输入</span><strong>${photoCount} 张</strong></div>
      <div class="dst-stat"><span>语音片段</span><strong>${voiceCount} 段</strong></div>
      <div class="dst-stat"><span>演化时长</span><strong>${evolutionMinutes ? `${evolutionMinutes} 分钟` : '刚刚开始'}</strong></div>
      <div class="dst-stat"><span>生成次数</span><strong>${Math.max(this.generationCount, this.blueprint ? 1 : 0)}</strong></div>
      <div class="dst-stat"><span>保存状态</span><strong>${this.lastSavedAt ? '已续写' : '未生成'}</strong></div>
    `;
  }

  updateSaveCopy(copy) {
    const node = this.root?.querySelector('[data-dst-save-copy]');
    if (node) node.textContent = copy;
  }

  updateRendererCopy(copy) {
    const node = this.root?.querySelector('[data-dst-renderer-copy]');
    if (node) node.textContent = copy;
  }

  updateFooter(copy) {
    const node = this.root?.querySelector('[data-dst-footer-copy]');
    if (node) node.textContent = copy;
  }

  syncFreeFlightUi() {
    const button = this.root?.querySelector('[data-dst-flight-toggle]');
    if (button) button.textContent = this.freeFlightEnabled ? '退出自由飞行' : '开启自由飞行';
    this.root?.classList.toggle('is-free-flight', this.freeFlightEnabled);
    if (!this.controls) return;
    this.controls.enablePan = !this.freeFlightEnabled;
    this.controls.autoRotate = !this.freeFlightEnabled;
    this.controls.enabled = !this.freeFlightEnabled;
  }

  updateRitualStage({ phase, copy, stepLabel, mark, progress }) {
    const overlay = this.root?.querySelector('[data-dst-ritual]');
    if (!overlay) return;
    overlay.hidden = false;
    const phaseNode = overlay.querySelector('[data-dst-ritual-phase]');
    const copyNode = overlay.querySelector('[data-dst-ritual-copy]');
    const stepNode = overlay.querySelector('[data-dst-ritual-step]');
    const markNode = overlay.querySelector('[data-dst-ritual-mark]');
    const fillNode = overlay.querySelector('[data-dst-ritual-fill]');
    if (phaseNode) phaseNode.textContent = phase;
    if (copyNode) copyNode.textContent = copy;
    if (stepNode) stepNode.textContent = stepLabel;
    if (markNode) markNode.textContent = mark;
    if (fillNode) fillNode.style.width = `${Math.round(progress * 100)}%`;
  }

  async runGenerationRitual(blueprint) {
    const steps = [
      {
        phase: '折叠叙事',
        copy: '把人生节点、照片光谱与声音起伏压缩成可生成的神性结构。',
        stepLabel: 'Phase 1 / 4',
        mark: '黑金展厅正在点亮',
        progress: 0.18,
        duration: 420,
      },
      {
        phase: '提纯命运张力',
        copy: `识别 ${blueprint.events.length} 条关键枝系，决定是生长成环、球体、螺旋还是拓扑曲面。`,
        stepLabel: 'Phase 2 / 4',
        mark: '命运枝系正在分叉',
        progress: 0.46,
        duration: 520,
      },
      {
        phase: '铸造神性几何',
        copy: '将价值排序、情绪镜像与回撤预案重新铸造成一件可呼吸的雕塑。',
        stepLabel: 'Phase 3 / 4',
        mark: '核心壳层正在生长',
        progress: 0.76,
        duration: 620,
      },
      {
        phase: '展陈完成',
        copy: '光晕、粒子与拓扑曲面已经对齐，你可以开始观看它如何继续演化。',
        stepLabel: 'Phase 4 / 4',
        mark: '神魂拓扑已显现',
        progress: 1,
        duration: 360,
      },
    ];
    for (const step of steps) {
      this.updateRitualStage(step);
      await wait(step.duration);
    }
    const overlay = this.root?.querySelector('[data-dst-ritual]');
    if (overlay) overlay.hidden = true;
  }

  async setupThree() {
    const canvas = this.root.querySelector('[data-dst-canvas]');
    const {
      THREE,
      WebGPURenderer,
      OrbitControls,
      GLTFExporter,
      ParametricGeometry,
      EffectComposer,
      RenderPass,
      UnrealBloomPass,
    } = await loadThreeStack();
    this.THREE = THREE;
    this.ParametricGeometry = ParametricGeometry;
    this.GLTFExporter = GLTFExporter;

    this.scene = new THREE.Scene();
    this.scene.fog = new THREE.FogExp2(0x050506, this.getFilterProfile().fog);
    this.camera = new THREE.PerspectiveCamera(48, window.innerWidth / window.innerHeight, 0.1, 180);
    this.camera.position.set(0, 3.4, 8.6);

    try {
      if (WebGPURenderer && navigator.gpu) {
        this.renderer = new WebGPURenderer({ canvas, antialias: true, alpha: true });
        await this.renderer.init?.();
        this.rendererType = 'WebGPU';
      } else {
        throw new Error('WebGPU unavailable');
      }
    } catch (error) {
      console.warn('Divine Soul Topology fallback to WebGL.', error);
      this.renderer = new THREE.WebGLRenderer({
        canvas,
        antialias: true,
        alpha: true,
        powerPreference: 'high-performance',
      });
      this.rendererType = 'WebGL';
    }

    this.renderer.setPixelRatio(this.device.pixelRatio);
    this.renderer.setSize(window.innerWidth, window.innerHeight);
    this.renderer.setClearColor(0x020202, 1);
    this.renderer.toneMapping = THREE.ACESFilmicToneMapping;
    this.renderer.toneMappingExposure = 1.06;
    this.renderer.outputColorSpace = THREE.SRGBColorSpace;

    this.controls = new OrbitControls(this.camera, canvas);
    this.controls.enableDamping = true;
    this.controls.dampingFactor = 0.06;
    this.controls.enablePan = true;
    this.controls.autoRotate = true;
    this.controls.autoRotateSpeed = this.getFilterProfile().autoRotate;
    this.controls.minDistance = 2.8;
    this.controls.maxDistance = 18;

    this.addLights();
    this.backgroundStars = createBackgroundStars(
      THREE,
      this.blueprint?.palette || buildSoulPalette(this.getStoryInputProfile(), { probabilities: extractProbabilities(this.data) }),
      this.device.lowPower
    );
    this.scene.add(this.backgroundStars);
    if (this.rendererType === 'WebGL' && this.renderer instanceof THREE.WebGLRenderer) {
      this.composer = new EffectComposer(this.renderer);
      this.renderPass = new RenderPass(this.scene, this.camera);
      this.bloomPass = new UnrealBloomPass(new THREE.Vector2(window.innerWidth, window.innerHeight), 0.92, 0.72, 0.1);
      this.composer.addPass(this.renderPass);
      this.composer.addPass(this.bloomPass);
    }
    this.frameSculpture(true);
    this.syncFreeFlightUi();

    this.updateRendererCopy(`Renderer ${this.rendererType} · 粒子预算 ${this.device.particleBudget.toLocaleString()} · ${this.composer ? 'Bloom 已开启' : '高光辉光已就绪'}`);
  }

  addLights() {
    const THREE = this.THREE;
    this.scene.add(new THREE.AmbientLight(0x3f4054, 0.64));
    this.lightKey = new THREE.PointLight(0xe8cd8c, 2.8, 40);
    this.lightKey.position.set(0, 6, 5);
    this.lightCyan = new THREE.PointLight(0x59e7dc, 1.7, 36);
    this.lightCyan.position.set(-6, 2, 4);
    this.lightViolet = new THREE.PointLight(0x8f66ff, 1.1, 42);
    this.lightViolet.position.set(6, -1, -3);
    this.scene.add(this.lightKey, this.lightCyan, this.lightViolet);
  }

  applyFilterMode(mode, { immediate = false } = {}) {
    this.filterMode = mode || 'essence';
    this.root?.querySelectorAll('[data-dst-filter]').forEach((button) => {
      button.classList.toggle('is-active', button.dataset.dstFilter === this.filterMode);
    });
    const profile = this.getFilterProfile();
    if (this.controls) this.controls.autoRotateSpeed = profile.autoRotate;
    if (this.lightKey) this.lightKey.intensity = profile.lightA;
    if (this.lightCyan) this.lightCyan.intensity = profile.lightB;
    if (this.lightViolet) this.lightViolet.intensity = profile.lightC;
    if (this.scene?.fog) this.scene.fog.density = profile.fog;
    if (this.bloomPass) {
      this.bloomPass.strength = profile.bloomStrength;
      this.bloomPass.radius = profile.bloomRadius;
      this.bloomPass.threshold = profile.bloomThreshold;
    }
    if (this.sculptureGroup) {
      this.sculptureGroup.traverse((child) => {
        if (child.userData.dstRole === 'topology-shell' && child.material) {
          child.material.opacity = profile.shellOpacity;
        }
        if (child.userData.dstRole === 'core' && child.material) {
          child.material.emissiveIntensity = 0.42 * profile.coreBoost;
        }
      });
    }
    if (!immediate) {
      this.updateFooter(`${profile.label} 已开启，雕塑正在重写光影关系。`);
      this.renderCuratorialNotes();
      this.saveState({ filterMode: this.filterMode });
      this.renderStats();
    }
  }

  frameSculpture(instant = false) {
    if (!this.camera || !this.controls) return;
    const distance = this.blueprint ? 6.4 + (this.blueprint.events.length * 0.28) : 8.4;
    const target = new this.THREE.Vector3(0, 0.2, 0);
    const position = new this.THREE.Vector3(0, 2.8 + distance * 0.08, distance);
    if (this.cameraRestore?.position && this.cameraRestore?.target) {
      const storedPosition = new this.THREE.Vector3(...this.cameraRestore.position);
      const storedTarget = new this.THREE.Vector3(...this.cameraRestore.target);
      this.camera.position.copy(storedPosition);
      this.controls.target.copy(storedTarget);
      this.cameraRestore = null;
      this.controls.update();
      return;
    }
    if (instant) {
      this.camera.position.copy(position);
      this.controls.target.copy(target);
      this.controls.update();
      return;
    }
    this.camera.position.lerp(position, 0.9);
    this.controls.target.lerp(target, 0.9);
    this.controls.update();
  }

  async handlePhotoInput(event) {
    const files = Array.from(event.currentTarget.files || []);
    if (!files.length) return;
    this.updateFooter('正在分析照片的亮度、对比、色温与隐性光谱...');
    const processed = [];
    for (const file of files.slice(0, 4)) {
      try {
        processed.push(await processPhotoFile(file));
      } catch (error) {
        console.warn('Photo processing failed:', error);
      }
    }
    this.photos = [...this.photos, ...processed].slice(0, 6);
    this.renderPhotoGrid();
    this.renderCuratorialNotes();
    this.renderStats();
    event.currentTarget.value = '';
    await this.saveState({ photosUpdatedAt: new Date().toISOString() });
  }

  async clearVoiceInputs() {
    if (this.voiceActive) {
      await this.stopVoiceCapture({ keepTranscript: false });
    }
    this.voiceTranscript = '';
    this.voiceRecordings = [];
    this.voiceMeterLevel = 0;
    this.root.querySelector('[data-dst-voice-meter]').style.width = '0%';
    this.root.querySelector('[data-dst-voice-status]').textContent = '语音输入已清空。';
    this.renderVoiceTranscript();
    this.renderCuratorialNotes();
    this.renderStats();
    await this.saveState({ voiceClearedAt: new Date().toISOString() });
  }

  async toggleVoiceCapture() {
    if (this.voiceActive) {
      await this.stopVoiceCapture();
      return;
    }
    await this.startVoiceCapture();
  }

  async startVoiceCapture() {
    if (!navigator.mediaDevices?.getUserMedia) {
      showToast('当前浏览器不支持语音录入。', 'warning', 2600);
      return;
    }
    try {
      this.voiceStream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        },
      });
      this.voiceChunks = [];
      this.voiceStartedAt = performance.now();
      this.voiceAccumulatedEnergy = 0;
      this.voiceSamples = 0;
      this.voiceActive = true;

      if (window.MediaRecorder) {
        this.voiceRecorder = new MediaRecorder(this.voiceStream);
        this.voiceRecorder.ondataavailable = (event) => {
          if (event.data?.size) this.voiceChunks.push(event.data);
        };
        this.voiceRecorder.start(200);
      }

      const RecognitionClass = window.SpeechRecognition || window.webkitSpeechRecognition;
      if (RecognitionClass) {
        this.voiceRecognition = new RecognitionClass();
        this.voiceRecognition.lang = 'zh-CN';
        this.voiceRecognition.continuous = true;
        this.voiceRecognition.interimResults = true;
        this.voiceRecognition.onresult = (event) => {
          let finalText = '';
          let interimText = '';
          for (let i = event.resultIndex; i < event.results.length; i += 1) {
            const fragment = event.results[i][0]?.transcript || '';
            if (event.results[i].isFinal) finalText += fragment;
            else interimText += fragment;
          }
          if (finalText) {
            this.voiceTranscript = compactText(`${this.voiceTranscript} ${finalText}`.trim());
          }
          this.renderVoiceTranscript();
          const status = interimText
            ? `正在转写：${compactText(interimText).slice(0, 26)}`
            : '正在聆听你的声音与停顿。';
          this.root.querySelector('[data-dst-voice-status]').textContent = status;
        };
        this.voiceRecognition.onerror = () => {
          this.root.querySelector('[data-dst-voice-status]').textContent = '浏览器转写不可用，仍会保留声纹能量用于雕塑生成。';
        };
        this.voiceRecognition.start();
      } else {
        this.root.querySelector('[data-dst-voice-status]').textContent = '浏览器不支持实时转写，将仅提取声纹能量。';
      }

      const AudioContextClass = window.AudioContext || window.webkitAudioContext;
      if (AudioContextClass) {
        this.voiceAudioContext = new AudioContextClass();
        const source = this.voiceAudioContext.createMediaStreamSource(this.voiceStream);
        this.voiceAnalyser = this.voiceAudioContext.createAnalyser();
        this.voiceAnalyser.fftSize = 512;
        this.voiceData = new Uint8Array(this.voiceAnalyser.fftSize);
        source.connect(this.voiceAnalyser);
      }

      this.root.querySelector('[data-dst-voice-toggle]').textContent = '停止语音录入';
      this.root.querySelector('[data-dst-voice-status]').textContent = '语音录入已开启，声纹会实时写入神魂参数。';
      this.updateFooter('语音输入已开启，雕塑正在监听声音的起伏。');
      this.sampleVoiceMeter();
    } catch (error) {
      console.warn('Voice capture failed:', error);
      showToast(`语音录入失败：${error.message || error}`, 'warning', 3200);
      await this.stopVoiceCapture({ keepTranscript: true });
    }
  }

  sampleVoiceMeter() {
    if (!this.voiceAnalyser || !this.voiceData) return;
    this.voiceAnalyser.getByteTimeDomainData(this.voiceData);
    let energy = 0;
    for (let i = 0; i < this.voiceData.length; i += 1) {
      const normalized = (this.voiceData[i] - 128) / 128;
      energy += normalized * normalized;
    }
    const rms = Math.sqrt(energy / this.voiceData.length);
    this.voiceMeterLevel = clamp(rms * 6.5, 0, 1);
    this.voiceAccumulatedEnergy += this.voiceMeterLevel;
    this.voiceSamples += 1;
    const meter = this.root?.querySelector('[data-dst-voice-meter]');
    if (meter) meter.style.width = `${Math.round(this.voiceMeterLevel * 100)}%`;
    this.voiceFrame = requestAnimationFrame(() => this.sampleVoiceMeter());
  }

  async stopVoiceCapture({ keepTranscript = true } = {}) {
    this.voiceActive = false;
    cancelAnimationFrame(this.voiceFrame);
    this.voiceFrame = 0;

    if (this.voiceRecognition) {
      try {
        this.voiceRecognition.stop();
      } catch (error) {
        console.warn('Voice recognition stop failed:', error);
      }
      this.voiceRecognition = null;
    }

    const recorder = this.voiceRecorder;
    this.voiceRecorder = null;
    if (recorder) {
      await new Promise((resolve) => {
        recorder.onstop = () => resolve();
        try {
          recorder.stop();
        } catch (error) {
          resolve();
        }
      });
    }

    const duration = (performance.now() - this.voiceStartedAt) / 1000;
    const averageEnergy = this.voiceSamples
      ? clamp(this.voiceAccumulatedEnergy / this.voiceSamples, 0, 1)
      : clamp(this.voiceMeterLevel, 0.18, 0.32);
    if (keepTranscript && (duration > 0.4 || this.voiceTranscript)) {
      this.voiceRecordings = [
        ...this.voiceRecordings,
        {
          id: `voice-${Date.now()}`,
          duration: Math.round(duration * 10) / 10,
          energy: averageEnergy,
        },
      ].slice(-6);
    }

    this.voiceStream?.getTracks?.().forEach((track) => track.stop());
    this.voiceStream = null;
    this.voiceAudioContext?.close?.();
    this.voiceAudioContext = null;
    this.voiceAnalyser = null;
    this.voiceData = null;
    this.voiceChunks = [];
    this.voiceMeterLevel = 0;

    const meter = this.root?.querySelector('[data-dst-voice-meter]');
    if (meter) meter.style.width = '0%';
    const toggle = this.root?.querySelector('[data-dst-voice-toggle]');
    if (toggle) toggle.textContent = '开始语音录入';
    const status = this.root?.querySelector('[data-dst-voice-status]');
    if (status) status.textContent = keepTranscript
      ? '语音录入已结束，转写与声纹能量已保留在当前拓扑状态中。'
      : '语音录入已取消。';
    this.renderVoiceTranscript();
    this.renderCuratorialNotes();
    this.renderStats();
    await this.saveState({ voiceUpdatedAt: new Date().toISOString() });
  }

  async generateTopology() {
    const input = this.getStoryInputProfile();
    const nextBlueprint = buildSoulBlueprint(this.data, input, this.blueprint);
    this.updateFooter('正在折叠人生节点、照片光谱与声纹能量，生成神魂拓扑...');
    await this.runGenerationRitual(nextBlueprint);
    this.blueprint = nextBlueprint;
    this.generationCount += 1;
    this.rebuildSculpture(nextBlueprint, { persist: true, announce: true });
  }

  seedGrowthAnimation(animated) {
    if (!this.sculptureGroup || !this.THREE) return;
    this.growthAnimation = animated ? { startedAt: performance.now() } : null;
    this.sculptureGroup.traverse((child) => {
      const target = (child.userData.dstTargetScale || child.scale.clone());
      child.userData.dstTargetScale = target;
      if (!animated) {
        child.scale.copy(target);
        return;
      }
      let delay = 0;
      if (child.userData.dstRole === 'core') delay = 0.08;
      if (child.userData.dstRole === 'topology-shell') delay = 0.22;
      if (child.userData.dstRole === 'aura') delay = 0.32;
      if (child.userData.dstRole === 'ring') delay = 0.42;
      if (child.userData.dstRole === 'event-group') delay = child.userData.growDelay || 0.72;
      if (child.parent?.userData?.dstRole === 'event-group' && child.userData.dstRole !== 'event-group') {
        delay = (child.parent.userData.growDelay || 0.72) + 0.08;
      }
      child.userData.dstGrowDelay = delay;
      if (child.userData.dstRole !== 'background-stars' && child.userData.dstRole !== 'particles') {
        child.scale.copy(target.clone().multiplyScalar(0.001));
      }
    });
  }

  rebuildSculpture(blueprint, { persist = true, announce = true } = {}) {
    if (!this.scene || !this.THREE || !this.ParametricGeometry || !blueprint) return;
    if (this.sculptureGroup) {
      this.disposeObject(this.sculptureGroup);
      this.scene.remove(this.sculptureGroup);
      this.sculptureGroup = null;
    }
    this.sculptureGroup = createSoulSculpture(this.THREE, this.ParametricGeometry, blueprint, {
      device: this.device,
      rendererType: this.rendererType,
      includeParticles: true,
    });
    this.scene.add(this.sculptureGroup);
    this.seedGrowthAnimation(announce);
    this.root.querySelector('[data-dst-empty-state]').hidden = true;
    this.applyFilterMode(this.filterMode, { immediate: true });
    this.renderCuratorialNotes();
    this.frameSculpture(false);
    this.renderStats();
    if (announce) {
      showToast('神魂拓扑已显现，雕塑正在开始呼吸。', 'success', 2600);
      this.updateFooter('新的几何结构已经长出，粒子流向与光影关系正在重排。');
    }
    if (persist) {
      this.saveState({
        topologyGeneratedAt: new Date().toISOString(),
        generationCount: this.generationCount,
      });
    }
  }

  toggleFreeFlight() {
    this.freeFlightEnabled = !this.freeFlightEnabled;
    this.syncFreeFlightUi();
    if (this.freeFlightEnabled) {
      this.lastOrbitTarget = this.controls?.target?.clone?.() || null;
      const lookVector = (this.lastOrbitTarget || new this.THREE.Vector3(0, 0.2, 0)).clone().sub(this.camera.position).normalize();
      this.freeFlightLook.yaw = Math.atan2(lookVector.x, lookVector.z);
      this.freeFlightLook.pitch = Math.asin(clamp(lookVector.y, -0.98, 0.98));
      const closer = this.camera.position.clone().lerp((this.lastOrbitTarget || new this.THREE.Vector3(0, 0.2, 0)), 0.24);
      this.camera.position.copy(closer);
      this.updateFooter('自由飞行已开启：拖动鼠标转头，WASD / QE 穿过雕塑，Shift 加速。');
      showToast('自由飞行已开启：拖动鼠标转头。', 'info', 2200);
    } else {
      this.freeFlightPointer.active = false;
      if (this.lastOrbitTarget) this.controls.target.copy(this.lastOrbitTarget);
      this.updateFooter('已回到轨道漫游。');
      showToast('已退出自由飞行。', 'info', 1600);
    }
    this.saveState({ freeFlightEnabled: this.freeFlightEnabled });
  }

  onKeyDown(event) {
    const target = event.target;
    const isTypingTarget = Boolean(
      target
      && (
        target.tagName === 'INPUT'
        || target.tagName === 'TEXTAREA'
        || target.isContentEditable
      )
    );
    if (event.key.toLowerCase() === 'f' && !isTypingTarget) {
      event.preventDefault();
      this.toggleFreeFlight();
      return;
    }
    if (!this.freeFlightEnabled) return;
    this.keyState[event.key.toLowerCase()] = true;
  }

  onKeyUp(event) {
    delete this.keyState[event.key.toLowerCase()];
  }

  onCanvasPointerDown(event) {
    if (!this.freeFlightEnabled || event.button !== 0) return;
    this.freeFlightPointer.active = true;
    this.freeFlightPointer.x = event.clientX;
    this.freeFlightPointer.y = event.clientY;
  }

  onCanvasPointerMove(event) {
    if (!this.freeFlightEnabled || !this.freeFlightPointer.active) return;
    const dx = event.clientX - this.freeFlightPointer.x;
    const dy = event.clientY - this.freeFlightPointer.y;
    this.freeFlightPointer.x = event.clientX;
    this.freeFlightPointer.y = event.clientY;
    this.freeFlightLook.yaw += dx * 0.0032;
    this.freeFlightLook.pitch = clamp(this.freeFlightLook.pitch - dy * 0.0025, -1.28, 1.28);
  }

  onCanvasPointerUp() {
    this.freeFlightPointer.active = false;
  }

  async handleExport(kind) {
    if (!this.blueprint) {
      showToast('先生成一件神魂拓扑艺术装置，再导出。', 'warning', 2200);
      return;
    }
    if (this.isExporting) {
      showToast('导出任务正在进行，请稍候。', 'info', 1800);
      return;
    }
    this.isExporting = true;
    try {
      if (kind === 'glb') {
        await this.exportGlb();
      } else if (kind === 'video') {
        await this.exportLoopVideo();
      } else {
        await this.exportStill(kind);
      }
    } catch (error) {
      console.error('Divine Soul Topology export failed:', error);
      showToast(`导出失败：${error.message || error}`, 'error', 3800);
    } finally {
      this.isExporting = false;
    }
  }

  async exportStill(kind) {
    const resolution = getResolutionPreset(kind);
    const filename = `${sanitizeFilename(this.data.question)}-神魂拓扑-${resolution.label}-${formatExportTimestamp()}.png`;
    const dataUrl = await this.captureArtworkFrame(resolution.width, resolution.height);
    downloadBlob(new Blob([dataUrlToUint8Array(dataUrl)], { type: 'image/png' }), filename);
    showToast(`${resolution.label} 艺术图已导出。`, 'success', 2200);
    await this.saveState({ lastStillExportAt: new Date().toISOString(), lastStillExportKind: kind });
  }

  async exportLoopVideo() {
    const canvas = this.renderer?.domElement;
    if (!canvas?.captureStream || typeof MediaRecorder === 'undefined') {
      throw new Error('当前浏览器不支持画布视频导出。');
    }
    const mimeType = [
      'video/webm;codecs=vp9',
      'video/webm;codecs=vp8',
      'video/webm',
    ].find((item) => !MediaRecorder.isTypeSupported || MediaRecorder.isTypeSupported(item)) || 'video/webm';

    const width = 1920;
    const height = 1080;
    const originalPosition = this.camera.position.clone();
    const originalTarget = this.controls.target.clone();
    const originalAspect = this.camera.aspect;
    const originalAutoRotate = this.controls.autoRotate;
    const originalEnabled = this.controls.enabled;

    this.root.classList.add('dst-exporting');
    this.controls.enabled = false;
    this.controls.autoRotate = false;
    this.renderer.setPixelRatio(1);
    this.renderer.setSize(width, height);
    this.composer?.setSize(width, height);
    this.camera.aspect = width / height;
    this.camera.updateProjectionMatrix();

    const stream = canvas.captureStream(30);
    const recorder = new MediaRecorder(stream, { mimeType });
    const chunks = [];
    recorder.ondataavailable = (event) => {
      if (event.data?.size) chunks.push(event.data);
    };
    const stopped = new Promise((resolve) => {
      recorder.onstop = () => resolve();
    });

    try {
      const center = new this.THREE.Vector3(0, 0.18, 0);
      const radius = clamp(this.blueprint.core.shellRadius * 2.2, 6.2, 11.5);
      this.videoCapture = {
        center,
        radius,
        elevation: 2.6,
        startedAt: performance.now(),
        duration: 10000,
      };

      recorder.start(200);
      await new Promise((resolve) => window.setTimeout(resolve, 10200));
      this.videoCapture = null;
      recorder.stop();
      await stopped;
    } finally {
      this.videoCapture = null;
      stream.getTracks().forEach((track) => track.stop());
      this.renderer.setPixelRatio(this.device.pixelRatio);
      this.renderer.setSize(window.innerWidth, window.innerHeight);
      this.composer?.setSize(window.innerWidth, window.innerHeight);
      this.camera.aspect = originalAspect;
      this.camera.updateProjectionMatrix();
      this.camera.position.copy(originalPosition);
      this.controls.target.copy(originalTarget);
      this.controls.autoRotate = originalAutoRotate;
      this.controls.enabled = originalEnabled;
      this.root.classList.remove('dst-exporting');
    }

    const blob = new Blob(chunks, { type: 'video/webm' });
    const filename = `${sanitizeFilename(this.data.question)}-神魂拓扑-10s-loop-${formatExportTimestamp()}.webm`;
    downloadBlob(blob, filename);
    showToast('10 秒循环视频已导出。', 'success', 2600);
    await this.saveState({ lastVideoExportAt: new Date().toISOString() });
  }

  async exportGlb() {
    if (!this.GLTFExporter || !this.ParametricGeometry) {
      throw new Error('GLB 导出器尚未加载完成。');
    }
    const exporter = new this.GLTFExporter();
    const exportGroup = createSoulSculpture(this.THREE, this.ParametricGeometry, this.blueprint, {
      device: this.device,
      rendererType: 'WebGL',
      includeParticles: false,
    });
    const blob = await new Promise((resolve, reject) => {
      exporter.parse(
        exportGroup,
        (result) => {
          if (result instanceof ArrayBuffer) {
            resolve(new Blob([result], { type: 'model/gltf-binary' }));
          } else {
            resolve(new Blob([JSON.stringify(result)], { type: 'application/json' }));
          }
        },
        (error) => reject(error),
        { binary: true }
      );
    });
    const filename = `${sanitizeFilename(this.data.question)}-神魂拓扑-${formatExportTimestamp()}.glb`;
    downloadBlob(blob, filename);
    this.disposeObject(exportGroup);
    showToast('GLB 模型已导出。', 'success', 2200);
    await this.saveState({ lastGlbExportAt: new Date().toISOString() });
  }

  async captureArtworkFrame(width, height) {
    const canvas = this.renderer?.domElement;
    if (!canvas || !this.renderer || !this.camera) {
      throw new Error('雕塑尚未完成初始化。');
    }
    const originalAspect = this.camera.aspect;
    const originalSize = { width: window.innerWidth, height: window.innerHeight };
    this.root.classList.add('dst-exporting');
    try {
      this.renderer.setPixelRatio(1);
      this.renderer.setSize(width, height);
      this.composer?.setSize(width, height);
      this.camera.aspect = width / height;
      this.camera.updateProjectionMatrix();
      this.updateSceneFrame(this.getSceneTime());
      await new Promise((resolve) => requestAnimationFrame(resolve));
      this.updateSceneFrame(this.getSceneTime());
      return canvas.toDataURL('image/png', 1.0);
    } finally {
      this.renderer.setPixelRatio(this.device.pixelRatio);
      this.renderer.setSize(originalSize.width, originalSize.height);
      this.composer?.setSize(originalSize.width, originalSize.height);
      this.camera.aspect = originalAspect;
      this.camera.updateProjectionMatrix();
      this.root.classList.remove('dst-exporting');
    }
  }

  animate() {
    this.raf = requestAnimationFrame(() => this.animate());
    this.updateSceneFrame(this.getSceneTime());
  }

  updateSceneFrame(time) {
    if (!this.scene || !this.camera || !this.renderer) return;
    const profile = this.getFilterProfile();
    const breath = this.blueprint?.motion?.breath || 0.42;
    const drift = this.blueprint?.motion?.drift || 0.4;
    if (this.backgroundStars) {
      this.backgroundStars.rotation.y += 0.00016;
      this.backgroundStars.rotation.x = Math.sin(time * 0.06) * 0.04;
    }
    if (this.sculptureGroup) {
      this.sculptureGroup.rotation.y += 0.0012 + drift * 0.0006;
      this.sculptureGroup.traverse((child) => {
        const role = child.userData.dstRole;
        if (role === 'core') {
          const pulse = 1 + Math.sin(time * child.userData.pulseSpeed) * (0.05 + breath * 0.02);
          child.scale.setScalar(pulse);
          child.rotation.y += 0.004;
        } else if (role === 'topology-shell') {
          child.rotation.x = Math.sin(time * 0.22) * 0.16;
          child.rotation.y += child.userData.spinSpeed * (profile.particleFlow * 0.9);
        } else if (role === 'aura') {
          const auraPulse = 1 + Math.sin(time * 0.34) * 0.08;
          child.scale.setScalar(auraPulse);
        } else if (role === 'ring') {
          const wave = 1 + Math.sin(time * child.userData.waveSpeed) * 0.03;
          child.scale.setScalar(wave);
          child.rotation.z += 0.0018 * profile.particleFlow;
        } else if (role === 'event-group') {
          const angle = child.userData.baseAngle + time * child.userData.spinSpeed * profile.particleFlow;
          child.rotation.y = angle;
        } else if (role === 'event-artifact' || role === 'event-anchor') {
          const pulse = 1 + Math.sin(time * child.userData.pulseSpeed) * 0.08;
          child.scale.setScalar(pulse);
          child.rotation.y += child.userData.spinSpeed || 0.003;
        } else if (role === 'particles') {
          child.rotation.y += child.userData.spinSpeed * profile.particleFlow;
          if (child.userData.dstUniforms) {
            child.userData.dstUniforms.uTime.value = time;
            child.userData.dstUniforms.uFlow.value = profile.particleFlow;
            child.userData.dstUniforms.uPixelRatio.value = this.device.pixelRatio;
          } else if (child.material) {
            child.material.opacity = 0.44 + profile.particleFlow * 0.1;
          }
        }
      });
    }

    if (this.growthAnimation) {
      const elapsed = (performance.now() - this.growthAnimation.startedAt) / 1000;
      let pending = false;
      this.sculptureGroup?.traverse((child) => {
        const target = child.userData.dstTargetScale;
        if (!target || child.userData.dstRole === 'background-stars' || child.userData.dstRole === 'particles') return;
        const delay = safeNumber(child.userData.dstGrowDelay, 0);
        const normalized = clamp((elapsed - delay) / 0.9, 0, 1);
        const eased = 1 - ((1 - normalized) ** 3);
        if (normalized < 1) pending = true;
        child.scale.copy(target.clone().multiplyScalar(0.001 + eased * 0.999));
      });
      if (!pending) this.growthAnimation = null;
    }

    if (this.freeFlightEnabled) {
      const forward = new this.THREE.Vector3();
      forward.set(
        Math.sin(this.freeFlightLook.yaw) * Math.cos(this.freeFlightLook.pitch),
        Math.sin(this.freeFlightLook.pitch),
        Math.cos(this.freeFlightLook.yaw) * Math.cos(this.freeFlightLook.pitch),
      ).normalize();
      const right = new this.THREE.Vector3().crossVectors(forward, new this.THREE.Vector3(0, 1, 0)).normalize();
      const up = new this.THREE.Vector3(0, 1, 0);
      const velocity = new this.THREE.Vector3();
      const speed = this.keyState.shift ? 0.28 : 0.14;
      if (this.keyState.w) velocity.add(forward);
      if (this.keyState.s) velocity.sub(forward);
      if (this.keyState.a) velocity.sub(right);
      if (this.keyState.d) velocity.add(right);
      if (this.keyState.q) velocity.sub(up);
      if (this.keyState.e) velocity.add(up);
      if (velocity.lengthSq() > 0) {
        velocity.normalize().multiplyScalar(speed);
        this.camera.position.add(velocity);
      }
      this.camera.lookAt(this.camera.position.clone().add(forward));
    }

    if (this.videoCapture) {
      const progress = ((performance.now() - this.videoCapture.startedAt) % this.videoCapture.duration) / this.videoCapture.duration;
      const angle = progress * Math.PI * 2;
      const bob = Math.sin(progress * Math.PI * 4) * 0.26;
      this.camera.position.set(
        this.videoCapture.center.x + Math.cos(angle) * this.videoCapture.radius,
        this.videoCapture.center.y + this.videoCapture.elevation + bob,
        this.videoCapture.center.z + Math.sin(angle) * this.videoCapture.radius,
      );
      this.controls.target.copy(this.videoCapture.center);
    }

    if (!this.freeFlightEnabled) {
      this.controls?.update();
    }
    if (this.composer) this.composer.render();
    else this.renderer.render(this.scene, this.camera);
  }

  onResize() {
    if (!this.camera || !this.renderer) return;
    this.camera.aspect = window.innerWidth / window.innerHeight;
    this.camera.updateProjectionMatrix();
    this.renderer.setSize(window.innerWidth, window.innerHeight);
    this.composer?.setSize(window.innerWidth, window.innerHeight);
  }

  async saveState(extra = {}) {
    this.lastSavedAt = new Date().toISOString();
    this.persistedState = {
      ...this.persistedState,
      decisionId: this.storageId,
      sourceDecisionId: this.decisionId,
      question: this.data.question,
      storyText: this.storyText,
      filterMode: this.filterMode,
      freeFlightEnabled: this.freeFlightEnabled,
      voice: {
        transcript: this.voiceTranscript,
        recordings: this.voiceRecordings,
      },
      photos: this.photos.map((photo) => ({
        id: photo.id,
        name: photo.name,
        dataUrl: photo.dataUrl,
        width: photo.width,
        height: photo.height,
        metrics: photo.metrics,
      })),
      topology: this.blueprint
        ? {
          blueprint: this.blueprint,
          evolutionClock: this.getSceneTime(),
        }
        : null,
      camera: this.camera && this.controls
        ? {
          position: this.camera.position.toArray(),
          target: this.controls.target.toArray(),
        }
        : null,
      generationCount: this.generationCount,
      updatedAt: this.lastSavedAt,
      ...extra,
    };
    await savePersistedSoulState(this.persistedState);
    this.updateSaveCopy(`已自动保存 ${new Date(this.lastSavedAt).toLocaleString('zh-CN')}`);
    this.renderStats();
  }

  disposeObject(object) {
    object.traverse?.((child) => {
      child.geometry?.dispose?.();
      if (Array.isArray(child.material)) {
        child.material.forEach((material) => {
          material.map?.dispose?.();
          material.dispose?.();
        });
      } else {
        child.material?.map?.dispose?.();
        child.material?.dispose?.();
      }
    });
  }

  async switchToQuantumMode() {
    const data = this.data;
    await this.close({ silent: true });
    await window.openQuantumVibeOracle?.(data);
  }

  async close({ silent = false } = {}) {
    if (this.voiceActive) {
      await this.stopVoiceCapture();
    }
    await this.saveState({ closedAt: new Date().toISOString() });
    cancelAnimationFrame(this.raf);
    if (this.saveTimer) window.clearInterval(this.saveTimer);
    window.removeEventListener('resize', this.onResize);
    window.removeEventListener('keydown', this.onKeyDown);
    window.removeEventListener('keyup', this.onKeyUp);
    const canvas = this.root?.querySelector('[data-dst-canvas]');
    canvas?.removeEventListener('pointerdown', this.onCanvasPointerDown);
    canvas?.removeEventListener('pointermove', this.onCanvasPointerMove);
    canvas?.removeEventListener('pointerup', this.onCanvasPointerUp);
    canvas?.removeEventListener('pointercancel', this.onCanvasPointerUp);
    canvas?.removeEventListener('pointerleave', this.onCanvasPointerUp);
    this.controls?.dispose?.();
    if (this.sculptureGroup) this.disposeObject(this.sculptureGroup);
    if (this.backgroundStars) this.disposeObject(this.backgroundStars);
    this.composer?.dispose?.();
    this.renderer?.dispose?.();
    this.root?.remove();
    document.body.style.overflow = '';
    activeTopology = null;
    if (!silent) {
      showToast('已回到理性模式。', 'info', 1600);
    }
  }
}

function syncWebglQueryHint() {
  const params = new URLSearchParams(window.location.search);
  if (params.get('webgl') === '1') return;
  params.set('webgl', '1');
  const next = `${window.location.pathname}?${params.toString()}${window.location.hash || ''}`;
  window.history.replaceState({}, '', next);
}

export function registerDivineSoulTopology() {
  window.openDivineSoulTopology = async (explicitData) => {
    try {
      if (activeTopology) {
        showToast('神魂拓扑已经开启。', 'info', 1500);
        return activeTopology;
      }
      syncWebglQueryHint();
      const decisionData = getCurrentDecisionData(explicitData);
      window.decisionData = decisionData;
      const persisted = await loadPersistedSoulState(getDecisionId(decisionData));
      activeTopology = new DivineSoulTopology(decisionData, persisted);
      await activeTopology.mount();
      return activeTopology;
    } catch (error) {
      console.error('Divine Soul Topology failed to open:', error);
      activeTopology = null;
      showToast(`神魂拓扑启动失败：${error.message || error}`, 'error', 4200);
      return null;
    }
  };
  window.closeDivineSoulTopology = () => activeTopology?.close();
}
