/**
 * 神魂拓扑目录入口
 */

import { createDivineSoulTopologyController } from './controller.js';

let activeController = null;

function syncWebglQueryHint() {
  const params = new URLSearchParams(window.location.search);
  if (params.get('webgl') === '1') return;
  params.set('webgl', '1');
  const next = `${window.location.pathname}?${params.toString()}${window.location.hash || ''}`;
  window.history.replaceState({}, '', next);
}

export async function openDivineSoulTopology(explicitData) {
  if (activeController) {
    return activeController;
  }
  syncWebglQueryHint();
  activeController = await createDivineSoulTopologyController(explicitData);
  try {
    await activeController.mount();
    return activeController;
  } catch (error) {
    activeController = null;
    throw error;
  }
}

export async function closeDivineSoulTopology() {
  await activeController?.close();
  activeController = null;
}

export function registerDivineSoulTopology() {
  window.openDivineSoulTopology = openDivineSoulTopology;
  window.closeDivineSoulTopology = closeDivineSoulTopology;
}
