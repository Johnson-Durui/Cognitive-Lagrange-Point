/**
 * 量子宇宙入口级懒加载代理
 */

let quantumModulePromise = null;

async function loadQuantumVibeOracleModule() {
  if (!quantumModulePromise) {
    if (window.__CLP_ART_DEBUG__) {
      window.__CLP_ART_DEBUG__.quantumLoadCount = (window.__CLP_ART_DEBUG__.quantumLoadCount || 0) + 1;
    }
    console.debug('[ART] quantum:load:start');
    quantumModulePromise = import('./quantum-vibe-oracle.js').then((module) => {
      if (window.__CLP_ART_DEBUG__) {
        window.__CLP_ART_DEBUG__.quantumModuleLoaded = true;
      }
      console.debug('[ART] quantum:load:done');
      return module;
    });
  }
  return quantumModulePromise;
}

export function registerQuantumVibeOracle() {
  window.openQuantumVibeOracle = async (explicitData) => {
    if (window.__CLP_ART_DEBUG__) {
      window.__CLP_ART_DEBUG__.quantumOpenCount = (window.__CLP_ART_DEBUG__.quantumOpenCount || 0) + 1;
    }
    const module = await loadQuantumVibeOracleModule();
    return module.openQuantumVibeOracle(explicitData);
  };
  window.closeQuantumVibeOracle = async () => {
    if (!quantumModulePromise) return null;
    const module = await loadQuantumVibeOracleModule();
    return module.closeQuantumVibeOracle?.();
  };
}
