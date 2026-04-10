/**
 * 神魂拓扑 Three 资源加载
 */

import { loadThreeExperienceStack } from '../../art-experience/three-loader.js';

export function loadDivineThreeStack() {
  return loadThreeExperienceStack({
    needExporter: true,
    needParametricGeometry: true,
    needPostprocessing: true,
  });
}
