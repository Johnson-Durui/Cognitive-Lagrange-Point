/**
 * Quantum Vibe Oracle
 * 量子 vibe 预言机：独立、懒加载的 Three.js/WebGPU + Web Audio + MediaPipe 体验层。
 *
 * 边界说明：
 * - 只读取当前 decisionData / state.currentDecision / state.engineBSession。
 * - 不修改决策引擎、Monte Carlo 计算、PDF 生成、三幕流程和后端逻辑。
 * - 所有重资源（Three、WebGPU、OrbitControls、MediaPipe）都在点击入口后动态加载。
 */

import { state } from '../core/state.js';
import { escapeHtml, showToast } from './utils.js';
import {
  extractProbabilities as extractSharedProbabilities,
  extractValidationMetrics as extractSharedValidationMetrics,
  getCurrentDecisionData as getSharedDecisionData,
  getDecisionId as getSharedDecisionId,
} from './art-experience/decision-data.js';
import { loadThreeExperienceStack } from './art-experience/three-loader.js';
import { getRecord, openIndexedDb, putRecord } from './art-experience/storage-base.js';

const DB_NAME = 'clp_quantum_vibe_oracle';
const DB_VERSION = 1;
const STORE_NAME = 'quantumStates';
const TEMPLATE_URL = new URL('../components/QuantumUniverseView.html', import.meta.url);
const MEDIAPIPE_WASM_URL = 'https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.34/wasm';
const FACE_MODEL_URL = 'https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/latest/face_landmarker.task';

let activeOracle = null;
let threeStackPromise = null;
let mediaPipePromise = null;

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
    return value.map((item) => {
      if (typeof item === 'string') return compactText(item);
      if (item && typeof item === 'object') {
        return compactText(item.summary || item.action || item.signal || item.title || item.label || item.content || item.core_insight || JSON.stringify(item));
      }
      return compactText(item);
    }).filter(Boolean).slice(0, limit);
  }
  if (value && typeof value === 'object') {
    return Object.values(value).flatMap((item) => listify(item, limit)).slice(0, limit);
  }
  return [compactText(value)].filter(Boolean).slice(0, limit);
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
    particleBudget: lowPower ? 26000 : 40000,
    pixelRatio: Math.min(pixelRatio, lowPower ? 1.25 : 1.75),
  };
}

function easeOutCubic(value) {
  const t = clamp(value, 0, 1);
  return 1 - ((1 - t) ** 3);
}

function getDecisionId(data) {
  return getSharedDecisionId(data, 'quantum-local');
}

function getCurrentDecisionData(explicitData) {
  return getSharedDecisionData(explicitData);
}

function extractProbabilities(data) {
  return extractSharedProbabilities(data);
}

function extractValidationMetrics(data) {
  return extractSharedValidationMetrics(data);
}

function collectTimelineHighlights(choice, limit = 3) {
  const timelines = choice?.timelines || {};
  const scenarios = ['tailwind', 'steady', 'headwind'];
  const lines = [];
  scenarios.forEach((scenario) => {
    const nodes = timelines?.[scenario]?.nodes || [];
    nodes.slice(0, 2).forEach((node) => {
      const text = compactText(node?.signal || node?.key_action || node?.external_state || node?.inner_feeling);
      if (text) lines.push(`${node?.time || scenario}：${text}`);
    });
  });
  return lines.slice(0, limit);
}

function buildUniverseStoryHighlights(data, key, fallbackLines = []) {
  const simulator = data.simulator_output || {};
  const choiceA = simulator.choice_a || {};
  const choiceB = simulator.choice_b || {};
  const thirdPath = simulator.third_path || data.engineb_session?.alternative_path || {};
  const storyMap = {
    A: [
      ...collectTimelineHighlights(choiceA, 3),
      ...listify(simulator.action_map_a, 2),
      ...listify(simulator.crossroads, 1),
    ],
    B: [
      ...collectTimelineHighlights(choiceB, 3),
      ...listify(simulator.action_map_b, 2),
      ...listify(simulator.final_insight, 1),
    ],
    C: [
      ...listify(thirdPath, 3),
      ...listify(simulator.worst_case_survival_plan, 2),
      ...listify(simulator.market_signals, 1),
    ],
  };
  const merged = [...storyMap[key], ...fallbackLines].filter(Boolean);
  return Array.from(new Set(merged)).slice(0, 5);
}

function buildUniverseData(data, persistedState = {}) {
  const probabilities = extractProbabilities(data);
  const metrics = extractValidationMetrics(data);
  const session = data.engineb_session || {};
  const simulator = data.simulator_output || {};
  const valueLines = listify(session.value_profile?.summary || session.value_profile?.top_values, 3);
  const emotionLines = listify(session.emotional_mirror || session.emotional_snapshot || session.b5_emotional_mirror, 3);
  const guardrails = listify(
    data.monte_carlo?.decision_guardrails
    || simulator.worst_case_survival_plan
    || session.worst_case_survival_plan,
    4,
  );
  const seedBase = `${getDecisionId(data)}:${data.question}:${JSON.stringify(metrics)}`;
  const drift = clamp((metrics.studyHours * 0.08) + (metrics.mockExam * 0.12) + (metrics.checkins * 0.5) + (persistedState.visitCount || 0), 0, 28);

  return [
    {
      id: 'universe-a',
      key: 'A',
      title: '宇宙A · 直接找工作',
      shortTitle: '直接找工作',
      probability: clamp(probabilities.a + drift * 0.12, 5, 90),
      color: 0x35d5ff,
      accent: '#35d5ff',
      position: [-8, 0, 0],
      sceneType: 'work',
      soundMode: 'stable',
      diary: [
        '第 18 天：平行自我把简历改成了三版，像把自己拆成三种可能性。',
        '第 47 天：第一份稳定收入像一颗冷静的星，照亮了现金流，但也压低了复习的振幅。',
        guardrails[0] ? `保护卡：${guardrails[0]}` : '保护卡：不要为了尽快稳定而牺牲长期选择权。',
      ],
      valueLines,
      emotionLines,
      storyHighlights: buildUniverseStoryHighlights(data, 'A', valueLines),
      seed: `${seedBase}:A`,
    },
    {
      id: 'universe-b',
      key: 'B',
      title: '宇宙B · 边工作边二战',
      shortTitle: '双轨路径',
      probability: clamp(probabilities.b + drift * 0.18, 5, 95),
      color: 0xf5c96b,
      accent: '#f5c96b',
      position: [0, 0.4, -2],
      sceneType: 'hybrid',
      soundMode: 'hopeful',
      diary: [
        '第 7 天：白天把现实稳住，夜里把未来重新点亮。',
        '第 52 天：平行自我开始相信，所谓双轨不是摇摆，而是给不确定性留一条缓冲带。',
        guardrails[1] ? `保护卡：${guardrails[1]}` : '保护卡：每周复盘一次体力、现金流和模考反馈，只在信号变绿时加码。',
      ],
      valueLines,
      emotionLines,
      storyHighlights: buildUniverseStoryHighlights(data, 'B', emotionLines),
      seed: `${seedBase}:B`,
      recommended: true,
    },
    {
      id: 'universe-c',
      key: 'C',
      title: '宇宙C · 全脱产二战',
      shortTitle: '全脱产二战',
      probability: clamp(probabilities.c - drift * 0.08, 3, 85),
      color: 0xd27bff,
      accent: '#d27bff',
      position: [8, 0, 0],
      sceneType: 'exam',
      soundMode: 'ethereal',
      diary: [
        '第 3 天：世界突然安静，安静到每一道题都像一次自我审判。',
        '第 66 天：专注让概率场变亮，但现金流的暗物质也在边缘聚集。',
        guardrails[2] ? `保护卡：${guardrails[2]}` : '保护卡：脱产前必须确认安全垫和失败后的回撤路径。',
      ],
      valueLines,
      emotionLines,
      storyHighlights: buildUniverseStoryHighlights(data, 'C', guardrails),
      seed: `${seedBase}:C`,
    },
  ];
}

function openQuantumDb() {
  return openIndexedDb(DB_NAME, DB_VERSION, (db) => {
    if (!db.objectStoreNames.contains(STORE_NAME)) {
      db.createObjectStore(STORE_NAME, { keyPath: 'decisionId' });
    }
  });
}

async function loadPersistedQuantumState(decisionId) {
  return getRecord(DB_NAME, DB_VERSION, STORE_NAME, decisionId, (db) => {
    if (!db.objectStoreNames.contains(STORE_NAME)) {
      db.createObjectStore(STORE_NAME, { keyPath: 'decisionId' });
    }
  });
}

async function savePersistedQuantumState(stateSnapshot) {
  await putRecord(DB_NAME, DB_VERSION, STORE_NAME, stateSnapshot, (db) => {
    if (!db.objectStoreNames.contains(STORE_NAME)) {
      db.createObjectStore(STORE_NAME, { keyPath: 'decisionId' });
    }
  });
}

function formatExportTimestamp(date = new Date()) {
  const pad = (value) => String(value).padStart(2, '0');
  return `${date.getFullYear()}${pad(date.getMonth() + 1)}${pad(date.getDate())}-${pad(date.getHours())}${pad(date.getMinutes())}${pad(date.getSeconds())}`;
}

function sanitizeFilename(value) {
  return compactText(value, '量子vibe').replace(/[<>:"/\\|?*\u0000-\u001F]+/g, '-');
}

function getResolutionPreset(key) {
  return {
    '2k': { width: 2560, height: 1440, label: '2K' },
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

function toBase64Utf8(text) {
  const bytes = new TextEncoder().encode(text);
  let binary = '';
  bytes.forEach((byte) => {
    binary += String.fromCharCode(byte);
  });
  return btoa(binary);
}

function crc32(bytes) {
  let crc = -1;
  for (let i = 0; i < bytes.length; i += 1) {
    crc ^= bytes[i];
    for (let bit = 0; bit < 8; bit += 1) {
      crc = (crc >>> 1) ^ (0xEDB88320 & -(crc & 1));
    }
  }
  return (crc ^ -1) >>> 0;
}

function buildPngTextChunk(keyword, text) {
  const encoder = new TextEncoder();
  const payload = encoder.encode(`${keyword}\0${text}`);
  const type = encoder.encode('tEXt');
  const chunk = new Uint8Array(4 + 4 + payload.length + 4);
  const view = new DataView(chunk.buffer);
  view.setUint32(0, payload.length);
  chunk.set(type, 4);
  chunk.set(payload, 8);
  view.setUint32(8 + payload.length, crc32(chunk.slice(4, 8 + payload.length)));
  return chunk;
}

function injectPngMetadata(dataUrl, metadata) {
  const bytes = dataUrlToUint8Array(dataUrl);
  const signature = bytes.slice(0, 8);
  const chunks = [];
  let offset = 8;
  while (offset < bytes.length) {
    const length = new DataView(bytes.buffer, bytes.byteOffset + offset, 4).getUint32(0);
    const chunkSize = 12 + length;
    const chunk = bytes.slice(offset, offset + chunkSize);
    const type = String.fromCharCode(...chunk.slice(4, 8));
    if (type === 'IEND') {
      chunks.push(buildPngTextChunk('CLPQuantumState', toBase64Utf8(JSON.stringify(metadata))));
    }
    chunks.push(chunk);
    offset += chunkSize;
  }
  return new Blob([signature, ...chunks], { type: 'image/png' });
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

function loadImageFromDataUrl(dataUrl) {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => resolve(img);
    img.onerror = reject;
    img.src = dataUrl;
  });
}

async function loadTemplate() {
  try {
    const response = await fetch(TEMPLATE_URL);
    if (response.ok) return response.text();
  } catch (error) {
    console.warn('Quantum template fetch failed, using fallback template.', error);
  }
  return `
    <section class="qvo-shell" role="dialog" aria-modal="true" aria-label="Quantum Vibe Oracle">
      <canvas class="qvo-canvas" data-qvo-canvas></canvas>
      <div class="qvo-story-orb" data-qvo-story-orb hidden></div>
      <header class="qvo-topbar"><div><div class="qvo-kicker">Quantum Vibe Oracle</div><h2>量子 vibe 预言机</h2><p data-qvo-question></p></div><div class="qvo-mode-switch"><button type="button" data-qvo-close>理性模式</button><button type="button" class="is-active" data-qvo-poetic>量子诗意模式</button></div></header>
      <aside class="qvo-panel"><div class="qvo-panel-title">三条可漫游多宇宙</div><div class="qvo-universe-list" data-qvo-universe-list></div><div class="qvo-diary" data-qvo-diary></div><div class="qvo-observer"><meter min="0" max="100" value="8" data-qvo-observer-meter></meter><small data-qvo-observer-copy></small><div class="qvo-bio-visuals"><div class="qvo-heart-cluster"><span class="qvo-heartbeat-dot" data-qvo-heartbeat></span><span class="qvo-heartbeat-ring" data-qvo-heartbeat-ring></span></div><svg class="qvo-breath-wave" viewBox="0 0 220 48" preserveAspectRatio="none"><path data-qvo-breath-path d="M0,24 C20,24 30,10 50,10 C70,10 80,38 100,38 C120,38 130,10 150,10 C170,10 180,24 220,24"></path></svg></div><div class="qvo-bio-readout"><span data-qvo-heart></span><span data-qvo-breath></span><span data-qvo-hrv></span></div><div class="qvo-audio-actions"><button type="button" class="qvo-audio-button" data-qvo-audio-toggle>静音量子音景</button><button type="button" class="qvo-audio-button" data-qvo-flight-toggle>开启自由飞行</button></div><div class="qvo-bio-actions"><button type="button" class="qvo-bio-button" data-qvo-bio-enable>允许生物共振</button><button type="button" class="qvo-bio-button" data-qvo-save>保存当前量子状态</button></div></div></aside>
      <footer class="qvo-footer"><span data-qvo-renderer>Renderer: preparing…</span><span>拖拽旋转 · 滚轮缩放 · 点击宇宙卡片飞行</span></footer>
    </section>
  `;
}

function ensureStyles() {
  if (document.getElementById('qvo-style')) return;
  const style = document.createElement('style');
  style.id = 'qvo-style';
  style.textContent = `
    .qvo-root { position: fixed; inset: 0; z-index: 9999; color: #f8fbff; font-family: "Noto Serif SC", "Songti SC", serif; }
    .qvo-shell { position: relative; width: 100%; height: 100%; overflow: hidden; background: radial-gradient(circle at 50% 35%, rgba(78, 42, 142, 0.42), #040511 58%, #010208 100%); isolation: isolate; }
    .qvo-shell::before { content: ""; position: absolute; inset: 0; pointer-events: none; background: radial-gradient(circle at 20% 20%, rgba(46, 219, 209, 0.16), transparent 32%), radial-gradient(circle at 80% 74%, rgba(236, 190, 95, 0.14), transparent 36%), linear-gradient(120deg, rgba(95, 50, 181, 0.18), transparent 46%, rgba(33, 222, 218, 0.1)); mix-blend-mode: screen; }
    .qvo-canvas { position: absolute; inset: 0; width: 100%; height: 100%; display: block; touch-action: none; }
    .qvo-topbar { position: absolute; z-index: 6; top: 22px; left: 22px; right: 22px; display: flex; justify-content: space-between; gap: 18px; align-items: flex-start; pointer-events: none; }
    .qvo-topbar h2 { margin: 4px 0 6px; font-size: clamp(26px, 4vw, 54px); line-height: 1; letter-spacing: 0.08em; text-shadow: 0 0 28px rgba(92, 234, 236, 0.34); }
    .qvo-topbar p { margin: 0; max-width: min(760px, 70vw); color: rgba(233, 240, 255, 0.72); font-size: 13px; letter-spacing: 0.04em; }
    .qvo-kicker, .qvo-panel-title { color: #f3d486; letter-spacing: 0.22em; text-transform: uppercase; font-size: 11px; }
    .qvo-mode-switch { display: flex; flex-wrap: wrap; justify-content: flex-end; gap: 6px; max-width: min(520px, calc(100vw - 44px)); padding: 6px; border: 1px solid rgba(230, 221, 173, 0.2); border-radius: 999px; background: rgba(9, 12, 31, 0.62); backdrop-filter: blur(18px); pointer-events: auto; }
    .qvo-mode-switch button, .qvo-universe-button, .qvo-bio-button, .qvo-audio-button { appearance: none; -webkit-appearance: none; box-sizing: border-box; font: inherit; white-space: nowrap; border: 1px solid rgba(255, 255, 255, 0.14); color: #f8fbff; background: rgba(255, 255, 255, 0.06); border-radius: 999px; padding: 10px 14px; cursor: pointer; transition: transform 0.2s ease, background 0.2s ease, border-color 0.2s ease; }
    .qvo-mode-switch button:hover, .qvo-universe-button:hover, .qvo-bio-button:hover, .qvo-audio-button:hover { transform: translateY(-1px); background: rgba(255, 255, 255, 0.13); border-color: rgba(243, 212, 134, 0.55); }
    .qvo-mode-switch .is-active { background: linear-gradient(135deg, rgba(96, 220, 216, 0.2), rgba(243, 212, 134, 0.22)); border-color: rgba(243, 212, 134, 0.5); }
    .qvo-panel { position: absolute; z-index: 5; right: 18px; top: clamp(128px, 18vh, 156px); width: min(372px, calc(100vw - 32px)); max-height: min(560px, calc(100vh - 176px)); overflow-y: auto; overscroll-behavior: contain; display: grid; align-content: start; gap: 11px; padding: 16px; border: 1px solid rgba(188, 218, 255, 0.18); border-radius: 24px; background: linear-gradient(180deg, rgba(9, 13, 36, 0.82), rgba(5, 8, 24, 0.66)); box-shadow: 0 24px 90px rgba(0, 0, 0, 0.38); backdrop-filter: blur(22px); scrollbar-width: thin; scrollbar-color: rgba(243, 212, 134, 0.42) rgba(255, 255, 255, 0.05); }
    .qvo-panel::-webkit-scrollbar { width: 8px; }
    .qvo-panel::-webkit-scrollbar-thumb { background: rgba(243, 212, 134, 0.42); border-radius: 999px; }
    .qvo-panel::-webkit-scrollbar-track { background: rgba(255,255,255,0.05); border-radius: 999px; }
    .qvo-story-orb[hidden] { display: none !important; }
    .qvo-story-orb { position: absolute; z-index: 4; max-width: 280px; padding: 12px 14px; border-radius: 16px; background: rgba(7, 10, 29, 0.86); border: 1px solid rgba(243, 212, 134, 0.36); box-shadow: 0 18px 48px rgba(0, 0, 0, 0.34); color: rgba(248, 251, 255, 0.92); font-size: 12px; line-height: 1.55; pointer-events: none; transform: translate(-50%, -115%); backdrop-filter: blur(18px); }
    .qvo-universe-list { display: grid; gap: 10px; }
    .qvo-universe-button { width: 100%; max-width: 100%; border-radius: 18px; padding: 12px 13px; text-align: left; display: grid; gap: 6px; color: #f8fbff !important; background: rgba(255, 255, 255, 0.06) !important; }
    .qvo-universe-button strong { display: flex; justify-content: space-between; gap: 10px; font-size: 14px; }
    .qvo-universe-button strong span:first-child { min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    .qvo-universe-button small { color: rgba(237, 243, 255, 0.72); line-height: 1.45; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
    .qvo-universe-button.is-active { background: linear-gradient(135deg, rgba(71, 226, 218, 0.18), rgba(244, 205, 112, 0.18)) !important; border-color: var(--qvo-accent, #f3d486); box-shadow: 0 0 28px rgba(87, 231, 224, 0.12); }
    .qvo-diary { min-height: 96px; max-height: 150px; overflow-y: auto; padding: 13px; border-radius: 18px; color: rgba(246, 248, 255, 0.82); background: rgba(255, 255, 255, 0.055); line-height: 1.58; font-size: 13px; }
    .qvo-diary p { margin: 0 0 8px; }
    .qvo-observer { display: grid; gap: 8px; color: rgba(246, 248, 255, 0.72); font-size: 12px; }
    .qvo-observer meter { width: 100%; height: 10px; }
    .qvo-bio-visuals { display: grid; grid-template-columns: 48px 1fr; gap: 10px; align-items: center; }
    .qvo-heart-cluster { position: relative; width: 42px; height: 42px; display: grid; place-items: center; }
    .qvo-heartbeat-dot, .qvo-heartbeat-ring { position: absolute; inset: 0; border-radius: 50%; }
    .qvo-heartbeat-dot { width: 16px; height: 16px; margin: auto; background: radial-gradient(circle, #fff2d1 0, #f26586 30%, #6426ff 100%); box-shadow: 0 0 18px rgba(242, 101, 134, 0.65); transform-origin: center; animation: qvo-heart-pulse 1.6s ease-in-out infinite; }
    .qvo-heartbeat-ring { border: 1px solid rgba(242, 101, 134, 0.44); animation: qvo-heart-ring 1.6s ease-out infinite; }
    .qvo-breath-wave { width: 100%; height: 42px; display: block; overflow: visible; }
    .qvo-breath-wave path { fill: none; stroke: rgba(86, 231, 224, 0.9); stroke-width: 3; stroke-linecap: round; stroke-linejoin: round; filter: drop-shadow(0 0 12px rgba(86, 231, 224, 0.36)); }
    .qvo-bio-actions, .qvo-audio-actions { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; }
    .qvo-bio-button, .qvo-audio-button { flex: 1; min-width: 0; border-radius: 14px; padding: 9px 11px; font-size: 12px; color: #f8fbff !important; background: rgba(255, 255, 255, 0.06) !important; }
    .qvo-export-button { box-shadow: 0 0 24px rgba(243, 212, 134, 0.18); background: linear-gradient(135deg, rgba(89, 48, 190, 0.32), rgba(243, 212, 134, 0.22)) !important; border-color: rgba(243, 212, 134, 0.46) !important; }
    .qvo-export-backdrop[hidden], .qvo-export-menu[hidden] { display: none !important; }
    .qvo-export-backdrop { position: absolute; inset: 0; z-index: 7; background: rgba(1, 4, 14, 0.46); backdrop-filter: blur(6px); }
    .qvo-export-menu { position: absolute; z-index: 8; right: 26px; bottom: 108px; width: min(360px, calc(100vw - 28px)); display: grid; gap: 14px; padding: 16px; border-radius: 20px; border: 1px solid rgba(243, 212, 134, 0.28); background: linear-gradient(180deg, rgba(8, 12, 34, 0.95), rgba(5, 8, 22, 0.92)); box-shadow: 0 28px 84px rgba(0, 0, 0, 0.45); backdrop-filter: blur(20px); }
    .qvo-export-head p { margin: 6px 0 0; font-size: 12px; line-height: 1.5; color: rgba(236, 243, 255, 0.74); }
    .qvo-export-group { display: grid; gap: 8px; }
    .qvo-export-group > span, .qvo-export-group > label { color: rgba(245, 248, 255, 0.9); font-size: 12px; }
    .qvo-export-mode-list { display: flex; flex-wrap: wrap; gap: 8px; }
    .qvo-export-chip, .qvo-export-menu select, .qvo-export-primary, .qvo-export-secondary { appearance: none; -webkit-appearance: none; font: inherit; color: #f8fbff; background: rgba(255,255,255,0.06); border: 1px solid rgba(255,255,255,0.14); border-radius: 12px; padding: 10px 12px; }
    .qvo-export-chip { cursor: pointer; }
    .qvo-export-chip.is-active { background: linear-gradient(135deg, rgba(86, 231, 224, 0.18), rgba(243, 212, 134, 0.18)); border-color: rgba(243, 212, 134, 0.54); }
    .qvo-export-grid { display: grid; gap: 12px; }
    .qvo-export-check { display: flex; align-items: center; gap: 8px; color: rgba(238, 244, 255, 0.78); font-size: 12px; }
    .qvo-export-actions { display: flex; gap: 10px; }
    .qvo-export-primary { flex: 1; cursor: pointer; background: linear-gradient(135deg, rgba(86, 231, 224, 0.2), rgba(243, 212, 134, 0.22)); border-color: rgba(243, 212, 134, 0.56); }
    .qvo-export-secondary { cursor: pointer; }
    .qvo-bio-readout { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; }
    .qvo-bio-readout span { padding: 8px; border-radius: 12px; background: rgba(255,255,255,0.055); color: rgba(246,248,255,0.78); }
    .qvo-bio-video { width: 1px; height: 1px; opacity: 0; position: absolute; pointer-events: none; }
    .qvo-footer { position: absolute; left: 24px; right: 24px; bottom: 20px; display: flex; justify-content: space-between; gap: 14px; color: rgba(241, 247, 255, 0.66); font-size: 12px; pointer-events: none; }
    .qvo-collapse { position: absolute; inset: 0; z-index: 3; display: grid; place-items: center; background: radial-gradient(circle, rgba(3, 7, 24, 0.22), rgba(3, 5, 18, 0.88)); transition: opacity 1s ease, transform 1s ease; pointer-events: none; }
    .qvo-collapse.is-done { opacity: 0; transform: scale(1.08); }
    .qvo-collapse-core { width: min(44vw, 420px); aspect-ratio: 1; border-radius: 50%; background: radial-gradient(circle, #fff 0 2%, #f5cf77 7%, rgba(47, 234, 224, 0.42) 24%, rgba(128, 72, 255, 0.18) 48%, transparent 72%); filter: blur(0.4px); animation: qvo-collapse-core 2.8s cubic-bezier(.2,.8,.2,1) forwards; box-shadow: 0 0 80px rgba(91, 236, 232, 0.45), inset 0 0 80px rgba(245, 207, 119, 0.28); }
    .qvo-collapse-copy { position: absolute; text-align: center; bottom: 18vh; color: rgba(255,255,255,0.86); }
    .qvo-collapse-copy span { display: block; color: #f3d486; letter-spacing: 0.2em; font-size: 11px; text-transform: uppercase; }
    .qvo-collapse-copy strong { display: block; margin-top: 8px; font-size: clamp(16px, 3vw, 28px); font-weight: 600; }
    @keyframes qvo-collapse-core { 0% { transform: scale(4.2) rotate(0deg); opacity: 0.05; } 58% { transform: scale(0.68) rotate(220deg); opacity: 1; } 100% { transform: scale(1.24) rotate(360deg); opacity: 0; } }
    @keyframes qvo-heart-pulse { 0%, 100% { transform: scale(0.92); } 30% { transform: scale(1.18); } 55% { transform: scale(0.98); } }
    @keyframes qvo-heart-ring { 0% { transform: scale(0.6); opacity: 0.7; } 80% { transform: scale(1.28); opacity: 0; } 100% { opacity: 0; } }
    @media (max-width: 760px) {
      .qvo-topbar { top: 14px; left: 14px; right: 14px; flex-direction: column; }
      .qvo-topbar p { max-width: 100%; }
      .qvo-panel { left: 12px; right: 12px; top: auto; bottom: 72px; width: auto; max-height: 46vh; overflow: auto; border-radius: 20px; }
      .qvo-story-orb { left: 50% !important; right: auto; bottom: 60vh; transform: translateX(-50%); max-width: calc(100vw - 36px); }
      .qvo-export-menu { left: 12px; right: 12px; width: auto; bottom: 82px; }
      .qvo-footer { left: 14px; right: 14px; bottom: 12px; flex-direction: column; gap: 4px; }
      .qvo-mode-switch button { padding: 9px 12px; }
    }
    @media (max-height: 720px) and (min-width: 761px) {
      .qvo-topbar h2 { font-size: clamp(24px, 3.2vw, 42px); }
      .qvo-topbar p { max-width: min(640px, 62vw); }
      .qvo-panel { top: 132px; right: 14px; width: min(340px, calc(100vw - 28px)); max-height: calc(100vh - 154px); gap: 8px; padding: 13px; border-radius: 20px; }
      .qvo-universe-list { gap: 7px; }
      .qvo-universe-button { padding: 9px 11px; border-radius: 15px; }
      .qvo-universe-button strong { font-size: 13px; }
      .qvo-universe-button small { font-size: 11px; line-height: 1.35; -webkit-line-clamp: 1; }
      .qvo-diary { min-height: 70px; max-height: 92px; padding: 10px; font-size: 12px; line-height: 1.42; }
      .qvo-bio-readout { grid-template-columns: 1fr; gap: 6px; }
      .qvo-bio-readout span { padding: 6px 8px; }
      .qvo-audio-actions, .qvo-bio-actions { gap: 6px; grid-template-columns: repeat(2, minmax(0, 1fr)); }
      .qvo-bio-button, .qvo-audio-button { padding: 7px 9px; font-size: 11px; }
      .qvo-footer { bottom: 10px; font-size: 11px; opacity: 0.72; }
    }
  `;
  document.head.appendChild(style);
}

async function loadThreeStack() {
  if (threeStackPromise) return threeStackPromise;
  threeStackPromise = loadThreeExperienceStack();
  return threeStackPromise;

}

async function loadMediaPipeStack() {
  if (mediaPipePromise) return mediaPipePromise;
  mediaPipePromise = import('@mediapipe/tasks-vision');
  return mediaPipePromise;
}

function makeLabelSprite(THREE, text, { color = '#ffffff', width = 640, height = 148 } = {}) {
  const canvas = document.createElement('canvas');
  canvas.width = width;
  canvas.height = height;
  const ctx = canvas.getContext('2d');
  ctx.clearRect(0, 0, width, height);
  ctx.fillStyle = 'rgba(4, 8, 24, 0.58)';
  ctx.strokeStyle = color;
  ctx.lineWidth = 3;
  if (ctx.roundRect) {
    ctx.beginPath();
    ctx.roundRect(10, 14, width - 20, height - 28, 30);
    ctx.fill();
    ctx.stroke();
  } else {
    ctx.fillRect(10, 14, width - 20, height - 28);
    ctx.strokeRect(10, 14, width - 20, height - 28);
  }
  ctx.fillStyle = color;
  ctx.font = '600 38px "Noto Serif SC", serif';
  ctx.textAlign = 'center';
  ctx.fillText(text, width / 2, 64);
  ctx.font = '24px "Noto Serif SC", serif';
  ctx.fillStyle = 'rgba(245, 248, 255, 0.82)';
  ctx.fillText('靠近粒子场 · 读取平行自我故事', width / 2, 104);
  const texture = new THREE.CanvasTexture(canvas);
  const material = new THREE.SpriteMaterial({ map: texture, transparent: true, depthWrite: false });
  const sprite = new THREE.Sprite(material);
  sprite.scale.set(5.7, 1.32, 1);
  return sprite;
}

function createQuantumParticleField(THREE, universe, { budget, collapseUniform, rendererType = 'WebGL' }) {
  const random = createSeededRandom(`${universe.seed}:luxury-particles`);
  const probability = clamp(universe.probability, 1, 95);
  const count = Math.round(clamp(budget * (probability / 100), 1800, budget * 0.7));
  const positions = new Float32Array(count * 3);
  const seeds = new Float32Array(count);
  const scales = new Float32Array(count);
  const phases = new Float32Array(count);
  const colors = new Float32Array(count * 3);
  const color = new THREE.Color(universe.color);
  const gold = new THREE.Color(0xf5d47d);

  for (let i = 0; i < count; i += 1) {
    const radius = 0.8 + random() * (2.4 + probability / 18);
    const theta = random() * Math.PI * 2;
    const phi = Math.acos(2 * random() - 1);
    const disk = universe.recommended ? 0.72 : 1;
    positions[i * 3] = Math.sin(phi) * Math.cos(theta) * radius;
    positions[i * 3 + 1] = Math.cos(phi) * radius * disk + (random() - 0.5) * 1.15;
    positions[i * 3 + 2] = Math.sin(phi) * Math.sin(theta) * radius;
    seeds[i] = random();
    scales[i] = 0.55 + random() * 1.8 + probability / 85;
    phases[i] = random() * Math.PI * 2;
    const mixed = color.clone().lerp(gold, random() * 0.38);
    colors[i * 3] = mixed.r;
    colors[i * 3 + 1] = mixed.g;
    colors[i * 3 + 2] = mixed.b;
  }

  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
  geometry.setAttribute('aSeed', new THREE.BufferAttribute(seeds, 1));
  geometry.setAttribute('aScale', new THREE.BufferAttribute(scales, 1));
  geometry.setAttribute('aPhase', new THREE.BufferAttribute(phases, 1));
  geometry.setAttribute('color', new THREE.BufferAttribute(colors, 3));

  const uniforms = {
    uTime: { value: 0 },
    uObserver: { value: 0.08 },
    uCollapse: collapseUniform,
    uColor: { value: color },
    uProbability: { value: probability / 100 },
    uPixelRatio: { value: Math.min(window.devicePixelRatio || 1, 1.75) },
    uHighlight: { value: 0 },
  };

  const material = rendererType === 'WebGPU'
    ? new THREE.PointsMaterial({
      size: 0.045 + probability / 2500,
      vertexColors: true,
      transparent: true,
      opacity: 0.42 + probability / 180,
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
      attribute float aScale;
      attribute float aPhase;
      uniform float uTime;
      uniform float uObserver;
      uniform float uCollapse;
      uniform float uProbability;
      uniform float uPixelRatio;
      varying float vPulse;
      varying float vSeed;
      void main() {
        vec3 p = position;
        float radial = length(p.xz);
        float waveA = sin(radial * 4.4 - uTime * (1.25 + uProbability) + aPhase);
        float waveB = cos((p.x - p.z) * 2.1 + uTime * 0.85 + aSeed * 6.28318);
        float interference = (waveA + waveB) * 0.22;
        float flicker = smoothstep(0.08, 0.92, fract(aSeed * 17.0 + uTime * (0.08 + uProbability * 0.24)));
        p += normalize(p + vec3(0.001)) * interference * (0.42 + uObserver * 0.9);
        p.y += sin(uTime * 0.6 + aPhase) * 0.22 * (0.4 + uObserver);
        p *= mix(0.08, 1.0 + uObserver * 0.18, uCollapse);
        vec4 mvPosition = modelViewMatrix * vec4(p, 1.0);
        gl_Position = projectionMatrix * mvPosition;
        gl_PointSize = aScale * (72.0 / max(0.35, -mvPosition.z)) * uPixelRatio * (0.72 + uProbability * 1.2 + uHighlight * 0.4) * mix(0.58, 1.05, flicker);
        vPulse = 0.42 + 0.42 * waveA + 0.24 * flicker;
        vSeed = aSeed;
      }
    `,
    fragmentShader: `
      uniform vec3 uColor;
      uniform float uObserver;
      uniform float uProbability;
      uniform float uHighlight;
      varying float vPulse;
      varying float vSeed;
      void main() {
        vec2 uv = gl_PointCoord - vec2(0.5);
        float dist = length(uv);
        if (dist > 0.5) discard;
        float core = smoothstep(0.5, 0.02, dist);
        float halo = smoothstep(0.5, 0.18, dist) * 0.42;
        vec3 gold = vec3(1.0, 0.78, 0.34);
        vec3 cyan = vec3(0.18, 0.94, 0.92);
        vec3 color = mix(uColor, gold, vSeed * 0.32 + uHighlight * 0.14);
        color = mix(color, cyan, max(0.0, uObserver - 0.52) * 0.35);
        float alpha = (core + halo) * (0.24 + uProbability * 0.84 + uObserver * 0.22 + uHighlight * 0.28) * clamp(vPulse, 0.24, 1.2);
        gl_FragColor = vec4(color, alpha);
      }
    `,
  });
  const points = new THREE.Points(geometry, material);
  points.userData.quantumUniforms = uniforms;
  points.userData.spin = 0.1 + probability / 260;
  points.userData.baseProbability = probability;
  points.userData.baseSize = 0.045 + probability / 2500;
  points.userData.baseOpacity = 0.42 + probability / 180;
  return points;
}

function createParallelSelf(THREE, universe) {
  const group = new THREE.Group();
  const bodyMaterial = new THREE.MeshStandardMaterial({
    color: universe.color,
    emissive: universe.color,
    emissiveIntensity: 0.54,
    roughness: 0.28,
    metalness: 0.32,
  });
  const head = new THREE.Mesh(new THREE.SphereGeometry(0.18, 28, 28), bodyMaterial);
  const body = new THREE.Mesh(new THREE.CapsuleGeometry(0.16, 0.52, 8, 20), bodyMaterial);
  head.position.y = 0.52;
  body.position.y = 0.12;
  group.add(head, body);
  const aura = new THREE.Mesh(
    new THREE.SphereGeometry(0.86, 36, 18),
    new THREE.MeshBasicMaterial({ color: universe.color, transparent: true, opacity: 0.09, blending: THREE.AdditiveBlending }),
  );
  group.add(aura);
  const markerGeometry = universe.sceneType === 'exam'
    ? new THREE.OctahedronGeometry(0.18, 0)
    : universe.sceneType === 'work'
      ? new THREE.BoxGeometry(0.26, 0.26, 0.26)
      : new THREE.TetrahedronGeometry(0.22, 0);
  const marker = new THREE.Mesh(markerGeometry, bodyMaterial);
  marker.position.set(0.42, 0.38, 0.08);
  group.add(marker);
  return group;
}

function addWorkScene(THREE, group, material) {
  const desk = new THREE.Mesh(new THREE.BoxGeometry(1.7, 0.12, 0.75), material);
  desk.position.set(-0.45, -0.55, 0.3);
  const screen = new THREE.Mesh(new THREE.BoxGeometry(0.78, 0.46, 0.05), material);
  screen.position.set(-0.45, -0.23, 0.02);
  group.add(desk, screen);
}

function addExamScene(THREE, group, material) {
  for (let i = 0; i < 5; i += 1) {
    const book = new THREE.Mesh(new THREE.BoxGeometry(0.52, 0.06, 0.72), material);
    book.position.set(-0.8 + i * 0.4, -0.45 + i * 0.04, 0.18 - i * 0.1);
    book.rotation.y = i * 0.18;
    group.add(book);
  }
}

function createUniverseGroup(THREE, universe, { budget, collapseUniform, rendererType }) {
  const group = new THREE.Group();
  group.position.set(...universe.position);
  group.userData.universe = universe;
  const color = new THREE.Color(universe.color);
  const core = new THREE.Mesh(
    new THREE.IcosahedronGeometry(0.58 + universe.probability / 120, 2),
    new THREE.MeshStandardMaterial({
      color,
      emissive: color,
      emissiveIntensity: 0.86,
      roughness: 0.16,
      metalness: 0.38,
      transparent: true,
      opacity: 0.82,
    }),
  );
  group.add(core);
  const ringMaterial = new THREE.MeshBasicMaterial({ color, transparent: true, opacity: 0.32, blending: THREE.AdditiveBlending, depthWrite: false });
  for (let i = 0; i < 4; i += 1) {
    const ring = new THREE.Mesh(new THREE.TorusGeometry(1.3 + i * 0.46, 0.012, 12, 180), ringMaterial.clone());
    ring.rotation.x = Math.PI / 2 + i * 0.38;
    ring.rotation.y = i * 0.44;
    ring.userData.waveSpeed = 0.32 + i * 0.09;
    group.add(ring);
  }
  group.add(createQuantumParticleField(THREE, universe, { budget, collapseUniform, rendererType }));
  const self = createParallelSelf(THREE, universe);
  self.position.set(0, -1.15, 0.28);
  group.add(self);
  const propMaterial = new THREE.MeshStandardMaterial({ color, emissive: color, emissiveIntensity: 0.22, roughness: 0.5, metalness: 0.2, transparent: true, opacity: 0.68 });
  if (universe.sceneType === 'work' || universe.sceneType === 'hybrid') addWorkScene(THREE, group, propMaterial);
  if (universe.sceneType === 'exam' || universe.sceneType === 'hybrid') addExamScene(THREE, group, propMaterial);
  const label = makeLabelSprite(THREE, `${universe.key} · ${universe.shortTitle} · ${Math.round(universe.probability)}%`, { color: universe.accent });
  label.position.set(0, 2.35, 0);
  group.add(label);
  return group;
}

function createProbabilityBridge(THREE, start, end, color) {
  const curve = new THREE.CatmullRomCurve3([
    new THREE.Vector3(...start).add(new THREE.Vector3(0, 0.9, 0)),
    new THREE.Vector3((start[0] + end[0]) / 2, 2.6, -3.2),
    new THREE.Vector3(...end).add(new THREE.Vector3(0, 0.9, 0)),
  ]);
  const geometry = new THREE.BufferGeometry().setFromPoints(curve.getPoints(120));
  const material = new THREE.LineBasicMaterial({ color, transparent: true, opacity: 0.36, blending: THREE.AdditiveBlending });
  return new THREE.Line(geometry, material);
}

class QuantumAudioEngine {
  constructor() {
    this.context = null;
    this.master = null;
    this.filter = null;
    this.reverb = null;
    this.humOscillators = [];
    this.windSource = null;
    this.windGain = null;
    this.chimeTimer = 0;
    this.muted = false;
    this.mode = 'hopeful';
    this.modeLayers = {};
  }

  async start() {
    if (this.context) {
      await this.context.resume?.();
      return;
    }
    const AudioContextClass = window.AudioContext || window.webkitAudioContext;
    if (!AudioContextClass) return;
    this.context = new AudioContextClass();
    this.master = this.context.createGain();
    this.master.gain.value = 0.18;
    this.filter = this.context.createBiquadFilter();
    this.filter.type = 'lowpass';
    this.filter.frequency.value = 820;
    this.filter.Q.value = 0.85;
    this.reverb = this.context.createConvolver();
    this.reverb.buffer = this.createImpulseResponse(2.8, 1.9);
    this.filter.connect(this.reverb);
    this.reverb.connect(this.master);
    this.master.connect(this.context.destination);
    this.createHum();
    this.createWind();
    this.createModeLayers();
    this.scheduleChimes();
    await this.context.resume?.();
  }

  createImpulseResponse(duration = 2, decay = 2) {
    const sampleRate = this.context.sampleRate;
    const length = Math.floor(sampleRate * duration);
    const impulse = this.context.createBuffer(2, length, sampleRate);
    for (let channel = 0; channel < 2; channel += 1) {
      const data = impulse.getChannelData(channel);
      for (let i = 0; i < length; i += 1) {
        data[i] = (Math.random() * 2 - 1) * Math.pow(1 - i / length, decay);
      }
    }
    return impulse;
  }

  createHum() {
    [43.2, 64.8, 97.2].forEach((frequency, index) => {
      const oscillator = this.context.createOscillator();
      const gain = this.context.createGain();
      oscillator.type = index === 0 ? 'sine' : 'triangle';
      oscillator.frequency.value = frequency;
      gain.gain.value = index === 0 ? 0.14 : 0.035;
      oscillator.connect(gain);
      gain.connect(this.filter);
      oscillator.start();
      this.humOscillators.push({ oscillator, gain, baseFrequency: frequency });
    });
  }

  createWind() {
    const length = this.context.sampleRate * 3;
    const buffer = this.context.createBuffer(1, length, this.context.sampleRate);
    const data = buffer.getChannelData(0);
    let last = 0;
    for (let i = 0; i < length; i += 1) {
      last = last * 0.985 + (Math.random() * 2 - 1) * 0.015;
      data[i] = last * 0.85;
    }
    this.windSource = this.context.createBufferSource();
    this.windSource.buffer = buffer;
    this.windSource.loop = true;
    this.windGain = this.context.createGain();
    this.windGain.gain.value = 0.055;
    this.windSource.connect(this.windGain);
    this.windGain.connect(this.filter);
    this.windSource.start();
  }

  createModeLayers() {
    const configs = {
      stable: { type: 'sine', freq: 110, gain: 0.045 },
      hopeful: { type: 'triangle', freq: 147, gain: 0.055 },
      ethereal: { type: 'sine', freq: 294, gain: 0.038 },
    };
    Object.entries(configs).forEach(([key, config]) => {
      const oscillator = this.context.createOscillator();
      const gain = this.context.createGain();
      oscillator.type = config.type;
      oscillator.frequency.value = config.freq;
      gain.gain.value = 0.0001;
      oscillator.connect(gain);
      gain.connect(this.filter);
      oscillator.start();
      this.modeLayers[key] = { oscillator, gain, baseGain: config.gain, baseFreq: config.freq };
    });
  }

  scheduleChimes() {
    const play = () => {
      if (!this.context || this.muted) return;
      const now = this.context.currentTime;
      const oscillator = this.context.createOscillator();
      const gain = this.context.createGain();
      const modes = { stable: [220, 330, 440], hopeful: [247, 370, 554], ethereal: [392, 587, 880] };
      const bank = modes[this.mode] || modes.hopeful;
      oscillator.frequency.value = bank[Math.floor(Math.random() * bank.length)] * (0.98 + Math.random() * 0.04);
      oscillator.type = 'sine';
      gain.gain.setValueAtTime(0.0001, now);
      gain.gain.exponentialRampToValueAtTime(0.085, now + 0.02);
      gain.gain.exponentialRampToValueAtTime(0.0001, now + 1.45);
      oscillator.connect(gain);
      gain.connect(this.filter);
      oscillator.start(now);
      oscillator.stop(now + 1.55);
    };
    this.chimeTimer = window.setInterval(play, 1800 + Math.random() * 900);
  }

  setUniverseMode(mode) {
    this.mode = mode || 'hopeful';
    if (!this.context) return;
    const now = this.context.currentTime;
    const configs = {
      stable: { lowpass: 620, volume: 0.16, ratios: [1, 1.5, 2] },
      hopeful: { lowpass: 980, volume: 0.2, ratios: [1, 1.68, 2.52] },
      ethereal: { lowpass: 1600, volume: 0.14, ratios: [1, 2.25, 3] },
    };
    const config = configs[this.mode] || configs.hopeful;
    this.filter.frequency.linearRampToValueAtTime(config.lowpass, now + 0.8);
    this.master.gain.linearRampToValueAtTime(this.muted ? 0 : config.volume, now + 0.8);
    this.humOscillators.forEach((item, index) => {
      item.oscillator.frequency.linearRampToValueAtTime(item.baseFrequency * config.ratios[index], now + 0.8);
    });
    Object.entries(this.modeLayers).forEach(([key, layer]) => {
      layer.gain.gain.linearRampToValueAtTime(key === this.mode && !this.muted ? layer.baseGain : 0.0001, now + 0.9);
    });
  }

  applyBioFeedback({ breath = 0.5, heartRate = 70, calmness = 0.5 } = {}) {
    if (!this.context) return;
    const now = this.context.currentTime;
    const breathFactor = clamp(breath, 0, 1);
    const heartFactor = clamp((heartRate - 55) / 75, 0, 1);
    const calmFactor = clamp(calmness, 0, 1);
    this.filter.frequency.linearRampToValueAtTime(520 + breathFactor * 1200 - heartFactor * 240, now + 0.18);
    this.master.gain.linearRampToValueAtTime(this.muted ? 0 : clamp(0.12 + calmFactor * 0.12 - heartFactor * 0.04, 0.04, 0.26), now + 0.18);
    this.humOscillators.forEach((item, index) => {
      item.oscillator.detune.linearRampToValueAtTime((heartFactor - calmFactor) * 18 + index * breathFactor * 4, now + 0.18);
    });
    if (this.windGain) this.windGain.gain.linearRampToValueAtTime(0.035 + breathFactor * 0.08, now + 0.18);
    Object.values(this.modeLayers).forEach((layer, index) => {
      layer.oscillator.detune.linearRampToValueAtTime((calmFactor - heartFactor) * 32 + breathFactor * (index + 1) * 9, now + 0.18);
      layer.gain.gain.linearRampToValueAtTime(this.muted ? 0.0001 : clamp(layer.baseGain * (0.72 + calmFactor * 0.42 - heartFactor * 0.16), 0.0001, 0.12), now + 0.18);
    });
  }

  setMuted(muted) {
    this.muted = Boolean(muted);
    if (!this.context || !this.master) return;
    this.master.gain.linearRampToValueAtTime(this.muted ? 0 : 0.18, this.context.currentTime + 0.2);
    Object.values(this.modeLayers).forEach((layer) => {
      layer.gain.gain.linearRampToValueAtTime(this.muted ? 0.0001 : layer.baseGain, this.context.currentTime + 0.2);
    });
  }

  stop() {
    window.clearInterval(this.chimeTimer);
    this.humOscillators.forEach((item) => item.oscillator.stop?.());
    Object.values(this.modeLayers).forEach((layer) => layer.oscillator.stop?.());
    this.windSource?.stop?.();
    this.context?.close?.();
    this.context = null;
  }
}

class QuantumBioFeedback {
  constructor({ onSignal, onStatus }) {
    this.onSignal = onSignal;
    this.onStatus = onStatus;
    this.stream = null;
    this.video = null;
    this.canvas = null;
    this.ctx = null;
    this.faceLandmarker = null;
    this.microphoneContext = null;
    this.microphoneAnalyser = null;
    this.microphoneData = null;
    this.raf = 0;
    this.lastVideoTime = -1;
    this.brightnessSamples = [];
  }

  async start() {
    if (!navigator.mediaDevices?.getUserMedia) throw new Error('当前浏览器不支持摄像头/麦克风生物反馈。');
    this.stream = await navigator.mediaDevices.getUserMedia({
      video: { facingMode: 'user', width: { ideal: 320 }, height: { ideal: 240 } },
      audio: { echoCancellation: true, noiseSuppression: true },
    });
    this.video = document.createElement('video');
    this.video.className = 'qvo-bio-video';
    this.video.playsInline = true;
    this.video.muted = true;
    this.video.srcObject = this.stream;
    document.body.appendChild(this.video);
    await this.video.play();
    this.canvas = document.createElement('canvas');
    this.canvas.width = 160;
    this.canvas.height = 120;
    this.ctx = this.canvas.getContext('2d', { willReadFrequently: true });
    await this.startMicrophoneAnalyser();
    await this.tryStartMediaPipe();
    this.onStatus?.(this.faceLandmarker ? 'MediaPipe 面部观测已连接，正在估算呼吸/HRV。' : '摄像头已连接，MediaPipe 模型不可用时使用轻量像素估算。');
    this.loop();
  }

  async startMicrophoneAnalyser() {
    const AudioContextClass = window.AudioContext || window.webkitAudioContext;
    if (!AudioContextClass) return;
    this.microphoneContext = new AudioContextClass();
    const source = this.microphoneContext.createMediaStreamSource(this.stream);
    this.microphoneAnalyser = this.microphoneContext.createAnalyser();
    this.microphoneAnalyser.fftSize = 1024;
    this.microphoneData = new Uint8Array(this.microphoneAnalyser.frequencyBinCount);
    source.connect(this.microphoneAnalyser);
  }

  async tryStartMediaPipe() {
    try {
      const { FaceLandmarker, FilesetResolver } = await loadMediaPipeStack();
      const filesetResolver = await FilesetResolver.forVisionTasks(MEDIAPIPE_WASM_URL);
      this.faceLandmarker = await FaceLandmarker.createFromOptions(filesetResolver, {
        baseOptions: { modelAssetPath: FACE_MODEL_URL, delegate: 'GPU' },
        runningMode: 'VIDEO',
        numFaces: 1,
      });
    } catch (error) {
      console.warn('MediaPipe optional bio resonance unavailable; using pixel/audio fallback.', error);
      this.faceLandmarker = null;
    }
  }

  estimateMicrophoneBreath() {
    if (!this.microphoneAnalyser || !this.microphoneData) return 0.5;
    this.microphoneAnalyser.getByteFrequencyData(this.microphoneData);
    let low = 0;
    for (let i = 0; i < Math.min(18, this.microphoneData.length); i += 1) low += this.microphoneData[i];
    return clamp(low / (18 * 255), 0, 1);
  }

  estimateFaceSignal() {
    if (!this.video || !this.ctx) return { brightness: 0.5, posture: 0.5 };
    this.ctx.drawImage(this.video, 0, 0, this.canvas.width, this.canvas.height);
    const pixels = this.ctx.getImageData(48, 30, 64, 48).data;
    let total = 0;
    for (let i = 0; i < pixels.length; i += 4) total += (pixels[i] + pixels[i + 1] + pixels[i + 2]) / 3;
    const brightness = total / (pixels.length / 4) / 255;
    let posture = 0.5;
    if (this.faceLandmarker && this.video.currentTime !== this.lastVideoTime) {
      this.lastVideoTime = this.video.currentTime;
      try {
        const result = this.faceLandmarker.detectForVideo(this.video, performance.now());
        const face = result.faceLandmarks?.[0];
        if (face?.length) {
          const leftEye = face[33] || face[159];
          const rightEye = face[263] || face[386];
          if (leftEye && rightEye) posture = clamp(1 - Math.abs(leftEye.y - rightEye.y) * 10, 0, 1);
        }
      } catch (error) {
        console.warn('MediaPipe frame failed:', error);
      }
    }
    return { brightness, posture };
  }

  estimateHeartRate(brightness) {
    const now = performance.now();
    this.brightnessSamples.push({ t: now, v: brightness });
    this.brightnessSamples = this.brightnessSamples.filter((item) => now - item.t < 9000);
    if (this.brightnessSamples.length < 24) return 70;
    const values = this.brightnessSamples.map((item) => item.v);
    const mean = values.reduce((sum, item) => sum + item, 0) / values.length;
    let zeroCrossings = 0;
    for (let i = 1; i < values.length; i += 1) {
      if ((values[i - 1] - mean) * (values[i] - mean) < 0) zeroCrossings += 1;
    }
    const durationMinutes = Math.max((this.brightnessSamples.at(-1).t - this.brightnessSamples[0].t) / 60000, 0.05);
    return clamp((zeroCrossings / 2) / durationMinutes, 48, 126);
  }

  loop() {
    const breath = this.estimateMicrophoneBreath();
    const face = this.estimateFaceSignal();
    const heartRate = this.estimateHeartRate(face.brightness);
    const calmness = clamp((face.posture * 0.55) + ((1 - breath) * 0.25) + (1 - clamp((heartRate - 58) / 70, 0, 1)) * 0.2, 0, 1);
    this.onSignal?.({ breath, heartRate, hrv: calmness, posture: face.posture, calmness, source: this.faceLandmarker ? 'mediapipe+microphone' : 'pixel+microphone' });
    this.raf = requestAnimationFrame(() => this.loop());
  }

  stop() {
    cancelAnimationFrame(this.raf);
    this.stream?.getTracks?.().forEach((track) => track.stop());
    this.video?.remove();
    this.microphoneContext?.close?.();
    this.faceLandmarker?.close?.();
  }
}

class QuantumVibeOracle {
  constructor(data, persistedState) {
    this.data = data;
    this.decisionId = getDecisionId(data);
    this.persistedState = persistedState || {};
    this.device = getDeviceProfile();
    this.universes = buildUniverseData(data, this.persistedState);
    this.root = null;
    this.scene = null;
    this.camera = null;
    this.renderer = null;
    this.controls = null;
    this.THREE = null;
    this.raf = 0;
    this.renderPending = false;
    this.startedAt = performance.now();
    this.observerEnergy = safeNumber(this.persistedState.observerEnergy, 8);
    this.bioSignal = { breath: 0.5, heartRate: 70, calmness: 0.5, posture: 0.5, hrv: 0.5 };
    this.flightTarget = null;
    this.activeUniverseId = this.persistedState.activeUniverseId || 'universe-b';
    this.collapseUniform = { value: 0 };
    this.audio = new QuantumAudioEngine();
    this.bioFeedback = null;
    this.saveTimer = 0;
    this.hoveredUniverseId = '';
    this.freeFlightEnabled = false;
    this.keyState = {};
    this.pointerLook = { yaw: 0, pitch: 0 };
    this.pointerState = { lastX: 0, lastY: 0 };
    this.exportState = {
      mode: 'current',
      resolution: '4k',
      universeId: this.activeUniverseId,
      includeMetadata: false,
    };
    this.exportBurstEnergy = 0;
    this.longPressTimer = 0;
    this.longPressOrigin = null;
    this.onPointerMove = this.onPointerMove.bind(this);
    this.onBioSignal = this.onBioSignal.bind(this);
    this.onKeyDown = this.onKeyDown.bind(this);
    this.onKeyUp = this.onKeyUp.bind(this);
  }

  async mount() {
    ensureStyles();
    const template = await loadTemplate();
    this.root = document.createElement('div');
    this.root.className = 'qvo-root';
    this.root.innerHTML = template;
    document.body.appendChild(this.root);
    document.body.style.overflow = 'hidden';
    this.root.querySelector('[data-qvo-question]').textContent = this.data.question || '当前决策';
    this.installExportUi();
    this.renderUniverseButtons();
    this.bindUi();
    this.updateObserverMeter();
    await this.audio.start();
    await this.setupThree();
    this.audio.setUniverseMode(this.getActiveUniverse()?.soundMode || 'hopeful');
    await this.saveState({ openedAt: new Date().toISOString() });
    this.playCollapse();
  }

  bindUi() {
    this.root.querySelector('[data-qvo-close]')?.addEventListener('click', () => this.close());
    this.root.querySelector('[data-qvo-poetic]')?.addEventListener('click', () => showToast('量子诗意模式已开启：继续在宇宙里观测你的选择。', 'info', 1800));
    this.root.querySelector('[data-qvo-topology]')?.addEventListener('click', async () => {
      const data = this.data;
      await this.close();
      await window.openDivineSoulTopology?.(data);
    });
    this.root.querySelector('[data-qvo-audio-toggle]')?.addEventListener('click', (event) => this.toggleAudio(event.currentTarget));
    this.root.querySelector('[data-qvo-flight-toggle]')?.addEventListener('click', (event) => this.toggleFreeFlight(event.currentTarget));
    this.root.querySelector('[data-qvo-bio-enable]')?.addEventListener('click', () => this.enableBioFeedback());
    this.root.querySelector('[data-qvo-save]')?.addEventListener('click', () => this.saveCurrentQuantumState());
    this.root.querySelector('[data-qvo-export-trigger]')?.addEventListener('click', () => this.openExportMenu());
    this.root.querySelector('[data-qvo-export-backdrop]')?.addEventListener('click', () => this.closeExportMenu());
    this.root.querySelector('[data-qvo-export-cancel]')?.addEventListener('click', () => this.closeExportMenu());
    this.root.querySelector('[data-qvo-export-confirm]')?.addEventListener('click', () => this.handleExportRequest());
    this.root.querySelectorAll('[data-qvo-export-mode]').forEach((button) => {
      button.addEventListener('click', () => this.setExportMode(button.dataset.qvoExportMode || 'current'));
    });
    this.root.querySelector('[data-qvo-export-resolution]')?.addEventListener('change', (event) => {
      this.exportState.resolution = event.currentTarget.value || '4k';
    });
    this.root.querySelector('[data-qvo-export-universe]')?.addEventListener('change', (event) => {
      this.exportState.universeId = event.currentTarget.value || this.activeUniverseId;
    });
    this.root.querySelector('[data-qvo-export-meta]')?.addEventListener('change', (event) => {
      this.exportState.includeMetadata = Boolean(event.currentTarget.checked);
    });
    window.addEventListener('pointermove', this.onPointerMove, { passive: true });
    window.addEventListener('clp:observer-bio-signal', this.onBioSignal);
    window.addEventListener('keydown', this.onKeyDown);
    window.addEventListener('keyup', this.onKeyUp);
    this.bindLongPressExport();
    this.saveTimer = window.setInterval(() => this.saveState({ heartbeatAt: new Date().toISOString() }), 8000);
  }

  renderUniverseButtons() {
    const list = this.root.querySelector('[data-qvo-universe-list]');
    if (!list) return;
    list.innerHTML = this.universes.map((universe) => `
      <button type="button" class="qvo-universe-button ${universe.id === this.activeUniverseId ? 'is-active' : ''}" data-qvo-universe="${universe.id}" style="--qvo-accent:${universe.accent}">
        <strong><span>${escapeHtml(universe.title)}</span><span>${Math.round(universe.probability)}%</span></strong>
        <small>${escapeHtml(universe.recommended ? '当前推荐的双轨路径：既稳住现实，也保留向上跃迁。' : universe.diary[0])}</small>
      </button>
    `).join('');
    list.querySelectorAll('[data-qvo-universe]').forEach((button) => button.addEventListener('click', () => this.focusUniverse(button.dataset.qvoUniverse)));
    this.updateDiary(this.activeUniverseId);
  }

  installExportUi() {
    const tools = this.root.querySelector('.qvo-mode-switch');
    if (tools && !tools.querySelector('[data-qvo-topology]')) {
      const button = document.createElement('button');
      button.type = 'button';
      button.dataset.qvoTopology = 'true';
      button.textContent = '神魂拓扑';
      tools.appendChild(button);
    }
    if (tools && !tools.querySelector('[data-qvo-export-trigger]')) {
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'qvo-export-button';
      button.dataset.qvoExportTrigger = 'true';
      button.textContent = '📸 导出量子艺术图';
      tools.appendChild(button);
    }

    if (this.root.querySelector('[data-qvo-export-menu]')) return;

    const dominantUniverse = this.getDominantUniverse()?.id || this.activeUniverseId;
    const exportMount = document.createElement('div');
    exportMount.innerHTML = `
      <div class="qvo-export-backdrop" data-qvo-export-backdrop hidden></div>
      <section class="qvo-export-menu" data-qvo-export-menu hidden>
        <div class="qvo-export-head">
          <div>
            <div class="qvo-panel-title">导出量子艺术图</div>
            <p>保留当前量子粒子、辉光、轨道与生物反馈快照。</p>
          </div>
        </div>
        <div class="qvo-export-group">
          <span>导出模式</span>
          <div class="qvo-export-mode-list">
            <button type="button" class="qvo-export-chip is-active" data-qvo-export-mode="current">当前视角艺术图</button>
            <button type="button" class="qvo-export-chip" data-qvo-export-mode="universe">单宇宙特写</button>
            <button type="button" class="qvo-export-chip" data-qvo-export-mode="poster">量子海报模式</button>
          </div>
        </div>
        <div class="qvo-export-group" data-qvo-export-universe-wrap hidden>
          <label for="qvo-export-universe">特写宇宙</label>
          <select id="qvo-export-universe" data-qvo-export-universe>
            ${this.universes.map((item) => `<option value="${item.id}" ${item.id === dominantUniverse ? 'selected' : ''}>${escapeHtml(item.title)}</option>`).join('')}
          </select>
        </div>
        <div class="qvo-export-grid">
          <label class="qvo-export-group">
            <span>分辨率</span>
            <select data-qvo-export-resolution>
              <option value="2k">2K · 2560×1440</option>
              <option value="4k" selected>4K · 3840×2160</option>
              <option value="8k">8K · 7680×4320</option>
            </select>
          </label>
          <label class="qvo-export-check">
            <input type="checkbox" data-qvo-export-meta>
            <span>把量子状态 JSON 写进 PNG 元数据</span>
          </label>
        </div>
        <div class="qvo-export-actions">
          <button type="button" class="qvo-export-secondary" data-qvo-export-cancel>取消</button>
          <button type="button" class="qvo-export-primary" data-qvo-export-confirm>开始导出</button>
        </div>
      </section>
    `;
    this.root.appendChild(exportMount.firstElementChild);
    this.root.appendChild(exportMount.lastElementChild);
  }

  bindLongPressExport() {
    const canvas = this.root.querySelector('[data-qvo-canvas]');
    if (!canvas) return;
    const clear = () => {
      if (this.longPressTimer) {
        window.clearTimeout(this.longPressTimer);
        this.longPressTimer = 0;
      }
      this.longPressOrigin = null;
    };
    canvas.addEventListener('pointerdown', (event) => {
      this.longPressOrigin = { x: event.clientX, y: event.clientY };
      clearTimeout(this.longPressTimer);
      this.longPressTimer = window.setTimeout(() => {
        this.openExportMenu();
        clear();
      }, 520);
    });
    canvas.addEventListener('pointermove', (event) => {
      if (!this.longPressOrigin) return;
      if (Math.hypot(event.clientX - this.longPressOrigin.x, event.clientY - this.longPressOrigin.y) > 14) clear();
    });
    ['pointerup', 'pointercancel', 'pointerleave'].forEach((type) => canvas.addEventListener(type, clear));
  }

  setExportMode(mode) {
    this.exportState.mode = mode || 'current';
    this.root.querySelectorAll('[data-qvo-export-mode]').forEach((button) => {
      button.classList.toggle('is-active', button.dataset.qvoExportMode === this.exportState.mode);
    });
    const wrap = this.root.querySelector('[data-qvo-export-universe-wrap]');
    if (wrap) wrap.hidden = this.exportState.mode !== 'universe';
  }

  openExportMenu() {
    const backdrop = this.root.querySelector('[data-qvo-export-backdrop]');
    const menu = this.root.querySelector('[data-qvo-export-menu]');
    if (!backdrop || !menu) return;
    backdrop.hidden = false;
    menu.hidden = false;
  }

  closeExportMenu() {
    const backdrop = this.root.querySelector('[data-qvo-export-backdrop]');
    const menu = this.root.querySelector('[data-qvo-export-menu]');
    if (backdrop) backdrop.hidden = true;
    if (menu) menu.hidden = true;
  }

  updateDiary(universeId) {
    this.activeUniverseId = universeId || this.activeUniverseId;
    const universe = this.getActiveUniverse();
    const diary = this.root.querySelector('[data-qvo-diary]');
    if (diary && universe) {
      const values = universe.valueLines.length ? `<br><br>价值锚点：${escapeHtml(universe.valueLines.join(' / '))}` : '';
      const emotion = universe.emotionLines.length ? `<br>情绪镜像：${escapeHtml(universe.emotionLines.join(' / '))}` : '';
      const story = universe.storyHighlights?.length
        ? `<br><br><strong>平行自我日记</strong>${universe.storyHighlights.map((line) => `<p>${escapeHtml(line)}</p>`).join('')}`
        : '';
      diary.innerHTML = universe.diary.map((line) => `<p>${escapeHtml(line)}</p>`).join('') + story + values + emotion;
    }
    this.root.querySelectorAll('[data-qvo-universe]').forEach((button) => {
      button.classList.toggle('is-active', button.dataset.qvoUniverse === this.activeUniverseId);
    });
  }

  getActiveUniverse() {
    return this.universes.find((item) => item.id === this.activeUniverseId) || this.universes[1] || this.universes[0];
  }

  getDominantUniverse() {
    return [...this.universes].sort((left, right) => right.probability - left.probability)[0] || this.getActiveUniverse();
  }

  buildExportFilename(universe) {
    const title = sanitizeFilename(this.data.question || '量子决策');
    const universeLabel = sanitizeFilename(universe?.shortTitle || universe?.title || '当前视角');
    return `量子vibe-${title}-${universeLabel}-${formatExportTimestamp()}.png`;
  }

  async waitForFlightSettle(timeout = 2400) {
    const started = performance.now();
    return new Promise((resolve) => {
      const poll = () => {
        if (!this.flightTarget || performance.now() - started > timeout) {
          resolve();
          return;
        }
        requestAnimationFrame(poll);
      };
      poll();
    });
  }

  triggerExportCelebration() {
    this.exportBurstEnergy = 1;
    showToast('量子粒子正在为这张艺术图聚光…', 'info', 1800);
  }

  async handleExportRequest() {
    const mode = this.exportState.mode || 'current';
    const resolution = getResolutionPreset(this.exportState.resolution);
    const universe = this.universes.find((item) => item.id === (this.exportState.universeId || this.activeUniverseId))
      || this.getActiveUniverse();

    this.closeExportMenu();
    this.triggerExportCelebration();

    if (mode === 'universe') {
      this.focusUniverse(universe.id, { instant: false });
      await this.waitForFlightSettle(2600);
    }

    const snapshotDataUrl = await this.captureCurrentView(resolution.width, resolution.height);
    const finalBlob = mode === 'poster'
      ? await this.buildPosterBlob(snapshotDataUrl, resolution, universe)
      : (
        this.exportState.includeMetadata
          ? injectPngMetadata(snapshotDataUrl, await this.buildQuantumSnapshotMetadata(universe, resolution, mode))
          : new Blob([dataUrlToUint8Array(snapshotDataUrl)], { type: 'image/png' })
      );

    downloadBlob(finalBlob, this.buildExportFilename(mode === 'current' ? this.getDominantUniverse() : universe));
    await this.saveState({ lastExportedAt: new Date().toISOString(), lastExportMode: mode });
    showToast('量子艺术图已保存至下载文件夹 ✨', 'success', 3200);
  }

  async captureCurrentView(width, height) {
    const canvas = this.renderer?.domElement;
    if (!canvas || !this.renderer || !this.camera) throw new Error('量子宇宙尚未完成初始化。');
    const storyOrb = this.root.querySelector('[data-qvo-story-orb]');
    const menu = this.root.querySelector('[data-qvo-export-menu]');
    const backdrop = this.root.querySelector('[data-qvo-export-backdrop]');
    const wasStoryHidden = storyOrb?.hidden;
    if (storyOrb) storyOrb.hidden = true;
    if (menu) menu.hidden = true;
    if (backdrop) backdrop.hidden = true;

    const originalAspect = this.camera.aspect;
    this.renderer.setPixelRatio(1);
    this.renderer.setSize(width, height);
    this.camera.aspect = width / height;
    this.camera.updateProjectionMatrix();
    this.updateSceneFrame((performance.now() - this.startedAt) / 1000);
    await new Promise((resolve) => requestAnimationFrame(resolve));
    this.updateSceneFrame((performance.now() - this.startedAt) / 1000);
    const dataUrl = canvas.toDataURL('image/png', 1.0);

    this.renderer.setPixelRatio(this.device.pixelRatio);
    this.renderer.setSize(window.innerWidth, window.innerHeight);
    this.camera.aspect = originalAspect;
    this.camera.updateProjectionMatrix();
    if (storyOrb) storyOrb.hidden = wasStoryHidden ?? true;
    return dataUrl;
  }

  async buildPosterBlob(baseDataUrl, resolution, universe) {
    const width = resolution.width;
    const height = resolution.height;
    const canvas = document.createElement('canvas');
    canvas.width = width;
    canvas.height = height;
    const ctx = canvas.getContext('2d');
    const image = await loadImageFromDataUrl(baseDataUrl);
    ctx.drawImage(image, 0, 0, width, height);

    const gradient = ctx.createLinearGradient(0, 0, width * 0.72, height);
    gradient.addColorStop(0, 'rgba(5, 8, 24, 0.1)');
    gradient.addColorStop(0.48, 'rgba(5, 8, 24, 0.6)');
    gradient.addColorStop(1, 'rgba(3, 5, 18, 0.92)');
    ctx.fillStyle = gradient;
    ctx.fillRect(0, 0, width, height);

    ctx.fillStyle = '#f3d486';
    ctx.font = `600 ${Math.round(width * 0.018)}px "Noto Serif SC", serif`;
    ctx.fillText('QUANTUM VIBE ORACLE', width * 0.06, height * 0.12);

    ctx.fillStyle = '#f8fbff';
    ctx.font = `700 ${Math.round(width * 0.042)}px "Noto Serif SC", serif`;
    const title = compactText(this.data.question || '当前决策', '当前决策');
    const maxTitleWidth = width * 0.48;
    const words = [];
    let line = '';
    title.split('').forEach((char) => {
      const next = line + char;
      if (ctx.measureText(next).width > maxTitleWidth && line) {
        words.push(line);
        line = char;
      } else {
        line = next;
      }
    });
    if (line) words.push(line);
    words.slice(0, 3).forEach((item, index) => ctx.fillText(item, width * 0.06, height * (0.19 + index * 0.055)));

    const probabilities = this.universes.map((item) => `${item.key} ${Math.round(item.probability)}%`).join(' / ');
    const stats = [
      `当前推荐：${universe.shortTitle}`,
      `Monte Carlo：${probabilities}`,
      `生物反馈：HR ${Math.round(this.bioSignal.heartRate)} · HRV ${Math.round(this.bioSignal.hrv * 100)}% · 呼吸 ${Math.round(this.bioSignal.breath * 100)}%`,
      `粒子总数：${this.device.particleBudget.toLocaleString()}`,
      `导出时间：${new Date().toLocaleString('zh-CN')}`,
    ];
    ctx.font = `500 ${Math.round(width * 0.013)}px "Noto Serif SC", serif`;
    ctx.fillStyle = 'rgba(242, 246, 255, 0.9)';
    stats.forEach((item, index) => ctx.fillText(item, width * 0.06, height * (0.43 + index * 0.038)));

    ctx.strokeStyle = 'rgba(243, 212, 134, 0.72)';
    ctx.lineWidth = Math.max(2, width * 0.0014);
    ctx.strokeRect(width * 0.055, height * 0.095, width * 0.49, height * 0.46);

    const posterDataUrl = canvas.toDataURL('image/png', 1.0);
    return this.exportState.includeMetadata
      ? injectPngMetadata(posterDataUrl, await this.buildQuantumSnapshotMetadata(universe, resolution, 'poster'))
      : new Blob([dataUrlToUint8Array(posterDataUrl)], { type: 'image/png' });
  }

  async buildQuantumSnapshotMetadata(universe, resolution, mode) {
    const persisted = await loadPersistedQuantumState(this.decisionId);
    return {
      kind: 'clp-quantum-snapshot',
      mode,
      resolution,
      decisionId: this.decisionId,
      question: this.data.question,
      activeUniverseId: this.activeUniverseId,
      exportedUniverse: universe?.id || this.activeUniverseId,
      bioSignal: this.bioSignal,
      probabilities: this.universes.map((item) => ({ id: item.id, title: item.title, probability: item.probability })),
      particleBudget: this.device.particleBudget,
      persistedState: persisted,
      exportedAt: new Date().toISOString(),
    };
  }

  async setupThree() {
    const canvas = this.root.querySelector('[data-qvo-canvas]');
    const { THREE, OrbitControls, WebGPURenderer, rendererType } = await loadThreeStack();
    this.THREE = THREE;
    this.scene = new THREE.Scene();
    this.scene.fog = new THREE.FogExp2(0x050510, 0.036);
    this.camera = new THREE.PerspectiveCamera(58, window.innerWidth / window.innerHeight, 0.1, 180);
    this.camera.position.set(0, 4.8, 13);
    try {
      if (WebGPURenderer && navigator.gpu) {
        this.renderer = new WebGPURenderer({ canvas, antialias: true, alpha: true });
        await this.renderer.init?.();
        this.rendererType = 'WebGPU';
      } else {
        throw new Error('WebGPU unavailable');
      }
    } catch (error) {
      console.warn('WebGPU renderer failed, falling back to WebGL.', error);
      this.renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true, powerPreference: 'high-performance' });
      this.rendererType = 'WebGL';
    }
    this.renderer.setPixelRatio(this.device.pixelRatio);
    this.renderer.setSize(window.innerWidth, window.innerHeight);
    this.renderer.setClearColor(0x02030b, 1);
    this.root.querySelector('[data-qvo-renderer]').textContent = `Renderer: ${this.rendererType} · 粒子预算 ${this.device.particleBudget.toLocaleString()} · ${rendererType === 'WebGPU' ? 'WebGPU 优先' : 'WebGL fallback'}`;
    this.controls = new OrbitControls(this.camera, canvas);
    this.controls.enableDamping = true;
    this.controls.dampingFactor = 0.06;
    this.controls.autoRotate = true;
    this.controls.autoRotateSpeed = 0.32;
    this.controls.maxDistance = 28;
    this.controls.minDistance = 3.2;
    this.addLights();
    this.addNebula();
    this.addUniverses();
    window.addEventListener('resize', () => this.resize(), { passive: true });
    this.focusUniverse(this.activeUniverseId, { instant: true });
    this.animate();
  }

  addLights() {
    const THREE = this.THREE;
    this.scene.add(new THREE.AmbientLight(0x7380ff, 0.46));
    const key = new THREE.PointLight(0xf5d47d, 2.4, 42);
    key.position.set(0, 5, 4);
    this.scene.add(key);
    const cyan = new THREE.PointLight(0x32efe0, 1.8, 34);
    cyan.position.set(-8, 3, 6);
    this.scene.add(cyan);
  }

  addNebula() {
    const THREE = this.THREE;
    const random = createSeededRandom(`${this.decisionId}:nebula`);
    const count = this.device.lowPower ? 1200 : 2600;
    const positions = new Float32Array(count * 3);
    const colors = new Float32Array(count * 3);
    const palette = [new THREE.Color(0x3721a7), new THREE.Color(0x2feee6), new THREE.Color(0xf4cf73)];
    for (let i = 0; i < count; i += 1) {
      positions[i * 3] = (random() - 0.5) * 68;
      positions[i * 3 + 1] = (random() - 0.5) * 26;
      positions[i * 3 + 2] = (random() - 0.5) * 68;
      const color = palette[Math.floor(random() * palette.length)].clone().multiplyScalar(0.35 + random() * 0.75);
      colors[i * 3] = color.r;
      colors[i * 3 + 1] = color.g;
      colors[i * 3 + 2] = color.b;
    }
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
    geometry.setAttribute('color', new THREE.BufferAttribute(colors, 3));
    const material = new THREE.PointsMaterial({ size: 0.045, vertexColors: true, transparent: true, opacity: 0.72, blending: THREE.AdditiveBlending, depthWrite: false });
    this.nebula = new THREE.Points(geometry, material);
    this.scene.add(this.nebula);
  }

  addUniverses() {
    const THREE = this.THREE;
    this.universeGroups = this.universes.map((universe) => createUniverseGroup(THREE, universe, {
      budget: this.device.particleBudget,
      collapseUniform: this.collapseUniform,
      rendererType: this.rendererType,
    }));
    this.universeGroups.forEach((group) => this.scene.add(group));
    this.scene.add(createProbabilityBridge(THREE, this.universes[0].position, this.universes[1].position, 0x46e5ff));
    this.scene.add(createProbabilityBridge(THREE, this.universes[1].position, this.universes[2].position, 0xf5cf73));
  }

  focusUniverse(universeId, { instant = false } = {}) {
    const universe = this.universes.find((item) => item.id === universeId) || this.universes[1];
    this.updateDiary(universe.id);
    this.audio.setUniverseMode(universe.soundMode);
    const THREE = this.THREE;
    if (!THREE || !this.camera) return;
    const target = new THREE.Vector3(...universe.position);
    const closeIn = this.freeFlightEnabled ? new THREE.Vector3(0, 1.55, 2.45) : new THREE.Vector3(0, 2.6, 5.4);
    this.flightTarget = { position: target.clone().add(closeIn), lookAt: target };
    if (instant) {
      this.camera.position.copy(this.flightTarget.position);
      this.controls.target.copy(this.flightTarget.lookAt);
      this.controls.update();
    }
    this.saveState({ activeUniverseId: universe.id });
  }

  toggleAudio(button) {
    this.audio.setMuted(!this.audio.muted);
    if (button) button.textContent = this.audio.muted ? '开启量子音景' : '静音量子音景';
  }

  toggleFreeFlight(button) {
    this.freeFlightEnabled = !this.freeFlightEnabled;
    this.controls.enablePan = !this.freeFlightEnabled;
    this.controls.autoRotate = !this.freeFlightEnabled;
    if (button) button.textContent = this.freeFlightEnabled ? '退出自由飞行' : '开启自由飞行';
    showToast(this.freeFlightEnabled ? '自由飞行已开启：WASD / QE / Shift 可穿梭量子宇宙。' : '已回到轨道漫游模式。', 'info', 2200);
  }

  async saveCurrentQuantumState() {
    await this.saveState({ savedManuallyAt: new Date().toISOString() });
    showToast('当前量子状态已保存。', 'success', 2200);
  }

  onKeyDown(event) {
    if (!this.freeFlightEnabled) return;
    this.keyState[event.key.toLowerCase()] = true;
  }

  onKeyUp(event) {
    delete this.keyState[event.key.toLowerCase()];
  }

  async enableBioFeedback() {
    const confirmed = window.confirm('允许使用摄像头和麦克风实现生物共振吗？这是可选体验，仅在本地估算呼吸/HRV，不上传数据。');
    if (!confirmed) return;
    try {
      this.bioFeedback = new QuantumBioFeedback({
        onSignal: (signal) => this.onBioSignal({ detail: signal }),
        onStatus: (message) => this.updateBioCopy(message),
      });
      await this.bioFeedback.start();
      showToast('生物共振已开启：呼吸/心率会轻微扭曲概率场。', 'success', 3200);
    } catch (error) {
      console.warn('Bio feedback failed:', error);
      this.updateBioCopy(`生物共振未开启：${error.message || error}`);
      showToast('没有开启摄像头也没关系，量子宇宙仍可正常使用。', 'warning', 3200);
    }
  }

  updateBioCopy(copy) {
    const label = this.root?.querySelector('[data-qvo-observer-copy]');
    if (label && copy) label.textContent = copy;
  }

  onPointerMove(event) {
    const centerX = window.innerWidth / 2;
    const centerY = window.innerHeight / 2;
    const distance = Math.hypot(event.clientX - centerX, event.clientY - centerY);
    this.observerEnergy = clamp(8 + (distance / Math.max(window.innerWidth, window.innerHeight)) * 80, 5, 96);
    if (this.freeFlightEnabled && event.buttons) {
      const dx = event.clientX - this.pointerState.lastX;
      const dy = event.clientY - this.pointerState.lastY;
      this.pointerLook.yaw -= dx * 0.0025;
      this.pointerLook.pitch = clamp(this.pointerLook.pitch - dy * 0.002, -1.1, 1.1);
    }
    this.pointerState.lastX = event.clientX;
    this.pointerState.lastY = event.clientY;
    this.updateObserverMeter();
    this.detectHoveredUniverse(event.clientX, event.clientY);
  }

  detectHoveredUniverse(clientX, clientY) {
    if (!this.camera || !this.universeGroups?.length) return;
    const THREE = this.THREE;
    let best = null;
    this.universeGroups.forEach((group) => {
      const pos = group.position.clone().project(this.camera);
      const x = (pos.x * 0.5 + 0.5) * window.innerWidth;
      const y = (-pos.y * 0.5 + 0.5) * window.innerHeight;
      const d = Math.hypot(clientX - x, clientY - y);
      if (d < 160 && (!best || d < best.d)) best = { group, d };
    });
    const nextId = best?.group.userData.universe?.id || '';
    if (nextId && nextId !== this.hoveredUniverseId) {
      this.hoveredUniverseId = nextId;
      this.updateDiary(nextId);
      const burst = new THREE.Vector3(...best.group.userData.universe.position);
      this.controls.target.lerp(burst, 0.12);
    }
    if (best?.group?.userData?.universe) {
      this.showStoryOrb(best.group.userData.universe, clientX, clientY);
    } else {
      this.hideStoryOrb();
    }
  }

  showStoryOrb(universe, x, y) {
    const orb = this.root?.querySelector('[data-qvo-story-orb]');
    if (!orb || !universe) return;
    const story = universe.storyHighlights?.[0] || universe.diary?.[0] || '平行时间线正在展开。';
    orb.hidden = false;
    orb.innerHTML = `<strong>${escapeHtml(universe.shortTitle)} · ${Math.round(universe.probability)}%</strong><div>${escapeHtml(story)}</div>`;
    orb.style.left = `${x}px`;
    orb.style.top = `${y}px`;
  }

  hideStoryOrb() {
    const orb = this.root?.querySelector('[data-qvo-story-orb]');
    if (!orb) return;
    orb.hidden = true;
  }

  onBioSignal(event) {
    const signal = event.detail || {};
    this.bioSignal = {
      breath: clamp(safeNumber(signal.breath, this.bioSignal.breath), 0, 1),
      heartRate: clamp(safeNumber(signal.heartRate, this.bioSignal.heartRate), 45, 140),
      hrv: clamp(safeNumber(signal.hrv, signal.calmness || this.bioSignal.hrv), 0, 1),
      posture: clamp(safeNumber(signal.posture, this.bioSignal.posture), 0, 1),
      calmness: clamp(safeNumber(signal.calmness, this.bioSignal.calmness), 0, 1),
      source: signal.source || this.bioSignal.source || 'observer',
    };
    this.observerEnergy = clamp(18 + (1 - this.bioSignal.calmness) * 60 + (this.bioSignal.heartRate - 60) * 0.38, 5, 100);
    this.audio.applyBioFeedback(this.bioSignal);
    this.updateObserverMeter(`${this.bioSignal.source} · 呼吸 ${Math.round(this.bioSignal.breath * 100)} · 心率估算 ${Math.round(this.bioSignal.heartRate)} · 冷静度 ${Math.round(this.bioSignal.calmness * 100)}%`);
  }

  updateObserverMeter(copy) {
    const meter = this.root?.querySelector('[data-qvo-observer-meter]');
    if (meter) meter.value = this.observerEnergy;
    const label = this.root?.querySelector('[data-qvo-observer-copy]');
    if (label && copy) label.textContent = copy;
    const heart = this.root?.querySelector('[data-qvo-heart]');
    const breath = this.root?.querySelector('[data-qvo-breath]');
    const hrv = this.root?.querySelector('[data-qvo-hrv]');
    const heartDot = this.root?.querySelector('[data-qvo-heartbeat]');
    const heartRing = this.root?.querySelector('[data-qvo-heartbeat-ring]');
    const breathPath = this.root?.querySelector('[data-qvo-breath-path]');
    if (heart) heart.textContent = `心率 ${Math.round(this.bioSignal.heartRate)} bpm`;
    if (breath) breath.textContent = `呼吸 ${Math.round(this.bioSignal.breath * 100)}%`;
    if (hrv) hrv.textContent = `HRV ${Math.round(this.bioSignal.hrv * 100)}%`;
    if (heartDot) heartDot.style.animationDuration = `${clamp(1.45 - (this.bioSignal.heartRate - 60) / 180, 0.55, 1.6)}s`;
    if (heartRing) heartRing.style.animationDuration = `${clamp(1.45 - (this.bioSignal.heartRate - 60) / 180, 0.55, 1.6)}s`;
    if (breathPath) {
      const amp = 6 + this.bioSignal.breath * 14;
      const calm = 24 - this.bioSignal.calmness * 7;
      breathPath.setAttribute('d', `M0,24 C20,24 30,${24 - amp} 50,${24 - amp} C70,${24 - amp} 80,${24 + amp} 100,${24 + amp} C120,${24 + amp} 130,${calm - amp * 0.4} 150,${calm - amp * 0.4} C170,${calm - amp * 0.4} 180,24 220,24`);
    }
  }

  animate() {
    const time = (performance.now() - this.startedAt) / 1000;
    this.raf = requestAnimationFrame(() => this.animate());
    this.updateSceneFrame(time);
  }

  updateSceneFrame(time) {
    const collapse = easeOutCubic(time / 2.4);
    this.collapseUniform.value = clamp(collapse, 0, 1);
    this.exportBurstEnergy = Math.max(0, this.exportBurstEnergy - 0.018);
    if (this.nebula) {
      this.nebula.rotation.y += 0.0009 + this.bioSignal.breath * 0.0008 + this.exportBurstEnergy * 0.01;
      this.nebula.rotation.x = Math.sin(time * 0.12) * 0.04;
    }
    const observerPulse = 1 + this.observerEnergy / 750 + this.exportBurstEnergy * 0.9;
    this.universeGroups?.forEach((group, index) => {
      const targetPosition = group.userData.universe?.position || [0, 0, 0];
      const isActive = group.userData.universe?.id === this.activeUniverseId;
      const isHovered = group.userData.universe?.id === this.hoveredUniverseId;
      const bioBoost = group.userData.universe?.recommended ? this.bioSignal.calmness * 0.28 : 0;
      group.position.lerp(new this.THREE.Vector3(...targetPosition).multiplyScalar(collapse), 0.08);
      group.rotation.y += (0.002 + (group.userData.universe?.probability || 30) / 50000) * observerPulse;
      group.scale.lerp(new this.THREE.Vector3(1, 1, 1).multiplyScalar((isActive || isHovered ? 1.08 + bioBoost : 1) * (0.72 + collapse * 0.32 + this.exportBurstEnergy * 0.16)), 0.04);
      group.children.forEach((child) => {
        if (child.userData?.waveSpeed) {
          const pulse = 1 + Math.sin(time * child.userData.waveSpeed + index) * 0.035 * observerPulse + this.exportBurstEnergy * 0.12;
          child.scale.setScalar(pulse);
          child.rotation.z += 0.0025 * observerPulse;
        }
        if (child.isPoints) {
          child.rotation.y += child.userData.spin * 0.002 * observerPulse;
          const uniforms = child.userData.quantumUniforms;
          if (uniforms) {
            uniforms.uTime.value = time;
            uniforms.uObserver.value = clamp(this.observerEnergy / 100 + bioBoost, 0, 1.35);
            uniforms.uPixelRatio.value = this.device.pixelRatio;
            uniforms.uHighlight.value = (isHovered ? 1 : (isActive ? 0.4 : 0)) + this.exportBurstEnergy * 0.8;
          } else {
            child.material.size = child.userData.baseSize * ((isHovered ? 1.38 : (isActive ? 1.14 : 1)) + this.exportBurstEnergy * 0.38);
            child.material.opacity = child.userData.baseOpacity * (isHovered ? 1.28 : 1) + this.exportBurstEnergy * 0.16;
          }
        }
      });
    });
    if (this.freeFlightEnabled && this.camera) {
      const forward = new this.THREE.Vector3();
      this.camera.getWorldDirection(forward);
      const right = new this.THREE.Vector3().crossVectors(forward, new this.THREE.Vector3(0, 1, 0)).normalize();
      const up = new this.THREE.Vector3(0, 1, 0);
      const velocity = new this.THREE.Vector3();
      const speed = (this.keyState.shift ? 0.32 : 0.16) * (0.55 + this.bioSignal.calmness * 0.6);
      if (this.keyState.w) velocity.add(forward);
      if (this.keyState.s) velocity.sub(forward);
      if (this.keyState.a) velocity.sub(right);
      if (this.keyState.d) velocity.add(right);
      if (this.keyState.q) velocity.sub(up);
      if (this.keyState.e) velocity.add(up);
      if (velocity.lengthSq() > 0) {
        velocity.normalize().multiplyScalar(speed);
        this.camera.position.add(velocity);
        this.controls.target.add(velocity);
      }
      const lookDirection = new this.THREE.Vector3(
        Math.sin(this.pointerLook.yaw) * Math.cos(this.pointerLook.pitch),
        Math.sin(this.pointerLook.pitch),
        Math.cos(this.pointerLook.yaw) * Math.cos(this.pointerLook.pitch),
      );
      if (lookDirection.lengthSq() > 0.0001) {
        this.controls.target.copy(this.camera.position.clone().add(lookDirection.multiplyScalar(4.2)));
      }
    }
    if (this.flightTarget) {
      this.camera.position.lerp(this.flightTarget.position, 0.045);
      this.controls.target.lerp(this.flightTarget.lookAt, 0.06);
      if (this.camera.position.distanceTo(this.flightTarget.position) < 0.05) this.flightTarget = null;
    }
    this.controls?.update();
    if (this.renderer?.render) {
      this.renderer.render(this.scene, this.camera);
    }
  }

  playCollapse() {
    this.universeGroups?.forEach((group) => group.position.set(0, 0, 0));
    window.setTimeout(() => this.root?.querySelector('[data-qvo-collapse]')?.classList.add('is-done'), 2400);
    window.setTimeout(() => this.root?.querySelector('[data-qvo-collapse]')?.remove(), 3600);
  }

  resize() {
    if (!this.camera || !this.renderer) return;
    this.camera.aspect = window.innerWidth / window.innerHeight;
    this.camera.updateProjectionMatrix();
    this.renderer.setSize(window.innerWidth, window.innerHeight);
  }

  async saveState(extra = {}) {
    this.persistedState = {
      ...this.persistedState,
      decisionId: this.decisionId,
      activeUniverseId: this.activeUniverseId,
      observerEnergy: this.observerEnergy,
      bioSignal: this.bioSignal,
      visitCount: safeNumber(this.persistedState.visitCount, 0) + 1,
      validationMetrics: extractValidationMetrics(this.data),
      updatedAt: new Date().toISOString(),
      ...extra,
    };
    await savePersistedQuantumState(this.persistedState);
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

  async close() {
    await this.saveState({ closedAt: new Date().toISOString() });
    cancelAnimationFrame(this.raf);
    if (this.saveTimer) window.clearInterval(this.saveTimer);
    window.removeEventListener('pointermove', this.onPointerMove);
    window.removeEventListener('clp:observer-bio-signal', this.onBioSignal);
    window.removeEventListener('keydown', this.onKeyDown);
    window.removeEventListener('keyup', this.onKeyUp);
    this.bioFeedback?.stop();
    this.audio.stop();
    this.controls?.dispose?.();
    if (this.scene) this.disposeObject(this.scene);
    this.renderer?.dispose?.();
    this.root?.remove();
    document.body.style.overflow = '';
    activeOracle = null;
    showToast('已回到理性报告视图。', 'info', 1600);
  }
}

function syncWebglQueryHint() {
  const params = new URLSearchParams(window.location.search);
  if (params.get('webgl') === '1') return;
  params.set('webgl', '1');
  const next = `${window.location.pathname}?${params.toString()}${window.location.hash || ''}`;
  window.history.replaceState({}, '', next);
}

export function registerQuantumVibeOracle() {
  window.openQuantumVibeOracle = async (explicitData) => {
    try {
      if (activeOracle) {
        showToast('量子宇宙已经开启。', 'info', 1600);
        return activeOracle;
      }
      syncWebglQueryHint();
      const decisionData = getCurrentDecisionData(explicitData);
      window.decisionData = decisionData;
      const decisionId = getDecisionId(decisionData);
      const persisted = await loadPersistedQuantumState(decisionId);
      activeOracle = new QuantumVibeOracle(decisionData, persisted);
      await activeOracle.mount();
      return activeOracle;
    } catch (error) {
      console.error('Quantum Vibe Oracle failed to open:', error);
      activeOracle = null;
      showToast(`量子宇宙启动失败：${error.message || error}`, 'error', 5200);
      return null;
    }
  };
  window.closeQuantumVibeOracle = () => activeOracle?.close();
}
