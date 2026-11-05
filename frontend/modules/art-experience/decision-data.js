/**
 * 决策上下文共享提取器
 */

import { state } from '../../core/state.js';
import { compactText, safeNumber } from './common.js';

export function getDecisionId(data, fallback = 'experience-local') {
  return compactText(
    data?.decision_id
    || data?.id
    || data?.engineb_session?.session_id
    || data?.session_id
    || state.currentDecisionId
    || state.currentDecision?.decision_id
    || fallback
  );
}

export function getCurrentDecisionData(explicitData) {
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

export function extractProbabilities(data) {
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

export function extractValidationMetrics(data) {
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
