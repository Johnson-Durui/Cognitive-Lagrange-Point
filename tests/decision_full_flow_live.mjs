const BASE_URL = 'http://127.0.0.1:4173';
const rawArgs = process.argv.slice(2);
let cliTier = '';
let cliQuestion = '';
let cliResumeId = '';

for (let i = 0; i < rawArgs.length; i += 1) {
  const arg = String(rawArgs[i] || '').trim();
  if (!arg) continue;
  if (arg === '--resume') {
    cliResumeId = String(rawArgs[i + 1] || '').trim();
    i += 1;
    continue;
  }
  if (arg === '--tier') {
    cliTier = String(rawArgs[i + 1] || '').trim().toLowerCase();
    i += 1;
    continue;
  }
  if (arg === '--question') {
    cliQuestion = String(rawArgs[i + 1] || '').trim();
    i += 1;
    continue;
  }
  if (!cliTier && ['quick', 'deep', 'pro', 'ultra', 'flash', 'panorama'].includes(arg.toLowerCase())) {
    cliTier = arg.toLowerCase();
    continue;
  }
  if (!cliQuestion) {
    cliQuestion = arg;
  }
}

const REQUESTED_TIER = cliTier || String(process.env.TIER || 'deep').trim().toLowerCase() || 'deep';
const REQUESTED_QUESTION = cliQuestion || String(process.env.QUESTION || '').trim() || '我该不该开Claude';
const FORCE_FRESH_START = Boolean((cliTier || cliQuestion || process.env.TIER || process.env.QUESTION) && !cliResumeId);

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function request(path, options = {}) {
  const response = await fetch(`${BASE_URL}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok || payload.ok === false) {
    throw new Error(payload.error || payload.detail || `HTTP ${response.status}`);
  }
  return payload;
}

function hasUsableAct2State(decision) {
  const session = decision?.engineb_session || {};
  return Boolean(
    Array.isArray(session.diagnosis_questions) && session.diagnosis_questions.length > 0
    || Array.isArray(session.sim_questions) && session.sim_questions.length > 0
    || session.recommendation
    || session.simulator_output
    || (session.phase && session.phase !== 'b1_diagnosis')
    || decision?.phase === 'act3'
  );
}

async function pickLatestRunnableDecision() {
  const payload = await request('/api/decision/history');
  const decisions = Array.isArray(payload.decisions) ? payload.decisions : [];
  const ranked = decisions.filter((item) => item && item.status === 'running');
  ranked.sort((a, b) => String(b.updated_at || '').localeCompare(String(a.updated_at || '')));
  for (const item of ranked) {
    if (!['act3', 'act2', 'act1'].includes(item.phase)) continue;
    const detail = await request(`/api/decision/status?id=${encodeURIComponent(item.decision_id)}`);
    const decision = detail.decision || null;
    if (!decision) continue;
    if (decision.phase === 'act1' || hasUsableAct2State(decision)) {
      return decision;
    }
  }
  return null;
}

async function waitForDecision(decisionId, predicate, {
  timeoutMs = 240000,
  intervalMs = 1500,
  label = 'decision wait',
} = {}) {
  const start = Date.now();
  let lastDecision = null;

  while (Date.now() - start < timeoutMs) {
    const payload = await request(`/api/decision/status?id=${encodeURIComponent(decisionId)}`);
    const decision = payload.decision || null;
    lastDecision = decision;
    if (decision && predicate(decision)) {
      return decision;
    }
    await sleep(intervalMs);
  }

  throw new Error(`${label} 超时。最后状态：${JSON.stringify({
    phase: lastDecision?.phase,
    status: lastDecision?.status,
    step: lastDecision?.step,
    status_text: lastDecision?.status_text,
    engineb_phase: lastDecision?.engineb_session?.phase,
  }, null, 2)}`);
}

function firstAnswerForQuestion(question) {
  const options = Array.isArray(question?.options) ? question.options : [];
  if (options.length > 0) {
    return String(options[0]);
  }
  const text = String(question?.question_text || '');
  if (text.includes('多久') || text.includes('几个月')) return '3个月';
  if (text.includes('最坏') || text.includes('最怕')) return '花了钱但实际没形成持续使用习惯';
  if (text.includes('回头') || text.includes('代价')) return '一周内可以停掉，代价是一点试错成本';
  return '先按保守方案推进';
}

function getRecheckMeta(decision) {
  const session = decision?.engineb_session || {};
  const recheck = session.recheck || {};
  const recheckJob = recheck.job || {};
  const recheckResult = recheckJob.result || {};
  return { recheck, recheckJob, recheckResult };
}

async function answerDiagnosis(decision) {
  let current = decision;
  while (true) {
    const session = current.engineb_session || {};
    const questions = Array.isArray(session.diagnosis_questions) ? session.diagnosis_questions : [];
    const answers = session.diagnosis_answers || {};
    const index = Object.keys(answers).length;
    if (index >= questions.length) {
      return current;
    }
    const question = questions[index];
    const answer = firstAnswerForQuestion(question);
    console.log(`B1 ${index + 1}/${questions.length}: ${question.question_text} -> ${answer}`);
    const payload = await request('/api/decision/answer', {
      method: 'POST',
      body: JSON.stringify({
        decision_id: current.decision_id,
        question_id: question.id,
        answer,
      }),
    });
    current = payload.decision;
  }
}

async function answerSimulator(decision) {
  let current = decision;
  while (true) {
    const session = current.engineb_session || {};
    const questions = Array.isArray(session.sim_questions) ? session.sim_questions : [];
    const answers = session.sim_answers || {};
    const index = Object.keys(answers).length;
    if (index >= questions.length) {
      return current;
    }
    const question = questions[index];
    const answer = firstAnswerForQuestion(question);
    console.log(`SIM ${index + 1}/${questions.length}: ${question.question_text} -> ${answer}`);
    const payload = await request('/api/decision/answer', {
      method: 'POST',
      body: JSON.stringify({
        decision_id: current.decision_id,
        question_id: question.id,
        answer,
      }),
    });
    current = payload.decision;
  }
}

async function main() {
  const resumeDecisionId = cliResumeId || String(process.env.DECISION_ID || '').trim();
  let decision;

  if (resumeDecisionId) {
    const payload = await request(`/api/decision/status?id=${encodeURIComponent(resumeDecisionId)}`);
    decision = payload.decision;
    if (!decision?.decision_id) {
      throw new Error(`找不到要继续的决策：${resumeDecisionId}`);
    }
    console.log('RESUME', decision.decision_id, decision.phase, decision.engineb_session?.phase || '');
  } else {
    const existing = FORCE_FRESH_START ? null : await pickLatestRunnableDecision();
    if (existing?.decision_id) {
      decision = existing;
      console.log('AUTO_RESUME', decision.decision_id, decision.phase, decision.engineb_session?.phase || '');
    } else {
      const startPayload = await request('/api/decision/start', {
        method: 'POST',
        body: JSON.stringify({
          question: REQUESTED_QUESTION,
          tier: REQUESTED_TIER,
        }),
      });

      decision = startPayload.decision;
      console.log('START', decision.decision_id, decision.tier, decision.phase, decision.status_text);
    }
  }

  if (decision.tier === 'quick') {
    if (decision.phase !== 'completed' && decision.status !== 'completed') {
      decision = await waitForDecision(
        decision.decision_id,
        (item) => item.status === 'completed' || item.phase === 'completed' || item.status === 'failed',
        { label: 'wait quick completion', timeoutMs: 180000 },
      );
    }

    if (decision.status === 'failed') {
      throw new Error(`快速流程失败：${decision.error || decision.status_text || 'unknown'}`);
    }

    console.log(JSON.stringify({
      ok: true,
      tier: decision.tier,
      decision_id: decision.decision_id,
      phase: decision.phase,
      status: decision.status,
      summary: decision.result?.summary || '',
      recommendation: decision.result?.recommendation || '',
    }, null, 2));
    return;
  }

  if (decision.phase === 'completed' || decision.status === 'completed') {
    const output = decision.engineb_session?.simulator_output || {};
    console.log(JSON.stringify({
      ok: true,
      tier: decision.tier,
      decision_id: decision.decision_id,
      phase: decision.phase,
      status: decision.status,
      recommendation: decision.engineb_session?.recommendation || '',
      final_insight: output.final_insight || '',
      comparison_summary: output.comparison_summary || '',
      action_map_a_count: Array.isArray(output.action_map_a) ? output.action_map_a.length : 0,
      action_map_b_count: Array.isArray(output.action_map_b) ? output.action_map_b.length : 0,
      resumed_completed: true,
    }, null, 2));
    return;
  }

  const session0 = decision.engineb_session || {};
  if (!session0.diagnosis_questions?.length && !session0.recommendation && decision.phase !== 'act3') {
    decision = await waitForDecision(
      decision.decision_id,
      (item) => {
        const session = item.engineb_session || {};
        return Boolean(
          session.diagnosis_questions?.length
          || hasUsableAct2State(item)
          || item.phase === 'act3'
          || item.phase === 'completed'
          || item.status === 'failed'
        );
      },
      { label: 'wait diagnosis questions' },
    );
    console.log('ACT2_READY', decision.decision_id, decision.engineb_session?.phase || decision.phase);
  }

  if (decision.engineb_session?.diagnosis_questions?.length) {
    decision = await answerDiagnosis(decision);
    console.log('DIAGNOSIS_SUBMITTED', decision.decision_id, decision.engineb_session?.phase);
  }

  if (!decision.engineb_session?.recommendation && decision.phase !== 'act3') {
    decision = await waitForDecision(
      decision.decision_id,
      (item) => {
        const session = item.engineb_session || {};
        return Boolean(
          session.recommendation
          || session.action_plan
          || session.reasoning
          || item.phase === 'act2_complete'
          || item.phase === 'act3'
          || item.status === 'failed'
        );
      },
      { label: 'wait recommendation', timeoutMs: REQUESTED_TIER === 'ultra' || REQUESTED_TIER === 'panorama' ? 600000 : 420000 },
    );
  }

  if (decision.status === 'failed') {
    throw new Error(`第二幕失败：${decision.error || decision.status_text || 'unknown'}`);
  }
  console.log('ACT2_DONE', decision.decision_id, decision.engineb_session?.phase, decision.engineb_session?.recommendation || '');

  const { recheck, recheckResult } = getRecheckMeta(decision);
  if (recheck.status === 'pending' || recheck.status === 'running') {
    decision = await waitForDecision(
      decision.decision_id,
      (item) => {
        const session = item.engineb_session || {};
        const meta = getRecheckMeta(item);
        return Boolean(
          session.sim_questions?.length
          || session.simulator_output
          || item.phase === 'act3'
          || item.status === 'failed'
          || (meta.recheck.status === 'completed' && meta.recheckResult.is_lagrange_point === true)
        );
      },
      { label: 'wait recheck settle', timeoutMs: REQUESTED_TIER === 'ultra' || REQUESTED_TIER === 'panorama' ? 600000 : 420000 },
    );
  } else if (recheck.status === 'completed' && recheckResult.is_lagrange_point === true) {
    console.log(JSON.stringify({
      ok: true,
      tier: decision.tier,
      decision_id: decision.decision_id,
      phase: decision.phase,
      status: decision.status,
      mode: 'recheck_lagrange',
      summary: recheckResult.summary || '',
    }, null, 2));
    return;
  }

  if (!(decision.engineb_session?.sim_questions?.length || decision.engineb_session?.simulator_output)) {
    let simStart = await request('/api/decision/simulate/start', {
      method: 'POST',
      body: JSON.stringify({ decision_id: decision.decision_id }),
    });
    decision = simStart.decision;
    console.log('SIM_START', decision.decision_id, decision.engineb_session?.phase);
  }

  if (decision.engineb_session?.sim_questions?.length) {
    console.log('SIM_READY', decision.decision_id, decision.engineb_session?.phase);
    decision = await answerSimulator(decision);
    console.log('SIM_SUBMITTED', decision.decision_id, decision.engineb_session?.phase);
  } else if (!decision.engineb_session?.simulator_output) {
    decision = await waitForDecision(
      decision.decision_id,
      (item) => Boolean(
        item.engineb_session?.sim_questions?.length
        || item.engineb_session?.simulator_output
        || item.phase === 'completed'
        || item.status === 'failed'
      ),
      { label: 'wait simulator questions', timeoutMs: REQUESTED_TIER === 'ultra' || REQUESTED_TIER === 'panorama' ? 240000 : 180000 },
    );
    if (decision.engineb_session?.sim_questions?.length) {
      console.log('SIM_READY', decision.decision_id, decision.engineb_session?.phase);
      decision = await answerSimulator(decision);
      console.log('SIM_SUBMITTED', decision.decision_id, decision.engineb_session?.phase);
    }
  }

  decision = await waitForDecision(
    decision.decision_id,
    (item) => Boolean(item.engineb_session?.simulator_output) || item.status === 'failed' || item.phase === 'completed',
    { label: 'wait simulator result', timeoutMs: REQUESTED_TIER === 'ultra' || REQUESTED_TIER === 'panorama' ? 600000 : 420000 },
  );

  if (decision.status === 'failed') {
    throw new Error(`第三幕失败：${decision.error || decision.status_text || 'unknown'}`);
  }

  const output = decision.engineb_session?.simulator_output || {};
  console.log(JSON.stringify({
    ok: true,
    tier: decision.tier,
    decision_id: decision.decision_id,
    phase: decision.phase,
    status: decision.status,
    recommendation: decision.engineb_session?.recommendation || '',
    final_insight: output.final_insight || '',
    comparison_summary: output.comparison_summary || '',
    action_map_a_count: Array.isArray(output.action_map_a) ? output.action_map_a.length : 0,
    action_map_b_count: Array.isArray(output.action_map_b) ? output.action_map_b.length : 0,
  }, null, 2));
}

main().catch((error) => {
  console.error(error?.stack || String(error));
  process.exit(1);
});
