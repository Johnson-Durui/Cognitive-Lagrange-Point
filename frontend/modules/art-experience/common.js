/**
 * 艺术体验共享工具
 */

export function clamp(value, min, max) {
  return Math.max(min, Math.min(max, value));
}

export function safeNumber(value, fallback = 0) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}

export function compactText(value, fallback = '') {
  const text = String(value || '').replace(/\s+/g, ' ').trim();
  return text || fallback;
}

export function truncateText(value, limit = 42) {
  const text = compactText(value);
  if (!text) return '';
  return text.length > limit ? `${text.slice(0, limit)}...` : text;
}

export function hashString(input) {
  const text = String(input || '');
  let hash = 2166136261;
  for (let i = 0; i < text.length; i += 1) {
    hash ^= text.charCodeAt(i);
    hash = Math.imul(hash, 16777619);
  }
  return Math.abs(hash >>> 0);
}

export function createSeededRandom(seedText) {
  let seed = hashString(seedText) || 1;
  return () => {
    seed += 0x6D2B79F5;
    let value = seed;
    value = Math.imul(value ^ (value >>> 15), value | 1);
    value ^= value + Math.imul(value ^ (value >>> 7), value | 61);
    return ((value ^ (value >>> 14)) >>> 0) / 4294967296;
  };
}

export function wait(ms) {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

export function getDeviceProfile() {
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

export function easeOutCubic(value) {
  const t = clamp(value, 0, 1);
  return 1 - ((1 - t) ** 3);
}

export function listify(value, limit = 5) {
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
      return [
        `价值排序：${record.top_values.slice(0, 3).map((item) => compactText(item)).filter(Boolean).join(' / ')}`
      ].filter(Boolean).slice(0, limit);
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
        compactText(record.signals?.green?.signal) ? `绿灯信号：${compactText(record.signals.green.signal)}` : '',
      ].filter(Boolean).slice(0, limit);
    }

    if (record.trigger || record.day_1 || record.week_1 || record.safety_runway) {
      return [
        record.trigger ? `最怕发生：${compactText(record.trigger)}` : '',
        record.safety_runway ? `安全垫：${compactText(record.safety_runway)}` : '',
        record.emotional_note ? `情绪预期：${compactText(record.emotional_note)}` : '',
      ].filter(Boolean).slice(0, limit);
    }

    return [
      compactText(record.title),
      compactText(record.label),
      compactText(record.description),
      compactText(record.check),
      compactText(record.signal),
      compactText(record.action),
      compactText(record.content),
      compactText(record.core_insight),
    ].filter(Boolean).slice(0, limit);
  }
  return [compactText(value)].filter(Boolean).slice(0, limit);
}

export function formatExportTimestamp(date = new Date()) {
  const pad = (value) => String(value).padStart(2, '0');
  return `${date.getFullYear()}${pad(date.getMonth() + 1)}${pad(date.getDate())}-${pad(date.getHours())}${pad(date.getMinutes())}${pad(date.getSeconds())}`;
}

export function sanitizeFilename(value, fallback = '艺术体验') {
  return compactText(value, fallback).replace(/[<>:"/\\|?*\u0000-\u001F]+/g, '-');
}

export function dataUrlToUint8Array(dataUrl) {
  const base64 = String(dataUrl).split(',')[1] || '';
  const binary = atob(base64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i += 1) bytes[i] = binary.charCodeAt(i);
  return bytes;
}

export function blobFromDataUrl(dataUrl, type = 'image/png') {
  return new Blob([dataUrlToUint8Array(dataUrl)], { type });
}

export function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 1200);
}

export function readFileAsDataUrl(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result || ''));
    reader.onerror = () => reject(reader.error || new Error('读取文件失败'));
    reader.readAsDataURL(file);
  });
}

export function loadImageFromDataUrl(dataUrl) {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => resolve(img);
    img.onerror = reject;
    img.src = dataUrl;
  });
}

export function canvasToBlob(canvas, type = 'image/png', quality = 1) {
  return new Promise((resolve, reject) => {
    if (!canvas?.toBlob) {
      try {
        resolve(blobFromDataUrl(canvas.toDataURL(type, quality), type));
      } catch (error) {
        reject(error);
      }
      return;
    }
    canvas.toBlob((blob) => {
      if (blob) resolve(blob);
      else reject(new Error('画布导出失败：没有生成 Blob'));
    }, type, quality);
  });
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

export function injectPngMetadata(dataUrl, metadata, keyword = 'CLPArtState') {
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
      chunks.push(buildPngTextChunk(keyword, toBase64Utf8(JSON.stringify(metadata))));
    }
    chunks.push(chunk);
    offset += chunkSize;
  }
  return new Blob([signature, ...chunks], { type: 'image/png' });
}
