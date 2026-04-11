/**
 * 神魂拓扑蓝图生成
 */

import {
  clamp,
  compactText,
  createSeededRandom,
  hashString,
  listify,
  truncateText,
} from '../art-experience/common.js';
import {
  extractProbabilities,
  extractValidationMetrics,
  getDecisionId,
} from '../art-experience/decision-data.js';

function splitNarrative(text) {
  return Array.from(new Set(
    String(text || '')
      .split(/[\n。！？!?;；]+/)
      .map((item) => compactText(item))
      .filter(Boolean)
  ));
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
  return photos.reduce((acc, photo) => {
    const metrics = photo.metrics || {};
    acc.brightness += Number(metrics.brightness || 0.42);
    acc.contrast += Number(metrics.contrast || 0.35);
    acc.saturation += Number(metrics.saturation || 0.35);
    acc.warmth += Number(metrics.warmth || 0.5);
    acc.palette.push(...(Array.isArray(metrics.palette) ? metrics.palette : []));
    return acc;
  }, { brightness: 0, contrast: 0, saturation: 0, warmth: 0, palette: [] });
}

function summarizeVoice(recordings = []) {
  if (!recordings.length) return { energy: 0.22, duration: 0 };
  return recordings.reduce((acc, item) => {
    acc.energy += Number(item.energy || 0.25);
    acc.duration += Number(item.duration || 0);
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

export function buildContextHighlights(data) {
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

export function extractNarrativeEvents(data, input) {
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
  const random = createSeededRandom(`${getDecisionId(data, 'soul-local')}:${input.storyText}:${input.voiceTranscript}`);
  const baseColors = [palette.gold, palette.silver, palette.cyan, palette.violet, palette.spirit];
  return events.map((label, index) => {
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
  }).slice(0, 12);
}

export function buildSoulBlueprint(data, input, previousBlueprint = null) {
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
  const seed = `${getDecisionId(data, 'soul-local')}:${input.storyText}:${input.voiceTranscript}:${JSON.stringify(photo)}:${voice.energy}`;
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
