/**
 * 认知拉格朗日点 · Engine A (发现) 模块
 */

import { state, normalizeSystemRecord } from '../core/state.js';
import { requestJson, showToast } from './utils.js';

let lastDiscoveredHash = '';

export async function pollDiscovered() {
  try {
    const payload = await requestJson('/api/discovered');
    const discovered = payload.discovered || payload;
    const hash = JSON.stringify(discovered || {});
    if (hash !== lastDiscoveredHash) {
      lastDiscoveredHash = hash;
      const systems = discovered?.systems || [];
      rebuildDiscoveredNodes(systems);
      if (systems.length > 0 && systems[0].nodes && systems[0].nodes.length > 0) {
        showToast(`发现 ${systems[0].nodes.length} 个新拉格朗日点`, 'success');
      }
    }
  } catch (e) {
    // silently ignore
  }
}

export function rebuildDiscoveredNodes(systems) {
  // 清掉之前注入的 discovered system
  for (let i = state.systems.length - 1; i >= 0; i--) {
    if (state.systems[i]?.id === 'discovered') {
      state.systems.splice(i, 1);
    }
  }
  if (state.hoveredNode?.system?.id === 'discovered') state.hoveredNode = null;
  if (state.selectedNode?.system?.id === 'discovered') state.selectedNode = null;

  if (Array.isArray(systems) && systems.length > 0) {
    const baseIndex = state.systems.length;
    const normalizedSystems = systems.map((system, index) => normalizeSystemRecord(system, baseIndex + index));
    state.systems.push(...normalizedSystems);
  }

  // 重新构建 allNodes
  state.allNodes.length = 0;
  state.systems.forEach(system => {
    if (!system || !Array.isArray(system.nodes)) return;
    system.nodes.forEach(node => {
      state.allNodes.push({
        system,
        data: node,
        wx: 0, wy: 0, sx: 0, sy: 0,
        hovered: false,
        glowIntensity: 0,
        pulsePhase: Math.random() * Math.PI * 2
      });
    });
  });
}
