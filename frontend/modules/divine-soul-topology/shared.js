/**
 * 神魂拓扑专用共享摘要
 */

import { compactText, truncateText } from '../art-experience/common.js';
import { extractProbabilities } from '../art-experience/decision-data.js';
import { buildContextHighlights, extractNarrativeEvents } from './blueprint.js';

export function buildCuratorialNotes(data, blueprint, input, filterLabel = '') {
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
      title: truncateText(valueSummary || emotionSummary || `这件雕塑由 ${eventCount} 条人生节点折叠而成`, 24),
      body: truncateText(
        emotionSummary
        || valueSummary
        || '它更像一张内在轮廓图，描述你真正不想失去的秩序。',
        84
      ),
    },
    {
      eyebrow: '命运张力',
      title: truncateText(finalInsight || `当前最强基线概率约 ${Math.round(dominantProbability)}%`, 26),
      body: truncateText(
        nodeLead || nodeSummary
          ? `${nodeLead || '关键节点'}：${nodeSummary || '那会是第一次验证这条路是否真的成立。'}`
          : `当前滤镜为${filterLabel || '灵魂本质'}，它会把命运结构解释成一套缓慢呼吸的几何关系。`,
        90
      ),
    },
    {
      eyebrow: '回撤预案',
      title: truncateText(survivalLead ? `如果${survivalLead}` : '先活下来，再决定值不值', 24),
      body: truncateText(
        survivalSupport
          || '这件作品保留了一条柔软的回撤路径，不把所有意义都压在一次出手上。',
        88
      ),
    },
  ];
}

export { buildContextHighlights };
