/**
 * Three / WebGPU / 导出器共享加载器
 */

let stackPromise = null;

export async function loadThreeExperienceStack(options = {}) {
  if (!stackPromise) {
    stackPromise = importThreeStack();
  }
  const stack = await stackPromise;
  return {
    THREE: stack.THREE,
    OrbitControls: stack.OrbitControls,
    WebGPURenderer: stack.WebGPURenderer,
    GLTFExporter: options.needExporter ? stack.GLTFExporter : null,
    ParametricGeometry: options.needParametricGeometry ? stack.ParametricGeometry : null,
    EffectComposer: options.needPostprocessing ? stack.EffectComposer : null,
    RenderPass: options.needPostprocessing ? stack.RenderPass : null,
    UnrealBloomPass: options.needPostprocessing ? stack.UnrealBloomPass : null,
    rendererType: stack.rendererType,
  };
}

async function importThreeStack() {
  let THREE = await import('three');
  let WebGPURenderer = null;
  let rendererType = 'WebGL';
  if (navigator.gpu) {
    try {
      const webgpu = await import('three/webgpu');
      THREE = { ...THREE, ...webgpu };
      WebGPURenderer = webgpu.WebGPURenderer || null;
      rendererType = WebGPURenderer ? 'WebGPU' : 'WebGL';
    } catch (error) {
      console.warn('Three loader: WebGPU unavailable, fallback to WebGL.', error);
    }
  }
  const modules = await Promise.all([
    import('three/addons/controls/OrbitControls.js'),
    import('three/addons/exporters/GLTFExporter.js'),
    import('three/addons/geometries/ParametricGeometry.js'),
    import('three/addons/postprocessing/EffectComposer.js'),
    import('three/addons/postprocessing/RenderPass.js'),
    import('three/addons/postprocessing/UnrealBloomPass.js'),
  ]);
  return {
    THREE,
    WebGPURenderer,
    OrbitControls: modules[0].OrbitControls,
    GLTFExporter: modules[1].GLTFExporter,
    ParametricGeometry: modules[2].ParametricGeometry,
    EffectComposer: modules[3].EffectComposer,
    RenderPass: modules[4].RenderPass,
    UnrealBloomPass: modules[5].UnrealBloomPass,
    rendererType,
  };
}
