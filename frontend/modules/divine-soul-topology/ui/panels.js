/**
 * 神魂拓扑面板渲染
 */

import { escapeHtml } from '../../utils.js';
import { compactText } from '../../art-experience/common.js';
import { buildCuratorialNotes, buildContextHighlights } from '../shared.js';
import { extractNarrativeEvents } from '../blueprint.js';

export function renderContextHighlights(controller) {
  const mount = controller.root?.querySelector('[data-dst-context]');
  if (!mount) return;
  const highlights = buildContextHighlights(controller.data);
  mount.innerHTML = highlights.map((item) => `<span class="dst-context-chip">${escapeHtml(item)}</span>`).join('');
}

export function renderCuratorialNotes(controller) {
  const mount = controller.root?.querySelector('[data-dst-curation]');
  if (!mount) return;
  const notes = buildCuratorialNotes(
    controller.data,
    controller.blueprint,
    controller.getStoryInputProfile(),
    controller.getFilterProfile().label,
  );
  mount.innerHTML = notes.map((item) => `
    <article class="dst-curation-card">
      <div class="dst-curation-eyebrow">${escapeHtml(item.eyebrow)}</div>
      <div class="dst-curation-title">${escapeHtml(item.title)}</div>
      <div class="dst-curation-body">${escapeHtml(item.body)}</div>
    </article>
  `).join('');
}

export function renderVoiceTranscript(controller) {
  const transcript = controller.root?.querySelector('[data-dst-transcript]');
  if (!transcript) return;
  const clipCount = controller.voiceRecordings.length;
  const header = clipCount ? `语音片段 ${clipCount} 段` : '还没有语音片段。';
  const text = compactText(controller.voiceTranscript);
  transcript.innerHTML = text
    ? `<strong>${escapeHtml(header)}</strong><br>${escapeHtml(text)}`
    : escapeHtml(header);
}

export function renderPhotoGrid(controller) {
  const grid = controller.root?.querySelector('[data-dst-photo-grid]');
  const copy = controller.root?.querySelector('[data-dst-photo-copy]');
  if (!grid || !copy) return;
  copy.textContent = controller.photos.length
    ? `已载入 ${controller.photos.length} 张图像，照片色温与对比度会进入雕塑生成参数。`
    : '还没有照片输入。';
  if (!controller.photos.length) {
    grid.innerHTML = '';
    return;
  }
  grid.innerHTML = controller.photos.map((photo) => `
    <div class="dst-photo-card">
      <img src="${photo.dataUrl}" alt="${escapeHtml(photo.name || '神魂照片')}">
      <button type="button" class="dst-photo-remove" data-dst-remove-photo="${photo.id}" aria-label="移除照片">×</button>
      <div class="dst-photo-meta">
        <span>${escapeHtml(photo.name || '未命名照片')}</span>
        <span>亮度 ${Math.round(Number(photo.metrics?.brightness || 0.5) * 100)} · 对比 ${Math.round(Number(photo.metrics?.contrast || 0.3) * 100)}</span>
      </div>
    </div>
  `).join('');
  grid.querySelectorAll('[data-dst-remove-photo]').forEach((button) => {
    button.addEventListener('click', () => {
      controller.photos = controller.photos.filter((item) => item.id !== button.dataset.dstRemovePhoto);
      renderPhotoGrid(controller);
      renderCuratorialNotes(controller);
      renderStats(controller);
    });
  });
}

export function renderStats(controller) {
  const mount = controller.root?.querySelector('[data-dst-stats]');
  if (!mount) return;
  const eventCount = controller.blueprint?.events?.length || extractNarrativeEvents(controller.data, controller.getStoryInputProfile()).length;
  const photoCount = controller.photos.length;
  const voiceCount = controller.voiceRecordings.length;
  const modeLabel = controller.getFilterProfile().label;
  const evolutionMinutes = Math.max(0, Math.round(controller.getSceneTime() / 60));
  const inputLayers = [
    controller.storyText ? '文字' : '',
    controller.voiceRecordings.length ? '声音' : '',
    controller.photos.length ? '图像' : '',
  ].filter(Boolean);
  mount.innerHTML = `
    <div class="dst-stat"><span>几何枝系</span><strong>${eventCount}</strong></div>
    <div class="dst-stat"><span>神性滤镜</span><strong>${escapeHtml(modeLabel)}</strong></div>
    <div class="dst-stat"><span>输入图层</span><strong>${escapeHtml(inputLayers.join(' / ') || '仅上下文')}</strong></div>
    <div class="dst-stat"><span>照片输入</span><strong>${photoCount} 张</strong></div>
    <div class="dst-stat"><span>语音片段</span><strong>${voiceCount} 段</strong></div>
    <div class="dst-stat"><span>演化时长</span><strong>${evolutionMinutes ? `${evolutionMinutes} 分钟` : '刚刚开始'}</strong></div>
    <div class="dst-stat"><span>生成次数</span><strong>${Math.max(controller.generationCount, controller.blueprint ? 1 : 0)}</strong></div>
    <div class="dst-stat"><span>保存状态</span><strong>${controller.lastSavedAt ? '已续写' : '未生成'}</strong></div>
  `;
}

export function updateSaveCopy(controller, copy) {
  const node = controller.root?.querySelector('[data-dst-save-copy]');
  if (node) node.textContent = copy;
}

export function updateRendererCopy(controller, copy) {
  const node = controller.root?.querySelector('[data-dst-renderer-copy]');
  if (node) node.textContent = copy;
}

export function updateFooter(controller, copy) {
  const node = controller.root?.querySelector('[data-dst-footer-copy]');
  if (node) node.textContent = copy;
}

export function updateRitualStage(controller, { phase, copy, stepLabel, mark, progress }) {
  const overlay = controller.root?.querySelector('[data-dst-ritual]');
  if (!overlay) return;
  overlay.hidden = false;
  const phaseNode = overlay.querySelector('[data-dst-ritual-phase]');
  const copyNode = overlay.querySelector('[data-dst-ritual-copy]');
  const stepNode = overlay.querySelector('[data-dst-ritual-step]');
  const markNode = overlay.querySelector('[data-dst-ritual-mark]');
  const fillNode = overlay.querySelector('[data-dst-ritual-fill]');
  if (phaseNode) phaseNode.textContent = phase;
  if (copyNode) copyNode.textContent = copy;
  if (stepNode) stepNode.textContent = stepLabel;
  if (markNode) markNode.textContent = mark;
  if (fillNode) fillNode.style.width = `${Math.round(progress * 100)}%`;
}

export function applyCapabilityState(controller) {
  const { capability, device } = controller;
  const voiceToggle = controller.root?.querySelector('[data-dst-voice-toggle]');
  const videoButton = controller.root?.querySelector('[data-dst-export="video"]');
  const eightKButton = controller.root?.querySelector('[data-dst-export="8k"]');
  const voiceStatus = controller.root?.querySelector('[data-dst-voice-status]');

  if (voiceToggle) {
    voiceToggle.disabled = !capability.canUseVoiceCapture;
    voiceToggle.title = capability.canUseVoiceCapture ? '' : '当前浏览器不支持麦克风输入';
  }
  if (videoButton) {
    videoButton.disabled = !capability.canRecordVideo;
    videoButton.title = capability.canRecordVideo ? '' : '当前浏览器不支持画布视频导出';
  }
  if (eightKButton) {
    const allow8k = !device.lowPower;
    eightKButton.hidden = !allow8k;
    eightKButton.disabled = !allow8k;
    eightKButton.title = allow8k ? '' : '当前设备默认降级隐藏 8K 导出';
  }
  if (voiceStatus && !capability.supportsSpeechRecognition && capability.canUseVoiceCapture) {
    voiceStatus.textContent = '当前浏览器不支持实时转写，仍可录入声音能量生成雕塑。';
  }
  if (voiceStatus && !capability.canUseVoiceCapture) {
    voiceStatus.textContent = '当前浏览器不支持麦克风输入，仍可使用文字与照片生成雕塑。';
  }
}

export function syncFreeFlightUi(controller) {
  const button = controller.root?.querySelector('[data-dst-flight-toggle]');
  if (button) button.textContent = controller.freeFlightEnabled ? '退出自由飞行' : '开启自由飞行';
  controller.root?.classList.toggle('is-free-flight', controller.freeFlightEnabled);
  if (!controller.controls) return;
  controller.controls.enablePan = !controller.freeFlightEnabled;
  controller.controls.autoRotate = !controller.freeFlightEnabled;
  controller.controls.enabled = !controller.freeFlightEnabled;
}
