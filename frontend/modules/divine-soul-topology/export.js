/**
 * 神魂拓扑导出链路
 */

import { showToast } from '../utils.js';
import {
  canvasToBlob,
  downloadBlob,
  formatExportTimestamp,
  sanitizeFilename,
} from '../art-experience/common.js';
import { createSoulSculpture } from './render/sculpture.js';

function getResolutionPreset(kind) {
  return {
    '4k': { width: 3840, height: 2160, label: '4K' },
    '8k': { width: 7680, height: 4320, label: '8K' },
  }[kind] || { width: 3840, height: 2160, label: '4K' };
}

async function captureArtworkBlob(controller, width, height) {
  const canvas = controller.renderer?.domElement;
  if (!canvas || !controller.renderer || !controller.camera) {
    throw new Error('雕塑尚未完成初始化。');
  }
  const originalAspect = controller.camera.aspect;
  const originalSize = { width: window.innerWidth, height: window.innerHeight };
  controller.root.classList.add('dst-exporting');
  try {
    controller.renderer.setPixelRatio(1);
    controller.renderer.setSize(width, height);
    controller.composer?.setSize(width, height);
    controller.camera.aspect = width / height;
    controller.camera.updateProjectionMatrix();
    controller.updateSceneFrame(controller.getSceneTime());
    await new Promise((resolve) => requestAnimationFrame(resolve));
    controller.updateSceneFrame(controller.getSceneTime());
    return await canvasToBlob(canvas, 'image/png', 1);
  } finally {
    controller.renderer.setPixelRatio(controller.device.pixelRatio);
    controller.renderer.setSize(originalSize.width, originalSize.height);
    controller.composer?.setSize(originalSize.width, originalSize.height);
    controller.camera.aspect = originalAspect;
    controller.camera.updateProjectionMatrix();
    controller.root.classList.remove('dst-exporting');
  }
}

export async function exportStill(controller, kind) {
  const resolution = getResolutionPreset(kind);
  if (kind === '8k' && controller.device.lowPower) {
    throw new Error('当前设备默认禁用 8K 导出，请使用 4K。');
  }
  const filename = `${sanitizeFilename(controller.data.question, '神魂拓扑')}-神魂拓扑-${resolution.label}-${formatExportTimestamp()}.png`;
  const blob = await captureArtworkBlob(controller, resolution.width, resolution.height);
  downloadBlob(blob, filename);
  showToast(`${resolution.label} 艺术图已导出。`, 'success', 2200);
  await controller.saveState({ lastStillExportAt: new Date().toISOString(), lastStillExportKind: kind });
}

export async function exportLoopVideo(controller) {
  const canvas = controller.renderer?.domElement;
  if (!controller.capability.canRecordVideo || !canvas?.captureStream || typeof MediaRecorder === 'undefined') {
    throw new Error('当前浏览器不支持画布视频导出。');
  }
  const mimeType = [
    'video/webm;codecs=vp9',
    'video/webm;codecs=vp8',
    'video/webm',
  ].find((item) => !MediaRecorder.isTypeSupported || MediaRecorder.isTypeSupported(item)) || 'video/webm';

  const width = 1920;
  const height = 1080;
  const originalPosition = controller.camera.position.clone();
  const originalTarget = controller.controls.target.clone();
  const originalAspect = controller.camera.aspect;
  const originalAutoRotate = controller.controls.autoRotate;
  const originalEnabled = controller.controls.enabled;

  controller.root.classList.add('dst-exporting');
  controller.controls.enabled = false;
  controller.controls.autoRotate = false;
  controller.renderer.setPixelRatio(1);
  controller.renderer.setSize(width, height);
  controller.composer?.setSize(width, height);
  controller.camera.aspect = width / height;
  controller.camera.updateProjectionMatrix();

  const stream = canvas.captureStream(30);
  const recorder = new MediaRecorder(stream, { mimeType });
  const chunks = [];
  recorder.ondataavailable = (event) => {
    if (event.data?.size) chunks.push(event.data);
  };
  const stopped = new Promise((resolve) => {
    recorder.onstop = () => resolve();
  });

  try {
    const center = new controller.THREE.Vector3(0, 0.18, 0);
    const radius = Math.max(6.2, Math.min(controller.blueprint.core.shellRadius * 2.2, 11.5));
    controller.videoCapture = {
      center,
      radius,
      elevation: 2.6,
      startedAt: performance.now(),
      duration: 10000,
    };
    recorder.start(200);
    await new Promise((resolve) => window.setTimeout(resolve, 10200));
    controller.videoCapture = null;
    recorder.stop();
    await stopped;
  } finally {
    controller.videoCapture = null;
    stream.getTracks().forEach((track) => track.stop());
    controller.renderer.setPixelRatio(controller.device.pixelRatio);
    controller.renderer.setSize(window.innerWidth, window.innerHeight);
    controller.composer?.setSize(window.innerWidth, window.innerHeight);
    controller.camera.aspect = originalAspect;
    controller.camera.updateProjectionMatrix();
    controller.camera.position.copy(originalPosition);
    controller.controls.target.copy(originalTarget);
    controller.controls.autoRotate = originalAutoRotate;
    controller.controls.enabled = originalEnabled;
    controller.root.classList.remove('dst-exporting');
  }

  const blob = new Blob(chunks, { type: 'video/webm' });
  const filename = `${sanitizeFilename(controller.data.question, '神魂拓扑')}-神魂拓扑-10s-loop-${formatExportTimestamp()}.webm`;
  downloadBlob(blob, filename);
  showToast('10 秒循环视频已导出。', 'success', 2600);
  await controller.saveState({ lastVideoExportAt: new Date().toISOString() });
}

export async function exportGlb(controller) {
  if (!controller.GLTFExporter || !controller.ParametricGeometry) {
    throw new Error('GLB 导出器尚未加载完成。');
  }
  const exporter = new controller.GLTFExporter();
  const exportGroup = createSoulSculpture(controller.THREE, controller.ParametricGeometry, controller.blueprint, {
    device: controller.device,
    rendererType: 'WebGL',
    includeParticles: false,
  });
  const blob = await new Promise((resolve, reject) => {
    exporter.parse(
      exportGroup,
      (result) => {
        if (result instanceof ArrayBuffer) {
          resolve(new Blob([result], { type: 'model/gltf-binary' }));
        } else {
          resolve(new Blob([JSON.stringify(result)], { type: 'application/json' }));
        }
      },
      (error) => reject(error),
      { binary: true }
    );
  });
  controller.disposeObject(exportGroup);
  const filename = `${sanitizeFilename(controller.data.question, '神魂拓扑')}-神魂拓扑-${formatExportTimestamp()}.glb`;
  downloadBlob(blob, filename);
  showToast('GLB 模型已导出。', 'success', 2200);
  await controller.saveState({ lastGlbExportAt: new Date().toISOString() });
}
