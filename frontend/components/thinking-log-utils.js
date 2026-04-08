function normalizeThinkingText(raw) {
  return String(raw ?? '').replace(/\s+/g, ' ').trim();
}

function formatTraceEntry(entry) {
  if (!entry || typeof entry !== 'object') return '';
  const title = normalizeThinkingText(entry.title);
  const detail = normalizeThinkingText(entry.detail);
  if (title && detail) {
    if (detail.startsWith(title)) return detail;
    return `${title}：${detail}`;
  }
  return title || detail;
}

function dedupeLines(lines, { limit = 60 } = {}) {
  const seen = new Set();
  const output = [];
  (Array.isArray(lines) ? lines : []).forEach((line) => {
    const text = normalizeThinkingText(line);
    if (!text || seen.has(text)) return;
    seen.add(text);
    output.push(text);
  });
  if (limit > 0 && output.length > limit) {
    return output.slice(-limit);
  }
  return output;
}

export function getThinkingLogTone(text) {
  const value = normalizeThinkingText(text);
  if (!value) return 'default';
  if (/^(⚠️|⚠|警告)/.test(value) || value.includes('失败')) return 'warning';
  if (/^(❌|🛑)/.test(value) || value.includes('异常') || value.includes('中断')) return 'error';
  if (/^(✅|🔮|🚀|🔴|⏳|🧠|🛰️|📡|⚡|✨)/.test(value)) return 'info';
  return 'default';
}

export function compressThinkingLogs(logs, { limit = 40 } = {}) {
  const groups = [];

  (Array.isArray(logs) ? logs : []).forEach((item) => {
    const text = normalizeThinkingText(item);
    if (!text) return;

    const previous = groups[groups.length - 1];
    if (previous && previous.text === text) {
      previous.count += 1;
      return;
    }

    groups.push({
      text,
      count: 1,
      tone: getThinkingLogTone(text),
    });
  });

  if (limit > 0 && groups.length > limit) {
    return groups.slice(-limit);
  }
  return groups;
}

export function buildThinkingFeed(logs, trace = [], { limit = 48 } = {}) {
  const merged = [
    ...(Array.isArray(logs) ? logs : []),
    ...(Array.isArray(trace) ? trace.map(formatTraceEntry) : []),
  ];
  return dedupeLines(merged, { limit });
}

export function buildThinkingHeadline(logs, trace = [], { phase = '' } = {}) {
  const feed = buildThinkingFeed(logs, trace, { limit: 16 });
  if (feed.length > 0) {
    return feed[feed.length - 1];
  }

  return {
    b2_info_fill: '我在补齐最容易打破平衡的关键事实。',
    b3_cognitive_unlock: '我在切换判断框架，看问题是不是问窄了。',
    b4_experience_sim: '我在找过来人路径，补足现实参照。',
    b5_emotional_mirror: '我在看情绪到底保护了什么，也看它是否拉偏了判断。',
    c1_reevaluation: '我在把前面的线索压成新的力量对比和建议。',
    b6_sim_params: '我在补齐安全垫、固定支出、可逆性和最坏情况。',
    b7_sim_timelines: '我在分别推演两条路的顺风局、平稳局和逆风局。',
    b8_sim_coping: '我在把未来节点拆成红黄绿信号灯和止损预案。',
    b9_sim_comparison: '我在把两条路压缩成可执行的对比和行动地图。',
  }[String(phase || '').trim()] || '系统正在拆解这个问题…';
}

export function buildLoadingNarrative(trace, phase = '', { limit = 4 } = {}) {
  const lines = dedupeLines(Array.isArray(trace) ? trace.map(formatTraceEntry) : [], { limit: Math.max(limit, 8) });
  if (lines.length === 0) {
    const fallback = buildThinkingHeadline([], [], { phase });
    return fallback ? [fallback] : [];
  }
  return lines.slice(-limit);
}
