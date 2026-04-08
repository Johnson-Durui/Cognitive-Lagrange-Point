import assert from 'node:assert/strict';
import { compressThinkingLogs } from '../frontend/components/thinking-log-utils.js';

const groups = compressThinkingLogs([
  '⚠️ 自动启动模拟器失败：Engine A 二次检测仍在进行，请先等待最终结论。',
  '⚠️ 自动启动模拟器失败：Engine A 二次检测仍在进行，请先等待最终结论。',
  '⚠️ 自动启动模拟器失败：Engine A 二次检测仍在进行，请先等待最终结论。',
  '⏳ 第二幕建议已形成，Engine A 正在二次检测，检测完成后再决定是否进入未来模拟。',
  '⏳ 第二幕建议已形成，Engine A 正在二次检测，检测完成后再决定是否进入未来模拟。',
  '🔮 第二幕建议已形成，自动进入第三幕未来模拟',
]);

assert.equal(groups.length, 3);
assert.equal(groups[0].count, 3);
assert.equal(groups[0].tone, 'warning');
assert.equal(groups[1].count, 2);
assert.equal(groups[2].count, 1);

console.log(JSON.stringify(groups, null, 2));
